"""PG-ORM-001: PostgreSQL types, committed writes, and strict DTO admission."""

import pytest
from driver_samples import sample
from sqlalchemy.exc import IntegrityError

from hmt_pg_patterns import orm, orm_async, orm_model
from hmt_pg_patterns.models import QueryWindow

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("driver", [orm, orm_model])
def test_core_and_sqlmodel_commit_and_seek(pg_conn, db_config, driver):
    engine = orm.create_pg_engine(db_config, size=1)
    try:
        driver.insert_metric(engine, sample(1))
        driver.insert_metric(engine, sample(2, "inactive"))
        assert driver.fetch_metrics(engine, QueryWindow()) == [sample(1)]
        assert driver.fetch_metrics(engine, QueryWindow(after_id=1)) == []
        with pytest.raises(IntegrityError):
            driver.insert_metric(engine, sample(1))
        assert driver.fetch_metrics(engine, QueryWindow()) == [sample(1)]
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        assert engine.pool.size() == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize("driver", [orm, orm_model])
def test_strict_dto_precedes_engine_or_session_access(driver):
    with pytest.raises(ValueError):
        driver.insert_metric(object(), sample().model_copy(update={"id": "1"}))


@pytest.mark.asyncio
async def test_sqlalchemy_async_uses_native_psycopg(pg_conn, db_config):
    engine = orm_async.create_pg_engine(db_config, size=1)
    try:
        await orm_async.insert_metric(engine, sample())
        assert await orm_async.fetch_metrics(engine, QueryWindow()) == [sample()]
        assert engine.dialect.is_async
        with pytest.raises(IntegrityError):
            await orm_async.insert_metric(engine, sample())
        assert await orm_async.fetch_metrics(engine, QueryWindow(after_id=1)) == []
    finally:
        await engine.dispose()
