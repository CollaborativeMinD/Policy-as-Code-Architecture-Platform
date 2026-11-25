"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Config
from .reference import Builder


def run_example(case: str = "nominal") -> dict[str, object]:
    limit = 3 if case == "nominal" else 8
    built = Builder("reviewer").with_limit(limit).finish()
    direct = Config(owner="reviewer", limit=limit, enabled=True)
    try:
        Builder("reviewer").finish()
    except ValueError as error:
        denied = str(error)
    return {
        "inputs": {"limit": limit},
        "computed": built.model_dump(),
        "positive_check": built == direct,
        "negative_detected": denied == "DENY_INCOMPLETE_BUILDER",
        "negative_hypothesis": "A partial mutable dict can escape without its required limit.",
    }
