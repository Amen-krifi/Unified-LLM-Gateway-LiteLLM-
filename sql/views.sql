-- Prices must match docs/prices.md
CREATE TABLE IF NOT EXISTS model_prices (
  model_name VARCHAR(50) PRIMARY KEY,
  usd_per_token NUMERIC(12,9) NOT NULL
);

INSERT INTO model_prices (model_name, usd_per_token) VALUES
  ('cheap-model', 0.000000100),
  ('strong-model', 0.000010000)
ON CONFLICT (model_name) DO NOTHING;

-- Budget used per department this month (feeds the 80% alert and the dashboard)
CREATE OR REPLACE VIEW v_budget_usage AS
SELECT d.name AS department,
       d.monthly_budget_usd AS budget_usd,
       COALESCE(SUM(l.cost_usd), 0) AS spent_usd,
       ROUND(COALESCE(SUM(l.cost_usd), 0) / d.monthly_budget_usd * 100, 2) AS percent_used
FROM departments d
LEFT JOIN cost_ledger l
  ON l.department_id = d.id
 AND l.created_at >= date_trunc('month', NOW())
GROUP BY d.id, d.name, d.monthly_budget_usd
ORDER BY d.id;

-- Savings versus sending every request to the strong model
CREATE OR REPLACE VIEW v_savings AS
SELECT COUNT(*) AS requests,
       ROUND(SUM(l.cost_usd), 6) AS cost_with_routing,
       ROUND(SUM((l.tokens_in + l.tokens_out) * p.usd_per_token), 6) AS cost_without_routing,
       ROUND((1 - SUM(l.cost_usd) /
              NULLIF(SUM((l.tokens_in + l.tokens_out) * p.usd_per_token), 0)) * 100, 2)
         AS savings_percent
FROM cost_ledger l
CROSS JOIN model_prices p
WHERE p.model_name = 'strong-model';

-- Requests, tokens and cost per model and status (shows fallbacks)
CREATE OR REPLACE VIEW v_model_usage AS
SELECT model_used,
       status,
       COUNT(*) AS requests,
       SUM(tokens_in + tokens_out) AS tokens,
       ROUND(SUM(cost_usd), 6) AS cost_usd
FROM cost_ledger
GROUP BY model_used, status
ORDER BY model_used, status;