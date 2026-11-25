"""Admit operational budgets independently of model and wire contracts."""
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class QualificationBudget:
    process_seconds: int
    declaration_bytes: int
    archive_bytes: int
    member_bytes: int
    archive_members: int
    manifest_bytes: int
    configuration_bytes: int
    intake_bytes: int
    source_bytes: int

    @classmethod
    def current(cls):
        return cls.read(Path(__file__).with_name("qualification_policy.toml"))

    @classmethod
    def read(cls, path):
        with Path(path).open("rb") as stream:
            values = tomllib.load(stream)
        if set(values) != set(cls.__annotations__):
            raise ValueError("Unknown or missing runtime budget")
        if type(values["process_seconds"]) is not int or not 1 <= values["process_seconds"] <= 600:
            raise ValueError("Invalid process_seconds")
        ceilings = {
            "declaration_bytes": 131_072,
            "archive_bytes": 4_194_304,
            "member_bytes": 262_144,
            "archive_members": 100,
            "manifest_bytes": 1_048_576,
            "configuration_bytes": 65_536,
            "intake_bytes": 524_288,
            "source_bytes": 8_388_608,
        }
        for key, ceiling in ceilings.items():
            if type(values[key]) is not int or not 1 <= values[key] <= ceiling:
                raise ValueError(f"Invalid {key}")
        return cls(**values)
