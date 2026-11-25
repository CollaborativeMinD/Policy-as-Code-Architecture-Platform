"""PG-MIGRATION-001: checksum-bound, transactional PostgreSQL migrations."""

import re
from hashlib import sha256
from pathlib import Path

import psycopg

MIGRATION_LOCK = 1380208720


def migration_inputs(directory: Path) -> list[tuple[str, str, str]]:
    """Read a finite, regular-file migration inventory and bind each exact byte."""
    files = sorted(directory.glob("[0-9][0-9]_*.sql"))
    if not files or len(files) > 99:
        raise ValueError("MIGRATION_COUNT_INVALID")
    result = []
    for file in files:
        if file.is_symlink() or not re.fullmatch(r"[0-9]{2}_[a-z_]+\.sql", file.name):
            raise ValueError("MIGRATION_PATH_INVALID")
        if file.stat().st_size > 262144:
            raise ValueError("MIGRATION_SIZE_LIMIT")
        raw = file.read_bytes()
        result.append((file.name, sha256(raw).hexdigest(), raw.decode("utf-8")))
    return result


def apply_migrations(conn: psycopg.Connection, directory: Path) -> list[str]:
    """Serialize checksum verification and execution in the owner transaction."""
    inputs = migration_inputs(directory)
    applied = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
        conn.execute("CREATE SCHEMA IF NOT EXISTS hmt_pg")
        conn.execute("""CREATE TABLE IF NOT EXISTS hmt_pg.schema_migrations
                     (name text PRIMARY KEY, sha256 text NOT NULL)""")
        for name, digest, sql in inputs:
            row = conn.execute(
                "SELECT sha256 FROM hmt_pg.schema_migrations WHERE name=%s", (name,)
            ).fetchone()
            if row is not None:
                if row[0] != digest:
                    raise ValueError("MIGRATION_CHECKSUM_DRIFT")
                continue
            # This is checksum-bound owner-authored migration code, never request data.
            conn.execute(sql.encode("utf-8"), prepare=False)
            conn.execute("INSERT INTO hmt_pg.schema_migrations VALUES (%s,%s)", (name, digest))
            applied.append(name)
    return applied
