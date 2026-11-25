"""PG-OPS-001: plan visibility and configuration-based WAL rejection."""

from unittest.mock import Mock

import pytest

from hmt_pg_patterns.diagnostics import WalSettings, explain_page, wal_settings
from hmt_pg_patterns.models import QueryWindow


@pytest.mark.parametrize(
    "fsync,full_page,sync",
    [
        ("off", "on", "on"),
        ("on", "off", "on"),
        ("on", "on", "off"),
    ],
)
def test_wal_guard_rejects_weakened_settings(fsync, full_page, sync):
    settings = WalSettings(
        fsync=fsync, full_page_writes=full_page, synchronous_commit=sync, wal_level="replica"
    )
    with pytest.raises(ValueError):
        settings.require_local_durable_commit()


def test_wal_guard_accepts_local_commit_configuration():
    WalSettings(
        fsync="on", full_page_writes="on", synchronous_commit="local", wal_level="replica"
    ).require_local_durable_commit()


def test_missing_observations_fail_visibly():
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = None
    with pytest.raises(RuntimeError, match="WAL_SETTINGS"):
        wal_settings(conn)
    with pytest.raises(RuntimeError, match="PLAN"):
        explain_page(conn, QueryWindow())


def test_postgresql_plan_and_settings_are_observed(pg_conn):
    plan = explain_page(pg_conn, QueryWindow())
    assert "Plan" in plan
    assert isinstance(wal_settings(pg_conn), WalSettings)
    indexes = pg_conn.execute(
        "SELECT indexname FROM pg_indexes WHERE schemaname=%s AND tablename=%s",
        ("hmt_pg", "metrics"),
    ).fetchall()
    assert ("metrics_status_id_idx",) in indexes
