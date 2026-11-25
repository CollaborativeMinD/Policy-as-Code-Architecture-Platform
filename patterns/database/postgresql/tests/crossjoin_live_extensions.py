"""Live bounded leases, checksum drift, fixed peer identity, and bulk row budgets."""

from contextlib import closing
from itertools import repeat
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from psycopg_pool import PoolTimeout
import pytest

from authority_samples import KEY, counts, register
from driver_samples import sample
from hmt_pg_patterns.analytics import metric_frames
from hmt_pg_patterns.bulk import copy_metrics
from hmt_pg_patterns.migrations import apply_migrations
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.pools import sync_pool
from hmt_pg_patterns.sync_driver import fetch_metrics, insert_metric
from hmt_pg_patterns.transport import PeerBindingError, TailcatBinding, bind_tailcat_connection


def pool_capacity(live):
    with sync_pool(live.config, size=1, timeout=0.1) as pool:
        with pool.connection() as first:
            with pytest.raises(PoolTimeout):
                pool.getconn(timeout=0.02)
            insert_metric(first, sample())
        with pool.connection() as recovered:
            assert fetch_metrics(recovered, QueryWindow()) == [sample()]
        assert pool.max_size == 1
    assert pool.closed
    return "finite_lease_recovered_without_extra_connection"


def migration_drift(live):
    with TemporaryDirectory(prefix="pg-crossjoin-migration-") as directory:
        root = Path(directory)
        source = root / "95_crossjoin.sql"
        source.write_text("SELECT 1")
        with live.conn.transaction():
            live.conn.execute(
                "DELETE FROM hmt_pg.schema_migrations WHERE name=%s", (source.name,)
            ) if migration_table_exists(live.conn) else None
            assert apply_migrations(live.conn, root) == [source.name]
            source.write_text("SELECT 1/0")
            with pytest.raises(ValueError, match="MIGRATION_CHECKSUM_DRIFT"):
                apply_migrations(live.conn, root)
            live.conn.execute("DELETE FROM hmt_pg.schema_migrations WHERE name=%s", (source.name,))
    assert live.conn.execute("SELECT 1").fetchone() == (1,)
    return "changed_sql_was_never_executed"


def migration_table_exists(connection):
    return (
        connection.execute("SELECT to_regclass('hmt_pg.schema_migrations')").fetchone()[0]
        is not None
    )


def tailcat_binding(live):
    authority = register(live.conn)
    role = authority.identity().db_role
    binding = TailcatBinding(KEY, role)
    with patch.dict(os.environ, {"TAILCAT_PEER_KEY": "nodekey:" + "b" * 64}):
        with pytest.raises(PeerBindingError, match="TAILCAT_PEER_MISMATCH"):
            bind_tailcat_connection(live.conn, binding)
    assert counts(live.conn) == (0, 0, 0)
    with patch.dict(os.environ, {"TAILCAT_PEER_KEY": KEY}):
        assert bind_tailcat_connection(live.conn, binding).db_role == role
    return "peer_and_database_binding_observed"


def bounded_rows(live):
    with pytest.raises(ValueError, match="BATCH_ROW_LIMIT"):
        copy_metrics(live.conn, repeat(sample()))
    assert fetch_metrics(live.conn, QueryWindow()) == []
    assert copy_metrics(live.conn, [sample(1), sample(2)]) == 2
    with closing(metric_frames(live.conn, QueryWindow(limit=2), batch_size=1)) as frames:
        assert [frame.height for frame in frames] == [1, 1]
    return "bounded_copy_then_server_cursor"
