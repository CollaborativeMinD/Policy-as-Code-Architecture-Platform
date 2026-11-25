"""PG-ADMIT-004: exact test identity, current source, and nonpassing preservation."""

from pathlib import Path
import sqlite3
import pytest

from tools.admission_binding import bind_executions
from tools.admission_junit import node_id, read_junit
from tools.candidate_ledger import create_ledger, export_tables
from tools.candidate_model import load_dimensions
import xml.etree.ElementTree as ET


@pytest.fixture
def binding_data(tmp_path):
    root = Path(__file__).resolve().parents[1]
    dimensions = load_dimensions(root / "contracts/candidate_dimensions.json")
    path = tmp_path / "ledger.sqlite3"
    create_ledger(dimensions, path, "a" * 64)
    assertions = export_tables(path)["assertions"]
    execution = {
        "method": "executed",
        "source_digest": "a" * 64,
        "run_id": "observed-001",
        "tests": [{"test_id": row["test_id"], "outcome": "PASS"} for row in assertions],
    }
    return path, execution


def test_all_four_families_bind_to_current_source(binding_data):
    path, execution = binding_data
    observed = bind_executions(path, execution, "b" * 64)
    assert observed["status"] == "PASS"
    assert observed["assertions"] == len(execution["tests"])
    rows = export_tables(path)["executions"]
    assert all(row["source_digest"] == "a" * 64 for row in rows)
    assert all(row["evidence_digest"] == "b" * 64 for row in rows)


@pytest.mark.parametrize("outcome", ["FAIL", "SUPPRESSED", "MISSING"])
def test_failure_or_suppression_never_becomes_passing_evidence(binding_data, outcome):
    path, execution = binding_data
    execution["tests"][0]["outcome"] = outcome
    observed = bind_executions(path, execution, "b" * 64)
    assert observed["status"] == "FAIL"
    rows = export_tables(path)["executions"]
    assert any(row["outcome"] == "FAIL" for row in rows)


def test_absent_witness_is_retained_as_failed(binding_data):
    path, execution = binding_data
    removed = execution["tests"].pop()
    observed = bind_executions(path, execution, "b" * 64)
    assert removed["test_id"] in observed["missing_or_nonpassing"]


def test_old_source_evidence_rejected_before_insertion(binding_data):
    path, execution = binding_data
    execution["source_digest"] = "c" * 64
    with pytest.raises(ValueError, match="SOURCE_DRIFT"):
        bind_executions(path, execution, "b" * 64)
    assert not export_tables(path)["executions"]


def test_prior_witness_cannot_be_overwritten(binding_data):
    path, execution = binding_data
    bind_executions(path, execution, "b" * 64)
    with pytest.raises(sqlite3.IntegrityError):
        bind_executions(path, execution, "c" * 64)


def test_xml_preserves_skipped_and_failure_states(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text(
        '<testsuite><testcase classname="tests.test_one" name="test_ok"/>'
        '<testcase classname="tests.test_one" name="test_bad"><failure/>'
        '</testcase><testcase classname="tests.test_one" name="test_deferred">'
        "<skipped/></testcase></testsuite>"
    )
    report = read_junit(path, "a" * 64, "run-1")
    assert (report["passed"], report["failed"], report["suppressed"]) == (1, 1, 1)


def test_parametrized_id_is_preserved():
    node = ET.fromstring(
        '<testcase classname="tests.test_crossjoin_unit" '
        'file="tests/test_crossjoin_unit.py" name="test_candidate_unit[epoch_fence]"/>'
    )
    assert node_id(node) == "tests/test_crossjoin_unit.py::test_candidate_unit[epoch_fence]"


def test_xml_empty_discovery_cannot_pass(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_text("<testsuite/>")
    with pytest.raises(ValueError, match="POPULATION"):
        read_junit(path, "a" * 64, "run-1")
