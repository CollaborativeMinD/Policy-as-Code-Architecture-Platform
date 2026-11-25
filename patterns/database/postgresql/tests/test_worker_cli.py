"""CLI framing, secret-free failure, and bounded process lifecycle witnesses."""

import base64
import json
import os
import subprocess
import sys
import time
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from test_worker_contracts import config_data

from hmt_pg_patterns import worker
from hmt_pg_patterns.worker_io import _expired, process_deadline


def test_cli_success_and_rejection(tmp_path, monkeypatch, capsys):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data()))
    path.chmod(0o600)
    monkeypatch.setattr(sys, "argv", ["worker", "--config", str(path)])
    monkeypatch.setenv("TAILCAT_PEER_KEY", config_data()["peer_key"])
    request = json.dumps(
        {"stream_id": str(uuid4()), "payload_b64": base64.b64encode(b"payload").decode()}
    ).encode()
    with patch.object(worker, "read_frame", return_value=request):
        with patch.object(worker, "serve", return_value={"status": "COMMITTED"}):
            monkeypatch.setattr(sys, "stdin", Mock())
            assert worker.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "COMMITTED"
    monkeypatch.setenv("TAILCAT_PEER_KEY", "invalid")
    assert worker.main() == 1
    assert capsys.readouterr().err == ""


def test_deadline_cancellation_and_hard_exit_contract():
    with patch("hmt_pg_patterns.worker_io.threading.Timer") as timer:
        with process_deadline(0.2):
            assert timer.return_value.start.called
        assert timer.return_value.cancel.called
    with patch("hmt_pg_patterns.worker_io.os.write") as output:
        with patch("hmt_pg_patterns.worker_io.os._exit") as terminate:
            _expired()
            terminate.assert_called_once_with(124)
            output.assert_not_called()


def test_hard_deadline_terminates_a_blocked_process():
    code = "from hmt_pg_patterns.worker_io import process_deadline; import time\nwith process_deadline(.1): time.sleep(5)"
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, timeout=2, env=dict(os.environ)
    )
    assert result.returncode == 124
    assert result.stderr == b""
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("seconds", [0, True, float("nan"), 31])
def test_invalid_hard_deadline_never_launches_watchdog(seconds):
    with pytest.raises(ValueError):
        with process_deadline(seconds):
            raise AssertionError("invalid deadline admitted")
