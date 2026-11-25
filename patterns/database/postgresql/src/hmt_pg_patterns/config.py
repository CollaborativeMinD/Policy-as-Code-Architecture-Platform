"""PG-CONFIG-001: explicit TLS, bounded timeouts, and secret-safe settings."""

import ssl
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class DbConfig(BaseModel):
    """Production requires verified TLS; plaintext is loopback test-only."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.:-]+$")
    port: int = Field(default=5432, ge=1, le=65535)
    dbname: str = Field(default="postgres", pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    user: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    password: SecretStr | None = Field(default=None, repr=False)
    profile: Literal["production", "test"] = "production"
    sslmode: Literal["verify-full", "disable"] = "verify-full"
    sslrootcert: Path | None = None
    connect_timeout: int = Field(default=5, ge=1, le=30)
    statement_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    lock_timeout_ms: int = Field(default=1000, ge=1, le=10000)
    idle_transaction_timeout_ms: int = Field(default=10000, ge=100, le=120000)

    @model_validator(mode="after")
    def enforce_security(self):
        """Reject unbounded or insecure profiles before any driver receives them."""
        if self.lock_timeout_ms >= self.statement_timeout_ms:
            raise ValueError("LOCK_TIMEOUT_MUST_PRECEDE_STATEMENT_DEADLINE")
        if self.profile == "test":
            if self.host not in {"127.0.0.1", "::1", "localhost"}:
                raise ValueError("TEST_PROFILE_REQUIRES_LOOPBACK")
        elif self.sslmode != "verify-full" or self.user == "postgres":
            raise ValueError("PRODUCTION_REQUIRES_TLS_AND_NONADMIN_ROLE")
        if self.sslmode == "verify-full":
            if self.sslrootcert is None or not self.sslrootcert.is_file():
                raise ValueError("TLS_CA_FILE_REQUIRED")
        return self

    def server_settings(self) -> dict[str, str]:
        """Return fixed session policy, never caller-supplied SQL fragments."""
        return {
            "application_name": "hmt_pg_patterns",
            "statement_timeout": str(self.statement_timeout_ms),
            "lock_timeout": str(self.lock_timeout_ms),
            "idle_in_transaction_session_timeout": str(self.idle_transaction_timeout_ms),
            "search_path": "pg_catalog,hmt_pg",
        }

    def connect_kwargs(self) -> dict:
        """Revalidate copies and return libpq parameters at the connection boundary."""
        DbConfig.model_validate(self.model_dump())
        result = {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "sslmode": self.sslmode,
            "connect_timeout": self.connect_timeout,
            "options": " ".join(f"-c {k}={v}" for k, v in self.server_settings().items()),
        }
        if self.password is not None:
            result["password"] = self.password.get_secret_value()
        if self.sslrootcert is not None:
            result["sslrootcert"] = str(self.sslrootcert)
        return result

    def asyncpg_kwargs(self) -> dict:
        """Revalidate copies and build a hostname-verifying native TLS context."""
        DbConfig.model_validate(self.model_dump())
        tls: ssl.SSLContext | bool = False
        if self.sslmode == "verify-full":
            tls = ssl.create_default_context(cafile=str(self.sslrootcert))
        result = {
            "host": self.host,
            "port": self.port,
            "database": self.dbname,
            "user": self.user,
            "ssl": tls,
            "timeout": self.connect_timeout,
            "command_timeout": self.statement_timeout_ms / 1000,
            "server_settings": self.server_settings(),
        }
        if self.password is not None:
            result["password"] = self.password.get_secret_value()
        return result
