import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from router.models import MODELS, PRICING, estimate_cost
from router.pipeline import run_pipeline


# --- Model tests ---

def test_models_has_four_roles():
    assert set(MODELS.keys()) == {"planner", "executor", "coder", "validator"}


def test_models_are_ollama_tags():
    for role, model in MODELS.items():
        assert model.startswith("ollama/"), f"{role} model missing ollama/ prefix"


def test_pricing_positive():
    for role, prices in PRICING.items():
        assert prices["input_per_1m"] > 0, f"{role} input price zero"
        assert prices["output_per_1m"] > 0, f"{role} output price zero"


def test_estimate_cost():
    cost = estimate_cost("executor", 1_000_000, 1_000_000)
    assert cost == 0.36  # 0.18 + 0.18


# --- Pipeline tests ---

def _mock_call(role, prompt):
    responses = {
        "planner": ("Step 1: Read file. Step 2: Fix bug.", 100, 50),
        "executor": ("Fixed the bug in auth.py", 200, 100),
        "validator": ("PASS - output is correct", 150, 30),
        "coder": ("Fixed properly with Kimi", 200, 100),
    }
    content, inp, out = responses[role]
    return {"content": content, "input_tokens": inp, "output_tokens": out, "cost": estimate_cost(role, inp, out)}


def test_pipeline_happy_path():
    with patch("router.pipeline.call", side_effect=_mock_call):
        result = run_pipeline("Fix the auth bug")
    assert result["route"] == "happy"
    assert result["steps"] == 3
    assert "Fixed the bug" in result["output"]


def test_pipeline_escalation():
    validator_calls = {"n": 0}

    def counting_mock(role, prompt):
        if role == "validator":
            validator_calls["n"] += 1
            if validator_calls["n"] == 1:
                # Step 3 validation fails
                content, inp, out = "FAIL - wrong logic", 150, 30
                return {"content": content, "input_tokens": inp, "output_tokens": out, "cost": estimate_cost(role, inp, out)}
        return _mock_call(role, prompt)

    with patch("router.pipeline.call", side_effect=counting_mock):
        result = run_pipeline("Fix the hard bug")
    assert result["route"] == "escalated"
    assert result["steps"] == 5


if __name__ == "__main__":
    test_models_has_four_roles()
    test_models_are_ollama_tags()
    test_pricing_positive()
    test_estimate_cost()
    test_pipeline_happy_path()
    test_pipeline_escalation()
    print("All tests passed.")