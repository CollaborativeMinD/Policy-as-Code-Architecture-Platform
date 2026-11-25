"""Fresh scoped admission: python tools/admit.py --output /external/evidence/run-id."""

import argparse
import json
from pathlib import Path
import sys
import uuid

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.admission_campaign import bind_campaign, execute_tests
from tools.admission_evidence import check_traceability, source_snapshot, timestamp, write_json
from tools.admission_structure import check_structure
from tools.admission_refinements import check_refinements
from tools.candidate_ledger import create_ledger
from tools.candidate_model import load_dimensions


def observed_gate(name, action, output):
    try:
        result = action()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        result = {"status": "FAIL", "error_type": type(error).__name__, "reason": str(error)}
    write_json(output / (name + ".json"), result)
    return result


def campaign(root, output, timeout=600):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("EVIDENCE_REQUIRES_SEPARATE_ROOT")
    output.mkdir(parents=True, exist_ok=False)
    run_id = "pg-admission-" + uuid.uuid4().hex
    identity = source_snapshot(root)
    write_json(output / "source-before.json", identity)
    dimensions = load_dimensions(root / "contracts/candidate_dimensions.json")
    gates = {}
    gates["structure"] = observed_gate("structure", lambda: check_structure(root), output)
    gates["traceability"] = observed_gate(
        "traceability", lambda: check_traceability(root, dimensions), output
    )
    gates["refinements"] = observed_gate("refinements", lambda: check_refinements(root), output)
    gates["candidate_space"] = observed_gate(
        "candidate-space",
        lambda: create_ledger(
            dimensions, output / "candidate-space.sqlite3", identity["source_digest"]
        ),
        output,
    )
    process, stable = execute_tests(root, output, identity, timeout)
    gates["pytest"] = process
    gates["source_stability"] = {"status": "PASS" if stable else "FAIL"}
    gates["witnesses"] = observed_gate(
        "witnesses", lambda: bind_campaign(root, output, identity, run_id), output
    )
    result = {
        "status": "PASS" if all(g["status"] == "PASS" for g in gates.values()) else "FAIL",
        "run_id": run_id,
        "completed_at": timestamp(),
        "source_digest": identity["source_digest"],
        "gates": gates,
        "scope": "fresh software tests and explicit PostgreSQL branch contracts",
        "native_ci42": "Separate immutable 42-lane campaign; this runner does not replace it.",
        "promotion_authority": False,
    }
    write_json(output / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    result = campaign(args.root, args.output, args.timeout)
    print(json.dumps({key: result[key] for key in ("status", "run_id", "source_digest")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
