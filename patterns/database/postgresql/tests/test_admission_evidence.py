"""PG-ADMIT-006: content identities change with source, and receipts are immutable."""

import pytest

from tools.admission_evidence import source_snapshot, write_json
from tools.admit import observed_gate


def test_changed_source_changes_identity_and_restoration_matches(tmp_path):
    source = tmp_path / "src/unit.py"
    source.parent.mkdir()
    source.write_text("value = 1\n")
    before = source_snapshot(tmp_path)
    source.write_text("value = 2\n")
    assert source_snapshot(tmp_path)["source_digest"] != before["source_digest"]
    source.write_text("value = 1\n")
    assert source_snapshot(tmp_path)["source_digest"] == before["source_digest"]


def test_generated_bytecode_is_not_source_truth(tmp_path):
    source = tmp_path / "src/unit.py"
    source.parent.mkdir()
    source.write_text("value = 1\n")
    before = source_snapshot(tmp_path)
    cache = source.parent / "__pycache__"
    cache.mkdir()
    (cache / "unit.pyc").write_bytes(b"disposable")
    assert source_snapshot(tmp_path)["source_digest"] == before["source_digest"]


def test_prior_receipt_is_not_rewritten(tmp_path):
    path = tmp_path / "receipt.json"
    write_json(path, {"status": "FAIL"})
    with pytest.raises(FileExistsError):
        write_json(path, {"status": "PASS"})
    assert '"FAIL"' in path.read_text()


def test_gate_exception_produces_nonpassing_receipt(tmp_path):
    def broken():
        raise ValueError("INJECTED_CONTRACT_FAILURE")

    result = observed_gate("gate", broken, tmp_path)
    assert result["status"] == "FAIL"
    assert result["reason"] == "INJECTED_CONTRACT_FAILURE"
    assert (tmp_path / "gate.json").is_file()
