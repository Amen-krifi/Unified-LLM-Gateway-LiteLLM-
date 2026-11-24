import os
import sys

import requests

BASE = "http://localhost:5000"
KEY = os.environ.get("LITELLM_MASTER_KEY", "")


def read_metrics():
    r = requests.get(BASE + "/metrics", timeout=10)
    r.raise_for_status()
    return r.text


def total(text, name, **labels):
    """Sum of all samples of `name` whose labels contain the given pairs."""
    s = 0.0
    for line in text.splitlines():
        if not line.startswith(name + "{") and not line.startswith(name + " "):
            continue
        if all(f'{k}="{v}"' in line for k, v in labels.items()):
            s += float(line.rsplit(" ", 1)[1])
    return s


def post(key, question):
    return requests.post(
        BASE + "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"messages": [{"role": "user", "content": question}]},
        timeout=300,
    )


failures = []


def check(label, ok):
    print(("PASS  " if ok else "FAIL  ") + label)
    if not ok:
        failures.append(label)


before = read_metrics()

# 1) a wrong key must count as "unauthorized"
r = post("wrong-key", "What is the capital of France?")
after = read_metrics()
check("wrong key returns 401", r.status_code == 401)
check("unauthorized counter increased by 1",
      total(after, "router_requests_total", department="unknown",
            outcome="unauthorized")
      - total(before, "router_requests_total", department="unknown",
              outcome="unauthorized") == 1)

# 2) a master-key request must be counted and timed
before = read_metrics()
r = post(KEY, "What is the capital of France?")
after = read_metrics()
check("master-key request returns 200", r.status_code == 200)
check("master request counter increased by 1",
      total(after, "router_requests_total", department="master")
      - total(before, "router_requests_total", department="master") == 1)
check("latency histogram count increased",
      total(after, "router_request_latency_seconds_count")
      > total(before, "router_request_latency_seconds_count"))
check("tokens counted for master traffic",
      total(after, "router_tokens_total", department="master")
      > total(before, "router_tokens_total", department="master"))

# 3) no prompt text may appear in the metrics
check("no prompt text in /metrics", "capital of France" not in after)

print()
print("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED")
sys.exit(1 if failures else 0)