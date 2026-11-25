"""PG-PEER-01: trusted Tailcat child context bound to a fixed PostgreSQL LOGIN.

Only the host-owned `tailcat serve ... exec -- <worker>` launcher may set the
peer environment. Arbitrary process environments are not authentication. A
hostile process under the same UID is outside this transport trust boundary.
"""

import hmac
import os
from dataclasses import dataclass
import re

from .authority import Authority


class PeerBindingError(RuntimeError):
    """The trusted launcher and fixed database session do not share an identity."""


@dataclass(frozen=True, slots=True)
class TailcatBinding:
    """Host-owned peer key and database LOGIN role; never read from client input."""

    peer_key: str
    db_role: str

    def __post_init__(self):
        if not isinstance(self.peer_key, str) or not re.fullmatch(
            r"nodekey:[0-9a-f]{64}", self.peer_key
        ):
            raise PeerBindingError("INVALID_PEER_BINDING")
        if not isinstance(self.db_role, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]{0,62}", self.db_role
        ):
            raise PeerBindingError("INVALID_ROLE_BINDING")


def require_tailcat_peer(binding):
    """Validate the exact authenticated context inherited from the trusted launcher."""
    if type(binding) is not TailcatBinding:
        raise PeerBindingError("INVALID_BINDING")
    observed = os.environ.get("TAILCAT_PEER_KEY", "")
    if not re.fullmatch(r"nodekey:[0-9a-f]{64}", observed) or not hmac.compare_digest(
        observed, binding.peer_key
    ):
        raise PeerBindingError("TAILCAT_PEER_MISMATCH")


def bind_tailcat_connection(connection, binding):
    """Fail closed before reading any client payload; never select a DSN from input."""
    require_tailcat_peer(binding)
    identity = Authority(connection).identity()
    if identity.db_role != binding.db_role or not hmac.compare_digest(
        identity.peer_key, binding.peer_key
    ):
        raise PeerBindingError("DATABASE_PEER_MISMATCH")
    return identity
