# RDP-S03 — Proxy

## 1. BLUF
Guard each artifact read with explicit identity, audience, scope, epoch, time, and bytes. Use direct immutable reads when there is no separate authority boundary. Added abstraction earns its cost only when the declared variation or custody is needed.

## 2. Identity and contracts
Version 1.0.0; RDP-S03-INV-001. Strict frozen Pydantic contracts reject extra fields and invalid bounds. Source pins live in manifest.json and catalog.json. Engineering reference only; no operational or promotion authority. 

## 3. Problem and anti-pattern
A source changes between pointer inspection and actual return. The live negative witness below runs a bounded local counterexample or forbidden input. It is an educational defect, not privileged service code.

## 4. Mechanism and simpler alternative
ReferenceProxy.read(Capability,now); returned bytes are hash-checked at use.

Simpler alternative: one guarded read function. Responsibilities and associations are visible in the actual implementation. No inherited scanner/provider authority is copied.

## 6. Worked inputs
Choose nominal or edge. Declared bounds are enforced by contracts.py. Both choices recompute a positive result and an independent negative predicate. The JSON output exposes the exact input and output.

## 8. Behavior under pressure
Failure hypothesis: stale or wrong-audience capability. A True negative_detected predicate means the forbidden behavior was rejected or the defective fixture differed from the lawful oracle. Tests include boundary and exception/replay pressure as applicable.

## 9. Applicability gate
Guard each artifact read with explicit identity, audience, scope, epoch, time, and bytes. Use direct immutable reads when there is no separate authority boundary.

The one guarded read function comparison avoids carrying a hierarchy when a plain function or immutable table satisfies the same contract.

## 10. Reproducibility and non-claims
From repository root: `uv run --frozen pytest -q patterns/structural/proxy/tests`. Run `uv run --frozen marimo run patterns/structural/proxy/notebook.py`. Python/marimo versions are frozen in uv.lock. Evidence is source-bound in evidence/qualification.json; digests in manifest.json. Native script/export is separate from local Hub/browser qualification. No physics, hostile-host isolation, distributed exactly-once, production identity, or human promotion claim.

## Implementation API
ReferenceProxy.read(Capability,now); returned bytes are hash-checked at use.

## Policy and provenance
Current released HMT-AXIOMS/2.0.0, HMT-TESTING-CONTINUOUS-ADMISSION/1.0.0, HMT-RRCA-POLICY/4.0.0, and reuse/bounded-transformation policies apply. Full exact bindings: policy/policy_bindings.json. Reuse disposition: ADAPT or NO_FIT for inherited code; all new leaf code has its own source identity. The field cards supply teaching cadence, not executable bulk.

## Stable witnesses
RDP-S03-EX-001; RDP-S03-INV-001; RDP-S03-T-001; negative and edge tests in tests/. Read contracts.py, reference.py, example.py, then notebook.py.
