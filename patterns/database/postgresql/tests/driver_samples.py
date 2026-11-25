"""Deterministic DTOs shared by driver tests; no dependency stubs."""

from datetime import UTC, datetime

from hmt_pg_patterns.models import Metric


def sample(identifier=1, status="active"):
    return Metric(
        id=identifier,
        status=status,
        telemetry={"temperature": 42.25},
        observed_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
    )
