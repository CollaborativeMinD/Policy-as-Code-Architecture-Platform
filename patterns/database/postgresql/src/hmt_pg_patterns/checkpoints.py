"""PG-CKPT-02..03: Redis is a bounded, disposable projection of database truth."""

import hashlib

from redis.exceptions import RedisError

from .checkpoints_lua import OFFER, READ
from .checkpoints_snapshot import encode_checkpoint, immutable_checkpoint


class CheckpointCache:
    """Use a TLS/ACL configured redis client with finite connect/read timeouts."""

    def __init__(self, client):
        self.client = client

    @staticmethod
    def _key(snapshot):
        owner = hashlib.sha256(snapshot["db_role"].encode("utf-8")).hexdigest()
        return f"hmt_pg:checkpoint:v1:{owner}:{snapshot['stream_id']}"

    def offer(self, value):
        """Atomically offer a bounded projection without creating authority."""
        snapshot = immutable_checkpoint(value)
        encoded = encode_checkpoint(snapshot)
        try:
            outcome = self.client.eval(OFFER, 1, self._key(snapshot), encoded, 300)
        except RedisError:
            return "UNAVAILABLE"
        if isinstance(outcome, bytes):
            outcome = outcome.decode("ascii", errors="replace")
        if outcome not in {"APPLIED", "IDENTICAL", "STALE", "CONFLICT", "INVALID"}:
            return "INVALID"
        return outcome

    def read(self, authoritative):
        """Caller supplies a fresh PostgreSQL checkpoint; cached bytes grant no authority."""
        snapshot = immutable_checkpoint(authoritative)
        try:
            cached = self.client.eval(READ, 1, self._key(snapshot))
        except RedisError:
            return None
        encoded = encode_checkpoint(snapshot).encode("utf-8")
        if isinstance(cached, str):
            cached = cached.encode("utf-8")
        return snapshot if cached == encoded else None
