"""PG-QUERY-001: no unchecked DTO/identifier or unbounded iterable admission."""

from itertools import repeat

import pytest
from driver_samples import sample
from pydantic import ValidationError

from hmt_pg_patterns.driver_contracts import owned_transaction, pool_limits
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.queries import bounded_metrics, qualified_table, snapshot_metric, window_values

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "value", ["metrics;DROP TABLE x", "public.metrics", "\nmetrics", "Metrics", ""]
)
def test_identifier_allowlist_rejects_sql_text(value):
    with pytest.raises(ValueError, match="TABLE_NOT_ADMITTED"):
        qualified_table(value)


def test_identifier_is_quoted_and_schema_qualified():
    assert qualified_table("metrics").as_string() == '"hmt_pg"."metrics"'


def test_validation_bypass_and_nested_mutation_are_rejected_or_snapshotted():
    metric = sample()
    snapshot = snapshot_metric(metric)
    metric.telemetry["temperature"] = 99.0
    assert snapshot.telemetry["temperature"] == 42.25
    bad = metric.model_copy(update={"id": "1"})
    with pytest.raises(ValidationError):
        snapshot_metric(bad)
    with pytest.raises(ValidationError):
        window_values(QueryWindow.model_construct(status="active' OR true--", after_id=0, limit=1))


def test_infinite_iterator_has_finite_rejection_boundary():
    with pytest.raises(ValueError, match="BATCH_ROW_LIMIT"):
        bounded_metrics(repeat(sample()))
    assert bounded_metrics([]) == []
    assert len(bounded_metrics([sample()])) == 1


@pytest.mark.parametrize("value", [0, 6, True, 1.0])
def test_retry_bounds_rejected_before_connection_use(value):
    with pytest.raises(ValueError, match="ATTEMPTS_OUT_OF_RANGE"):
        owned_transaction(None, value)


@pytest.mark.parametrize(
    "size,timeout", [(0, 1), (33, 1), (True, 1), (1, 0), (1, 31), (1, float("inf")), (1, True)]
)
def test_pool_and_teardown_deadlines_are_finite(size, timeout):
    with pytest.raises(ValueError):
        pool_limits(size, timeout)
