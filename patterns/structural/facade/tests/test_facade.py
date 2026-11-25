"""RDP-S02-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("facade", "reference")
c = load("facade", "contracts")
e = load("facade", "example")


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
    def good():
        return c.Reading(subsystem="catalog", count=2)

    def failure():
        raise TimeoutError("offline")

    report = r.AuditFacade(good, failure).inspect()
    assert (
        report.status == "HOLD" and report.consequential_effects == 0 and len(report.readings) == 1
    )
    assert r.AuditFacade(good, good).inspect().reason == "HOLD_PORT_IDENTITY"


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
