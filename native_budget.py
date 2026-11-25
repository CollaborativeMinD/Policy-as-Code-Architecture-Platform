"""Admit operational budgets independently of model and wire contracts."""
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class QualificationBudget:
    process_seconds: int

    @classmethod
    def read(cls, path):
        with Path(path).open("rb") as stream:
            values = tomllib.load(stream)
        if set(values) != set(cls.__annotations__):
            raise ValueError("Unknown or missing runtime budget")
        if type(values["process_seconds"]) is not int or not 1 <= values["process_seconds"] <= 600:
            raise ValueError("Invalid process_seconds")
        return cls(**values)
