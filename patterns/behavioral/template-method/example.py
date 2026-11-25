"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Request
from .reference import Pipeline, UppercasePipeline


def run_example(case: str = "nominal") -> dict[str, object]:
    text = " bounded " if case == "nominal" else " edge "
    value = UppercasePipeline().run(Request(text=text))
    try:
        type("UnsafePipeline", (Pipeline,), {"run": lambda self, request: None})
    except TypeError as error:
        denied = str(error)
    return {
        "inputs": {"text": text},
        "computed": value.model_dump(),
        "positive_check": value.value == text.strip().upper()
        and value.steps == ("parse", "validate", "emit"),
        "negative_detected": denied == "DENY_SKELETON_OVERRIDE",
        "negative_hypothesis": (
            "Overriding the public skeleton can skip validation and grant authority."
        ),
    }
