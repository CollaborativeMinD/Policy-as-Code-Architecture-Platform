# PostgreSQL reference branch runbook

## 1. Select the execution profile

This is a standalone Python reference branch. Install it beside the existing reusable design references at `database_design_patterns/postgresql`. Its catalog is independent of the inherited 15-pattern catalog.

| Profile | Executes | Does not establish |
|---|---|---|
| Software qualification | Python contracts, real PostgreSQL WASM SQL/protocol, live Redis, driver/ORM/CDC/authority composition, mutations, native admission tools | Native multi-backend contention, native LOGIN/SCRAM/TLS, encrypted Tailcat exchange, storage crash durability |
| Native database | The same tests against a disposable native PostgreSQL and Redis service; additional child-worker profile | A field mission's performance or failover acceptance |
| Native Tailcat wire | Actual pinned Tailcat local-DERP process, fixed worker, native LOGIN, PostgreSQL, and Redis | Public-network or field-link qualification |

The software worker composition supplies trusted launcher context and sets a test session identity explicitly. The actual native worker and Tailcat startup tests remain in `qualification/`; they are separately invoked, with their observed environment limitations retained in the release ledger. There are no hidden skips or xfails in the software campaign.

## 2. Reproduce the Python environment

From this branch directory, using the pinned uv toolchain recorded in the release inventory:

```bash
uv sync --frozen --python 3.13.17
```

The production package includes Psycopg3 binary and pool support, asyncpg, SQLAlchemy with asyncio support, SQLModel, Pydantic, Polars, Pyrsistent, and Redis. Development dependencies are separately pinned. The binary Psycopg distribution packages its client libraries; upgrades must be lockfile changes with renewed advisories and regression evidence.

## 3. Prepare disposable services

The suite creates and truncates its `hmt_pg` tables and creates test roles. Supply only a disposable database controlled for this run. Do not point `HMT_TEST_DSN` at an application or production database.

For the qualified Linux x64 software fixture, use Node 24.22.1:

```bash
npm ci --ignore-scripts --prefix fixtures/pglite
uv run python fixtures/pglite/apply_callback.py fixtures/pglite
export HMT_PGLITE_CLI="$(pwd)/fixtures/pglite/server.mjs"
export HMT_REDIS_SERVER=/absolute/path/to/redis-server
```

The package contains only the new repair kit, not inherited npm source or installed dependencies. The applicator checks exact package versions and the upstream/patched source hashes. COPY still runs inside PostgreSQL; the fixture reads the original frontend protocol bytes. Named prepared statements are scoped to the logical client. The remaining single-backend, shared-session, and cancellation limits are explicit in the kit README.

The recorded test substrate used Redis6.2.14. That version is evidence identity, not a production recommendation. The test fixture binds loopback, disables persistence, and applies finite connect/read timeouts. Production Redis requires TLS and ACL credentials in the private worker configuration.

Alternatively, set `HMT_TEST_DSN` and `HMT_TEST_REDIS_URL` to disposable native services. These variables take precedence over spawned fixture processes. The default driver tests exercise a loopback test profile; use the separate production configuration tests and native profile for TLS/LOGIN qualification.

## 4. Run fresh software admission

The output directory must be outside this branch and must not already exist:

```bash
uv run python tools/admit.py --output /absolute/evidence/pg-admission-run-001
uv run python -m tools.mutation_campaign --output /absolute/evidence/pg-mutations-run-001
```

Admission runs pytest itself and writes source-before/source-after inventories, the complete SQL candidate ledger, JUnit, exact test bindings, branch coverage, structural findings, and a summary. A nonzero exit is a failed run; the tool cannot turn an imported historical report into a current pass. Every selected candidate has separate unit, regex, integration, and E2E witnesses. The mutation campaign copies a frozen source snapshot into isolated directories, executes each changed witness, restores its exact bytes, and reruns the witness. Missing, timed-out, or unviable mutants do not count as caught.

The supplied independent 42-lane native tool bundle is an external, hash-bound prerequisite. Its source is excluded from this delta. The release records the original bundle, minimal loader/format repairs if used, prepared interpreter profiles, exact request, and every original native receipt. Follow the native-admission recipe in `admission/README.md` for a fresh campaign. The standalone branch runner complements those native tools; it does not replace them.

## 5. Apply schema and roles

Run `apply_migrations(connection, Path("sql"))` under a dedicated schema owner inside an explicit deployment session. It serializes migrations with a PostgreSQL advisory transaction lock, checks exact-byte SHA-256 replay, and executes each migration transactionally. Changing an already-recorded migration produces `MIGRATION_CHECKSUM_DRIFT`. Author a new numbered migration instead.

