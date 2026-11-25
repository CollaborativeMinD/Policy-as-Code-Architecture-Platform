"""RDP-B01-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("strategy", "reference")
c = load("strategy", "contracts")
e = load("strategy", "example")


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
    for costs, index in (((3, 1, 1), 1), ((0,), 0), ((1000, 999), 1)):
        left = r.select(c.Request(algorithm="scan", costs=costs))
        right = r.select(c.Request(algorithm="sort", costs=costs))
        assert left == right and left.index == index
    for costs in ((True,), (-1,), (1001,)):
        with pytest.raises(ValueError):
            r.select(c.Request(algorithm="scan", costs=costs))


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
