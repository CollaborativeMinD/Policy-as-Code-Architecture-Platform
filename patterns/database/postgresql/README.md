# PostgreSQL design patterns

This branch contains **17 reusable PostgreSQL pattern groups** with executable Python primitives, PostgreSQL migrations, adversarial tests, and separate software and native qualification evidence. It covers blocking and asyncio execution, raw SQL, SQLAlchemy, SQLModel, strict parsing contracts, bounded Polars extraction, transactional batches, peer/epoch authority, checkpoint recovery, and content-defined streaming.

The branch is a standalone Python package. PostgreSQL owns stored constraints, transaction outcomes, identity admission, and durable checkpoint custody. Redis supplies a disposable projection. Pyrsistent supplies immutable memory snapshots. Tailcat supplies a trusted transport context to a fixed worker when its launcher and native transport are qualified.

## Start here

| Need | Reference |
| --- | --- |
| Select a primitive or find its implementation | [Index.md](Index.md) and [catalog.json](catalog.json) |
| Understand the usage and composition map | [SKILLS.md](SKILLS.md) |
| Configure services, roles, and execution profiles | [Runbook.md](Runbook.md) |
| Preserve contributor and release rules | [Agents.md](Agents.md) |
| Assess the exact verified scope and limitations | [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md) |
| Machine-readable handoff and file lineage | [machine_handoff.json](machine_handoff.json), [artifact manifest](release/artifact_manifest.json), and [provenance](release/provenance.json) |
| Reproduce the governing admission | [admission/README.md](admission/README.md) |

The pattern catalog is an independent inventory of implemented capabilities. It is separate from the V&V candidate space in `contracts/`: a catalog entry is not itself a passing assertion or release decision.

## Choose the PostgreSQL interface

| Interface | Execution model | Appropriate use in this branch | Ownership decision |
| --- | --- | --- | --- |
| Psycopg 3 raw SQL | Blocking or asyncio | Explicit SQL, transactions, COPY, pipeline, server cursors, and PostgreSQL functions | Caller owns a connection and transaction, or a documented owning helper |
| asyncpg raw SQL | asyncio | Applications choosing asyncpg's PostgreSQL protocol API and `$n` bindings | Explicit connection/transaction scope and finite checkout/teardown |
| SQLAlchemy Core + Psycopg | Blocking or asyncio | Structured engine, pooling, and SQL-expression ownership | One SQLAlchemy pool; `engine.begin()` for owned writes |
| SQLModel + SQLAlchemy/Psycopg | Blocking reference | Mapped PostgreSQL rows with a separate strict input DTO | One session per unit of work; migrations remain authoritative |
| Polars + Psycopg server cursor | Blocking extraction | Stable-schema analytical batches | Generator owns the cursor and transaction until exhausted or closed |

