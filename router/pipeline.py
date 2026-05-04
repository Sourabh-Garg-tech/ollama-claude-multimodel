import litellm
from .models import MODELS, estimate_cost


VALIDATE_PROMPT = "Check correctness of this output. Reply with only PASS or FAIL followed by a brief reason.\n\n## Task\n{task}\n\n## Output\n{output}"


def call(role: str, prompt: str) -> dict:
    """Call a model by role. Returns content, token counts, cost."""
    response = litellm.completion(
        model=MODELS[role],
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )
    content = response.choices[0].message.content
    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    return {
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": estimate_cost(role, input_tokens, output_tokens),
    }


def run_pipeline(task: str) -> dict:
    """Plan -> Execute -> Validate -> Escalate -> Re-validate."""

    # Step 1: Plan
    plan = call("planner", task)

    # Step 2: Execute
    execute_prompt = f"## Plan\n{plan['content']}\n\n## Task\n{task}\n\nExecute the plan step by step."
    result = call("executor", execute_prompt)

    # Step 3: Validate
    validate_prompt = VALIDATE_PROMPT.format(task=task, output=result["content"])
    validation = call("validator", validate_prompt)

    if validation["content"].strip().upper().startswith("PASS"):
        return {
            "output": result["content"],
            "route": "happy",
            "cost": plan["cost"] + result["cost"] + validation["cost"],
            "steps": 3,
        }

    # Step 4: Escalate
    escalate_prompt = f"## Plan\n{plan['content']}\n\n## Task\n{task}\n\nThe initial execution failed validation. Fix it properly."
    escalated = call("coder", escalate_prompt)

    # Step 5: Re-validate
    revalidate_prompt = VALIDATE_PROMPT.format(task=task, output=escalated["content"])
    revalidation = call("validator", revalidate_prompt)

    passed = revalidation["content"].strip().upper().startswith("PASS")
    return {
        "output": escalated["content"] if passed else result["content"],
        "route": "escalated" if passed else "failed",
        "cost": plan["cost"] + result["cost"] + validation["cost"] + escalated["cost"] + revalidation["cost"],
        "steps": 5,
    }