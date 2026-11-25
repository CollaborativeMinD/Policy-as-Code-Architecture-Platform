# Policy-bound pattern starter

Use Python 3.13 in an isolated virtual environment. Install the hash-locked dependencies and replay the binding.

```sh
python -m pip install -r requirements.lock
python -m policy_runtime.witness
```

The pattern and policy hash live in `binding.json`. The exact policy lives in `configuration.toml`. Fields outside the pattern contract fail admission. To change the policy, use the factory and issue a fresh archive.

The entry point uses software fixture ports. A PostgreSQL witness opens no native database, Redis, or Tailcat connection. The package carries the original code for the binding and scope evidence. The consuming application owns identity, credentials, service connections, and authorization for real effects.
