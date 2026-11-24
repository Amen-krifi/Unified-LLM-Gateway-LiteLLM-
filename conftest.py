import os
import sys
from decimal import Decimal
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# The root-level test_*.py files are live scripts that call the real servers.
# pytest must never import them.
collect_ignore = ["test.py", "test_router.py", "test_budget.py",
                  "test_metrics.py", "benchmark_run.py"]

# Safe test environment, set BEFORE router_proxy is imported.
# Real keys and the real webhook are never used in tests.
os.environ["LITELLM_MASTER_KEY"] = "test-master-key"
os.environ["PGPASSWORD"] = "unused-in-tests"
os.environ["N8N_WEBHOOK_URL"] = ""

import router_proxy  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

MASTER = "test-master-key"
DEPT_KEY = "test-dept-key"


def gateway_reply(model="mock-frontier", tin=20, tout=15):
    return {
        "id": "test",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": "ok"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": tin, "completion_tokens": tout,
                  "total_tokens": tin + tout},
    }


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.fixture
def world(monkeypatch):
    """Router with a fake database and a fake gateway."""
    state = SimpleNamespace(
        reply=gateway_reply(), status=200, fail=False,
        spent=0.0, budget=Decimal("30"), rpm=10,
        logs=[], gateway_calls=[])

    class FakeConn:
        def close(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            state.gateway_calls.append(json)
            if state.fail:
                raise RuntimeError("gateway down")
            return FakeResponse(state.status, state.reply)

    def fake_get_department(conn, key):
        if key == DEPT_KEY:
            return [1, "HR", state.budget, state.rpm]
        return None

    def fake_log(conn, dept_id, model, category, tin, tout, cost, status):
        state.logs.append({"model": model, "category": category,
                           "tin": tin, "tout": tout, "cost": cost,
                           "status": status})

    monkeypatch.setattr(router_proxy, "db", lambda: FakeConn())
    monkeypatch.setattr(router_proxy, "get_department", fake_get_department)
    monkeypatch.setattr(router_proxy, "month_spend",
                        lambda conn, dept_id: state.spent)
    monkeypatch.setattr(router_proxy, "log", fake_log)
    monkeypatch.setattr(router_proxy.httpx, "AsyncClient", FakeClient)
    router_proxy.recent.clear()
    router_proxy.alerted.clear()

    state.client = TestClient(router_proxy.app)
    return state