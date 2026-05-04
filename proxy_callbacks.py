"""LiteLLM proxy callback: auto-routes requests + logs usage.

Uses LiteLLM's CustomLogger interface for the proxy. The async_pre_call_hook
inspects each request and rewrites the model to the best fit. The
async_post_call_success_hook logs usage and updates budget.

Auto-routing rules (checked in order):
  1. Tool results → V4 Flash (cheap execution)
  2. Short questions → GLM-5.1 (quick lookups)
  3. Planning keywords → V4 Pro (best reasoning)
  4. Code signals → Kimi K2.6 (best coding)
  5. Long + analytical → V4 Pro
  6. Everything else → V4 Flash (cheapest, default)
"""
import re
import time
import csv
import json
import asyncio
from pathlib import Path
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import DualCache, UserAPIKeyAuth
from litellm.types.utils import CallTypesLiteral


# --- Routing logic ---

PLANNING_KEYWORDS = [
    "architecture", "design", "strategy", "plan", "roadmap",
    "structure", "organize", "approach", "blueprint", "system design",
    "refactor the", "rewrite the", "migrate from",
]

CODE_PATTERNS = [
    r"```[a-z]*\n",
    r"\.(py|js|ts|tsx|go|rs|java|cpp|c|h)\b",
    r"\b(fix|debug|implement|build|compile|test|deploy)\b",
    r"\b(error|exception|traceback|bug|issue)\b",
    r"\b(function|class|method|variable|import)\b",
]

COMPLEX_MIN_CHARS = 2000
COMPLEX_KEYWORDS = ["analyze", "compare", "evaluate", "assess", "deep dive"]
LOOKUP_MAX_CHARS = 200

ROLE_TO_MODEL = {
    "planner":   "deepseek-v4-pro:cloud",
    "executor":  "deepseek-v4-flash:cloud",
    "coder":     "kimi-k2.6:cloud",
    "validator": "glm-5.1:cloud",
}


def _classify(messages: list) -> str:
    """Classify the latest user message to pick the best model."""
    user_msg = ""
    for msg in reversed(messages):
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_result":
                    return "executor"
                if block.get("type") == "text":
                    user_msg = block.get("text", "")
                    break
        elif isinstance(content, str) and msg.get("role") == "user":
            user_msg = content
            break

    if not user_msg:
        return "executor"

    length = len(user_msg)

    if length < LOOKUP_MAX_CHARS and user_msg.strip().endswith("?"):
        return "validator"

    if any(kw in user_msg.lower() for kw in PLANNING_KEYWORDS):
        return "planner"

    if any(re.search(p, user_msg, re.IGNORECASE) for p in CODE_PATTERNS):
        return "coder"

    if length >= COMPLEX_MIN_CHARS:
        if any(kw in user_msg.lower() for kw in COMPLEX_KEYWORDS):
            return "planner"

    return "executor"


# --- CustomLogger for LiteLLM Proxy ---

_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_PATH = _LOG_DIR / "proxy-usage.csv"
_STATE_PATH = _LOG_DIR / "budget-state.json"

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


class AutoRouter(CustomLogger):
    """LiteLLM Proxy callback that auto-routes requests to the best model."""

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: CallTypesLiteral,
    ) -> dict:
        """Route each request to the best model based on content."""
        try:
            messages = data.get("messages", [])
            role = _classify(messages)
            selected = ROLE_TO_MODEL[role]
            data["model"] = selected
        except Exception:
            data["model"] = "deepseek-v4-flash:cloud"
        return data

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        response,
    ):
        """Log usage and update budget after each successful call."""
        try:
            model = data.get("model", "unknown")
            if model.startswith("ollama/"):
                model = model[7:]

            if hasattr(response, "usage"):
                input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
            else:
                input_tokens = 0
                output_tokens = 0

            state = _load_budget()
            state["input_tokens"] += input_tokens
            state["output_tokens"] += output_tokens
            _save_budget(state)

            if not _LOG_PATH.exists():
                with open(_LOG_PATH, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "model", "input_tokens", "output_tokens", "route"])
            with open(_LOG_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    model, input_tokens, output_tokens,
                    data.get("_route", ""),
                ])
        except Exception:
            pass


proxy_handler_instance = AutoRouter()