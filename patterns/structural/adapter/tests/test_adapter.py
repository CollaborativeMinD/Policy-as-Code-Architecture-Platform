"""RDP-S01-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("adapter", "reference")
c = load("adapter", "contracts")
e = load("adapter", "example")


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
    adapter = r.TemperatureAdapter()
    for value in (-273150, 0, 1000, 1000000):
        external = c.External(version="1", unit="mC", temperature=value)
        converted = adapter.convert(external)
        assert converted.temperature == value + 273150
        assert adapter.inverse(converted) == external
    with pytest.raises(ValueError):
        c.External(version=2, unit="K", temperature=0)


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
