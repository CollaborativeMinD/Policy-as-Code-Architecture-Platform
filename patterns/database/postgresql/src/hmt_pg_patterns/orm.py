"""PG-ORM-001: PostgreSQL SQLAlchemy Core, explicit transactions, finite pooling."""

from sqlalchemy import URL, Engine, bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

from .config import DbConfig
from .driver_contracts import pool_limits
from .models import Metric, QueryWindow
from .queries import snapshot_metric, window_values

SELECT = text(
    "SELECT id,status,telemetry,observed_at FROM hmt_pg.metrics "
    "WHERE status=:status AND id>:after_id ORDER BY id LIMIT :limit"
)
INSERT = text(
    "INSERT INTO hmt_pg.metrics(id,status,telemetry,observed_at) "
    "VALUES (:id,:status,:telemetry,:observed_at)"
).bindparams(bindparam("telemetry", type_=JSONB))


def engine_options(config: DbConfig, size: int = 4) -> tuple[URL, dict]:
    """Build a PostgreSQL URL and finite pool options without string interpolation."""
    pool_limits(size, float(config.connect_timeout))
    password = config.password.get_secret_value() if config.password is not None else None
    url = URL.create(
        "postgresql+psycopg",
        username=config.user,
        password=password,
        host=config.host,
        port=config.port,
        database=config.dbname,
    )
    connect_args = config.connect_kwargs()
    for key in ("host", "port", "dbname", "user", "password"):
        connect_args.pop(key, None)
    return url, {
        "connect_args": connect_args,
        "pool_size": size,
        "max_overflow": 0,
        "pool_timeout": config.connect_timeout,
        "pool_pre_ping": True,
        "hide_parameters": True,
    }


def create_pg_engine(config: DbConfig, size: int = 4) -> Engine:
    """The caller owns Engine.dispose(); do not wrap this in a driver pool."""
    url, options = engine_options(config, size)
    return create_engine(url, **options)


def insert_metric(engine: Engine, metric: Metric) -> None:
    """Validate a detached DTO, then commit it within an owned transaction."""
    params = snapshot_metric(metric).model_dump()
    with engine.begin() as conn:
        conn.execute(INSERT, params)


def fetch_metrics(engine: Engine, window: QueryWindow) -> list[Metric]:
    """Read a bounded keyset page and validate every result before release."""
    status, after_id, limit = window_values(window)
    with engine.connect() as conn:
        rows = conn.execute(SELECT, {"status": status, "after_id": after_id, "limit": limit})
        return [Metric.model_validate(dict(row)) for row in rows.mappings()]
