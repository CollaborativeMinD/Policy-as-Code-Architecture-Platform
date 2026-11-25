"""Direct public witnesses isolate the semantic guard changed by each mutant."""

import psycopg
import pytest

from authority_samples import counts, register, request
from hmt_pg_patterns.pace import perform
from hmt_pg_patterns.pace_models import Mode, PaceState

pytestmark = pytest.mark.mutation


def test_epoch_guard_new_stream(pg_conn):
    authority = register(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    assert authority.admit(request(epoch=2)).epoch == 2
    before = counts(pg_conn)
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        authority.admit(request(epoch=1))
    assert counts(pg_conn) == before


def test_active_guard(pg_conn):
    authority = register(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2,active=false")
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        authority.admit(request(epoch=2))
    assert counts(pg_conn) == (0, 0, 0)


def test_pace_guard_precedes_callback():
    executed = []
    with pytest.raises(PermissionError, match="PACE_OPERATION_DENIED"):
        perform(PaceState(mode=Mode.TERMINAL), "write", lambda: executed.append(True))
    assert executed == []
