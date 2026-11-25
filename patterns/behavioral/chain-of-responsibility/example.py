"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Context
from .reference import GuardChain


def run_example(case: str = "nominal") -> dict[str, object]:
    context = Context(
        authenticated=True,
        current_policy=True,
        evidence_intact=True,
        receipt_bound=case == "nominal",
    )
    value = GuardChain().check(context)
    denied = GuardChain().check(context.model_copy(update={"current_policy": False}))
    try:
        GuardChain(("authenticate", "evidence", "receipt"))
    except ValueError:
        missing_denied = True
    return {
        "inputs": context.model_dump(),
        "computed": value.model_dump(),
        "positive_check": value.disposition == ("READ_ADMITTED" if case == "nominal" else "DENY")
        and value.consequential_effects == 0,
        "negative_detected": missing_denied and denied.visited == ("authenticate", "policy"),
        "negative_hypothesis": (
            "Omitting a policy handler admits stale authority; later handlers must not run."
        ),
    }
