# Database design

The database stores the department budgets and keeps a record of every request
that goes through the gateway, so costs can be analysed and alerts can fire.
It runs on PostgreSQL. All SQL is in the `sql/` folder.

## Tables

### departments

One row per department, with its rules.

|Column|Meaning|
|-|-|
|id|Automatic number identifying the department|
|name|Department name (unique)|
|monthly\_budget\_usd|Monthly spending cap in dollars|
|rpm\_limit|Maximum requests per minute|
|tpm\_limit|Maximum tokens per minute|

Current values: Marketing 50 USD, HR 30 USD, Finance 80 USD, IT 100 USD.

### cost\_ledger

One row per request handled by the gateway.

|Column|Meaning|
|-|-|
|id|Automatic number|
|created\_at|When the request happened (filled automatically)|
|department\_id|Which department asked (must exist in departments)|
|model\_used|Which model answered (cheap-model or strong-model)|
|query\_category|simple or complex (any other value is rejected)|
|tokens\_in|Tokens sent to the model|
|tokens\_out|Tokens received from the model|
|cost\_usd|Cost of the request in dollars|
|status|success, fallback or failed|

### model\_prices

The price of each model per token. These values must match `docs/prices.md`.

|Column|Meaning|
|-|-|
|model\_name|cheap-model or strong-model|
|usd\_per\_token|Price of one token in dollars|

## Views

A view is a saved query that behaves like a table, so the dashboard and the
alert can read ready-made figures.

|View|What it shows|Used by|
|-|-|-|
|v\_budget\_usage|Per department: budget, money spent this month, percent used|The 80% alert and the dashboard|
|v\_savings|Cost with routing, cost without routing, savings percent|The benchmark result (target: more than 50%)|
|v\_model\_usage|Requests, tokens and cost per model and status|Dashboard, shows how many requests fell back|

The alert condition is: `SELECT \* FROM v\_budget\_usage WHERE percent\_used >= 80;`

## Scripts

|File|Purpose|
|-|-|
|sql/schema.sql|Creates the departments and cost\_ledger tables and inserts the four departments|
|sql/views.sql|Creates model\_prices and the three views|
|sql/create\_keys.py|Creates one virtual key per department in the gateway, using the budgets and limits from the departments table (use --dry-run to preview)|
|sql/seed\_fake.sql|Inserts 100 FAKE requests for testing only. Never use on the real benchmark database|

## How to build the database on a new PostgreSQL server

1. Create a database called llm\_gateway.
2. Run sql/schema.sql.
3. Run sql/views.sql.
4. Point the gateway to the database with the DATABASE\_URL variable.
5. Run sql/create\_keys.py to create the department keys.

## Rules

* Real passwords and keys are never committed (see .env.example and .gitignore).
* Sample data from seed\_fake.sql is simulated. Savings figures reported in the
final results must come only from the gateway's 100-request benchmark.
* Before the real benchmark, check that the ledger is empty:
`SELECT COUNT(\*) FROM cost\_ledger;` must return 0.

## Tested so far

On a local PostgreSQL with fake data: the views agree with each other (same
totals), the savings formula reproduces by hand, and the 80% condition returns
only a department that crossed 80 percent of its budget.

## Still to define

How cost\_ledger gets filled during the real benchmark (gateway callback or a
sync from the gateway's own spend logs) depends on the LiteLLM version used
by the host and is to be decided once the gateway runs.

