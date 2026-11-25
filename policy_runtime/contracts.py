"""Closed boundary for a single software-qualified pattern."""

import json
from pathlib import Path
import tomllib


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def settings(value, *names):
    require(type(value) is dict and value.keys() == set(names), "UNDECLARED_OR_MISSING_SETTING")
    return value


def integer(value, minimum, maximum):
    require(type(value) is int and minimum <= value <= maximum, "INTEGER_NOT_ADMITTED")
    return value


def number(value, minimum, maximum):
    require(type(value) in (int, float) and minimum <= value <= maximum, "NUMBER_NOT_ADMITTED")
    return value


def choice(value, *allowed):
    require(type(value) is str and value in allowed, "VALUE_NOT_ADMITTED")
    return value


def boolean(value):
    require(type(value) is bool, "BOOLEAN_NOT_ADMITTED")
    return value


def model(cls, value, *names):
    # JSON validation permits only the wire conversions needed for tuples,
    # enum values and ISO timestamps. Scalars remain strict.
    settings(value, *names)
    return cls.model_validate_json(json.dumps(value, allow_nan=False), strict=True)


def read_policy(path: Path, authorized_id: str):
    with path.open("rb") as handle:
        raw = handle.read(65_537)
    return raw, parse_policy(raw, authorized_id)


def parse_policy(raw: bytes, authorized_id: str):
    require(len(raw) <= 65_536, "POLICY_SIZE_LIMIT")
    obj = settings(tomllib.loads(raw.decode()), "version", "pattern", "scope", "settings")
    integer(obj["version"], 1, 1)
    choice(obj["pattern"], authorized_id)
    choice(obj["scope"], "software")
    require(type(obj["settings"]) is dict, "SETTINGS_TABLE_REQUIRED")
    return obj["settings"]
