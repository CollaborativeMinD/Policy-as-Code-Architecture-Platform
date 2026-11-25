# PostgreSQL branch admission and native CI42 reproduction

## Recorded result and custody

The completed native campaign `pg-native42-final-002` dispatched all 42 lanes: **24 PASS, 18 NOT_APPLICABLE, 0 FAIL, and 0 HOLD**. Every N/A has an explicit predicate checked by the native engine. Source stability and evidence custody passed. The applicable `pytest` lane executed all 446 software tests; no test was skipped or deselected. `lane-statuses.json` records the complete inventory.

| Identity | Recorded value |
|---|---|
| Final candidate Git commit | `9bc06522f27d4576f08caf44f4989031d1b145f1` |
| Historical Git baseline | `e3387ddb0772fdeaa4093f7b049033c5ef6f43eb` |
| Standalone source digest | `6771f2465d4f6e644f13af47375e562ccaee1a5476d44e8846954b0095fa13b7` |
| Native orchestration scope digest | `32f657c21db285274e40de63e57a6c760e2853b2cf0626afdf6a705e958719b7` |
| Native engine digest | `c5fb2a4895108113445b9cbc3559b8ef033008b0f653f73f42ceb0c6a3a1ecd1` |

The two source digests use different declared scopes and algorithms. Preserve both. The native request includes the admission configuration in its scope. Final reports and receipts belong outside the Git target.

Paths below are relative to the delivered PostgreSQL packet root:

| Packet path | Purpose |
|---|---|
| `evidence/native42/` | Unmodified final request, lane receipts, summary, and journal files |
| `evidence/history/native42-001/` | Preserved first campaign: 22 PASS, 18 N/A, and 2 FAIL |
| `evidence/git_custody/reference-history.bundle` | Actual first-party historical and final Git objects |
| `evidence/native_vv/` | Observed native qualification payload, DuckDB ledger, and full test trace |
| `admission/native_inputs/` | Sealed evidence-binding claims and explicitly synthetic PACE input |
| `admission/dependency_reviews/pg-reference-2-20261104/` | Exact-source external policy and nine-family review evidence |
| `admission/tool_overlay/` | Three hash-bound native loader/digest patches and regression receipts |
| `admission/runtime-profiles-observed.json` | Declared lane runtimes and observed interpreter overrides |
| `evidence/dependencies/license/profile.json` | Observed license profile and its precise scope |

The first campaign exposed three unused imports and a strict native pytest guard triggered by an auto-loaded Hypothesis collection hook. The three imports were removed. The final runtime explicitly loaded only the required asyncio and coverage plugins. Software admission, all 12 mutations and restoration runs, native V&V, external review binding, and CI42 were then rerun against the final source. Earlier failures remain in their original receipts.

## Restore the exact target and native engine

Clone the history bundle into a separate target directory. Its SHA-256 is `35623e912abb5afa2942b672f332b34d394e513c49136232d245029d7bf8288f`.

```bash
git clone evidence/git_custody/reference-history.bundle /absolute/replay-target
git -C /absolute/replay-target rev-parse HEAD
git -C /absolute/replay-target cat-file -e e3387ddb0772fdeaa4093f7b049033c5ef6f43eb^{commit}
```

The final commit must match the table above. The bundle receipt records successful `git bundle verify` and exact source-file custody. Keep the delivered reports outside this checkout. The source snapshot includes generated package metadata; an installation that changes those bytes creates a new source identity and needs fresh binding.

Restore the original `HMT-CI-42-Independent-Lane-Bundles_v2.0.0.zip` separately. Its SHA-256 is `85882a410803d8741bdce4a56f6f6c2a7629e950bb5c938241bd6fd74944a6f1`. The inherited suite is not duplicated in this packet. Preserve its original bytes, create a working copy, and apply only the three supplied patches after checking the before/after hashes in `admission/tool_overlay/manifest.json`. The supplied 16-check regression receipt records unchanged policy limits and findings. The repairs resolve two resource-module collisions and the required digest prefix; they do not alter gate thresholds.

Prepare the pinned target dependencies from `uv.lock`. Use the observed per-lane runtime profiles: the target and analyzer overrides were CPython 3.13.17; optimization ran its original frozen lane lock under CPython **3.15.0rc3**. Most original lane profiles declare 3.13.15, so the recorded 3.13.17 override must remain explicit. The native analyzer environment used Ruff 0.16.10, mypy 1.20.2, Pyrefly 1.3.2, and its pinned tools, including uv 0.12.23 on that environment's PATH. Do not use one assumed interpreter for all lanes.

## Bind the request without adding a renderer

Copy `admission/native42-request.template.json` to an external working directory. Fill every `@@NAME@@` token manually using `bindings.example.json` as the checklist. `bindings.observed.json` records the actual completed run's bindings; its original scratch paths are historical facts, not portable defaults. Alternatively, edit a copy of the observed native request. Preserve the native placeholders `{target}`, `{candidate}`, `{evidence}`, and `{run}`; the native executor owns those substitutions.

