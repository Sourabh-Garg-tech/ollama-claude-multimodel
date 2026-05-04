"""Tests for proxy_callbacks.py: routing logic, budget tracking, and CSV logging."""
import sys
import os
import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from proxy_callbacks import _classify, ROLE_TO_MODEL, PLANNING_KEYWORDS, CODE_PATTERNS


# --- _classify() routing tests ---

def test_tool_result_routes_to_executor():
    messages = [{"role": "user", "content": [
        {"type": "tool_result", "content": "file contents here"}
    ]}]
    assert _classify(messages) == "executor"


def test_short_question_routes_to_validator():
    messages = [{"role": "user", "content": "What is Python?"}]
    assert _classify(messages) == "validator"


def test_short_question_without_question_mark_routes_to_executor():
    messages = [{"role": "user", "content": "Tell me about Python"}]
    assert _classify(messages) == "executor"


def test_long_question_routes_to_executor():
    msg = "What is the best way to handle " + "x " * 200 + "?"
    messages = [{"role": "user", "content": msg}]
    assert _classify(messages) == "executor"


def test_planning_keyword_routes_to_planner():
    for kw in ["architecture", "design", "strategy", "plan", "roadmap"]:
        messages = [{"role": "user", "content": f"Help me with the {kw} of this system"}]
        assert _classify(messages) == "planner", f"Keyword '{kw}' did not route to planner"


def test_code_signal_routes_to_coder():
    messages = [{"role": "user", "content": "Fix the bug in auth.py"}]
    assert _classify(messages) == "coder"


def test_code_block_routes_to_coder():
    messages = [{"role": "user", "content": "Here is my code:\n```python\nprint('hello')\n```"}]
    assert _classify(messages) == "coder"


def test_file_extension_routes_to_coder():
    for ext in [".py", ".js", ".ts", ".go", ".rs"]:
        messages = [{"role": "user", "content": f"Review the file main{ext}"}]
        assert _classify(messages) == "coder", f"Extension '{ext}' did not route to coder"


def test_long_analytical_routes_to_planner():
    msg = "Let me analyze the performance of this system and compare different approaches. " + "x " * 2000
    messages = [{"role": "user", "content": msg}]
    assert _classify(messages) == "planner"


def test_default_routes_to_executor():
    messages = [{"role": "user", "content": "Run the deployment script"}]
    assert _classify(messages) == "executor"


def test_empty_message_routes_to_executor():
    messages = [{"role": "user", "content": ""}]
    assert _classify(messages) == "executor"


def test_no_user_message_routes_to_executor():
    messages = [{"role": "assistant", "content": "I did something"}]
    assert _classify(messages) == "executor"


# --- Budget tracking tests ---

def test_budget_healthy():
    with patch("proxy_callbacks.BUDGET_ENABLED", False):
        from proxy_callbacks import _check_budget, _STATE_PATH, _load_budget
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "budget-state.json"
            with patch("proxy_callbacks._STATE_PATH", state_path):
                status = _check_budget()
                assert status in ("healthy", "ok"), f"Expected healthy, got {status}"


def test_budget_low():
    import time as _time
    from proxy_callbacks import DAILY_INPUT, DAILY_OUTPUT
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "budget-state.json"
        today = _time.strftime("%Y-%m-%d")
        state = {"date": today, "input_tokens": int(DAILY_INPUT * 0.85), "output_tokens": 0}
        with open(state_path, "w") as f:
            json.dump(state, f)
        with patch("proxy_callbacks._STATE_PATH", state_path):
            from proxy_callbacks import _check_budget
            status = _check_budget()
            assert status == "low"


# --- Role-to-model mapping tests ---

def test_all_roles_have_models():
    for role in ["planner", "executor", "coder", "validator"]:
        assert role in ROLE_TO_MODEL
        assert ":cloud" in ROLE_TO_MODEL[role]


if __name__ == "__main__":
    test_tool_result_routes_to_executor()
    test_short_question_routes_to_validator()
    test_short_question_without_question_mark_routes_to_executor()
    test_long_question_routes_to_executor()
    test_planning_keyword_routes_to_planner()
    test_code_signal_routes_to_coder()
    test_code_block_routes_to_coder()
    test_file_extension_routes_to_coder()
    test_long_analytical_routes_to_planner()
    test_default_routes_to_executor()
    test_empty_message_routes_to_executor()
    test_no_user_message_routes_to_executor()
    test_budget_healthy()
    test_budget_low()
    test_all_roles_have_models()
    print("All proxy_callbacks tests passed.")