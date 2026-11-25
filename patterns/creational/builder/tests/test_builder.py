"""RDP-C02-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load


PAIR_LIMIT = 2

r = load("builder", "reference")
c = load("builder", "contracts")
e = load("builder", "example")


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
    builder = r.Builder("owner")
    with pytest.raises(ValueError, match="INCOMPLETE"):
        builder.finish()
    complete = builder.with_limit(2)
    assert complete.finish().limit == PAIR_LIMIT and builder.limit is None
    with pytest.raises(ValueError, match="REPETITION"):
        complete.with_limit(3)
    with pytest.raises(ValueError):
        builder.with_limit(99)


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
