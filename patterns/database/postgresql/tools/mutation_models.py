"""Immutable, bounded mutation specifications; every patch has one exact anchor."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Patch:
    """One literal replacement inside one admitted source file."""

    path: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class Mutation:
    """A semantic change, its governing requirement, and its public witness."""

    identifier: str
    requirement: str
    patch: Patch
    selector: str
