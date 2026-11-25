"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from pydantic import ValidationError
from .contracts import Request
from .reference import select


def run_example(case: str = "nominal") -> dict[str, object]:
    costs = (4, 1, 1) if case == "nominal" else (0, 0, 7)
    first = select(Request(algorithm="scan", costs=costs))
    second = select(Request(algorithm="sort", costs=costs))
    try:
        Request(algorithm="remote-admin", costs=costs)
    except ValidationError:
        denied = True
    oracle = min(enumerate(costs), key=lambda pair: (pair[1], pair[0]))
    return {
        "inputs": {"costs": costs},
        "computed": first.model_dump(),
        "positive_check": first == second and (first.index, first.cost) == oracle,
        "negative_detected": denied,
        "negative_hypothesis": (
            "An open strategy name selects an unreviewed algorithm or side effect."
        ),
    }
