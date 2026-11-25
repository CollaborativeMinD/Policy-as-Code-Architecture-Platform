# Portable external review and replay

This packet contains the sealed external policy, nine engineering review records, and actual supporting evidence. It contains no regenerated approval, bundled reviewer implementation, or authority to promote a changed source tree.

## Verify the delivered review packet

Keep each sealed epoch's `policy.json`, `reviews/`, and `inputs/` together. Every native `evidence_ref` is relative to the policy directory. Absolute paths inside historical receipts identify the recorded execution environment; they are not paths that must exist on the reader's machine.

The current packet is **`pg-reference-2-20261104`**, bound to source digest `6771f2465d4f6e644f13af47375e562ccaee1a5476d44e8846954b0095fa13b7`. Its raw policy SHA-256 is `6a819f707026021de229ffd9d5aebb6e39d9f594c6f4df6d09fa93abd48c26e2`. The first epoch remains historical evidence.

Obtain the supplied native42 bundle separately and verify its recorded artifact hash. Prepare its exact runtime and the disclosed hash-verified repair overlay using `admission/README.md`; preserve the inherited original. The unchanged native policy parser and evidence verifier can check this external packet:

```bash
python /external/ci42/tools/adversarial-agents.py compile-policy \
  --policy /external/reviews/pg-reference-2-20261104/policy.json \
  --policy-sha256 6a819f707026021de229ffd9d5aebb6e39d9f594c6f4df6d09fa93abd48c26e2 \
  --epoch pg-reference-2-20261104
```

The paths above are operator-selected locations for the separately supplied engine and delivered packet. No scratch generator is required or shipped by this workflow.

Compilation validates schema, epoch, safe relative paths, and evidence hashes. It is not the complete native campaign. Native evaluation additionally requires the recorded immutable Git baseline and candidate; receipt-identical replay requires those original Git objects, the recorded policy, the exact evaluator, and the required environment identity. Use any delivered Git custody bundle/export to restore them and verify the recorded hashes. A working tree reconstructed only from files with new commit metadata is a fresh equivalent-source run, not receipt-identical replay.

| Git identity | Commit |
|---|---|
| Historical baseline | `e3387ddb0772fdeaa4093f7b049033c5ef6f43eb` |
| Current candidate | `9bc06522f27d4576f08caf44f4989031d1b145f1` |

## Evidence required for changed source

Any changed source needs a new review epoch and fresh source-bound witnesses. Use the branch's software-admission, mutation, and native V&V commands documented in `Runbook.md` and `admission/README.md`. Write each run into a new external directory. Do not edit the old policy to turn a new tree into a historic pass.

An engineering reviewer must independently inventory every surface selected by the original native `dependency_surface` predicate, including all `tools/` files, Python manifests/lockfiles, and npm manifests/lockfiles. For each exact relative path and SHA-256, supply all nine distinct review families: reputation, identity, source integrity, hash, provenance, vulnerability, license, organizational standard, and closure. Every review must identify its evidence, scope, remaining limits, epoch, and disposition. New or renamed surfaces and changed package versions require substantive review; a copied family label is insufficient.

The original native `Review`, `Admission`, `Policy`, and `verify_reviews` contracts define the exact schema. Each passing review references a regular, nonsymlink evidence file below the external policy directory, no larger than 1 MiB, and records its SHA-256. Review epochs must match the policy epoch. Keep raw large evidence separately and bind it through smaller hashed review records. Preserve the native limits, protected paths, mandatory protections, and declared static profile.

Before sealing, verify all of these conditions against the actual captured artifacts:

- The exact current source inventory agrees with software admission, actual JUnit identities, branch/line coverage, and final native V&V/analyzer receipts. Failures and suppressed tests cannot be converted to passing witnesses.
- Every selected mutation caused a viable assertion failure. Baseline execution, isolated imported source, byte restoration, and the restored passing execution are established from per-phase process and JUnit evidence.
- Native Python advisory output covers the exact installed lock population and versions, with no skipped or vulnerable dependency. npm audit covers the complete current fixture lock and the command's prefix points to that fixture. The build backend is separately covered when it lies outside the runtime/dev lock.
- All audit captures retain actual argv, timing, integer exit status, stdout/stderr, and output hashes. Never reconstruct an unobserved successful invocation from a JSON payload alone.
- Installed license metadata matches the exact lock. Any selected license profile is explicit, narrowly identity-bound, and separately hashed; preserve the native stock result. A metadata inventory is not legal compatibility advice or human approval.
- The source and dependency inventories remain unchanged after evidence assembly. Native policy parsing, review hash verification, and the dependency witness pass on the immutable candidate.

## Exact dependency profile and audit reuse

The measured Linux profile contains **35 installed Python dependencies**, **nine npm fixture dependencies**, and **setuptools 84.2.1** as the separately audited build backend. `colorama` and `tzdata` are excluded only because every applicable lock reference has `sys_platform == 'win32'`; they are not claimed as runtime-tested Linux dependencies.

The chosen license profile retains the original native HOLD and adds the exact token `LGPL-3.0-only` only after restricting it to `psycopg==3.3.7`, `psycopg-binary==3.3.7`, and `psycopg-pool==3.3.3`. Its actual native command, 35 roots, allowed tokens, installed metadata, and capture hashes are supplied. The original engine is unchanged. No third-party distributions are shipped in the branch, and the profile grants no redistribution compatibility opinion.

The build-backend evidence records versioned official PyPI metadata and a wheel digest verified before isolated installation. The wheel and isolated environment are excluded from delivery. A future build should obtain the artifact from its recorded official source, verify the published hash, and execute fresh native checks where required.

Epoch two reused the actual advisory/license queries because all **32 dependency-surface hashes and the complete package inventory were unchanged**; only three unused test imports were removed. The original query dates remain visible. The software, mutation, native V&V, and complete native campaign were rerun for the new source. Reuse does not imply a new advisory query or permanent admission.

Engineering review records retain `human_approval: false` and `promotion_authorized: false`. Native PostgreSQL authentication/TLS/concurrency, authenticated Tailcat wire operation, physical power-loss recovery, and deployment activation require their separate qualification profiles.
