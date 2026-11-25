"""Fixed-child composition; launcher environment is injected, wire transport is separate."""

import base64
import json
import os
import subprocess
import sys
from uuid import uuid4

from authority_samples import KEY, grant_peer
from psycopg.conninfo import conninfo_to_dict


def configured_worker(connection, dsn, redis_client, directory):
    role = grant_peer(connection, "hmt_fixed_worker")
    connection.execute("TRUNCATE hmt_pg.peer_authority CASCADE")
    connection.execute(
        "INSERT INTO hmt_pg.peer_authority VALUES(%s,%s,1,true,'infinity')", (role, KEY)
    )
    database = conninfo_to_dict(dsn)
    database.update(user=role, port=int(database["port"]), profile="test", sslmode="disable")
    database["connect_timeout"] = int(database.get("connect_timeout", 5))
    endpoint = "redis://127.0.0.1:" + str(redis_client.connection_pool.connection_kwargs["port"])
    config = {
        "database": database,
        "peer_key": KEY,
        "redis_url": endpoint,
        "deadline_seconds": 10.0,
    }
    path = directory / "worker.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return role, path


def invoke(path, request, peer=KEY):
    environment = dict(os.environ, TAILCAT_PEER_KEY=peer)
    return subprocess.run(
        [sys.executable, "-m", "hmt_pg_patterns.worker", "--config", str(path)],
        input=request,
        capture_output=True,
        timeout=15,
        env=environment,
    )


def test_fixed_worker_commits_replays_reconciles_and_obeys_revocation(
    pg_conn, pg_dsn, redis_client, tmp_path
):
    role, path = configured_worker(pg_conn, pg_dsn, redis_client, tmp_path)
    payload = b"bounded fixed-command PostgreSQL composition" * 100
    request = (
        json.dumps(
            {"stream_id": str(uuid4()), "payload_b64": base64.b64encode(payload).decode()}
        ).encode()
        + b"\n"
    )
    first = invoke(path, request)
    assert first.returncode == 0, first.stderr.decode()
    result = json.loads(first.stdout)
    assert result["status"] == "COMMITTED" and result["projection"] == "ACKED"
    assert result["durability"] == "TEST_ONLY_NOT_QUALIFIED"
    count = pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0]
    assert count > 1
    repeated = invoke(path, request)
    assert json.loads(repeated.stdout)["checkpoint"] == result["checkpoint"]
    assert pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0] == count
    assert not invoke(path, request, "nodekey:" + "b" * 64).stdout
    pg_conn.execute(
        "UPDATE hmt_pg.peer_authority SET epoch=2,active=false WHERE db_role=%s", (role,)
    )
    assert invoke(path, request).returncode == 1
    assert pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0] == count
