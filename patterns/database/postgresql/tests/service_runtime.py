"""Disposable child services; native DSNs take precedence over the SQL test engine."""

import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_ready(process, port):
    for _ in range(500):
        if process.poll() is not None:
            raise RuntimeError("DISPOSABLE_SERVICE_EXITED_BEFORE_READY")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError("DISPOSABLE_SERVICE_STARTUP_DEADLINE")


@contextmanager
def child_service(command, port, log):
    with log.open("w") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        try:
            wait_ready(process, port)
            yield process
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@contextmanager
def postgres_service(folder):
    configured = os.environ.get("HMT_TEST_DSN")
    if configured:
        yield configured
        return
    cli = os.environ.get("HMT_PGLITE_CLI")
    if cli is None or not Path(cli).is_file():
        raise RuntimeError("SUPPLY_HMT_TEST_DSN_OR_HMT_PGLITE_CLI")
    port = free_port()
    command = [
        "node",
        cli,
        "--db=memory://",
        f"--port={port}",
        "--host=127.0.0.1",
        "--max-connections=8",
    ]
    with child_service(command, port, folder / "postgres.log"):
        yield (
            f"host=127.0.0.1 port={port} dbname=postgres user=postgres "
            "sslmode=disable connect_timeout=5"
        )


@contextmanager
def redis_service(folder):
    configured = os.environ.get("HMT_TEST_REDIS_URL")
    if configured:
        yield configured
        return
    binary = os.environ.get("HMT_REDIS_SERVER")
    if binary is None or not Path(binary).is_file():
        raise RuntimeError("SUPPLY_HMT_TEST_REDIS_URL_OR_HMT_REDIS_SERVER")
    port = free_port()
    command = [
        binary,
        "--port",
        str(port),
        "--bind",
        "127.0.0.1",
        "--protected-mode",
        "yes",
        "--save",
        "",
        "--appendonly",
        "no",
    ]
    with child_service(command, port, folder / "redis.log"):
        yield f"redis://127.0.0.1:{port}/0"
