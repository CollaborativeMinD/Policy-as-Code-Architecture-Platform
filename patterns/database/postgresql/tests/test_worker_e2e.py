"""Live SQL/Redis composition with explicit trusted launcher and test session identity."""

import base64
import json
from uuid import uuid4

import psycopg
import pytest
from authority_samples import KEY, grant_peer
from psycopg import sql

from hmt_pg_patterns.worker_config import WorkerConfig
from hmt_pg_patterns.worker_io import IngressRequest
from hmt_pg_patterns.worker_service import execute_stream


def worker_inputs(connection, redis_client):
    role = grant_peer(connection, "hmt_fixed_worker")
    connection.execute("TRUNCATE hmt_pg.peer_authority CASCADE")
    connection.execute(
        "INSERT INTO hmt_pg.peer_authority VALUES(%s,%s,1,true,'infinity')", (role, KEY)
    )
    endpoint = "redis://127.0.0.1:" + str(redis_client.connection_pool.connection_kwargs["port"])
    config = WorkerConfig.model_validate_json(
        json.dumps(
            {
                "database": {
                    "host": "127.0.0.1",
                    "user": role,
                    "profile": "test",
                    "sslmode": "disable",
                },
                "peer_key": KEY,
                "redis_url": endpoint,
            }
        )
    )
    request = IngressRequest(
        stream_id=uuid4(), payload_b64=base64.b64encode(b"fixed worker composition" * 100).decode()
    )
    return config, request


def invoke(connection, redis_client, config, request):
    connection.execute(
        sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(config.database.user))
    )
    try:
        return execute_stream(connection, redis_client, config, request)
    finally:
        connection.execute("SET SESSION AUTHORIZATION postgres")


def test_worker_commits_replays_reconciles_and_obeys_revocation(pg_conn, redis_client):
    config, request = worker_inputs(pg_conn, redis_client)
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("TAILCAT_PEER_KEY", KEY)
        result = invoke(pg_conn, redis_client, config, request)
        assert result["status"] == "COMMITTED" and result["projection"] == "ACKED"
        assert result["durability"] == "TEST_ONLY_NOT_QUALIFIED"
        count = pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0]
        assert count > 1
        assert invoke(pg_conn, redis_client, config, request)["checkpoint"] == result["checkpoint"]
        assert pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0] == count
        environment.setenv("TAILCAT_PEER_KEY", "nodekey:" + "b" * 64)
        with pytest.raises(RuntimeError, match="PEER_MISMATCH"):
            invoke(pg_conn, redis_client, config, request)
        environment.setenv("TAILCAT_PEER_KEY", KEY)
        pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2,active=false")
        with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
            invoke(pg_conn, redis_client, config, request)
        assert pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0] == count
