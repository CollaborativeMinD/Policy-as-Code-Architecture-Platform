"""Independent packetization and capacity attacks on the live CDC primitive."""

import pytest

from hmt_pg_patterns.streaming_contracts import Policy, StreamError
from hmt_pg_patterns.streaming_scan import Scanner

PAYLOAD = bytes(range(256)) * 4


def chunk_policy(**changes):
    values = dict(
        block_size_target=16,
        window_size=4,
        min_size=8,
        max_size=32,
        max_packet_bytes=2048,
        max_total_bytes=4096,
        quantum_bytes=64,
    )
    values.update(changes)
    return Policy(**values)


def scan(data, packet_size):
    scanner = Scanner(chunk_policy())
    chunks = []
    for start in range(0, len(data), packet_size):
        chunks.extend(scanner.feed(data[start : start + packet_size]))
    chunks.extend(scanner.finish())
    assert b"".join(chunk.data for chunk in chunks) == data
    assert scanner.buffer_peak <= scanner.policy.max_size
    assert scanner.window_peak <= scanner.policy.window_size
    return chunks


def packet_invariance():
    baseline = scan(PAYLOAD, len(PAYLOAD))
    for packet_size in (1, 7, 63, 257):
        assert scan(PAYLOAD, packet_size) == baseline
    return baseline[0].reason


def stream_limits():
    scanner = Scanner(chunk_policy(max_total_bytes=16))
    with pytest.raises(StreamError) as denied:
        list(scanner.feed(b"x" * 17))
    assert scanner.offset == 0 and scanner.buffer_peak == 0
    return denied.value.code
