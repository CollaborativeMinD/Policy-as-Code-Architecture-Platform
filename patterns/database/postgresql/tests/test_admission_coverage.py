"""PG-ADMIT-002: branch-only threshold and complete production population."""

from copy import deepcopy
import pytest

from tools.admission_coverage import check_coverage, summary_counts


@pytest.fixture
def measured(tmp_path):
    path = tmp_path / "src/hmt_pg_patterns"
    path.mkdir(parents=True)
    (path / "unit.py").write_text("def decision(x):\n    return x if x else 0\n")
    return {
        "meta": {"branch_coverage": True},
        "files": {
            "src/hmt_pg_patterns/unit.py": {
                "summary": {
                    "num_statements": 1000,
                    "covered_lines": 1000,
                    "num_branches": 10,
                    "covered_branches": 9,
                }
            }
        },
    }


def test_pure_branch_gate_cannot_hide_behind_lines(tmp_path, measured):
    measured["files"]["src/hmt_pg_patterns/unit.py"]["summary"]["covered_branches"] = 8
    observed = check_coverage(measured, tmp_path)
    assert observed["line_percent"] == 100
    assert observed["branch_percent"] == 80
    assert observed["status"] == "FAIL"


def test_exact_ninety_percent_is_accepted(tmp_path, measured):
    assert check_coverage(measured, tmp_path)["status"] == "PASS"


def test_missing_module_is_not_dropped_from_denominator(tmp_path, measured):
    (tmp_path / "src/hmt_pg_patterns/untested.py").write_text("value = 1\n")
    with pytest.raises(ValueError, match="POPULATION"):
        check_coverage(measured, tmp_path)


@pytest.mark.parametrize("instrumented", [False, None, "true", 1])
def test_instrumentation_must_be_explicit_boolean(tmp_path, measured, instrumented):
    measured["meta"]["branch_coverage"] = instrumented
    with pytest.raises(ValueError, match="BRANCH_MEASUREMENT"):
        check_coverage(measured, tmp_path)


def test_duplicate_normalized_paths_cannot_replace_a_module(tmp_path, measured):
    measured["files"]["./src/hmt_pg_patterns/unit.py"] = deepcopy(
        measured["files"]["src/hmt_pg_patterns/unit.py"]
    )
    with pytest.raises(ValueError, match="POPULATION"):
        check_coverage(measured, tmp_path)


def test_escaping_coverage_path_rejected(tmp_path, measured):
    measured["files"]["../outside.py"] = measured["files"].pop("src/hmt_pg_patterns/unit.py")
    with pytest.raises(ValueError, match="SOURCE_ESCAPE"):
        check_coverage(measured, tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"covered_branches": True},
        {"num_branches": -1},
        {"covered_branches": 11},
        {"covered_lines": 1001},
    ],
)
def test_impossible_counts_rejected(change):
    summary = {
        "num_statements": 1000,
        "covered_lines": 1000,
        "num_branches": 10,
        "covered_branches": 9,
    } | change
    with pytest.raises(ValueError, match="COVERAGE_"):
        summary_counts(summary)


def test_zero_branch_population_is_not_vacuous_admission(tmp_path, measured):
    summary = measured["files"]["src/hmt_pg_patterns/unit.py"]["summary"]
    summary.update(num_branches=0, covered_branches=0)
    with pytest.raises(ValueError, match="BRANCH_POPULATION_EMPTY"):
        check_coverage(measured, tmp_path)


def test_lines_and_branches_have_independent_thresholds(tmp_path, measured):
    measured["files"]["src/hmt_pg_patterns/unit.py"]["summary"]["covered_lines"] = 899
    assert check_coverage(measured, tmp_path)["status"] == "FAIL"
