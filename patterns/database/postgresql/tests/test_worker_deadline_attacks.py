"""Regression witnesses for independent review: diagnostics/config cannot stall exit."""

import json
import os
import subprocess
import sys
import time

import pytest
from test_worker_contracts import config_data

from hmt_pg_patterns.worker_config import load_config


def diagnostic_pipe(diagnostics):
    closed = "os.close(2)"
    full = """read_fd, write_fd = os.pipe()
os.set_blocking(write_fd, False)
for _ in range(1024):
    try: os.write(write_fd, b'x' * 4096)
    except BlockingIOError: break
else: raise RuntimeError('TEST_PIPE_DID_NOT_FILL')
os.dup2(write_fd, 2)
os.set_blocking(2, True)"""
    return closed if diagnostics == "closed" else full


@pytest.mark.parametrize("diagnostics", ["closed", "full"])
def test_hard_exit_does_not_depend_on_diagnostic_pipe(diagnostics):
    code = "from hmt_pg_patterns.worker_io import process_deadline\nimport os,time\n"
    code += diagnostic_pipe(diagnostics)
    code += "\nwith process_deadline(.1): time.sleep(5)\n"
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=2)
    assert result.returncode == 124
    assert time.monotonic() - started < 2


def test_private_fifo_is_rejected_without_waiting_for_a_writer(tmp_path):
    path = tmp_path / "config.pipe"
    os.mkfifo(path, 0o600)
    code = """from pathlib import Path
from hmt_pg_patterns.worker_config import load_config
import sys
try: load_config(Path(sys.argv[1]))
except PermissionError: raise SystemExit(0)
raise SystemExit(1)
"""
    result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, timeout=2)
    assert result.returncode == 0, result.stderr.decode()
    with pytest.raises(PermissionError):
        load_config(path)


@pytest.mark.parametrize("diagnostics", ["closed", "full"])
@pytest.mark.parametrize("failure", ["config", "request"])
def test_rejection_has_no_blocking_diagnostic_dependency(tmp_path, diagnostics, failure):
    path = tmp_path / "worker.json"
    if failure == "request":
        path.write_text(json.dumps(config_data()))
        path.chmod(0o600)
    code = "import os,sys\nfrom hmt_pg_patterns.worker import main\n"
    code += diagnostic_pipe(diagnostics)
    code += "\nsys.argv=['worker','--config',sys.argv[1]]\nraise SystemExit(main())\n"
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        input=b"invalid-json\n",
        env=dict(os.environ, TAILCAT_PEER_KEY=config_data()["peer_key"]),
        capture_output=True,
        timeout=2,
    )
    assert result.returncode == 1
