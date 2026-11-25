"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Cursor, Record
from .reference import EvidenceIterator


def run_example(case: str = "nominal") -> dict[str, object]:
    records = (Record(record_id="b", value=2), Record(record_id="a", value=1))
    iterator = EvidenceIterator(records)
    cursor = Cursor(offset=0, snapshot_digest=iterator.snapshot_digest, expires_at=10)
    size = 1 if case == "nominal" else 2
    page = iterator.page(cursor, size, 1)
    try:
        iterator.page(cursor, size, 10)
    except ValueError as error:
        denied = str(error)
    return {
        "inputs": {"size": size, "now": 1},
        "computed": page.model_dump(),
        "positive_check": page.records[0].record_id == "a" and len(page.records) == size,
        "negative_detected": denied == "DENY_CURSOR_EXPIRED",
        "negative_hypothesis": (
            "An expired cursor keeps reading a snapshot beyond its admitted lease."
        ),
    }
