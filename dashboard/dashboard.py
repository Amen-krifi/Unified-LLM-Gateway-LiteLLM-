"""LLM Gateway FinOps dashboard - reads REAL data from PostgreSQL.

Run:  streamlit run dashboard/dashboard.py
Needs the same environment variables as the router (password never in code):
  PGPASSWORD (required), PGHOST (default localhost), PGPORT (default 5432),
  PGDATABASE (default llm_gateway), PGUSER (default postgres)
"""
import os

import pandas as pd
import pg8000.dbapi
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="LLM Gateway FinOps", layout="wide")


def query(sql: str) -> pd.DataFrame:
    conn = pg8000.dbapi.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        database=os.environ.get("PGDATABASE", "llm_gateway"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        conn.close()


@st.cache_data(ttl=10)
def load():
    return {
        "budget": query("SELECT * FROM v_budget_usage"),
        "savings": query("SELECT * FROM v_savings"),
        "models": query("SELECT * FROM v_model_usage"),
        "daily": query(
            "SELECT date_trunc('day', created_at)::date AS day, "
            "SUM(cost_usd) AS cost_usd, COUNT(*) AS requests "
            "FROM cost_ledger GROUP BY 1 ORDER BY 1"),
        "category": query(
            "SELECT query_category, model_used, COUNT(*) AS requests "
            "FROM cost_ledger GROUP BY 1, 2 ORDER BY 1, 2"),
    }


st.title("LLM Gateway - Token Spend per Department")
st.caption("Live data from PostgreSQL (cost_ledger and views). Prices are simulated.")

if st.button("Refresh"):
    st.cache_data.clear()

try:
    data = load()
except Exception as exc:  # DB down, wrong password, views missing...
    st.error("Cannot read PostgreSQL. Check PGPASSWORD / PGHOST / PGPORT and that "
             "sql/schema.sql, views.sql and the router have been run.")
    st.code(str(exc))
    st.stop()

budget, savings, models = data["budget"], data["savings"], data["models"]
if savings.empty or not savings.loc[0, "requests"]:
    st.info("The cost ledger is empty. Send some requests through the router "
            "(port 5000) or run the benchmark, then click Refresh.")
    st.stop()

s = savings.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Requests logged", f"{int(s['requests'])}")
c2.metric("Spend with routing (USD)", f"{float(s['cost_with_routing']):.6f}")
c3.metric("Spend without routing (USD)", f"{float(s['cost_without_routing']):.6f}")
c4.metric("Savings", f"{float(s['savings_percent']):.1f}%")

left, right = st.columns(2)
with left:
    st.plotly_chart(px.bar(budget, x="department", y="spent_usd",
                           title="Spend per department this month (USD)"),
                    )
with right:
    fig = px.bar(budget, x="department", y="percent_used",
                 title="Budget used this month (%)")
    fig.add_hline(y=80, line_dash="dash", annotation_text="80% alert")
    st.plotly_chart(fig)

left, right = st.columns(2)
with left:
    st.plotly_chart(px.line(data["daily"], x="day", y="cost_usd", markers=True,
                            title="Daily spend (USD)"))
with right:
    st.plotly_chart(px.pie(models.groupby("model_used", as_index=False)["requests"].sum(),
                           names="model_used", values="requests",
                           title="Share of requests per model"),
                    )

st.subheader("Requests per model and status (fallbacks and blocked requests)")
st.dataframe(models)
st.subheader("Budget table")
st.dataframe(budget)
