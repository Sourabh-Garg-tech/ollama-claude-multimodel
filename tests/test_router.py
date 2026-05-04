import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from router.models import MODELS, PRICING, estimate_cost
from router.pipeline import run_pipeline, CriticalBudgetError
from router.budget import BudgetTracker


# --- Model tests ---

def test_models_has_four_roles():
    assert set(MODELS.keys()) == {"planner", "executor", "coder", "validator"}


def test_models_are_ollama_tags():
    for role, model in MODELS.items():
        assert ":cloud" in model, f"{role} model missing :cloud tag"


def test_pricing_positive():
    for role, prices in PRICING.items():
        assert prices["input_per_1m"] > 0, f"{role} input price zero"
        assert prices["output_per_1m"] > 0, f"{role} output price zero"


def test_estimate_cost():
    cost = estimate_cost("executor", 1_000_000, 1_000_000)
    assert cost == 0.36  # 0.18 + 0.18


# --- Budget tests ---

def test_budget_healthy():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        assert budget.status() == "healthy"


def test_budget_low():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        budget.add_usage(850, 850)
        assert budget.status() == "low"


def test_budget_critical():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        budget.add_usage(960, 960)
        assert budget.status() == "critical"


def test_budget_auto_resets_next_day():
    import json
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "budget.json")
        budget = BudgetTracker(config, path)
        budget.add_usage(500, 500)
        with open(path) as f:
            data = json.load(f)
        data["date"] = "2000-01-01"
        with open(path, "w") as f:
            json.dump(data, f)
        budget2 = BudgetTracker(config, path)
        assert budget2.status() == "healthy"


# --- Pipeline tests ---

def _mock_call(role, prompt, budget=None):
    responses = {
        "planner": ("Step 1: Read file. Step 2: Fix bug.", 100, 50),
        "executor": ("Fixed the bug in auth.py", 200, 100),
        "validator": ("PASS - output is correct", 150, 30),
        "coder": ("Fixed properly with Kimi", 200, 100),
    }
    content, inp, out = responses[role]
    return {"content": content, "input_tokens": inp, "output_tokens": out, "cost": estimate_cost(role, inp, out), "role_used": role}


def test_pipeline_happy_path():
    with patch("router.pipeline.call", side_effect=_mock_call):
        result = run_pipeline("Fix the auth bug")
    assert result["route"] == "happy"
    assert result["steps"] == 3
    assert "Fixed the bug" in result["output"]


def test_pipeline_escalation():
    validator_calls = {"n": 0}

    def counting_mock(role, prompt, budget=None):
        if role == "validator":
            validator_calls["n"] += 1
            if validator_calls["n"] == 1:
                content, inp, out = "FAIL - wrong logic", 150, 30
                return {"content": content, "input_tokens": inp, "output_tokens": out, "cost": estimate_cost(role, inp, out), "role_used": role}
        return _mock_call(role, prompt, budget=budget)

    with patch("router.pipeline.call", side_effect=counting_mock):
        result = run_pipeline("Fix the hard bug")
    assert result["route"] == "escalated"
    assert result["steps"] == 5


def test_pipeline_critical_budget():
    config = {"daily_input_tokens": 1000, "daily_output_tokens": 1000}
    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetTracker(config, os.path.join(tmp, "budget.json"))
        budget.add_usage(960, 960)
        try:
            run_pipeline("Do something", budget=budget)
            assert False, "Should have raised CriticalBudgetError"
        except CriticalBudgetError:
            pass


if __name__ == "__main__":
    test_models_has_four_roles()
    test_models_are_ollama_tags()
    test_pricing_positive()
    test_estimate_cost()
    test_budget_healthy()
    test_budget_low()
    test_budget_critical()
    test_budget_auto_resets_next_day()
    test_pipeline_happy_path()
    test_pipeline_escalation()
    test_pipeline_critical_budget()
    print("All tests passed.")