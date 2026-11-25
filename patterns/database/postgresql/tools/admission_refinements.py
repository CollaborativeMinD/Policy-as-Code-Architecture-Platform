"""Closed source/test inventory and explicit mappings for all public refinements."""

import ast
import json
from pathlib import Path
import re

IDENTITIES = re.compile(r"\b(?:PG-[A-Z]+(?:-[A-Z]+)*|CDC)-\d{2,3}(?:\.\.\d{2,3})?\b")


def read_registry(root):
    return json.loads((Path(root) / "contracts/contract_refinements.json").read_text())


def check_refinements(root):
    root = Path(root)
    registry = read_registry(root)
    sources = {
        path.relative_to(root).as_posix() for path in (root / "src/hmt_pg_patterns").rglob("*.py")
    }
    sources.update(path.relative_to(root).as_posix() for path in (root / "sql").glob("*.sql"))
    tests = {path.relative_to(root).as_posix() for path in (root / "tests").rglob("test_*.py")}
    missing = sorted(sources.symmetric_difference(registry["source_files"]))
    missing += sorted(tests.symmetric_difference(registry["test_files"]))
    qualification = {p.relative_to(root).as_posix() for p in (root / "qualification").glob("*.py")}
    missing += sorted(qualification.symmetric_difference(registry.get("qualification_files", {})))
    unknown = set()
    for relative in sources:
        if relative.endswith(".py"):
            doc = ast.get_docstring(ast.parse((root / relative).read_text())) or ""
            unknown.update(set(IDENTITIES.findall(doc)) - set(registry["public_contracts"]))
    for relative, row in registry["source_files"].items():
        if not row["selected_invariants"] and row.get("mapping") != "metadata_only":
            missing.append("UNMAPPED_BEHAVIOR:" + relative)
    return {
        "status": "FAIL" if missing or unknown else "PASS",
        "inventory_gaps": missing,
        "unmapped_public_contracts": sorted(unknown),
        "source_files": len(sources),
        "test_files": len(tests),
        "public_contracts": len(registry["public_contracts"]),
    }


def full_test_manifest(execution, registry, dimensions):
    cases = {row["id"]: row["requirement"] for row in dimensions["cases"]}
    result = []
    for witness in execution["tests"]:
        identity = witness["test_id"]
        filename = identity.split("::", 1)[0]
        entry = registry["test_files"].get(filename) or registry.get("qualification_files", {}).get(
            filename
        )
        if entry is None:
            raise ValueError("EXECUTED_TEST_HAS_NO_REQUIREMENT:" + identity)
        requirement = registry.get("test_overrides", {}).get(identity, entry["source_contract"])
        if requirement == "PER_CANDIDATE_PARAMETER":
            match = re.search(r"\[([a-z_]+)\]$", identity)
            if match is None or match[1] not in cases:
                raise ValueError("CANDIDATE_TEST_IDENTITY_DRIFT:" + identity)
            requirement = cases[match[1]]
        if requirement not in registry["public_contracts"]:
            raise ValueError("TEST_CONTRACT_UNMAPPED:" + requirement)
        result.append(
            {
                "test_id": identity,
                "source_requirement_or_invariant": requirement,
                "selected_invariants": registry["public_contracts"][requirement],
                "evidence_ref": "junit.xml",
            }
        )
    return result
