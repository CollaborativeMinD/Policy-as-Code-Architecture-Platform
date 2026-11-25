# PostgreSQL pattern index

The branch has 17 pattern groups and 39 mapped Python source modules. [catalog.json](catalog.json) is the independent machine-readable inventory. Each pattern page describes its PostgreSQL contract, public API, limits, code, and executable checks.

| Pattern | PostgreSQL responsibility | Execution | Main interface |
| --- | --- | --- | --- |
| [01 — Verified PostgreSQL configuration](patterns/01-secure-postgresql-configuration/README.md) | Admit one explicit PostgreSQL connection profile before opening a driver or ORM connection. | sync, asyncio | libpq, asyncpg TLS |
| [02 — Psycopg synchronous bound SQL](patterns/02-psycopg-sync-bound-sql/README.md) | Perform bounded PostgreSQL reads and validated writes with explicit connection and transaction ownership. | sync | raw PostgreSQL SQL |
| [03 — Psycopg native asyncio SQL](patterns/03-psycopg-async-bound-sql/README.md) | Expose the same PostgreSQL value and transaction contract through awaited driver operations. | asyncio | raw PostgreSQL SQL |
| [04 — asyncpg with bounded teardown](patterns/04-asyncpg-bounded-lifecycle/README.md) | Use raw asyncio PostgreSQL access while making connection closure, failures, and forced termination observable. | asyncio | asyncpg PostgreSQL protocol |
| [05 — Owned transactions and bounded retry](patterns/05-owned-transactions-and-bounded-retry/README.md) | Retry a complete aborted PostgreSQL transaction under an explicit attempt budget and ownership contract. | sync, asyncio | PostgreSQL transactions |
| [06 — Finite connection pools](patterns/06-finite-connection-pools/README.md) | Make PostgreSQL connection capacity, checkout wait, readiness, and shutdown explicit at one ownership layer. | sync, asyncio | psycopg_pool, asyncpg pool |
| [07 — SQLAlchemy PostgreSQL Core and asyncio](patterns/07-sqlalchemy-postgresql-core-and-async/README.md) | Offer SQLAlchemy transaction and pooling ownership over the explicit Psycopg PostgreSQL dialect. | sync, asyncio | SQLAlchemy Core |
| [08 — SQLModel PostgreSQL mapping](patterns/08-sqlmodel-postgresql-mapping/README.md) | Map a PostgreSQL table without treating an ORM constructor as strict input admission. | sync | SQLModel over SQLAlchemy/Psycopg |
| [09 — Strict PostgreSQL data contracts](patterns/09-strict-pydantic-data-contracts/README.md) | Validate telemetry, query windows, and authority receipts at every persistence or parsing boundary. | sync, asyncio | Pydantic DTOs, PostgreSQL JSONB and bigint |
| [10 — Polars through a PostgreSQL server cursor](patterns/10-polars-server-cursor-batches/README.md) | Convert bounded server-fetched rows into stable-schema Polars batches without implicit full-result buffering. | sync | PostgreSQL named cursor, Polars DataFrame |
| [11 — Atomic COPY and pipeline batches](patterns/11-atomic-copy-and-pipeline-batches/README.md) | Select a PostgreSQL batch mechanism while preserving full-batch validation and transaction rollback. | sync | PostgreSQL COPY FROM STDIN, Psycopg pipeline |
| [12 — Checksum-bound PostgreSQL migrations](patterns/12-checksum-bound-migrations/README.md) | Apply a finite, owner-authored migration inventory transactionally and reject changed bytes after application. | sync | PostgreSQL SQL migrations, transaction advisory lock |
| [13 — Peer and epoch authority with a fixed Tailcat worker](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) | Bind trusted transport identity to one fixed database LOGIN and recheck epoch authority in the transaction that changes PostgreSQL state. | sync, asyncio, fixed child process | PostgreSQL SECURITY DEFINER entry points, Tailcat CLI stdin/stdout |
| [14 — WAL, immutable checkpoints, outbox, and Redis projection](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md) | Keep authority and replay custody in PostgreSQL while treating Redis as a recoverable projection and Pyrsistent as immutable in-memory state. | sync | PostgreSQL WAL transactions, Redis Lua CAS, Pyrsistent PMap |
| [15 — Content-defined streaming into PostgreSQL](patterns/15-content-defined-streaming/README.md) | Preserve byte content and deterministic boundaries across packetizations, then persist ordered chunks through the same database authority contract. | sync, asyncio | content-defined byte chunks, PostgreSQL bytea effects |
| [16 — PACE capability and guarded recovery](patterns/16-pace-capability-and-recovery/README.md) | Select PostgreSQL service capabilities from trusted observations while keeping effect authority in the database. | sync control plane | PostgreSQL operation admission |
| [17 — PostgreSQL plans, indexes, and WAL observations](patterns/17-postgresql-plans-indexes-and-operations/README.md) | Inspect the actual PostgreSQL query plan and durability prerequisites without issuing mutating maintenance operations in the hot path. | sync | EXPLAIN FORMAT JSON, PostgreSQL settings and indexes |

