"""PG-CDC-001: continuous rolling state is causal to packetization independence."""

import pytest

from hmt_pg_patterns.streaming_contracts import Policy
from hmt_pg_patterns.streaming_scan import Scanner

pytestmark = pytest.mark.causal
POLICY = Policy(17, 4, 4, 13, target=3, max_packet_bytes=512, quantum_bytes=32)
DATA = bytes(range(128)) * 3
ORIGINAL_FEED = Scanner.feed


def scan(packets):
    scanner = Scanner(POLICY)
    chunks = [chunk for packet in packets for chunk in scanner.feed(packet)]
    return chunks + scanner.finish()


def split(width):
    return [DATA[start : start + width] for start in range(0, len(DATA), width)]


def reset_window_at_packet(scanner, data):
    """Delete only rolling context at the transport boundary; retain source bytes."""
    scanner._window.clear()
    scanner._fingerprint = 0
    return ORIGINAL_FEED(scanner, data)


def test_deletion(monkeypatch):
    expected = scan([DATA])
    monkeypatch.setattr(Scanner, "feed", reset_window_at_packet)
    altered = scan(split(11))
    assert b"".join(chunk.data for chunk in altered) == DATA
    assert altered != expected


def test_restoration(monkeypatch):
    expected = scan([DATA])
    with monkeypatch.context() as removed:
        removed.setattr(Scanner, "feed", reset_window_at_packet)
        assert scan(split(11)) != expected
    assert scan(split(11)) == expected


def test_matched_control():
    assert scan(split(11)) == scan(split(17)) == scan([b"", DATA, b""])


def test_alternate_path(monkeypatch):
    """A bounded single-packet batch compensates only within max_packet_bytes."""
    expected = scan(split(17))
    monkeypatch.setattr(Scanner, "feed", reset_window_at_packet)
    assert scan(split(11)) != expected
    batched = b"".join(split(11))
    assert len(batched) <= POLICY.max_packet_bytes
    assert scan([batched]) == expected
