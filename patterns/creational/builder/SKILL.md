# RDP-C02 — Builder

## 1. BLUF
Construct a complete configuration through ordered immutable stages. Use the strict constructor when there are few fields. Added abstraction earns its cost only when the declared variation or custody is needed.

## 2. Identity and contracts
Version 1.0.0; RDP-C02-INV-001. Strict frozen Pydantic contracts reject extra fields and invalid bounds. Source pins live in manifest.json and catalog.json. Engineering reference only; no operational or promotion authority. 

## 3. Problem and anti-pattern
An incomplete mutable dict escapes before required configuration exists. The live negative witness below runs a bounded local counterexample or forbidden input. It is an educational defect, not privileged service code.

## 4. Mechanism and simpler alternative
Builder(owner).with_limit(limit).finish(); finish before limit is denied.

Simpler alternative: direct Pydantic Config constructor. Responsibilities and associations are visible in the actual implementation. No inherited scanner/provider authority is copied.

## 6. Worked inputs
Choose nominal or edge. Declared bounds are enforced by contracts.py. Both choices recompute a positive result and an independent negative predicate. The JSON output exposes the exact input and output.

## 8. Behavior under pressure
Failure hypothesis: partial invalid configuration. A True negative_detected predicate means the forbidden behavior was rejected or the defective fixture differed from the lawful oracle. Tests include boundary and exception/replay pressure as applicable.

## 9. Applicability gate
Construct a complete configuration through ordered immutable stages. Use the strict constructor when there are few fields.

The direct Pydantic Config constructor comparison avoids carrying a hierarchy when a plain function or immutable table satisfies the same contract.

## 10. Reproducibility and non-claims
From repository root: `uv run --frozen pytest -q patterns/creational/builder/tests`. Run `uv run --frozen marimo run patterns/creational/builder/notebook.py`. Python/marimo versions are frozen in uv.lock. Evidence is source-bound in evidence/qualification.json; digests in manifest.json. Native script/export is separate from local Hub/browser qualification. No physics, hostile-host isolation, distributed exactly-once, production identity, or human promotion claim.

## Implementation API
Builder(owner).with_limit(limit).finish(); finish before limit is denied.

## Policy and provenance
Current released HMT-AXIOMS/2.0.0, HMT-TESTING-CONTINUOUS-ADMISSION/1.0.0, HMT-RRCA-POLICY/4.0.0, and reuse/bounded-transformation policies apply. Full exact bindings: policy/policy_bindings.json. Reuse disposition: ADAPT or NO_FIT for inherited code; all new leaf code has its own source identity. The field cards supply teaching cadence, not executable bulk.

## Stable witnesses
RDP-C02-EX-001; RDP-C02-INV-001; RDP-C02-T-001; negative and edge tests in tests/. Read contracts.py, reference.py, example.py, then notebook.py.
