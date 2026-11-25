"""Pool, migration, Tailcat child binding, and bounded analytics reference flows."""

from contextlib import closing
from itertools import repeat
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from psycopg_pool import PoolTimeout
import pytest

from authority_samples import KEY, counts
from crossjoin_e2e_flow import PAYLOAD, prepare
from driver_samples import sample
from hmt_pg_patterns.analytics import metric_frames
from hmt_pg_patterns.bulk import pipeline_metrics
from hmt_pg_patterns.migrations import apply_migrations
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.pools import sync_pool
from hmt_pg_patterns.sync_driver import fetch_metrics, insert_metric, transaction_retry
from hmt_pg_patterns.transport import PeerBindingError, TailcatBinding, bind_tailcat_connection


def pool_capacity(live):
    with sync_pool(live.config, size=1, timeout=0.1) as pool:
        with pool.connection() as lease:
            transaction_retry(lease, lambda conn: insert_metric(conn, sample()))
            with pytest.raises(PoolTimeout):
                pool.getconn(timeout=0.02)
        with pool.connection() as second:
            with closing(metric_frames(second, QueryWindow(), 1)) as frames:
                assert next(frames)["id"].to_list() == [1]
    assert pool.closed and fetch_metrics(live.conn, QueryWindow()) == [sample()]
    return "bounded_pool_transaction_and_analytics"


def migration_drift(live):
    with TemporaryDirectory(prefix="pg-crossjoin-e2e-migration-") as folder:
        root = Path(folder)
        source = root / "96_crossjoin.sql"
        source.write_text("SELECT 1")
        with live.conn.transaction():
            assert apply_migrations(live.conn, root) == [source.name]
            source.write_text(
                "INSERT INTO hmt_pg.metrics VALUES (1,'active','{}','2026-01-01T00:00:00Z')"
            )
            with pytest.raises(ValueError, match="MIGRATION_CHECKSUM_DRIFT"):
                apply_migrations(live.conn, root)
            assert fetch_metrics(live.conn, QueryWindow()) == []
            live.conn.execute("DELETE FROM hmt_pg.schema_migrations WHERE name=%s", (source.name,))
    return "changed_migration_could_not_introduce_an_effect"


def tailcat_binding(live):
    flow = prepare(live)
    role = flow.authority.identity().db_role
    binding = TailcatBinding(KEY, role)
    with patch.dict(os.environ, {"TAILCAT_PEER_KEY": "nodekey:" + "b" * 64}):
        with pytest.raises(PeerBindingError, match="TAILCAT_PEER_MISMATCH"):
            bind_tailcat_connection(live.conn, binding)
    assert counts(live.conn) == (0, 0, 0)
    with patch.dict(os.environ, {"TAILCAT_PEER_KEY": KEY}):
        assert bind_tailcat_connection(live.conn, binding).db_role == role
        snapshot = flow.write([PAYLOAD])
    return flow.complete(snapshot, PAYLOAD)


def bounded_rows(live):
    with pytest.raises(ValueError, match="BATCH_ROW_LIMIT"):
        pipeline_metrics(live.conn, repeat(sample()))
    assert fetch_metrics(live.conn, QueryWindow()) == []
    assert pipeline_metrics(live.conn, [sample(1), sample(2), sample(3)]) == 3
    with closing(metric_frames(live.conn, QueryWindow(limit=2), 1)) as frames:
        assert [frame["id"].to_list() for frame in frames] == [[1], [2]]
    assert live.conn.execute("SELECT count(*) FROM pg_cursors").fetchone()[0] == 0
    return "bounded_pipeline_to_polars_and_cursor_cleanup"
