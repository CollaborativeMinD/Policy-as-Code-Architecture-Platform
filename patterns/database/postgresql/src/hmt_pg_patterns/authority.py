"""PG-AUTH-01: PostgreSQL transaction owns authority, effect, checkpoint, and intent."""

from psycopg.types.json import Jsonb

from .authority_types import ChunkRequest, PeerIdentity, checkpoint as parse_checkpoint, receipt


class Authority:
    """Use a fixed authenticated LOGIN connection; outer transactions own final commit."""

    def __init__(self, connection):
        self.connection = connection

    def identity(self):
        """Read the current identity derived from the authenticated database session."""
        with self.connection.transaction():
            row = self.connection.execute("SELECT * FROM hmt_pg.own_identity()").fetchone()
        return PeerIdentity.model_validate(dict(zip(PeerIdentity.model_fields, row, strict=True)))

    def admit(self, request):
        """Revalidate the request and atomically admit its immutable effect."""
        request = ChunkRequest.model_validate(
            request.model_dump() if isinstance(request, ChunkRequest) else request
        )
        with self.connection.transaction():
            row = self.connection.execute(
                "SELECT * FROM hmt_pg.admit_chunk(%s,%s)", (Jsonb(request.header()), request.data)
            ).fetchone()
        return receipt(row)

    def checkpoint(self, stream_id):
        """Read the session-owned durable tip after current authority validation."""
        with self.connection.transaction():
            row = self.connection.execute(
                "SELECT * FROM hmt_pg.read_checkpoint(%s)", (stream_id,)
            ).fetchone()
        return parse_checkpoint(row)
