"""RDP-B07-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("chain-of-responsibility", "reference")
c = load("chain-of-responsibility", "contracts")
e = load("chain-of-responsibility", "example")


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
    value = c.Context(
        authenticated=True, current_policy=True, evidence_intact=True, receipt_bound=True
    )
    assert r.GuardChain().check(value).disposition == "READ_ADMITTED"
    for field in ("authenticated", "current_policy", "evidence_intact", "receipt_bound"):
        result = r.GuardChain().check(value.model_copy(update={field: False}))
        assert result.disposition == "DENY" and result.consequential_effects == 0
    with pytest.raises(ValueError):
        r.GuardChain(("auth", "evidence", "policy", "receipt"))


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
