"""Blocking PostgreSQL CDC writer with finite source iteration and owned cleanup."""

from .streaming_contracts import StreamError
from .streaming_scan import Scanner
from .streaming_state import WriterState


class StreamWriter(WriterState):
    """One stream per instance; failure requires a fresh writer and origin replay."""

    def _store_chunks(self, chunks, db_role):
        try:
            for chunk in chunks:
                self.accept(self.authority.admit(self.request(chunk)), db_role)
        finally:
            close = getattr(chunks, "close", None)
            if close is not None:
                close()

    def write(self, packets):
        """Consume a finite source once; origin replay uses a fresh writer instance."""
        if self._started:
            raise StreamError("WRITER_ALREADY_STARTED")
        self._started = True
        identity = self.authority.identity()
        scanner, source = Scanner(self.policy), iter(packets)
        try:
            for packet_index in range(self.policy.max_packets + 1):
                try:
                    packet = next(source)
                except StopIteration:
                    break
                if packet_index == self.policy.max_packets:
                    raise StreamError("PACKET_COUNT_CAPACITY")
                self._store_chunks(scanner.feed(packet), identity.db_role)
            self._store_chunks(scanner.finish(), identity.db_role)
        finally:
            scanner.abort()
            close = getattr(source, "close", None)
            if close is not None:
                close()
        return self.snapshot
