"""Assemble and verify a software binding distribution."""

from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import stat
from native_budget import QualificationBudget
import subprocess
import sys
import tempfile
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from factory import AdmissionError, at, canonical, digest, fields, read_bytes, require


ARCHIVE_LIMIT = 4_194_304
SAFE_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*|__[A-Za-z0-9_]+\.py")


def runtime_release(registry):
    raw = read_bytes(registry.root / "bindings" / "release.json")
    require(digest(raw) == registry.bindings_sha256, "software adapter release pin differs")
    release = json.loads(raw)
    fields(release, ("version", "postgres_manifest_sha256", "files", "defaults"), "software adapter release")
    require(type(release["version"]) is int and release["version"] == 1, "unknown adapter release")
    require(type(release["files"]) is dict and len(release["files"]) <= 24, "adapter inventory exceeds limit")
    supported = {item["id"] for item in registry.entries.values()
                 if item["binding"] in {"rdp-software-v1", "postgres-software-v1"}}
    require(type(release["defaults"]) is dict and release["defaults"].keys() == supported,
            "default policy inventory differs from registry")
    return release


def default_policy(registry, release, identity):
    from policy_runtime.contracts import parse_policy

    path = f"bindings/{identity}.toml"
    raw = read_bytes(at(registry.root, path))
    require(digest(raw) == release["defaults"].get(identity), f"default policy pin differs: {identity}")
    return parse_policy(raw, identity)


def runtime_files(registry, release):
    files = {}
    for name, expected in release["files"].items():
        raw = read_bytes(at(registry.root, name))
        require(digest(raw) == expected, f"adapter release member differs: {name}")
        exported = {"BOUND_STARTER.md": "README.md", "bindings/requirements.lock": "requirements.lock"}.get(name, name)
        if exported.startswith("policy_runtime/hmt_rdp/"):
            exported = exported.removeprefix("policy_runtime/")
        files[exported] = raw
    return files


def original_files(registry, item, release):
    if item["binding"] == "rdp-software-v1":
        return leaf_files(registry, item)
    require(item["binding"] == "postgres-software-v1", "unknown software adapter")
    return postgres_files(registry, item, release)


def leaf_files(registry, item):
    branch = at(registry.root, item["path"])
    source_manifest = registry.evidence(item)
    require((source_manifest["pattern_id"], source_manifest["version"]) == (item["id"], item["version"]),
            "leaf release differs from binding")
    files = {"pattern_reference/__init__.py": b"", "reference/upstream-manifest.json": read_bytes(branch / "manifest.json")}
    for name, target in (("reference.py", "pattern_reference/reference.py"), ("contracts.py", "pattern_reference/contracts.py"),
                         ("SKILL.md", "reference/SKILL.md"), ("evidence/qualification.json", "reference/qualification.json")):
        data = read_bytes(branch / name)
        require(digest(data) == source_manifest["files"][name], f"leaf source pin differs: {name}")
        files[target] = data
    return files


def postgres_files(registry, item, release):
    branch = registry.root / "patterns" / "database" / "postgresql"
    raw = read_bytes(branch / "release" / "artifact_manifest.json", 1_048_576)
    require(digest(raw) == release["postgres_manifest_sha256"], "PostgreSQL manifest pin differs")
    records = {row["path"]: row["sha256"] for row in json.loads(raw)["files"]}
    catalog = registry.evidence(item)
    description, = (row for row in catalog["patterns"] if row["id"] == item["id"])
    chosen = set(catalog["source_inventory"]) | {name for name in records if name.startswith("sql/")}
    chosen |= {description["readme"]}
    files = {"reference/postgres-catalog.json": read_bytes(branch / "catalog.json")}
    for name in sorted(chosen):
        path = at(branch, name)
        data = read_bytes(path)
        require(digest(data) == records.get(name), f"PostgreSQL source pin differs: {name}")
        target = name.removeprefix("src/") if not name.endswith("README.md") else "reference/README.md"
        files[target] = data
    return files


