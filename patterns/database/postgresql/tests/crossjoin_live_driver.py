"""Real PostgreSQL driver/configuration failures with observed database postconditions."""

import asyncio
import warnings
import asyncpg
import psycopg
from pydantic import ValidationError
import pytest

from driver_samples import sample
from hmt_pg_patterns.asyncpg_driver import close_connection
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.diagnostics import wal_settings
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.queries import qualified_table
from hmt_pg_patterns.sync_driver import fetch_metrics, insert_metric, transaction_retry


def tls_profile(live):
    with psycopg.connect(**live.config.connect_kwargs()) as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)
    changes = live.config.model_dump() | {"profile": "production", "user": "runtime"}
    with pytest.raises(ValidationError, match="PRODUCTION_REQUIRES_TLS"):
        DbConfig.model_validate(changes)
    assert fetch_metrics(live.conn, QueryWindow()) == []
    return "unsafe_profile_denied_before_effect"


def bound_values(live):
    attack = "active'; DROP TABLE hmt_pg.metrics; --"
    assert live.conn.execute("SELECT %s::text", (attack,)).fetchone()[0] == attack
    with pytest.raises(ValueError, match="TABLE_NOT_ADMITTED"):
        qualified_table(attack)
    transaction_retry(live.conn, lambda conn: insert_metric(conn, sample()))
    assert [row.id for row in fetch_metrics(live.conn, QueryWindow())] == [1]
    return "sql_text_remained_data"


def rollback(live):
    def operation(connection):
        insert_metric(connection, sample())
        raise RuntimeError("crossjoin_after_insert")

    with pytest.raises(RuntimeError, match="crossjoin_after_insert"):
        transaction_retry(live.conn, operation)
    assert fetch_metrics(live.conn, QueryWindow()) == []
    return "rolled_back"


def retry_budget(live):
    attempts = []

    def operation(connection):
        attempts.append(len(attempts) + 1)
        insert_metric(connection, sample())
        connection.execute("DO $$ BEGIN RAISE EXCEPTION USING ERRCODE='40001'; END $$")

    with pytest.raises(psycopg.errors.SerializationFailure):
        transaction_retry(live.conn, operation, attempts=3)
    assert attempts == [1, 2, 3]
    assert fetch_metrics(live.conn, QueryWindow()) == []
    return "budget_exhausted_without_effect"


async def observed_close(config):
    connection = await asyncpg.connect(**config.asyncpg_kwargs())
    try:
        assert await connection.fetchval("SELECT 1") == 1
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            outcome = await close_connection(connection, timeout=0.05)
        assert connection.is_closed()
        assert outcome in {"graceful", "forced"}
        if outcome == "forced":
            assert any("FORCED_TERMINATION" in str(item.message) for item in emitted)
        return outcome
    finally:
        if not connection.is_closed():
            connection.terminate()


def bounded_close(live):
    return asyncio.run(observed_close(live.config))


def contract_rejection(live):
    malformed = sample().model_copy(update={"telemetry": {"bad-key;": 1.0}})
    with pytest.raises(ValidationError, match="TELEMETRY_KEY_INVALID"):
        transaction_retry(live.conn, lambda conn: insert_metric(conn, malformed))
    assert fetch_metrics(live.conn, QueryWindow()) == []
    return "malformed_dto_denied"


def wal_prerequisites(live):
    observed = wal_settings(live.conn)
    weakened = observed.model_copy(update={"fsync": "off"})
    with pytest.raises(ValueError, match="WAL_PROTECTION_DISABLED"):
        weakened.require_local_durable_commit()
    assert fetch_metrics(live.conn, QueryWindow()) == []
    return "observed_settings_guarded_without_power_loss_claim"
