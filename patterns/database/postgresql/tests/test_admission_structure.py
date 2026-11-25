"""PG-ADMIT-001: threshold edges, suppression, and malformed-source attacks."""

import ast
import pytest

from tools.admission_structure import band, check_structure, function_metrics, suppressed


@pytest.mark.parametrize(
    "count,expected",
    [
        (44, "NOMINAL"),
        (45, "WATCH"),
        (49, "WATCH"),
        (50, "REFACTOR_REQUIRED"),
        (59, "REFACTOR_REQUIRED"),
        (60, "BLOCK"),
        (61, "BLOCK"),
    ],
)
def test_function_policy_boundaries(count, expected):
    assert band(count, True) == expected


@pytest.mark.parametrize(
    "count,expected",
    [
        (99, "NOMINAL"),
        (100, "WATCH"),
        (149, "WATCH"),
        (150, "REFACTOR_REQUIRED"),
        (179, "REFACTOR_REQUIRED"),
        (180, "BLOCK"),
        (181, "BLOCK"),
    ],
)
def test_module_policy_boundaries(count, expected):
    assert band(count) == expected


def make_source(tmp_path, text):
    source = tmp_path / "src/unit.py"
    source.parent.mkdir(exist_ok=True)
    source.write_text(text)
    return source


def test_exact_limit_is_not_legacy_off_by_one(tmp_path):
    make_source(tmp_path, "number = 1\n" * 180)
    observed = check_structure(tmp_path)
    assert observed["status"] == "FAIL"
    assert observed["errors"][0]["reason"] == "MODULE_LOC_BLOCK"


def test_function_refactor_band_denies_further_responsibility(tmp_path):
    make_source(tmp_path, "def work():\n" + "    number = 1\n" * 49)
    assert check_structure(tmp_path)["status"] == "FAIL"


def test_empty_source_and_parse_error_fail_closed(tmp_path):
    assert check_structure(tmp_path)["status"] == "FAIL"
    make_source(tmp_path, "def broken(:\n")
    assert check_structure(tmp_path)["errors"][0]["reason"] == "SyntaxError"


@pytest.mark.parametrize(
    "source",
    [
        "import pytest\npytest.skip('reason')",
        "from pytest import xfail as defer\ndefer('reason')",
        "import unittest\n@unittest.skipIf(True, 'reason')\ndef check(): pass",
    ],
)
def test_suppression_aliases_are_observed(source):
    assert suppressed(ast.parse(source))


def test_literal_error_names_are_not_suppression():
    assert not suppressed(ast.parse("text = 'skip and xfail are forbidden'"))


def test_argument_and_control_depth_measurements(tmp_path):
    text = "def work(a,b,c,d,e,f):\n"
    text += "".join("    " * index + "if True:\n" for index in range(1, 7))
    text += "    " * 7 + "return 0\n"
    make_source(tmp_path, text)
    observed = check_structure(tmp_path)
    assert any("ARGUMENT_OR_NESTING" in row["reason"] for row in observed["errors"])


def test_method_self_is_not_a_callers_argument():
    node = ast.parse("def work(self, one):\n    return one").body[0]
    assert function_metrics(node)["arguments"] == 1


def test_linked_source_is_rejected(tmp_path):
    original = tmp_path / "outside.py"
    original.write_text("value = 1\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/alias.py").symlink_to(original)
    assert check_structure(tmp_path)["status"] == "FAIL"
