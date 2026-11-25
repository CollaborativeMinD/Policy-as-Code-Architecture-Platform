"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

import hashlib
from .contracts import Capability
from .reference import ReferenceProxy


def run_example(case: str = "nominal") -> dict[str, object]:
    raw = b"source-v1" if case == "nominal" else b"source-v2"
    capability = Capability(
        subject="reviewer",
        audience="pattern-reference",
        scope="read",
        resource="reference.py",
        policy_epoch=1,
        expires_at=100,
        source_digest=hashlib.sha256(raw).hexdigest(),
    )
    value = ReferenceProxy(lambda: raw).read(capability, 1)
    try:
        ReferenceProxy(lambda: raw + b"drift").read(capability, 1)
    except ValueError as error:
        denied = str(error)
    return {
        "inputs": {"now": 1, "expires_at": 100},
        "computed": {"bytes": value.decode()},
        "positive_check": value == raw,
        "negative_detected": denied == "DENY_SOURCE_DRIFT",
        "negative_hypothesis": (
            "A prechecked pointer can change before returned bytes are verified."
        ),
    }
