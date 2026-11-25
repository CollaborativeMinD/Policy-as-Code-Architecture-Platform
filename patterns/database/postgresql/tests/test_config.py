"""PG-CONFIG-001: reject unsafe config before opening a socket."""

import ssl
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from hmt_pg_patterns.config import DbConfig


def config(**changes):
    return DbConfig(
        host="127.0.0.1", user="hmt_reader", profile="test", sslmode="disable", **changes
    )


def test_secret_safe_config_and_bounded_settings():
    value = config(password=SecretStr("test-only-value"))
    assert "test-only-value" not in repr(value)
    assert "test-only-value" not in value.model_dump_json()
    assert value.connect_kwargs()["password"] == "test-only-value"
    assert value.asyncpg_kwargs()["password"] == "test-only-value"
    assert value.asyncpg_kwargs()["ssl"] is False
    assert value.server_settings()["search_path"] == "pg_catalog,hmt_pg"


@pytest.mark.parametrize(
    "changes",
    [
        {"port": 0},
        {"connect_timeout": 0},
        {"lock_timeout_ms": 5000},
        {"dbname": "postgres;DROP SCHEMA public"},
        {"user": "x' OR 1=1"},
        {"connect_timeout": True},
        {"statement_timeout_ms": float("nan")},
    ],
)
def test_invalid_connection_config(changes):
    values = dict(host="127.0.0.1", user="hmt_reader", profile="test", sslmode="disable")
    values.update(changes)
    with pytest.raises(ValidationError):
        DbConfig(**values)


def test_production_security_gates(tmp_path):
    for user, mode in [("postgres", "verify-full"), ("app", "disable")]:
        with pytest.raises(ValidationError):
            DbConfig(host="db.example", user=user, sslmode=mode)
    with pytest.raises(ValidationError):
        DbConfig(host="db.example", user="app")
    with pytest.raises(ValidationError):
        DbConfig(host="db.example", user="app", sslrootcert=tmp_path / "missing")
    with pytest.raises(ValidationError):
        DbConfig(host="db.example", user="app", profile="test", sslmode="disable")


def test_tls_ca_uses_hostname_verified_context(tmp_path):
    ca = tmp_path / "ca.crt"
    ca.write_text("fixture path; TLS context factory is observed independently")
    settings = DbConfig(host="db.example", user="app", sslrootcert=ca)
    context = ssl.create_default_context()
    with patch(
        "hmt_pg_patterns.config.ssl.create_default_context", return_value=context
    ) as factory:
        result = settings.asyncpg_kwargs()
    factory.assert_called_once_with(cafile=str(ca))
    assert result["ssl"].check_hostname
    assert result["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert settings.connect_kwargs()["sslrootcert"] == str(ca)
    assert settings.connect_kwargs()["sslmode"] == "verify-full"


@pytest.mark.parametrize("method", ["connect_kwargs", "asyncpg_kwargs"])
def test_unvalidated_copy_cannot_bypass_connection_admission(method):
    unsafe = config().model_copy(update={"profile": "production", "sslmode": "disable"})
    with pytest.raises(ValidationError):
        getattr(unsafe, method)()