Psycopg 3 is the primary adapter selected for this new branch. Psycopg 2 remains a migration/legacy consideration and is not added as a dependency. There is no universal fastest-driver claim: compare a real workload with the same transaction, validation, pool, and durability rules. The asyncpg choice is compatible with an explicit architecture; it does not require describing all ORM integrations as unsupported. See the [Psycopg documentation](https://www.psycopg.org/psycopg3/docs/) and [SQLAlchemy PostgreSQL dialect documentation](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html).

## Reproducible installation and first use

The exact dependency selections are in [pyproject.toml](pyproject.toml) and [uv.lock](uv.lock). The tested Python runtime is 3.13.17; the package declares Python 3.12–3.13 compatibility, which is broader than the recorded runtime execution evidence. Use the runbook's pinned tooling and frozen environment path:

```bash
uv sync --frozen --group dev --python 3.13.17
uv run --frozen python -m pytest -q tests/test_models.py tests/test_query_contracts.py
```

The chosen `psycopg[binary,pool]` distribution includes binary client components. It avoids local client development headers on supported wheel platforms; it does not build a self-contained application executable. Plain `psycopg` requires system `libpq`, and `psycopg[c]` builds against system client libraries. A packaging change therefore requires a new lock and verification record. The async SQLAlchemy path uses the locked `sqlalchemy[asyncio]` extra. [Upstream installation details](https://www.psycopg.org/psycopg3/docs/basic/install.html).

Create a production `DbConfig` through [pattern 01](patterns/01-secure-postgresql-configuration/README.md), supplying host-owned credentials, a certificate authority file, and the runtime LOGIN. Apply the reviewed SQL migrations as the migration owner before invoking application primitives. The tests use disposable state; production examples assume deployment has already established schema ownership and grants.

```python
import psycopg
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.sync_driver import fetch_metrics

def read_active(config: DbConfig):
    with psycopg.connect(**config.connect_kwargs(), autocommit=True) as conn:
        return fetch_metrics(conn, QueryWindow(status="active", limit=100))
```

Values remain parameters. Dynamic identifiers, where exposed, pass an allowlist and `Identifier` composition. Read results pass strict DTO validation. No example embeds a password or superuser connection string.

## Transaction and resource ownership

| Primitive | Ownership contract | Material boundary |
| --- | --- | --- |
| Raw `insert_metric` / `fetch_metrics` | Borrowed connection | Caller decides the larger transaction |
| `transaction_retry` | Idle autocommit connection; complete transaction per attempt | Only `40001` and `40P01`, at most five attempts; unknown commit outcomes propagate |
| `copy_metrics` / `pipeline_metrics` | Idle autocommit connection; one owned batch transaction | At most 10,000 validated rows; separate modes |
| `metric_frames` | Owned transaction and named server cursor | Finite rows and batch size; explicitly close on early exit |
| SQLAlchemy / SQLModel write helpers | Engine/session-level owned transaction | Separate helper calls are separate commits |
| `Authority.admit` / `AsyncAuthority.admit` | Transaction context on a fixed LOGIN connection | An existing outer transaction still owns final commit |
| Outbox claim/relay/reconcile | Idle autocommit connection | Claim commits before external Redis I/O |
| Stream writer | One writer lifecycle; one admitted chunk at a time | A committed prefix may survive a later failure; stable origin replay reconciles it |

An awaitable API does not make a single connection execute independent statements in parallel. A connection or mutable ORM session must have one transaction owner. Pool capacity and acquisition timeout are finite; application task admission must also be bounded. Do not layer a Psycopg pool beneath the SQLAlchemy engine's pool. [Psycopg concurrency](https://www.psycopg.org/psycopg3/docs/advanced/async.html), [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/21/core/connections.html).

## Data and parsing contract

`Metric` admits a positive bigint id, a closed status enum, at most 64 bounded telemetry keys, finite float values, and a timezone-aware timestamp. SQL uses explicit `bigint`, `jsonb`, and `timestamptz` semantics. The read window is an ordered keyset page of at most 10,000 rows.

A frozen Pydantic model does not recursively freeze a nested dictionary. `Metric.telemetry` remains mutable; the write seam revalidates and detaches it. Authority checkpoints use validated immutable scalar fields inside a Pyrsistent `PMap`. Pyrsistent's persistence means versioned immutable data structures in memory; PostgreSQL supplies durable custody. [Pydantic configuration](https://pydantic.dev/docs/validation/latest/api/pydantic/config/), [Pyrsistent](https://github.com/tobgu/pyrsistent).

Polars extraction uses an explicit PostgreSQL server cursor and stable output schema, including canonical JSON text and UTC timestamps. `iter_batches=True` alone would not prove bounded driver buffering. Retaining every returned DataFrame still retains the whole result. [Polars database batch behavior](https://docs.pola.rs/api/python/stable/reference/api/polars.read_database.html).

## Peer authority, checkpoint recovery, and streaming

The fixed worker binds a trusted Tailcat child peer key to host-owned configuration and a fixed PostgreSQL LOGIN. PostgreSQL derives identity from `session_user`, locks the current authority row, verifies epoch/expiry, and atomically records the effect, stream head, and outbox intent. Request data cannot select the peer, database endpoint, epoch, or chunk policy. The worker rejects an administratively privileged runtime role and checks local WAL prerequisites in the production profile.

Redis receives a bounded, canonical checkpoint projection. A cache value never authorizes a database effect. Publication outcomes are `ACKED` only after explicit readback; uncertain delivery remains durable outbox work. The returned worker projection is `ACKED` or `UNKNOWN`, independently of the recorded PostgreSQL commit outcome. An external cache update is not an atomic participant in the PostgreSQL transaction.

Content-defined streaming preserves bytes across different packetizations and applies the supplied rolling-window rule. It is a byte-chunking primitive; this branch does not implement PostgreSQL logical decoding or replication slots. Recovery uses a fresh writer and the same immutable source, stream UUID, epoch, and policy from byte zero. The checkpoint tip alone does not reconstruct the rolling window. Refer to patterns [13](patterns/13-peer-epoch-authority-and-tailcat-worker/README.md), [14](patterns/14-wal-checkpoints-outbox-and-redis-projection/README.md), and [15](patterns/15-content-defined-streaming/README.md).

## Verification and qualification boundaries

| Evidence surface | What it can establish | What it does not establish |
| --- | --- | --- |
| Pure contracts, independent streaming oracle, negative and causal tests | Input rejection, bounds, lifecycle transitions, recurrence parity, selected guard necessity | Native services or mission calibration |
| Repaired PGlite PostgreSQL WASM + native Redis software profile | Actual PostgreSQL SQL outcomes, driver bindings, COPY, rollback, named plans, authority functions, cache projection, and worker service composition | Independent backend sessions, native LOGIN/SCRAM/TLS, contention, wire cancellation, storage power loss, or native child startup authentication |
| `qualification/native_worker_test.py` | Fixed child against a separately supplied native PostgreSQL service | Tailcat encrypted transport unless the wire profile also executes |
| `qualification/tailcat_wire_test.py` | Actual pinned Tailcat transport and fixed worker when its host capabilities are available | General Internet reachability, production topology, or storage recovery by implication |

The local PGlite fixture has one PostgreSQL backend. Its reviewed compatibility repair supplies real socket bytes to synchronous COPY and namespaces named prepared statements per logical client. It does not manufacture successful COPY responses, replace COPY with INSERT, or disable production preparation. Shared roles/GUCs and other session state remain explicitly unqualified.

Default worker composition injects a trusted launcher context and uses explicit test `SET SESSION AUTHORIZATION` to exercise actual PostgreSQL privilege checks. It does not prove that a native startup username was authenticated. The managed environment's Tailcat process hit a Linux netlink `EPERM` restriction even with local DERP; no Tailcat wire PASS is claimed.

The release outcome is recorded in [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md), [software summary](evidence/software/summary.json), [native admission summary](evidence/native42/summary.json), [cumulative gates](release/cumulative_gates.json), and [RRCA record](release/rrca.json). Native admission tools and native PostgreSQL runtime qualification are different evidence dimensions. A passing static or software lane must not be relabeled as an unexecuted transport or durability qualification.

## Reuse and change control

Select a pattern by its PostgreSQL contract, copy its required source/SQL dependencies, preserve transaction and resource ownership, and run its listed tests plus applicable cross-join cases. Keep the frozen lock, release lineage, and governing admission attached to the derived package. Changes to authority, replay identity, limits, schema, dependencies, or fixture semantics require a fresh evidence epoch.

Tests and local examples contain deliberate negative inputs and disposable identities. They are verification fixtures, not deployment credentials. Production provisioning, grants, secret delivery, service readiness, native qualification, and release decisions are specified in the runbook and release records.
