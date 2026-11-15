import os
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from router import classify

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:4000")
app = FastAPI()


def last_user_text(messages):
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            return c
    return ""


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    category = classify(last_user_text(body.get("messages", [])))
    body["model"] = "cheap-model" if category == "simple" else "strong-model"
    headers = {"Authorization": request.headers.get("authorization", "")}
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{GATEWAY}/v1/chat/completions", json=body, headers=headers)
    resp = JSONResponse(r.json(), status_code=r.status_code)
    resp.headers["X-Route-Category"] = category
    resp.headers["X-Route-Model"] = body["model"]
    return resp