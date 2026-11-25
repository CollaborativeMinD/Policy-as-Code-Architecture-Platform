# Resilience starter

Install the locked dependency in a Python 3.11+ virtual environment. Run the witness from this directory.

```sh
python -m pip install -r requirements.lock
python witness.py
```

Edit selection.toml and run the witness again to qualify a new local configuration. A changed selection is a different build. Export it again when you need a fresh manifest and archive receipt.

```python
from pathlib import Path
from retry_runtime import RetryRuntime, load_policy

runtime = RetryRuntime(load_policy(Path("selection.toml")))
result = runtime.run("delivery", lambda: "ready")
```

Use a profile name declared in your selection. For an async profile, await runtime.run_async. The host owns the callable and must explicitly pass replay_safe=True to allow repeat calls. Connection failures qualify for retry in applicable profiles. The logging demonstration handles ValueError. The selected filtering trigger controls whether a missing result or a connection failure qualifies.

The OODA profile checks a monotonic deadline before dispatch and backoff and after an attempt returns. Its immutable receipt includes the policy digest, reason, attempt count, and timing. An optional deadline listener can tighten the window. The host owns cancellation, fallback, and reconciliation of effects.

manifest.json records the files and the checks that passed during export. The historical upstream evidence and exact selected examples live under reference/. The source archive manifest describes the full input archive. The export manifest lists what shipped in this starter.
