"""Bounded async source and sink mechanics for the public streaming owner."""

import asyncio
import math
from inspect import isawaitable

from .streaming_contracts import StreamError


def _positive(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise StreamError("INVALID_DEADLINE")


async def _deliver(chunk, sink, stats):
    try:
        result = sink(chunk)
        if isawaitable(result):
            await result
    except Exception as exc:
        raise StreamError("SINK_FAILURE") from exc
    stats.delivered_bytes += len(chunk.data)
    stats.delivered_chunks += 1


def _packet(packet, policy, stats):
    if not isinstance(packet, (bytes, bytearray, memoryview)):
        raise StreamError("INVALID_PACKET")
    try:
        view = memoryview(packet)
    except ValueError as exc:
        raise StreamError("INVALID_PACKET") from exc
    if view.nbytes > policy.max_packet_bytes:
        raise StreamError("PACKET_CAPACITY")
    if stats.input_bytes + view.nbytes > policy.max_total_bytes:
        raise StreamError("STREAM_CAPACITY")
    packet = bytes(view)
    stats.input_bytes += len(packet)
    return packet


async def _consume(source, scanner, sink, stats):
    p = scanner.policy
    for packet_index in range(p.max_packets + 1):
        try:
            packet = await anext(source)
        except StopAsyncIteration:
            break
        except Exception as exc:
            raise StreamError("SOURCE_FAILURE") from exc
        if packet_index == p.max_packets:
            raise StreamError("PACKET_COUNT_CAPACITY")
        stats.input_packets += 1
        packet = _packet(packet, p, stats)
        for start in range(0, len(packet), p.quantum_bytes):
            iterator = scanner.feed(packet[start : start + p.quantum_bytes])
            try:
                for chunk in iterator:
                    await _deliver(chunk, sink, stats)
            finally:
                iterator.close()
            await asyncio.sleep(0)
        await asyncio.sleep(0)  # Empty packets cannot starve cancellation.
    for chunk in scanner.finish():
        await _deliver(chunk, sink, stats)


async def _cleanup(source, timeout, stats):
    close = getattr(source, "aclose", None)
    if close is None:
        return
    try:
        async with asyncio.timeout(timeout):
            await close()
    except TimeoutError as exc:
        raise StreamError("CLEANUP_TIMEOUT") from exc
    except asyncio.CancelledError:
        stats.cleanup_code = "CLEANUP_CANCELLED"
        stats.terminal, stats.code = "CANCELLED", "CLEANUP_CANCELLED"
        raise
    except Exception as exc:
        raise StreamError("CLEANUP_FAILURE") from exc


async def cleanup_source(source, timeout, stats):
    """Record classified cleanup failure while preserving any primary operation failure."""
    try:
        await _cleanup(source, timeout, stats)
    except StreamError as error:
        stats.cleanup_code = error.code
