import yaml
from pathlib import Path

try:
    from .classifier import classify
    from .budget import BudgetTracker
except ImportError:
    from classifier import classify
    from budget import BudgetTracker


_CONFIG_PATH = Path(__file__).with_name("models.yaml")


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def select_model(messages: list[dict], budget: BudgetTracker | None = None) -> str:
    """Pick the best model for a given prompt, considering classification and budget."""
    config = _load_config()
    classification = classify(messages)

    matrix = config.get("routing_matrix", {})
    classification_routing = matrix.get(classification, matrix.get("default", {}))

    if budget is not None:
        status = budget.status()
        if status == "critical":
            raise CriticalBudgetError("Daily token budget is critical. Pausing requests.")
        if status == "low":
            return classification_routing.get("low_budget", "glm-5.1:cloud")

    return classification_routing.get("healthy", "kimi-k2.6:cloud")


def select_model_from_description(description: str, budget: BudgetTracker | None = None) -> str:
    """Convenience for the launcher GUI."""
    messages = [{"role": "user", "content": description}]
    return select_model(messages, budget)


class CriticalBudgetError(Exception):
    pass
