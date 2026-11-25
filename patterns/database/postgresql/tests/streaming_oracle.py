"""Independent test oracle; recomputed windows share no scanner recurrence."""

import itertools
import random

from hmt_pg_patterns.streaming_contracts import Policy
from hmt_pg_patterns.streaming_scan import Scanner


def oracle(data, policy):
    """POLY-02: recompute each window from scratch, O(nW), no rolling state."""
    result, start = [], 0
    fingerprint = 0
    for end in range(1, len(data) + 1):
        window = data[max(0, end - policy.window_size) : end]
        fingerprint = int.from_bytes(window, "big") % ((1 << 61) - 1)
        content = fingerprint % policy.block_size_target == policy.target
        if end - start >= policy.min_size and (content or end - start >= policy.max_size):
            result.append((start, end, fingerprint, "content" if content else "max size"))
            start = end
    if start < len(data):
        result.append((start, len(data), fingerprint, "tail"))
    return result


def check_partition(data, packets, policy, factory=Scanner):
    scanner = factory(policy)
    chunks = []
    for packet in packets:
        chunks.extend(scanner.feed(packet))
    chunks.extend(scanner.finish())
    actual = [(c.start, c.end, c.fingerprint, c.reason) for c in chunks]
    checks = {
        "BOUNDARY_OR_FINGERPRINT_MISMATCH": actual == oracle(data, policy),
        "RECONSTRUCTION_MISMATCH": b"".join(c.data for c in chunks) == data,
        "INDEX_MISMATCH": [c.index for c in chunks] == list(range(len(chunks))),
        "CHUNK_BOUND": all(0 < len(c.data) <= policy.max_size for c in chunks),
        "MINIMUM_BOUND": all(len(c.data) >= policy.min_size for c in chunks[:-1]),
    }
    for reason, passed in checks.items():
        if not passed:
            raise AssertionError(reason)
    return len(chunks)


def exhaustive_partitions(data):
    if not data:
        yield [b""]
        return
    for decisions in itertools.product((False, True), repeat=len(data) - 1):
        points = [0] + [i + 1 for i, cut in enumerate(decisions) if cut] + [len(data)]
        yield [data[a:b] for a, b in itertools.pairwise(points)]


def randomized_packets(data, rng, cap):
    offset = 0
    yield b""
    while offset < len(data):
        size = rng.randint(1, cap)
        yield data[offset : offset + size]
        offset += size
        if rng.randrange(8) == 0:
            yield b""


def qualify(factory=Scanner, *, seed=481, cases=80):
    """Replayable finite campaign for any scanner adapter with this interface."""
    rng, partitions, byte_count = random.Random(seed), 0, 0  # noqa: S311 - replayable test data, not keys.
    tiny = Policy(block_size_target=3, window_size=2, min_size=2, max_size=5)
    for size in range(12):
        data = bytes((i * 73 + size) % 256 for i in range(size))
        for packets in exhaustive_partitions(data):
            check_partition(data, packets, tiny, factory)
            partitions += 1
            byte_count += size
    for case in range(cases):
        interval = rng.choice((3, 7, 16, 31, 64, 257, 512))
        width = rng.randint(1, 80)
        minimum = max(width, interval // 4)
        maximum = max(minimum, interval * 4)
        p = Policy(
            block_size_target=interval,
            window_size=width,
            min_size=minimum,
            max_size=maximum,
            target=rng.randrange(interval),
        )
        data = (
            rng.randbytes(rng.randrange(4097))
            if case % 3
            else bytes([case % 256]) * rng.randrange(4097)
        )
        for packets in (
            [data],
            randomized_packets(data, rng, 97),
            [data[i : i + 1] for i in range(len(data))],
        ):
            check_partition(data, packets, p, factory)
            partitions += 1
            byte_count += len(data)
    return dict(
        seed=seed, cases=cases, partitions=partitions, bytes_checked=byte_count, status="PASS"
    )
