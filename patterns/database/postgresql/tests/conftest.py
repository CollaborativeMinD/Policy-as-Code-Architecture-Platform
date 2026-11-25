"""No skip-on-missing dependency: integration fixtures fail visibly."""

import json
import os
from pathlib import Path

import psycopg
import pytest
import redis
from psycopg.conninfo import conninfo_to_dict
from service_runtime import postgres_service, redis_service

from hmt_pg_patterns.config import DbConfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def pg_dsn(tmp_path_factory):
    folder = tmp_path_factory.mktemp("postgres")
    with postgres_service(folder) as dsn:
        with psycopg.connect(dsn, autocommit=True) as conn:
            for migration in sorted((ROOT / "sql").glob("[0-9][0-9]_*.sql")):
                conn.execute(migration.read_text(), prepare=False)
            version = conn.execute("SELECT version()").fetchone()[0]
            target = os.environ.get("HMT_EVIDENCE_DIR")
            if target:
                path = Path(target)
                path.mkdir(parents=True, exist_ok=True)
                (path / "service_identity.json").write_text(
                    json.dumps(
                        {
                            "postgres_version": version,
                            "profile": "pglite" if "PGlite" in version else "native_postgresql",
                            "native_contention_qualified": False,
                        },
                        indent=2,
                    )
                    + "\n"
                )
        yield dsn


@pytest.fixture
def pg_conn(pg_dsn):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("TRUNCATE hmt_pg.metrics")
        yield conn


@pytest.fixture
def db_config(pg_dsn):
    parts = conninfo_to_dict(pg_dsn)
    return DbConfig(
        host=parts.get("host", "127.0.0.1"),
        port=int(parts["port"]),
        dbname=parts.get("dbname", "postgres"),
        user=parts["user"],
        profile="test",
        sslmode="disable",
    )


@pytest.fixture(scope="session")
def redis_url(tmp_path_factory):
    with redis_service(tmp_path_factory.mktemp("redis")) as url:
        yield url


@pytest.fixture
def redis_client(redis_url):
    client = redis.Redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2)
    assert client.ping()
    yield client
    client.close()
