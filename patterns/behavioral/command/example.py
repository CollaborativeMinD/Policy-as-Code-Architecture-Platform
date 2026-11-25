"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

import tempfile
from pathlib import Path
from .contracts import Operation
from .reference import CommandStore


def run_example(case: str = "nominal") -> dict[str, object]:
    operation = Operation(
        operation_id="demo",
        value=2 if case == "nominal" else 8,
        mode="COMMIT_CONFINED_TEST",
        authority="fixture:effect",
    )
    with tempfile.TemporaryDirectory() as directory:
        store = CommandStore(Path(directory) / "fixture.sqlite3")
        try:
            store.execute(operation, "after_effect")
        except RuntimeError:
            rolled_back = store.counts() == (0, 0)
        first = store.execute(operation)
        repeated = store.execute(operation)
        counts = store.counts()
    return {
        "inputs": operation.model_dump(),
        "computed": {"receipt": first.model_dump(), "counts": counts},
        "positive_check": first == repeated and counts == (1, 1),
        "negative_detected": rolled_back,
        "negative_hypothesis": (
            "Committing an effect before its outbox can duplicate an unknown outcome."
        ),
    }
