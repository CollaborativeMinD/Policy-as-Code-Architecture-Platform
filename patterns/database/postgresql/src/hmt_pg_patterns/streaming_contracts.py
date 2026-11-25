"""CDC-01..06: immutable byte records, bounded policy, explicit failures."""

from dataclasses import dataclass, fields


class StreamError(RuntimeError):
    """Stable classification for source, sink, lifecycle, and capacity failures."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class Chunk:
    """Immutable contiguous bytes and the exact boundary decision that emitted them."""

    index: int
    start: int
    end: int
    data: bytes
    fingerprint: int
    reason: str


@dataclass(frozen=True, slots=True)
class Policy:
    """Finite scanner, packet, and work-quantum bounds with strict integer fields."""

    block_size_target: int = 512
    window_size: int = 64
    min_size: int = 128
    max_size: int = 2048
    target: int = 1
    max_packet_bytes: int = 65536
    max_total_bytes: int = (1 << 63) - 1
    quantum_bytes: int = 4096
    max_packets: int = 1000000

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 0 <= value <= (1 << 63) - 1:
                raise StreamError("INVALID_POLICY")
        if not (
            2 <= self.block_size_target
            and 1 <= self.window_size <= self.min_size <= self.max_size <= 1048576
            and 0 <= self.target < self.block_size_target
            and 1 <= self.quantum_bytes <= min(self.max_packet_bytes, 65536)
            and self.max_packet_bytes <= 16777216
            and 1 <= self.max_packets <= 1000000
            and 1 <= self.max_total_bytes
        ):
            raise StreamError("INVALID_POLICY")


@dataclass(slots=True)
class StreamStats:
    """One owned run's measured counters, bounded peaks, and terminal outcome."""

    input_bytes: int = 0
    input_packets: int = 0
    delivered_bytes: int = 0
    delivered_chunks: int = 0
    buffer_peak: int = 0
    window_peak: int = 0
    terminal: str = "NEW"
    code: str | None = None
    cleanup_code: str | None = None


@dataclass(frozen=True, slots=True)
class StreamLimits:
    """Cooperative stream and cleanup deadlines validated before source ownership."""

    deadline_s: float = 30.0
    cleanup_timeout_s: float = 1.0
