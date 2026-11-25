"""Live worked and negative witnesses; bounded local fixture effects only."""

from __future__ import annotations

from .contracts import Event
from .reference import Publisher


def failed_subscriber(event: Event) -> str:
    raise RuntimeError("isolated subscriber failure")


def run_example(case: str = "nominal") -> dict[str, object]:
    event = Event(
        event_id="event-1", sequence=1, payload="nominal" if case == "nominal" else "edge"
    )
    bus = Publisher((lambda item: item.payload.upper(), failed_subscriber))
    delivered = bus.publish(event)
    duplicate = bus.publish(event)
    return {
        "inputs": event.model_dump(),
        "computed": delivered.model_dump(),
        "positive_check": delivered.outputs == (event.payload.upper(),)
        and delivered.failures == (1,),
        "negative_detected": duplicate.status == "DUPLICATE" and not duplicate.outputs,
        "negative_hypothesis": (
            "Retrying every subscriber duplicates successful deliveries after one failure."
        ),
    }
