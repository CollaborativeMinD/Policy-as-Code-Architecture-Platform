"""PG-CKPT-01: persistent immutable memory snapshots; PostgreSQL is durable custody."""

import json

from pyrsistent import PMap, pmap

from .authority_types import CheckpointData

MAX_CHECKPOINT_BYTES = 8192


def immutable_checkpoint(value):
    """Validate before structural sharing; bytes, UUIDs, ints, and strings are immutable."""
    if isinstance(value, CheckpointData):
        value = value.model_dump()
    elif isinstance(value, PMap):
        value = dict(value)
    return pmap(CheckpointData.model_validate(value).model_dump())


def encode_checkpoint(value):
    """Encode a bounded canonical value with lossless BIGINT decimal strings."""
    value = dict(immutable_checkpoint(value))
    for name in ("epoch", "sequence", "end"):
        value[name] = str(value[name])  # Redis Lua numbers cannot represent every bigint.
    for name in ("digest", "policy_digest"):
        value[name] = value[name].hex()
    value["stream_id"] = str(value["stream_id"])
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_CHECKPOINT_BYTES:
        raise ValueError("CHECKPOINT_CAPACITY")
    return encoded
