"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Reading
from .reference import AuditFacade


def unavailable() -> Reading:
    raise TimeoutError("bounded offline port")


def run_example(case: str = "nominal") -> dict[str, object]:
    def catalog() -> Reading:
        return Reading(subsystem="catalog", count=15)

    def evidence() -> Reading:
        return Reading(subsystem="evidence", count=1 if case == "nominal" else 2)

    value = AuditFacade(catalog, evidence).inspect()
    failed = AuditFacade(catalog, unavailable).inspect()
    return {
        "inputs": {"ports": ["catalog", "evidence"]},
        "computed": value.model_dump(),
        "positive_check": value.status == "PASS" and value.consequential_effects == 0,
        "negative_detected": failed.status == "HOLD" and failed.reason == "HOLD_SUBSYSTEM",
        "negative_hypothesis": (
            "Swallowing a port timeout and reporting PASS hides an incomplete read."
        ),
    }
