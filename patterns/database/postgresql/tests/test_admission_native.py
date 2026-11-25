"""PG-ADMIT-008: native export preserves failures and rejects invented or stale evidence."""

import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import duckdb
import pytest

from tools.admission_binding import bind_executions
from tools.admission_evidence import source_snapshot
from tools.admission_junit import read_junit
from tools.candidate_ledger import create_ledger, export_tables
from tools.candidate_model import load_dimensions
from tools.native_vv_database import TABLES, copy_ledger
from tools.native_vv_inputs import current_inputs
from tools.native_vv_power10 import bind_power10

ROOT = Path(__file__).resolve().parents[1]


def test_native_transfer_preserves_every_candidate_and_failed_execution(tmp_path):
    source, target = tmp_path / "source.sqlite3", tmp_path / "target.duckdb"
    dimensions = load_dimensions(ROOT / "contracts/candidate_dimensions.json")
    create_ledger(dimensions, source, "a" * 64)
    tests = [
        {"test_id": row["test_id"], "outcome": "PASS"}
        for row in export_tables(source)["assertions"]
    ]
    tests[0]["outcome"] = "FAIL"
    execution = {
        "tests": tests,
        "method": "executed",
        "source_digest": "a" * 64,
        "run_id": "negative-transfer",
    }
    assert bind_executions(source, execution, "b" * 64)["status"] == "FAIL"
    with sqlite3.connect(source) as db:
        ddl = [
            db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
            for table in TABLES
        ]
    copy_ledger(source, target, ddl)
    with duckdb.connect(str(target), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 896
        assert db.execute("SELECT count(*) FROM executions WHERE outcome='FAIL'").fetchone()[0] == 1
    with pytest.raises(FileExistsError):
        copy_ledger(source, target, ddl)


def test_edited_passing_json_cannot_replace_failed_junit(tmp_path):
    root, admission = tmp_path / "root", tmp_path / "evidence"
    (root / "src").mkdir(parents=True)
    (root / "src/module.py").write_text("value = 1\n")
    admission.mkdir()
    source = source_snapshot(root)["source_digest"]
    (admission / "summary.json").write_text(
        json.dumps({"source_digest": source, "status": "PASS", "run_id": "tamper-check"})
    )
    xml = admission / "junit.xml"
    xml.write_text(
        '<testsuite><testcase classname="tests.test_one" name="test_one">'
        "<failure/></testcase></testsuite>"
    )
    measured = read_junit(xml, source, "tamper-check")
    measured["tests"][0]["outcome"] = "PASS"
    (admission / "test-execution.json").write_text(json.dumps(measured))
    with pytest.raises(ValueError, match="JUNIT_EXECUTION_BINDING_CHANGED"):
        current_inputs(SimpleNamespace(root=root, admission=admission))


def test_new_loop_site_cannot_inherit_old_bound_claim():
    observations = [{"path": "src/new.py", "ast_digest": "new", "rule": "P10-02"}]
    contract = {"bound_sites": [], "rules": {}}
    with pytest.raises(ValueError, match="SITE_INVENTORY_CHANGED"):
        bind_power10(observations, contract, [], {})


def test_failed_bound_witness_cannot_establish_power10():
    site = {
        "path": "src/new.py",
        "ast_digest": "same",
        "rule": "P10-02",
        "bound": "two iterations",
        "test_id": "observed-test",
    }
    contract = {"bound_sites": [site], "rules": {}}
    with pytest.raises(ValueError, match="BOUND_NOT_WITNESSED"):
        bind_power10([site], contract, [{"id": "observed-test", "passed": False}], {})
