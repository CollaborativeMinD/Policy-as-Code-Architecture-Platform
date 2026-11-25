"""Bounded projection drain and explicit readback reconciliation after publication."""

from .outbox import recover, reconcile, relay_checkpoint
from .pace import perform


def project(connection, cache, state, maximum: int) -> None:
    """Drain a finite budget; unresolved outcomes remain in PostgreSQL for recovery."""
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 514:
        raise ValueError("PROJECTION_BUDGET_INVALID")
    for _ in range(maximum):
        outcome = perform(state, "relay", lambda: relay_checkpoint(connection, cache))
        if outcome is None:
            break
    for _ in range((maximum + 99) // 100):
        events = recover(connection, min(maximum, 100))
        if not events:
            break
        for event in events:
            if reconcile(connection, cache, event) == "UNKNOWN":
                return
