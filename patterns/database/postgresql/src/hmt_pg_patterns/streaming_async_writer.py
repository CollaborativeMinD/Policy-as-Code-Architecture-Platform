"""Async PostgreSQL CDC composition with zero queued chunks and cooperative cancellation."""

from .streaming import stream_chunks
from .streaming_contracts import StreamError
from .streaming_state import WriterState


class AsyncStreamWriter(WriterState):
    """Await each database admission before consuming another emitted chunk."""

    async def write(self, packets, limits=None):
        """Own one async source and return the immutable last admitted checkpoint."""
        if self._started:
            raise StreamError("WRITER_ALREADY_STARTED")
        self._started = True
        identity = await self.authority.identity()

        async def store(chunk):
            result = await self.authority.admit(self.request(chunk))
            self.accept(result, identity.db_role)

        await stream_chunks(packets, store, policy=self.policy, limits=limits)
        return self.snapshot
