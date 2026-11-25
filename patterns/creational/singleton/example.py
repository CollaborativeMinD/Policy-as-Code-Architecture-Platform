"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Config
from .reference import ScopedSingleton


def run_example(case: str = "nominal") -> dict[str, object]:
    limit = 2 if case == "nominal" else 8
    scope = ScopedSingleton()
    first = scope.get(Config(tenant="alpha", limit=limit))
    same = scope.get(Config(tenant="alpha", limit=limit))
    other = scope.get(Config(tenant="beta", limit=1))
    hidden_global = first
    leaked = hidden_global.tenant != other.tenant
    scope.close()
    try:
        scope.get(first)
    except ValueError as error:
        denied = str(error)
    return {
        "inputs": {"limit": limit},
        "computed": {
            "same_identity": first is same,
            "tenant_isolation": first is not other,
            "closed_scope": denied,
        },
        "positive_check": first is same and first is not other,
        "negative_detected": leaked,
        "negative_hypothesis": "A hidden process global leaks alpha config to beta.",
    }
