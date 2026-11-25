"""Replay a single selected software binding with no production ports."""

from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import sys

from policy_runtime.contracts import read_policy, require, settings


ROOT = Path(__file__).resolve().parent.parent


def dependency_versions():
    names = ("pydantic", "networkx", "psycopg", "asyncpg", "sqlalchemy", "sqlmodel", "polars", "pyrsistent", "redis")
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    pinned = {name: next(line.split()[0].split("==")[1] for line in lock.splitlines() if line.startswith(f"{name}=="))
              for name in names}
    require(all(metadata.version(name) == version for name, version in pinned.items()), "DEPENDENCY_PIN_MISMATCH")
    return pinned


def operation(identity, values):
    if identity.startswith("PG-PAT-"):
        from policy_runtime.postgres import OPERATIONS
        return OPERATIONS[identity](values)
    from pattern_reference import contracts, reference
    from policy_runtime.rdp import OPERATIONS
    return OPERATIONS[identity](contracts, reference, values)


def qualify():
    identity = settings(json.loads((ROOT / "binding.json").read_bytes()), "pattern", "policy_sha256")
    raw, values = read_policy(ROOT / "configuration.toml", identity["pattern"])
    stamp = sha256(raw).hexdigest()
    require(stamp == identity["policy_sha256"], "BOUND_POLICY_DIGEST_MISMATCH")
    versions = dependency_versions()
    result = operation(identity["pattern"], values)
    try:
        operation(identity["pattern"], values | {"undeclared_override": True})
    except ValueError:
        pass
    else:
        raise RuntimeError("UNDECLARED_SETTING_ESCAPED_ADMISSION")
    return {"status": "PASS", "scope": "software", "pattern": identity["pattern"], "policy_sha256": stamp,
            "dependency_versions": versions, "python": sys.version.split()[0],
            "undeclared_setting": "DENY", "observed": result}


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, allow_nan=False))
