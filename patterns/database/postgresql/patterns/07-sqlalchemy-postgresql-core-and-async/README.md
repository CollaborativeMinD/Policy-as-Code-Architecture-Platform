# 07 — SQLAlchemy PostgreSQL Core and asyncio

**PG-PAT-007** · Contracts: `PG-QUERY-001`, `PG-TX-001`, `PG-POOL-001`, `PG-CONTRACT-001`

Offer SQLAlchemy transaction and pooling ownership over the explicit Psycopg PostgreSQL dialect.

## Contract and PostgreSQL purpose

`create_pg_engine()` constructs a `postgresql+psycopg` URL with `URL.create`, passes TLS/session policy through `connect_args`, and configures one finite SQLAlchemy pool. The engine uses zero overflow, pre-ping, a finite checkout timeout, and hidden SQL parameter logging. Credential values are never concatenated into a URL string.

The insert uses `engine.begin()`, strict detached input, and an explicitly typed PostgreSQL `JSONB` bind. Reads use named binds and validate the projected result. `engine.connect()` alone is a connection scope and is not the write-commit contract.

## Reference use

```python
from hmt_pg_patterns import orm
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import Metric, QueryWindow

def store_and_read(config: DbConfig, metric: Metric):
    engine = orm.create_pg_engine(config, size=4)
    try:
        orm.insert_metric(engine, metric)
        return orm.fetch_metrics(engine, QueryWindow(limit=100))
    finally:
        engine.dispose()
```

These two helper calls are separate transactions. If a caller requires one atomic workflow, it must own a connection/transaction and compose SQL explicitly instead of treating two engine-level helpers as one commit.

```python
from hmt_pg_patterns import orm_async
from hmt_pg_patterns.models import QueryWindow

async def read_async(config):
    engine = orm_async.create_pg_engine(config, size=4)
    try:
        return await orm_async.fetch_metrics(engine, QueryWindow(limit=100))
    finally:
        await engine.dispose()
```

## Delivery and optimization

The locked `sqlalchemy[asyncio]` dependency includes the async runtime requirement. Keep engines at application lifespan and dispose them at shutdown. Use one connection or session per independent task; an async session contains mutable transaction state.

The choice of Core, ORM, or raw SQL is an interface decision. It supplies no inherent throughput guarantee. These helpers materialize a bounded page; large analytical extraction uses the server-cursor pattern. TLS handshake, real production grants, and native backend contention require additional qualification.

## Implementation and verification

Implementation: [orm.py](../../src/hmt_pg_patterns/orm.py), [orm_async.py](../../src/hmt_pg_patterns/orm_async.py).

Executable checks: [test_orm_drivers.py](../../tests/test_orm_drivers.py).

**Resource contract:** Pool size 1–32, max_overflow=0, finite checkout wait, bounded QueryWindow.

Upstream or governing basis: [SQLAlchemy PostgreSQL dialects](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html), [SQLAlchemy transaction ownership](https://docs.sqlalchemy.org/en/21/core/connections.html), [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
