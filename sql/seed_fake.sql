-- FAKE TEST DATA ONLY. Delete with TRUNCATE before using real data.
INSERT INTO cost_ledger
  (created_at, department_id, model_used, query_category,
   tokens_in, tokens_out, cost_usd, status)
SELECT ts, dept, model, cat, tin, tout, (tin + tout) * price, status
FROM (
  SELECT
    NOW() - (random() * INTERVAL '10 days') AS ts,
    (1 + floor(random() * 4))::int AS dept,
    CASE WHEN r < 0.7 THEN 'cheap-model' ELSE 'strong-model' END AS model,
    CASE WHEN r < 0.7 THEN 'simple' ELSE 'complex' END AS cat,
    (20 + floor(random() * 80))::int AS tin,
    (50 + floor(random() * 150))::int AS tout,
    CASE WHEN r < 0.7 THEN 0.0000001 ELSE 0.00001 END AS price,
    CASE WHEN random() < 0.05 THEN 'fallback' ELSE 'success' END AS status
  FROM (SELECT random() AS r FROM generate_series(1, 100)) s
) t;