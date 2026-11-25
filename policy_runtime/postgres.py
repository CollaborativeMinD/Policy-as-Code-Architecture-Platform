"""Bind PostgreSQL contracts to explicit settings and disposable software ports."""

import asyncio
from dataclasses import fields
from hashlib import sha256
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from psycopg import errors
from psycopg.pq import TransactionStatus

from hmt_pg_patterns import (
    analytics, async_driver, asyncpg_driver, asyncpg_pool, bulk, diagnostics, migrations,
    orm, orm_async, orm_model, outbox, pace, pools, streaming, sync_driver, transport,
)
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import Metric, QueryWindow
from hmt_pg_patterns.pace_models import Observation, PacePolicy, PaceState
from hmt_pg_patterns.streaming_contracts import Policy, StreamLimits

from policy_runtime.contracts import choice, integer, model, number, require, settings


ROOT = Path(__file__).resolve().parent.parent
WINDOW = ("status", "after_id", "limit")
METRIC = ("id", "status", "telemetry", "observed_at")
CONFIG = ("host", "port", "dbname", "user", "profile", "sslmode", "connect_timeout",
          "statement_timeout_ms", "lock_timeout_ms", "idle_transaction_timeout_ms")


def config(value):
    configs = model(DbConfig, value, *CONFIG)
    choice(configs.profile, "test")
    choice(configs.sslmode, "disable")
    return configs


def connection(*, asynchronous=False):
    conn = MagicMock()
    conn.autocommit = True
    conn.info.transaction_status = TransactionStatus.IDLE
    cursor = MagicMock()
    for method in ("execute", "fetchall"):
        if asynchronous:
            setattr(cursor, method, AsyncMock())
    if asynchronous:
        conn.cursor.return_value.__aenter__.return_value = cursor
    else:
        conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def configured(values):
    admitted = config(values)
    libpq, asyncpg = admitted.connect_kwargs(), admitted.asyncpg_kwargs()
    require(asyncpg["server_settings"] == admitted.server_settings()
            and f"-c lock_timeout={admitted.lock_timeout_ms}" in libpq["options"], "CONFIG_BINDING_DRIFT")
    return {"profile": admitted.profile, "server_settings": admitted.server_settings(),
            "connect_timeout": admitted.connect_timeout}


def keyset(values, *, asynchronous=False):
    window = model(QueryWindow, values, *WINDOW)
    conn, cursor = connection(asynchronous=asynchronous)
    cursor.fetchall.return_value = []
    if asynchronous:
        result = asyncio.run(async_driver.fetch_metrics(conn, window))
    else:
        result = sync_driver.fetch_metrics(conn, window)
    parameters = cursor.execute.call_args.args[1]
    require(not result and parameters == (window.status, window.after_id, window.limit), "KEYSET_BINDING_DRIFT")
    return {"parameters": parameters}


def close_asyncpg(values):
    settings(values, "timeout_ms")
    timeout = integer(values["timeout_ms"], 1, 30_000) / 1000
    conn = MagicMock()
    conn.close = AsyncMock()
    result = asyncio.run(asyncpg_driver.close_connection(conn, timeout))
    conn.close.assert_awaited_once_with(timeout=timeout)
    require(result == "graceful" and not conn.terminate.called, "CLOSE_BINDING_DRIFT")
    return {"status": result, "timeout_ms": values["timeout_ms"]}


def retry_transaction(values):
    settings(values, "attempts", "driver")
    attempts = integer(values["attempts"], 1, 5)
    driver = choice(values["driver"], "psycopg-sync", "psycopg-async")
    conn, _ = connection()
    calls = []

    def attempt(current):
        require(current is conn, "TRANSACTION_OWNERSHIP_DRIFT")
        calls.append(1)
        raise errors.SerializationFailure("fixture abort")

    async def attempt_async(current):
        return attempt(current)

    try:
        if driver == "psycopg-sync":
            sync_driver.transaction_retry(conn, attempt, attempts)
        else:
            asyncio.run(async_driver.transaction_retry(conn, attempt_async, attempts))
    except errors.SerializationFailure:
        require(len(calls) == attempts and conn.transaction.call_count == attempts, "TRANSACTION_CAP_DRIFT")
    else:
        raise ValueError("SERIALIZATION_EXHAUSTION_LOST")
    return {"attempts": len(calls), "driver": driver}


def finite_pool(values):
    settings(values, "database", "size", "timeout_ms", "driver")
    admitted = config(values["database"])
    size = integer(values["size"], 1, 32)
    timeout = integer(values["timeout_ms"], 1, 30_000) / 1000
    driver = choice(values["driver"], "psycopg-sync", "psycopg-async", "asyncpg")
    observed = {}
    fixture = MagicMock()

    def create(**kwargs):
        observed.update(kwargs)
        return fixture

    if driver == "psycopg-sync":
        with patch.object(pools, "ConnectionPool", create), pools.sync_pool(admitted, size, timeout):
            fixture.open.assert_called_once_with(wait=True, timeout=timeout)
        fixture.close.assert_called_once_with(timeout=timeout)
    else:
        asyncio.run(_async_pool(admitted, size, timeout, driver, create, fixture))
    require(observed["max_size"] == size and observed["min_size"] == 1, "POOL_BOUND_DRIFT")
    return {"size": size, "timeout_ms": values["timeout_ms"], "driver": driver}


