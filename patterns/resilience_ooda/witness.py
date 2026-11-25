"""Exercise the selected retry profiles without network I/O or real sleeps."""

import asyncio
from importlib.metadata import version
import json
from math import ceil
from pathlib import Path
import sys

from tenacity import RetryError

from retry_runtime import DeadlineReceipt, RetryRuntime, RetryWindowClosed, load_policy


def check(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def expect(error_type, operation):
    try:
        operation()
    except error_type as error:
        return error
    raise RuntimeError(f"expected {error_type.__name__}")


def test_sync(runtime, name, profile):
    calls, delays, events = [], [], []
    missing = profile.settings.get("trigger") == "missing_result"
    retryable = ValueError if profile.kind == "logging" else ConnectionError
    exception = retryable("fixture failure")

    def operation():
        calls.append(1)
        if missing:
            return None
        raise exception

    terminal = RetryError if missing else retryable
    error = expect(terminal, lambda: runtime.run(name, operation, sleep=delays.append))
    check(len(calls) == 1 and not delays, f"{name} replayed without authority")
    check(missing or error is exception, f"{name} changed terminal exception")
    calls.clear()
    expect(terminal, lambda: runtime.run(name, operation, replay_safe=True,
                                        on_retry=events.append, sleep=delays.append))
    check(len(calls) == profile.attempts and len(delays) == profile.attempts - 1, f"{name} attempt cap mismatch")
    check([event.attempt for event in events] == list(range(1, profile.attempts)), f"{name} retry notice mismatch")
    check(all(event.policy_sha256 == runtime.policy.sha256 for event in events), f"{name} notice digest mismatch")
    settings = profile.settings
    if "min_ms" in settings:
        check(all(settings["min_ms"] <= round(delay * 1000) <= settings["max_ms"] for delay in delays),
              f"{name} wait outside policy")
    else:
        expected = settings.get("delay_ms", settings.get("backoff_ms"))
        check(all(round(delay * 1000) == expected for delay in delays), f"{name} wait mismatch")
    calls.clear()

    def fail():
        calls.append(1)
        raise TypeError("terminal")

    expect(TypeError, lambda: runtime.run(name, fail, replay_safe=True, sleep=delays.append))
    check(calls == [1], f"{name} retried a terminal exception")


async def test_async(runtime, name, profile):
    calls, events, delays = [], [], []

    async def operation():
        calls.append(1)
        raise ConnectionError("fixture")

    async def sleep(delay):
        delays.append(delay)

    for replay, expected in ((False, 1), (True, profile.attempts)):
        try:
            await runtime.run_async(name, operation, replay_safe=replay, on_retry=events.append, sleep=sleep)
        except ConnectionError:
            pass
        else:
            raise RuntimeError("async exhaustion did not propagate")
        check(len(calls) == expected and len(events) == len(delays) == expected - 1, "async attempt mismatch")
        check(all(round(delay * 1000) == profile.settings["backoff_ms"] for delay in delays), "async backoff mismatch")
        calls.clear()
        events.clear()
        delays.clear()


def test_ooda(policy, name, profile):
    now = [0]
    runtime = RetryRuntime(policy, clock=lambda: now[0])
    settings = profile.settings
    bound = settings["attempt_bound_ns"]
    required = bound + settings["fallback_reserve_ns"] + settings["uncertainty_ns"]
    calls = []

    def operation():
        calls.append(1)
        return 42

    exact = expect(RetryWindowClosed, lambda: runtime.run(name, operation, violation_deadline_ns=lambda: required))
    check(exact.receipt == DeadlineReceipt(name, policy.sha256, "insufficient_margin", 0, 0, required, required)
          and not calls, "strict equality failed to block dispatch")
    result = runtime.run(name, operation, violation_deadline_ns=lambda: required + 1)
    check(result == 42 and calls == [1], "one-nanosecond margin did not admit")
    error = expect(RetryWindowClosed, lambda: runtime.run(name, operation, violation_deadline_ns=lambda: True))
    check(error.receipt.reason == "invalid_time_evidence" and calls == [1], "invalid evidence reached execution")

    def overrun():
        now[0] += bound + 1
        return 42

    error = expect(RetryWindowClosed, lambda: runtime.run(name, overrun))
    check(error.receipt.reason == "attempt_bound_exceeded" and error.receipt.attempts == 1, "overrun was accepted")

    def transient():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("fixture")
        return 42

    calls.clear()
    expect(ConnectionError, lambda: runtime.run(name, transient))
    check(calls == [1], "OODA replayed without authority")
    if profile.attempts > 1:
        calls.clear()
        stop = now[0] + required + 1
        if settings["backoff_ns"] == 0:
            end = [stop]

            def tighten(_):
                end[0] -= 1

            try:
                runtime.run(name, transient, replay_safe=True, violation_deadline_ns=lambda: end[0],
                            on_retry=tighten, sleep=lambda _: None)
            except RetryWindowClosed as error:
                check(error.receipt.attempts == 1, "tightened deadline did not stop replay")
            else:
                raise RuntimeError("retry ignored deadline")
        else:
            error = expect(RetryWindowClosed, lambda: runtime.run(
                name, transient, replay_safe=True, violation_deadline_ns=lambda: stop,
                sleep=lambda _: (_ for _ in ()).throw(RuntimeError("backoff was not admitted"))))
            check(error.receipt.attempts == 1, "backoff bypassed the deadline")
        delay_ns = max(settings["backoff_ns"], ceil(settings["backoff_ns"] / 1_000_000_000 * 1_000_000_000))
        if required + delay_ns < settings["window_ns"]:
            calls.clear()

            def sleep(_):
                now[0] += delay_ns

            recovered = runtime.run(name, transient, replay_safe=True, sleep=sleep)
            check(recovered == 42 and calls == [1, 1], "admitted OODA retry did not recover")


def qualify(path):
    policy = load_policy(path)
    runtime = RetryRuntime(policy)
    results = {}
    for name, profile in sorted(policy.profiles.items()):
        if profile.kind == "async":
            asyncio.run(test_async(runtime, name, profile))
        elif profile.kind == "ooda":
            test_ooda(policy, name, profile)
        else:
            test_sync(runtime, name, profile)
        results[name] = {"kind": profile.kind, "status": "PASS"}
    return {"status": "PASS", "selection_sha256": policy.sha256,
            "python": sys.version.split()[0], "tenacity": version("tenacity"), "profiles": results}


if __name__ == "__main__":
    print(json.dumps(qualify(Path(__file__).with_name("selection.toml")), sort_keys=True))
