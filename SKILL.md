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
