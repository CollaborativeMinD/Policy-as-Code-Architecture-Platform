"""CDC independent math, packetization, byte ownership, and state boundaries."""

from dataclasses import replace

import pytest

from hmt_pg_patterns.streaming_contracts import Policy, StreamError
from hmt_pg_patterns.streaming_scan import Scanner
from streaming_oracle import check_partition, qualify

TINY = Policy(block_size_target=3, window_size=2, min_size=2, max_size=5)


def test_independent_polynomial_and_all_tiny_partitions():
    report = qualify(cases=80)
    assert report["status"] == "PASS" and report["partitions"] == 2288
    assert report["bytes_checked"] > 400000


@pytest.mark.parametrize(
    "change",
    [
        {"max_size": 1048577},
        {"max_packet_bytes": 16777217},
        {"window_size": 0},
        {"min_size": 1},
        {"block_size_target": 1},
        {"target": 3},
        {"max_packets": 0},
        {"max_packets": 1000001},
        {"max_total_bytes": 0},
        {"quantum_bytes": 65537},
        {"max_size": True},
        {"max_packets": 1.0},
        {"target": -1},
    ],
)
def test_all_policy_dimensions_are_typed_and_finite(change):
    with pytest.raises(StreamError, match="INVALID_POLICY"):
        replace(TINY, **change)


def test_empty_source_terminal_states_and_policy_type():
    scanner = Scanner(TINY)
    assert scanner.finish() == scanner.finish() == []
    with pytest.raises(StreamError, match="SCANNER_FINISHED"):
        scanner.feed(b"x")
    scanner.abort()
    assert scanner.state == "ABORTED"
    with pytest.raises(StreamError, match="SCANNER_ABORTED"):
        scanner.finish()
    with pytest.raises(StreamError, match="INVALID_POLICY"):
        Scanner({})


def test_mutable_packet_is_snapshotted_and_partial_feed_aborts():
    scanner = Scanner(TINY)
    value = bytearray(range(20))
    iterator = scanner.feed(value)
    value[:] = b"x" * len(value)
    first = next(iterator)
    assert first.data == bytes(range(len(first.data)))
    assert scanner.offset == first.end
    for action in (lambda: scanner.feed(b""), scanner.finish, scanner.abort):
        with pytest.raises(StreamError, match="FEED_ACTIVE"):
            action()
    iterator.close()
    assert scanner.state == "ABORTED"


def test_precreated_feed_revalidates_live_total_bound():
    scanner = Scanner(replace(TINY, max_total_bytes=4))
    late = scanner.feed(b"1234")
    list(scanner.feed(b"abc"))
    with pytest.raises(StreamError, match="STREAM_CAPACITY"):
        list(late)


def test_invalid_packet_capacity_and_released_views():
    scanner = Scanner(replace(TINY, max_packet_bytes=4, quantum_bytes=4, max_total_bytes=4))
    for value, code in (("text", "INVALID_PACKET"), (b"12345", "PACKET_CAPACITY")):
        with pytest.raises(StreamError, match=code):
            scanner.feed(value)
    view = memoryview(b"a")
    view.release()
    with pytest.raises(StreamError, match="INVALID_PACKET"):
        scanner.feed(view)
    list(scanner.feed(b"abc"))
    with pytest.raises(StreamError, match="STREAM_CAPACITY"):
        scanner.feed(b"de")
    assert scanner.buffer_peak <= 5 and scanner.window_peak <= 2


def test_non_contiguous_memoryview_preserves_logical_bytes():
    data = bytes(range(90))
    view = memoryview(data)[::2]
    assert check_partition(data[::2], [view], TINY) > 1


@pytest.mark.parametrize("tail_size", [1, 2, 3])
def test_short_tail_retains_rolling_window_across_cut(tail_size):
    """The public tail fingerprint includes bytes before the preceding chunk cut."""
    policy = Policy(17, 4, 4, 4, target=3, quantum_bytes=4)
    data = b"abcdefgh" + b"xyz"[:tail_size]
    scanner = Scanner(policy)
    chunks = list(scanner.feed(data[:7])) + list(scanner.feed(data[7:])) + scanner.finish()
    assert b"".join(chunk.data for chunk in chunks) == data
    tail = chunks[-1]
    assert tail.reason == "tail" and tail.data == b"xyz"[:tail_size]
    assert tail.fingerprint == int.from_bytes(data[-4:], "big") % ((1 << 61) - 1)
