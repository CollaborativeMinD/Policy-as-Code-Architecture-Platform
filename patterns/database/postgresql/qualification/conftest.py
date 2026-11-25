"""External wire qualification explicitly reuses the software service fixtures."""

from tests.conftest import pg_conn, pg_dsn, redis_client, redis_url

__all__ = ["pg_conn", "pg_dsn", "redis_client", "redis_url"]
