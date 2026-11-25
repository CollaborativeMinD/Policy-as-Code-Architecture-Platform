"""Every applicable candidate is attacked against live PostgreSQL or Redis components."""

import pytest

from crossjoin_cases import CASE_IDS
import crossjoin_live_authority as authority
import crossjoin_live_driver as driver
import crossjoin_live_extensions as extensions
import crossjoin_live_pace as pace
import crossjoin_live_stream as streaming

pytestmark = pytest.mark.integration

LIVE = {
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
    "terminal_authority": pace.terminal_authority,
    "guarded_recovery": pace.guarded_recovery,
    "wal_prerequisites": driver.wal_prerequisites,
    "pool_capacity": extensions.pool_capacity,
    "migration_drift": extensions.migration_drift,
    "tailcat_binding": extensions.tailcat_binding,
    "bounded_rows": extensions.bounded_rows,
}


@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_candidate_integration(case_id, pg_conn, db_config, redis_client):
    assert set(LIVE) == set(CASE_IDS)
    result = LIVE[case_id](authority.Live(pg_conn, db_config, redis_client))
    assert isinstance(result, str) and result
