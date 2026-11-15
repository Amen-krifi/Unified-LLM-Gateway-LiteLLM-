import os
import requests

KEY = os.environ.get("LITELLM_MASTER_KEY", "")
questions = [
    "What is the capital of France?",
    "Compare star and snowflake schemas and recommend one for a retail data warehouse",
]
for q in questions:
    r = requests.post(
        "http://localhost:5000/v1/chat/completions",
        headers={"Authorization": f"Bearer {KEY}"},
        json={"messages": [{"role": "user", "content": q}]},
        timeout=300,
    )
    print("Q:", q)
    print("  HTTP", r.status_code, "| category:", r.headers.get("X-Route-Category"),
          "| routed to:", r.headers.get("X-Route-Model"))
    print("  answer:", r.json()["choices"][0]["message"]["content"][:100])
    