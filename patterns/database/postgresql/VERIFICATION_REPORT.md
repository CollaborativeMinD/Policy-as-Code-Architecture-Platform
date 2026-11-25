# PostgreSQL design patterns — verification and release report

Release: **1.0.0**, 4 November 2026. Scope: the new `database_design_patterns/postgresql` reference branch. The original reusable-design archive and its 15-pattern catalog remain unchanged.

## Release decision

**Software reference qualification: PASS.** The delivered runtime, SQL, tests, contracts, fixtures, deployment surfaces, and reference inputs are bound to source digest `6771f2465d4f6e644f13af47375e562ccaee1a5476d44e8846954b0095fa13b7`. Native standalone admission: **PASS — 24 applicable lanes passed; 18 explicit nonapplicability records; zero failures or holds**. Native PostgreSQL startup authentication/TLS, independent-backend contention, actual Tailcat transport, and storage power-loss recovery remain separate qualification profiles. Those profiles are not silently represented as passing software tests.

The package is suitable as a reusable software reference under these declared boundaries. This record does not authorize a field deployment or assert that configuration observations prove storage durability. Its machine handoff uses the supplied governing schema without adding undocumented fields.

## Delivered inventory

The branch implements **17 PostgreSQL pattern groups**, mapped to **39 production Python modules** and **three ordered PostgreSQL migrations**. Each pattern page contains its contract, APIs, resource limits, source files, and executable checks. `catalog.json` and `Index.md` provide the complete map.

| Pattern groups | Delivered behavior |
| --- | --- |
| Configuration; Psycopg sync/async; asyncpg | Parameter binding, strict connection profiles, finite timeouts, resource ownership, and observable forced teardown |
| Transactions; pools | Complete-transaction retries limited to PostgreSQL abort SQLSTATEs, finite pool capacity, checkout, readiness, and shutdown |
| SQLAlchemy Core/async; SQLModel | Explicit PostgreSQL dialect, transaction/session ownership, one pool layer, and strict DTO admission outside ORM constructors |
| Pydantic; Polars | Revalidation at persistence seams, detached mutable payloads, bounded named-cursor batches, stable analytical schema |
| COPY/pipeline; migrations | Atomic validated batches, exact migration checksums, and PostgreSQL transaction advisory locks |
| Peer authority; WAL/checkpoints/outbox | Database-derived identity, epoch and expiry fencing, atomic effects/head/outbox, immutable memory snapshots, and recoverable Redis projection |
| Content-defined streaming; PACE; operations | Continuous rolling-window chunking, origin replay, bounded async delivery, capability/recovery guards, and PostgreSQL plan/WAL observations |

The deployment surface consists of least-privilege role and grant SQL, PostgreSQL settings, and a fixed Tailcat worker systemd unit. This standalone branch does not build a container image or introduce a Kubernetes deployment. Unrelated language, image, and cluster admission lanes require explicit nonapplicability records rather than empty substitute manifests.

## Measured verification

| Gate | Actual observation | Evidence |
| --- | --- | --- |
| Standalone software admission | **446 passed; 0 failed, 0 errors, 0 skipped** | `evidence/software/junit.xml`, `summary.json`, `pytest-process.json` |
| Branch coverage | **265/278 = 95.323741%**; threshold ≥90% | `evidence/software/branch-coverage.json` |
| Line coverage | **1,285/1,301 = 98.770177%**; independently checked ≥90% | Same receipt and raw `coverage.json` |
| Full candidate space | **16 invariants × 14 failure modes × 4 gates = 896 rows** | SQLite and DuckDB candidate ledgers |
| Applicable candidates | **19 selected; 877 explicit nonapplicability predicates** | `candidate-space.json` and retained ledger |
| Required witnesses | **76 distinct unit/regex/integration/E2E witnesses** | `crossjoin-manifest.json`, execution bindings, raw JUnit |
| Causal verification | **5 edges × 4 experiments = 20** | `causal-binding.json` and ledger experiments |
| Native V&V | **PASS**, 15 test families, 16 claims, 35 reviewed loop sites | `evidence/native_vv/native-vv-result.json` |
| Mutation campaign | **12/12 detected; 0 missed, 0 timed out, 0 unviable; all restorations pass** | `evidence/mutations/mutation-report.json` and per-mutant receipts |
| Structure | **143 Python modules checked**; largest 131 physical lines, largest function 49 lines, ≤5 arguments and depth ≤5 | `evidence/software/structure.json` |
| Production-only structure | **39 modules**; largest 123 physical lines, largest function 39 lines, ≤5 arguments and depth ≤4 | Same structural inventory |
| Source stability | Identical source-before/source-after digest; isolated mutation copies restored | Software and mutation source inventories |
| Native admission | **PASS — 24 applicable lanes passed; 18 explicit nonapplicability records; zero failures or holds** | `evidence/native42/summary.json` |

