"""A collected assertion failure is distinct from timeout, startup, or fixture failure."""

from pathlib import Path
import xml.etree.ElementTree as ET

from .admission_junit import node_id


def _failure_text(node):
    return " ".join((node.get("message", ""), node.text or ""))


def junit_details(path):
    """Parse only bounded local pytest XML and retain exact executed identities."""
    path = Path(path)
    if not path.exists():
        return {"valid": False, "reason": "MISSING_JUNIT"}
    raw = path.read_bytes()
    if len(raw) > 8388608 or b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return {"valid": False, "reason": "INVALID_JUNIT_BOUND"}
    root = ET.fromstring(raw)
    cases = list(root.iter("testcase"))
    if not 0 < len(cases) <= 10000:
        return {"valid": False, "reason": "INVALID_JUNIT_POPULATION"}
    failures = [node for case in cases for node in case.findall("failure")]
    assertions = sum(
        "AssertionError" in _failure_text(node)
        or "Failed: DID NOT RAISE" in _failure_text(node)
        or node.get("message", "").startswith("assert ")
        for node in failures
    )
    return {
        "valid": True,
        "tests": len(cases),
        "failures": len(failures),
        "assertion_failures": assertions,
        "errors": sum(len(case.findall("error")) for case in cases),
        "skipped": sum(len(case.findall("skipped")) for case in cases),
        "test_ids": [node_id(case) for case in cases],
    }


def classify(process, details):
    """Only real assertion failures in viable pytest runs count as caught mutants."""
    if process["reason"] == "PROCESS_TIMEOUT":
        return "timeout"
    valid = details.get("valid", False) and process["reason"] == "COMPLETE"
    valid = valid and process["import_verified"] and process["source_unchanged"]
    if not valid or details["errors"] or details["skipped"]:
        return "unviable"
    if process["returncode"] == 0 and not details["failures"]:
        return "missed"
    if (
        process["returncode"] == 1
        and details["failures"] > 0
        and details["failures"] == details["assertion_failures"]
    ):
        return "caught"
    return "unviable"


def passed(process, details):
    """A baseline or restoration must execute cleanly with no suppressed tests."""
    return classify(process, details) == "missed"
