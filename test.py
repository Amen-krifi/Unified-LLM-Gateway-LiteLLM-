import os
import sys
import requests

KEY = os.environ.get("LITELLM_MASTER_KEY", "")
model = sys.argv[1] if len(sys.argv) > 1 else "cheap-model"
r = requests.post(
    "http://localhost:4000/v1/chat/completions",
    headers={"Authorization": f"Bearer {KEY}"},
    json={"model": model, "messages": [{"role": "user", "content": "What is the capital of France?"}]},
    timeout=120,
)
print("HTTP", r.status_code)
data = r.json()
print("model:", data.get("model"))
print("answer:", data["choices"][0]["message"]["content"])