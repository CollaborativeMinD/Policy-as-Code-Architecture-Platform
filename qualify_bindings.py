"""Export and verify every default registry binding as a separate ZIP."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from factory import BRANCHES, RETRY_ID, Registry, canonical, digest, export, require, verify


def qualify_one(registry, item, destination):
    identity = item["id"]
    configuration = ("patterns/resilience_ooda/selections/ooda-starter.toml"
                     if identity == RETRY_ID else f"bindings/{identity}.toml")
    folder = destination / identity
    folder.mkdir()
    selection = folder / "selection.toml"
    selection.write_text(
        f'version = 1\nregistry = "patterns@1"\nname = "{identity.lower()}"\n\n[[patterns]]\n'
        f'id = "{identity}"\nversion = {json.dumps(item["version"])}\n'
        f'configuration = "{configuration}"\n', encoding="utf-8", newline="\n",
    )
    archive = folder / f"{identity}.zip"
    receipt_path = folder / "receipt.json"
    receipt = export(registry, selection, archive)
    require(receipt["status"] == "QUALIFIED", f"{identity} did not qualify: {receipt}")
    receipt_bytes = canonical(receipt)
    receipt_path.write_bytes(receipt_bytes)
    checked = verify(registry, archive, receipt_path)
    return {"pattern": identity, "branch": item["branch"], "status": checked["status"],
            "scope": receipt["artifact"].get("scope", "retry-witness"),
            "archive_sha256": checked["archive_sha256"], "receipt_sha256": digest(receipt_bytes),
            "selection_sha256": receipt["resolution"]["selection_sha256"],
            "configuration_sha256": receipt["resolution"]["configuration_sha256"]}


def qualify_all(registry, destination):
    destination = destination.resolve()
    require(not destination.exists(), "choose a new campaign destination")
    audit = registry.audit()
    require(len(audit["factory_bindings"]) == audit["registry_entries"], "default campaign has an unbound entry")
    with TemporaryDirectory(dir=destination.parent) as temporary:
        staged = Path(temporary) / "campaign"
        staged.mkdir()
        entries = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for branch in BRANCHES:
                work = [pool.submit(qualify_one, registry, item, staged) for item in registry.entries.values()
                        if item["branch"] == branch]
                entries.extend(future.result() for future in work)
        report = {"status": "PASS", "registry_sha256": registry.sha256,
                  "bindings_sha256": registry.bindings_sha256, "audit": audit, "patterns": entries}
        (staged / "campaign.json").write_bytes(canonical(report))
        require(not destination.exists(), "campaign destination already exists")
        staged.rename(destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        report = qualify_all(Registry(), args.destination)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Campaign denied: {error}\n")
    print(f'{report["status"]}: {len(report["patterns"])} pattern ZIPs and receipts verified')


if __name__ == "__main__":
    main()
