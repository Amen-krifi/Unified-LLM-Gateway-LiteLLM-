import re

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