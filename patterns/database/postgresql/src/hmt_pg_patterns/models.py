"""PG-CONTRACT-001: strict DTOs before persistence or analytics."""

import math
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Metric(BaseModel):
    """Validated DTO; authority snapshots use deep immutable structures separately."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)
    id: int = Field(ge=1, le=9223372036854775807)
    status: Literal["active", "inactive"]
    telemetry: dict[str, float] = Field(max_length=64)
    observed_at: datetime

    @field_validator("telemetry")
    @classmethod
    def bounded_keys(cls, values):
        """Reject unbounded identifiers and nonfinite telemetry before persistence."""
        for name, value in values.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name):
                raise ValueError("TELEMETRY_KEY_INVALID")
            if not math.isfinite(value):
                raise ValueError("TELEMETRY_VALUE_NOT_FINITE")
        return values

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value):
        """Keep timestamps explicit about their UTC offset."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("TIMESTAMP_REQUIRES_TIMEZONE")
        return value


class QueryWindow(BaseModel):
    """Bound one keyset page; offset scans are not exposed by this reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    status: Literal["active", "inactive"] = "active"
    after_id: int = Field(default=0, ge=0, le=9223372036854775807)
    limit: int = Field(default=1000, ge=1, le=10000)


class BatchSpec(BaseModel):
    """Cap total admitted rows separately from a batch's working set."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    batch_size: int = Field(default=256, ge=1, le=4096)
    max_rows: int = Field(default=10000, ge=1, le=1000000)
