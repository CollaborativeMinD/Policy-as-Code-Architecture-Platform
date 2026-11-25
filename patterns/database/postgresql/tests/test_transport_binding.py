"""Trusted launcher context must match both fixed configuration and DB session."""

import pytest

from authority_samples import KEY, register
from hmt_pg_patterns.transport import (
    TailcatBinding,
    PeerBindingError,
    bind_tailcat_connection,
    require_tailcat_peer,
)


@pytest.mark.parametrize(
    "key,role", [("bad", "peer"), (KEY, "postgres;drop"), (None, "peer"), (KEY, None)]
)
def test_binding_configuration_is_bounded(key, role):
    with pytest.raises(PeerBindingError):
        TailcatBinding(key, role)


@pytest.mark.parametrize("observed", [None, "", "nodekey:" + "b" * 64, "☃"])
def test_context_mismatch_denies_before_database(monkeypatch, observed):
    if observed is None:
        monkeypatch.delenv("TAILCAT_PEER_KEY", raising=False)
    else:
        monkeypatch.setenv("TAILCAT_PEER_KEY", observed)
    with pytest.raises(PeerBindingError, match="TAILCAT_PEER_MISMATCH"):
        require_tailcat_peer(TailcatBinding(KEY, "postgres"))
    with pytest.raises(PeerBindingError, match="INVALID_BINDING"):
        require_tailcat_peer({"peer_key": KEY, "db_role": "postgres"})


def test_fixed_login_and_stored_binding_required(pg_conn, monkeypatch):
    authority = register(pg_conn)
    role = authority.identity().db_role
    monkeypatch.setenv("TAILCAT_PEER_KEY", KEY)
    assert bind_tailcat_connection(pg_conn, TailcatBinding(KEY, role)).peer_key == KEY
    with pytest.raises(PeerBindingError, match="DATABASE_PEER_MISMATCH"):
        bind_tailcat_connection(pg_conn, TailcatBinding(KEY, "wrong_role"))
    pg_conn.execute(
        "UPDATE hmt_pg.peer_authority SET epoch=2,peer_key=%s", ("nodekey:" + "b" * 64,)
    )
    with pytest.raises(PeerBindingError, match="DATABASE_PEER_MISMATCH"):
        bind_tailcat_connection(pg_conn, TailcatBinding(KEY, role))
