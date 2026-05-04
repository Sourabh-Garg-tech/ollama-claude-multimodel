import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "smart_router"))

from classifier import classify, classify_description
from budget import BudgetTracker
from router import select_model, CriticalBudgetError


def test_classify_lookup():
    messages = [{"role": "user", "content": "What is Python?"}]
    assert classify(messages) == "lookup"
    print("PASS: classify_lookup")


def test_classify_planning():
    messages = [{"role": "user", "content": "Design the architecture for a microservices system."}]
    assert classify(messages) == "planning"
    print("PASS: classify_planning")


def test_classify_code():
    messages = [{"role": "user", "content": "Fix this bug in main.py: def foo(): pass"}]
    assert classify(messages) == "code"
    print("PASS: classify_code")


def test_classify_complex():
    text = "Analyze and compare the performance of these three database solutions in detail. Evaluate tradeoffs. " * 30
    messages = [{"role": "user", "content": text}]
    result = classify(messages)
    assert result == "complex", f"Expected complex, got {result} (len={len(text)})"
    print("PASS: classify_complex")


def test_classify_description():
    assert classify_description("How do I sort a list in Python?") == "lookup"
    assert classify_description("Implement a REST API with FastAPI") == "code"
    print("PASS: classify_description")


def test_budget_tracking():
    config = {
        "daily_input_tokens": 1000,
        "daily_output_tokens": 1000,
        "low_budget_percent": 20,
        "critical_budget_percent": 5,
    }
    with tempfile.TemporaryDirectory() as tmp:
        state_path = os.path.join(tmp, "budget.json")
        budget = BudgetTracker(config, state_path)

        assert budget.status() == "healthy"
        budget.add_usage(500, 500)
        assert budget.status() == "healthy"
        budget.add_usage(400, 400)
        assert budget.status() == "low"
        budget.add_usage(200, 200)
        assert budget.status() == "critical"
        print("PASS: budget_tracking")


def test_router_healthy():
    messages = [{"role": "user", "content": "What is Python?"}]
    model = select_model(messages)
    assert model == "glm-5.1:cloud"
    print("PASS: router_healthy_lookup")

    messages = [{"role": "user", "content": "Design an architecture"}]
    model = select_model(messages)
    assert model == "deepseek-v4-pro:cloud"
    print("PASS: router_healthy_planning")


def test_router_low_budget():
    config = {
        "daily_input_tokens": 100,
        "daily_output_tokens": 100,
        "low_budget_percent": 20,
        "critical_budget_percent": 5,
    }
    with tempfile.TemporaryDirectory() as tmp:
        state_path = os.path.join(tmp, "budget.json")
        budget = BudgetTracker(config, state_path)
        budget.add_usage(85, 85)

        messages = [{"role": "user", "content": "Design an architecture"}]
        model = select_model(messages, budget=budget)
        assert model == "glm-5.1:cloud"  # downgraded due to low budget
        print("PASS: router_low_budget")


def test_router_critical_budget():
    config = {
        "daily_input_tokens": 100,
        "daily_output_tokens": 100,
        "low_budget_percent": 20,
        "critical_budget_percent": 5,
    }
    with tempfile.TemporaryDirectory() as tmp:
        state_path = os.path.join(tmp, "budget.json")
        budget = BudgetTracker(config, state_path)
        budget.add_usage(99, 99)

        messages = [{"role": "user", "content": "Hello"}]
        try:
            select_model(messages, budget=budget)
            assert False, "Should have raised CriticalBudgetError"
        except CriticalBudgetError:
            print("PASS: router_critical_budget")


if __name__ == "__main__":
    test_classify_lookup()
    test_classify_planning()
    test_classify_code()
    test_classify_complex()
    test_classify_description()
    test_budget_tracking()
    test_router_healthy()
    test_router_low_budget()
    test_router_critical_budget()
    print("\nAll tests passed.")
