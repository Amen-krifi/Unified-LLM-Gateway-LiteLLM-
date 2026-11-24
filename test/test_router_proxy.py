from conftest import DEPT_KEY, MASTER, gateway_reply
import router_proxy

from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from test_classifier import RoutingAccuracyMetric

SIMPLE = "What is the capital of France?"
COMPLEX = ("Compare star and snowflake schemas and recommend one "
           "for a retail data warehouse")


def ask(world, key, question):
    return world.client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"messages": [{"role": "user", "content": question}]})


def test_simple_question_goes_to_cheap_model(world):
    r = ask(world, MASTER, SIMPLE)
    assert r.status_code == 200

    actual_model = r.headers["X-Route-Model"]
    assert world.gateway_calls[-1]["model"] == "cheap-model"

    test_case = LLMTestCase(
        input=SIMPLE,
        actual_output=actual_model,
        expected_output="cheap-model",
    )
    assert_test(test_case, [RoutingAccuracyMetric()])


def test_complex_question_goes_to_strong_model(world):
    r = ask(world, MASTER, COMPLEX)
    assert r.status_code == 200

    actual_model = r.headers["X-Route-Model"]
    assert world.gateway_calls[-1]["model"] == "strong-model"

    test_case = LLMTestCase(
        input=COMPLEX,
        actual_output=actual_model,
        expected_output="strong-model",
    )
    assert_test(test_case, [RoutingAccuracyMetric()])


def test_unknown_key_is_rejected_with_401(world):
    r = ask(world, "wrong-key", SIMPLE)
    assert r.status_code == 401
    assert world.gateway_calls == []


def test_mock_frontier_name_is_billed_as_strong_not_fallback(world):
    # Regression: the gateway reported "mock-frontier" and the router
    # wrongly billed it at the cheap price as a fallback.
    world.reply = gateway_reply("mock-frontier", 20, 15)
    r = ask(world, DEPT_KEY, COMPLEX)
    assert r.status_code == 200
    entry = world.logs[-1]
    assert entry["model"] == "strong-model"
    assert entry["status"] == "success"
    assert abs(entry["cost"] - 35 * router_proxy.PRICE["strong-model"]) < 1e-12


def test_llama_reply_to_a_strong_request_is_a_fallback(world):
    world.reply = gateway_reply("ollama_chat/llama3.1:latest", 20, 15)
    r = ask(world, DEPT_KEY, COMPLEX)
    assert r.status_code == 200
    entry = world.logs[-1]
    assert entry["model"] == "cheap-model"
    assert entry["status"] == "fallback"


def test_budget_exceeded_returns_429_before_calling_the_gateway(world):
    world.budget = 0.01
    world.spent = 0.02
    r = ask(world, DEPT_KEY, SIMPLE)
    assert r.status_code == 429
    assert "budget" in r.json()["error"]
    assert world.gateway_calls == []
    assert world.logs[-1]["status"] == "failed"


def test_rpm_limit_blocks_the_third_request(world):
    world.rpm = 2
    assert ask(world, DEPT_KEY, SIMPLE).status_code == 200
    assert ask(world, DEPT_KEY, SIMPLE).status_code == 200
    r = ask(world, DEPT_KEY, SIMPLE)
    assert r.status_code == 429
    assert "RPM" in r.json()["error"]


def test_alert_is_triggered_at_80_percent(world):
    world.budget = 0.01
    world.spent = 0.0085
    r = ask(world, DEPT_KEY, SIMPLE)
    assert r.status_code == 200
    assert float(r.headers["X-Budget-Used-Pct"]) >= 80
    assert len(router_proxy.alerted) == 1


def test_gateway_down_returns_502(world):
    world.fail = True
    r = ask(world, DEPT_KEY, SIMPLE)
    assert r.status_code == 502


def test_metrics_endpoint_never_contains_prompt_text(world):
    secret = "my confidential salary question"
    ask(world, MASTER, secret)
    text = world.client.get("/metrics").text
    assert "router_requests_total" in text
    assert secret not in text