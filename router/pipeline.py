import time
from ollama import Client
from .models import MODELS, estimate_cost
from .budget import BudgetTracker


VALIDATE_PROMPT = "Check correctness of this output. Reply with only PASS or FAIL followed by a brief reason.\n\n## Task\n{task}\n\n## Output\n{output}"

# On low budget, executor downgrades to the cheapest model
BUDGET_DOWNGRADE = {"executor": "validator"}

# Simple retry: 3 attempts with 5s backoff
MAX_RETRIES = 3
RETRY_BACKOFF = 5

_client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(host="http://localhost:11434")
    return _client


def call(role: str, prompt: str, budget: BudgetTracker | None = None) -> dict:
    """Call a model by role. Returns content, token counts, cost."""
    effective_role = role
    if budget and budget.status() == "low" and role in BUDGET_DOWNGRADE:
        effective_role = BUDGET_DOWNGRADE[role]
    if budget and budget.status() == "critical":
        raise CriticalBudgetError("Daily token budget is critical. Pausing requests.")

    model = MODELS[effective_role]
    client = _get_client()

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.message.content
            input_tokens = response.prompt_eval_count or 0
            output_tokens = response.eval_count or 0

            if budget:
                budget.add_usage(input_tokens, output_tokens)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": estimate_cost(effective_role, input_tokens, output_tokens),
                "role_used": effective_role,
            }
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF)
            else:
                raise


class CriticalBudgetError(Exception):
    pass


def run_pipeline(task: str, budget: BudgetTracker | None = None) -> dict:
    """Plan -> Execute -> Validate -> Escalate -> Re-validate."""

    # Step 1: Plan
    plan = call("planner", task, budget=budget)

    # Step 2: Execute
    execute_prompt = f"## Plan\n{plan['content']}\n\n## Task\n{task}\n\nExecute the plan step by step."
    result = call("executor", execute_prompt, budget=budget)

    # Step 3: Validate
    validate_prompt = VALIDATE_PROMPT.format(task=task, output=result["content"])
    validation = call("validator", validate_prompt, budget=budget)

    if validation["content"].strip().upper().startswith("PASS"):
        return {
            "output": result["content"],
            "route": "happy",
            "cost": plan["cost"] + result["cost"] + validation["cost"],
            "steps": 3,
        }

    # Step 4: Escalate
    escalate_prompt = f"## Plan\n{plan['content']}\n\n## Task\n{task}\n\nThe initial execution failed validation. Fix it properly."
    escalated = call("coder", escalate_prompt, budget=budget)

    # Step 5: Re-validate
    revalidate_prompt = VALIDATE_PROMPT.format(task=task, output=escalated["content"])
    revalidation = call("validator", revalidate_prompt, budget=budget)

    passed = revalidation["content"].strip().upper().startswith("PASS")
    return {
        "output": escalated["content"] if passed else result["content"],
        "route": "escalated" if passed else "failed",
        "cost": plan["cost"] + result["cost"] + validation["cost"] + escalated["cost"] + revalidation["cost"],
        "steps": 5,
    }