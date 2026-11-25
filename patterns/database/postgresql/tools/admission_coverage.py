"""PG-ADMIT-002: pure branch coverage over every delivered production module."""

from pathlib import Path


def expected_sources(root):
    return {
        path.relative_to(root).as_posix() for path in (root / "src/hmt_pg_patterns").rglob("*.py")
    }


def normalize_source(name, root):
    path = Path(name)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("COVERAGE_SOURCE_ESCAPE")
    return resolved.relative_to(root).as_posix()


def summary_counts(summary):
    fields = ("num_statements", "covered_lines", "num_branches", "covered_branches")
    values = tuple(summary[name] for name in fields)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("COVERAGE_INVALID_COUNTS")
    statements, lines, branches, covered = values
    if lines > statements or covered > branches:
        raise ValueError("COVERAGE_INCONSISTENT_COUNTS")
    return values


def check_coverage(report, root):
    root = Path(root).resolve()
    if report.get("meta", {}).get("branch_coverage") is not True:
        raise ValueError("BRANCH_MEASUREMENT_REQUIRED")
    observed = {
        normalize_source(name, root): row["summary"] for name, row in report["files"].items()
    }
    expected = expected_sources(root)
    if not expected or set(observed) != expected or len(observed) != len(report["files"]):
        raise ValueError("COVERAGE_SOURCE_POPULATION_MISMATCH")
    counts = [summary_counts(summary) for summary in observed.values()]
    statements, lines, branches, covered = map(sum, zip(*counts))
    if branches == 0:
        raise ValueError("BRANCH_POPULATION_EMPTY")
    percent = 100 * covered / branches
    line_percent = 100 * lines / statements if statements else 100
    return {
        "status": "PASS" if percent >= 90 and line_percent >= 90 else "FAIL",
        "branch_percent": percent,
        "minimum_branch_percent": 90,
        "covered_branches": covered,
        "num_branches": branches,
        "line_percent": line_percent,
        "minimum_line_percent": 90,
        "covered_lines": lines,
        "num_statements": statements,
        "scope": "all delivered src/hmt_pg_patterns/*.py, recursively",
        "tooling_scope": "independent admission tool tests and structural checks",
        "files": len(observed),
    }
