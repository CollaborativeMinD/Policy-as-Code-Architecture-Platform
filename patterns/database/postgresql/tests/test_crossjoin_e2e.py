"""Every applicable candidate has an end-to-end failure or delivery witness."""

import pytest

from crossjoin_cases import CASE_IDS
from crossjoin_live_authority import Live
import crossjoin_e2e_authority as authority
import crossjoin_e2e_driver as driver
import crossjoin_e2e_extensions as extensions
import crossjoin_e2e_stream_pace as streaming

pytestmark = pytest.mark.e2e

FLOWS = {
    "tls_profile": driver.tls_profile,
    "bound_values": driver.bound_values,
    "rollback": driver.rollback,
    "retry_budget": driver.retry_budget,
    "bounded_close": driver.bounded_close,
    "contract_rejection": driver.contract_rejection,
    "immutable_snapshot": authority.immutable_snapshot,
    "epoch_fence": authority.epoch_fence,
    "outbox_replay": authority.outbox_replay,
    "checkpoint_order": authority.checkpoint_order,
    "packet_invariance": streaming.packet_invariance,
    "stream_limits": streaming.stream_limits,
    "terminal_authority": streaming.terminal_authority,
    "guarded_recovery": streaming.guarded_recovery,
    "wal_prerequisites": streaming.wal_prerequisites,
    "pool_capacity": extensions.pool_capacity,
    "migration_drift": extensions.migration_drift,
    "tailcat_binding": extensions.tailcat_binding,
    "bounded_rows": extensions.bounded_rows,
}


@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_candidate_e2e(case_id, pg_conn, db_config, redis_client):
    assert set(FLOWS) == set(CASE_IDS)
    result = FLOWS[case_id](Live(pg_conn, db_config, redis_client))
    assert isinstance(result, str) and result
