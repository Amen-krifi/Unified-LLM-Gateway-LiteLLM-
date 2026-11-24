# Unified LLM Gateway — Startup, Demo & Shutdown Guide

Windows 11 + PowerShell. Project folder: `$HOME\Documents\Unified-LLM-Gateway-LiteLLM-`

> Secrets are never stored in this repo. Replace `YOUR_MASTER_KEY` and `YOUR_PG_PASSWORD` locally.
> The **same master key** must be used in the Gateway and Router windows.

## Services and ports

| Service | Port | Runs in |
|---|---|---|
| Router Proxy (FastAPI) | 5000 | PowerShell window 3 |
| LiteLLM Gateway | 4000 | PowerShell window 2 |
| Mock Cloud (ok / 429 / 503) | 8001 | PowerShell window 1 |
| Ollama (llama3.1) | 11434 | Ollama app |
| PostgreSQL (`llm_gateway`) | 5432 | Windows service |
| Prometheus | 9090 | Docker |
| Grafana | 3000 | Docker |
| n8n (budget alert) | 5678 | Docker |
| Langfuse | cloud.langfuse.com | Cloud |

## One-time setup

**Langfuse keys** are stored as Windows user variables (run once, in any window, then open new windows):

```powershell
[Environment]::SetEnvironmentVariable("LANGFUSE_PUBLIC_KEY","pk-lf-...","User")
[Environment]::SetEnvironmentVariable("LANGFUSE_SECRET_KEY","sk-lf-...","User")
[Environment]::SetEnvironmentVariable("LANGFUSE_HOST","https://cloud.langfuse.com","User")
```

**n8n container** — only if `docker ps -a` does not list `n8n` (data is kept in the `n8n_data` volume):

```powershell
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

## Start (in this order)

### 0. Dependencies
- Start **Docker Desktop** (wait for *Engine running*) and **Ollama**.
- Check: `ollama list` shows `llama3.1:latest`; `Test-NetConnection 127.0.0.1 -Port 5432` is `True`.

### 1. Docker containers (any window, can be closed afterwards)
```powershell
docker start n8n prometheus grafana
docker ps
```
Prometheus and Grafana run **only in Docker** — do not start `prometheus.exe` or `grafana-server`.

### 2. Window "1 - MOCK CLOUD 8001" (keep open)
```powershell
$Host.UI.RawUI.WindowTitle = "1 - MOCK CLOUD 8001"
cd "$HOME\Documents\Unified-LLM-Gateway-LiteLLM-"
.\.venv\Scripts\Activate.ps1
python -m uvicorn mock_cloud:app --host 127.0.0.1 --port 8001
```

### 3. Window "2 - GATEWAY 4000" (keep open)
```powershell
$Host.UI.RawUI.WindowTitle = "2 - GATEWAY 4000"
cd "$HOME\Documents\Unified-LLM-Gateway-LiteLLM-"
.\.venv\Scripts\Activate.ps1
$env:LITELLM_MASTER_KEY="YOUR_MASTER_KEY"
$env:PYTHONUTF8=1
python -m litellm.proxy.proxy_cli --config config.yaml --port 4000
```
Check: `http://localhost:4000/health/liveliness`

### 4. Window "3 - ROUTER 5000" (keep open)
```powershell
$Host.UI.RawUI.WindowTitle = "3 - ROUTER 5000"
cd "$HOME\Documents\Unified-LLM-Gateway-LiteLLM-"
.\.venv\Scripts\Activate.ps1
$env:PGPASSWORD="YOUR_PG_PASSWORD"
$env:LITELLM_MASTER_KEY="YOUR_MASTER_KEY"
$env:N8N_WEBHOOK_URL="http://localhost:5678/webhook/2a1e8978-bcaf-4d10-ad3d-717ffb229355"
python -m uvicorn router_proxy:app --host 127.0.0.1 --port 5000
```
Check: `http://localhost:5000/metrics` returns text; `http://localhost:5000/docs` lists `POST /v1/chat/completions`.

### 5. Window "4 - TESTS"
```powershell
$Host.UI.RawUI.WindowTitle = "4 - TESTS"
cd "$HOME\Documents\Unified-LLM-Gateway-LiteLLM-"
.\.venv-deepeval\Scripts\Activate.ps1
python -m pytest -v test
```
Expected: **21 passed**.

