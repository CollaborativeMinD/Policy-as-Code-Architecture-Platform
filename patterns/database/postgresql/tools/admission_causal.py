"""Bind all four causal experiments to actual, current pytest executions."""

from contextlib import closing
import sqlite3


def append_witness(db, edge, candidate_id, experiment, context):
    identity = edge["tests"][experiment]
    assertion = edge["id"] + ":" + experiment
    witness = context["observed"].get(identity)
    passed = witness is not None and witness["outcome"] == "PASS"
    actual = "ASSERTIONS_PASSED" if passed else "TEST_NOT_PASSED"
    execution = context["execution"]
    execution_id = execution["run_id"] + ":" + assertion
    assertion_row = (
        assertion,
        candidate_id,
        edge["requirement"],
        "causal",
        identity,
        "ASSERTIONS_PASSED",
    )
    execution_row = (
        execution_id,
        assertion,
        execution["source_digest"],
        "PASS" if passed else "FAIL",
        actual,
        context["digest"],
    )
    db.execute("INSERT INTO assertions VALUES (?,?,?,?,?,?)", assertion_row)
    db.execute("INSERT INTO executions VALUES (?,?,?,?,?,?)", execution_row)
    db.execute(
        "INSERT INTO causal_witnesses VALUES (?,?,?)", (edge["id"], experiment, execution_id)
    )
    return None if passed else identity


def attach_causal(path, execution, registry, evidence_digest):
    observed = {row["test_id"]: row for row in execution["tests"]}
    if len(observed) != len(execution["tests"]):
        raise ValueError("DUPLICATE_CAUSAL_WITNESS")
    context = {"execution": execution, "observed": observed, "digest": evidence_digest}
    missing = []
    with closing(sqlite3.connect(path)) as db, db:
        source = db.execute("SELECT value FROM metadata WHERE key='source_digest'").fetchone()
        if execution.get("method") != "executed" or source != (execution["source_digest"],):
            raise ValueError("CAUSAL_SOURCE_DRIFT")
        for edge in registry["causal_edges"]:
            if set(edge["tests"]) != {
                "deletion",
                "restoration",
                "matched_control",
                "alternate_path",
            }:
                raise ValueError("CAUSAL_EXPERIMENT_POPULATION")
            db.execute("INSERT INTO causal_edges VALUES (?,?)", (edge["id"], edge["requirement"]))
            candidate = db.execute(
                "SELECT id FROM candidates WHERE invariant_id=? "
                "AND status='PENDING' ORDER BY id LIMIT 1",
                (edge["requirement"],),
            ).fetchone()
            if candidate is None:
                raise ValueError("CAUSAL_REQUIREMENT_HAS_NO_CANDIDATE")
            for experiment in edge["tests"]:
                absent = append_witness(db, edge, candidate[0], experiment, context)
                if absent:
                    missing.append(absent)
    return {
        "status": "FAIL" if missing else "PASS",
        "edges": len(registry["causal_edges"]),
        "missing_or_nonpassing": missing,
        "experiment_count": len(registry["causal_edges"]) * 4,
    }
