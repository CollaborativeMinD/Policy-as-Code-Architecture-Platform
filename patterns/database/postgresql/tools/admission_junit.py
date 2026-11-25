"""Bind native pytest XML to exact test identities; suppression never becomes PASS."""

from pathlib import Path
import xml.etree.ElementTree as ET


def node_id(testcase):
    classname = testcase.get("classname", "")
    filename = testcase.get("file")
    parts = classname.split(".")
    if filename:
        marker = Path(filename).stem
        classes = parts[parts.index(marker) + 1 :] if marker in parts else []
    else:
        module_end = max(
            (i for i, part in enumerate(parts) if part.startswith("test_")), default=len(parts) - 1
        )
        filename = "/".join(parts[: module_end + 1]) + ".py"
        classes = parts[module_end + 1 :]
    return "::".join([filename, *classes, testcase.get("name", "")])


def read_junit(path, source_digest, run_id):
    raw = Path(path).read_bytes()
    if len(raw) > 8388608 or b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("JUNIT_INPUT_BOUND")
    root = ET.fromstring(raw)
    tests, seen = [], set()
    for node in root.iter("testcase"):
        identity = node_id(node)
        if identity in seen:
            raise ValueError("DUPLICATE_EXECUTED_TEST_ID")
        seen.add(identity)
        outcome = "PASS"
        if node.find("skipped") is not None:
            outcome = "SUPPRESSED"
        elif node.find("failure") is not None or node.find("error") is not None:
            outcome = "FAIL"
        tests.append(
            {"test_id": identity, "outcome": outcome, "seconds": float(node.get("time", "0"))}
        )
    if not tests or len(tests) > 10000:
        raise ValueError("EXECUTED_TEST_POPULATION_BOUND")
    return {
        "method": "executed",
        "source_digest": source_digest,
        "run_id": run_id,
        "tests": tests,
        "passed": sum(row["outcome"] == "PASS" for row in tests),
        "failed": sum(row["outcome"] == "FAIL" for row in tests),
        "suppressed": sum(row["outcome"] == "SUPPRESSED" for row in tests),
    }
