"""Bounded isolated mutations, assertion witnesses, and observed source restoration."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from .admission_evidence import file_digest, source_snapshot, timestamp, write_json
from .mutation_execution import run_pytest
from .mutation_python import MUTATIONS as PYTHON_MUTATIONS
from .mutation_results import classify, passed
from .mutation_sql import MUTATIONS as SQL_MUTATIONS
from .mutation_storage import apply_mutation, freeze_source, mutation_path

MUTATIONS = tuple(sorted(PYTHON_MUTATIONS + SQL_MUTATIONS, key=lambda item: item.identifier))


def run_mutant(baseline, workspace, output, mutation, timeout):
    """Mutate one copy, execute its witness, restore exact bytes, and rerun that witness."""
    root, folder = workspace / mutation.identifier, output / mutation.identifier
    original_snapshot = freeze_source(baseline, root)
    folder.mkdir(exist_ok=False)
    path = mutation_path(root, mutation.patch)
    original, application_error = path.read_bytes(), None
    try:
        try:
            apply_mutation(root, mutation, folder)
        except (ValueError, SyntaxError) as error:
            application_error = {"type": type(error).__name__, "reason": str(error)}
            write_json(folder / "application_error.json", application_error)
        process, details = run_pytest(root, folder / "mutated", [mutation.selector], timeout)
        outcome = "unviable" if application_error else classify(process, details)
    finally:
        mutation_path(root, mutation.patch).write_bytes(original)
    restored_snapshot = source_snapshot(root)
    restoration, restored_tests = run_pytest(
        root, folder / "restored", [mutation.selector], timeout
    )
    restored = restored_snapshot["files"] == original_snapshot["files"]
    restored = restored and passed(restoration, restored_tests)
    if not restored:
        outcome = "unviable"
    receipt = {
        "id": mutation.identifier,
        "requirement": mutation.requirement,
        "path": mutation.patch.path,
        "selector": mutation.selector,
        "outcome": outcome,
        "source_digest": original_snapshot["source_digest"],
        "mutated_source_digest": process["source_digest"],
        "restored_source_digest": restored_snapshot["source_digest"],
        "restoration_observed": restored,
        "restored_file_sha256": file_digest(path),
        "application_error": application_error,
        "mutation_process": process,
        "mutation_tests": details,
        "restoration_process": restoration,
        "restoration_tests": restored_tests,
    }
    write_json(folder / "receipt.json", receipt)
    return receipt


def campaign(root, output, timeout=90):
    """Export native mutation counts without treating timeout or startup failure as a kill."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 120:
        raise ValueError("MUTATION_TIMEOUT_BOUND")
    root, output = Path(root).resolve(), Path(output).resolve()
    if any(
        output.is_relative_to(root / name) for name in ("src", "tests", "tools", "sql", "contracts")
    ):
        raise ValueError("EVIDENCE_MUST_NOT_OVERLAP_SOURCE")
    output.mkdir(parents=True, exist_ok=False)
    started = timestamp()
    snapshot = freeze_source(root, output / "baseline_source")
    write_json(output / "source_snapshot.json", snapshot)
    selectors = sorted({mutation.selector for mutation in MUTATIONS})
    baseline, tests = run_pytest(
        output / "baseline_source", output / "baseline", selectors, timeout
    )
    with TemporaryDirectory(prefix="hmt-pg-mutations-") as workspace:
        results = [
            run_mutant(output / "baseline_source", Path(workspace), output, mutant, timeout)
            for mutant in MUTATIONS
        ]
    baseline_passed = passed(baseline, tests)
    if not baseline_passed:
        for result in results:
            result["outcome"] = "unviable"
    counts = {
        name: sum(row["outcome"] == name for row in results)
        for name in ("missed", "caught", "timeout", "unviable")
    }
    unchanged = source_snapshot(root)["files"] == snapshot["files"]
    all_caught = baseline_passed and counts["caught"] == len(MUTATIONS)
    report = {
        "schema": "hmt-native-mutation-evidence-v1",
        "source_digest": snapshot["source_digest"],
        "status": "PASS" if all_caught and unchanged else "FAIL",
        "start_time": started,
        "end_time": timestamp(),
        "total_mutants": len(MUTATIONS),
        **counts,
        "all_mutants_caught": all_caught,
        "source_unchanged": unchanged,
        "baseline_passed": baseline_passed,
        "baseline_process": baseline,
        "baseline_tests": tests,
        "results": results,
    }
    write_json(output / "mutation-report.json", report)
    return report


def main():
    """Require a fresh evidence directory; invoke as python -m tools.mutation_campaign."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    report = campaign(args.root, args.output, args.timeout)
    print(
        f"{report['status']}: {report['caught']}/{report['total_mutants']} caught; "
        f"missed={report['missed']} timeout={report['timeout']} unviable={report['unviable']}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
