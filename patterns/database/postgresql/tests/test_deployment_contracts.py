"""PG-CONFIG-001/PG-PEER-001/PG-OPS-001: shipped roles and hardening are executable."""

import configparser
from pathlib import Path

from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("hmt_pg_owner", "hmt_peer_a", "hmt_metrics_reader", "hmt_metrics_writer")


def test_shipped_role_grants_preserve_authority_boundary(pg_conn):
    pg_conn.execute((ROOT / "deployment/01_roles.sql").read_text(), prepare=False)
    try:
        pg_conn.execute((ROOT / "deployment/02_grants.sql").read_text(), prepare=False)
        privilege = pg_conn.execute(
            "SELECT rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls,rolconnlimit "
            "FROM pg_roles WHERE rolname='hmt_peer_a'"
        ).fetchone()
        assert privilege == (False, False, False, False, False, 4)
        assert pg_conn.execute(
            "SELECT has_function_privilege('hmt_peer_a','hmt_pg.admit_chunk(jsonb,bytea)','EXECUTE')"
        ).fetchone()[0]
        for name in ("peer_authority", "chunk_effect", "stream_head", "checkpoint_outbox"):
            assert not pg_conn.execute(
                "SELECT has_table_privilege('hmt_peer_a',%s,'SELECT,INSERT,UPDATE,DELETE')",
                ("hmt_pg." + name,),
            ).fetchone()[0]
        assert pg_conn.execute(
            "SELECT has_table_privilege('hmt_metrics_reader','hmt_pg.metrics','SELECT')"
        ).fetchone()[0]
        assert not pg_conn.execute(
            "SELECT has_table_privilege('hmt_metrics_reader','hmt_pg.metrics','INSERT')"
        ).fetchone()[0]
    finally:
        for role in reversed(ROLES):
            pg_conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
            pg_conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_runtime_containment_and_wal_config_are_concrete():
    service = configparser.ConfigParser(interpolation=None)
    service.read(ROOT / "deployment/hmt-pg-worker.service")
    assert service["Service"]["NoNewPrivileges"] == "yes"
    assert service["Service"]["CapabilityBoundingSet"] == ""
    assert service["Service"]["KillMode"] == "control-group"
    assert int(service["Service"]["TasksMax"]) == 128
    assert "--allow=${HMT_PEER_KEY}" in service["Service"]["ExecStart"]
    assert "-m hmt_pg_patterns.worker" in service["Service"]["ExecStart"]
    settings = (ROOT / "deployment/postgresql.conf").read_text()
    for required in ("fsync = on", "full_page_writes = on", "synchronous_commit = on", "ssl = on"):
        assert required in settings.splitlines()
    assert "password_encryption = 'scram-sha-256'" in settings.splitlines()
