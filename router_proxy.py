import os
import time
from collections import defaultdict, deque

import httpx
import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from router import classify

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:4000")
MASTER = os.environ.get("LITELLM_MASTER_KEY", "")
WEBHOOK = os.environ.get("N8N_WEBHOOK_URL", "")
PRICE = {"cheap-model": 0.0000001, "strong-model": 0.00001}  # USD per token

app = FastAPI()
recent = defaultdict(deque)   # department id -> timestamps of the last minute
alerted = set()               # (department id, month) already alerted at 80%


def db():
    return psycopg.connect(host="localhost", port=5432, dbname="llm_gateway",
                           user="postgres", password=os.environ["PGPASSWORD"],
                           autocommit=True)


def last_user_text(messages):
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            return c
    return ""


def get_department(conn, key):
    return conn.execute(
        "select d.id, d.name, d.monthly_budget_usd, d.rpm_limit "
        "from department_keys k join departments d on d.id = k.department_id "
        "where k.api_key = %s", (key,)).fetchone()


def month_spend(conn, dept_id):
    row = conn.execute(
        "select coalesce(sum(cost_usd), 0) from cost_ledger "
        "where department_id = %s and created_at >= date_trunc('month', now())",
        (dept_id,)).fetchone()
    return float(row[0])


def log(conn, dept_id, model, category, tin, tout, cost, status):
    conn.execute(
        "insert into cost_ledger (department_id, model_used, query_category, "
        "tokens_in, tokens_out, cost_usd, status) values (%s,%s,%s,%s,%s,%s,%s)",
        (dept_id, model, category, tin, tout, cost, status))


async def send_alert(dept_id, name, percent):
    key = (dept_id, time.strftime("%Y-%m"))
    if key in alerted:
        return
    alerted.add(key)
    print(f"ALERT: {name} used {percent:.0f}% of its budget")
    if not WEBHOOK:
        print("   (N8N_WEBHOOK_URL not set, alert not sent)")
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(WEBHOOK, json={"department": name,
                                             "percent_used": round(percent, 1)})
    except Exception as e:
        print("   alert failed:", str(e)[:100])


@app.post("/v1/chat/completions")
async def chat(request: Request):
    key = request.headers.get("authorization", "").replace("Bearer ", "").strip()
    body = await request.json()
    category = classify(last_user_text(body.get("messages", [])))
    model = "cheap-model" if category == "simple" else "strong-model"
    body["model"] = model

    conn = db()
    dept = None
    if not (MASTER and key == MASTER):          # master key skips the limits
        dept = get_department(conn, key)
        if dept is None:
            conn.close()
            return JSONResponse({"error": "unknown API key"}, status_code=401)
        dept_id, name, budget, rpm = dept
        budget = float(budget)

        # RPM limit (requests in the last 60 seconds)
        now = time.time()
        q = recent[dept_id]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= rpm:
            log(conn, dept_id, model, category, 0, 0, 0, "failed")
            conn.close()
            return JSONResponse({"error": f"RPM limit reached ({rpm}/min)"},
                                status_code=429)
        q.append(now)

        # Monthly budget limit
        spent = month_spend(conn, dept_id)
        if spent >= budget:
            log(conn, dept_id, model, category, 0, 0, 0, "failed")
            conn.close()
            return JSONResponse(
                {"error": f"monthly budget exceeded ({spent:.4f} of {budget} USD)"},
                status_code=429)

    # Forward to the LiteLLM gateway
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(f"{GATEWAY}/v1/chat/completions", json=body,
                                  headers={"Authorization": f"Bearer {MASTER}"})
        data = r.json()
    except Exception as e:
        if dept:
            log(conn, dept[0], model, category, 0, 0, 0, "failed")
        conn.close()
        return JSONResponse({"error": f"gateway error: {str(e)[:100]}"}, status_code=502)

    resp = JSONResponse(data, status_code=r.status_code)
    resp.headers["X-Route-Category"] = category
    resp.headers["X-Route-Model"] = model

    if dept:
        dept_id, name, budget, rpm = dept
        budget = float(budget)
        if r.status_code == 200:
            answered = "strong-model" if data.get("model") == "strong-model" else "cheap-model"
            usage = data.get("usage", {})
            tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            cost = (tin + tout) * PRICE[answered]
            status = "fallback" if (model == "strong-model" and answered == "cheap-model") else "success"
            log(conn, dept_id, answered, category, tin, tout, cost, status)
        else:
            log(conn, dept_id, model, category, 0, 0, 0, "failed")
        percent = month_spend(conn, dept_id) / budget * 100
        resp.headers["X-Department"] = name
        resp.headers["X-Budget-Used-Pct"] = f"{percent:.1f}"
        if percent >= 80:
            await send_alert(dept_id, name, percent)
    conn.close()
    return resp