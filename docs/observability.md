# Observability

## Prometheus metrics (router, port 5000)

`GET http://localhost:5000/metrics` exposes metadata only (no prompts, answers or keys).

| Metric | Labels | Meaning |
|---|---|---|
| router_requests_total | department, category, outcome | Requests by result |
| router_request_latency_seconds | outcome | Latency histogram |
| router_fallbacks_total | department | strong-model answered by cheap-model |
| router_tokens_total | department, model, direction | Tokens used |
| router_cost_usd_total | department, model | Simulated cost |
| router_budget_used_percent | department | Share of monthly budget |
| router_budget_limit_usd | department | Monthly budget |
| router_alerts_total | department, result | Alerts (sent, failed, not_configured, http_error) |

Outcomes: success, fallback, upstream_error, gateway_unreachable,
unauthorized, rpm_limited, budget_exceeded. Department `master` is traffic
using the master key; `unknown` is an unrecognised key.

Test: `python test_metrics.py` (router and gateway must be running).