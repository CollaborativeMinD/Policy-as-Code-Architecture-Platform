"""Validate an operator selection and bind only declared Tenacity profiles."""

from dataclasses import dataclass
from hashlib import sha256
import logging
from pathlib import Path
import re
from time import monotonic_ns
import tomllib
from types import MappingProxyType
from collections.abc import Mapping


PATTERNS = frozenset({"basic", "filtering", "logging", "async", "waiting", "ooda"})
CATALOG_ID = "resilience-ooda@1"
MAX_POLICY_BYTES = 65_536
NAME = re.compile(r"[a-z][a-z0-9_-]{0,62}")
NANOSECONDS = 1_000_000_000
MAX_WINDOW_NS = 3_600 * NANOSECONDS
MAX_BACKOFF_MS = 60_000
LOGGER = logging.getLogger(__name__)


class PolicyError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PolicyError(message)


def fields(data, expected, label):
    require(type(data) is dict and data.keys() == set(expected), f"{label}: unexpected or missing fields")


def integer(value, lower, upper, label):
    require(type(value) is int and lower <= value <= upper, f"{label}: integer outside admitted range")


@dataclass(frozen=True)
class Profile:
    kind: str
    attempts: int
    settings: Mapping


@dataclass(frozen=True)
class Policy:
    name: str
    catalog: str
    profiles: Mapping[str, Profile]
    sha256: str


def parse_policy(raw: bytes) -> Policy:
    require(type(raw) is bytes and len(raw) <= MAX_POLICY_BYTES, "selection exceeds the byte limit")
    try:
        declaration = tomllib.loads(raw.decode("utf-8"))
    except ValueError:
        raise PolicyError("invalid TOML selection") from None
    fields(declaration, ("version", "catalog", "name", "profiles"), "selection")
    integer(declaration["version"], 1, 1, "version")
    require(declaration["catalog"] == CATALOG_ID, "unknown catalog version")
    name = declaration["name"]
    require(type(name) is str and NAME.fullmatch(name), "invalid bundle name")
    profiles = declaration["profiles"]
    require(type(profiles) is dict and 0 < len(profiles) <= 32, "invalid profile count")
    admitted = {}
    for profile_name, entry in profiles.items():
        require(NAME.fullmatch(profile_name), "invalid profile name")
        admitted[profile_name] = _profile(profile_name, entry)
    return Policy(name, CATALOG_ID, MappingProxyType(admitted), sha256(raw).hexdigest())


def load_policy(path: Path) -> Policy:
    with path.open("rb") as source:
        return parse_policy(source.read(MAX_POLICY_BYTES + 1))


def _profile(name, entry):
    require(type(entry) is dict and type(entry.get("kind")) is str and entry["kind"] in PATTERNS,
            f"{name}: no runtime binding for pattern")
    kind = entry["kind"]
    keys = {"kind", "attempts"}
    if kind == "ooda":
        timing = ("window_ns", "attempt_bound_ns", "fallback_reserve_ns", "uncertainty_ns", "backoff_ns")
        fields(entry, keys | set(timing), name)
        for key in timing:
            integer(entry[key], int(key in {"window_ns", "attempt_bound_ns"}), MAX_WINDOW_NS, f"{name}.{key}")
        require(entry["attempt_bound_ns"] + entry["fallback_reserve_ns"] + entry["uncertainty_ns"]
                < entry["window_ns"], f"{name}: first attempt has no strict margin")
    elif kind == "waiting":
        _validate_wait(name, entry, keys)
    else:
        fields(entry, keys | {"backoff_ms"} | ({"trigger"} if kind == "filtering" else set()), name)
        integer(entry["backoff_ms"], 0, MAX_BACKOFF_MS, f"{name}.backoff_ms")
        if kind == "filtering":
            require(entry["trigger"] in ("missing_result", "connection_error"), f"{name}: unknown retry trigger")
    integer(entry["attempts"], 1, 11, f"{name}.attempts")
    return Profile(kind, entry["attempts"], MappingProxyType({k: v for k, v in entry.items() if k not in keys}))


def _validate_wait(name, entry, keys):
    strategy = entry.get("strategy")
    strategies = {"fixed": ("delay_ms",), "random": ("min_ms", "max_ms"),
                  "exponential": ("min_ms", "max_ms", "multiplier_ms")}
    require(type(strategy) is str and strategy in strategies, f"{name}: unknown wait strategy")
    params = strategies[strategy]
    fields(entry, keys | {"strategy", *params}, name)
    for key in params:
        integer(entry[key], int(key == "multiplier_ms"), MAX_BACKOFF_MS, f"{name}.{key}")
    if "min_ms" in params:
        require(entry["min_ms"] <= entry["max_ms"], f"{name}: inverted wait range")


@dataclass(frozen=True)
class RetryNotice:
    profile: str
    attempt: int
    delay_ns: int
    policy_sha256: str


@dataclass(frozen=True)
class DeadlineReceipt:
    profile: str
    policy_sha256: str
    reason: str
    attempts: int
    observed_ns: int
    deadline_ns: int
    required_ns: int


