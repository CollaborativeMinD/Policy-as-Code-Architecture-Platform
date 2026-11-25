"""Worker fault boundaries classify retained effects and never infer cache authority."""

import json
from unittest.mock import Mock, patch

import pytest
from redis.exceptions import RedisError
from test_worker_e2e import invoke, worker_inputs

from hmt_pg_patterns.diagnostics import WalSettings
from hmt_pg_patterns.worker_config import WorkerConfig
from hmt_pg_patterns.worker_service import _durability, _role_contract, serve


def test_cache_failure_keeps_committed_effect_and_recoverable_work(pg_conn, redis_client):
    config, request = worker_inputs(pg_conn, redis_client)
    unavailable = Mock()
    unavailable.ping.side_effect = RedisError("connection unavailable")
    unavailable.eval.side_effect = RedisError("connection unavailable")
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("TAILCAT_PEER_KEY", config.peer_key)
        result = invoke(pg_conn, unavailable, config, request)
    assert result["status"] == "COMMITTED" and result["mode"] == "A"
    assert result["projection"] == "UNKNOWN"
    assert pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0] > 0
    assert (
        pg_conn.execute(
            "SELECT count(*) FROM hmt_pg.checkpoint_outbox WHERE state='UNKNOWN'"
        ).fetchone()[0]
        > 0
    )


@pytest.mark.parametrize("row", [None, (True, False, False, False, False)])
def test_privileged_or_unobserved_role_is_rejected(row):
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = row
    with pytest.raises(PermissionError):
        _role_contract(connection)


def production_config(tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("test placeholder; no live TLS claim")
    return WorkerConfig.model_validate_json(
        json.dumps(
            {
                "database": {"host": "pg.example", "user": "peer_a", "sslrootcert": str(ca)},
                "peer_key": "nodekey:" + "a" * 64,
                "redis_url": "rediss://peer:fixture@redis.example/0",
            }
        )
    )


def test_observed_tls_and_wal_prerequisites_are_both_required(tmp_path):
    config = production_config(tmp_path)
    connection = Mock()
    connection.pgconn.ssl_in_use = False
    with pytest.raises(PermissionError, match="TLS"):
        _durability(connection, config)
    connection.pgconn.ssl_in_use = True
    settings = WalSettings(
        fsync="on", full_page_writes="on", synchronous_commit="on", wal_level="replica"
    )
    with patch("hmt_pg_patterns.worker_service.wal_settings", return_value=settings):
        assert _durability(connection, config) == "WAL_PREREQUISITES_OBSERVED"
    with patch(
        "hmt_pg_patterns.worker_service.wal_settings",
        return_value=settings.model_copy(update={"fsync": "off"}),
    ):
        with pytest.raises(ValueError):
            _durability(connection, config)


def test_connection_owners_close_resources_after_primary_failure(tmp_path):
    config = production_config(tmp_path)
    with patch("hmt_pg_patterns.worker_service.psycopg.connect") as connect:
        with patch("hmt_pg_patterns.worker_service.Redis.from_url") as redis:
            with patch(
                "hmt_pg_patterns.worker_service.execute_stream", side_effect=RuntimeError("fault")
            ):
                with pytest.raises(RuntimeError, match="fault"):
                    serve(config, Mock())
            assert connect.return_value.__exit__.called
            assert redis.return_value.__exit__.called
