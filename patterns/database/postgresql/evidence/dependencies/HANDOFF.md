# Native dependency review handoff

The unmodified original native dependency checker accepted **32 exact file surfaces, with all nine review families**. The records are automated engineering findings. They assert no human approval, institutional endorsement, deployment activation, or promotion authority.

## Immutable review identity

| Field | Value |
|---|---|
| Epoch | `pg-reference-1-20261104` |
| External policy | `pg-reference-1-20261104/policy.json` |
| Raw policy SHA-256 | `3847a106df2212e5e9f5f91ca6e4a765740bea618bb638825deb94d123fd88b2` |
| Semantic policy SHA-256 | `4366359ca7f0387700826c82c8879f20e066c9cd9f7b924decff43418750835d` |
| Frozen source digest | `6710f678900766f47969172cc2f1da03de3eb9d6fb42ca86135cb2e3f59ca11d` |
| Original native engine identity | `5703738103a4686bb3000bd80ef20710d86c7c91838f38a200cc9a3131283739` |
| Current Git candidate | `4cbd9152b079cf3f745b5de4ac6e181cc2f782d9` |
| Historical Git baseline | `e3387ddb0772fdeaa4093f7b049033c5ef6f43eb` |

The policy keeps the native static profile, default limits, default protected paths, and mandatory protections. Every review file is below 1 MiB. The policy's nine evidence files refer to content-addressed copies of the actual supporting receipts. `candidate-binding.json` verifies the exact policy inventory against the immutable Git candidate using the disclosed overlay; its snapshot and dependency functions are byte-identical to the original. The original snapshot attempt is retained as a failure: its pre-exec hook encountered the confirmed `resource` loader-symbol collision before applying OS limits. The previously reviewed overlay fixes that binding and preserves all five OS ceilings.

This is the **first review epoch**. The first complete native42 campaign subsequently reported 22 PASS, 18 explicit nonapplicable lanes, and two failures. Three unused test imports and pytest plugin auto-discovery were corrected. A new source digest and fresh software, mutation, V&V, and native42 campaign belong to `pg-reference-2-20261104`; the first policy and receipts remain historical evidence.

## Actual evidence checked

- Final source-bound admission: **446 tests passed**, no suppression, **95.3237% branch coverage** and **98.7702% line coverage** across all 39 production modules. Actual JUnit was reparsed.
- **12/12 semantic mutants** produced assertion failures; baseline and exact restoration reruns passed. Every mutated/restored JUnit was reparsed, and the final source digest matched.
- Current native V&V and fresh Ruff, mypy, and Pyrefly observations passed. Native42 overall disposition belongs to its separate campaign.
- Actual native pip-audit covered **35 installed Linux lock dependencies** with no skipped or vulnerable record. `colorama` and `tzdata` remain outside this Linux execution profile only after every lock reference was verified as `sys_platform == 'win32'`.
- Actual npm audit covered **all nine fixture lock packages**, with no reported vulnerabilities; all nine recorded license expressions are `Apache-2.0`.
- The separate **setuptools 84.2.1** build-backend audit and original native license check passed. The downloaded wheel matched the versioned official PyPI metadata SHA-256 `ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2`.

## Narrow license selection

The stock native HOLD remains at `../epochs/final-license.json`. `license/profile.json` has SHA-256 `b74040e0a3317b837d8b7893c941ffbf3fa3bc8e91706d9c28af64d9c17418a9`. The chosen profile adds the exact token `LGPL-3.0-only` after restricting it to `psycopg==3.3.7`, `psycopg-binary==3.3.7`, and `psycopg-pool==3.3.3`. The original native engine remains unchanged. The full executable command, 35 roots, allowed tokens, metadata, raw output, and hashes are in `license/receipt.json` and sibling files.

This is a dependency metadata inventory for the user-requested Psycopg reference. Third-party distributions are not shipped in the reference branch. The profile does not assert legal compatibility for another distribution or deployment.

## Reuse the generator

`generate.py prepare` uses the original engine's exact dependency predicate, validates package pins, records the source inventory, and produces `PENDING_FINAL_INPUTS`. `generate.py finalize` accepts `prepared.json` and `inputs.json`, validates real current receipts, seals evidence, checks the policy through the original native parser/verifier, and emits a policy only after the native dependency witness and final source check pass.

For a new source epoch, create a new preparation and new receipt inputs, explicitly review any changed surfaces, and use a fresh output directory. Do not relabel the existing epoch. A new, unmapped surface raises `UNREVIEWED_SURFACE`; source drift, stale epochs, failed processes, advisory skips, package gaps, and mismatched license profiles block emission.

`generator-verification.json` records **11 passing negative controls** for changed dependency bytes, stale review epochs, missing/advisory-skipped/vulnerable packages, forged PASS with a failed process, policy pin tamper, native stale epoch, review-file tamper, duplicate review families, and the native HOLD on changed dependency content. The checks are reviewer tests, not additional product test counts.

## Remaining claim boundaries

The review closes exact-source software-reference and dependency evidence only. Native PostgreSQL authentication/TLS/multiple-backend contention, physical WAL power-loss recovery, and authenticated Tailcat wire operation require their separate qualification profiles. No branch source, contracts, lockfile, supplied policy, or original native engine was changed during this final review subtask.
