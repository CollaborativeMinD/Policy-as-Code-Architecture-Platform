# 01 — Verified PostgreSQL configuration

**PG-PAT-001** · Contracts: `PG-CONFIG-001`

Admit one explicit PostgreSQL connection profile before opening a driver or ORM connection.

## Contract and PostgreSQL purpose

`DbConfig` is a strict, frozen Pydantic boundary with unknown fields forbidden. Production admits `verify-full`, an existing CA file, and a user name other than `postgres`. Psycopg receives explicit libpq parameters; asyncpg receives a validating `SSLContext`. The test profile is restricted to `127.0.0.1`, `::1`, or `localhost` and may explicitly disable TLS.

This name check is only an initial guard. A differently named role can still be privileged. The fixed worker separately checks its connected role's administrative flags, while deployment controls the grants and function owner.

## Reference use

Supply endpoints and credentials through the host's configuration boundary. This function performs no connection or logging:

```python
import os
from pathlib import Path
from pydantic import SecretStr
from hmt_pg_patterns.config import DbConfig

def production_config() -> DbConfig:
    password = os.environ.get("PGPASSWORD")
    return DbConfig(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=SecretStr(password) if password is not None else None,
        sslrootcert=Path(os.environ["PGSSLROOTCERT"]),
    )
```

`connect_kwargs()` and `asyncpg_kwargs()` revalidate the model at the driver seam, including copies constructed outside normal validation. Both carry a fixed application name, a restricted search path, and finite PostgreSQL session deadlines. A lock deadline must precede the statement deadline so contention fails before consuming the entire operation budget.

## Delivery, maintenance, and limits

Use the locked binary Psycopg variant selected by this branch. Its wheel includes client libraries; it does not produce a standalone executable. The plain Python variant needs a system `libpq`; the `c` variant needs a compiler and PostgreSQL development headers and links to system libraries. A packaging change therefore changes the delivery and patching contract and requires a fresh lock and verification run.

Keep connection dictionaries and credential-bearing URLs out of logs. `SecretStr` reduces accidental representation exposure, but calling `get_secret_value()` deliberately crosses that boundary. A production TLS handshake, certificate mismatch rejection, and actual LOGIN privileges remain native qualification obligations.

## Implementation and verification

Implementation: [config.py](../../src/hmt_pg_patterns/config.py), [__init__.py](../../src/hmt_pg_patterns/__init__.py).

Executable checks: [test_config.py](../../tests/test_config.py), [test_worker_contracts.py](../../tests/test_worker_contracts.py).

**Resource contract:** Connect 1–30 s; statement 100–60,000 ms; lock 1–10,000 ms and below statement timeout; idle transaction 100–120,000 ms.

Upstream or governing basis: [PostgreSQL TLS verification](https://www.postgresql.org/docs/current/libpq-ssl.html), [Psycopg installation variants](https://www.psycopg.org/psycopg3/docs/basic/install.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
