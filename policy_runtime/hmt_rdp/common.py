"""Local compatibility port for the two helpers used by the supplied leaves."""

from hashlib import sha256
import json

from pydantic import BaseModel, ConfigDict


class Closed(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
