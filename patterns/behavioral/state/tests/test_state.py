"""RDP-B03-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("state", "reference")
c = load("state", "contracts")
e = load("state", "example")


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
    def tick(state, **updates):
        return c.Tick(
            state=state,
            soft_failures=(),
            recovery_streak=0,
            pressure=False,
            hard_terminal=False,
            emergency=False,
            history_epoch=1,
        ).model_copy(update=updates)

    assert r.transition(tick(c.State.TERMINAL)).state == c.State.TERMINAL
    assert r.transition(tick(c.State.PRIMARY, hard_terminal=True)).state == c.State.TERMINAL
    assert r.transition(tick(c.State.PRIMARY, emergency=True)).state == c.State.EMERGENCY
    assert (
        r.transition(tick(c.State.PRIMARY, pressure=True, soft_failures=(True,))).state
        == c.State.ALTERNATE
    )
    assert r.transition(tick(c.State.ALTERNATE, recovery_streak=4)).state == c.State.PRIMARY
    assert r.transition(tick(c.State.PRIMARY)).state == c.State.PRIMARY
    with pytest.raises(ValueError):
        c.Tick.model_validate_json(
            tick(c.State.PRIMARY)
            .model_dump_json()
            .replace('"history_epoch":1', '"history_epoch":2')
        )


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
