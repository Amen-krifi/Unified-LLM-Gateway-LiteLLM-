import random
import pandas as pd
import plotly.express as px
import streamlit as st

random.seed(42)
budgets = {"Marketing": 50, "HR": 30, "Finance": 80, "IT": 100}
PRICE = {"cheap-model": 0.0001, "strong-model": 0.01}  # USD per 1K tokens

rows = []
for day in pd.date_range("2026-11-01", periods=14):
    for dept in budgets:
        for _ in range(random.randint(5, 20)):
            model = random.choices(["cheap-model", "strong-model"], weights=[70, 30])[0]
            tokens = random.randint(100, 800)
            rows.append({
                "date": day, "department": dept, "model": model,
                "tokens": tokens,
                "cost_usd": tokens / 1000 * PRICE[model],
                "cost_unrouted": tokens / 1000 * PRICE["strong-model"],
            })
df = pd.DataFrame(rows)

st.title("LLM Gateway - Token Spend per Team")

total = df["cost_usd"].sum()
baseline = df["cost_unrouted"].sum()
c1, c2, c3 = st.columns(3)
c1.metric("Total spend (USD)", f"{total:.2f}")
c2.metric("Spend without routing (USD)", f"{baseline:.2f}")
c3.metric("Savings", f"{(baseline - total) / baseline:.0%}")

by_dept = df.groupby("department", as_index=False)["cost_usd"].sum()
by_dept["budget_used_pct"] = by_dept.apply(
    lambda r: r["cost_usd"] / budgets[r["department"]] * 100, axis=1)
st.plotly_chart(px.bar(by_dept, x="department", y="cost_usd", title="Spend per department"))
st.plotly_chart(px.bar(by_dept, x="department", y="budget_used_pct",
                       title="Budget used (%)"))

daily = df.groupby("date", as_index=False)["cost_usd"].sum()
st.plotly_chart(px.line(daily, x="date", y="cost_usd", title="Daily spend"))
st.plotly_chart(px.pie(df, names="model", title="Share of requests per model"))