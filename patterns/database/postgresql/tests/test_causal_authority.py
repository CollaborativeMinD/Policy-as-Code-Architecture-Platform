"""PG-FENCE-001: distinct experiments on the database epoch admission edge."""

import psycopg
import pytest

from authority_samples import counts, register, request
from causal_samples import EPOCH_GUARD, replace_function

pytestmark = pytest.mark.causal
SIGNATURE = "hmt_pg.authority_for(bigint)"


def test_deletion(pg_conn):
    authority = register(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    with replace_function(pg_conn, SIGNATURE, EPOCH_GUARD, "false"):
        stale = authority.admit(request(epoch=1))
        assert stale.epoch == 1
        assert authority.identity().epoch == 2
        assert counts(pg_conn) == (1, 1, 1)


def test_restoration(pg_conn):
    authority = register(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    with replace_function(pg_conn, SIGNATURE, EPOCH_GUARD, "false"):
        assert authority.admit(request(epoch=1)).epoch == 1
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        authority.admit(request(epoch=1))
    assert counts(pg_conn) == (1, 1, 1)
    assert authority.admit(request(epoch=2)).epoch == 2


def test_matched_control(pg_conn):
    authority = register(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    with replace_function(pg_conn, SIGNATURE, "RETURN a;", "RETURN a; -- neutral edit"):
        with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
            authority.admit(request(epoch=1))
        assert authority.admit(request(epoch=2)).epoch == 2
    assert counts(pg_conn) == (1, 1, 1)


def test_alternate_path(pg_conn):
    """The stream-head epoch compensates only for an already established stream."""
    authority = register(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    first = request(epoch=2)
    receipt = authority.admit(first)
    stale = request(
        stream_id=first.stream_id,
        epoch=1,
        sequence=1,
        start=receipt.end,
        previous_digest=receipt.digest,
    )
    with replace_function(pg_conn, SIGNATURE, EPOCH_GUARD, "false"):
        with pytest.raises(psycopg.Error, match="CHECKPOINT_CONFLICT"):
            authority.admit(stale)
    assert counts(pg_conn) == (1, 1, 1)
