# OODA pattern exporter

Pick retry profiles in TOML. Export a verified starter ZIP. Each bundle contains the selected policy, its enforcing runtime, a witness, the original example files, and a hash manifest.

## Export a build

Use Python 3.11 or later in a virtual environment. Install the pinned dependency once.

```sh
python -m pip install -r requirements.lock
python bundle_exporter.py export selections/ooda-starter.toml ooda-starter.zip
python bundle_exporter.py verify ooda-starter.zip --sha256 ARCHIVE_SHA256_FROM_RECEIPT
```

The exporter prints the receipt as JSON. Save it beside the ZIP or in an independent release record. Export to a fresh path on a filesystem that supports hard links. The ZIP becomes visible only after qualification and readback pass.

Unpack at the target directory. The README, policy, runtime, witness, and manifest sit at the root. Reference paths stay intact. Install the same lock in the target environment and run python witness.py.

## Pick profiles

| Kind | Behavior |
| --- | --- |
| basic | Fixed backoff, bounded attempts, and connection-error retry. |
| filtering | Retry on a missing result or a connection error. TOML selects one trigger. |
| logging | Retry the example’s ValueError contract and emit a scheduled-retry notice. |
| async | Bounded async retry for connection failures. |
| waiting | Choose fixed, random, or capped exponential backoff. |
| ooda | Admit attempts against a strict monotonic window with a fallback reserve. |

The starter selects OODA and basic retry. The [full selection](selections/all-configurations.toml) exercises all six families, both filter modes, and all three wait strategies. Profile names are local to a bundle. The runtime accepts only the fields it enforces.

## Follow the policy

1. Edit the selection first. Pick the behavior, attempt limit, timing, and strategy you need.
2. Export and read the admission result. A profile with an unknown kind, invalid bounds, or missing binding produces no ZIP.
3. Add runtime behavior when a new declaration needs it. Rerun the same selection and its witness. Keep the original source as reference evidence.
4. Verify the archive against the receipt. Unpack it and replay the witness before use.

The [catalog](catalog.toml) pins the supplied archive, its manifest, the selected source paths, and the Tenacity version. The exporter reads the source files as data. It executes the checked-in witness against the staged runtime and policy. The manifest records the Python and Tenacity versions used for that witness. Exports from the same input and witness toolchain produce the same bytes.

The witness qualifies retry, wait, and deadline behavior with local callbacks. Production use needs qualified timing bounds and a host that owns replay authorization and effect reconciliation. The original package’s simulated and live test reports remain historical source evidence.