class RetryWindowClosed(TimeoutError):
    def __init__(self, receipt: DeadlineReceipt):
        self.receipt = receipt
        super().__init__(receipt.reason)


class RetryRuntime:
    def __init__(self, policy: Policy, *, clock=monotonic_ns):
        self.policy = policy
        self.clock = clock

    def _admit(self, name, replay_safe, *, asynchronous):
        require(type(name) is str and type(replay_safe) is bool, "profile name and replay authority must be explicit")
        profile = self.policy.profiles.get(name)
        require(profile is not None and (profile.kind == "async") == asynchronous, "profile not admitted for this entry point")
        return profile, profile.attempts if replay_safe else 1

    def run(self, name, operation, *, replay_safe=False, violation_deadline_ns=None, on_retry=None, sleep=None):
        from tenacity import Retrying

        profile, attempts = self._admit(name, replay_safe, asynchronous=False)
        if profile.kind == "ooda":
            return self._timed(name, profile, attempts, operation, violation_deadline_ns, on_retry, sleep)
        require(violation_deadline_ns is None, "only OODA profiles consume deadline evidence")
        return Retrying(**self._settings(name, profile, attempts, on_retry, sleep))(operation)

    async def run_async(self, name, operation, *, replay_safe=False, on_retry=None, sleep=None):
        from tenacity import AsyncRetrying

        profile, attempts = self._admit(name, replay_safe, asynchronous=True)
        return await AsyncRetrying(**self._settings(name, profile, attempts, on_retry, sleep))(operation)

    def _notice(self, name, state, delay, on_retry, *, log=False):
        notice = RetryNotice(name, state.attempt_number, delay, self.policy.sha256)
        if on_retry is not None:
            on_retry(notice)
        elif log:
            LOGGER.warning("Retry scheduled for %s after attempt %d", name, notice.attempt)

    def _settings(self, name, profile, attempts, on_retry, sleep):
        from tenacity import retry_if_exception_type, retry_if_result, stop_after_attempt

        retry = retry_if_exception_type(ValueError if profile.kind == "logging" else ConnectionError)
        if profile.settings.get("trigger") == "missing_result":
            retry = retry_if_result(lambda result: result is None)
        settings = dict(stop=stop_after_attempt(attempts), retry=retry, wait=_wait(profile), reraise=True)
        if on_retry is not None or profile.kind == "logging":
            settings["before_sleep"] = lambda state: self._notice(
                name, state, round(state.next_action.sleep * NANOSECONDS), on_retry, log=profile.kind == "logging")
        if sleep is not None:
            settings["sleep"] = sleep
        return settings

    def _timed(self, name, profile, attempts, operation, listener, on_retry, sleep):
        from math import ceil
        from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

        settings = profile.settings
        end = self.clock() + settings["window_ns"]
        bound = settings["attempt_bound_ns"]
        reserve = settings["fallback_reserve_ns"] + settings["uncertainty_ns"]
        wait = settings["backoff_ns"] / NANOSECONDS
        calls = 0

        def close(reason, now, required):
            raise RetryWindowClosed(DeadlineReceipt(name, self.policy.sha256, reason, calls, now, end, required))

        def admit(required):
            nonlocal end
            if listener is not None:
                try:
                    candidate = listener()
                    require(type(candidate) is int and candidate >= 0, "invalid deadline evidence")
                except Exception:
                    close("invalid_time_evidence", self.clock(), required)
                end = min(end, candidate)
            now = self.clock()
            if required >= end - now:
                close("insufficient_margin", now, required)
            return now

        def before_sleep(state):
            delay = max(settings["backoff_ns"], ceil(state.next_action.sleep * NANOSECONDS))
            admit(delay + bound + reserve)
            if on_retry is not None:
                self._notice(name, state, delay, on_retry)
                admit(delay + bound + reserve)

        def guarded():
            nonlocal calls
            started = admit(bound + reserve)
            calls += 1
            try:
                return operation()
            finally:
                now = self.clock()
                if now - started > bound:
                    close("attempt_bound_exceeded", now, bound + reserve)
                admit(reserve)

        options = dict(retry=retry_if_exception_type(ConnectionError), stop=stop_after_attempt(attempts),
                       wait=wait_fixed(wait), before_sleep=before_sleep, reraise=True)
        if sleep is not None:
            options["sleep"] = sleep
        return Retrying(**options)(guarded)


def _wait(profile):
    from tenacity import wait_exponential, wait_fixed, wait_random

    settings = profile.settings
    strategy = settings.get("strategy")
    if strategy is None:
        return wait_fixed(settings["backoff_ms"] / 1000)
    if strategy == "fixed":
        return wait_fixed(settings["delay_ms"] / 1000)
    low, high = settings["min_ms"] / 1000, settings["max_ms"] / 1000
    if strategy == "random":
        return wait_random(min=low, max=high)
    return wait_exponential(multiplier=settings["multiplier_ms"] / 1000, min=low, max=high)
