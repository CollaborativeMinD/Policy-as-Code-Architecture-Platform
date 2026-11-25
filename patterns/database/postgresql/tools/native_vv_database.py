"""Copy the measured SQLite ledger into the exact supplied native DuckDB schema."""

from contextlib import closing
import sqlite3

from .candidate_ledger import export_tables

TABLES = (
    "dimensions",
    "predicates",
    "candidates",
    "metadata",
    "assertions",
    "executions",
    "supersessions",
    "causal_edges",
    "causal_witnesses",
)


def copy_ledger(source, target, ddl):
    import duckdb

    if target.exists():
        raise FileExistsError("NATIVE_LEDGER_ALREADY_EXISTS")
    tables = export_tables(source)
    with closing(sqlite3.connect(source)) as original, duckdb.connect(str(target)) as db:
        for statement in ddl:
            db.execute(statement)
        for table in TABLES:
            names = [row[1] for row in original.execute(f"PRAGMA table_info({table})")]
            if tables[table]:
                placeholders = ",".join("?" for _ in names)
                db.executemany(
                    f"INSERT INTO {table} VALUES ({placeholders})",
                    [[row[name] for name in names] for row in tables[table]],
                )
            if db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] != len(tables[table]):
                raise ValueError("NATIVE_LEDGER_TRANSFER_LOSS")


def add_families(database, contracts, execution):
    import duckdb

    observed = {row["test_id"]: row for row in execution["tests"]}
    with duckdb.connect(str(database)) as db:
        for family, contract in contracts.items():
            identity, requirement = contract["test_id"], contract["requirement"]
            witness = observed.get(identity)
            if witness is None:
                raise ValueError("FAMILY_EXECUTION_MISSING:" + identity)
            candidate = db.execute(
                "SELECT id FROM candidates WHERE invariant_id=? "
                "AND status='PENDING' ORDER BY id LIMIT 1",
                [requirement],
            ).fetchone()
            if candidate is None:
                raise ValueError("FAMILY_REQUIREMENT_NOT_SELECTED")
            identifier = "FAMILY:" + family
            passed = witness["outcome"] == "PASS"
            db.execute(
                "INSERT INTO assertions VALUES (?,?,?,?,?,?)",
                [identifier, candidate[0], requirement, family, identity, "ASSERTIONS_PASSED"],
            )
            db.execute(
                "INSERT INTO executions VALUES (?,?,?,?,?,?)",
                [
                    execution["run_id"] + identifier,
                    identifier,
                    execution["source_digest"],
                    "PASS" if passed else "FAIL",
                    "ASSERTIONS_PASSED" if passed else witness["outcome"],
                    execution["evidence_digest"],
                ],
            )
