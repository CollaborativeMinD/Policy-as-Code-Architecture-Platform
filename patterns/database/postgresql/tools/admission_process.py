"""Bounded local pytest process capture; the runner grants no runtime authority."""

import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

OUTPUT_LIMIT = 8388608


def capture(process, logs, deadline):
    captured = 0
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ, logs[0])
        selector.register(process.stderr, selectors.EVENT_READ, logs[1])
        while selector.get_map() or process.poll() is None:
            if time.monotonic() >= deadline:
                return "PROCESS_TIMEOUT", captured
            for key, _ in selector.select(0.05):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                remaining = OUTPUT_LIMIT - captured
                key.data.write(block[:remaining])
                captured += min(len(block), remaining)
                if len(block) > remaining:
                    return "PROCESS_OUTPUT_LIMIT", captured
    return "COMPLETE", captured


def terminate(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run_command(argv, root, folder, environment, timeout=600):
    if not 0 < timeout <= 7200:
        raise ValueError("PROCESS_TIMEOUT_BOUND")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with (folder / "pytest.stdout.log").open("xb") as stdout:
        with (folder / "pytest.stderr.log").open("xb") as stderr:
            with subprocess.Popen(
                argv,
                cwd=root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ) as process:
                reason, captured = capture(process, (stdout, stderr), started + timeout)
                if reason != "COMPLETE":
                    terminate(process)
                returncode = process.wait(timeout=5)
    return {
        "status": "PASS" if reason == "COMPLETE" and returncode == 0 else "FAIL",
        "argv": argv,
        "returncode": returncode,
        "reason": reason,
        "seconds": time.monotonic() - started,
        "captured_bytes": captured,
        "stdout": "pytest.stdout.log",
        "stderr": "pytest.stderr.log",
    }
