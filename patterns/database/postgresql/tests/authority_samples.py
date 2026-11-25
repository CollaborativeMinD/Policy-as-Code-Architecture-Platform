"""Independent database test inputs and bounded identity fixtures."""

import hashlib
from uuid import uuid4

from psycopg import sql

from hmt_pg_patterns.authority import Authority
from hmt_pg_patterns.authority_types import ChunkRequest

KEY = "nodekey:" + "a" * 64
POLICY = hashlib.sha256(b"fixture-policy-v1").digest()
ENTRY_POINTS = (
    "own_identity()",
    "admit_chunk(jsonb,bytea)",
    "read_checkpoint(uuid)",
    "claim_checkpoint()",
    "finish_checkpoint(uuid,uuid,text)",
    "recover_checkpoints(integer)",
    "checkpoint_for_claim(uuid,uuid)",
)


def register(connection):
    connection.execute("TRUNCATE hmt_pg.peer_authority CASCADE")
    connection.execute(
        "INSERT INTO hmt_pg.peer_authority VALUES(session_user,%s,1,true,'infinity')", (KEY,)
    )
    return Authority(connection)


def request(data=b"payload", **changes):
    values = dict(
        stream_id=uuid4(),
        request_id=uuid4(),
        epoch=1,
        sequence=0,
        start=0,
        previous_digest=bytes(32),
        policy_digest=POLICY,
        data=data,
    )
    values.update(changes)
    return ChunkRequest.model_validate(values)


def counts(connection):
    return tuple(
        connection.execute(
            sql.SQL("SELECT count(*) FROM hmt_pg.{}").format(sql.Identifier(name))
        ).fetchone()[0]
        for name in ("chunk_effect", "stream_head", "checkpoint_outbox")
    )


def grant_peer(connection, role="hmt_test_peer"):
    found = connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
    if not found:
        connection.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
    connection.execute(sql.SQL("GRANT USAGE ON SCHEMA hmt_pg TO {}").format(sql.Identifier(role)))
    for entry in ENTRY_POINTS:
        connection.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION hmt_pg.{} TO {}").format(
                sql.SQL(entry), sql.Identifier(role)
            )
        )
    return role
