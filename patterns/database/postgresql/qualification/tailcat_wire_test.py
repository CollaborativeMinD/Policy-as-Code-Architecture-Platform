"""PG-PEER-001: actual Tailcat peer → fixed worker → PostgreSQL → Redis."""

import base64
import json
from uuid import uuid4

from authority_samples import grant_peer
from psycopg.conninfo import conninfo_to_dict
from tailcat_runtime import binary_path, client_key, exchange, server


def test_authenticated_tailcat_replay_and_revocation(pg_conn, pg_dsn, redis_client, tmp_path):
    binary = binary_path()
    key_path, peer = client_key(binary, tmp_path)
    role = grant_peer(pg_conn, "hmt_tailcat_peer")
    pg_conn.execute("TRUNCATE hmt_pg.peer_authority CASCADE")
    pg_conn.execute(
        "INSERT INTO hmt_pg.peer_authority VALUES(%s,%s,1,true,'infinity')", (role, peer)
    )
    database = conninfo_to_dict(pg_dsn)
    database.update(user=role, port=int(database["port"]), profile="test", sslmode="disable")
    database["connect_timeout"] = int(database.get("connect_timeout", 5))
    config = {
        "database": database,
        "peer_key": peer,
        "redis_url": "redis://127.0.0.1:"
        + str(redis_client.connection_pool.connection_kwargs["port"]),
        "deadline_seconds": 10.0,
    }
    path = tmp_path / "worker.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    payload = b"actual authenticated Tailcat composition" * 100
    request = (
        json.dumps(
            {"stream_id": str(uuid4()), "payload_b64": base64.b64encode(payload).decode()}
        ).encode()
        + b"\n"
    )
    with server(binary, tmp_path, peer, path) as address:
        first = exchange(binary, key_path, address, request)
        assert first.returncode == 0, first.stderr.decode()
        result = json.loads(first.stdout)
        assert result["status"] == "COMMITTED"
        assert result["projection"] == "ACKED"
        count = pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0]
        repeated = exchange(binary, key_path, address, request)
        assert json.loads(repeated.stdout)["checkpoint"] == result["checkpoint"]
        assert pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0] == count
        pg_conn.execute(
            "UPDATE hmt_pg.peer_authority SET epoch=2,active=false WHERE db_role=%s", (role,)
        )
        rejected = exchange(binary, key_path, address, request)
        assert not rejected.stdout
        assert pg_conn.execute("SELECT count(*) FROM hmt_pg.chunk_effect").fetchone()[0] == count
