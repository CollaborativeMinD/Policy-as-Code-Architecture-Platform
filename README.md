# Policy-as-Code Architecture Platform

Build from qualified design patterns. Select a pattern in TOML, verify its behavior, and export a flat ZIP with a receipt.

**Behavioral → Creational → Structural → Database → Resilience OODA → Verify → Package and ship**

All 33 registered bindings passed verification in the release scope. The default campaign covers all five branches with zero unresolved holds.

| Branch | Bindings | What you select |
| --- | ---: | --- |
| Behavioral | 7 | Execution and coordination strategies |
| Creational | 3 | Construction and lifecycle mechanisms |
| Structural | 5 | Composition and interface patterns |
| Database | 17 | PostgreSQL persistence and transaction patterns |
| Resilience OODA | 1 | Recovery, retry, and continuity profiles |

Verification covers each binding and its declared effect. PostgreSQL uses software fixtures. Each default ships as its own archive. The original source and evidence stay pinned. [Continuity policy](patterns/DESIGN_PATTERNS.md) · [Registry](registry.toml)

## Select and export

Use Python 3.13 in a virtual environment to run all five branches. The hash-locked requirements include the Tenacity version used by OODA.

```sh
python -m pip install -r bindings/requirements.lock
python factory.py audit
python factory.py plan selections/postgres-transaction.toml
python factory.py export selections/postgres-transaction.toml postgres-transaction.zip > postgres-transaction.receipt.json
python factory.py verify postgres-transaction.zip --receipt postgres-transaction.receipt.json
```

To make a variation, copy a policy from `bindings/` and point a new selection at it. The binding requires every declared setting. An extra key, invalid type, or unsupported choice blocks the build. The witness records the observed result and denial in the archive manifest. [Default policies](bindings/)

The OODA starter chooses two profiles. The full selection chooses nine from the same retry implementation. [OODA starter](selections/ooda-starter.toml) · [Full OODA selection](selections/ooda-all.toml)

## Change the factory

1. **Declare.** Set the pattern, version, and settings in TOML. State the expected effect and denial.
2. **Run admission.** Let the candidate expose a missing model, binding, or guard.
3. **Implement the missing piece.** Bind it to the declared contract and rerun the same candidate.
4. **Verify.** Check the effect and denial. Run `python qualify_bindings.py ./qualified-bindings` for the default campaign.
5. **Package and ship.** Verify each ZIP against its receipt. For a repository release, wait for local Forgejo to admit the exact commit before pushing to GitHub.

Keep the TOML selection, ZIP, and receipt together. Use the campaign report to trace each archive to its configuration and source. [Runbook](Runbook.md) · [Agent instructions](AGENTS.md) · [Factory skill](SKILL.md)

## Live operator console

Use the [console guide](Console.md) to observe inventory, publish scoped TOML changes, run admitted tasks and verify their receipts.

## From policy change to release

Start with [registry.toml](registry.toml) for this component and [console.toml](console.toml) for terminal access. Write down the requested effect and one case that must be denied. Change the TOML first.

1. Apply the candidate to disposable state. An unknown field or unbound operation must fail admission before an effect. Keep that denial.
2. For supported behavior, continue with the existing runtime. For new behavior, implement the missing typed field and the method that enforces it. Run the same candidate again.
3. Run `python qualify_bindings.py qualified-bindings` in the project environment. Exercise the normal entry point and the denial. Review the qualified selection ZIP and matching receipt. Reconcile discrepancies and repeat.
4. Qualify the exact commit on local Forgejo. Review the package, image, security scan and receipt for each release target. Ship the reviewed artifacts and record their digests.
