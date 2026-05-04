MODELS = {
    "planner":   "ollama/deepseek-v4-pro:cloud",
    "executor":  "ollama/deepseek-v4-flash:cloud",
    "coder":     "ollama/kimi-k2.6:cloud",
    "validator": "ollama/glm-5.1:cloud",
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