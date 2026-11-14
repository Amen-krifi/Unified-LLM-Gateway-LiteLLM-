CREATE TABLE departments (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) UNIQUE NOT NULL,
  monthly_budget_usd NUMERIC(10,2) NOT NULL,
  rpm_limit INT NOT NULL,
  tpm_limit INT NOT NULL
);

CREATE TABLE cost_ledger (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  department_id INT REFERENCES departments(id),
  model_used VARCHAR(50) NOT NULL,
  query_category VARCHAR(10) CHECK (query_category IN ('simple','complex')),
  tokens_in INT NOT NULL,
  tokens_out INT NOT NULL,
  cost_usd NUMERIC(10,6) NOT NULL,
  status VARCHAR(20) NOT NULL
);

INSERT INTO departments (name, monthly_budget_usd, rpm_limit, tpm_limit) VALUES
  ('Marketing', 50, 20, 20000),
  ('HR', 30, 10, 10000),
  ('Finance', 80, 30, 30000),
  ('IT', 100, 60, 60000);