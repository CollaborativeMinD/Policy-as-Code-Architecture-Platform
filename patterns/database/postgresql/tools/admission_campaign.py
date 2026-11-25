"""Fresh subprocess execution and exact-source-bound PostgreSQL branch evidence."""

import json
import os
import sys

from .admission_binding import bind_executions
from .admission_causal import attach_causal
from .admission_coverage import check_coverage
from .admission_evidence import file_digest, source_snapshot, write_json
from .admission_junit import read_junit
from .admission_harness import harness_identity
from .admission_process import run_command
from .admission_refinements import full_test_manifest, read_registry
from .candidate_ledger import export_tables
from .candidate_model import load_dimensions


def pytest_command(root, output):
    return [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--import-mode=importlib",
        "-p",
        "pytest_cov.plugin",
        "-p",
        "pytest_asyncio.plugin",
        "-o",
        "junit_family=xunit1",
        "--cov=hmt_pg_patterns",
        "--cov-branch",
        "--cov-report=json:" + str(output / "coverage.json"),
        "--junitxml=" + str(output / "junit.xml"),
        str(root / "tests"),
    ]


def execute_tests(root, output, identity, timeout):
    harness = harness_identity()
    write_json(output / "harness-before.json", harness)
    environment = dict(os.environ)
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        HMT_EVIDENCE_DIR=str(output),
        COVERAGE_FILE=str(output / ".coverage"),
    )
    process = run_command(pytest_command(root, output), root, output, environment, timeout)
    write_json(output / "pytest-process.json", process)
    after = source_snapshot(root)
    stable = identity["source_digest"] == after["source_digest"]
    harness_after = harness_identity()
    stable = stable and harness_after == harness
    write_json(output / "harness-after.json", harness_after)
    write_json(output / "source-after.json", after)
    return process, stable


def bind_campaign(root, output, identity, run_id):
    measured = read_junit(output / "junit.xml", identity["source_digest"], run_id)
    measured["evidence_digest"] = file_digest(output / "junit.xml")
    write_json(output / "test-execution.json", measured)
    registry = read_registry(root)
    dimensions = load_dimensions(root / "contracts/candidate_dimensions.json")
    write_json(output / "test-manifest.json", full_test_manifest(measured, registry, dimensions))
    bound = bind_executions(
        output / "candidate-space.sqlite3", measured, measured["evidence_digest"]
    )
    write_json(output / "crossjoin-manifest.json", bound.pop("manifest"))
    write_json(output / "crossjoin-execution.json", bound.pop("execution"))
    write_json(output / "candidate-binding.json", bound)
    causal = attach_causal(
        output / "candidate-space.sqlite3", measured, registry, measured["evidence_digest"]
    )
    write_json(output / "causal-binding.json", causal)
    write_json(
        output / "candidate-space-native.json", export_tables(output / "candidate-space.sqlite3")
    )
    coverage = check_coverage(json.loads((output / "coverage.json").read_text()), root)
    write_json(output / "branch-coverage.json", coverage)
    clear = measured["failed"] == 0 and measured["suppressed"] == 0
    return {
        "status": "PASS"
        if clear and bound["status"] == coverage["status"] == causal["status"] == "PASS"
        else "FAIL",
        "test_count": len(measured["tests"]),
        "test_binding": bound,
        "coverage": coverage,
        "causal": causal,
        "junit_sha256": measured["evidence_digest"],
    }
