"""PG-SQLMODEL-001: strict application DTO before a PostgreSQL SQLModel table."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Engine, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Session, SQLModel, col, select

from .models import Metric, QueryWindow
from .queries import snapshot_metric, window_values


class Metrics(SQLModel, table=True):
    """PostgreSQL storage mapping; application admission uses the Metric DTO."""

    __table_args__ = {"schema": "hmt_pg"}
    id: int = Field(sa_column=Column(BigInteger, primary_key=True))
    status: str = Field(sa_column=Column(Text, nullable=False))
    telemetry: dict = Field(sa_column=Column(JSONB, nullable=False))
    observed_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


# Preserve the public row API while using SQLModel's Metrics → metrics convention.
MetricRow = Metrics


def insert_metric(engine: Engine, metric: Metric) -> None:
    """Table constructors are not the validation boundary; the Metric DTO is."""
    params = snapshot_metric(metric).model_dump()
    with Session(engine) as session, session.begin():
        session.add(MetricRow(**params))


def fetch_metrics(engine: Engine, window: QueryWindow) -> list[Metric]:
    """Use SQLModel SQL expressions with the strict page and result contracts."""
    status, after_id, limit = window_values(window)
    statement = (
        select(MetricRow)
        .where(
            col(MetricRow.status) == status,
            col(MetricRow.id) > after_id,
        )
        .order_by(col(MetricRow.id))
        .limit(limit)
    )
    with Session(engine) as session:
        return [Metric.model_validate(row.model_dump()) for row in session.exec(statement)]
