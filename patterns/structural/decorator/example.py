"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Call
from .reference import read_reference, scanner, semantic, watchdog


def run_example(case: str = "nominal") -> dict[str, object]:
    call = Call(authorized=True, semantic_label="READ", source_intact=True)
    value = read_reference(call)
    wrong = semantic(scanner(watchdog(lambda request: None)))
    try:
        wrong(call)
    except ValueError as error:
        denied = str(error)
    return {
        "inputs": call.model_dump(),
        "computed": value.model_dump(),
        "positive_check": value.stages == ("scanner", "semantic", "watchdog", "target"),
        "negative_detected": denied == "DENY_GUARD_ORDER",
        "negative_hypothesis": "Reordered wrappers can admit a target before required guards.",
    }
