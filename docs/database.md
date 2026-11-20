# Database design

The database stores the department budgets and keeps a record of every request
that goes through the router, so costs can be analysed and alerts can fire.
It runs on PostgreSQL. All SQL is in the `sql/` folder.

## Tables

### departments

One row per department, with its rules.

| Column | Meaning |
|---|---|
| id | Automatic number identifying the department |
| name | Department name (unique) |
| monthly_budget_usd | Monthly spending cap in dollars |
| rpm_limit | Maximum requests per minute |
| tpm_limit | Maximum tokens per minute (see "Known gaps") |

Current values: Marketing 50 USD, HR 30 USD, Finance 80 USD, IT 100 USD.

### department_keys

One API key per department, used by the router to identify who is calling.

| Column | Meaning |
|---|---|
| id | Automatic number |
| department_id | Which department the key belongs to |
| api_key | The key, for example sk-dept-hr-isg2026 (unique) |
| created_at | When the key was created |

### cost_ledger

One row per request handled through a department key.

| Column | Meaning |
|---|---|
| id | Automatic number |
| created_at | When the request happened (filled automatically) |
| department_id | Which department asked (must exist in departments) |
| model_used | Which model actually answered (cheap-model or strong-model) |
| query_category | simple or complex (any other value is rejected) |
| tokens_in | Tokens sent to the model |
| tokens_out | Tokens received from the model |
| cost_usd | Cost of the request in dollars |
| status | success or fallback (the router writes a row only for successful answers) |

A request is a fallback when it was routed to strong-model but cheap-model
answered. In that case model_used is cheap-model and status is fallback.

### model_prices

The price of each model per token. These values must match `docs/prices.md`.

| Column | Meaning |
|---|---|
| model_name | cheap-model or strong-model |
| usd_per_token | Price of one token in dollars |

## Views

A view is a saved query that behaves like a table, so the dashboard and the
alert can read ready-made figures.

| View | What it shows | Used by |
|---|---|---|
| v_budget_usage | Per department: budget, money spent this month, percent used | The 80% alert and the dashboard |
| v_savings | Cost with routing, cost without routing, savings percent | Savings from requests logged in the ledger |
| v_model_usage | Requests, tokens and cost per model and status | Dashboard, shows how many requests fell back |

The alert condition is: `SELECT * FROM v_budget_usage WHERE percent_used >= 80;`

## How budgets, keys and limits are enforced

LiteLLM's built-in virtual keys could not run on the team's Windows PCs (the
database component was blocked), so the router (`router_proxy.py`, port 5000)
does this job using the tables above:

1. A request arrives with a department key. An unknown key gets HTTP 401.
2. The router checks the department's monthly budget and its requests per
   minute. Over the limit gets HTTP 429.
3. The router picks cheap-model or strong-model and forwards the request to
   the gateway (LiteLLM, port 4000).
4. After a successful answer, the router writes one row to cost_ledger.
5. At 80% of the budget, the router calls the n8n webhook, which sends the
   alert email.

The master key skips limits and logging. The benchmark uses it, so benchmark
requests are not in cost_ledger.

## Scripts

| File | Purpose |
|---|---|
| sql/schema.sql | Creates departments and cost_ledger and inserts the four departments |
| sql/views.sql | Creates model_prices and the three views |
| sql/department_keys.sql | Creates department_keys and one key per department |
| sql/seed_fake.sql | Inserts 100 FAKE requests for testing only. Never use on the real database |
| sql/create_keys.py | Not used. It creates keys through LiteLLM's key API, which is not available in this setup |
| benchmark/verify_savings.py | Recomputes the savings from the benchmark result files |

## How to build the database on a new PostgreSQL server

1. Create a database called llm_gateway.
2. Run sql/schema.sql, then sql/views.sql, then sql/department_keys.sql.
3. Start the router with the database password in the PGPASSWORD variable
   (see docs/how-to-start.md).

## Verified results

The benchmark results files were checked independently with
`benchmark/verify_savings.py`:

| Run | Requests | Successful | Fallbacks | Classified right | Cost with routing | Cost without | Savings |
|---|---|---|---|---|---|---|---|
| Normal | 100 | 100 | 0 | 99 | 0.010758 USD | 0.070950 USD | 84.84% |
| Chaos (503 outage) | 100 | 100 | 11 | 99 | 0.007100 USD | 0.086300 USD | 91.77% |

The 84.84% figure is the savings result. The chaos figure is inflated because
the local model, which is almost free, answered during the outage, so that run
only proves uptime. The strong model is a mock with fixed token counts, so all
costs are a simulation based on the assumed prices in `docs/prices.md`.

The views were also tested on fake data: they agree with each other, the
savings formula reproduces by hand, and the 80% condition returns only a
department that crossed 80 percent of its budget.

## Rules

- Real passwords and keys are never committed (see .env.example and .gitignore).
- Sample data from seed_fake.sql is simulated and must not appear in results.
- The department keys follow a predictable pattern. This is acceptable for a
  school simulation and is not real security.

## Known gaps

- The tpm_limit column (tokens per minute) exists but no check on it was found
  in the router code. The official step lists RPM, TPM and USD limits.
- Benchmark requests use the master key and are not in cost_ledger, so the
  views describe only requests made with department keys.
