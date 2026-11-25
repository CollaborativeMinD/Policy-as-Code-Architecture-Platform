"""PG-PEER-001: host-owned fixed worker configuration, separate from request data."""

import os
import stat
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from .config import DbConfig
from .transport import TailcatBinding


class WorkerConfig(BaseModel):
    """One authenticated Tailcat key maps to exactly one database LOGIN role."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)
    database: DbConfig
    peer_key: str = Field(pattern=r"^nodekey:[0-9a-f]{64}$")
    redis_url: SecretStr = Field(repr=False)
    max_payload_bytes: int = Field(default=65536, ge=1, le=65536)
    deadline_seconds: float = Field(default=15.0, ge=0.1, le=30)

    @model_validator(mode="after")
    def secure_projection(self):
        """Production Redis uses TLS plus an ACL identity; tests stay on loopback."""
        parsed = urlsplit(self.redis_url.get_secret_value())
        if parsed.query or parsed.fragment or parsed.path not in {"", "/0"}:
            raise ValueError("REDIS_ENDPOINT_NOT_FIXED")
        if self.database.profile == "production":
            if parsed.scheme != "rediss" or not parsed.username or not parsed.password:
                raise ValueError("REDIS_TLS_ACL_REQUIRED")
        elif parsed.scheme != "redis" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("TEST_REDIS_REQUIRES_LOOPBACK")
        if parsed.hostname is None or parsed.port == 0:
            raise ValueError("REDIS_ENDPOINT_INVALID")
        return self

    def binding(self) -> TailcatBinding:
        """Build the immutable transport-to-LOGIN binding from trusted configuration."""
        return TailcatBinding(self.peer_key, self.database.user)


def load_config(path: Path) -> WorkerConfig:
    """Open without following links; require a private regular file owned by this UID."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise PermissionError("WORKER_CONFIG_REQUIRES_PRIVATE_OWNED_FILE")
        raw = os.read(descriptor, 16385)
    finally:
        os.close(descriptor)
    if len(raw) > 16384:
        raise ValueError("WORKER_CONFIG_CAPACITY")
    return WorkerConfig.model_validate_json(raw)