The SQL cross join is retained before filtering. Nonapplicable rows have explicit predicates. A pattern catalog entry is not counted as test execution. Current JUnit identities and source hashes bind each reported witness; earlier reports cannot be imported as a fresh pass.

Coverage is measured over every delivered `src/hmt_pg_patterns/*.py` recursively. The separate 143-module structural population includes source, tests, and tooling. The 13 uncovered branches and 16 uncovered statements remain visible in raw coverage; no 100% or exhaustive-correctness claim is made. Mutation detection establishes sensitivity to the selected 12 faults, not all possible faults.

## Hardening decisions and corrections

**PostgreSQL authority is the decision point.** A fixed worker compares trusted Tailcat launcher identity with host-owned configuration and its fixed database LOGIN. Security-definer functions pin their search path, derive `session_user`, lock current authority, and recheck epoch and expiration before atomically recording effects, stream head, and outbox intent. Replays with the same deterministic identity and bytes are idempotent; a conflicting replay, invalid chain, revoked grant, or stale epoch is rejected. The worker has named function execution grants, not direct authority/effect/outbox table access.

Atomicity applies to each admitted chunk. The fixed worker commits chunks sequentially, so a later failure or lost response may leave a durable prefix. Recovery replays the same source from byte zero.

**Redis is a projection with explicit uncertainty.** A PostgreSQL outbox claim commits before Redis I/O. Decimal bigint comparisons preserve ordering above JavaScript/Lua floating-point precision. Readback determines `ACKED`; ambiguous publication remains `UNKNOWN`. Cache loss requires a fresh authority check before rebuilding the current same-epoch checkpoint. Pyrsistent protects versioned in-memory snapshots; it is not a disk persistence mechanism. The PostgreSQL commit outcome and Redis projection outcome are separate results.

**Input and resources are bounded at active seams.** The worker accepts one newline-delimited JSON frame with only the stream identifier and canonical payload. Maximum decoded payload is 65,536 bytes, frame size is 131,072 bytes, and request-processing deadline is at most 30 seconds. The timer starts after configuration and launcher-context checks. Configuration must be a private regular file owned by the service identity, with no group/other permission bits; mode 0600 is recommended and 0400 is also accepted. `O_NOFOLLOW` and `O_NONBLOCK` prevent symlink and FIFO admission. Production database access requires observed TLS and a nonadministrative LOGIN; production Redis requires TLS, ACL credentials, certificate verification, and hostname checks.

**Cancellation does not depend on logging.** Independent adversarial review reproduced a full/closed stderr pipe preventing deadline termination. The watchdog now exits directly with status 124. Another reproducer found configuration FIFO blocking before validation; nonblocking open plus regular-file verification closes it. A third probe found that an error diagnostic after watchdog cancellation could itself block; CLI rejection now exits directly with status 1. Typed exceptions remain available through the Python APIs. Real child-process regressions cover the closed/full-pipe cases. A lost response or timeout does not prove rollback: replay and reconcile the same request identity.

**The streaming recurrence survives boundaries.** CDC means content-defined byte chunking in this branch, not PostgreSQL logical change-data capture. Its rolling window continues across emitted chunks. The initial mutation campaign exposed a short-tail gap in the selected parity witnesses: a rolling-state-reset mutant survived when long chunks repopulated the window. The independent polynomial oracle remained valid. New 1-, 2-, and 3-byte tail fingerprints detect that same retained mutant. All 12 selected mutations now fail their witnesses and pass after exact restoration. Recovery starts a new writer and replays the same immutable source, stream UUID, epoch, and policy from byte zero.

**Fixture defects were repaired without substituting database behavior.** The original PGlite socket adapter could consume EOF before asynchronous TCP delivered COPY bytes, and prepared-statement names leaked between logical clients. The delivered repair kit passes the actual frontend bytes to PostgreSQL's synchronous COPY callback and namespaces named statements per logical handler. COPY executes in PostgreSQL; there is no INSERT replacement or fabricated success response. Exact upstream and patched hashes, a readable patch, reproduction instructions, and regressions accompany the kit.

## Runtime and qualification boundaries

The executed software profile used **CPython 3.13.17**, **PostgreSQL 18.6 through PGlite 0.5.15**, `pglite-socket` 0.2.18, Node 24.22.1, and **Redis 6.2.14**. These identify the test substrate; they do not recommend an old Redis server for production. `uv.lock`, the npm lock, tool profiles, and observed executable hashes preserve this identity. The declared Python range is 3.12–3.13; only 3.13.17 has current runtime evidence.

