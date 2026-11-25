"""Fixed Tailcat worker: peer binding → PostgreSQL CDC/WAL → Redis projection."""

import psycopg
from redis import Redis
from redis.exceptions import RedisError

from .authority import Authority
from .checkpoints import CheckpointCache
from .checkpoints_snapshot import encode_checkpoint
from .diagnostics import wal_settings
from .pace import perform, step
from .pace_models import Observation, PaceState
from .streaming_contracts import Policy
from .streaming_writer import StreamWriter
from .transport import bind_tailcat_connection
from .worker_config import WorkerConfig
from .worker_io import IngressRequest
from .worker_projection import project


def _role_contract(connection) -> None:
    row = connection.execute(
        "SELECT rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname=session_user"
    ).fetchone()
    if row is None or any(row):
        raise PermissionError("WORKER_ROLE_HAS_ADMIN_PRIVILEGE")


def _state(cache) -> PaceState:
    try:
        ready = bool(cache.ping())
    except RedisError:
        ready = False
    observation = Observation(
        now=0.0,
        margin=1.0,
        database_ready=True,
        cache_ready=ready,
        transport_ready=True,
        authority_valid=True,
        epoch_current=True,
        reconciled=True,
        uncertain_ack=False,
    )
    return step(PaceState(), observation)


def _durability(connection, config: WorkerConfig) -> str:
    if config.database.profile == "test":
        return "TEST_ONLY_NOT_QUALIFIED"
    if not connection.pgconn.ssl_in_use:
        raise PermissionError("WORKER_REQUIRES_OBSERVED_TLS")
    wal_settings(connection).require_local_durable_commit()
    return "WAL_PREREQUISITES_OBSERVED"


def execute_stream(connection, cache, config: WorkerConfig, request: IngressRequest) -> dict:
    """Each chunk checks current authority; Redis failure leaves durable outbox work."""
    config = WorkerConfig.model_validate(config.model_dump())
    identity = bind_tailcat_connection(connection, config.binding())
    _role_contract(connection)
    durability = _durability(connection, config)
    payload = request.payload(config.max_payload_bytes)
    state = _state(cache)
    policy = Policy(max_total_bytes=config.max_payload_bytes, max_packets=1)
    writer = StreamWriter(Authority(connection), request.stream_id, identity.epoch, policy)
    snapshot = perform(state, "write", lambda: writer.write([payload]))
    projection = CheckpointCache(cache)
    project(connection, projection, state, config.max_payload_bytes // policy.min_size + 2)
    current = Authority(connection).checkpoint(request.stream_id)
    acknowledged = current is not None and projection.read(current) is not None
    return {
        "status": "COMMITTED",
        "mode": state.mode.value,
        "durability": durability,
        "checkpoint": encode_checkpoint(snapshot),
        "projection": "ACKED" if acknowledged else "UNKNOWN",
    }


def serve(config: WorkerConfig, request: IngressRequest) -> dict:
    """Own bounded connections; no endpoint or identity is selected from client bytes."""
    tls = {"ssl_cert_reqs": "required", "ssl_check_hostname": True}
    options = tls if config.database.profile == "production" else {}
    with psycopg.connect(**config.database.connect_kwargs(), autocommit=True) as connection:
        with Redis.from_url(
            config.redis_url.get_secret_value(),
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
            **options,
        ) as cache:
            return execute_stream(connection, cache, config, request)
