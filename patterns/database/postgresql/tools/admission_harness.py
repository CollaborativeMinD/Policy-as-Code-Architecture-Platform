"""Bind external service programs without recording connection strings or credentials."""

import hashlib
import os
from pathlib import Path
import platform
import sys


def binary_identity(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def harness_identity():
    programs = {"python": binary_identity(sys.executable)}
    for name in ("HMT_PGLITE_CLI", "HMT_REDIS_SERVER", "HMT_TAILCAT_BIN"):
        if os.environ.get(name):
            programs[name] = binary_identity(os.environ[name])
    return {
        "programs": programs,
        "python_version": platform.python_version(),
        "external_postgresql_configured": bool(os.environ.get("HMT_TEST_DSN")),
        "external_redis_configured": bool(os.environ.get("HMT_TEST_REDIS_URL")),
        "qualification_scope": "Managed software services or explicitly configured external services; "
        "native qualification requires its separate execution receipt.",
    }
