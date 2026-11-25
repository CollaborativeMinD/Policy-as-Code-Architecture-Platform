"""RDP-S04-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("decorator", "reference")
c = load("decorator", "contracts")
e = load("decorator", "example")


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
    call = c.Call(authorized=True, semantic_label="READ", source_intact=True, stages=())
    assert r.read_reference(call).stages == ("scanner", "semantic", "watchdog", "target")
    for update in ({"authorized": False}, {"source_intact": False}, {"stages": ("scanner",)}):
        with pytest.raises(ValueError):
            r.read_reference(call.model_copy(update=update))
    with pytest.raises(ValueError):
        r.read_reference.__wrapped__.__wrapped__.__wrapped__(call)


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
