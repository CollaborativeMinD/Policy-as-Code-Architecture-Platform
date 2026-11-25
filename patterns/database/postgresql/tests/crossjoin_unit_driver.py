"""Isolated public-boundary witnesses for driver and configuration candidates."""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
import psycopg
from psycopg.pq import TransactionStatus
from pydantic import ValidationError
import pytest

from driver_samples import sample
from hmt_pg_patterns.asyncpg_driver import close_connection
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.diagnostics import WalSettings
from hmt_pg_patterns.models import Metric, QueryWindow
from hmt_pg_patterns.queries import qualified_table, window_values
from hmt_pg_patterns.sync_driver import transaction_retry


def tls_profile():
    with pytest.raises(ValidationError) as denied:
        DbConfig(host="db.example", user="runtime", sslmode="disable")
    assert "PRODUCTION_REQUIRES_TLS_AND_NONADMIN_ROLE" in str(denied.value)
    return str(denied.value.errors()[0]["ctx"]["error"])


def bound_values():
    with pytest.raises(ValueError) as denied:
        qualified_table("metrics; DROP TABLE hmt_pg.metrics;--")
    with pytest.raises(ValidationError):
        window_values(QueryWindow.model_construct(status="active' OR TRUE--"))
    return str(denied.value)


def rollback():
    invoked = []
    with pytest.raises(ValueError) as denied:
        transaction_retry(SimpleNamespace(autocommit=False), lambda conn: invoked.append(conn))
    assert not invoked
    return str(denied.value)


class IsolatedTransaction:
    autocommit = True
    info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)

    @contextmanager
    def transaction(self):
        yield self


def retry_budget():
    calls = []

    def rejected(conn):
        calls.append(conn)
        raise psycopg.errors.SerializationFailure("controlled unit witness")

    with pytest.raises(psycopg.errors.SerializationFailure) as denied:
        transaction_retry(IsolatedTransaction(), rejected, attempts=3)
    assert len(calls) == 3
    return denied.value.sqlstate


class StalledClose:
    def __init__(self):
        self.terminated = False

    async def close(self, **kwargs):
        await asyncio.Event().wait()

    def terminate(self):
        self.terminated = True


def bounded_close():
    probe = StalledClose()
    with pytest.warns(RuntimeWarning, match="FORCED_TERMINATION"):
        outcome = asyncio.run(close_connection(probe, timeout=0.01))
    assert outcome == "forced" and probe.terminated
    return outcome


def contract_rejection():
    values = sample().model_dump()
    values["telemetry"] = {"temperature; DROP TABLE metrics": 1.0}
    with pytest.raises(ValidationError) as denied:
        Metric.model_validate(values)
    assert "TELEMETRY_KEY_INVALID" in str(denied.value)
    return str(denied.value.errors()[0]["ctx"]["error"])


def wal_prerequisites():
    observed = WalSettings(
        fsync="off", full_page_writes="on", synchronous_commit="on", wal_level="replica"
    )
    with pytest.raises(ValueError) as denied:
        observed.require_local_durable_commit()
    return str(denied.value)
