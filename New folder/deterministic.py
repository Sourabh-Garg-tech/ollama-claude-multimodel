"""
Deterministic validators — run before any LLM judge.
Fast, cheap, reproducible.  Each returns (passed: bool, reason: str).
"""

import json
import ast
import re
import time
from typing import Any


def validate_json_schema(output: str, schema: dict | None = None) -> tuple[bool, str]:
    """Check the output is valid JSON and optionally matches a schema."""
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as e:
        return False, f"invalid_json: {e}"

    if schema is None:
        return True, "ok"

    # Basic key presence check (swap for jsonschema lib if you need full validation)
    required = schema.get("required", [])
    missing = [k for k in required if k not in parsed]
    if missing:
        return False, f"missing_keys: {missing}"

    return True, "ok"


def validate_python_syntax(output: str) -> tuple[bool, str]:
    """Extract and parse any Python code blocks in the output."""
    blocks = re.findall(r"```(?:python)?\n(.*?)```", output, re.DOTALL)
    if not blocks:
        return True, "no_code_blocks"   # nothing to validate

    for block in blocks:
        try:
            ast.parse(block)
        except SyntaxError as e:
            return False, f"syntax_error: {e}"

    return True, "ok"


def validate_tool_results(output: str, expected_tool_keys: list[str] | None = None) -> tuple[bool, str]:
    """
    If the task expected tool calls, check they appear in the output.
    expected_tool_keys is a list of strings that must be present.
    """
    if not expected_tool_keys:
        return True, "no_tool_validation_required"

    missing = [k for k in expected_tool_keys if k not in output]
    if missing:
        return False, f"missing_tool_keys: {missing}"

    return True, "ok"


def validate_semantic_constraints(
    output: str,
    required_phrases: list[str] | None = None,
    forbidden_phrases: list[str] | None = None,
    required_entities: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Lightweight semantic checks that don't require an LLM.
    - required_phrases: strings that MUST appear in the output
    - forbidden_phrases: strings that MUST NOT appear
    - required_entities: named entities (case-insensitive) that must be present
    These cover the gap between structural validity and semantic correctness
    for well-defined tasks (e.g. extraction, data transformation).
    """
    if required_phrases:
        missing = [p for p in required_phrases if p not in output]
        if missing:
            return False, f"missing_required_phrases: {missing}"

    if forbidden_phrases:
        found = [p for p in forbidden_phrases if p.lower() in output.lower()]
        if found:
            return False, f"forbidden_phrases_present: {found}"

    if required_entities:
        lower_out = output.lower()
        missing = [e for e in required_entities if e.lower() not in lower_out]
        if missing:
            return False, f"missing_required_entities: {missing}"

    return True, "ok"



    """Sanity-check output length."""
    n = len(output)
    if n < min_chars:
        return False, f"output_too_short: {n} chars"
    if n > max_chars:
        return False, f"output_too_long: {n} chars"
    return True, "ok"


def validate_no_refusal(output: str) -> tuple[bool, str]:
    """Detect common model refusal patterns."""
    refusal_phrases = [
        "i cannot", "i'm unable to", "i am unable to",
        "as an ai", "i don't have the ability",
        "i must decline", "i'm not able to",
    ]
    lower = output.lower()
    for phrase in refusal_phrases:
        if phrase in lower:
            return False, f"refusal_detected: '{phrase}'"
    return True, "ok"


def run_all_validators(
    output: str,
    schema: dict | None = None,
    expected_tool_keys: list[str] | None = None,
    check_python: bool = False,
    required_phrases: list[str] | None = None,
    forbidden_phrases: list[str] | None = None,
    required_entities: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the full deterministic suite and return a structured results dict.
    All checks run regardless of earlier failures so you get full diagnostics.
    """
    start = time.perf_counter()

    results: dict[str, Any] = {}

    results["length"], results["length_reason"]           = validate_length(output)
    results["no_refusal"], results["no_refusal_reason"]   = validate_no_refusal(output)

    if schema is not None:
        results["schema"], results["schema_reason"]       = validate_json_schema(output, schema)
    else:
        results["schema"], results["schema_reason"]       = True, "skipped"

    if check_python:
        results["syntax"], results["syntax_reason"]       = validate_python_syntax(output)
    else:
        results["syntax"], results["syntax_reason"]       = True, "skipped"

    if expected_tool_keys:
        results["tools"], results["tools_reason"]         = validate_tool_results(output, expected_tool_keys)
    else:
        results["tools"], results["tools_reason"]         = True, "skipped"

    if any([required_phrases, forbidden_phrases, required_entities]):
        results["semantic"], results["semantic_reason"]   = validate_semantic_constraints(
            output, required_phrases, forbidden_phrases, required_entities
        )
    else:
        results["semantic"], results["semantic_reason"]   = True, "skipped"

    gate_keys = ["length", "no_refusal", "schema", "syntax", "tools", "semantic"]
    results["all_passed"] = all(results[k] for k in gate_keys)
    results["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 1)

    return results
