"""Single explicit case inventory; every selected candidate gets four real test families."""

from pathlib import Path

from tools.candidate_model import load_dimensions
import crossjoin_unit_authority as authority
import crossjoin_unit_driver as driver
import crossjoin_unit_extensions as extensions
import crossjoin_unit_pace as pace
import crossjoin_unit_stream as streaming

DIMENSIONS = load_dimensions(
    Path(__file__).resolve().parents[1] / "contracts/candidate_dimensions.json"
)
CASE_IDS = tuple(case["id"] for case in DIMENSIONS["cases"])
UNIT = {
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

REGEX = {
    "tls_profile": r"PRODUCTION_REQUIRES_TLS_AND_NONADMIN_ROLE",
    "bound_values": r"TABLE_NOT_ADMITTED",
    "rollback": r"IDLE_AUTOCOMMIT_CONNECTION_REQUIRED",
    "retry_budget": r"40001",
    "bounded_close": r"forced",
    "contract_rejection": r"TELEMETRY_KEY_INVALID",
    "immutable_snapshot": r"[0-9a-f]{64}",
    "epoch_fence": r"int_type",
    "outbox_replay": r"OUTBOX_REQUIRES_IDLE_AUTOCOMMIT",
    "checkpoint_order": r"greater_than_equal",
    "packet_invariance": r"content|max size|tail",
    "stream_limits": r"STREAM_CAPACITY",
    "terminal_authority": r"PACE_OPERATION_DENIED:T:write",
    "guarded_recovery": r"PACE_OPERATION_DENIED:E:write",
    "wal_prerequisites": r"WAL_PROTECTION_DISABLED",
    "pool_capacity": r"POOL_SIZE_OUT_OF_RANGE",
    "migration_drift": r"MIGRATION_CHECKSUM_DRIFT",
    "tailcat_binding": r"TAILCAT_PEER_MISMATCH",
    "bounded_rows": r"BATCH_ROW_LIMIT",
}
