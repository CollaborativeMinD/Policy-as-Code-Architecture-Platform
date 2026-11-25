"""RDP-B05-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("template-method", "reference")
c = load("template-method", "contracts")
e = load("template-method", "example")


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
    request = c.Request(text="alpha")
    assert r.UppercasePipeline().run(request).value == "ALPHA"
    with pytest.raises(TypeError):
        type("SkippedValidation", (r.Pipeline,), {"run": lambda self, value: value})
    with pytest.raises(ValueError):
        c.Request(text="")


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
