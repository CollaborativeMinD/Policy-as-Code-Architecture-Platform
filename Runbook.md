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

## Live operator console

Use the [console guide](Console.md) to observe inventory, publish scoped TOML changes, run admitted tasks and verify their receipts.

## From policy change to release

Start with [registry.toml](registry.toml) for this component and [console.toml](console.toml) for terminal access. Write down the requested effect and one case that must be denied. Change the TOML first.

1. Apply the candidate to disposable state. An unknown field or unbound operation must fail admission before an effect. Keep that denial.
2. For supported behavior, continue with the existing runtime. For new behavior, implement the missing typed field and the method that enforces it. Run the same candidate again.
3. Run `python qualify_bindings.py qualified-bindings` in the project environment. Exercise the normal entry point and the denial. Review the qualified selection ZIP and matching receipt. Reconcile discrepancies and repeat.
4. Qualify the exact commit on local Forgejo. Review the package, image, security scan and receipt for each release target. Ship the reviewed artifacts and record their digests.

The version 2 `[runtime]` table in `console.toml` sets request size, concurrency and client deadlines. Version 1 files inherit the shipped budget. Reissue them as version 2 to pin these choices in the admitted document.

Set the native witness deadline in [qualification_policy.toml](qualification_policy.toml). It applies to software bindings and OODA subprocesses.

## Build and ship this revision

Review [release/policy.toml](release/policy.toml) and the hash-locked dependency closure. Local Forgejo builds the Linux wheel, source distribution and exact-source ZIP. On the trusted Windows workstation set `PAC_CHECKOUT` to the clean checkout, `PAC_OUTPUT` to a fresh release directory, `PAC_BUILD_PYTHON` to a Python 3.13 environment with `release/build.lock`, and `PAC_SCANNER` to the pinned Trivy executable. Run this from the checkout.

```powershell
forgejo-runner exec --workflows release/workstation.yml --job workstation --image=-self-hosted --detect-event --env "PAC_CHECKOUT=$env:PAC_CHECKOUT" --env "PAC_OUTPUT=$env:PAC_OUTPUT" --env "PAC_BUILD_PYTHON=$env:PAC_BUILD_PYTHON" --env "PAC_SCANNER=$env:PAC_SCANNER"
```

The job builds and reinstalls the Windows wheel, checks the target machine and UID, exercises the native console effect in hardened Compose, scans the image, exports it and checks the restored image ID. For a package installation, install the release lock followed by the wheel with `--no-deps`. Use the command named by the release policy with `unpack NEW_DIRECTORY` to install the exact component tree. Follow its native runbook from there.

For a container installation, load the matching `.image.tar.gz` and use its accompanying `compose.json`. Provision the service's credential directory with `docker compose -f compose.json run --rm console credentials /state/credentials`. Apply the component's native setup before starting the console. The server binds loopback inside its own network namespace. Supply upstream files as read-only mounts and place a dependent local service or client in that same namespace. Review the policy digest, package hashes, image identity, scan report and effect before promoting the revision.