async def _async_pool(config, size, timeout, driver, create, fixture):
    fixture.open, fixture.close = AsyncMock(), AsyncMock()
    if driver == "psycopg-async":
        with patch.object(pools, "AsyncConnectionPool", create):
            async with pools.async_pool(config, size, timeout):
                fixture.open.assert_awaited_once_with(wait=True, timeout=timeout)
        fixture.close.assert_awaited_once_with(timeout=timeout)
    else:
        with patch.object(asyncpg_pool.asyncpg, "create_pool", AsyncMock(side_effect=create)):
            async with asyncpg_pool.pool(config, size, timeout):
                pass
        fixture.close.assert_awaited_once()


def engine(values):
    settings(values, "database", "size", "driver")
    admitted = config(values["database"])
    size = integer(values["size"], 1, 32)
    driver = choice(values["driver"], "sqlalchemy-sync", "sqlalchemy-async")
    if driver == "sqlalchemy-sync":
        engine = orm.create_pg_engine(admitted, size)
        try:
            require(engine.pool.size() == size and engine.dialect.name == "postgresql", "ENGINE_BINDING_DRIFT")
        finally:
            engine.dispose()
    else:
        asyncio.run(_async_engine(admitted, size))
    return {"pool_size": size, "driver": driver}


async def _async_engine(config, size):
    engine = orm_async.create_pg_engine(config, size)
    try:
        require(engine.pool.size() == size and engine.dialect.name == "postgresql", "ENGINE_BINDING_DRIFT")
    finally:
        await engine.dispose()


def metric(values):
    return model(Metric, values, *METRIC)


def mapped_metric(values):
    row = metric(values)
    with patch.object(orm_model, "Session") as session:
        instance = session.return_value.__enter__.return_value
        orm_model.insert_metric(object(), row)
        stored = instance.add.call_args.args[0]
    require(orm_model.MetricRow.__table__.schema == "hmt_pg"
            and Metric.model_validate(stored.model_dump()) == row, "MAPPING_DRIFT")
    return {"metric": row.model_dump(mode="json"), "fixture_rows": 1}


def frames(values):
    settings(values, "window", "batch_size", "metrics")
    window = model(QueryWindow, values["window"], *WINDOW)
    batch = integer(values["batch_size"], 1, 4096)
    rows = metric_rows(values["metrics"], window.limit)
    require(all(row.status == window.status and row.id > window.after_id for row in rows), "FIXTURE_OUTSIDE_WINDOW")
    conn, cursor = connection()
    material = [row.model_dump() for row in rows]
    cursor.fetchmany.side_effect = [material[i:i + batch] for i in range(0, len(rows), batch)] + [[]]
    widths = [frame.height for frame in analytics.metric_frames(conn, window, batch)]
    require(sum(widths) == len(rows) and all(size <= batch for size in widths) and cursor.itersize == batch,
            "ANALYTICS_BATCH_DRIFT")
    return {"batches": widths, "batch_size": batch}


def metric_rows(values, limit):
    require(type(values) is list and 1 <= len(values) <= limit, "METRIC_BATCH_BOUND")
    return [metric(row) for row in values]


def bulk_write(values):
    settings(values, "mode", "max_rows", "metrics")
    mode = choice(values["mode"], "copy", "pipeline")
    rows = metric_rows(values["metrics"], integer(values["max_rows"], 1, 10_000))
    conn, cursor = connection()
    operation = bulk.copy_metrics if mode == "copy" else bulk.pipeline_metrics
    count = operation(conn, rows)
    if mode == "copy":
        writes = cursor.copy.return_value.__enter__.return_value.write_row.call_count
    else:
        writes = conn.execute.call_count
    require(count == writes == len(rows) and conn.transaction.call_count == 1, "BULK_TRANSACTION_DRIFT")
    return {"mode": mode, "fixture_rows": count}


def migration_inventory(values):
    settings(values, "filenames")
    expected = values["filenames"]
    require(type(expected) is list and all(type(name) is str for name in expected), "MIGRATION_NAMES_REQUIRED")
    inventory = migrations.migration_inputs(ROOT / "sql")
    require(expected == [name for name, _, _ in inventory], "MIGRATION_ORDER_OR_NAME_DRIFT")
    conn, _ = connection()
    conn.execute.return_value.fetchone.return_value = None
    ran = migrations.apply_migrations(conn, ROOT / "sql")
    require(ran == expected and conn.transaction.call_count == 1, "MIGRATION_BINDING_DRIFT")
    return {"fixture_applied": ran, "sha256": {name: stamp for name, stamp, _ in inventory}}


