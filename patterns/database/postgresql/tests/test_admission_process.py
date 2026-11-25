"""PG-ADMIT-005: actual subprocess failure, timeout, and bounded output witnesses."""

import os
import sys
import pytest

from tools import admission_process


def execute(tmp_path, script, timeout=2):
    return admission_process.run_command(
        [sys.executable, "-c", script], tmp_path, tmp_path / "logs", dict(os.environ), timeout
    )


def test_real_process_success_retains_both_logs(tmp_path):
    result = execute(
        tmp_path, "import sys; print('observed'); print('diagnostic', file=sys.stderr)"
    )
    assert result["status"] == "PASS"
    assert (tmp_path / "logs/pytest.stdout.log").read_text() == "observed\n"
    assert (tmp_path / "logs/pytest.stderr.log").read_text() == "diagnostic\n"


def test_nonzero_is_not_a_success_receipt(tmp_path):
    result = execute(tmp_path, "raise SystemExit(4)")
    assert result["status"] == "FAIL" and result["returncode"] == 4


def test_timeout_revokes_execution(tmp_path):
    result = execute(tmp_path, "import time; time.sleep(10)", 0.1)
    assert result["status"] == "FAIL" and result["reason"] == "PROCESS_TIMEOUT"
    assert result["seconds"] < 5


def test_output_budget_terminates_flood(tmp_path, monkeypatch):
    monkeypatch.setattr(admission_process, "OUTPUT_LIMIT", 16)
    result = execute(tmp_path, "import os; os.write(1, b'x' * 100000)")
    assert result["reason"] == "PROCESS_OUTPUT_LIMIT"
    assert result["captured_bytes"] == 16
    assert (tmp_path / "logs/pytest.stdout.log").stat().st_size == 16


@pytest.mark.parametrize("timeout", [0, -1, 7201])
def test_invalid_timeout_fails_before_process(tmp_path, timeout):
    with pytest.raises(ValueError, match="TIMEOUT_BOUND"):
        execute(tmp_path, "raise SystemExit(0)", timeout)
