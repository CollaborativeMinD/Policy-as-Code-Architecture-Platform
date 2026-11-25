"""RDP-B02-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("observer", "reference")
c = load("observer", "contracts")
e = load("observer", "example")


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
    def failed(event):
        raise RuntimeError(event.payload)

    publisher = r.Publisher((lambda event: event.payload, failed))
    first = c.Event(event_id="e1", sequence=1, payload="one")
    result = publisher.publish(first)
    assert result.outputs == ("one",) and result.failures == (1,)
    assert publisher.publish(first).status == "DUPLICATE"
    with pytest.raises(ValueError):
        publisher.publish(first.model_copy(update={"payload": "conflict"}))
    with pytest.raises(ValueError):
        publisher.publish(c.Event(event_id="e3", sequence=3, payload="skip"))
    for index in range(2, 5):
        publisher.publish(c.Event(event_id=f"e{index}", sequence=index, payload="ok"))
    with pytest.raises(ValueError):
        publisher.publish(c.Event(event_id="full", sequence=4, payload="full"))
    with pytest.raises(ValueError):
        r.Publisher(())
    assert r.Publisher((lambda event: 99,)).publish(first).failures == (0,)


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
