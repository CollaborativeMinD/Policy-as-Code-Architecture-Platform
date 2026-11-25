# PostgreSQL branch governing instructions

## Ownership and scope

This branch contains reusable PostgreSQL software primitives. The Human Architect retains policy, deployment, activation, and promotion authority. A passing software campaign qualifies only its declared source and executable requirements. It does not activate a mission or establish native service, hardware, or field qualification.

The attached Verification and Validation, Structural Complexity, and PACE-T policies version 2.0.0 govern this branch. RRCA V&V v4 governs cumulative evidence and the eight-column sub-agent ledger. Source references and exact input hashes are recorded in `references/` and the release provenance. Existing reusable-design-reference files are inherited authority, excluded from this delta; the old 15-pattern catalog is not changed.

## Required engineering sequence

1. Select the PostgreSQL contract, failure mode, gate, and exact source lineage before implementation. Use `contracts/candidate_dimensions.json` and the complete traceability inventory.
2. Run a tracer on the intended execution path. Preserve failures and classify an unavailable external substrate independently of executable software logic.
3. Implement bounded transactions, strict inputs, explicit connection ownership, and least privilege. Credentials, peer identity, database role, and chunking policy are never selected by client payload.
4. Derive negative, boundary, temporal, mutation, causal, and integration witnesses from the selected requirements. Keep the full SQL CROSS JOIN; every excluded row needs an explicit violated applicability predicate.
5. Run fresh standalone admission, the isolated mutation campaign, and all applicable supplied native Python lanes. Never replace actual execution with a report claiming execution, or count a timeout, collection error, or missing dependency as a killed mutant.
6. Retain seven-column cumulative gates and eight-column RRCA records. A repaired failure needs a causal explanation, the same requirement/failure mechanism, and observed regression success.
7. Freeze source; bind JUnit, coverage, mutation, rule observations, dependencies, service identity, and native receipts to that exact inventory. A source change invalidates an earlier current-source claim.

## Nonnegotiable software boundaries

- Python branch coverage and line coverage must each be at least 90%; the blended percentage cannot substitute for branch coverage.
- Functions stay below 50 physical lines and modules below 150. Watch thresholds remain visible. No `skip`, `xfail`, hidden alternate path, relaxed schema, or omitted production module may manufacture a pass.
- PostgreSQL derives authority from `session_user`, locks the authoritative row, checks epoch and expiry, and commits the effect, chain head, and outbox together. A Redis value, Pyrsistent object, or Tailcat address never grants database authority.
- Tailcat runs one host-owned fixed command and supplies the authenticated peer context. A process environment injected by an arbitrary caller is not authentication. The native LOGIN and tunnel profiles are separately executable.
- Unknown acknowledgement is a retained state. Replay of the effect uses its deterministic identity; projection recovery checks current authority and reconciles readback. No external exactly-once delivery claim is made.
- Persistent immutable memory structures are separate from PostgreSQL durable custody. Observed WAL settings are prerequisites, not evidence of storage power-loss behavior.
- PACE enforces local operation selection through `perform`; database authority remains an independent guard. Terminal is latched within a lifecycle. Connectivity alone cannot restore capability.

## Runtime and delivery

Use the checked `uv.lock` and `.python-version`. The test-only PGlite repair has its own exact npm pins, before/after hashes, bounded protocol adaptation, and limitations. Never load that adapter into production Python. An explicit disposable native DSN takes precedence over the test engine.

No live production fault injection, secret publication, automatic policy change, external message, image publication, or mission promotion is authorized by this reference package. Run destructive setup and mutation witnesses only in the disposable test database declared in the Runbook.

## Review and handoff

Reviewers must contradict confidence claims against current receipts and test the seam between ownership domains. A worker cannot promote its own consequential output. The release manifest classifies every delivered artifact as new or modified and separately records inherited references that are excluded. Exploration notebooks, original archives, caches, environments, credentials, and generated dependency trees stay outside the delivered branch.

`machine_handoff.json` must validate against the supplied Ontology Machine Handoff schema. The release report states scope, measured results, residual external qualification, and exact rerun commands. Do not broaden a software finding into a field-readiness claim or turn an unrelated deployment condition into a blanket hold on these reference primitives.
