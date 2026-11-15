from fastapi import FastAPI
from fastapi.responses import JSONResponse
import time

app = FastAPI()
state = {"mode": "ok"}

@app.get("/mode/{mode}")
def set_mode(mode: str):
    if mode not in ("ok", "503", "429"):
        return JSONResponse({"error": "use ok, 503 or 429"}, status_code=400)
    state["mode"] = mode
    return {"mode": mode}

@app.post("/v1/chat/completions")
async def chat(body: dict):
    if state["mode"] in ("503", "429"):
        code = int(state["mode"])
        return JSONResponse(
            {"error": {"message": f"mock provider error {code}", "type": "mock_error", "code": code}},
            status_code=code,
        )
    return {
        "id": "mock-1",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "mock-frontier",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": "[MOCK FRONTIER] This is a simulated frontier-model answer."},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
    }