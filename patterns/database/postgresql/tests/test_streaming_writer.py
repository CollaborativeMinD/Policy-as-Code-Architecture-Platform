"""PostgreSQL CDC storage, immutable snapshots, and deterministic origin replay."""

import asyncio
from uuid import uuid4

import psycopg
import pytest
from pydantic import ValidationError
from pyrsistent import PMap

from authority_samples import counts, register, request
from hmt_pg_patterns.authority_async import AsyncAuthority
from hmt_pg_patterns.streaming_async_writer import AsyncStreamWriter
from hmt_pg_patterns.streaming_contracts import Policy, StreamError
from hmt_pg_patterns.streaming_writer import StreamWriter
from streaming_samples import Source, TINY


def test_sync_storage_replay_and_immutable_tip(pg_conn):
    authority = register(pg_conn)
    data, stream_id = bytes(range(90)), uuid4()
    writer = StreamWriter(authority, stream_id, 1, TINY)
    tip = writer.write([data[:11], data[11:]])
    assert isinstance(tip, PMap) and tip["end"] == len(data)
    rows = pg_conn.execute("SELECT payload FROM hmt_pg.chunk_effect ORDER BY sequence").fetchall()
    assert b"".join(row[0] for row in rows) == data
    before = counts(pg_conn)
    replay = StreamWriter(authority, stream_id, 1, TINY).write([data])
    assert replay == tip and counts(pg_conn) == before
    assert tip.set("end", 0)["end"] == 0 and tip["end"] == len(data)
    with pytest.raises(StreamError, match="WRITER_ALREADY_STARTED"):
        writer.write([data])


def test_source_failure_owns_cleanup_and_origin_replay(pg_conn):
    authority, stream_id = register(pg_conn), uuid4()
    cleaned = []

    def source():
        try:
            yield b"abcdefghi"
            raise OSError("synthetic source fault")
        finally:
            cleaned.append(True)

    writer = StreamWriter(authority, stream_id, 1, TINY)
    with pytest.raises(OSError, match="synthetic"):
        writer.write(source())
    assert cleaned == [True] and counts(pg_conn)[0] > 0
    tip = StreamWriter(authority, stream_id, 1, TINY).write([b"abcdefghi"])
    assert tip["end"] == 9


def test_writer_empty_cap_and_strict_epoch(pg_conn):
    authority = register(pg_conn)
    assert StreamWriter(authority, uuid4(), 1, TINY).write([]) is None
    cap = Policy(3, 2, 2, 5, max_packets=2)
    with pytest.raises(StreamError, match="PACKET_COUNT_CAPACITY"):
        StreamWriter(authority, uuid4(), 1, cap).write([b"", b"", b""])
    with pytest.raises(ValidationError):
        StreamWriter(authority, uuid4(), True, TINY)
    forged = request().model_copy(update={"epoch": True})
    with pytest.raises(ValidationError):
        authority.admit(forged)


def test_async_authority_and_writer(pg_conn, pg_dsn):
    register(pg_conn)
    stream_id, data = uuid4(), bytes(range(60))

    async def exercise():
        async with await psycopg.AsyncConnection.connect(
            pg_dsn, autocommit=True, prepare_threshold=None
        ) as connection:
            authority = AsyncAuthority(connection)
            assert (await authority.identity()).epoch == 1
            assert await authority.checkpoint(stream_id) is None
            writer = AsyncStreamWriter(authority, stream_id, 1, TINY)
            source = Source([data[:17], data[17:]])
            tip = await writer.write(source)
            assert tip["end"] == len(data) and source.closed == 1
            assert (await authority.checkpoint(stream_id)).digest == tip["digest"]
            replay = await AsyncStreamWriter(authority, stream_id, 1, TINY).write(Source([data]))
            assert replay == tip
            with pytest.raises(StreamError, match="WRITER_ALREADY_STARTED"):
                await writer.write(Source([]))
            with pytest.raises(ValidationError):
                await authority.admit(request().model_copy(update={"epoch": True}))
            separate = request()
            assert (await authority.admit(separate.model_dump())).replayed is False

    asyncio.run(exercise())


def test_async_caller_rollback_owns_commit(pg_conn, pg_dsn):
    register(pg_conn)

    async def exercise():
        async with await psycopg.AsyncConnection.connect(
            pg_dsn, autocommit=True, prepare_threshold=None
        ) as connection:
            with pytest.raises(RuntimeError, match="abort"):
                async with connection.transaction():
                    await AsyncAuthority(connection).admit(request())
                    raise RuntimeError("abort")

    asyncio.run(exercise())
    assert counts(pg_conn) == (0, 0, 0)
