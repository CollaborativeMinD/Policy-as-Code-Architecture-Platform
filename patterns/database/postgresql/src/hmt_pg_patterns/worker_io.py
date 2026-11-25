"""PG-PEER-001 and PG-CDC-001: finite ingress and a hard process deadline."""

import base64
import math
import os
import selectors
import threading
import time
from contextlib import contextmanager
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngressRequest(BaseModel):
    """Request data contains no peer identity, DSN, epoch, or chunking policy."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    stream_id: UUID
    payload_b64: str = Field(min_length=4, max_length=87384)

    def payload(self, maximum: int) -> bytes:
        """Reject noncanonical base64 and zero or oversized source bytes."""
        data = base64.b64decode(self.payload_b64, validate=True)
        if not 1 <= len(data) <= maximum or base64.b64encode(data).decode() != self.payload_b64:
            raise ValueError("INGRESS_PAYLOAD_CAPACITY_OR_ENCODING")
        return data


def read_frame(descriptor: int, maximum: int, deadline: float) -> bytes:
    """Read one bounded newline frame with an absolute monotonic deadline."""
    if type(maximum) is not int or not 1 <= maximum <= 131072:
        raise ValueError("INGRESS_FRAME_BOUND_INVALID")
    if isinstance(deadline, bool) or not math.isfinite(deadline):
        raise ValueError("INGRESS_DEADLINE_INVALID")
    data = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(descriptor, selectors.EVENT_READ)
        for _ in range(maximum + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise TimeoutError("INGRESS_DEADLINE")
            block = os.read(descriptor, min(4096, maximum + 1 - len(data)))
            if not block:
                raise ValueError("INGRESS_TRUNCATED")
            data.extend(block)
            if len(data) > maximum:
                raise ValueError("INGRESS_FRAME_CAPACITY")
            if b"\n" in data:
                frame, remainder = bytes(data).split(b"\n", 1)
                if remainder:
                    raise ValueError("ONE_REQUEST_PER_CONNECTION")
                return frame
    raise ValueError("INGRESS_FRAME_CAPACITY")


def _expired() -> None:
    # Exit124 itself means unknown; a full/closed diagnostic pipe must not prevent exit.
    os._exit(124)


@contextmanager
def process_deadline(seconds: float):
    """Bound even blocked native I/O; termination requires idempotent origin replay."""
    if isinstance(seconds, bool) or not math.isfinite(seconds) or not 0.1 <= seconds <= 30:
        raise ValueError("WORKER_DEADLINE_BOUND_INVALID")
    timer = threading.Timer(seconds, _expired)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
