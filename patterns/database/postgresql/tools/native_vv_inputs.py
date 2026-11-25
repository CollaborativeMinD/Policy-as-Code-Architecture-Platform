"""Reject stale, edited, or incomplete admission inputs before native qualification."""

import json
from pathlib import Path

from .admission_evidence import file_digest, source_snapshot
from .admission_junit import read_junit
from .admission_refinements import full_test_manifest, read_registry
from .candidate_model import load_dimensions


def read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 33554432:
        raise ValueError("NATIVE_EVIDENCE_INPUT_BOUND")
    return json.loads(path.read_text())


def current_inputs(args):
    root, admission = args.root.resolve(), args.admission.resolve()
    identity = source_snapshot(root)
    summary = read(admission / "summary.json")
    if summary["source_digest"] != identity["source_digest"]:
        raise ValueError("ADMISSION_SOURCE_NOT_CURRENT")
    if summary["status"] != "PASS":
        raise ValueError("ADMISSION_NOT_PASSED")
    measured = read(admission / "test-execution.json")
    reparsed = read_junit(admission / "junit.xml", identity["source_digest"], summary["run_id"])
    reparsed["evidence_digest"] = file_digest(admission / "junit.xml")
    if measured != reparsed:
        raise ValueError("JUNIT_EXECUTION_BINDING_CHANGED")
    if measured["source_digest"] != identity["source_digest"]:
        raise ValueError("EXECUTION_SOURCE_NOT_CURRENT")
    mutation = read(args.mutation)
    if mutation["source_digest"] != identity["source_digest"]:
        raise ValueError("MUTATION_SOURCE_NOT_CURRENT")
    if not mutation.get("source_unchanged") or not mutation.get("baseline_passed"):
        raise ValueError("MUTATION_BASELINE_NOT_ESTABLISHED")
    manifest = full_test_manifest(
        measured, read_registry(root), load_dimensions(root / "contracts/candidate_dimensions.json")
    )
    if read(admission / "test-manifest.json") != manifest:
        raise ValueError("TEST_MANIFEST_CHANGED")
    return {
        "identity": identity,
        "execution": measured,
        "mutation": mutation,
        "manifest": manifest,
        "coverage": read(admission / "coverage.json"),
        "summary": summary,
    }


def native_executions(execution):
    return [
        {
            "id": row["test_id"],
            "test_id": row["test_id"],
            "method": "executed",
            "source_digest": execution["source_digest"],
            "passed": row["outcome"] == "PASS",
            "actual": "ASSERTIONS_PASSED" if row["outcome"] == "PASS" else row["outcome"],
        }
        for row in execution["tests"]
    ]
