"""PG-ADMIT-003: candidate-space completeness, exclusions, and immutable history."""

from copy import deepcopy
from pathlib import Path
import sqlite3
import pytest

from tools.candidate_ledger import check_ledger, create_ledger, export_tables
from tools.candidate_model import load_dimensions, validate_dimensions

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def dimensions():
    return load_dimensions(ROOT / "contracts/candidate_dimensions.json")


def test_full_cartesian_population_and_explicit_exclusions(tmp_path, dimensions):
    path = tmp_path / "candidates.sqlite3"
    report = create_ledger(dimensions, path, "a" * 64)
    expected = (
        len(dimensions["invariants"]) * len(dimensions["failure_modes"]) * len(dimensions["gates"])
    )
    assert report["status"] == "PASS"
    assert report["candidate_count"] == report["expected_count"] == expected
    assert report["applicable"] == len(dimensions["cases"])
    assert report["not_applicable"] + report["applicable"] == expected
    tables = export_tables(path)
    assert len(tables["predicates"]) == report["not_applicable"]
    assert all(row["reason"].endswith("== false") for row in tables["predicates"])


def test_history_cannot_be_overwritten_or_deleted(tmp_path, dimensions):
    path = tmp_path / "candidates.sqlite3"
    create_ledger(dimensions, path, "a" * 64)
    with pytest.raises(FileExistsError, match="PRESERVED"):
        create_ledger(dimensions, path, "b" * 64)
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
            db.execute("DELETE FROM candidates")
        with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
            db.execute("UPDATE candidates SET status='PENDING'")


def test_corrupted_candidate_population_is_detected(tmp_path, dimensions):
    path = tmp_path / "candidates.sqlite3"
    create_ledger(dimensions, path, "a" * 64)
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER freeze_candidates_DELETE")
        db.execute("DELETE FROM candidates WHERE id=1")
    assert check_ledger(path)["status"] == "FAIL"


def test_duplicate_dimensions_fail_before_materialization(dimensions):
    dimensions["invariants"].append(deepcopy(dimensions["invariants"][0]))
    with pytest.raises(ValueError, match="DUPLICATE_DIMENSION"):
        validate_dimensions(dimensions)


def test_ambiguous_case_cannot_hide_exclusions(dimensions):
    dimensions["cases"].append(deepcopy(dimensions["cases"][0]))
    with pytest.raises(ValueError, match="AMBIGUOUS_APPLICABILITY"):
        validate_dimensions(dimensions)


def test_candidate_resource_limit_cannot_be_silently_truncated(dimensions):
    dimensions["bounds"]["max_candidate_rows"] = 2
    with pytest.raises(ValueError, match="CROSS_JOIN_RESOURCE_BOUND"):
        validate_dimensions(dimensions)


def test_missing_family_obligation_is_rejected(dimensions):
    dimensions["cases"][0]["families"] = ["unit"]
    with pytest.raises(ValueError, match="FAMILIES"):
        validate_dimensions(dimensions)


def test_uncovered_declared_failure_relation_is_rejected(dimensions):
    dimensions["invariants"][0]["failure_modes"].append("FM-REPLAY")
    with pytest.raises(ValueError, match="RELATION_UNCOVERED"):
        validate_dimensions(dimensions)


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / "dimensions.json"
    path.write_text('{"schema_id":"one","schema_id":"two"}')
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        load_dimensions(path)
