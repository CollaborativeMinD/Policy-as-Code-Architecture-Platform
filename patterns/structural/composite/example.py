"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Graph, Node
from .reference import Composite


def run_example(case: str = "nominal") -> dict[str, object]:
    weight = 2 if case == "nominal" else 10
    value = Graph(
        root="root",
        nodes=(
            Node(node_id="root", weight=weight, children=("leaf",)),
            Node(node_id="leaf", weight=1, children=()),
        ),
    )
    aggregate = Composite().aggregate(value)
    cycle = Graph(root="root", nodes=(Node(node_id="root", weight=1, children=("root",)),))
    try:
        Composite().aggregate(cycle)
    except ValueError as error:
        denied = str(error)
    return {
        "inputs": value.model_dump(),
        "computed": {"aggregate": aggregate},
        "positive_check": aggregate == weight + 1,
        "negative_detected": denied == "DENY_CYCLE",
        "negative_hypothesis": "Unchecked child recursion repeats a cyclic node indefinitely.",
    }
