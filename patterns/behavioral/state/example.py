"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import State, Tick
from .reference import transition


def run_example(case: str = "nominal") -> dict[str, object]:
    state = State.PRIMARY if case == "nominal" else State.ALTERNATE
    tick = Tick(
        state=state,
        soft_failures=(True,),
        recovery_streak=0,
        pressure=True,
        hard_terminal=False,
        emergency=False,
        history_epoch=1,
    )
    value = transition(tick)
    terminal = tick.model_copy(
        update={
            "state": State.TERMINAL,
            "pressure": False,
            "soft_failures": (),
            "recovery_streak": 4,
        }
    )
    lawful = transition(terminal)
    defective = State.PRIMARY
    expected = State.ALTERNATE if state == State.PRIMARY else State.CONTINGENCY
    return {
        "inputs": tick.model_dump(mode="json"),
        "computed": value.model_dump(mode="json"),
        "positive_check": value.state == expected and lawful.state == State.TERMINAL,
        "negative_detected": defective != lawful.state,
        "negative_hypothesis": "A recovery fallback reopens an absorbing TERMINAL state.",
    }
