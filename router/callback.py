"""LiteLLM proxy callback: logs usage and updates budget."""
import time
import csv
from pathlib import Path

from .budget import BudgetTracker

_LOG_PATH = Path(__file__).parent.parent / "logs" / "router-usage.csv"
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_budget = None


def _init_budget():
    global _budget
    if _budget is None:
        import yaml
        config_path = Path(__file__).parent / "models.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _budget = BudgetTracker(data.get("budget", {}))
    return _budget


def litellm_logging_callback(kwargs, response_obj, start_time, end_time):
    """Post-call: log usage and update budget."""
    try:
        model = kwargs.get("model", "unknown")
        if model.startswith("ollama/"):
            model = model[7:]

        usage = response_obj.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        budget = _init_budget()
        budget.add_usage(input_tokens, output_tokens)

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