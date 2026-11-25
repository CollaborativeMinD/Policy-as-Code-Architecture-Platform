"""PG-MIGRATION-001: atomic replay and mutation drift rejection."""

import psycopg
import pytest

from hmt_pg_patterns.migrations import apply_migrations, migration_inputs


def test_migration_inputs_reject_empty_unsafe_and_oversized(tmp_path):
    with pytest.raises(ValueError, match="COUNT"):
        migration_inputs(tmp_path)
    path = tmp_path / "01_test.sql"
    path.write_text("SELECT 1")
    assert len(migration_inputs(tmp_path)) == 1
    path.write_bytes(b"x" * 262145)
    with pytest.raises(ValueError, match="SIZE"):
        migration_inputs(tmp_path)
    path.unlink()
    (tmp_path / "01_bad-name.sql").write_text("SELECT 1")
    with pytest.raises(ValueError, match="PATH"):
        migration_inputs(tmp_path)


def test_checksum_bound_migration_and_transaction_rollback(pg_conn, tmp_path):
    first = tmp_path / "91_test.sql"
    first.write_text("CREATE TABLE hmt_pg.migration_probe(id int PRIMARY KEY)")
    assert apply_migrations(pg_conn, tmp_path) == ["91_test.sql"]
    assert apply_migrations(pg_conn, tmp_path) == []
    first.write_text("SELECT 'changed contract'")
    with pytest.raises(ValueError, match="CHECKSUM_DRIFT"):
        apply_migrations(pg_conn, tmp_path)
    assert pg_conn.execute("SELECT count(*) FROM hmt_pg.migration_probe").fetchone() == (0,)
    first.unlink()
    (tmp_path / "92_rollback.sql").write_text(
        "INSERT INTO hmt_pg.migration_probe VALUES (1); SELECT 1/0"
    )
    with pytest.raises(psycopg.errors.DivisionByZero):
        apply_migrations(pg_conn, tmp_path)
    assert pg_conn.execute("SELECT count(*) FROM hmt_pg.migration_probe").fetchone() == (0,)
    assert pg_conn.execute(
        "SELECT count(*) FROM hmt_pg.schema_migrations WHERE name=%s", ("92_rollback.sql",)
    ).fetchone() == (0,)
