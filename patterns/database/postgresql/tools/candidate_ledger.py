"""Materialize every CROSS JOIN row and retain explicit exclusions and witnesses."""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from .candidate_model import applicability, test_id, validate_dimensions
from .candidate_sql import CROSS_JOIN, TABLES, create_tables, protect_history


def canonical_digest(value):
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def append_candidate(db, candidate_id, triple, data):
    case, predicate = applicability(data, triple)
    excluded_id = None if case else f"NA-{candidate_id:04d}"
    if not case:
        db.execute("INSERT INTO predicates VALUES (?,?,?,?,?)", (excluded_id, *triple, predicate))
    db.execute(
        "INSERT INTO candidates VALUES (?,?,?,?,?,?)",
        (candidate_id, *triple, "PENDING" if case else "NOT_APPLICABLE", excluded_id),
    )
    if case:
        db.execute(
            "INSERT INTO case_bindings VALUES (?,?,?)",
            (candidate_id, case["id"], case["assertion"]),
        )
        for family in case["families"]:
            db.execute(
                "INSERT INTO assertions VALUES (?,?,?,?,?,?)",
                (
                    f"{candidate_id}:{family}",
                    candidate_id,
                    case["requirement"],
                    family,
                    test_id(case["id"], family),
                    "ASSERTIONS_PASSED",
                ),
            )


def create_ledger(data, path, source_digest):
    validate_dimensions(data)
    path = Path(path)
    if path.exists():
        raise FileExistsError("PRIOR_LEDGER_MUST_BE_PRESERVED")
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        create_tables(db)
        for group, kind in (
            ("invariants", "invariant"),
            ("failure_modes", "failure"),
            ("gates", "gate"),
        ):
            db.executemany(
                "INSERT INTO dimensions VALUES (?,?,?)",
                [(kind, row["id"], row["requirement"]) for row in data[group]],
            )
        triples = db.execute(CROSS_JOIN).fetchall()
        for index, triple in enumerate(triples, 1):
            append_candidate(db, index, triple, data)
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [
                ("dimensions_digest", canonical_digest(data)),
                ("source_digest", source_digest),
                ("expected_count", str(len(triples))),
            ],
        )
        protect_history(db)
    return check_ledger(path)


def check_ledger(path):
    with closing(sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)) as db:
        expected = db.execute(CROSS_JOIN).fetchall()
        observed = db.execute(
            "SELECT invariant_id,failure_id,gate_id FROM candidates "
            "ORDER BY invariant_id,failure_id,gate_id"
        ).fetchall()
        invalid = db.execute(
            "SELECT count(*) FROM candidates c LEFT JOIN predicates p "
            "ON p.id=c.predicate_id WHERE c.status='NOT_APPLICABLE' "
            "AND (p.reason IS NULL OR trim(p.reason)='')"
        ).fetchone()[0]
        applicable = db.execute(
            "SELECT count(*) FROM candidates WHERE status='PENDING'"
        ).fetchone()[0]
        assertions = db.execute("SELECT count(*) FROM assertions").fetchone()[0]
        families = db.execute(
            "SELECT c.id,count(DISTINCT a.family) FROM candidates c "
            "LEFT JOIN assertions a ON a.candidate_id=c.id "
            "AND a.family IN ('unit','regex','integration','e2e') "
            "WHERE c.status='PENDING' GROUP BY c.id"
        ).fetchall()
        wrong = db.execute(
            "SELECT count(*) FROM assertions a JOIN candidates c "
            "ON c.id=a.candidate_id WHERE a.requirement!=c.invariant_id "
            "OR c.status!='PENDING' OR a.family NOT IN "
            "('unit','regex','integration','e2e','negative','mutation',"
            "'behavioral','api','routing','boundary','security','complexity',"
            "'authorization_drift','causal','speed')"
        ).fetchone()[0]
        passed = bool(expected) and expected == observed and not invalid
        passed = passed and applicable > 0 and assertions >= applicable * 4
        passed = passed and not wrong and all(count == 4 for _, count in families)
    return {
        "status": "PASS" if passed else "FAIL",
        "candidate_count": len(observed),
        "expected_count": len(expected),
        "applicable": applicable,
        "not_applicable": len(observed) - applicable,
        "assertions": assertions,
        "sql": CROSS_JOIN,
        "exclusions_missing_predicates": invalid,
    }


def export_tables(path):
    result = {}
    with closing(sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        for table in TABLES:
            result[table] = [dict(row) for row in db.execute(f"SELECT * FROM {table}")]
    return result
