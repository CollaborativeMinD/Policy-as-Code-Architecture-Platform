"""CDC-04..06: zero-queue backpressure, cooperative cancellation, owned cleanup."""

import asyncio

from .streaming_contracts import Policy, StreamError, StreamStats, StreamLimits
from .streaming_scan import Scanner
from .streaming_runtime import _consume, _positive, cleanup_source


async def stream_chunks(packets, sink, *, policy=None, limits=None, stats=None):
    """Own the async iterator; never retry sink calls. No background tasks."""
    limits = StreamLimits() if limits is None else limits
    if type(limits) is not StreamLimits:
        raise StreamError("INVALID_LIMITS")
    _positive(limits.deadline_s)
    _positive(limits.cleanup_timeout_s)
    scanner = Scanner(Policy() if policy is None else policy)
    if not callable(sink):
        raise StreamError("INVALID_SINK")
    stats = stats if stats is not None else StreamStats()
    if type(stats) is not StreamStats or stats.terminal != "NEW":
        raise StreamError("INVALID_STATS")
    try:
        source = aiter(packets)
    except Exception as exc:
        raise StreamError("INVALID_SOURCE") from exc
    stats.terminal = "RUNNING"
    try:
        async with asyncio.timeout(limits.deadline_s):
            await _consume(source, scanner, sink, stats)
        stats.terminal = "COMPLETED"
    except asyncio.CancelledError:
        stats.terminal, stats.code = "CANCELLED", "CANCELLED"
        raise
    except TimeoutError as exc:
        stats.terminal, stats.code = "FAILED", "DEADLINE"
        raise StreamError("DEADLINE") from exc
    except StreamError as exc:
        stats.terminal, stats.code = "FAILED", exc.code
        raise
    finally:
        stats.buffer_peak, stats.window_peak = scanner.buffer_peak, scanner.window_peak
        scanner.abort()
        await cleanup_source(source, limits.cleanup_timeout_s, stats)
        if stats.cleanup_code and stats.terminal == "COMPLETED":
            stats.terminal, stats.code = "FAILED", stats.cleanup_code
            raise StreamError(stats.cleanup_code)
    return stats
