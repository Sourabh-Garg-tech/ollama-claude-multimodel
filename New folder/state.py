from typing import TypedDict, Optional, Literal, Any

Route = Literal["v4_flash", "v4_pro", "kimi", "glm"]

MODEL_MAP: dict[Route, str] = {
    "v4_flash": "deepseek-v4-flash",
    "v4_pro":   "deepseek-v4-pro",
    "kimi":     "kimi-k2.6",
    "glm":      "glm-5.1",
}

ESCALATION_MAP: dict[Route, Route] = {
    "v4_flash": "v4_pro",
    "kimi":     "v4_pro",
    "glm":      "v4_pro",
    "v4_pro":   "v4_pro",   # already at ceiling
}

# Max attempts allowed per route before forced escalation.
# Flash/Kimi/Pro get 1 shot each — they're either right or we escalate.
# GLM gets 2 because long-horizon tasks may need one self-correction pass.
ROUTE_RETRY_BUDGET: dict[Route, int] = {
    "v4_flash": 1,
    "kimi":     1,
    "glm":      2,
    "v4_pro":   1,
}


class State(TypedDict):
    # Task
    input: str
    context: Optional[dict[str, Any]]   # optional caller-supplied metadata

    # Routing
    route: Optional[Route]
    initial_route: Optional[Route]
    router_source: Optional[str]        # "hard_rule" | "classifier"

    # Execution
    litellm_model: Optional[str]
    model_used: Optional[Route]
    output: Optional[str]

    # Validation
    validation_passed: bool
    failure_reason: Optional[str]
    validator_results: dict[str, Any]

    # Escalation / retry
    attempts: int
    max_attempts: int                   # global hard cap
    route_attempts: dict[str, int]      # per-route attempt counts
    escalation_count: int

    # Telemetry — every step appends here
    telemetry: dict[str, Any]