### 6. Browser
- Prometheus targets: `http://localhost:9090/targets` → `llm-router` **UP**
- Grafana: `http://localhost:3000` → *LLM Gateway Monitoring* (time range: Last 15 minutes)
- n8n: `http://localhost:5678` → budget-alert workflow **Active**
- Langfuse: `https://cloud.langfuse.com` → Traces

## Demo commands (window "4 - TESTS")

```powershell
$headers = @{ Authorization = "Bearer sk-dept-marketing-isg2026" }
$simple  = @{ messages = @(@{ role = "user"; content = "What is 2+2?" }) } | ConvertTo-Json -Depth 5
$complex = @{ messages = @(@{ role = "user"; content = "Analyze the trade-offs between microservices and monoliths for a bank, step by step, with risks and costs." }) } | ConvertTo-Json -Depth 5
$url = "http://localhost:5000/v1/chat/completions"

# 1. Simple -> local model (llama)
(Invoke-RestMethod -Uri $url -Method Post -Headers $headers -ContentType "application/json" -Body $simple).model

# 2. Complex -> strong model (mock-frontier)
(Invoke-RestMethod -Uri $url -Method Post -Headers $headers -ContentType "application/json" -Body $complex).model

# 3. Cloud outage -> fallback to llama (mode routes use GET)
Invoke-RestMethod -Method Get -Uri "http://localhost:8001/mode/503"
(Invoke-RestMethod -Uri $url -Method Post -Headers $headers -ContentType "application/json" -Body $complex).model
Invoke-RestMethod -Method Get -Uri "http://localhost:8001/mode/ok"

# 4. Wrong key -> 401
try { Invoke-RestMethod -Uri $url -Method Post -Headers @{ Authorization = "Bearer wrong-key" } -ContentType "application/json" -Body $simple } catch { $_.Exception.Response.StatusCode.value__ }

# 5. n8n budget alert test (85 % >= 80 % threshold)
$body = @{ department = "Marketing"; percent_used = 85 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:5678/webhook/2a1e8978-bcaf-4d10-ad3d-717ffb229355" -ContentType "application/json" -Body $body
```

The first request after a restart is slow (Ollama loads the model, ~10–20 s).

## Shutdown

1. **Ctrl + C** in windows 1, 2 and 3.
2. `docker stop n8n prometheus grafana` (stops without deleting data).
3. Quit Ollama from the taskbar icon, then `taskkill /F /IM ollama.exe`.
4. Verify all ports are free (no output = OK):
```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
Where-Object { $_.LocalPort -in 8001,4000,5000,8501,11434,3000,9090,5678 } |
Select-Object LocalAddress,LocalPort,OwningProcess
```
Do **not** delete containers, the `n8n_data` volume, the `llm_gateway` database, or the `.venv` folders.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No connected db.` from the Router | Router and Gateway use different master keys | Restart both with the same `LITELLM_MASTER_KEY` |
| `Unable to connect to the remote server` | The server on that port is stopped | Restart the matching window |
| `No such container: n8n` | Container was removed | Recreate it (see One-time setup) |
| `Method Not Allowed` on `/mode/...` | Wrong HTTP method | Use `-Method Get` |
| No new traces in Langfuse | Langfuse keys missing in the Gateway environment | Set the user variables, open a new Gateway window |
| Grafana panel "No data" | No traffic yet, or wrong query | Send requests; check the panel query |
| Port 11434 still busy after stop | Ollama auto-restarts | `taskkill /F /IM ollama.exe` |

## Current configuration highlights (`config.yaml`)

- `cheap-model`: Ollama llama3.1 — $0.10 per 1M tokens
- `strong-model`: Mock frontier — $10 per 1M tokens
- `num_retries: 2`, `retry_after: 1`, `allowed_fails: 1`, `cooldown_time: 30`
- `fallbacks`: strong-model → cheap-model (on 429/503)
- `context_window_fallbacks`: cheap-model → strong-model (prompt too long)

## Verified results (24 Nov 2026)

- pytest: 21 passed; GitHub Actions green (DeepEval routing-quality test runs in CI)
- Benchmark: 71 % routed to local model; 85.1 % (normal) / 91.7 % (chaos) cost savings; 100 % success; 11 fallbacks in chaos
- Prometheus target `llm-router` UP; Grafana panels populated; Langfuse traces received; n8n alert e-mail delivered