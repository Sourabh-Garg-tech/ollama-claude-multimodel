"""LiteLLM proxy callback: logs usage to CSV and updates budget.

Placed as a flat file (not in a package) because LiteLLM resolves
callbacks as module files, not Python packages.
"""
import time
import csv
import json
import os
from pathlib import Path


_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_PATH = _LOG_DIR / "proxy-usage.csv"
_STATE_PATH = _LOG_DIR / "budget-state.json"

# Budget defaults
DAILY_INPUT = 100_000
DAILY_OUTPUT = 200_000


def _load_budget():
    if _STATE_PATH.exists():
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        today = time.strftime("%Y-%m-%d")
        if data.get("date") != today:
            return {"date": today, "input_tokens": 0, "output_tokens": 0}
        return data
    return {"date": time.strftime("%Y-%m-%d"), "input_tokens": 0, "output_tokens": 0}


def _save_budget(state):
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def litellm_logging_callback(kwargs, response_obj, start_time, end_time):
    """Post-call: log usage and update budget."""
    try:
        model = kwargs.get("model", "unknown")
        if model.startswith("ollama/"):
            model = model[7:]

        usage = response_obj.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Update budget
        state = _load_budget()
        state["input_tokens"] += input_tokens
        state["output_tokens"] += output_tokens
        _save_budget(state)

        # Log to CSV
        if not _LOG_PATH.exists():
            with open(_LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "model", "input_tokens", "output_tokens"])
        with open(_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                model, input_tokens, output_tokens,
            ])
    except Exception:
        pass