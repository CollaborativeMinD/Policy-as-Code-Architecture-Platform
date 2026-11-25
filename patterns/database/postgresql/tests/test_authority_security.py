"""PG-AUTH identity, temporal fencing, SQL defense, and privilege boundaries."""

from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest
from pydantic import ValidationError

from hmt_pg_patterns.authority import Authority
from authority_samples import KEY, counts, grant_peer, register, request


def test_role_is_server_identity_and_client_claim_forbidden(pg_conn):
    authority = register(pg_conn)
    role = grant_peer(pg_conn)
    pg_conn.execute(
        "INSERT INTO hmt_pg.peer_authority VALUES(%s,%s,1,true,'infinity')",
        (role, "nodekey:" + "b" * 64),
    )
    pg_conn.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role)))
    try:
        assert authority.identity().db_role == role
        result = authority.admit(request())
        assert authority.checkpoint(result.stream_id).db_role == role
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=epoch+1")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            pg_conn.execute("SELECT hmt_pg.authority_for(1)")
    finally:
        pg_conn.execute("SET SESSION AUTHORIZATION postgres")
    assert counts(pg_conn) == (1, 1, 1)
    with pytest.raises(ValidationError):
        authority.admit(dict(request().model_dump(), peer_key=KEY))


@pytest.mark.parametrize(
    "header_change,payload",
    [
        ({"peer_key": KEY}, b"x"),
        ({"epoch": True}, b"x"),
        ({"sequence": "0"}, b"x"),
        ({"start": -1}, b"x"),
        ({"previous_digest": "xz" * 32}, b"x"),
        ({"policy_digest": None}, b"x"),
        ({"stream_id": "'; DROP TABLE hmt_pg.chunk_effect;--"}, b"x"),
        ({}, b""),
        ({}, b"x" * 1048577),
    ],
)
def test_direct_sql_contract_cannot_bypass_python_validation(pg_conn, header_change, payload):
    register(pg_conn)
    header = request().header() | header_change
    with pytest.raises(psycopg.Error):
        pg_conn.execute("SELECT * FROM hmt_pg.admit_chunk(%s,%s)", (Jsonb(header), payload))
    assert counts(pg_conn) == (0, 0, 0)


def test_revocation_fences_new_effect_and_old_replay(pg_conn):
    authority = register(pg_conn)
    value = request()
    authority.admit(value)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2,active=false")
    for candidate in (value, request(epoch=2)):
        with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
            authority.admit(candidate)
    assert counts(pg_conn) == (1, 1, 1)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=3,active=true")
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        authority.admit(value)
    assert not authority.admit(request(epoch=3)).replayed
    with pytest.raises(psycopg.Error, match="EPOCH_MUST_ADVANCE"):
        pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")


def test_expiration_is_rechecked_after_authority_lock(pg_conn):
    authority = register(pg_conn)
    signature = "hmt_pg.chunk_digest(name,hmt_pg.chunk_input,bytea)"
    original = pg_conn.execute(
        "SELECT pg_get_functiondef(%s::regprocedure)", (signature,)
    ).fetchone()[0]
    delayed = """CREATE OR REPLACE FUNCTION hmt_pg.chunk_digest(a name,v hmt_pg.chunk_input,p bytea)
    RETURNS bytea LANGUAGE plpgsql VOLATILE SET search_path=pg_catalog,hmt_pg AS $$
    BEGIN PERFORM pg_sleep(0.2); RETURN decode(repeat('ab',32),'hex'); END $$"""
    pg_conn.execute(delayed)
    try:
        pg_conn.execute(
            "UPDATE hmt_pg.peer_authority SET epoch=2,expires_at=clock_timestamp()+interval '150 milliseconds'"
        )
        with pytest.raises(psycopg.Error, match="AUTHORITY_EXPIRED"):
            authority.admit(request(epoch=2))
        assert counts(pg_conn) == (0, 0, 0)
    finally:
        pg_conn.execute(original)


def test_unregistered_identity_and_expired_lease_are_denied(pg_conn):
    register(pg_conn)
    pg_conn.execute("TRUNCATE hmt_pg.peer_authority CASCADE")
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        Authority(pg_conn).identity()
    register(pg_conn)
    pg_conn.execute(
        "UPDATE hmt_pg.peer_authority SET epoch=2,expires_at=clock_timestamp()-interval '1 second'"
    )
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        Authority(pg_conn).checkpoint(uuid4())
