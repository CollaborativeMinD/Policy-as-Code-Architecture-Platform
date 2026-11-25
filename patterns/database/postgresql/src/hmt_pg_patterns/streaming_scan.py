"""Derived from governance_cdc.py; same polynomial and continuous window."""

from collections import deque

from .streaming_contracts import Chunk, Policy, StreamError

PRIME = (1 << 61) - 1


class Scanner:
    """Single-owner scanner. Fully exhaust each feed; early close aborts it."""

    def __init__(self, policy: Policy | None = None):
        self.policy = Policy() if policy is None else policy
        if type(self.policy) is not Policy:
            raise StreamError("INVALID_POLICY")
        p = self.policy
        removal = pow(256, p.window_size, PRIME)
        self._remove = tuple(byte * removal % PRIME for byte in range(256))
        self._mask = (
            p.block_size_target - 1
            if p.block_size_target & (p.block_size_target - 1) == 0
            else None
        )
        self._window: deque[int] = deque()
        self._buffer = bytearray()
        self._fingerprint = self._offset = self._start = self._index = 0
        self._active = False
        self._state = "OPEN"
        self.buffer_peak = self.window_peak = 0

    @property
    def state(self):
        """Expose the scanner lifecycle without granting mutation rights."""
        return self._state

    @property
    def offset(self):
        """Return the total number of accepted source bytes."""
        return self._offset

    def _available(self):
        if self._active:
            raise StreamError("FEED_ACTIVE")
        if self._state != "OPEN":
            raise StreamError("SCANNER_" + self._state)

    def feed(self, data):
        """Snapshot one bounded packet and return a single-owner chunk iterator."""
        self._available()
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise StreamError("INVALID_PACKET")
        try:
            view = memoryview(data)
        except ValueError as exc:
            raise StreamError("INVALID_PACKET") from exc
        if view.nbytes > self.policy.max_packet_bytes:
            raise StreamError("PACKET_CAPACITY")
        if self._offset + view.nbytes > self.policy.max_total_bytes:
            raise StreamError("STREAM_CAPACITY")
        # Own an immutable, bounded snapshot even while the iterator is suspended.
        return self._scan(bytes(view))

    def _cut(self, reason):
        value = Chunk(
            self._index, self._start, self._offset, bytes(self._buffer), self._fingerprint, reason
        )
        self._buffer.clear()
        self._start = self._offset
        self._index += 1
        return value

    def _scan(self, data):
        self._available()
        if self._offset + len(data) > self.policy.max_total_bytes:
            raise StreamError("STREAM_CAPACITY")
        self._active = True
        exhausted = False
        p = self.policy
        try:
            for byte in data:
                # POLY-01: H' = (256*H + incoming - outgoing*256**W) mod P.
                old = (
                    self._remove[self._window.popleft()]
                    if len(self._window) == p.window_size
                    else 0
                )
                self._fingerprint = ((self._fingerprint << 8) + byte - old) % PRIME
                self._window.append(byte)
                self._buffer.append(byte)
                self._offset += 1
                self.buffer_peak = max(self.buffer_peak, len(self._buffer))
                self.window_peak = max(self.window_peak, len(self._window))
                remainder = (
                    self._fingerprint & self._mask
                    if self._mask is not None
                    else self._fingerprint % p.block_size_target
                )
                if len(self._buffer) >= p.min_size and (
                    remainder == p.target or len(self._buffer) >= p.max_size
                ):
                    yield self._cut("content" if remainder == p.target else "max size")
            exhausted = True
        finally:
            self._active = False
            if not exhausted:
                self.abort()

    def finish(self):
        """Emit the final nonempty tail once and close the scanner lifecycle."""
        if self._state == "FINISHED":
            return []
        self._available()
        self._state = "FINISHED"
        return [self._cut("tail")] if self._buffer else []

    def abort(self):
        """Discard retained source bytes after the active feed has relinquished ownership."""
        if self._active:
            raise StreamError("FEED_ACTIVE")
        self._state = "ABORTED"
        self._buffer.clear()
        self._window.clear()
