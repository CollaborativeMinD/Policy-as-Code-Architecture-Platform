"""RDP-B06-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load


FOUR_LIMIT = 4

r = load("iterator", "reference")
c = load("iterator", "contracts")
e = load("iterator", "example")


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
    iterator = r.EvidenceIterator(tuple(c.Record(record_id=chr(97 + i), value=i) for i in range(5)))
    cursor = c.Cursor(offset=0, snapshot_digest=iterator.snapshot_digest, expires_at=10)
    page = iterator.page(cursor, 4, 1)
    assert len(page.records) == FOUR_LIMIT
    assert iterator.page(page.next_cursor, 4, 1).next_cursor is None
    for size, now, change in (
        (0, 1, {}),
        (True, 1, {}),
        (4, 10, {}),
        (4, -1, {}),
        (4, 1, {"offset": 6}),
        (4, 1, {"snapshot_digest": "0" * 64}),
    ):
        with pytest.raises(ValueError):
            iterator.page(cursor.model_copy(update=change), size, now)
    with pytest.raises(ValueError):
        r.EvidenceIterator((c.Record(record_id="x", value=1), c.Record(record_id="x", value=2)))


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
