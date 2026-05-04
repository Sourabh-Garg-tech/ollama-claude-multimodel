"""
LangGraph state machine.

Graph shape:
  hard_router → classifier → execute → det_validator → llm_judge
                                            ↓ fail
                                         escalate → execute (retry loop)
                                            ↓ max_attempts
                                         finalize
"""

from langgraph.graph import StateGraph, END

from graph.state import State
from graph.nodes import (
    hard_router,
    classifier_node,
    execute_node,
    deterministic_validator,
    llm_judge,
    escalate,
    finalize,
)


from graph.state import State, ROUTE_RETRY_BUDGET


def _should_escalate(state: State) -> str:
    """
    Edge condition after llm_judge.
    Escalate if validation failed AND we have budget remaining.
    Respect both the global cap and per-route budget.
    """
    if state["validation_passed"]:
        return "finalize"
    if state["attempts"] >= state["max_attempts"]:
        return "finalize"   # global hard cap

    current_route = state["route"]
    route_used = state["route_attempts"].get(current_route, 0)
    budget = ROUTE_RETRY_BUDGET.get(current_route, 1)
    if route_used >= budget:
        return "escalate"   # this route is exhausted → escalate even if global cap not hit

    # Still have budget on current route — retry same route
    return "execute_retry"


def build_graph() -> StateGraph:
    g = StateGraph(State)

    g.add_node("hard_router",          hard_router)
    g.add_node("classifier",           classifier_node)
    g.add_node("execute",              execute_node)
    g.add_node("det_validator",        deterministic_validator)
    g.add_node("llm_judge",            llm_judge)
    g.add_node("escalate",             escalate)
    g.add_node("finalize",             finalize)

    # Linear path
    g.set_entry_point("hard_router")
    g.add_edge("hard_router",  "classifier")
    g.add_edge("classifier",   "execute")
    g.add_edge("execute",      "det_validator")
    g.add_edge("det_validator","llm_judge")

    # Conditional branch after judge:
    #   pass              → finalize
    #   fail, budget left → execute (same route retry)
    #   fail, exhausted   → escalate → execute (new route)
    g.add_conditional_edges(
        "llm_judge",
        _should_escalate,
        {
            "finalize":      "finalize",
            "escalate":      "escalate",
            "execute_retry": "execute",   # same route, budget not yet exhausted
        },
    )

    g.add_edge("escalate", "execute")
    g.add_edge("finalize", END)

    return g.compile()


def make_initial_state(
    task: str,
    max_attempts: int = 3,
    context: dict | None = None,
) -> State:
    return State(
        input=task,
        context=context or {},
        route=None,
        initial_route=None,
        router_source=None,
        litellm_model=None,
        model_used=None,
        output=None,
        validation_passed=False,
        failure_reason=None,
        validator_results={},
        attempts=0,
        max_attempts=max_attempts,
        route_attempts={},
        escalation_count=0,
        telemetry={},
    )
