import sys
import requests

key = sys.argv[1] if len(sys.argv) > 1 else "sk-dept-hr-isg2026"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
q = "Compare star and snowflake schemas and recommend one for a retail data warehouse"
for i in range(n):
    r = requests.post("http://localhost:5000/v1/chat/completions",
                      headers={"Authorization": f"Bearer {key}"},
                      json={"messages": [{"role": "user", "content": q}]}, timeout=300)
    try:
        msg = r.json().get("error", "ok")
    except Exception:
        msg = "NOT JSON: " + r.text[:150]
    print(i + 1, "HTTP", r.status_code, "| budget used:",
          r.headers.get("X-Budget-Used-Pct"), "%", "|", msg)