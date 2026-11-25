"""PG-AUTH-01..06: strict byte contracts; peer identity is never request data."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

BIGINT = (1 << 63) - 1
Epoch = Annotated[int, Field(strict=True, ge=1, le=BIGINT)]
Offset = Annotated[int, Field(strict=True, ge=0, le=BIGINT)]
Digest = Annotated[bytes, Field(strict=True, min_length=32, max_length=32)]


class FrozenContract(BaseModel):
    """Reject unknown fields, coercion, and in-place contract mutation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class ChunkRequest(FrozenContract):
    """One bounded immutable effect request with no client identity claim."""

    stream_id: UUID
    request_id: UUID
    epoch: Epoch
    sequence: Offset
    start: Offset
    previous_digest: Digest
    policy_digest: Digest
    data: Annotated[bytes, Field(strict=True, min_length=1, max_length=1048576)]

    def header(self):
        """Encode the exact SQL header, keeping the payload in a separate parameter."""
        value = self.model_dump(mode="json", exclude={"data", "previous_digest", "policy_digest"})
        value.update(
            previous_digest=self.previous_digest.hex(), policy_digest=self.policy_digest.hex()
        )
        return value


class Receipt(FrozenContract):
    """Database observation of an admitted or exactly replayed chunk."""

    stream_id: UUID
    request_id: UUID
    epoch: Epoch
    sequence: Offset
    start: Offset
    end: Offset
    digest: Digest
    policy_digest: Digest
    replayed: bool


class PeerIdentity(FrozenContract):
    """Current database role, trusted peer binding, and fencing epoch."""

    db_role: str
    peer_key: Annotated[str, Field(pattern=r"^nodekey:[0-9a-f]{64}$")]
    epoch: Epoch


class CheckpointData(FrozenContract):
    """Authoritative PostgreSQL stream tip for a single role and epoch."""

    db_role: str
    stream_id: UUID
    epoch: Epoch
    sequence: Offset
    end: Offset
    digest: Digest
    policy_digest: Digest


def receipt(row):
    """Accept exactly the typed columns returned by hmt_pg.admit_chunk."""
    keys = tuple(Receipt.model_fields)
    return Receipt.model_validate(dict(zip(keys, row, strict=True)))


def checkpoint(row):
    """Decode one SQL checkpoint row, preserving the absence of a stream head."""
    if row is None:
        return None
    return CheckpointData.model_validate(dict(zip(CheckpointData.model_fields, row, strict=True)))