## Complete source map

Each source module is mapped below. Shared modules can serve several patterns; the catalog lists every declared use. SQL ownership and grants are defined by the three reviewed migrations.

| Source | Pattern ownership |
| --- | --- |
| [__init__.py](src/hmt_pg_patterns/__init__.py) | [01](patterns/01-secure-postgresql-configuration/README.md) |
| [analytics.py](src/hmt_pg_patterns/analytics.py) | [10](patterns/10-polars-server-cursor-batches/README.md) |
| [async_driver.py](src/hmt_pg_patterns/async_driver.py) | [03](patterns/03-psycopg-async-bound-sql/README.md), [05](patterns/05-owned-transactions-and-bounded-retry/README.md) |
| [asyncpg_driver.py](src/hmt_pg_patterns/asyncpg_driver.py) | [04](patterns/04-asyncpg-bounded-lifecycle/README.md) |
| [asyncpg_pool.py](src/hmt_pg_patterns/asyncpg_pool.py) | [06](patterns/06-finite-connection-pools/README.md) |
| [authority.py](src/hmt_pg_patterns/authority.py) | [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |
| [authority_async.py](src/hmt_pg_patterns/authority_async.py) | [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |
| [authority_types.py](src/hmt_pg_patterns/authority_types.py) | [09](patterns/09-strict-pydantic-data-contracts/README.md), [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |
| [bulk.py](src/hmt_pg_patterns/bulk.py) | [11](patterns/11-atomic-copy-and-pipeline-batches/README.md) |
| [checkpoints.py](src/hmt_pg_patterns/checkpoints.py) | [14](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md) |
| [checkpoints_lua.py](src/hmt_pg_patterns/checkpoints_lua.py) | [14](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md) |
| [checkpoints_snapshot.py](src/hmt_pg_patterns/checkpoints_snapshot.py) | [14](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md) |
| [config.py](src/hmt_pg_patterns/config.py) | [01](patterns/01-secure-postgresql-configuration/README.md) |
| [diagnostics.py](src/hmt_pg_patterns/diagnostics.py) | [14](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md), [17](patterns/17-postgresql-plans-indexes-and-operations/README.md) |
| [driver_contracts.py](src/hmt_pg_patterns/driver_contracts.py) | [05](patterns/05-owned-transactions-and-bounded-retry/README.md), [06](patterns/06-finite-connection-pools/README.md), [11](patterns/11-atomic-copy-and-pipeline-batches/README.md) |
| [migrations.py](src/hmt_pg_patterns/migrations.py) | [12](patterns/12-checksum-bound-migrations/README.md) |
| [models.py](src/hmt_pg_patterns/models.py) | [08](patterns/08-sqlmodel-postgresql-mapping/README.md), [09](patterns/09-strict-pydantic-data-contracts/README.md), [10](patterns/10-polars-server-cursor-batches/README.md) |
| [orm.py](src/hmt_pg_patterns/orm.py) | [07](patterns/07-sqlalchemy-postgresql-core-and-async/README.md) |
| [orm_async.py](src/hmt_pg_patterns/orm_async.py) | [07](patterns/07-sqlalchemy-postgresql-core-and-async/README.md) |
| [orm_model.py](src/hmt_pg_patterns/orm_model.py) | [08](patterns/08-sqlmodel-postgresql-mapping/README.md) |
| [outbox.py](src/hmt_pg_patterns/outbox.py) | [14](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md) |
| [pace.py](src/hmt_pg_patterns/pace.py) | [16](patterns/16-pace-capability-and-recovery/README.md) |
| [pace_models.py](src/hmt_pg_patterns/pace_models.py) | [16](patterns/16-pace-capability-and-recovery/README.md) |
| [pools.py](src/hmt_pg_patterns/pools.py) | [06](patterns/06-finite-connection-pools/README.md) |
| [queries.py](src/hmt_pg_patterns/queries.py) | [02](patterns/02-psycopg-sync-bound-sql/README.md), [09](patterns/09-strict-pydantic-data-contracts/README.md), [11](patterns/11-atomic-copy-and-pipeline-batches/README.md) |
| [streaming.py](src/hmt_pg_patterns/streaming.py) | [15](patterns/15-content-defined-streaming/README.md) |
| [streaming_async_writer.py](src/hmt_pg_patterns/streaming_async_writer.py) | [15](patterns/15-content-defined-streaming/README.md) |
| [streaming_contracts.py](src/hmt_pg_patterns/streaming_contracts.py) | [15](patterns/15-content-defined-streaming/README.md) |
| [streaming_runtime.py](src/hmt_pg_patterns/streaming_runtime.py) | [15](patterns/15-content-defined-streaming/README.md) |
| [streaming_scan.py](src/hmt_pg_patterns/streaming_scan.py) | [15](patterns/15-content-defined-streaming/README.md) |
| [streaming_state.py](src/hmt_pg_patterns/streaming_state.py) | [15](patterns/15-content-defined-streaming/README.md) |
| [streaming_writer.py](src/hmt_pg_patterns/streaming_writer.py) | [15](patterns/15-content-defined-streaming/README.md) |
| [sync_driver.py](src/hmt_pg_patterns/sync_driver.py) | [02](patterns/02-psycopg-sync-bound-sql/README.md), [05](patterns/05-owned-transactions-and-bounded-retry/README.md) |
| [transport.py](src/hmt_pg_patterns/transport.py) | [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |
| [worker.py](src/hmt_pg_patterns/worker.py) | [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |
| [worker_config.py](src/hmt_pg_patterns/worker_config.py) | [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |
| [worker_io.py](src/hmt_pg_patterns/worker_io.py) | [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |
| [worker_projection.py](src/hmt_pg_patterns/worker_projection.py) | [14](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md) |
| [worker_service.py](src/hmt_pg_patterns/worker_service.py) | [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md) |

## PostgreSQL schema surfaces

| Migration | Responsibility |
| --- | --- |
| [01_metrics.sql](sql/01_metrics.sql) | Strict telemetry storage, primary key, status/id index, schema creation privilege boundary |
| [02_authority.sql](sql/02_authority.sql) | Session-derived authority, locked epoch checks, immutable chunk admission, stream head, outbox intent |
| [03_checkpoints.sql](sql/03_checkpoints.sql) | Claim/recovery/finish entry points, immutable effect trigger, monotonic epoch trigger, revoked public access |

## Evidence and release navigation

- [Verification report](VERIFICATION_REPORT.md), [software evidence](evidence/software/summary.json), and [native admission evidence](evidence/native42/summary.json).
- [Governing admission](admission/README.md), [candidate dimensions](contracts/candidate_dimensions.json), and [traceability](contracts/traceability.json).
- [Native fixed-worker qualification](qualification/native_worker_test.py) and [Tailcat wire qualification](qualification/tailcat_wire_test.py).
- [Runbook](Runbook.md), [contributor rules](Agents.md), [machine handoff](machine_handoff.json), [artifact manifest](release/artifact_manifest.json), and [provenance](release/provenance.json).

A catalog reference identifies implementation and verification obligations. Passing outcomes and exceptions come only from the corresponding immutable evidence epoch.
