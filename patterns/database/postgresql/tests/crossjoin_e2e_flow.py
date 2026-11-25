"""Complete CDC -> fenced PostgreSQL effect -> outbox -> Redis projection reference."""

from dataclasses import dataclass
from uuid import uuid4

from authority_samples import register
from crossjoin_live_stream import reconstruct
from crossjoin_unit_stream import chunk_policy
from hmt_pg_patterns.checkpoints import CheckpointCache
from hmt_pg_patterns.outbox import reconcile, recover, relay_checkpoint
from hmt_pg_patterns.pace import perform
from hmt_pg_patterns.pace_models import PaceState
from hmt_pg_patterns.streaming_writer import StreamWriter

PAYLOAD = b"postgresql reference bytes; values stay data; " * 3


@dataclass(frozen=True)
class Flow:
    live: object
    authority: object
    stream_id: object
    policy: object

    def write(self, packets):
        writer = StreamWriter(self.authority, self.stream_id, 1, self.policy)
        return perform(PaceState(), "write", lambda: writer.write(packets))

    def complete(self, snapshot, payload):
        assert reconstruct(self.live.conn, self.stream_id) == payload
        current = self.authority.checkpoint(self.stream_id)
        assert snapshot["digest"] == current.digest and snapshot["end"] == len(payload)
        cache = CheckpointCache(self.live.redis)
        for _ in range(100):
            outcome = relay_checkpoint(self.live.conn, cache)
            if outcome is None:
                break
            assert outcome in {"ACKED", "UNKNOWN"}
        else:
            raise AssertionError("OUTBOX_TEST_BOUND")
        assert cache.read(current) == snapshot
        # Earlier projections are retained as uncertain until the latest head is observed.
        for event in recover(self.live.conn):
            assert reconcile(self.live.conn, cache, event) == "ACKED"
        assert not recover(self.live.conn)
        return "complete_fenced_flow"


def prepare(live, policy=None):
    return Flow(live, register(live.conn), uuid4(), chunk_policy() if policy is None else policy)
