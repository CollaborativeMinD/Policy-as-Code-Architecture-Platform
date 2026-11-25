"""PG-CONTRACT-001: malformed telemetry never reaches the database API."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from hmt_pg_patterns.models import BatchSpec, Metric, QueryWindow


def metric(**changes):
    values = dict(id=1, status="active", telemetry={"temp": 20.5}, observed_at=datetime.now(UTC))
    values.update(changes)
    return Metric(**values)


def test_valid_metric_and_window():
    assert metric().telemetry["temp"] == 20.5
    assert QueryWindow().limit == 1000
    assert BatchSpec().batch_size == 256


@pytest.mark.parametrize(
    "changes",
    [
        {"id": True},
        {"id": 0},
        {"id": 2**63},
        {"status": "active' OR 1=1 --"},
        {"telemetry": {"bad-key": 1.0}},
        {"telemetry": {"x": float("inf")}},
        {"telemetry": {"x": float("nan")}},
        {"telemetry": {"x": True}},
        {"telemetry": {f"x{i}": 1.0 for i in range(65)}},
        {"observed_at": datetime(2026, 1, 1)},
        {"unexpected": 1},
    ],
)
def test_contract_rejects_invalid_metric(changes):
    with pytest.raises(ValidationError):
        metric(**changes)


@pytest.mark.parametrize(
    "factory,values",
    [
        (QueryWindow, {"after_id": -1}),
        (QueryWindow, {"limit": 0}),
        (QueryWindow, {"limit": 10001}),
        (BatchSpec, {"batch_size": 0}),
        (BatchSpec, {"max_rows": 1000001}),
        (BatchSpec, {"batch_size": True}),
    ],
)
def test_resource_bounds(factory, values):
    with pytest.raises(ValidationError):
        factory(**values)
