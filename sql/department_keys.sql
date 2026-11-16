CREATE TABLE IF NOT EXISTS department_keys (
  id SERIAL PRIMARY KEY,
  department_id INT NOT NULL REFERENCES departments(id),
  api_key VARCHAR(80) UNIQUE NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO department_keys (department_id, api_key)
SELECT id, 'sk-dept-' || lower(name) || '-isg2026'
FROM departments
ON CONFLICT (api_key) DO NOTHING;