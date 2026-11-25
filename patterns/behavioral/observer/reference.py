"""RDP-B02 fault isolation and deduplication; no implicit retry after entry."""

from __future__ import annotations

from collections.abc import Callable
from .contracts import Delivery, Event


FOUR_LIMIT = 4
OUTPUT_MAX = 64
PAIR_LIMIT = 2


class Publisher:
    def __init__(self, subscribers: tuple[Callable[[Event], str], ...]) -> None:
        if not 1 <= len(subscribers) <= PAIR_LIMIT:
            raise ValueError("DENY_SUBSCRIBER_BOUND")
        self._subscribers = subscribers
        self._seen: dict[str, Event] = {}

    def publish(self, event: Event) -> Delivery:
        if not self.claim(event):
            return Delivery(status="DUPLICATE", outputs=(), failures=())
        outputs, failures = [], []
        for index, subscriber in enumerate(self._subscribers):
            try:
                output = subscriber(event)
                if not isinstance(output, str) or len(output) > OUTPUT_MAX:
                    raise RuntimeError("INVALID_SUBSCRIBER_RESULT")
                outputs.append(output)
            except (RuntimeError, TimeoutError):
                failures.append(index)
        return Delivery(status="DELIVERED", outputs=tuple(outputs), failures=tuple(failures))

    def claim(self, event: Event) -> bool:
        if event.event_id in self._seen:
            if self._seen[event.event_id] != event:
                raise ValueError("DENY_DUPLICATE_CONFLICT")
            return False
        if len(self._seen) >= FOUR_LIMIT:
            raise ValueError("DENY_BACKPRESSURE")
        if event.sequence != len(self._seen) + 1:
            raise ValueError("DENY_EVENT_ORDER")
        self._seen[event.event_id] = event
        return True
