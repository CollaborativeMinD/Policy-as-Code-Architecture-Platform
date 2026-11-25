"""Resolve a registry selection and export only a qualified composition."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
from native_budget import QualificationBudget
import subprocess
import sys
import tempfile
import tomllib
from zipfile import BadZipFile


ROOT = Path(__file__).resolve().parent
REGISTRY_ID = "patterns@1"
BRANCHES = ("behavioral", "creational", "structural", "database", "resilience")
RETRY_ID = "resilience-ooda"
MINIMUM_POLICY_FILES = {"bundle_exporter.py", "retry_runtime.py", "witness.py", "requirements.lock", "catalog.toml"}
MAX_DECLARATION_BYTES = 131_072


class AdmissionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AdmissionError(message)


def fields(value, expected, label):
    require(type(value) is dict and value.keys() == set(expected), f"{label}: unexpected or missing fields")


def digest(raw):
    return sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def read_bytes(path, maximum=MAX_DECLARATION_BYTES):
    with path.open("rb") as source:
        value = source.read(maximum + 1)
    require(len(value) <= maximum, f"file exceeds its limit: {path.name}")
    return value


def rooted(base, raw):
    require(type(raw) is str and bool(raw) and "\\" not in raw and ":" not in raw, "invalid registry path")
    parts = raw.split("/")
    require(all(part and part not in {".", ".."} for part in parts), "registry path leaves its scope")
    return base.joinpath(*PurePosixPath(raw).parts).resolve().relative_to(base.resolve())


def at(base, name):
    return base / rooted(base, name)


@dataclass(frozen=True)
class Resolution:
    record: dict
    selection_bytes: bytes | None


class Registry:
    def __init__(self, root=ROOT):
        self.root = root.resolve()
        raw = read_bytes(self.root / "registry.toml")
        declaration = tomllib.loads(raw.decode())
        fields(declaration, ("version", "registry", "intake_sha256", "bindings_sha256", "entries"), "registry")
        require(type(declaration["version"]) is int and declaration["version"] == 1
                and declaration["registry"] == REGISTRY_ID, "unsupported registry")
        require(type(declaration["entries"]) is list and 0 < len(declaration["entries"]) <= 128,
                "invalid registry entry count")
        self.sha256 = digest(raw)
        self.intake_sha256 = declaration["intake_sha256"]
        self.bindings_sha256 = declaration["bindings_sha256"]
        self.entries = {}
        for item in declaration["entries"]:
            fields(item, ("id", "branch", "version", "path", "evidence", "evidence_sha256", "binding"), "entry")
            require(type(item["id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", item["id"])
                    and item["id"] not in self.entries, "duplicate or invalid pattern identity")
            require(item["branch"] in BRANCHES and type(item["version"]) is str, "unknown branch or version")
            allowed = {"behavioral": "rdp-software-v1", "creational": "rdp-software-v1",
                       "structural": "rdp-software-v1", "database": "postgres-software-v1", "resilience": "ooda-v1"}
            require(item["binding"] in {"reference", allowed[item["branch"]]}, "unknown adapter for branch")
            if item["binding"] == "ooda-v1":
                require((item["id"], item["branch"], item["path"], item["evidence"]) ==
                        (RETRY_ID, "resilience", "patterns/resilience_ooda",
                         "patterns/resilience_ooda/release.json"), "retry adapter scope differs")
            self.entries[item["id"]] = item

    def evidence(self, item):
        raw = read_bytes(at(self.root, item["evidence"]))
        require(digest(raw) == item["evidence_sha256"], f"evidence pin differs: {item['id']}")
        return json.loads(raw)

    def retry_release(self):
        item = self.entries[RETRY_ID]
        require(item["binding"] == "ooda-v1", "OODA exporter is not admitted")
        release = self.evidence(item)
        fields(release, ("id", "version", "files"), "OODA release")
        require((release["id"], release["version"]) == (item["id"], item["version"]), "OODA release identity differs")
        require(type(release["files"]) is dict and MINIMUM_POLICY_FILES <= release["files"].keys(),
                "OODA release is incomplete")
        require(len(release["files"]) <= 32, "OODA inventory exceeds its limit")
        branch = at(self.root, item["path"])
        contents = {}
        for path, want in release["files"].items():
            raw = read_bytes(at(branch, path))
            require(digest(raw) == want, f"OODA release member differs: {path}")
            contents[path] = raw
        return contents

    def resolve(self, path):
        raw = read_bytes(path)
        request = tomllib.loads(raw.decode())
        fields(request, ("version", "registry", "name", "patterns"), "selection")
        require(type(request["version"]) is int and request["version"] == 1
                and request["registry"] == REGISTRY_ID, "selection names an unsupported registry")
        require(type(request["name"]) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", request["name"]),
                "invalid build name")
        require(type(request["patterns"]) is list and 0 < len(request["patterns"]) <= 32, "invalid pattern count")
        chosen = {}
        configurations = {}
        holds = []
        profile_bytes = None
        config_hash = None
        for request_item in request["patterns"]:
            require(type(request_item) is dict and request_item.keys() in
                    ({"id", "version"}, {"id", "version", "configuration"}), "invalid pattern selection")
            key = request_item["id"]
            require(type(key) is str and key in self.entries and key not in chosen, "unknown or duplicate pattern")
            item = self.entries[key]
            require(item["version"] == request_item["version"], f"pattern {key} version is not available")
            self.evidence(item)
            chosen[key] = {"id": key, "version": item["version"], "branch": item["branch"],
                           "binding": item["binding"], "evidence_sha256": item["evidence_sha256"]}
            if item["binding"] == "reference":
                holds.append({"pattern": key, "reason": "NO_QUALIFIED_FACTORY_BINDING"})
            elif "configuration" in request_item:
                configurations[key] = read_bytes(at(self.root, request_item["configuration"]), 65_536)
            else:
                holds.append({"pattern": key, "reason": "CONFIGURATION_REQUIRED"})
        if len(chosen) != 1:
            holds.append({"reason": "COMPOSITION_WITNESS_REQUIRED"})
        if not holds:
            key, = chosen
            profile_bytes = configurations[key]
            config_hash = digest(profile_bytes)
            self.validate_configuration(key, profile_bytes)
        continuity = digest(read_bytes(self.root / "patterns" / "DESIGN_PATTERNS.md"))
        return Resolution({
            "name": request["name"], "registry": REGISTRY_ID, "registry_sha256": self.sha256,
            "continuity_sha256": continuity, "selection_sha256": digest(raw), "configuration_sha256": config_hash,
            "patterns": [chosen[key] for key in sorted(chosen)], "holds": holds,
            "status": "HOLD" if holds else "READY_FOR_QUALIFICATION",
        }, profile_bytes)

    def validate_configuration(self, key, raw):
        if self.entries[key]["binding"] != "ooda-v1":
            from bound_release import default_policy, runtime_files, runtime_release
            from policy_runtime.contracts import parse_policy

            release = runtime_release(self)
            runtime_files(self, release)
            configured = parse_policy(raw, key)
            declared = default_policy(self, release, key)
            require(configured.keys() == declared.keys(), "UNDECLARED_OR_MISSING_SETTING")
            return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _stage(root, self.retry_release())
            configuration = root / "selection.toml"
            configuration.write_bytes(raw)
            check = ("import sys; from pathlib import Path; root=Path(sys.argv[1]); "
                     "sys.path.insert(0,str(root)); from retry_runtime import load_policy; "
                     "load_policy(root/'selection.toml')")
            _run(root, check)

    def audit(self):
        from bound_release import default_policy, original_files, runtime_files, runtime_release

        raw = read_bytes(self.root / "evidence" / "intake.json", 524_288)
        require(digest(raw) == self.intake_sha256, "intake evidence digest mismatch")
        intake = json.loads(raw)
        preserved = intake["untouched_branch_files"]
        for name, expected in preserved.items():
            require(digest(read_bytes(at(self.root, name), 8_388_608)) == expected, f"intake bytes changed: {name}")
        release = runtime_release(self)
        runtime_files(self, release)
        for item in self.entries.values():
            self.evidence(item)
            require(at(self.root, item["path"]).is_dir(), f"missing pattern: {item['id']}")
            if item["binding"] in {"rdp-software-v1", "postgres-software-v1"}:
                original_files(self, item, release)
                default_policy(self, release, item["id"])
        self.retry_release()
        return {"status": "PASS", "registry_entries": len(self.entries), "preserved_files": len(preserved),
                "intake_source_sha256": intake["source_sha256"],
                "factory_bindings": [item["id"] for item in self.entries.values() if item["binding"] != "reference"]}


def _stage(root, contents):
    for name, raw in contents.items():
        target = at(root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def _run(root, bootstrap, *arguments):
    proc = subprocess.run([sys.executable, "-I", "-B", "-c", bootstrap, str(root), *map(str, arguments)],
                          cwd=root, capture_output=True, timeout=QualificationBudget.read(Path(__file__).with_name("qualification_policy.toml")).process_seconds)
    require(proc.returncode == 0, proc.stderr.decode(errors="replace").strip() or "adapter failed")
    return proc.stdout


def _adapter(root, contents, *arguments):
    _stage(root, contents)
    bootstrap = ("import runpy,sys; from pathlib import Path; root=Path(sys.argv.pop(1)); "
                 "sys.path.insert(0,str(root)); runpy.run_path(str(root/'bundle_exporter.py'),run_name='__main__')")
    return json.loads(_run(root, bootstrap, *arguments))


def export(registry, selection, destination):
    decision = registry.resolve(selection)
    if decision.record["status"] == "HOLD":
        return decision.record
    destination = destination.resolve()
    require(destination.suffix == ".zip" and not destination.exists(), "choose a new ZIP destination")
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        root = Path(directory)
        candidate = root / "candidate.zip"
        selected, = decision.record["patterns"]
        if selected["binding"] == "ooda-v1":
            contents = registry.retry_release()
            config = root / "requested.toml"
            config.write_bytes(decision.selection_bytes)
            receipt = _adapter(root, contents, "export", config, candidate)
        else:
            from bound_release import build_bundle
            receipt = build_bundle(registry, registry.entries[selected["id"]], decision, candidate)
        require(receipt["selection_sha256"] == decision.record["configuration_sha256"],
                "qualification did not bind the selected configuration")
        os.link(candidate, destination)
    return {"status": "QUALIFIED", "resolution": decision.record,
            "resolution_sha256": digest(canonical(decision.record)), "artifact": receipt}


def verify(registry, archive, receipt_path):
    receipt = json.loads(read_bytes(receipt_path))
    fields(receipt, ("status", "resolution", "resolution_sha256", "artifact"), "factory receipt")
    decision = receipt["resolution"]
    require(type(decision) is dict and receipt["status"] == "QUALIFIED"
            and digest(canonical(decision)) == receipt["resolution_sha256"], "factory receipt was altered")
    require(decision.get("registry_sha256") == registry.sha256
            and decision.get("continuity_sha256") ==
            digest(read_bytes(registry.root / "patterns" / "DESIGN_PATTERNS.md"))
            and decision.get("status") == "READY_FOR_QUALIFICATION", "receipt differs from the active registry")
    require(decision.get("configuration_sha256") == receipt["artifact"].get("selection_sha256"),
            "receipt does not bind the configuration")
    selected, = decision["patterns"]
    current = registry.entries[selected["id"]]
    require(selected["binding"] == current["binding"] and selected["version"] == current["version"]
            and selected["evidence_sha256"] == current["evidence_sha256"], "receipt pattern binding differs")
    if current["binding"] == "ooda-v1":
        with tempfile.TemporaryDirectory() as directory:
            observed = _adapter(Path(directory), registry.retry_release(), "verify", archive.resolve(),
                                "--sha256", receipt["artifact"]["archive_sha256"])
    else:
        from bound_release import original_files, runtime_files, runtime_release, verify_bundle

        release = runtime_release(registry)
        released_files = runtime_files(registry, release) | original_files(registry, current, release)
        observed = verify_bundle(archive, current, released_files, expected=receipt["artifact"]["archive_sha256"])
        require(observed["pattern"] == current["id"] and observed["binding_sha256"] == registry.bindings_sha256
                and observed["origin_sha256"] == current["evidence_sha256"], "receipt pattern identity differs")
    require(observed == receipt["artifact"], "factory receipt set differs from archive")
    return {"status": "PASS", "archive_sha256": observed["archive_sha256"],
            "resolution_sha256": receipt["resolution_sha256"], "qualified_profiles": observed["qualified_profiles"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    commands.add_parser("audit")
    commands.add_parser("plan").add_argument("selection", type=Path)
    build = commands.add_parser("export")
    build.add_argument("selection", type=Path)
    build.add_argument("destination", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("archive", type=Path)
    check.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    try:
        registry = Registry()
        if args.command == "list":
            result = {"entries": list(registry.entries.values())}
        elif args.command == "audit":
            result = registry.audit()
        elif args.command == "plan":
            result = registry.resolve(args.selection).record
        elif args.command == "export":
            result = export(registry, args.selection, args.destination)
        else:
            result = verify(registry, args.archive, args.receipt)
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Registry denied: {error}\n")
    print(canonical(result).decode(), end="")
    return 2 if result.get("status") == "HOLD" else 0


if __name__ == "__main__":
    raise SystemExit(main())
