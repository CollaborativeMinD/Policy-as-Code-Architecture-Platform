"""Mutation receipts cannot convert a timeout, fixture error, or wrong import into a kill."""

from pathlib import Path

import pytest

from tools.mutation_results import classify, junit_details, passed


def process(**changes):
    result = {
        "reason": "COMPLETE",
        "returncode": 1,
        "import_verified": True,
        "source_unchanged": True,
    }
    result.update(changes)
    return result


def details(**changes):
    result = {
        "valid": True,
        "tests": 1,
        "failures": 1,
        "assertion_failures": 1,
        "errors": 0,
        "skipped": 0,
    }
    result.update(changes)
    return result


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"reason": "PROCESS_TIMEOUT"}, "timeout"),
        ({"reason": "PROCESS_OUTPUT_LIMIT"}, "unviable"),
        ({"returncode": 3}, "unviable"),
        ({"import_verified": False}, "unviable"),
        ({"source_unchanged": False}, "unviable"),
    ],
)
def test_process_failure_is_never_caught(change, expected):
    assert classify(process(**change), details()) == expected


@pytest.mark.parametrize(
    "change", [{"valid": False}, {"errors": 1}, {"skipped": 1}, {"assertion_failures": 0}]
)
def test_nonassertion_results_are_unviable(change):
    assert classify(process(), details(**change)) == "unviable"


def test_only_assertion_failures_count_as_caught():
    assert classify(process(), details()) == "caught"
    clean = details(failures=0, assertion_failures=0)
    assert classify(process(returncode=0), clean) == "missed"
    assert passed(process(returncode=0), clean)
    assert not passed(process(), details())


def test_junit_distinguishes_runtime_failure_from_fixture_error(tmp_path):
    path = Path(tmp_path) / "report.xml"
    path.write_text(
        '<testsuites><testsuite><testcase classname="tests.test_guard" name="test_one">'
        '<failure message="assert 1 == 2">AssertionError</failure></testcase>'
        "</testsuite></testsuites>"
    )
    result = junit_details(path)
    assert result["assertion_failures"] == 1 and result["errors"] == 0
    assert result["test_ids"] == ["tests/test_guard.py::test_one"]
    path.write_text(path.read_text().replace("failure", "error"))
    result = junit_details(path)
    assert result["assertion_failures"] == 0 and result["errors"] == 1
    path.write_text("<!DOCTYPE forged><testsuites/>")
    assert not junit_details(path)["valid"]
    assert not junit_details(tmp_path / "absent.xml")["valid"]
