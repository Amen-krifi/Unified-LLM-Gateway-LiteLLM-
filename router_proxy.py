import os
import time
from collections import defaultdict, deque

import httpx
import pg8000.native
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)

from router import classify

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:4000")
MASTER = os.environ.get("LITELLM_MASTER_KEY", "")
WEBHOOK = os.environ.get("N8N_WEBHOOK_URL", "")
PRICE = {"cheap-model": 0.0000001, "strong-model": 0.00001}  # USD per token

app = FastAPI()
recent = defaultdict(deque)   # department id -> request timestamps
recent_tokens = defaultdict(deque)  # department id -> (timestamp, token count)
alerted = set()               # (department id, month) already alerted at 80%

# ---------------------------------------------------------------------------
# Prometheus metrics. Metadata only: never prompts, answers or API keys.
# ---------------------------------------------------------------------------
REQUESTS = Counter(
    "router_requests_total", "Requests handled by the router",
    ["department", "category", "outcome"])
LATENCY = Histogram(
    "router_request_latency_seconds", "End-to-end router latency in seconds",
    ["outcome"], buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300))
FALLBACKS = Counter(
    "router_fallbacks_total",
    "Requests sent to strong-model but answered by cheap-model", ["department"])
TOKENS = Counter(
    "router_tokens_total", "Tokens used", ["department", "model", "direction"])
COST = Counter(
    "router_cost_usd_total", "Cost in USD (simulated prices)",
    ["department", "model"])
BUDGET_PCT = Gauge(
    "router_budget_used_percent", "Share of the monthly budget used",
    ["department"])
BUDGET_LIMIT = Gauge(
    "router_budget_limit_usd", "Monthly budget in USD", ["department"])
ALERTS = Counter(
    "router_alerts_total", "Budget alerts by result", ["department", "result"])


def record_request(department, category, outcome, started):
    try:
        REQUESTS.labels(department, category, outcome).inc()
        LATENCY.labels(outcome).observe(time.perf_counter() - started)
    except Exception as e:
        print("metrics error:", str(e)[:100])


def record_usage(department, model, tin, tout, cost, fallback):
    try:
        TOKENS.labels(department, model, "in").inc(tin)
        TOKENS.labels(department, model, "out").inc(tout)
        COST.labels(department, model).inc(cost)
        if fallback:
            FALLBACKS.labels(department).inc()
    except Exception as e:
        print("metrics error:", str(e)[:100])


def record_budget(department, percent, limit):
    try:
        BUDGET_PCT.labels(department).set(percent)
        BUDGET_LIMIT.labels(department).set(limit)
    except Exception as e:
        print("metrics error:", str(e)[:100])


def record_alert(department, result):
    try:
        ALERTS.labels(department, result).inc()
    except Exception as e:
        print("metrics error:", str(e)[:100])


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Database helpers (pg8000, pure Python)
# ---------------------------------------------------------------------------
def db():
    return pg8000.native.Connection(
        host="localhost",
        port=5432,
        database="llm_gateway",
        user="postgres",
        password=os.environ["PGPASSWORD"]
    )


def last_user_text(messages):
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                c = " ".join(
                    p.get("text", "") for p in c if isinstance(p, dict)
                )
            return c
    return ""


def get_department(conn, key):
    rows = conn.run(
        "select d.id, d.name, d.monthly_budget_usd, d.rpm_limit, d.tpm_limit "
        "from department_keys k join departments d on d.id = k.department_id "
        "where k.api_key = :key",
        key=key
    )
    return rows[0] if rows else None


def month_spend(conn, dept_id):
    rows = conn.run(
        "select coalesce(sum(cost_usd), 0) "
        "from cost_ledger "
        "where department_id = :dept_id "
        "and created_at >= date_trunc('month', now())",
        dept_id=dept_id
    )
    return float(rows[0][0])


def log(conn, dept_id, model, category, tin, tout, cost, status):
    conn.run(
        "insert into cost_ledger "
        "(department_id, model_used, query_category, tokens_in, "
        "tokens_out, cost_usd, status) "
        "values (:dept_id, :model, :category, :tin, :tout, :cost, :status)",
        dept_id=dept_id,
        model=model,
        category=category,
        tin=tin,
        tout=tout,
        cost=cost,
        status=status
    )


