# 12 — Checksum-bound PostgreSQL migrations

**PG-PAT-012** · Contracts: `PG-MIGRATION-001`, `PG-TX-001`

Apply a finite, owner-authored migration inventory transactionally and reject changed bytes after application.

## Contract and PostgreSQL purpose

The migration runner reads `NN_lowercase_name.sql` files in sorted order, checks bounds and path form, and computes SHA-256 over each exact byte sequence. It takes a fixed transaction advisory lock before inspecting or updating `hmt_pg.schema_migrations`.

A new file executes and records its checksum within the same transaction. An unchanged applied file is a no-op. Any changed checksum raises `MIGRATION_CHECKSUM_DRIFT`; the altered SQL does not execute. A failure in a new migration rolls back its effects and history entry.

## Reference use

```python
from pathlib import Path
import psycopg
from hmt_pg_patterns.migrations import apply_migrations

def migrate(owner_config, directory: Path) -> list[str]:
    with psycopg.connect(**owner_config.connect_kwargs(), autocommit=True) as conn:
        return apply_migrations(conn, directory)
```

Use an explicitly authorized migration owner and a fresh or already ledger-managed schema. Application LOGIN roles receive only their runtime grants. Applying SQL manually first and then asking the runner to adopt it is outside this helper's contract; the migration inventory and ledger must describe the same deployment lineage.

## Delivery and maintenance

Treat applied migration files as immutable and express later changes in new files. The checksum binds contents to history; trust in the author and directory comes from the release package and host permissions. Requests must never select a migration path or provide migration SQL.

The advisory lock coordinates cooperating runners that use this lock contract. Its mutual exclusion under native independent backends remains a native qualification obligation. The local SQL fixture verifies transactional behavior and checksum rejection, not concurrent migration scheduling.

PostgreSQL operations such as `CREATE INDEX CONCURRENTLY` that cannot run inside the transaction need a separately designed deployment step. This reference deliberately does not grow into a general migration framework or hide nontransactional steps behind the same API.

## Implementation and verification

Implementation: [migrations.py](../../src/hmt_pg_patterns/migrations.py).

Executable checks: [test_migrations.py](../../tests/test_migrations.py).

**Resource contract:** 1–99 migration files; at most 262,144 bytes per file; constrained names; symlinks rejected.

Upstream or governing basis: [PostgreSQL explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
