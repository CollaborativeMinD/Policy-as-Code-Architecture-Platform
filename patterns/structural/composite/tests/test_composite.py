"""RDP-S05-INV-001: positive, negative, pressure, API and source coupling."""

import json
import pytest
from hmt_rdp.pattern_loader import load


RECOVERY_WINDOW = 5
SIX_EXPECTED = 6
TRIPLE_EXPECTED = 3

r = load("composite", "reference")
c = load("composite", "contracts")
e = load("composite", "example")


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
    def graph(nodes, root="a"):
        return c.Graph(root=root, nodes=tuple(c.Node(**node) for node in nodes))

    value = graph(
        [dict(node_id="a", weight=1, children=("b",)), dict(node_id="b", weight=2, children=())]
    )
    assert r.Composite().aggregate(value) == TRIPLE_EXPECTED
    invalid = [
        [dict(node_id="a", weight=1, children=("a",))],
        [dict(node_id="a", weight=1, children=("absent",))],
        [
            dict(node_id="a", weight=1, children=("b", "b")),
            dict(node_id="b", weight=2, children=()),
        ],
        [dict(node_id="a", weight=1, children=()), dict(node_id="a", weight=2, children=())],
        [
            dict(node_id=str(i), weight=1, children=(str(i + 1),) if i < RECOVERY_WINDOW else ())
            for i in range(6)
        ],
    ]
    for nodes in invalid:
        with pytest.raises(ValueError):
            r.Composite().aggregate(graph(nodes, "0" if len(nodes) == SIX_EXPECTED else "a"))


@pytest.mark.api
def test_json_example_boundary():
    encoded = json.dumps(e.run_example("nominal"), allow_nan=False)
    assert json.loads(encoded)["positive_check"] is True
