"""Regex oracles inspect actual rejected-input and serialization outputs of live primitives."""

import re
import pytest

from crossjoin_cases import CASE_IDS, REGEX, UNIT

pytestmark = [pytest.mark.regex, pytest.mark.negative]


@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_candidate_regex(case_id):
    observed = UNIT[case_id]()
    assert re.fullmatch(REGEX[case_id], observed), (case_id, observed)
    assert re.fullmatch(REGEX[case_id], observed + "\nINJECTED") is None
