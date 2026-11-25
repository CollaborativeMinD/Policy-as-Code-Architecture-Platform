"""CDC async ownership, cleanup, deadlines, cancellation, and backpressure."""

import asyncio
from dataclasses import replace

import pytest

from hmt_pg_patterns.streaming import stream_chunks
from hmt_pg_patterns.streaming_contracts import StreamError, StreamLimits, StreamStats
from streaming_samples import Source, TINY


async def test_zero_queue_backpressure_and_complete_reconstruction():
    source = Source([bytes(range(20)), b"tail"])
    chunks = []

    async def sink(chunk):
        reads = source.reads
        await asyncio.sleep(0)
        assert source.reads == reads
        chunks.append(chunk)

    result = await stream_chunks(source, sink, policy=TINY)
    assert b"".join(c.data for c in chunks) == bytes(range(20)) + b"tail"
    assert result.terminal == "COMPLETED" and source.closed
    assert result.input_packets == 2 and result.delivered_bytes == 24
    assert result.buffer_peak <= 5 and result.window_peak <= 2


async def test_sync_sink_and_empty_packets_are_supported():
    chunks = []
    result = await stream_chunks(Source([b"", b"abc"]), chunks.append, policy=TINY)
    assert result.delivered_bytes == 3 and chunks


@pytest.mark.parametrize(
    "failure,code",
    [(ValueError("source"), "SOURCE_FAILURE"), (TimeoutError("source"), "SOURCE_FAILURE")],
)
async def test_source_failure_keeps_primary_code_and_closes(failure, code):
    source, stats = Source(failure=failure, cleanup=RuntimeError("cleanup")), StreamStats()
    with pytest.raises(StreamError, match=code):
        await stream_chunks(source, lambda _: None, policy=TINY, stats=stats)
    assert source.closed and stats.code == code and stats.cleanup_code == "CLEANUP_FAILURE"


async def test_sink_failure_is_not_retried():
    calls, source, stats = [], Source([b"abcdef"]), StreamStats()

    def sink(chunk):
        calls.append(chunk)
        raise RuntimeError("maybe externally applied")

    with pytest.raises(StreamError, match="SINK_FAILURE"):
        await stream_chunks(source, sink, policy=TINY, stats=stats)
    assert len(calls) == 1 and source.closed and stats.delivered_chunks == 0


async def test_deadline_and_source_cancellation_propagate():
    for failure in (None, asyncio.CancelledError()):
        source = Source(failure=failure, delay=0.05 if failure is None else 0)
        stats = StreamStats()
        error = StreamError if failure is None else asyncio.CancelledError
        with pytest.raises(error):
            await stream_chunks(
                source, lambda _: None, policy=TINY, limits=StreamLimits(0.01, 0.01), stats=stats
            )
        assert source.closed and stats.terminal in {"FAILED", "CANCELLED"}


@pytest.mark.parametrize(
    "cleanup,code", [(RuntimeError("close"), "CLEANUP_FAILURE"), ("slow", "CLEANUP_TIMEOUT")]
)
async def test_success_does_not_hide_cleanup_failure(cleanup, code):
    stats = StreamStats()
    with pytest.raises(StreamError, match=code):
        await stream_chunks(
            Source(cleanup=cleanup),
            lambda _: None,
            policy=TINY,
            limits=StreamLimits(1.0, 0.01),
            stats=stats,
        )
    assert stats.code == code and stats.terminal == "FAILED"


async def test_empty_packet_source_stops_at_finite_admission_count():
    source, stats = Source([b""] * 4), StreamStats()
    with pytest.raises(StreamError, match="PACKET_COUNT_CAPACITY"):
        await stream_chunks(
            source, lambda _: None, policy=replace(TINY, max_packets=3), stats=stats
        )
    assert source.reads == 4 and source.closed and stats.input_packets == 3