Provision the owner and worker roles using `deployment/01_roles.sql`, and execute `deployment/02_grants.sql` after migrations exist. Set credentials through the deployment secret mechanism. The worker has schema usage and explicitly named function execution; it has no direct authority, effect, head, or outbox table access. Keep the schema owner separate from the worker LOGIN. The reference server configuration and systemd unit make the selected WAL, timeout, and process containment controls concrete; adapt only through a recorded configuration change and rerun the relevant gates.

## 6. Run the fixed Tailcat worker

Create a mode0600 worker configuration owned by the service UID. It contains `database` settings accepted by `DbConfig`, `peer_key`, a secret `redis_url`, `max_payload_bytes`, and `deadline_seconds`. A production database requires `verify-full`, a real CA file, a non-administrative LOGIN, and an observed TLS connection. A production Redis URL requires `rediss`, an ACL username, and a password. Do not put credentials into a command line or commit them.

Use Tailcat0.7.0 pinned by the archive digest in the external dependency inventory. Generate persistent server/client keys according to its official CLI; keep the server address and preshared key private. Run one fixed key-to-role worker binding:

```bash
tailcat serve --key=/private/server.private.json --allow=nodekey:YOUR_VERIFIED_PUBLIC_KEY exec -- python -m hmt_pg_patterns.worker --config /private/worker.json
```

Replace the public-key placeholder with the exact registered key. The launcher provides `TAILCAT_PEER_KEY`. The worker compares it with both its fixed configuration and PostgreSQL's current authority row before accepting effects. Client JSON may contain only `stream_id` and canonical `payload_b64`. One newline frame is accepted per connection, with a maximum decoded payload of65536 bytes, a131072-byte frame bound, and a request-processing deadline of at most30 seconds. The timer starts after configuration and launcher-context checks.

The worker returns `COMMITTED` only after database transactions return successfully. `projection=UNKNOWN` retains PostgreSQL outbox work; it is not a failed database commit. Production WAL settings must be observed before a durability-dependent effect. CLI rejection exits1 without depending on diagnostic output; typed Python exceptions remain available to library callers. An expired hard deadline returns an unknown outcome and exit124; replay the exact source from origin and reconcile the deterministic request identities. Do not infer rollback from a lost response.

## 7. Recover and revoke

`relay_checkpoint` commits a durable claim before Redis I/O. Older intermediate checkpoints can remain `UNKNOWN` until the latest head is projected. Drain a finite work budget, then call `recover` and `reconcile` to compare current PostgreSQL custody with Redis readback. `rebuild_checkpoint` explicitly republishes a missing projection only after current authority and same-epoch admission. Redis loss never removes the PostgreSQL effect or authorizes another one.

Revoke through the privileged authority-control session: increase the epoch and set `active=false`. Epoch updates must increase. Normal worker requests cannot reinstate the grant. An old claim may record an already-observed external receipt after revocation, but cannot use that observation to regain operational authority. A new grant requires a new epoch and a deliberate owner action.

CDC writer instances are single-use. Restart with a new writer and replay the same source bytes from offset zero. The rolling window intentionally continues across chunk boundaries; resuming from a byte offset without the full scanner state is not an admitted operation. Changed payload or policy under a reused request identity fails closed.

## 8. Native qualification commands

After provisioning disposable native PostgreSQL/Redis with the required test privileges and installing the pinned Tailcat binary:

```bash
export HMT_TAILCAT_BIN=/absolute/path/to/tailcat
uv run pytest qualification/native_worker_test.py -q
uv run pytest qualification/tailcat_wire_test.py -q
```

The Tailcat profile starts a local DERP and disables public DERP discovery. The current managed environment denied Tailcat's netlink interface monitor before tunnel establishment. PGlite's startup username does not establish native `session_user`, so native child-worker LOGIN qualification is also separate. These are recorded service-profile boundaries, not suppressed software test failures.

## 9. Interpret the release

Read `VERIFICATION_REPORT.md`, the cumulative gate/RRCA exports, native receipts, and `machine_handoff.json`. Recompute the artifact manifest before reuse. Any implementation, SQL, policy, fixture, or dependency change requires fresh source-bound evidence. Performance suitability requires a mission workload and measured latency/throughput; this branch supplies bounded algorithms, plans, and batching primitives without asserting a universal fastest driver.