def peer(values):
    settings(values, "expected_db_role")
    key = "nodekey:" + "a" * 64  # Public fixture identity. A deployment obtains this from its launcher.
    mapping = transport.TailcatBinding(key, values["expected_db_role"])
    conn, _ = connection()
    conn.execute.return_value.fetchone.return_value = (mapping.db_role, key, 1)
    with patch.dict(os.environ, {"TAILCAT_PEER_KEY": ""}):
        try:
            transport.bind_tailcat_connection(conn, mapping)
        except transport.PeerBindingError:
            require(not conn.execute.called, "INVALID_PEER_REACHED_DATABASE")
        else:
            raise ValueError("PEER_GUARD_BYPASS")
    with patch.dict(os.environ, {"TAILCAT_PEER_KEY": key}):
        identity = transport.bind_tailcat_connection(conn, mapping)
    return {"matched_fixture_role": identity.db_role, "transport": "software-fixture"}


def recover(values):
    settings(values, "limit")
    limit = integer(values["limit"], 1, 100)
    conn, _ = connection()
    conn.execute.return_value.fetchall.return_value = []
    recovered = outbox.recover(conn, limit)
    require(not recovered and conn.execute.call_args.args[1] == (limit,), "RECOVERY_LIMIT_DRIFT")
    return {"limit": limit, "fixture_pending": len(recovered)}


async def _stream(values):
    settings(values, "policy", "limits", "packets")
    policy = streaming.Policy(**settings(values["policy"], *(item.name for item in fields(streaming.Policy))))
    limits = settings(values["limits"], "deadline_s", "cleanup_timeout_s")
    configured_limits = streaming.StreamLimits(number(limits["deadline_s"], .001, 300),
                                               number(limits["cleanup_timeout_s"], .001, 30))
    packets = values["packets"]
    require(type(packets) is list and 1 <= len(packets) <= 64 and all(type(s) is str for s in packets),
            "FIXTURE_PACKET_BOUND")
    encoded = tuple(packet.encode("utf-8") for packet in packets)
    output = []

    async def source():
        for packet in encoded:
            yield packet

    async def sink(chunk):
        output.append(chunk.data)

    result = await streaming.stream_chunks(source(), sink, policy=policy, limits=configured_limits)
    data = b"".join(output)
    require(data == b"".join(encoded) and result.terminal == "COMPLETED", "STREAM_EFFECT_DRIFT")
    return {"sha256": sha256(data).hexdigest(), "bytes": len(data), "chunks": len(output)}


def pace_step(values):
    settings(values, "policy", "observation", "state", "operation")
    policy = model(PacePolicy, values["policy"], *PacePolicy.model_fields)
    observed = model(Observation, values["observation"], *Observation.model_fields)
    initial = settings(values["state"], *PaceState.model_fields)
    since, last_at = initial["healthy_since"], initial["last_at"]
    if since == "not-started":
        since = None
    else:
        require(type(last_at) in (int, float), "INVALID_PACE_TIMESTAMP")
        since = number(since, 0, last_at)
    state = model(PaceState, initial | {"healthy_since": since}, *PaceState.model_fields)
    effect = choice(values["operation"], "read", "write", "relay", "read_checkpoint", "health")
    lifecycle = pace.step(state, observed, policy)
    admitted = pace.perform(lifecycle, effect, lambda: "fixture-admitted")
    return {"mode": lifecycle.mode, "operation": effect, "decision": admitted}


def diagnostic(values):
    settings(values, "window", "wal")
    window = model(QueryWindow, values["window"], *WINDOW)
    wal = model(diagnostics.WalSettings, values["wal"], *diagnostics.WalSettings.model_fields)
    conn, _ = connection()
    conn.execute.return_value.fetchone.side_effect = [tuple(wal.model_dump().values()), ([{"Plan": {}}],)]
    diagnostics.wal_settings(conn).require_local_durable_commit()
    diagnostics.explain_page(conn, window)
    statement, parameters = conn.execute.call_args.args
    require(statement.startswith("EXPLAIN (FORMAT JSON)") and "ANALYZE" not in statement, "EXPLAIN_EXECUTED_DATA")
    return {"window": parameters, "fixture_wal_prerequisites": "PASS"}


OPERATIONS = {
    "PG-PAT-001": configured, "PG-PAT-002": keyset,
    "PG-PAT-003": lambda values: keyset(values, asynchronous=True), "PG-PAT-004": close_asyncpg,
    "PG-PAT-005": retry_transaction, "PG-PAT-006": finite_pool, "PG-PAT-007": engine,
    "PG-PAT-008": mapped_metric, "PG-PAT-009": lambda values: metric(values).model_dump(mode="json"),
    "PG-PAT-010": frames, "PG-PAT-011": bulk_write, "PG-PAT-012": migration_inventory,
    "PG-PAT-013": peer, "PG-PAT-014": recover, "PG-PAT-015": lambda values: asyncio.run(_stream(values)),
    "PG-PAT-016": pace_step, "PG-PAT-017": diagnostic,
}
