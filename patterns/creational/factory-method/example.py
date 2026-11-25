"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from pydantic import ValidationError
from .contracts import Request
from .reference import create


def run_example(case: str = "nominal") -> dict[str, object]:
    provider = "echo" if case == "nominal" else "uppercase"
    value = create(Request(provider=provider, text="bounded"))
    try:
        Request(provider="cloud-admin", text="bounded")
    except ValidationError:
        denied = True
    return {
        "inputs": {"provider": provider},
        "computed": value.model_dump(),
        "positive_check": value.text == ("bounded" if provider == "echo" else "BOUNDED"),
        "negative_detected": denied,
        "negative_hypothesis": "Unrestricted dynamic imports can instantiate privileged providers.",
    }
