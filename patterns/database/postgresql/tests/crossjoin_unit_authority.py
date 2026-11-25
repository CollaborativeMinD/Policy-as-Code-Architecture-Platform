"""Typed authority/snapshot boundaries; live SQL fences have separate witnesses."""

import json
from types import SimpleNamespace
from uuid import uuid4
from pydantic import ValidationError
import pytest

from authority_samples import request
from hmt_pg_patterns.authority import Authority
from hmt_pg_patterns.authority_types import CheckpointData
from hmt_pg_patterns.checkpoints_snapshot import encode_checkpoint, immutable_checkpoint
from hmt_pg_patterns.outbox import claim


def checkpoint_value():
    return CheckpointData(
        db_role="peer_alpha",
        stream_id=uuid4(),
        epoch=1,
        sequence=0,
        end=1,
        digest=b"a" * 32,
        policy_digest=b"b" * 32,
    )


def immutable_snapshot():
    caller = checkpoint_value().model_dump()
    original = caller["digest"]
    snapshot = immutable_checkpoint(caller)
    caller["digest"] = b"c" * 32
    assert snapshot["digest"] == original
    with pytest.raises(TypeError):
        snapshot["epoch"] = 99
    changed = snapshot.set("epoch", 2)
    assert snapshot["epoch"] == 1 and changed["epoch"] == 2
    return json.loads(encode_checkpoint(snapshot))["digest"]


def epoch_fence():
    invalid = request().model_copy(update={"epoch": False})
    with pytest.raises(ValidationError) as denied:
        Authority(None).admit(invalid)
    assert denied.value.errors()[0]["loc"] == ("epoch",)
    return denied.value.errors()[0]["type"]


def outbox_replay():
    with pytest.raises(ValueError) as denied:
        claim(SimpleNamespace(autocommit=False))
    return str(denied.value)


def checkpoint_order():
    values = checkpoint_value().model_dump()
    values["sequence"] = -1
    with pytest.raises(ValidationError) as denied:
        immutable_checkpoint(values)
    high = checkpoint_value().model_copy(update={"sequence": (1 << 63) - 1})
    assert json.loads(encode_checkpoint(high))["sequence"] == "9223372036854775807"
    return denied.value.errors()[0]["type"]
