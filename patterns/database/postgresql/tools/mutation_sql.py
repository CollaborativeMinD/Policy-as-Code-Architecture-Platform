"""Four viable PostgreSQL guard deletions; real SQL outcomes must kill them."""

from .mutation_models import Mutation, Patch

SOURCE = "sql/02_authority.sql"
MUTATIONS = (
    Mutation(
        "PG-M05",
        "PG-FENCE-001",
        Patch(SOURCE, "(expected IS NOT NULL AND a.epoch<>expected)", "false"),
        "tests/test_mutation_witnesses.py::test_epoch_guard_new_stream",
    ),
    Mutation(
        "PG-M06",
        "PG-FENCE-001",
        Patch(SOURCE, "NOT FOUND OR NOT a.active OR", "NOT FOUND OR false OR"),
        "tests/test_mutation_witnesses.py::test_active_guard",
    ),
    Mutation(
        "PG-M07",
        "PG-FENCE-001",
        Patch(
            SOURCE,
            "d:=hmt_pg.chunk_digest(a.db_role,v,p);\n"
            " IF a.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'AUTHORITY_EXPIRED'; END IF;",
            "d:=hmt_pg.chunk_digest(a.db_role,v,p);",
        ),
        "tests/test_authority_security.py::test_expiration_is_rechecked_after_authority_lock",
    ),
    Mutation(
        "PG-M08",
        "PG-FENCE-001",
        Patch(
            SOURCE,
            "IF ROW(head.epoch,head.sequence+1,head.end_offset,head.digest,head.policy_digest) IS DISTINCT FROM\n"
            "  ROW(v.epoch,v.sequence,v.start_offset,v.previous_digest,v.policy_digest) THEN",
            "IF false THEN",
        ),
        "tests/test_authority_atomic.py::test_chain_rejects_gap_or_forgery_before_any_effect",
    ),
)
