from fastapi.testclient import TestClient

import mock_cloud


def test_mock_modes_return_the_expected_status():
    c = TestClient(mock_cloud.app)
    try:
        for code in (503, 429):
            assert c.get(f"/mode/{code}").status_code == 200
            r = c.post("/v1/chat/completions", json={"messages": []})
            assert r.status_code == code
        c.get("/mode/ok")
        r = c.post("/v1/chat/completions", json={"messages": []})
        assert r.status_code == 200
        assert "[MOCK FRONTIER]" in r.json()["choices"][0]["message"]["content"]
        assert c.get("/mode/bogus").status_code == 400
    finally:
        c.get("/mode/ok")