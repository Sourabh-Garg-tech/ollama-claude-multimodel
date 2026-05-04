"""
LangGraph nodes.
Each node receives State, mutates it, and returns it.
LiteLLM proxy sits at LITELLM_BASE_URL — all model calls go through it.
"""

import json
import os
import re
import time
from typing import Any

from openai import OpenAI

from graph.state import State, Route, MODEL_MAP, ESCALATION_MAP, ROUTE_RETRY_BUDGET
from validators.deterministic import run_all_validators
from telemetry.logger import (
    log_route_decision, log_execution, log_validation,
    log_escalation, log_final, record_route_outcome,
)

# ── LiteLLM proxy client ──────────────────────────────────────────────────────

client = OpenAI(
    base_url=os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
    api_key=os.getenv("LITELLM_MASTER_KEY", "sk-placeholder"),
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def token_count(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 chars."""
    return len(text) // 4


def has_code_content(text: str) -> bool:
    code_signals = [
        # Structural: actual code present
        r"```",
        r"\bdef \w+\(",
        r"\bclass \w+",
        r"\bimport \w+",
        r"\bfrom \w+ import",
        r"stack trace",
        r"traceback",
        r"\bSQL\b",
        r"\bAPI\b.*endpoint",
        # Plain-language coding intents (no code snippet needed)
        r"\brefactor\b",
        r"\bdebug\b",
        r"\bwrite a function\b",
        r"\bwrite a script\b",
        r"\bwrite.*\bcode\b",
        r"\bimplement\b.*\bfunction\b",
        r"\boptimize.*\balgorithm\b",
        r"\bfix.*\bbug\b",
        r"\bfix.*\bcode\b",
        r"\bfix this\b",
        r"\bunit test\b",
        r"\bwrite tests?\b",
        r"\bcode review\b",
        r"\balgorithm\b.*\bimplement\b",
        r"\bparsing\b.*\bcode\b",
        r"\bbuild.*\bscript\b",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in code_signals)


def is_long_running_task(text: str) -> bool:
    """
    Score-based: require 2+ signals to avoid false positives.
    Single keywords like 'loop' or 'pipeline' alone are too ambiguous.
    """
    strong_signals = [
        # Explicit persistence / temporal
        r"\bcontinuously\b", r"\bkeep running\b", r"\brun indefinitely\b",
        r"\buntil done\b", r"\buntil (it|the task) (is )?complete",
        r"\b24/7\b", r"\bbackground (agent|worker|process)\b",
        # Iteration / step count
        r"\bmany (iterations|steps|rounds)\b",
        r"\b\d{2,}\s*(steps?|iterations?|rounds?|tool calls?)\b",
        r"\bmulti-?step\b.*\bagen",
        # Long-horizon explicit framing
        r"\blong.?horizon\b", r"\bpersistent (agent|session|loop)\b",
        r"\bautonomo\w+\s+(execut|run|work)",
    ]
    weak_signals = [
        r"\bmonitor\b", r"\bpoll\b", r"\bwatch\b",
        r"\bautonomous\b", r"\bloop\b", r"\bpipeline\b",
        r"\bmulti.?step\b", r"\bagent\b", r"\bworkflow\b",
        r"\bschedule\b", r"\bperiodic\b", r"\brepeat\b",
    ]
    lower = text.lower()
    strong_hits = sum(1 for p in strong_signals if re.search(p, lower))
    if strong_hits >= 1:
        return True
    weak_hits = sum(1 for p in weak_signals if re.search(p, lower))
    return weak_hits >= 3


# ── Node 1: Hard router ───────────────────────────────────────────────────────

def hard_router(state: State) -> State:
    task = state["input"]
    route: Route | None = None
    source = "hard_rule"

    if token_count(task) > 50_000:
        route = "v4_pro"
    elif has_code_content(task):
        route = "kimi"
    elif is_long_running_task(task):
        route = "glm"
    # else → None, hand off to classifier

    state["route"] = route
    if route:
        state["initial_route"] = route
        state["router_source"] = source
        log_route_decision(route, source, task)

    return state


# ── Node 2: Flash classifier (runs only when hard router abstained) ───────────

_CLASSIFIER_SYSTEM = (
    "You are a task classifier for an LLM routing system. "
    "Return ONLY valid JSON, no prose, no markdown fences."
)

_CLASSIFIER_SCHEMA = {
    "type": "object",
    "required": ["type", "confidence", "estimated_tokens", "risk"],
    "properties": {
        "type": {"enum": ["simple_execution", "complex_reasoning", "code_generation", "long_running_task"]},
        "confidence": {"type": "number"},
        "estimated_tokens": {"type": "integer"},
        "risk": {"enum": ["low", "medium", "high"]},
    },
}

_INTENT_TO_ROUTE: dict[str, Route] = {
    "simple_execution":   "v4_flash",
    "complex_reasoning":  "v4_pro",
    "code_generation":    "kimi",
    "long_running_task":  "glm",
}


def classifier_node(state: State) -> State:
    if state["route"] is not None:
        return state   # hard router already decided

    t0 = time.perf_counter()
    prompt = json.dumps({
        "task": state["input"][:2000],   # truncate for cheap classification
        "classify_into": list(_INTENT_TO_ROUTE.keys()),
        "output_format": _CLASSIFIER_SCHEMA,
    })

    resp = client.chat.completions.create(
        model=MODEL_MAP["v4_flash"],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _CLASSIFIER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=128,
    )

    raw = resp.choices[0].message.content
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: parse type field with regex
        m = re.search(r'"type"\s*:\s*"([^"]+)"', raw)
        result = {"type": m.group(1) if m else "simple_execution", "confidence": 0.5}

    intent = result.get("type", "simple_execution")
    route: Route = _INTENT_TO_ROUTE.get(intent, "v4_flash")

    # Escalate low-confidence or medium/high-risk classifications to Pro.
    # 0.75 threshold: finance/trading prompts are often ambiguous enough
    # that Flash misclassifies at the 0.6–0.75 band.
    if result.get("confidence", 1.0) < 0.75 or result.get("risk") in ("medium", "high"):
        route = "v4_pro"

    state["route"] = route
    state["initial_route"] = route
    state["router_source"] = "classifier"
    state["telemetry"]["classifier"] = {
        **result,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }

    log_route_decision(route, "classifier", state["input"], result)
    return state


# Per-model pricing: (input $/1M, output $/1M)
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "deepseek-v4-flash": (0.27,  0.28),
    "deepseek-v4-pro":   (1.74,  3.48),
    "kimi-k2.6":         (0.95,  4.00),
    "glm-5.1":           (1.05,  3.50),
}

def _compute_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _MODEL_PRICING.get(model_name, (0.0, 0.0))
    return round(
        (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000, 6
    )


# ── Node 3: Execute ───────────────────────────────────────────────────────────

def execute_node(state: State) -> State:
    route: Route = state["route"]
    model_name = MODEL_MAP[route]
    state["litellm_model"] = model_name

    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": state["input"]}],
        temperature=0.2,
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    usage = resp.usage
    in_tok  = usage.prompt_tokens     if usage else 0
    out_tok = usage.completion_tokens if usage else 0
    cost    = _compute_cost(model_name, in_tok, out_tok)

    state["model_used"] = route
    state["output"] = resp.choices[0].message.content
    state["attempts"] += 1
    state["route_attempts"][route] = state["route_attempts"].get(route, 0) + 1

    # Accumulate per-task cost in telemetry
    state["telemetry"].setdefault("total_cost_usd", 0.0)
    state["telemetry"]["total_cost_usd"] = round(
        state["telemetry"]["total_cost_usd"] + cost, 6
    )

    log_execution(
        route=route,
        model=model_name,
        attempt=state["attempts"],
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
        cost_usd=cost,
    )
    return state


# ── Node 4: Deterministic validators ─────────────────────────────────────────

def deterministic_validator(state: State) -> State:
    ctx = state.get("context") or {}

    results = run_all_validators(
        output=state["output"],
        schema=ctx.get("expected_schema"),
        expected_tool_keys=ctx.get("expected_tool_keys"),
        check_python=ctx.get("check_python", False),
        required_phrases=ctx.get("required_phrases"),
        forbidden_phrases=ctx.get("forbidden_phrases"),
        required_entities=ctx.get("required_entities"),
    )

    state["validator_results"] = results
    state["validation_passed"] = results["all_passed"]

    if not results["all_passed"]:
        # Find first failing gate for the failure reason
        for key in ["length", "no_refusal", "schema", "syntax", "tools", "semantic"]:
            if not results.get(key, True):
                state["failure_reason"] = results.get(f"{key}_reason", key)
                break

    log_validation(
        passed=state["validation_passed"],
        results=results,
        failure_reason=state.get("failure_reason"),
    )
    return state


# ── Node 5: LLM judge (runs only when deterministic checks pass) ──────────────

_JUDGE_SYSTEM = (
    "You are a strict quality judge. "
    "Evaluate the answer and return ONLY valid JSON, no prose."
)

_JUDGE_SCHEMA = {
    "verdict": "pass | fail",
    "scores": {
        "correctness":    "0-10",
        "hallucination":  "0-10 (10 = none)",
        "constraints_met": "0-10",
    },
    "issues": ["list of specific problems, empty if none"],
}


def llm_judge(state: State) -> State:
    if not state["validation_passed"]:
        return state   # deterministic check already failed — skip judge

    ctx = state.get("context") or {}
    if not ctx.get("use_llm_judge", False):
        return state   # caller opted out

    resp = client.chat.completions.create(
        model=MODEL_MAP["v4_pro"],   # always use Pro as judge
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": json.dumps({
                "task":    state["input"],
                "output":  state["output"],
                "rubric":  _JUDGE_SCHEMA,
            })},
        ],
        temperature=0,
        max_tokens=512,
    )

    raw = resp.choices[0].message.content
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        verdict = {"verdict": "pass"}   # judge parse failure → don't block

    state["telemetry"]["judge"] = verdict

    if verdict.get("verdict") != "pass":
        state["validation_passed"] = False
        state["failure_reason"] = "quality_failure"

    return state


# ── Node 6: Escalate ──────────────────────────────────────────────────────────

def escalate(state: State) -> State:
    from_route: Route = state["route"]
    to_route: Route = ESCALATION_MAP[from_route]

    state["escalation_count"] += 1

    log_escalation(
        from_route=from_route,
        to_route=to_route,
        attempt=state["attempts"],
        reason=state.get("failure_reason", "unknown"),
    )

    state["route"] = to_route
    state["failure_reason"] = None
    state["validation_passed"] = False
    return state


# ── Node 7: Final ─────────────────────────────────────────────────────────────

def finalize(state: State) -> State:
    pipeline_success = state["validation_passed"]
    # First-route accuracy = initial route succeeded WITHOUT escalation.
    # A task that failed on Flash and was saved by Pro is NOT a router success.
    initial_route_succeeded = pipeline_success and state["escalation_count"] == 0
    record_route_outcome(state["initial_route"], initial_route_succeeded)

    log_final(
        success=pipeline_success,
        initial_route=state["initial_route"],
        final_route=state["route"],
        total_attempts=state["attempts"],
        escalation_count=state["escalation_count"],
        failure_reason=state.get("failure_reason"),
    )
    return state