async def send_alert(dept_id, name, percent):
    key = (dept_id, time.strftime("%Y-%m"))
    if key in alerted:
        return

    alerted.add(key)
    print(f"ALERT: {name} used {percent:.0f}% of its budget")

    if not WEBHOOK:
        print("   (N8N_WEBHOOK_URL not set, alert not sent)")
        record_alert(name, "not_configured")
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                WEBHOOK,
                json={
                    "department": name,
                    "percent_used": round(percent, 1)
                }
            )
        print("   n8n answered:", r.status_code, r.text[:150])
        record_alert(name, "sent" if r.status_code < 300 else "http_error")
    except Exception as e:
        print("   alert failed:", str(e)[:100])
        record_alert(name, "failed")


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------
@app.post("/v1/chat/completions")
async def chat(request: Request):
    started = time.perf_counter()
    key = request.headers.get(
        "authorization", ""
    ).replace("Bearer ", "").strip()

    body = await request.json()
    category = classify(last_user_text(body.get("messages", [])))
    model = "cheap-model" if category == "simple" else "strong-model"
    body["model"] = model

    conn = db()
    dept = None
    dept_name = "master"

    if not (MASTER and key == MASTER):          # master key skips the limits
        dept = get_department(conn, key)

        if dept is None:
            conn.close()
            record_request("unknown", category, "unauthorized", started)
            return JSONResponse(
                {"error": "unknown API key"},
                status_code=401
            )

        dept_id, name, budget, rpm, tpm = dept
        budget = float(budget)
        dept_name = name

        # RPM limit (requests in the last 60 seconds)
        now = time.time()
        q = recent[dept_id]

        while q and now - q[0] > 60:
            q.popleft()

        if len(q) >= rpm:
            log(conn, dept_id, model, category, 0, 0, 0, "failed")
            conn.close()
            record_request(dept_name, category, "rpm_limited", started)
            return JSONResponse(
                {"error": f"RPM limit reached ({rpm}/min)"},
                status_code=429
            )

        # TPM limit (actual tokens used in the last 60 seconds)
        token_q = recent_tokens[dept_id]
        while token_q and now - token_q[0][0] > 60:
            token_q.popleft()

        tokens_used = sum(count for _, count in token_q)
        if tokens_used >= tpm:
            log(conn, dept_id, model, category, 0, 0, 0, "failed")
            conn.close()
            record_request(dept_name, category, "tpm_limited", started)
            return JSONResponse(
                {"error": f"TPM limit reached ({tpm}/min)"},
                status_code=429
            )

        q.append(now)

        # Monthly budget limit
        spent = month_spend(conn, dept_id)

        if spent >= budget:
            log(conn, dept_id, model, category, 0, 0, 0, "failed")
            conn.close()
            record_budget(dept_name, spent / budget * 100, budget)
            record_request(dept_name, category, "budget_exceeded", started)
            return JSONResponse(
                {"error": f"monthly budget exceeded "
                          f"({spent:.4f} of {budget} USD)"},
                status_code=429
            )

    # Forward to the LiteLLM gateway
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(
                f"{GATEWAY}/v1/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {MASTER}"}
            )

        data = r.json()

    except Exception as e:
        if dept:
            log(conn, dept[0], model, category, 0, 0, 0, "failed")

        conn.close()
        record_request(dept_name, category, "gateway_unreachable", started)

        return JSONResponse(
            {"error": f"gateway error: {str(e)[:100]}"},
            status_code=502
        )

    resp = JSONResponse(data, status_code=r.status_code)
    resp.headers["X-Route-Category"] = category
    resp.headers["X-Route-Model"] = model
    outcome = "upstream_error"

    if r.status_code == 200:
        # The gateway may report the model as "mock-frontier" or
        # "strong-model"; only a llama/ollama name means a fallback happened.
        returned = str(data.get("model", "")).lower()
        answered = (
            "cheap-model"
            if ("llama" in returned or "ollama" in returned
                or returned == "cheap-model")
            else "strong-model"
        )

        usage = data.get("usage") or {}
        tin = usage.get("prompt_tokens", 0) or 0
        tout = usage.get("completion_tokens", 0) or 0
        if dept:
            recent_tokens[dept[0]].append((time.time(), tin + tout))
        cost = (tin + tout) * PRICE[answered]
        fallback = model == "strong-model" and answered == "cheap-model"
        outcome = "fallback" if fallback else "success"

        record_usage(dept_name, answered, tin, tout, cost, fallback)
        if dept:
            log(conn, dept[0], answered, category, tin, tout, cost, outcome)
    elif dept:
        log(conn, dept[0], model, category, 0, 0, 0, "failed")

    if dept:
        dept_id, name, budget, rpm, tpm = dept
        budget = float(budget)
        percent = month_spend(conn, dept_id) / budget * 100

        resp.headers["X-Department"] = name
        resp.headers["X-Budget-Used-Pct"] = f"{percent:.1f}"
        record_budget(name, percent, budget)

        if percent >= 80:
            await send_alert(dept_id, name, percent)

    conn.close()
    record_request(dept_name, category, outcome, started)
    return resp