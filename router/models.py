MODELS = {
    "planner":   "deepseek-v4-pro:cloud",
    "executor":  "deepseek-v4-flash:cloud",
    "coder":     "kimi-k2.6:cloud",
    "validator": "glm-5.1:cloud",
}

PRICING = {
    "planner":   {"input_per_1m": 1.42, "output_per_1m": 0.87},
    "executor":  {"input_per_1m": 0.18, "output_per_1m": 0.18},
    "coder":     {"input_per_1m": 1.15, "output_per_1m": 4.00},
    "validator": {"input_per_1m": 1.66, "output_per_1m": 4.40},
}


def estimate_cost(role: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING[role]
    return (input_tokens * p["input_per_1m"] + output_tokens * p["output_per_1m"]) / 1_000_000