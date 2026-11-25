"""Same database admission contract through Psycopg native asyncio."""

from psycopg.types.json import Jsonb

from .authority_types import ChunkRequest, PeerIdentity, checkpoint as parse_checkpoint, receipt


class AsyncAuthority:
    """One owner per connection; outer transactions retain commit ownership."""

    def __init__(self, connection):
        self.connection = connection

    async def identity(self):
        """Read the current session-derived identity without blocking the event loop."""
        async with self.connection.transaction():
            cursor = await self.connection.execute("SELECT * FROM hmt_pg.own_identity()")
            row = await cursor.fetchone()
        return PeerIdentity.model_validate(dict(zip(PeerIdentity.model_fields, row, strict=True)))

    async def admit(self, request):
        """Revalidate and admit one effect in the caller-owned transaction context."""
        request = ChunkRequest.model_validate(
            request.model_dump() if isinstance(request, ChunkRequest) else request
        )
        async with self.connection.transaction():
            cursor = await self.connection.execute(
                "SELECT * FROM hmt_pg.admit_chunk(%s,%s)", (Jsonb(request.header()), request.data)
            )
            row = await cursor.fetchone()
        return receipt(row)

    async def checkpoint(self, stream_id):
        """Read this session's current durable tip after database authority admission."""
        async with self.connection.transaction():
            cursor = await self.connection.execute(
                "SELECT * FROM hmt_pg.read_checkpoint(%s)", (stream_id,)
            )
            row = await cursor.fetchone()
        return parse_checkpoint(row)
