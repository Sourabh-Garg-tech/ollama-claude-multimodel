"""
Telemetry — structured per-step logging.
Writes to stdout (JSON lines) so it pipes into any log aggregator.
Swap the sink for your own (DataDog, Loki, etc.) without changing graph nodes.
"""

import json
import time
import logging
from typing import Any

logger = logging.getLogger("llm_router.telemetry")


def _emit(event: str, data: dict[str, Any]) -> None:
    record = {"ts": time.time(), "event": event, **data}
    print(json.dumps(record, default=str))
    logger.debug(record)


def log_route_decision(
    route: str,
    source: str,           # "hard_rule" | "classifier"
    input_preview: str,    # first 120 chars
    classifier_meta: dict | None = None,
) -> None:
    _emit("route_decision", {
        "route": route,
        "source": source,
        "input_preview": input_preview[:120],
        "classifier": classifier_meta or {},
    })


def log_execution(
    route: str,
    model: str,
    attempt: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: float | None = None,
    cost_usd: float | None = None,
) -> None:
    _emit("execution", {
        "route": route,
        "model": model,
        "attempt": attempt,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
    })


def log_validation(
    passed: bool,
    results: dict[str, Any],
    failure_reason: str | None = None,
) -> None:
    _emit("validation", {
        "passed": passed,
        "failure_reason": failure_reason,
        "results": results,
    })


def log_escalation(
    from_route: str,
    to_route: str,
    attempt: int,
    reason: str,
) -> None:
    _emit("escalation", {
        "from_route": from_route,
        "to_route": to_route,
        "attempt": attempt,
        "reason": reason,
    })


def log_final(
    success: bool,
    initial_route: str,
    final_route: str,
    total_attempts: int,
    escalation_count: int,
    failure_reason: str | None = None,
) -> None:
    _emit("final", {
        "success": success,
        "initial_route": initial_route,
        "final_route": final_route,
        "total_attempts": total_attempts,
        "escalation_count": escalation_count,
        "failure_reason": failure_reason,
    })


# ── First-route accuracy tracker (in-memory, swap for Redis/DB in prod) ──────

_stats: dict[str, dict[str, int]] = {}   # route → {success, fail}


def record_route_outcome(route: str, success: bool) -> None:
    bucket = _stats.setdefault(route, {"success": 0, "fail": 0})
    bucket["success" if success else "fail"] += 1


def first_route_accuracy() -> dict[str, float]:
    out = {}
    for route, counts in _stats.items():
        total = counts["success"] + counts["fail"]
        out[route] = round(counts["success"] / total, 3) if total else 0.0
    return out