Use absolute paths, a fresh run ID, and a fresh evidence directory disjoint from both the target and the native suite. Relevant packet bindings are:

| Binding | Sealed packet input |
|---|---|
| `EVIDENCE_BINDING_ROOT` | `admission/native_inputs/evidence-binding` |
| `PACE_INPUT` | `admission/native_inputs/pace-evaluate.json` |
| `ADVERSARIAL_POLICY` | `admission/dependency_reviews/pg-reference-2-20261104/policy.json` |
| `POLICY_SHA256` | `6a819f707026021de229ffd9d5aebb6e39d9f594c6f4df6d09fa93abd48c26e2` |
| `POLICY_EPOCH` | `pg-reference-2-20261104` |
| `NATIVE_VV_ROOT` | A newly generated, location-correct V&V output, or an explicitly identified derivative of the sealed packet |

The template retains the actual license roots and allowed identifiers. The added `LGPL-3.0-only` token is supported by the exact Psycopg inventory and profile; it is not a general license exception. Keep all 42 lane entries, their full arguments, and their explicit N/A predicates. The native request parser and applicability engine validate these during execution. A schema-valid request alone does not qualify the source.

### Sealed evidence consumption versus a fresh epoch

Reading or rechecking `admission/native_inputs/` verifies the supplied historical evidence bytes. Reusing those inputs does **not** create a fresh software, mutation, advisory, or review observation. Their original timestamps, run IDs, and source hashes remain authoritative for what they observed.

The sealed V&V `qualification.json` contains the original absolute DuckDB path. Copying it to another machine does not make that path valid. Preserve the original receipt. Regenerate location-correct V&V inputs with the admitted exporter, or clearly label a separate relocation derivative and retain its transformation record. Never silently rewrite a historical receipt.

For a genuinely fresh epoch, run the already-admitted tools from the Git target, with the target interpreter and fresh external outputs:

```bash
/absolute/target-python tools/admit.py --root /absolute/replay-target --output /absolute/new-evidence/software
/absolute/target-python -m tools.mutation_campaign --root /absolute/replay-target --output /absolute/new-evidence/mutations --timeout 90
/absolute/target-python -m tools.native_vv --root /absolute/replay-target --suite /absolute/repaired-ci42 --admission /absolute/new-evidence/software --mutation /absolute/new-evidence/mutations/mutation-report.json --output /absolute/new-evidence/native_vv --analyzers-python /absolute/analyzers/bin/python
```

These commands require PostgreSQL and Redis fixtures. Use the packet's pinned fixture setup, or explicitly provided native service endpoints through `HMT_TEST_DSN` and `HMT_TEST_REDIS_URL`. For the observed managed fixture profile, set `HMT_PGLITE_CLI` to the repaired fixture server and `HMT_REDIS_SERVER` to the pinned Redis executable. The observed absolute paths are recorded in `environment.observed.json`.

Refresh the evidence-binding claim hashes and the external dependency/review epoch against the new source and actual receipts. Follow the supplied dependency review reproduction instructions. Reused advisory captures must retain their actual timestamps and establish unchanged dependency identities. Update the request's source digest, policy digest, epoch, and V&V paths. A changed source or dependency set cannot inherit an old PASS by changing labels.

## Execute the native campaign

Export the selected service configuration and invoke the existing native orchestrator:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTEST_PLUGINS=pytest_asyncio.plugin,pytest_cov.plugin \
/absolute/analyzers/bin/python /absolute/repaired-ci42/src/hmt-ci-app.py run /absolute/new-request.json
```

Use the same explicit plugin selection for fresh standalone admission; pytest-cov is required there. Native pytest owns its coverage invocation and does not start an additional pytest-cov measurement without `--cov`.

Inspect the new summary and every lane receipt. Require all 42 completed entries, successful applicable gates, validated N/A predicates, source stability, and reconciled custody. Record the actual exit status. Keep failed epochs unchanged. After the process exits, copy the journal with any accompanying WAL/SHM files as one evidence set; the delivered final journal was quiescent before packaging.

## Scope of the result

The software campaign measured 265/278 production branches (95.323741%) and 1285/1301 lines (98.770177%), with all 446 tests passing. Twelve assertion-killed mutants and twelve restored witness runs passed. Native V&V consumed the complete declared candidate ledger and test manifest. The source has separate deployment qualification profiles for capabilities outside the default software fixture; this result does not assert native multi-backend behavior, remote TLS/SCRAM deployment, hardware power-loss durability, or completed Tailcat wire qualification.

The native PACE input is a nominal, explicitly synthetic reference-profile evaluation. Its scope is recorded in `admission/native_inputs/pace-scope.json`; it does not establish pressure-equation equivalence or production calibration. Actual branch PACE callback and recovery behavior is covered by its separate software and causal witnesses. Human approval and deployment promotion remain false in the external policy.
