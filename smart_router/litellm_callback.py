import os
import sys
import time
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from .router import select_model, CriticalBudgetError
    from .budget import BudgetTracker
except ImportError:
    from router import select_model, CriticalBudgetError
    from budget import BudgetTracker


_LOG_PATH = Path(__file__).parent.parent / "logs" / "router-usage.csv"
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_budget = None


def _init_budget():
    global _budget
    if _budget is None:
        import yaml
        config_path = Path(__file__).with_name("models.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _budget = BudgetTracker(data.get("budget", {}))
    return _budget


def log_event(timestamp: str, model: str, classification: str, input_tokens: int, output_tokens: int):
    if not _LOG_PATH.exists():
        with open(_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "model", "classification", "input_tokens", "output_tokens"])
    with open(_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, model, classification, input_tokens, output_tokens])


def litellm_pre_call_utils(kwargs):
    """LiteLLM pre-call callback: rewrite the model before the request is sent."""
    try:
        messages = kwargs.get("messages", [])
        budget = _init_budget()

        status = budget.status()
        if status == "critical":
            raise CriticalBudgetError("Daily token budget is critical. Pausing requests.")

        selected = select_model(messages, budget=budget)
        kwargs["model"] = f"ollama/{selected}"

    except CriticalBudgetError:
        raise
    except Exception:
        kwargs["model"] = "ollama/glm-5.1:cloud"


def litellm_logging_callback(kwargs, response_obj, start_time, end_time):
    """LiteLLM post-call callback: log usage and update budget."""
    try:
        model = kwargs.get("model", "unknown")
        if model.startswith("ollama/"):
            model = model[7:]

        input_tokens = response_obj.get("usage", {}).get("prompt_tokens", 0)
        output_tokens = response_obj.get("usage", {}).get("completion_tokens", 0)

        budget = _init_budget()
        budget.add_usage(input_tokens, output_tokens)

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log_event(timestamp, model, "unknown", input_tokens, output_tokens)
    except Exception:
        pass
