"""PG-ASYNCPG-001: primary error identity survives an independent teardown fault."""

import pytest
from test_teardown_faults import CloseProbe

from hmt_pg_patterns import asyncpg_driver, asyncpg_pool
from hmt_pg_patterns.config import DbConfig

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.mark.parametrize(
    "module,context_name,factory_name",
    [(asyncpg_driver, "connection", "connect"), (asyncpg_pool, "pool", "create_pool")],
)
async def test_primary_failure_preserved_with_cleanup_failure(
    monkeypatch, module, context_name, factory_name
):
    async def factory(**kwargs):
        return CloseProbe("error")

    monkeypatch.setattr(module.asyncpg, factory_name, factory)
    config = DbConfig(host="127.0.0.1", user="hmt_app", profile="test", sslmode="disable")
    primary = RuntimeError("application witness")
    with pytest.raises(RuntimeError) as captured:
        async with getattr(module, context_name)(config):
            raise primary
    assert captured.value is primary
    assert isinstance(primary.__cause__, ValueError)
    assert primary.__notes__ == [
        f"{'Connection' if context_name == 'connection' else 'Pool'} teardown failed: ValueError"
    ]


@pytest.mark.parametrize(
    "module,context_name,factory_name",
    [(asyncpg_driver, "connection", "connect"), (asyncpg_pool, "pool", "create_pool")],
)
async def test_successful_body_does_not_hide_cleanup_failure(
    monkeypatch, module, context_name, factory_name
):
    async def factory(**kwargs):
        return CloseProbe("error")

    monkeypatch.setattr(module.asyncpg, factory_name, factory)
    config = DbConfig(host="127.0.0.1", user="hmt_app", profile="test", sslmode="disable")
    with pytest.raises(ValueError, match="cleanup witness"):
        async with getattr(module, context_name)(config):
            pass
