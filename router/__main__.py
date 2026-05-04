"""CLI entry point: run the pipeline from the command line.

Usage:
    python -m router "Fix the auth bug"
    python -m router "Write a palindrome checker" --budget
"""
import argparse
import sys

from .pipeline import run_pipeline
from .budget import BudgetTracker


def main():
    parser = argparse.ArgumentParser(description="Run the Plan->Execute->Validate->Escalate pipeline")
    parser.add_argument("task", help="Task description to process")
    parser.add_argument("--budget", action="store_true", help="Enable daily token budget tracking")
    args = parser.parse_args()

    budget = None
    if args.budget:
        budget = BudgetTracker({"daily_input_tokens": 100_000, "daily_output_tokens": 200_000})

    print(f"Running pipeline: {args.task}")
    print()

    result = run_pipeline(args.task, budget=budget)

    print(f"Route: {result['route']}")
    print(f"Steps: {result['steps']}")
    print(f"Cost: ${result['cost']:.6f}")
    print()
    print(result["output"])


if __name__ == "__main__":
    main()