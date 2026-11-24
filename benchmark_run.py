
import csv
import os
import random
import sys
import time
import requests

KEY = os.environ.get("LITELLM_MASTER_KEY", "")
ROUTER = "http://localhost:5000/v1/chat/completions"
MOCK = "http://localhost:8001/mode/"
PRICE = {
    "cheap-model": 0.0000001,
    "strong-model": 0.00001,
}  # USD per token

mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

with open("benchmark/questions.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

random.Random(42).shuffle(rows)

if limit:
    rows = rows[:limit]

n = len(rows)
results = []

try:
    for i, row in enumerate(rows):

        if mode == "chaos" and i == n // 3:
            requests.get(MOCK + "503")
            print(">>> mock set to 503 (provider outage starts)")

        if mode == "chaos" and i == 2 * n // 3:
            requests.get(MOCK + "ok")
            print(">>> mock set to ok (provider recovered)")

        start = time.time()
        ok = False
        category = ""
        routed = ""
        answered = ""
        tokens = 0

        try:
            r = requests.post(
                ROUTER,
                headers={"Authorization": f"Bearer {KEY}"},
                json={
                    "messages": [
                        {"role": "user", "content": row["question"]}
                    ],
                    "max_tokens": 150,
                },
                timeout=300,
            )

            category = r.headers.get("X-Route-Category", "")
            routed = r.headers.get("X-Route-Model", "")

            if r.status_code == 200:
                data = r.json()

                ok = bool(
                    data["choices"][0]["message"]["content"].strip()
                )

                response_model = data.get("model", "")

                if response_model in ("strong-model", "mock-frontier"):
                    answered = "strong-model"

                elif response_model in (
                    "cheap-model",
                    "ollama_chat/llama3.1:latest",
                ):
                    answered = "cheap-model"

                else:
                    raise ValueError(
                        f"Unknown response model: {response_model}"
                    )

                tokens = data.get("usage", {}).get("total_tokens", 0)

        except Exception as e:
            print("   error:", str(e)[:80])

        secs = time.time() - start

        results.append({
            "id": row["id"],
            "real": row["category"],
            "predicted": category,
            "routed": routed,
            "answered": answered,
            "success": ok,
            "fallback": (
                ok
                and routed == "strong-model"
                and answered == "cheap-model"
            ),
            "tokens": tokens,
            "seconds": round(secs, 1),
            "cost": tokens * PRICE.get(answered, 0),
            "cost_unrouted": tokens * PRICE["strong-model"],
        })

        print(
            f"{i + 1}/{n} id={row['id']} {category} -> {routed} "
            f"(answered by {answered}) ok={ok} {secs:.1f}s"
        )

finally:
    requests.get(MOCK + "ok")


out = f"benchmark/results_{mode}.csv"

with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)


ok_n = sum(r["success"] for r in results)
correct = sum(r["real"] == r["predicted"] for r in results)
fb = sum(r["fallback"] for r in results)
cost = sum(r["cost"] for r in results)
base = sum(r["cost_unrouted"] for r in results)

print("\n===== SUMMARY =====")
print(f"Mode: {mode} | requests: {n}")
print(f"Success rate: {ok_n}/{n} = {ok_n / n:.0%}")
print(f"Classification correct: {correct}/{n} = {correct / n:.0%}")
print(f"Fallbacks to Ollama: {fb}")
print(f"Cost with routing:    ${cost:.6f}")
print(f"Cost without routing: ${base:.6f}")

if base:
    print(f"Savings: {(base - cost) / base:.1%}")

print(
    f"Average time per request: "
    f"{sum(r['seconds'] for r in results) / n:.1f}s"
)

print(f"Results saved in {out}")
