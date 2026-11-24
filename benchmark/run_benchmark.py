import re
import time
import pandas as pd
import requests

GATEWAY = "http://localhost:4000/v1/chat/completions"   # ask Person 1
API_KEY = "PASTE_KEY_HERE"                              # never push this to GitHub
PRICE = {"cheap-model": 0.0001, "strong-model": 0.01}   # agree with Person 2

KEYWORDS = ["compare", "analyze", "analyse", "explain", "why", "write code",
            "write a", "recommend", "design", "step by step", "evaluate",
            "assess", "propose", "describe", "plan", "outline", "create",
            "should", "how would", "strategy", "risks", "trade-off"]

def classify(q):
    q = q.lower()
    if len(q.split()) > 35 or any(re.search(r"\b" + re.escape(k) + r"\b", q) for k in KEYWORDS):
        return "complex"
    return "simple"

df = pd.read_csv("benchmark/questions.csv")
rows = []
for _, r in df.iterrows():
    predicted = classify(r["question"])
    model = "strong-model" if predicted == "complex" else "cheap-model"
    try:
        resp = requests.post(
            GATEWAY,
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": model, "messages": [{"role": "user", "content": r["question"]}]},
            timeout=120,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data["usage"]
        tokens = usage["prompt_tokens"] + usage["completion_tokens"]
        status = "success"
        if model == "strong-model" and "[MOCK FRONTIER]" not in text:
            status = "fallback"      # strong model failed, Ollama answered
    except Exception as e:
        tokens, status = 0, "failed"
    rows.append({
        "id": r["id"], "department": ["Marketing", "HR", "Finance", "IT"][int(r["id"]) % 4],
        "model": model, "category": predicted, "tokens": tokens,
        "cost_usd": tokens / 1000 * PRICE[model],
        "cost_unrouted": tokens / 1000 * PRICE["strong-model"],
        "status": status,
    })
    print(r["id"], model, status)
    time.sleep(0.2)

out = pd.DataFrame(rows)
out["date"] = pd.Timestamp.now().normalize()
out.to_csv("benchmark/results.csv", index=False)
print("Saved benchmark/results.csv")