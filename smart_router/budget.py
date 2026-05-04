import json
import os
import time
from pathlib import Path


class BudgetTracker:
    def __init__(self, config: dict, state_path: str | None = None):
        self.daily_input_limit = config.get("daily_input_tokens", 100_000)
        self.daily_output_limit = config.get("daily_output_tokens", 200_000)
        self.hard_stop = config.get("hard_stop_on_critical", True)
        self.low_pct = config.get("low_budget_percent", 20)
        self.critical_pct = config.get("critical_budget_percent", 5)

        if state_path is None:
            state_path = os.path.join(
                os.path.dirname(__file__), "..", "logs", "budget-state.json"
            )
        self.state_path = Path(state_path).resolve()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        self._state = self._load()

    def _load(self) -> dict:
        if self.state_path.exists():
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") != time.strftime("%Y-%m-%d"):
                return self._fresh_state()
            return data
        return self._fresh_state()

    def _fresh_state(self) -> dict:
        return {
            "date": time.strftime("%Y-%m-%d"),
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _save(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f)

    def add_usage(self, input_tokens: int, output_tokens: int):
        self._state["input_tokens"] += input_tokens
        self._state["output_tokens"] += output_tokens
        self._save()

    def status(self) -> str:
        input_pct = (self._state["input_tokens"] / self.daily_input_limit) * 100
        output_pct = (self._state["output_tokens"] / self.daily_output_limit) * 100
        max_pct = max(input_pct, output_pct)

        if max_pct >= 100 - self.critical_pct:
            return "critical"
        if max_pct >= 100 - self.low_pct:
            return "low"
        return "healthy"

    def remaining(self) -> dict:
        return {
            "input": max(0, self.daily_input_limit - self._state["input_tokens"]),
            "output": max(0, self.daily_output_limit - self._state["output_tokens"]),
        }
