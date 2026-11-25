"""PG-PACE-001: recovery gating, actual callback execution, and an independent fence."""

import psycopg
import pytest

from authority_samples import counts, register, request
from hmt_pg_patterns import pace
from hmt_pg_patterns.pace_models import Mode, PaceState
from test_pace import observation

pytestmark = pytest.mark.causal


def bypass_recovery(old, obs, policy, _pressure):
    """Delete the recovery gate while leaving capability selection in place."""
    return policy.recovery_samples, old.healthy_since or obs.now, True


def test_deletion(monkeypatch):
    monkeypatch.setattr(pace, "recovery_state", bypass_recovery)
    state = pace.step(
        PaceState(mode=Mode.EMERGENCY), observation(reconciled=False, uncertain_ack=True)
    )
    executed = []
    pace.perform(state, "write", lambda: executed.append("effect invoked"))
    assert state.mode == Mode.PRIMARY and executed == ["effect invoked"]


def test_restoration(monkeypatch):
    initial = PaceState(mode=Mode.EMERGENCY)
    with monkeypatch.context() as removed:
        removed.setattr(pace, "recovery_state", bypass_recovery)
        assert pace.step(initial, observation(reconciled=False)).mode == Mode.PRIMARY
    state = pace.step(initial, observation(reconciled=False))
    executed = []
    with pytest.raises(PermissionError, match="PACE_OPERATION_DENIED"):
        pace.perform(state, "write", lambda: executed.append("premature"))
    for tick in range(2, 6):
        state = pace.step(state, observation(now=float(tick)))
    pace.perform(state, "write", lambda: executed.append("reconciled"))
    assert state.mode == Mode.PRIMARY and executed == ["reconciled"]


def test_matched_control():
    initial = PaceState(mode=Mode.EMERGENCY, reason="unrelated diagnostic text")
    state = initial
    for tick in range(1, 6):
        state = pace.step(state, observation(now=float(tick), reconciled=False))
    executed = []
    with pytest.raises(PermissionError, match="PACE_OPERATION_DENIED"):
        pace.perform(state, "write", lambda: executed.append("forbidden"))
    assert state.mode == Mode.EMERGENCY and executed == []


def test_alternate_path(pg_conn, monkeypatch):
    """A forged local recovery decision cannot override the database epoch fence."""
    authority = register(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    monkeypatch.setattr(pace, "recovery_state", bypass_recovery)
    state = pace.step(
        PaceState(mode=Mode.EMERGENCY), observation(reconciled=False, uncertain_ack=True)
    )
    assert state.mode == Mode.PRIMARY
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        pace.perform(state, "write", lambda: authority.admit(request(epoch=1)))
    assert counts(pg_conn) == (0, 0, 0)
