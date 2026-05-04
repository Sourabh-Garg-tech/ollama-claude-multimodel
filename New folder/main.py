"""
Main entrypoint.

Usage:
    python main.py

Or import and call run_task() directly from your own code.
"""

import json
import logging
import sys

from graph.builder import build_graph, make_initial_state
from telemetry.logger import first_route_accuracy

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

graph = build_graph()


def run_task(
    task: str,
    max_attempts: int = 3,
    context: dict | None = None,
) -> dict:
    """
    Run a task through the router graph.

    Returns:
        {
            "output":           str | None,
            "success":          bool,
            "initial_route":    str,
            "final_route":      str,
            "attempts":         int,
            "escalation_count": int,
            "failure_reason":   str | None,
            "telemetry":        dict,
        }
    """
    state = make_initial_state(task, max_attempts=max_attempts, context=context)
    final = graph.invoke(state)

    return {
        "output":           final["output"],
        "success":          final["validation_passed"],
        "initial_route":    final["initial_route"],
        "final_route":      final["route"],
        "attempts":         final["attempts"],
        "escalation_count": final["escalation_count"],
        "failure_reason":   final.get("failure_reason"),
        "telemetry":        final["telemetry"],
    }


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tasks = [
        # Should route to v4_flash (simple extraction)
        "Extract the company name and revenue from this text: 'Acme Corp reported $4.2B revenue in Q1 2026.'",

        # Should route to kimi (code task)
        "Refactor this Python function to use async/await:\ndef fetch_data(url):\n    return requests.get(url).json()",

        # Should route to v4_pro (complex reasoning, large prompt simulation)
        "Analyse the trade-offs between MoE and dense transformer architectures for inference at scale.",

        # Should route to glm (long-running agent task)
        "Continuously monitor the /data/prices.csv file and alert when any value exceeds 3 standard deviations from the rolling mean.",
    ]

    for task in tasks:
        print("\n" + "─" * 70)
        print(f"TASK: {task[:80]}...")
        result = run_task(task, max_attempts=2)
        print(f"ROUTE:   {result['initial_route']} → {result['final_route']}")
        print(f"SUCCESS: {result['success']}  |  attempts={result['attempts']}  |  escalations={result['escalation_count']}")
        if result["failure_reason"]:
            print(f"FAILURE: {result['failure_reason']}")

    print("\n" + "═" * 70)
    print("First-route accuracy:", json.dumps(first_route_accuracy(), indent=2))
