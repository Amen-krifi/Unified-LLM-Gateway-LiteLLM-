import re
import pandas as pd

KEYWORDS = ["compare", "analyze", "analyse", "explain", "why", "write code",
            "write a", "recommend", "design", "step by step", "evaluate",
            "assess", "propose", "describe", "plan", "outline", "create",
            "should", "how would", "strategy", "risks", "trade-off"]

def has_keyword(q):
    return any(re.search(r"\b" + re.escape(k) + r"\b", q) for k in KEYWORDS)

def classify(q):
    q = q.lower()
    if len(q.split()) > 35 or has_keyword(q):
        return "complex"
    return "simple"

df = pd.read_csv("benchmark/questions.csv")
df["predicted"] = df["question"].apply(classify)

acc = (df["predicted"] == df["category"]).mean()
print(f"Accuracy: {acc:.0%}\n")

print("Confusion table (rows = real, columns = predicted):")
print(pd.crosstab(df["category"], df["predicted"]))

print("\nMistakes:")
print(df[df["predicted"] != df["category"]][["id", "question", "category", "predicted"]].to_string(index=False))