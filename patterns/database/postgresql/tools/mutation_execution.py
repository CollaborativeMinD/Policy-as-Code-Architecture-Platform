"""Every phase launches real pytest with bounded process time and captured output."""

import json
import os
from pathlib import Path
import sys

from .admission_evidence import source_snapshot, write_json
from .admission_process import run_command
from .mutation_results import junit_details


def run_pytest(root, folder, selectors, timeout):
    """Bind interpreter imports, process output, and JUnit to the exact isolated tree."""
    root, folder = Path(root).resolve(), Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    snapshot = source_snapshot(root)
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_CURRENT_TEST", None)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join(
                str(root / name) for name in ("src", ".", "tests", "tools")
            ),
            "HMT_MUTATION_SOURCE_DIR": str(root),
            "HMT_MUTATION_SOURCE_DIGEST": snapshot["source_digest"],
            "HMT_MUTATION_EVIDENCE": str(folder),
            "HMT_EVIDENCE_DIR": str(folder),
        }
    )
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-o",
        "addopts=",
        "-p",
        "tools.mutation_probe",
        "--junitxml=" + str(folder / "junit.xml"),
        *selectors,
    ]
    process = run_command(argv, root, folder, environment, timeout)
    receipt = folder / "runtime_source.json"
    process["import_verified"] = (
        receipt.exists()
        and json.loads(receipt.read_text()).get("source_digest") == snapshot["source_digest"]
    )
    process["source_unchanged"] = source_snapshot(root)["files"] == snapshot["files"]
    process["source_digest"] = snapshot["source_digest"]
    details = junit_details(folder / "junit.xml")
    write_json(folder / "process.json", process)
    write_json(folder / "junit_summary.json", details)
    return process, details
