"""RDP-B04-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load

r = load("command", "reference")
c = load("command", "contracts")
e = load("command", "example")


@pytest.mark.unit
@pytest.mark.parametrize("case", ["nominal", "edge"])
def test_computed_example(case):
    actual = e.run_example(case)
    assert actual["positive_check"] is True
    assert actual["inputs"]


@pytest.mark.negative
@pytest.mark.mutation
def test_forbidden_witness():
    assert e.run_example("edge")["negative_detected"] is True


@pytest.mark.behavioral
@pytest.mark.integration
def test_lifecycle_and_forbidden_states(tmp_path):
    store = r.CommandStore(tmp_path / "effects.sqlite3")
    proposal = c.Operation(
        operation_id="op", value=2, mode="PROPOSAL_ONLY", authority="fixture:effect"
    )
    assert store.execute(proposal).disposition == "PROPOSAL_ONLY" and store.counts() == (0, 0)
    committed = proposal.model_copy(update={"mode": "COMMIT_CONFINED_TEST"})
    with pytest.raises(RuntimeError):
        store.execute(committed, "after_effect")
    assert store.counts() == (0, 0)
    receipt = store.execute(committed)
    assert r.CommandStore(store.path).execute(committed) == receipt
    assert store.counts() == (1, 1)
    with pytest.raises(ValueError):
        store.execute(committed.model_copy(update={"value": 3}))


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True


@pytest.mark.negative
def test_outbox_drift_requires_reconciliation(tmp_path):
    from hmt_rdp.sqlite_store import transaction

    store = r.CommandStore(tmp_path / "effects.sqlite3")
    operation = c.Operation(
        operation_id="op", value=2, mode="COMMIT_CONFINED_TEST", authority="fixture:effect"
    )
    receipt = store.execute(operation)
    with transaction(store.path) as connection:
        connection.execute(
            "UPDATE outbox SET receipt=? WHERE id=?",
            (receipt.model_copy(update={"value": 3}).model_dump_json(), "op"),
        )
    with pytest.raises(ValueError, match="OUTBOX_DRIFT"):
        store.execute(operation)
    with transaction(store.path) as connection:
        connection.execute("DELETE FROM outbox")
    with pytest.raises(ValueError, match="OUTBOX_INCONSISTENT"):
        store.execute(operation)
    assert store.counts() == (1, 0)
