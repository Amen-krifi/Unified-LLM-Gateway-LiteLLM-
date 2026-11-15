# How to start the gateway (Windows)

Run everything from the repo folder, with the virtual environment active
(`.\.venv\Scripts\Activate.ps1`). Use `python -m ...` because Windows may block `.exe` files.

## One-time setup
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "litellm[proxy]" uvicorn fastapi requests
```
Ollama needs a model. We use `llama3.1:latest` (`ollama pull llama3.1:latest`).
To use the smaller `llama3.2:1b`, run `ollama pull llama3.2:1b` and change the
`model:` line of `cheap-model` in `config.yaml`.

## The 3 terminals

**Terminal 1: Ollama.** It runs as a Windows service. Check with `ollama list`.

**Terminal 2: mock cloud (fake frontier model)**
```powershell
python -m uvicorn mock_cloud:app --port 8001
```

**Terminal 3: gateway**
```powershell
$env:LITELLM_MASTER_KEY="ASK-THE-TEAM-FOR-THE-KEY"
$env:PYTHONUTF8=1
python -m litellm.proxy.proxy_cli --config config.yaml --port 4000
```
Wait for `Uvicorn running on http://0.0.0.0:4000`.
**Terminal 4: router (port 5000)**
```powershell
python -m uvicorn router_proxy:app --port 5000
```
Apps send requests to port 5000 instead of 4000. The router picks
`cheap-model` or `strong-model` and forwards the request to the gateway.
Test it with `python test_router.py`.

## Test (4th terminal)
```powershell
$env:LITELLM_MASTER_KEY="ASK-THE-TEAM-FOR-THE-KEY"
python test.py cheap-model     # answer from Ollama
python test.py strong-model    # [MOCK FRONTIER] text
```

## Failover test
```powershell
python -c "import requests; print(requests.get('http://localhost:8001/mode/503').text)"
python test.py strong-model    # answer comes from Ollama
python -c "import requests; print(requests.get('http://localhost:8001/mode/429').text)"
python test.py strong-model    # answer comes from Ollama
python -c "import requests; print(requests.get('http://localhost:8001/mode/ok').text)"
python test.py strong-model    # [MOCK FRONTIER] again
```
After failures, `strong-model` can stay in cooldown for up to 30 seconds, so a
request may go straight to Ollama. This is expected.

## Notes
- The master key is never stored in the repo. Share it privately.
- The `model:` line in the test output shows who answered: `strong-model` means
  the mock, `ollama_chat/...` means the fallback.