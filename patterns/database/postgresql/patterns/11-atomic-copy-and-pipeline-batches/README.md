# 11 — Atomic COPY and pipeline batches

**PG-PAT-011** · Contracts: `PG-CONTRACT-001`, `PG-TX-001`

Select a PostgreSQL batch mechanism while preserving full-batch validation and transaction rollback.

## Contract and PostgreSQL purpose

Both functions validate and detach the complete finite input before the first database effect. A malformed item or a batch exceeding 10,000 rows fails before insertion. An infinite iterable reaches the finite rejection boundary. The helper requires ownership of an outer PostgreSQL transaction.

`copy_metrics()` uses row-wise adaptation with `COPY ... FROM STDIN`, a safely composed table identifier, and `write_row()`. It does not mix row adaptation with CSV delimiter or NULL formatting options. `pipeline_metrics()` sends bound INSERTs within a separate pipeline context and explicitly synchronizes before the owning transaction completes.

## Reference use

```python
import psycopg
from hmt_pg_patterns.bulk import copy_metrics
from hmt_pg_patterns.models import Metric

def ingest_batch(config, rows: list[Metric]) -> int:
    with psycopg.connect(**config.connect_kwargs(), autocommit=True) as conn:
        return copy_metrics(conn, rows)
```

Select `pipeline_metrics` for the alternative mode with the same validated row contract. Do not call both on the same new rows merely to compare them: the primary key makes the second operation a duplicate write. Benchmark each mode on separate disposable datasets and preserve identical transaction and validation rules.

## Delivery, evidence, and limits

A constraint failure rolls back the whole batch, including rows that PostgreSQL processed before discovering the failure. An empty batch is valid and returns zero. Completion means the owned transaction exited successfully; a lost commit response still requires reconciliation rather than a guessed retry.

COPY reduces per-row SQL framing, while pipeline mode can reduce round-trip waits. Network latency, row width, constraints, storage, and driver adaptation determine the result. This branch supplies no comparative benchmark claim.

The local PGlite protocol fixture required an explicit bounded socket-read repair to execute real COPY input. Tests include duplicate rollback, multiple protocol data frames, producer CopyFail, and subsequent connection reuse. The repair records its upstream hash and does not replace COPY with INSERT. Native socket, authentication, and durability qualification remain separate.

## Implementation and verification

Implementation: [bulk.py](../../src/hmt_pg_patterns/bulk.py), [queries.py](../../src/hmt_pg_patterns/queries.py), [driver_contracts.py](../../src/hmt_pg_patterns/driver_contracts.py).

Executable checks: [test_bulk_analytics.py](../../tests/test_bulk_analytics.py), [test_fixture_protocol_regressions.py](../../tests/test_fixture_protocol_regressions.py).

**Resource contract:** At most 10,000 validated rows before database I/O; each mode requires an idle autocommit connection and owns one transaction.

Upstream or governing basis: [Psycopg row COPY](https://www.psycopg.org/psycopg3/docs/basic/copy.html), [Psycopg pipeline mode](https://www.psycopg.org/psycopg3/docs/advanced/pipeline.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
