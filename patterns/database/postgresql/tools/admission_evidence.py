"""Source identity and append-only receipts for one fresh engineering test run."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .candidate_ledger import canonical_digest


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def inventory_paths(root):
    paths = []
    excluded = {"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", "upstream-snapshots"}
    for directory in (
        "src",
        "tests",
        "tools",
        "contracts",
        "sql",
        "qualification",
        "fixtures",
        "deployment",
        "references",
    ):
        for path in (root / directory).rglob("*"):
            if excluded.intersection(path.parts):
                continue
            if path.is_symlink():
                raise ValueError("SOURCE_LINK_NOT_ADMITTED")
            if path.is_file() and path.suffix != ".pyc":
                paths.append(path)
    paths.extend(
        root / name
        for name in ("pyproject.toml", "uv.lock", ".python-version")
        if (root / name).exists()
    )
    if not paths or len(paths) > 4096:
        raise ValueError("SOURCE_POPULATION_BOUND")
    return sorted(paths)


def source_snapshot(root):
    root = Path(root).resolve()
    files, total = {}, 0
    for path in inventory_paths(root):
        size = path.stat().st_size
        total += size
        if size > 2097152 or total > 16777216:
            raise ValueError("SOURCE_BYTES_BOUND")
        files[path.relative_to(root).as_posix()] = file_digest(path)
    return {
        "source_digest": canonical_digest(files),
        "files": files,
        "total_bytes": total,
        "measured_at": timestamp(),
        "scope": [
            "src",
            "tests",
            "tools",
            "contracts",
            "sql",
            "qualification",
            "fixtures",
            "deployment",
            "references",
            "pyproject.toml",
            "uv.lock",
            ".python-version",
        ],
    }


def check_traceability(root, dimensions):
    path = Path(root) / "contracts/traceability.json"
    trace = json.loads(path.read_text())
    rows = trace["requirements"]
    expected = {row["id"] for row in dimensions["invariants"]}
    errors = []
    if {row["id"] for row in rows} != expected or len(rows) != len(expected):
        errors.append("REQUIREMENT_INVENTORY_MISMATCH")
    for row in rows:
        cases = {case["id"] for case in dimensions["cases"] if case["invariant_id"] == row["id"]}
        if cases != set(row["case_ids"]):
            errors.append("CASE_REQUIREMENT_MISMATCH:" + row["id"])
        if not row["source_refs"]:
            errors.append("SOURCE_MAPPING_MISSING:" + row["id"])
        for reference in row["source_refs"]:
            source = (Path(root) / reference).resolve()
            if not source.is_relative_to(Path(root).resolve()) or not source.is_file():
                errors.append("SOURCE_REFERENCE_INVALID:" + reference)
    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "requirements": len(rows),
        "traceability_sha256": file_digest(path),
    }
