"""PG-ADMIT-003: bounded, explicit applicability for the complete candidate space."""

import json
import re
from pathlib import Path

FAMILIES = ("unit", "regex", "integration", "e2e")
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def load_dimensions(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 1048576:
        raise ValueError("DIMENSIONS_INPUT_BOUND")
    data = json.loads(path.read_text(), object_pairs_hook=unique_keys)
    validate_dimensions(data)
    return data


def identity_rows(rows, bound):
    if not isinstance(rows, list) or not 1 <= len(rows) <= bound:
        raise ValueError("DIMENSION_CARDINALITY_BOUND")
    identities = [row["id"] for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("DUPLICATE_DIMENSION_ID")
    if any(not IDENTITY.fullmatch(identity) for identity in identities):
        raise ValueError("INVALID_DIMENSION_ID")
    if any(not row["requirement"].strip() for row in rows):
        raise ValueError("REQUIREMENT_REQUIRED")
    return set(identities)


def validate_dimensions(data):
    if data["schema_id"] != "urn:hmt:pg:candidate-dimensions:1.0.0":
        raise ValueError("DIMENSIONS_SCHEMA")
    limit = data["bounds"]["max_dimension_items"]
    maximum = data["bounds"]["max_candidate_rows"]
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("DIMENSION_LIMIT_INVALID")
    if type(maximum) is not int or not 1 <= maximum <= 4096:
        raise ValueError("CANDIDATE_LIMIT_INVALID")
    groups = ("invariants", "failure_modes", "gates")
    identities = [identity_rows(data[group], limit) for group in groups]
    total = len(identities[0]) * len(identities[1]) * len(identities[2])
    if total > maximum:
        raise ValueError("CROSS_JOIN_RESOURCE_BOUND")
    validate_cases(data, identities)


def validate_cases(data, identities):
    inv_ids, failure_ids, gate_ids = identities
    if not data["cases"] or len(data["cases"]) > 4096:
        raise ValueError("CASE_INVENTORY_BOUND")
    triples, names = set(), set()
    for case in data["cases"]:
        triple = (case["invariant_id"], case["failure_id"], case["gate_id"])
        if triple in triples or case["id"] in names:
            raise ValueError("AMBIGUOUS_APPLICABILITY")
        triples.add(triple)
        names.add(case["id"])
        if not (triple[0] in inv_ids and triple[1] in failure_ids and triple[2] in gate_ids):
            raise ValueError("CASE_DIMENSION_REFERENCE")
        if tuple(case["families"]) != FAMILIES or not case["assertion"].strip():
            raise ValueError("CASE_ASSERTION_FAMILIES")
        if not IDENTITY.fullmatch(case["id"]) or case["requirement"] != triple[0]:
            raise ValueError("CASE_REQUIREMENT_IDENTITY")
    for row in data["invariants"]:
        selected = {case[1] for case in triples if case[0] == row["id"]}
        if not selected or selected != set(row["failure_modes"]):
            raise ValueError("FAILURE_RELATION_UNCOVERED")


def applicability(data, triple):
    for case in data["cases"]:
        if triple == (case["invariant_id"], case["failure_id"], case["gate_id"]):
            return case, "selected_contract_failure_and_gate == true"
    invariant = next(row for row in data["invariants"] if row["id"] == triple[0])
    if triple[1] not in invariant["failure_modes"]:
        return None, "failure_id in invariant.failure_modes == false"
    return None, "gate_id is assigned to this contract/failure boundary == false"


def test_id(case_id, family):
    if family not in FAMILIES or not IDENTITY.fullmatch(case_id):
        raise ValueError("TEST_IDENTITY_INPUT")
    return f"tests/test_crossjoin_{family}.py::test_candidate_{family}[{case_id}]"