| Profile | State | Reason and next proof |
| --- | --- | --- |
| Software contracts, drivers, ORM, actual SQL, Redis, and injected-launcher worker composition | **PASS** | Current source-bound tests execute real PostgreSQL SQL and Redis operations |
| Native standalone admission tools | **PASS — 24 applicable lanes passed; 18 explicit nonapplicability records; zero failures or holds** | Exact supplied bundle, disclosed repair overlay, and lane receipts |
| Native PostgreSQL LOGIN/SCRAM/TLS and child startup identity | **NOT_QUALIFIED** | Native `initdb` refused uid 0; available namespace could not host a nonroot server. PGlite startup username does not establish authenticated `session_user` |
| Actual Tailcat 0.7.0 wire exchange | **NOT_QUALIFIED** | Actual process failed `netmon.New: route ip+net: netlinkrib: operation not permitted` before tunnel establishment, even with local DERP |
| Independent-backend concurrency, wire cancellation, storage crash/power-loss recovery, production containment activation | **NOT_QUALIFIED** | Single-backend WASM and static deployment surfaces cannot establish these behaviors |

The software worker fixture explicitly sets a PostgreSQL test session identity and injects trusted launcher context. This exercises actual privilege and authority functions without claiming native startup authentication. The failed native child and Tailcat attempts remain in historical evidence. Separate native qualification tests are delivered under `qualification/` and are not hidden skips or xfails in the software suite.

An asyncpg teardown limitation in the adapter is explicitly classified: closure has a deadline, forced termination is observable, and tests do not relabel it as a graceful handshake. PostgreSQL WAL settings are observed prerequisites; they do not prove storage hardware, power-loss recovery, replication durability, or mission throughput.

## Standalone admission and dependency review

The native 42-lane bundle is the supplied `HMT-CI-42-Independent-Lane-Bundles_v2.0.0.zip`, SHA-256 `85882a410803d8741bdce4a56f6f6c2a7629e950bb5c938241bd6fd74944a6f1`. It remains an external inherited prerequisite. The original bytes were preserved. Three narrowly scoped overlay changes repair two stdlib `resource` symbol collisions and one schema-required `sha256:` prefix. The overlay changes no rules, resource ceilings, protected paths, or candidate thresholds. Sixteen regression/parity checks preserve limit enforcement and original findings. The first complete native run recorded 22 PASS, 18 NOT_APPLICABLE, and two FAIL: three unused test imports and an automatically loaded Hypothesis collection hook. The imports were removed, required pytest plugins were loaded explicitly, and software, mutation, V&V, and all 42 lanes were rerun against the corrected source. The original failed run and plugin-runtime revalidation remain in history. The optimization lane's intentional Python 3.15.0rc3 `frozendict` requirement is retained; other lanes use declared prepared interpreters with the patch-version difference recorded.

Dependency review uses actual lock hashes, published artifact identities, current advisory outputs, installed license metadata, and executed engineering evidence. The final inventories include 35 installed Linux Python dependencies, nine npm dependencies, and the separately checked setuptools 84.2.1 build backend. The two Windows-only lock entries are explicitly scoped by their platform markers. All checked advisory inventories reported zero known vulnerabilities at the recorded audit time; this is not a future vulnerability guarantee.

The native stock license profile initially held Psycopg's LGPL metadata. That result is retained. The selected profile adds only the exact `LGPL-3.0-only` token for the three pinned Psycopg distributions explicitly required by this task. It does not waive license obligations or claim legal compatibility for a future product. Engineering reviews of dependency surfaces are labeled as such; no human or organizational signoff is invented.

## Provenance and reproduction

Creation provenance was stamped before implementation. The measured source has 183 files, including newly generated package metadata retained to preserve the exact admitted inventory. Git custody verifies the real historical snapshot at `e3387ddb0772fdeaa4093f7b049033c5ef6f43eb` and candidate `9bc06522f27d4576f08caf44f4989031d1b145f1`. Final reports and release evidence are appended after execution and are separately bound by the artifact manifest; they are not relabeled as files that existed in the measured candidate.

`release/artifact_manifest.json` classifies each shipped file as new or modified, identifies excluded inherited inputs, and hashes every other payload file. The external archive checksum binds the manifest bytes without a self-hash claim. `release/provenance.json`, the cumulative seven-column gate ledger, eight-column RRCA ledger, and source-grounded, derived ontology field bindings preserve evidence lineage and resolved incidents. Historical failures are retained alongside their repair and revalidation evidence.

Follow `Runbook.md` for frozen installation, disposable services, software admission, mutation execution, role provisioning, and native qualification. Follow `admission/README.md` for the exact independent tool prerequisites, repair verification, runtime profiles, and request construction. Fresh runs require new evidence directories. Any change to implementation, SQL, policy, fixtures, dependencies, or authority semantics requires a new source-bound evidence epoch.

The final archive excludes the inherited reusable-design package, inherited native tool implementation, upstream npm source, virtual environments, service binaries, the working `.git` directory, and exploration code. A small first-party Git custody bundle preserves the actual baseline and candidate objects needed for optimization replay. The archive includes the new executable primitives, contracts, deployment surfaces, tests, portable reproduction guidance, and observed verification receipts needed to assess this scoped release.
