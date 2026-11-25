"""Real pinned Tailcat processes with local DERP and bounded test cleanup."""

import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path


def client_key(binary, directory):
    path = directory / "client.private.json"
    result = subprocess.run(
        [binary, "genkey", "--client", "--key=" + str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return path, result.stdout.strip()


def ready_address(path, process):
    for _ in range(200):
        if path.is_file() and path.stat().st_size:
            return path.read_text().strip()
        if process.poll() is not None:
            raise RuntimeError("TAILCAT_SERVER_EXITED")
        time.sleep(0.05)
    raise TimeoutError("TAILCAT_STARTUP_DEADLINE")


@contextmanager
def server(binary, directory, peer_key, config_path):
    address_path = directory / "address.secret"
    environment = dict(
        os.environ, TS_DEBUG_TAILCAT_LOCAL_DERP="1", TAILCAT_ADDR_FILE=str(address_path)
    )
    command = [
        binary,
        "serve",
        "--derpmap-url=none",
        "--key=new",
        "--allow=" + peer_key,
        "exec",
        "--",
        sys.executable,
        "-m",
        "hmt_pg_patterns.worker",
        "--config",
        str(config_path),
    ]
    with (directory / "tailcat.log").open("wb") as log:
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
        try:
            yield ready_address(address_path, process)
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def exchange(binary, key_path, address, payload, timeout=20):
    command = [binary, "--derpmap-url=none", "--key=" + str(key_path), address]
    return subprocess.run(command, input=payload, capture_output=True, timeout=timeout)


def binary_path():
    binary = os.environ.get("HMT_TAILCAT_BIN")
    if not binary or not Path(binary).is_file():
        raise RuntimeError("HMT_TAILCAT_BIN_REQUIRED_NO_TEST_SKIP")
    return binary
