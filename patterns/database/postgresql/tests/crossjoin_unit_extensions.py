"""Distinct pool, migration, peer-binding, and bounded-row admission mechanisms."""

from contextlib import contextmanager
from itertools import repeat
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from authority_samples import KEY
from driver_samples import sample
from hmt_pg_patterns.driver_contracts import pool_limits
from hmt_pg_patterns.migrations import apply_migrations
from hmt_pg_patterns.queries import bounded_metrics
from hmt_pg_patterns.transport import PeerBindingError, TailcatBinding, require_tailcat_peer


def pool_capacity():
    with pytest.raises(ValueError) as denied:
        pool_limits(33, 1.0)
    return str(denied.value)


class DriftProbe:
    def __init__(self):
        self.statements = []

    @contextmanager
    def transaction(self):
        yield self

    def execute(self, statement, parameters=None):
        self.statements.append(statement)
        return SimpleNamespace(fetchone=lambda: ("0" * 64,))


def migration_drift():
    with TemporaryDirectory(prefix="pg-crossjoin-migration-") as directory:
        root = Path(directory)
        (root / "95_crossjoin.sql").write_text("SELECT 'unadmitted changed SQL'")
        probe = DriftProbe()
        with pytest.raises(ValueError) as denied:
            apply_migrations(probe, root)
        assert not any("unadmitted changed SQL" in sql for sql in probe.statements)
    return str(denied.value)


def tailcat_binding():
    binding = TailcatBinding(KEY, "peer_alpha")
    with patch.dict(os.environ, {"TAILCAT_PEER_KEY": "nodekey:" + "b" * 64}):
        with pytest.raises(PeerBindingError) as denied:
            require_tailcat_peer(binding)
    return str(denied.value)


def bounded_rows():
    with pytest.raises(ValueError) as denied:
        bounded_metrics(repeat(sample()))
    return str(denied.value)
