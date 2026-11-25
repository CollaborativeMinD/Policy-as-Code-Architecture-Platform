"""Frozen historical vectors are re-encoded; no upstream implementation is packaged."""

import base64
import hashlib
import json
from pathlib import Path

from hmt_pg_patterns.streaming_contracts import Policy
from hmt_pg_patterns.streaming_scan import Scanner


def test_all_historical_source_vectors_match_with_changed_packetization():
    value = json.loads((Path(__file__).parent / "fixtures/streaming_vectors.json").read_text())
    assert len(value["vectors"]) == 12
    for vector in value["vectors"]:
        data = base64.b85decode(vector["payload_b85"])
        scanner = Scanner(Policy(**vector["policy"]))
        chunks = []
        for offset in range(0, len(data), 17):
            chunks.extend(scanner.feed(data[offset : offset + 17]))
        chunks.extend(scanner.finish())
        actual = [
            [c.start, c.end, c.fingerprint, c.reason, hashlib.sha256(c.data).hexdigest()]
            for c in chunks
        ]
        assert actual == vector["expected"], vector["id"]
        assert b"".join(c.data for c in chunks) == data
