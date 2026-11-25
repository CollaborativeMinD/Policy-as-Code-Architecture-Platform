"""Export selected patterns only through native resolution, qualification and verification."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256

from factory import Registry, export, verify

TITLE = "Architecture Platform"
OPERATIONS = {"selection.export"}


def validate(binding, inputs):
    if inputs != {}:
        raise ValueError("Selection exports take no caller-supplied paths")


def resolve(path):
    registry = Registry()
    record = registry.resolve(path).record
    if record["status"] != "READY_FOR_QUALIFICATION":
        raise ValueError("Selection on HOLD")
    return registry, record, sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def observe(binding):
    _, record, revision = resolve(binding["source"])
    return revision, ", ".join(p["branch"] + " · " + p["id"] for p in record["patterns"])


def execute(binding, inputs, directory, receipt_id, revision):
    output = directory / (receipt_id + ".zip")
    with TemporaryDirectory(dir=directory) as tmp:
        stage = Path(tmp)
        selection = stage / "selection.toml"
        selection.write_bytes(binding["source"].read_bytes())
        registry, record, stamp = resolve(selection)
        if stamp != revision:
            raise ValueError("Selection changed")
        archive = stage / "bundle.zip"
        receipt = export(registry, selection, archive)
        if receipt["status"] != "QUALIFIED" or receipt["resolution"] != record:
            raise ValueError("Qualification or revision mismatch")
        witness = stage / "receipt.json"
        witness.write_text(json.dumps(receipt))
        verify(registry, archive, witness)
        archive.replace(output)
        witness.replace(output.with_suffix(".receipt.json"))
    return {"status": "QUALIFIED", "zip": output.name, "sha256": sha256(output.read_bytes()).hexdigest(),
            "selection_sha256": record["selection_sha256"]}
