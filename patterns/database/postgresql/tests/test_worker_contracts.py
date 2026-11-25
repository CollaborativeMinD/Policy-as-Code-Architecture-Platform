"""PG-PEER-001: private configuration, closed request shape, and finite ingress."""

import base64
import json
import os
import time
from uuid import uuid4

import pytest
from pydantic import ValidationError

from hmt_pg_patterns.worker_config import WorkerConfig, load_config
from hmt_pg_patterns.worker_io import IngressRequest, read_frame


def config_data():
    return {
        "database": {
            "host": "127.0.0.1",
            "user": "hmt_peer",
            "profile": "test",
            "sslmode": "disable",
        },
        "peer_key": "nodekey:" + "a" * 64,
        "redis_url": "redis://127.0.0.1:6379/0",
    }


def test_private_configuration_and_link_rejection(tmp_path):
    path = tmp_path / "worker.json"
    path.write_text(json.dumps(config_data()))
    path.chmod(0o600)
    assert load_config(path).binding().db_role == "hmt_peer"
    path.chmod(0o644)
    with pytest.raises(PermissionError):
        load_config(path)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        load_config(link)
    path.chmod(0o600)
    path.write_bytes(b" " * 16385)
    with pytest.raises(ValueError, match="CAPACITY"):
        load_config(path)


@pytest.mark.parametrize(
    "url",
    [
        "redis://remote.example/0",
        "redis://127.0.0.1/1",
        "redis://127.0.0.1/0?ssl_cert_reqs=none",
        "redis:///0",
    ],
)
def test_request_cannot_weaken_projection_config(url):
    values = config_data() | {"redis_url": url}
    with pytest.raises(ValidationError):
        WorkerConfig.model_validate_json(json.dumps(values))


def test_closed_request_and_canonical_payload():
    values = {"stream_id": str(uuid4()), "payload_b64": base64.b64encode(b"payload").decode()}
    request = IngressRequest.model_validate_json(json.dumps(values))
    assert request.payload(7) == b"payload"
    with pytest.raises(ValueError):
        request.payload(6)
    with pytest.raises(ValidationError):
        IngressRequest.model_validate_json(json.dumps(values | {"peer_key": "attacker"}))
    with pytest.raises(ValueError):
        IngressRequest(stream_id=uuid4(), payload_b64="!!!!").payload(10)


@pytest.mark.parametrize(
    "payload,maximum,error",
    [
        (b"abc\n", 10, None),
        (b"abcdef\n", 3, "CAPACITY"),
        (b"a\nb\n", 10, "ONE_REQUEST"),
        (b"abc", 10, "TRUNCATED"),
    ],
)
def test_ingress_frames(payload, maximum, error):
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, payload)
        os.close(write_fd)
        if error:
            with pytest.raises(ValueError, match=error):
                read_frame(read_fd, maximum, time.monotonic() + 1)
        else:
            assert read_frame(read_fd, maximum, time.monotonic() + 1) == b"abc"
    finally:
        os.close(read_fd)


def test_ingress_stall_and_expired_budget():
    read_fd, write_fd = os.pipe()
    try:
        for deadline in (time.monotonic() - 1, time.monotonic() + 0.01):
            with pytest.raises(TimeoutError):
                read_frame(read_fd, 20, deadline)
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.parametrize(
    "maximum,deadline", [(0, 1.0), (True, 1.0), (131073, 1.0), (1, float("nan")), (1, True)]
)
def test_invalid_ingress_limits_fail_before_descriptor_use(maximum, deadline):
    with pytest.raises(ValueError):
        read_frame(-1, maximum, deadline)
