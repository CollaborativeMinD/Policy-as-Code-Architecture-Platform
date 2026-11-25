"""CDC typed admission and cleanup edge boundaries."""

import asyncio
from dataclasses import replace

import pytest

from hmt_pg_patterns.streaming import stream_chunks
from hmt_pg_patterns.streaming_contracts import StreamError, StreamLimits, StreamStats
from streaming_samples import Source, TINY


@pytest.mark.parametrize(
    "limits",
    [
        None,
        {},
        StreamLimits(False, 1),
        StreamLimits(float("nan"), 1),
        StreamLimits(-1, 1),
        StreamLimits(1, 0),
    ],
)
async def test_deadline_types_and_limits_fail_before_source_consumption(limits):
    source = Source()
    if limits is None:
        assert (await stream_chunks(source, lambda _: None)).terminal == "COMPLETED"
    else:
        with pytest.raises(StreamError):
            await stream_chunks(source, lambda _: None, limits=limits)
        assert source.reads == 0


@pytest.mark.parametrize("value", ["text", 1, None])
async def test_invalid_packet_types(value):
    with pytest.raises(StreamError, match="INVALID_PACKET"):
        await stream_chunks(Source([value]), lambda _: None, policy=TINY)


async def test_packet_and_total_capacity_and_released_view():
    view = memoryview(b"a")
    view.release()
    cases = [
        ([view], TINY, "INVALID_PACKET"),
        ([b"12345"], replace(TINY, max_packet_bytes=4), "PACKET_CAPACITY"),
        ([b"abcd", b"e"], replace(TINY, max_total_bytes=4), "STREAM_CAPACITY"),
    ]
    for packets, policy, code in cases:
        with pytest.raises(StreamError, match=code):
            await stream_chunks(Source(packets), lambda _: None, policy=policy)


async def test_invalid_source_sink_and_reused_stats():
    for source, sink, stats, code in [
        (1, lambda _: None, None, "INVALID_SOURCE"),
        (Source(), None, None, "INVALID_SINK"),
        (Source(), lambda _: None, {}, "INVALID_STATS"),
        (Source(), lambda _: None, StreamStats(terminal="COMPLETED"), "INVALID_STATS"),
    ]:
        with pytest.raises(StreamError, match=code):
            await stream_chunks(source, sink, stats=stats)


async def test_source_without_close_is_supported():
    class Bare:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    assert (await stream_chunks(Bare(), lambda _: None)).terminal == "COMPLETED"


async def test_cleanup_and_sink_cancellation_are_visible():
    stats = StreamStats()
    with pytest.raises(asyncio.CancelledError):
        await stream_chunks(Source(cleanup=asyncio.CancelledError()), lambda _: None, stats=stats)
    assert stats.cleanup_code == "CLEANUP_CANCELLED"
    source = Source([b"abc"])

    async def sink(_):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await stream_chunks(source, sink, policy=TINY)
    assert source.closed
