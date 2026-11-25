"""Owned PostgreSQL fault injection; always restore the exact observed definition."""

from contextlib import contextmanager

from psycopg import sql

EPOCH_GUARD = "(expected IS NOT NULL AND a.epoch<>expected)"


@contextmanager
def replace_function(connection, signature, old, new):
    """Change one known body fragment and restore its original catalog bytes."""
    original = connection.execute(
        "SELECT pg_get_functiondef(%s::regprocedure)", (signature,)
    ).fetchone()[0]
    assert original.count(old) == 1, "causal injection anchor must be unique"
    connection.execute(sql.SQL(original.replace(old, new)), prepare=False)
    try:
        yield
    finally:
        connection.execute(sql.SQL(original), prepare=False)
        restored = connection.execute(
            "SELECT pg_get_functiondef(%s::regprocedure)", (signature,)
        ).fetchone()[0]
        assert restored == original, "the experiment must restore the observed source"


@contextmanager
def fail_outbox_insert(connection):
    """Inject a late SQL failure after the effect and head were written."""
    connection.execute(
        "CREATE FUNCTION hmt_pg.causal_outbox_failure() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'CAUSAL_OUTBOX_FAULT'; END $$; "
        "CREATE TRIGGER causal_outbox_fault BEFORE INSERT ON hmt_pg.checkpoint_outbox "
        "FOR EACH ROW EXECUTE FUNCTION hmt_pg.causal_outbox_failure()",
        prepare=False,
    )
    try:
        yield
    finally:
        connection.execute(
            "DROP TRIGGER causal_outbox_fault ON hmt_pg.checkpoint_outbox; "
            "DROP FUNCTION hmt_pg.causal_outbox_failure()",
            prepare=False,
        )
