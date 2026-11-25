"""PG-ADMIT-007: unknown source/test contracts and missing causal experiments fail."""

from copy import deepcopy
import json
from pathlib import Path
import pytest

from tools.admission_causal import attach_causal
from tools.admission_evidence import source_snapshot
from tools.admission_refinements import check_refinements, full_test_manifest, read_registry
from tools.candidate_ledger import check_ledger, create_ledger, export_tables
from tools.candidate_model import load_dimensions

ROOT = Path(__file__).resolve().parents[1]


def test_unmapped_executed_test_cannot_be_discarded():
    registry = read_registry(ROOT)
    dimensions = load_dimensions(ROOT / "contracts/candidate_dimensions.json")
    execution = {"tests": [{"test_id": "tests/test_unknown.py::test_new", "outcome": "PASS"}]}
    with pytest.raises(ValueError, match="HAS_NO_REQUIREMENT"):
        full_test_manifest(execution, registry, dimensions)


def test_new_runtime_file_requires_explicit_refinement(tmp_path):
    (tmp_path / "contracts").mkdir()
    (tmp_path / "src/hmt_pg_patterns").mkdir(parents=True)
    (tmp_path / "src/hmt_pg_patterns/new.py").write_text('"""PG-UNKNOWN-001."""\n')
    registry = {"source_files": {}, "test_files": {}, "public_contracts": {}}
    (tmp_path / "contracts/contract_refinements.json").write_text(json.dumps(registry))
    result = check_refinements(tmp_path)
    assert result["status"] == "FAIL"
    assert result["unmapped_public_contracts"] == ["PG-UNKNOWN-001"]


@pytest.fixture
def causal_ledger(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    create_ledger(load_dimensions(ROOT / "contracts/candidate_dimensions.json"), path, "a" * 64)
    registry = read_registry(ROOT)
    execution = {
        "source_digest": "a" * 64,
        "run_id": "observed-causal",
        "method": "executed",
        "tests": [
            {"test_id": identity, "outcome": "PASS"}
            for edge in registry["causal_edges"]
            for identity in edge["tests"].values()
        ],
    }
    return path, registry, execution


def test_all_distinct_causal_experiments_extend_complete_ledger(causal_ledger):
    path, registry, execution = causal_ledger
    assert attach_causal(path, execution, registry, "b" * 64)["status"] == "PASS"
    assert check_ledger(path)["status"] == "PASS"
    assert len(export_tables(path)["causal_witnesses"]) == 20


def test_missing_causal_execution_is_retained_as_failure(causal_ledger):
    path, registry, execution = causal_ledger
    execution["tests"].pop()
    result = attach_causal(path, execution, registry, "b" * 64)
    assert result["status"] == "FAIL"
    assert any(row["outcome"] == "FAIL" for row in export_tables(path)["executions"])


def test_old_causal_source_and_omitted_experiment_are_rejected(causal_ledger):
    path, registry, execution = causal_ledger
    stale = deepcopy(execution)
    stale["source_digest"] = "c" * 64
    with pytest.raises(ValueError, match="SOURCE_DRIFT"):
        attach_causal(path, stale, registry, "b" * 64)
    registry["causal_edges"][0]["tests"].pop("alternate_path")
    with pytest.raises(ValueError, match="EXPERIMENT_POPULATION"):
        attach_causal(path, execution, registry, "b" * 64)
    assert not export_tables(path)["executions"]


def test_qualification_code_changes_bound_source_identity(tmp_path):
    path = tmp_path / "qualification/native_worker_test.py"
    path.parent.mkdir()
    path.write_text("flag = 1\n")
    before = source_snapshot(tmp_path)["source_digest"]
    path.write_text("flag = 2\n")
    assert source_snapshot(tmp_path)["source_digest"] != before