def path_check(name):
    parts = name.split("/")
    require(len(name) <= 180 and all(SAFE_PART.fullmatch(part) and not part.endswith(".")
            and part.split(".")[0].lower() not in
            {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
            for part in parts), "unsupported export path")


def hashes(files):
    index = {}
    folded = set()
    for name, value in sorted(files.items()):
        path_check(name)
        require(name.casefold() not in folded and len(value) <= 262_144, "duplicate or oversized archive member")
        folded.add(name.casefold())
        index[name] = digest(value)
    require(not any(parent.as_posix().casefold() in folded for name in files for parent in PurePosixPath(name).parents),
            "path collides with file")
    return index


def _witness(directory):
    code = ("import runpy,sys; from pathlib import Path; root=Path(sys.argv[1]);"
            "sys.path.insert(0,str(root)); runpy.run_module('policy_runtime.witness',run_name='__main__')")
    proc = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(directory)], cwd=directory,
                          capture_output=True, timeout=QualificationBudget.read(Path(__file__).with_name("qualification_policy.toml")).process_seconds)
    if proc.returncode:
        raise AdmissionError("software binding did not qualify:\n" + proc.stderr.decode(errors="replace")[-3000:])
    return json.loads(proc.stdout)


def build_bundle(registry, item, decision, candidate):
    release = runtime_release(registry)
    files = runtime_files(registry, release)
    files.update(original_files(registry, item, release))
    identity = {"pattern": item["id"], "policy_sha256": digest(decision.selection_bytes)}
    files.update({"binding.json": canonical(identity), "configuration.toml": decision.selection_bytes})
    hashes(files)
    with tempfile.TemporaryDirectory() as work:
        directory = Path(work)
        for name, raw in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        report = _witness(directory)
    manifest = {"version": 1, "format": "software-pattern-v1", "pattern": item["id"],
                "version_selected": item["version"], "binding_sha256": registry.bindings_sha256,
                "origin_sha256": item["evidence_sha256"], "qualification": report, "files": hashes(files)}
    with ZipFile(candidate, "x", compression=ZIP_STORED) as archive:
        for name, raw in sorted((files | {"manifest.json": canonical(manifest)}).items()):
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, raw)
    return verify_bundle(candidate, item, {
        name: raw for name, raw in files.items() if name not in {"binding.json", "configuration.toml"}
    })


def verify_bundle(path, item, released_files, expected=None):
    from policy_runtime.contracts import parse_policy

    raw = read_bytes(path, ARCHIVE_LIMIT)
    stamp = digest(raw)
    require(expected is None or stamp == expected, "archive checksum differs")
    with ZipFile(BytesIO(raw)) as archive:
        files = {}
        require(len(archive.infolist()) <= 100, "too many archive files")
        for member in archive.infolist():
            name = member.filename
            path_check(name)
            require(name not in files and member.file_size <= 262_144 and member.compress_type == ZIP_STORED
                    and stat.S_ISREG(member.external_attr >> 16), "unsupported archive member")
            files[name] = archive.read(member)
    hashes(files)
    manifest_bytes = files.pop("manifest.json")
    manifest = json.loads(manifest_bytes)
    require(manifest["format"] == "software-pattern-v1" and type(manifest["version"]) is int
            and manifest["version"] == 1 and manifest["pattern"] == item["id"]
            and manifest["version_selected"] == item["version"]
            and manifest["files"] == hashes(files), "archive manifest does not reproduce")
    identity = json.loads(files["binding.json"])
    policy_raw = files.pop("configuration.toml")
    files.pop("binding.json")
    require(files == released_files, "archive members differ from admitted release")
    parse_policy(policy_raw, item["id"])
    policy_stamp = digest(policy_raw)
    require(identity == {"pattern": manifest["pattern"], "policy_sha256": policy_stamp},
            "pattern identity does not match policy")
    report = manifest["qualification"]
    require(report["pattern"] == identity["pattern"] and report["policy_sha256"] == policy_stamp
            and report["scope"] == "software" and report["status"] == "PASS"
            and report["undeclared_setting"] == "DENY", "qualification is not bound to archive")
    return {"format": manifest["format"], "pattern": identity["pattern"], "scope": report["scope"],
            "binding_sha256": manifest["binding_sha256"], "origin_sha256": manifest["origin_sha256"],
            "archive_sha256": stamp, "manifest_sha256": digest(manifest_bytes), "selection_sha256": policy_stamp,
            "qualified_profiles": [identity["pattern"]]}
