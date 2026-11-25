"""PG-BULK-001 / PG-ANALYTICS-001: atomic batches and actual server cursor lifetime."""

from contextlib import closing

import polars as pl
import psycopg
import pytest
from driver_samples import sample

from hmt_pg_patterns.analytics import metric_frames
from hmt_pg_patterns.bulk import copy_metrics, pipeline_metrics
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.sync_driver import fetch_metrics, insert_metric

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("writer", [copy_metrics, pipeline_metrics])
def test_atomic_bulk_and_duplicate_rollback(pg_conn, writer):
    assert writer(pg_conn, [sample(1), sample(2)]) == 2
    with pytest.raises(psycopg.errors.UniqueViolation):
        writer(pg_conn, [sample(3), sample(1), sample(4)])
    assert [row.id for row in fetch_metrics(pg_conn, QueryWindow())] == [1, 2]
    assert writer(pg_conn, []) == 0


def test_server_cursor_batches_have_explicit_stable_schema(pg_conn):
    for item in range(1, 8):
        insert_metric(pg_conn, sample(item))
    frames = list(metric_frames(pg_conn, QueryWindow(limit=6), batch_size=2))
    assert [frame.height for frame in frames] == [2, 2, 2]
    frame = pl.concat(frames)
    assert frame["id"].to_list() == [1, 2, 3, 4, 5, 6]
    assert frame.schema["observed_at"] == pl.Datetime("us", "UTC")
    assert frame.schema["telemetry_json"] == pl.String
    assert list(metric_frames(pg_conn, QueryWindow(after_id=8))) == []


def test_early_generator_close_releases_cursor_and_transaction(pg_conn):
    for item in range(1, 5):
        insert_metric(pg_conn, sample(item))
    with closing(metric_frames(pg_conn, QueryWindow(), batch_size=1)) as frames:
        assert next(frames).height == 1
        assert pg_conn.execute("SELECT count(*) FROM pg_cursors").fetchone()[0] == 1
    assert pg_conn.execute("SELECT count(*) FROM pg_cursors").fetchone()[0] == 0
    assert pg_conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


def test_bulk_validates_entire_batch_before_first_database_effect(pg_conn):
    bad = sample().model_copy(update={"id": "2"})
    with pytest.raises(ValueError):
        copy_metrics(pg_conn, [sample(), bad])
    assert fetch_metrics(pg_conn, QueryWindow()) == []
