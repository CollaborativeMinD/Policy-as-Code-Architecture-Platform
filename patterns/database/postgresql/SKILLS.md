# Usage map

This file maps implementation tasks to the PostgreSQL reference patterns. It is ordinary branch documentation and does not install an assistant skill or add authority to an agent. The user's governing instructions and the branch's [Agents.md](Agents.md) remain the operational controls.

## Select work by the seam being changed

| Intended work | Start with | Required inputs | Reviewable output |
| --- | --- | --- | --- |
| Add a PostgreSQL connection path | Patterns 01, 06 | Host-owned configuration, TLS trust, role and connection budget | Explicit driver/engine owner and finite lifecycle |
| Add a raw blocking query | Patterns 02, 05, 09 | Literal SQL, bounded values, transaction boundary | Strict DTO result and rollback evidence |
| Add an asyncio query | Patterns 03 or 04, then 06 | Task ownership, deadlines, cancellation semantics | Awaited path with finite lease and visible cleanup outcome |
| Add SQLAlchemy or SQLModel storage | Patterns 07 or 08, then 09 and 12 | PostgreSQL mapping, DTO, migration, engine lifecycle | One pool and an explicit commit boundary |
| Export analytical rows | Patterns 10 and 17 | Stable ordering, batch and total limits, plan | Server-cursor frames with deterministic closure |
| Load a finite row batch | Pattern 11 | Strict rows, batch cap, idle connection | Atomic COPY or pipeline result with rollback evidence |
| Evolve the schema | Pattern 12 | Owner-authored immutable migration bytes | Recorded checksum and transactional result |
| Accept a peer-bound stream | Patterns 13, 15, 16 | Trusted launcher binding, fixed LOGIN, epoch, source policy | Admitted effects and an immutable checkpoint |
| Recover projection delivery | Pattern 14 | Stored claim token and fresh PostgreSQL checkpoint | Observed ACKED/UNKNOWN state or explicitly authorized rebuild |
| Assess optimization or durability prerequisites | Pattern 17 | Representative query window and connected server | Plan/settings observations with bounded claims |

## Composition rules

1. Start at the strict boundary. Validate configuration, request shape, identifiers, limits, and stored result types before treating them as admitted values.
2. Name the connection, transaction, generator, pool, and process owner. A helper that borrows one of these objects must not silently acquire broader commit authority.
3. Keep PostgreSQL identity and epoch admission in the transaction that records the effect. Tailcat context, PACE state, Redis content, and immutable memory objects do not replace that check.
4. Select bounded work deliberately. A finite default is not mission calibration, and a pool capacity is not a bound on every queued task.
5. Treat an uncertain response as an uncertain observation. Use stable request identity and the outbox reconciliation APIs; do not invent success or retry an external effect blindly.
6. Preserve evidence scope. A repaired SQL fixture, controlled fault, injected launcher context, native database service, and actual transport run support different claims.

## Where to find the executable truth

[The index](Index.md) maps every package source module to a pattern. [catalog.json](catalog.json) records the independent pattern inventory, public APIs, tests, limits, and upstream references. The `contracts/` directory records V&V obligations. The `tests/` directory contains executable checks; `qualification/` contains the service/transport profiles that need a suitable native environment.

Use [Runbook.md](Runbook.md) to run the branch and [admission/README.md](admission/README.md) for the governing admission. Assess outcomes through [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md) and the release records. This map is a navigation aid; it is not an additional runtime component, a deployment permission, or a substitute for test evidence.
