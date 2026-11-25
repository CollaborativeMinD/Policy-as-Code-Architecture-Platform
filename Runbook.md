# Architecture Platform runbook

The release covers 33 verified bindings with zero unresolved holds. Work through Behavioral, Creational, Structural, Database, and Resilience OODA. Verify the selected effects, then package and ship the admitted artifacts.

## 1. Decide what changes

| Intent | Change | Proof |
| --- | --- | --- |
| Pick another supported profile | Copy the TOML configuration and point a new selection to it. | The same implementation digest produces the new selected behavior. |
| Add a missing capability or setting | Declare it in TOML and run admission before editing code. | The original failure isolates a missing model, binding, or guard. |
| Request a new composition | Declare the selected patterns and the owner of the effect. | A witness exercises the interaction and checks that a denied request has no effect. |

## 2. Resolve and qualify

```sh
python -m pip install -r bindings/requirements.lock
python factory.py list
python factory.py audit
python factory.py plan selections/postgres-transaction.toml
```

The plan resolves the identity, version, source, and configuration. Audit checks the preserved files, adapter release, and default policy pins. The tests also submit a deliberately unqualified composition and require admission to block publication.

For a missing behavior, add the runtime part named by the failed case. Rerun admission and check the observed effect and required denial. When changing an adapter or default contract, update its SHA-256 digest in `bindings/release.json` and set `bindings_sha256` in `registry.toml` to the new release digest. Audit and qualify the candidate before release. A custom selection and configuration have their own receipt digests, so testing a variation needs no re-pin.

PostgreSQL verification uses software fixtures. The imported archive lists one generated metadata path that differs from its supplied path. The supplied bytes match the original checksum. [Continuity policy](patterns/DESIGN_PATTERNS.md)

## 3. Export and carry the evidence

```sh
python factory.py export selections/postgres-transaction.toml postgres-transaction.zip > postgres-transaction.receipt.json
python factory.py verify postgres-transaction.zip --receipt postgres-transaction.receipt.json
python qualify_bindings.py ./qualified-bindings
```

Use a fresh destination on a filesystem with hard-link support. The factory publishes each ZIP after its witness and archive readback pass. Keep the receipt as a separate record. It binds the selection, continuity policy, registry, configuration, original source evidence, and ZIP. The full campaign publishes its directory after every default passes.

On the receiving system, unpack into an empty directory and follow the bundled README. Install its locked dependencies and run its witness there. Check the expected effect against the selected policy. Stop when the evidence agrees.

## 4. Admit and publish a repository release

1. Push the candidate commit to the private local Forgejo repository. The workflow installs the hash-locked dependencies, runs the tests, and builds and verifies all 33 default ZIPs on the repository runner.
2. Check the successful run for the exact candidate commit. Read back the published campaign artifact. It contains the tested revision, selections, receipts, and ZIPs.
3. Push the same commit to GitHub and verify the remote ref. Keep the local run and artifact as the admission record.

To reproduce the gate in a local Python 3.13 environment, install the lock and run `python -m pip check`, `python -m unittest -v`, and `python qualify_bindings.py ./qualified-bindings` with a fresh destination. [Forgejo workflow](.forgejo/workflows/qualification.yml)
