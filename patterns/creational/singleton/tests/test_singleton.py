"""RDP-C01-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("singleton", "reference")
c = load("singleton", "contracts")
e = load("singleton", "example")


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
    scope = r.ScopedSingleton()
    first = c.Config(tenant="a", limit=1)
    assert scope.get(first) is scope.get(c.Config(tenant="a", limit=1))
    with pytest.raises(ValueError, match="DRIFT"):
        scope.get(c.Config(tenant="a", limit=2))
    for tenant in ("b", "c", "d"):
        scope.get(c.Config(tenant=tenant, limit=1))
    with pytest.raises(ValueError, match="CAPACITY"):
        scope.get(c.Config(tenant="e", limit=1))
    scope.close()
    with pytest.raises(ValueError, match="CLOSED"):
        scope.get(first)


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
