"""PG-CDC-01: ordered byte chunks to database effects; origin replay is idempotent."""

from dataclasses import asdict
import hashlib
import json
from uuid import UUID, uuid5

from pydantic import TypeAdapter

from .authority_types import CheckpointData, ChunkRequest, Epoch
from .checkpoints_snapshot import immutable_checkpoint
from .streaming_contracts import Policy
from .streaming_scan import Scanner


class WriterState:
    """One stream/epoch per writer; resume by replaying the immutable source from byte0."""

    def __init__(self, authority, stream_id, epoch, policy=None):
        self.authority = authority
        self.stream_id = UUID(str(stream_id))
        self.epoch = TypeAdapter(Epoch).validate_python(epoch)
        self.policy = Policy() if policy is None else policy
        Scanner(self.policy)
        self.policy_digest = hashlib.sha256(
            json.dumps(asdict(self.policy), sort_keys=True).encode()
        ).digest()
        self.previous = bytes(32)
        self.snapshot = None
        self._started = False

    def request(self, chunk):
        """Bind sequence, policy, predecessor, and source bytes to a stable replay key."""
        key = f"hmt-pg-v1:{self.epoch}:{chunk.index}:{hashlib.sha256(chunk.data).hexdigest()}"
        return ChunkRequest(
            stream_id=self.stream_id,
            request_id=uuid5(self.stream_id, key),
            epoch=self.epoch,
            sequence=chunk.index,
            start=chunk.start,
            previous_digest=self.previous,
            policy_digest=self.policy_digest,
            data=chunk.data,
        )

    def accept(self, result, db_role):
        """Advance local state only after receiving a typed database receipt."""
        self.previous = result.digest
        value = CheckpointData(
            db_role=db_role,
            stream_id=result.stream_id,
            epoch=result.epoch,
            sequence=result.sequence,
            end=result.end,
            digest=result.digest,
            policy_digest=result.policy_digest,
        )
        self.snapshot = immutable_checkpoint(value)
