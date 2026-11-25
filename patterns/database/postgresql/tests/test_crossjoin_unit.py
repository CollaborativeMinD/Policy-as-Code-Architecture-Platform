"""One unit-boundary attack for every applicable candidate-space row."""

import pytest

from crossjoin_cases import CASE_IDS, UNIT

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_candidate_unit(case_id):
    assert set(UNIT) == set(CASE_IDS)
    observed = UNIT[case_id]()
    assert isinstance(observed, str) and observed
