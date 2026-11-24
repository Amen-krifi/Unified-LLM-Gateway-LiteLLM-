import pytest

from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from router import classify


class RoutingAccuracyMetric(BaseMetric):
    def __init__(self, threshold=1.0):
        self.threshold = threshold
        self.async_mode = False
        self.include_reason = False
        self.strict_mode = True
        self.score = 0.0
        self.success = False

    def measure(self, test_case):
        self.score = (
            1.0
            if test_case.actual_output == test_case.expected_output
            else 0.0
        )
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case):
        return self.measure(test_case)

    def is_successful(self):
        return self.success

    @property
    def __name__(self):
        return "Routing Accuracy"


@pytest.mark.parametrize(
    "prompt, expected",
    [
        ("Hi", "simple"),
        ("What is 2 + 2?", "simple"),
        ("Explain the difference between star and snowflake schemas.", "complex"),
        ("Compare these two models", "complex"),
        (
            "Analyze the architecture and explain the risks, "
            "recommend improvements, and evaluate the alternatives.",
            "complex",
        ),
    ],
)
def test_routing_quality_with_deepeval(prompt, expected):
    actual = classify(prompt)

    test_case = LLMTestCase(
        input=prompt,
        actual_output=actual,
        expected_output=expected,
    )

    assert_test(test_case, [RoutingAccuracyMetric()])