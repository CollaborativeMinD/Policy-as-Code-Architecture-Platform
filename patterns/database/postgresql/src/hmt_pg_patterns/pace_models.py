"""PG-PACE-001: bounded observations and explicit recovery policy."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Mode(StrEnum):
    """Degradation order: Primary through Terminal."""

    PRIMARY = "P"
    ALTERNATE = "A"
    CONTINGENCY = "C"
    EMERGENCY = "E"
    TERMINAL = "T"


class PacePolicy(BaseModel):
    """Reference recovery bounds; a mission must select its own calibrated values."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)
    recovery_margin: float = Field(default=0.25, gt=0, le=1)
    pressure_limit: float = Field(default=0.1, ge=0, le=1)
    pressure_decay: float = Field(default=0.8, ge=0, le=1)
    recovery_samples: int = Field(default=3, ge=2, le=100)
    dwell_seconds: float = Field(default=3.0, gt=0, le=300)
    max_sample_gap: float = Field(default=60.0, gt=0, le=600)


class Observation(BaseModel):
    """One immutable observation supplied by trusted health and authority adapters."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)
    now: float = Field(ge=0)
    margin: float = Field(ge=-1, le=1)
    database_ready: bool
    cache_ready: bool
    transport_ready: bool
    authority_valid: bool
    epoch_current: bool
    reconciled: bool
    uncertain_ack: bool


class PaceState(BaseModel):
    """Local selection state; this object is never a database authority token."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)
    mode: Mode = Mode.PRIMARY
    pressure: float = Field(default=0.0, ge=0)
    healthy_samples: int = Field(default=0, ge=0)
    healthy_since: float | None = None
    last_at: float = Field(default=0.0, ge=0)
    reason: str = "INITIAL"


OPERATIONS = {
    Mode.PRIMARY: ("read", "write", "relay"),
    Mode.ALTERNATE: ("read", "write", "relay"),
    Mode.CONTINGENCY: ("read", "write"),
    Mode.EMERGENCY: ("read_checkpoint", "health"),
    Mode.TERMINAL: (),
}
