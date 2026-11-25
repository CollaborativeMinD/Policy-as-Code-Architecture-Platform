"""RDP-S03-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("proxy", "reference")
c = load("proxy", "contracts")
e = load("proxy", "example")


@pytest.mark.unit
@pytest.mark.parametrize("case", ["nominal", "edge"])
def test_computed_example(case):
    actual = e.run_example(case)
    assert actual["positive_check"] is True
    assert actual["inputs"]


@pytest.mark.negative
@pytest.mark.mutation
def test_forbidden_witness():
    assert e.run_example("edge")["negative_detected"] is True


@pytest.mark.behavioral
@pytest.mark.integration
def test_lifecycle_and_forbidden_states(tmp_path):
    import hashlib

    raw = b"reference"
    cap = c.Capability(
        subject="reviewer",
        audience="pattern-reference",
        scope="read",
        resource="reference.py",
        policy_epoch=1,
        expires_at=20,
        source_digest=hashlib.sha256(raw).hexdigest(),
    )
    assert r.ReferenceProxy(lambda: raw).read(cap, 1) == raw
    for now in (-1, 20):
        with pytest.raises(ValueError):
            r.ReferenceProxy(lambda: raw).read(cap, now)
    with pytest.raises(ValueError):
        r.ReferenceProxy(lambda: b"drift").read(cap, 1)
    with pytest.raises(ValueError):
        r.ReferenceProxy(lambda: b"x" * 4097).read(cap, 1)


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
