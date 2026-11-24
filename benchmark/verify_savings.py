import csv


def summarize(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    cost = sum(float(r["cost"]) for r in rows)
    base = sum(float(r["cost_unrouted"]) for r in rows)
    return {
        "requests": n,
        "success": sum(r["success"] == "True" for r in rows),
        "fallbacks": sum(r["fallback"] == "True" for r in rows),
        "correct_class": sum(r["real"] == r["predicted"] for r in rows),
        "cost_with": cost,
        "cost_without": base,
        "savings": (1 - cost / base) * 100,
    }


for label, path in [("Normal run", "benchmark/results_normal.csv"),
                    ("Chaos run", "benchmark/results_chaos.csv")]:
    s = summarize(path)
    print(label)
    print(f"  requests:           {s['requests']}")
    print(f"  successful:         {s['success']}")
    print(f"  fallbacks:          {s['fallbacks']}")
    print(f"  classified right:   {s['correct_class']}")
    print(f"  cost with routing:  {s['cost_with']:.6f} USD")
    print(f"  cost without:       {s['cost_without']:.6f} USD")
    print(f"  savings:            {s['savings']:.2f} %")
    print()