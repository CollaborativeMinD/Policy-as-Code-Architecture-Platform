"""Child pytest process receipt proves which isolated source was actually imported."""

import os
from pathlib import Path

import hmt_pg_patterns

from .admission_evidence import source_snapshot, write_json


def pytest_sessionstart(session):
    """Fail before collection if editable-install resolution escaped the isolated copy."""
    root = Path(os.environ["HMT_MUTATION_SOURCE_DIR"]).resolve()
    imported = Path(hmt_pg_patterns.__file__).resolve()
    if not imported.is_relative_to(root / "src"):
        raise RuntimeError("MUTATION_IMPORT_ESCAPED_COPY")
    snapshot = source_snapshot(root)
    expected = os.environ["HMT_MUTATION_SOURCE_DIGEST"]
    if snapshot["source_digest"] != expected:
        raise RuntimeError("MUTATION_SOURCE_DRIFT_BEFORE_COLLECTION")
    write_json(
        Path(os.environ["HMT_MUTATION_EVIDENCE"]) / "runtime_source.json",
        {
            "source_digest": expected,
            "imported_package": str(imported),
            "pytest_root": str(session.config.rootpath),
            "isolated_root": str(root),
        },
    )
