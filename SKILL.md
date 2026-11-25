---
name: pattern-registry-factory
description: Select, bind, verify, or export patterns from the Policy-as-Code Architecture Platform. Use for TOML policy changes, admission failures, and qualification of a pattern or release.
---

# Build from pattern policy

Start from the 33 verified bindings. The release scope has zero unresolved holds. Follow Behavioral, Creational, Structural, Database, and Resilience OODA, then verify, package, and ship.

1. Copy the pinned TOML when testing a variation. Declare every setting, the intended effect, and the expected denial.
2. Run admission on the candidate before editing code. Use the failure to locate the missing model, binding, or guard.
3. Add the missing runtime piece. Rerun the same candidate and check the effect and denial. PostgreSQL evidence covers software fixtures.
4. Export the ZIP, verify its receipt, and replay its witness in a clean directory. Use `python qualify_bindings.py <new-directory>` to check all defaults after a shared binding or default contract change.
5. For an authorized repository release, confirm local Forgejo admitted the exact commit. Read back the artifact before publishing the commit.

Match the receipt to the selected policy, original evidence, observed effect, and ZIP. [Runbook](Runbook.md) · [Continuity policy](patterns/DESIGN_PATTERNS.md)

## Live operator console

Use the [console guide](Console.md) to observe inventory, publish scoped TOML changes, run admitted tasks and verify their receipts.

## From policy change to release

Start with [registry.toml](registry.toml) for this component and [console.toml](console.toml) for terminal access. Write down the requested effect and one case that must be denied. Change the TOML first.

1. Apply the candidate to disposable state. An unknown field or unbound operation must fail admission before an effect. Keep that denial.
2. For supported behavior, continue with the existing runtime. For new behavior, implement the missing typed field and the method that enforces it. Run the same candidate again.
3. Run `python qualify_bindings.py qualified-bindings` in the project environment. Exercise the normal entry point and the denial. Review the qualified selection ZIP and matching receipt. Reconcile discrepancies and repeat.
4. Qualify the exact commit on local Forgejo. Review the package, image, security scan and receipt for each release target. Ship the reviewed artifacts and record their digests.
