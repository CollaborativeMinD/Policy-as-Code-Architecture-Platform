"""Byte-stream reconstruction and source bounds exercised through PostgreSQL effects."""

from uuid import uuid4
import pytest

from authority_samples import counts, register
from crossjoin_unit_stream import PAYLOAD, chunk_policy
from hmt_pg_patterns.streaming_contracts import StreamError
from hmt_pg_patterns.streaming_writer import StreamWriter


def reconstruct(connection, stream_id):
    rows = connection.execute(
        "SELECT payload FROM hmt_pg.chunk_effect "
        "WHERE db_role=session_user AND stream_id=%s ORDER BY sequence",
        (stream_id,),
    ).fetchall()
    return b"".join(row[0] for row in rows)


def packet_invariance(live):
    authority = register(live.conn)
    stream_id = uuid4()
    policy = chunk_policy()
    first = StreamWriter(authority, stream_id, 1, policy).write([PAYLOAD])
    original_counts = counts(live.conn)
    second = StreamWriter(authority, stream_id, 1, policy).write(
        [PAYLOAD[index : index + 7] for index in range(0, len(PAYLOAD), 7)]
    )
    assert first == second and counts(live.conn) == original_counts
    assert reconstruct(live.conn, stream_id) == PAYLOAD
    return "packetization_independent_origin_replay"


class ClosingSource:
    def __init__(self):
        self.closed = False
        self.remaining = 1

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining == 0:
            raise StopIteration
        self.remaining -= 1
        return b"x" * 17

    def close(self):
        self.closed = True


def stream_limits(live):
    authority = register(live.conn)
    source = ClosingSource()
    writer = StreamWriter(authority, uuid4(), 1, chunk_policy(max_total_bytes=16))
    with pytest.raises(StreamError, match="STREAM_CAPACITY"):
        writer.write(source)
    assert source.closed and counts(live.conn) == (0, 0, 0)
    return "bounded_source_closed_without_effect"
