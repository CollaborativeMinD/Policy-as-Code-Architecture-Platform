"""Export exact-source native V&V inputs; run as python -m tools.native_vv."""

import argparse
from pathlib import Path
import sys

from .admission_evidence import file_digest, source_snapshot, write_json
from .native_vv_analysis import fresh_analysis, observations
from .native_vv_database import add_families, copy_ledger
from .native_vv_inputs import current_inputs, native_executions, read
from .native_vv_power10 import bind_power10


def build(args):
    current = current_inputs(args)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.suite.resolve() / "src"))
    from hmt_policy.ledger_schema import DDL
    from hmt_policy.qualification import assess

    source = current["identity"]["source_digest"]
    database = args.output.resolve() / "candidate-space.duckdb"
    copy_ledger(args.admission / "candidate-space.sqlite3", database, DDL)
    families = read(args.root / "contracts/native_families.json")
    add_families(database, families, current["execution"])
    analyzer = fresh_analysis(args.root, args.output, args.analyzers_python, source)
    executions = native_executions(current["execution"])
    power10 = bind_power10(
        observations(args.root), read(args.root / "contracts/power10.json"), executions, analyzer
    )
    payload = {
        "source_digest": source,
        "database": str(database),
        "applicability": {},
        "claims": read(args.root / "contracts/native_claims.json"),
        "executions": executions,
        "manifest": current["manifest"],
        "execution": current["execution"],
        "languages": ["python"],
        "mutation": {"python": current["mutation"]},
        "coverage": {"python": current["coverage"]},
        "power10": {"python": power10},
    }
    if source_snapshot(args.root)["source_digest"] != source:
        raise ValueError("SOURCE_CHANGED_DURING_NATIVE_EXPORT")
    write_json(args.output / "qualification.json", payload)
    write_json(args.output / "test-manifest.json", current["manifest"])
    write_json(args.output / "test-execution.json", current["execution"])
    result = assess(payload)
    result.update(
        admission_run_id=current["summary"]["run_id"],
        native_schema_sha256=file_digest(args.suite / "src/hmt_policy/ledger_schema.py"),
        database_sha256=file_digest(database),
        mutation_sha256=file_digest(args.mutation),
    )
    write_json(args.output / "native-vv-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "suite", "admission", "mutation", "output", "analyzers-python"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.root.resolve()):
        raise ValueError("NATIVE_EVIDENCE_REQUIRES_EXTERNAL_ROOT")
    result = build(args)
    print(result["status"], result["source_digest"])
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
