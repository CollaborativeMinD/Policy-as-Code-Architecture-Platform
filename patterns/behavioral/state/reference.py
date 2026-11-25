"""RDP-B03 software reflex lesson; full physical PACE law remains external."""

from __future__ import annotations

from .contracts import State, Tick, Transition


PAIR_LIMIT = 2
RECOVERY_WINDOW = 5

ORDER = (State.PRIMARY, State.ALTERNATE, State.CONTINGENCY, State.EMERGENCY)


def transition(tick: Tick) -> Transition:
    history = (*tick.soft_failures, tick.pressure)
    streak = 0 if tick.pressure else tick.recovery_streak + 1
    if tick.state == State.TERMINAL or tick.hard_terminal:
        return Transition(
            state=State.TERMINAL, soft_failures=(), recovery_streak=0, reason="TERMINAL_ABSORBING"
        )
    if tick.emergency:
        return Transition(
            state=State.EMERGENCY,
            soft_failures=history[-2:],
            recovery_streak=0,
            reason="HARD_EMERGENCY",
        )
    index = ORDER.index(tick.state)
    next_index, reason = advance(index, history, streak)
    return Transition(
        state=ORDER[next_index],
        soft_failures=history[-2:],
        recovery_streak=0 if next_index != index else min(streak, 4),
        reason=reason,
    )


def advance(index: int, history: tuple[bool, ...], streak: int) -> tuple[int, str]:
    if sum(history) >= PAIR_LIMIT:
        return min(index + 1, 3), "SOFT_DEGRADE_TWO_OF_THREE"
    if streak >= RECOVERY_WINDOW:
        return max(index - 1, 0), "RECOVER_FIVE_CLEAR"
    return index, "HYSTERESIS_HOLD"
