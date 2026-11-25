"""Preserve every candidate assertion and attach current, observed test witnesses."""

from contextlib import closing
import sqlite3


def bind_executions(path, execution, evidence_digest):
    if execution.get("method") != "executed":
        raise ValueError("FRESH_EXECUTION_REQUIRED")
    observed = {row["test_id"]: row for row in execution["tests"]}
    if len(observed) != len(execution["tests"]):
        raise ValueError("DUPLICATE_TEST_ID")
    manifest, selected, missing = [], [], []
    with closing(sqlite3.connect(path)) as db, db:
        source = db.execute("SELECT value FROM metadata WHERE key='source_digest'").fetchone()[0]
        if source != execution["source_digest"]:
            raise ValueError("EXECUTION_SOURCE_DRIFT")
        rows = db.execute("SELECT id,requirement,test_id,expected FROM assertions").fetchall()
        for assertion, requirement, identity, expected in rows:
            witness = observed.get(identity)
            passed = witness is not None and witness["outcome"] == "PASS"
            actual = expected if passed else "TEST_NOT_PASSED"
            db.execute(
                "INSERT INTO executions VALUES (?,?,?,?,?,?)",
                (
                    execution["run_id"] + ":" + assertion,
                    assertion,
                    source,
                    "PASS" if passed else "FAIL",
                    actual,
                    evidence_digest,
                ),
            )
            manifest.append(
                {
                    "test_id": identity,
                    "source_requirement_or_invariant": requirement,
                    "evidence_ref": "junit.xml",
                }
            )
            selected.append(witness or {"test_id": identity, "outcome": "MISSING"})
            if not passed:
                missing.append(identity)
    subset = {key: execution[key] for key in ("method", "source_digest", "run_id")}
    subset["tests"] = selected
    return {
        "status": "FAIL" if missing else "PASS",
        "missing_or_nonpassing": missing,
        "assertions": len(manifest),
        "manifest": manifest,
        "execution": subset,
    }
