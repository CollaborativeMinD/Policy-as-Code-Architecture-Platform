"""Export a pinned retry selection as a deterministic ZIP with an admission receipt."""

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
from zipfile import BadZipFile, ZIP_STORED, ZipFile, ZipInfo

from retry_runtime import MAX_POLICY_BYTES, PATTERNS, PolicyError, fields, parse_policy, require


ROOT = Path(__file__).resolve().parent
MAX_ARCHIVE_BYTES = 2_097_152
MEMBER_LIMIT = 131_072
SHA256 = re.compile(r"[0-9a-f]{64}")
WORD = re.compile(r"[a-zA-Z0-9_.-]+")


def digest(raw):
    return sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def read(path, limit):
    with path.open("rb") as source:
        result = source.read(limit + 1)
    require(len(result) <= limit, f"{path.name} exceeds its byte limit")
    return result


def member_name(name):
    require(type(name) is str and len(name) <= 200, "invalid archive path")
    parts = name.split("/")
    require(all(WORD.fullmatch(part) and part not in {".", ".."} and not part.endswith((".", " "))
                and part.split(".")[0].lower() not in
                {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
                for part in parts), f"unsafe archive path: {name}")
    return PurePosixPath(name)


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON key in manifest")
        value[key] = item
    return value


def _catalog(raw):
    catalog = tomllib.loads(raw.decode())
    fields(catalog, ("version", "bundle", "release", "source_archive", "source_sha256", "source_prefix",
                     "manifest_sha256", "tenacity", "evidence", "patterns"), "catalog")
    require(type(catalog["version"]) is int and catalog["version"] == 1, "unknown catalog schema")
    require(catalog["bundle"] == "resilience-ooda" and catalog["release"] == "1", "unexpected source release")
    require(type(catalog["patterns"]) is dict and catalog["patterns"].keys() == PATTERNS,
            "catalog bindings differ from supported patterns")
    require(type(catalog["evidence"]) is list and len(catalog["evidence"]) > 0, "missing catalog evidence")
    for key in ("source_sha256", "manifest_sha256"):
        require(type(catalog[key]) is str and SHA256.fullmatch(catalog[key]), "invalid source pin")
    return catalog


def _sources_for(catalog, pattern_kinds):
    selected = [catalog["patterns"][key] for key in pattern_kinds] + catalog["evidence"]
    return sorted({str(member_name(name)) for name in selected})


def load_source(path, pattern_kinds):
    raw = read(path, MAX_POLICY_BYTES)
    catalog = _catalog(raw)
    source_path = path.parent / member_name(catalog["source_archive"])
    source_bytes = read(source_path, MAX_ARCHIVE_BYTES)
    require(digest(source_bytes) == catalog["source_sha256"], "source archive digest mismatch")
    prefix = member_name(catalog["source_prefix"])
    manifest_name = str(prefix / "MANIFEST.sha256.json")
    selections = _sources_for(catalog, pattern_kinds)
    pending = {}
    with ZipFile(BytesIO(source_bytes)) as archive:
        raw_manifest = archive.read(manifest_name)
        require(digest(raw_manifest) == catalog["manifest_sha256"], "source manifest digest mismatch")
        original = json.loads(raw_manifest, object_pairs_hook=_unique_json_object)["files"]
        for relative in selections:
            source = str(prefix / member_name(relative))
            info = archive.getinfo(source)
            require(info.file_size <= MEMBER_LIMIT, "source member too large")
            data = archive.read(info)
            require(digest(data) == original.get(relative), f"source member digest mismatch: {relative}")
            pending[f"reference/{relative}"] = data
        pending["reference/upstream-manifest.json"] = raw_manifest
    return catalog, raw, pending


@dataclass(frozen=True)
class ExportReceipt:
    archive_sha256: str
    manifest_sha256: str
    selection_sha256: str
    catalog_sha256: str
    source_sha256: str
    qualified_profiles: tuple[str, ...]


def _file_index(files):
    seen = set()
    directories = {}
    index = {}
    for name, raw in sorted(files.items()):
        parents = member_name(name).parents
        folded = name.casefold()
        require(folded not in seen and folded not in directories and len(raw) <= MEMBER_LIMIT,
                "colliding or oversized export member")
        for parent in parents:
            key = str(parent).casefold()
            require(key not in seen and directories.setdefault(key, str(parent)) == str(parent),
                    "file and directory collision")
        seen.add(folded)
        index[name] = digest(raw)
    return index


def verify_bundle(path: Path, *, expected_sha256: str | None = None) -> ExportReceipt:
    raw_archive = read(path, MAX_ARCHIVE_BYTES)
    archive_sha256 = digest(raw_archive)
    require(expected_sha256 is None or archive_sha256 == expected_sha256, "export digest mismatch")
    with ZipFile(BytesIO(raw_archive)) as archive:
        files = {}
        members = archive.infolist()
        require(0 < len(members) <= 32 and sum(item.file_size for item in members) <= MAX_ARCHIVE_BYTES,
                "archive exceeds extraction limits")
        for item in members:
            member_name(item.filename)
            require(item.filename not in files and item.file_size <= MEMBER_LIMIT and item.compress_type == ZIP_STORED
                    and stat.S_ISREG(item.external_attr >> 16), "duplicate, oversized, or unsupported member")
            files[item.filename] = archive.read(item)
        require(sum(name.casefold() == "manifest.json" for name in files) == 1, "ambiguous bundle manifest")
        raw_manifest = files.pop("manifest.json")
    manifest = json.loads(raw_manifest, object_pairs_hook=_unique_json_object)
    fields(manifest, ("version", "name", "catalog", "catalog_sha256", "source_sha256", "source_manifest_sha256",
                      "selection_sha256", "qualification", "files"), "bundle manifest")
    require(type(manifest["version"]) is int and manifest["version"] == 1
            and _file_index(files) == manifest["files"], "bundle file digest mismatch")
    policy = parse_policy(files["selection.toml"])
    require((policy.name, policy.catalog, policy.sha256) ==
            (manifest["name"], manifest["catalog"], manifest["selection_sha256"]), "manifest selection mismatch")
    for key in ("catalog_sha256", "source_sha256", "source_manifest_sha256"):
        require(type(manifest[key]) is str and SHA256.fullmatch(manifest[key]), "invalid provenance digest")
    catalog_raw = files["catalog.toml"]
    require(digest(catalog_raw) == manifest["catalog_sha256"], "packaged catalog digest mismatch")
    catalog = _catalog(catalog_raw)
    require((catalog["source_sha256"], catalog["manifest_sha256"]) ==
            (manifest["source_sha256"], manifest["source_manifest_sha256"]), "manifest does not match source pins")
    reference_names = {f"reference/{path}" for path in _sources_for(catalog, {p.kind for p in policy.profiles.values()})}
    require(set(files) == reference_names | {"reference/upstream-manifest.json", "selection.toml", "catalog.toml",
            "README.md", "retry_runtime.py", "witness.py", "requirements.lock"}, "archive payload differs from selection")
    origin = files["reference/upstream-manifest.json"]
    require(digest(origin) == manifest["source_manifest_sha256"],
            "origin manifest digest mismatch")
    original = json.loads(origin, object_pairs_hook=_unique_json_object)["files"]
    require(all(digest(content) == original.get(name.removeprefix("reference/"))
                for name, content in files.items()
                if name.startswith("reference/") and name != "reference/upstream-manifest.json"),
            "packaged reference differs from original member")
    witness = manifest["qualification"]
    expected = {name: {"kind": profile.kind, "status": "PASS"} for name, profile in policy.profiles.items()}
    require(type(witness) is dict and witness.get("status") == "PASS"
            and witness.get("selection_sha256") == policy.sha256 and witness.get("tenacity") == catalog["tenacity"]
            and witness.get("profiles") == expected, "manifest qualification mismatch")
    return ExportReceipt(archive_sha256, digest(raw_manifest), policy.sha256, manifest["catalog_sha256"],
                         manifest["source_sha256"], tuple(sorted(expected)))


def _qualify(staged: Path, expected_tenacity):
    code = ("import runpy,sys; from pathlib import Path; root=Path(sys.argv[1]); "
            "sys.path.insert(0,str(root)); runpy.run_path(str(root/'witness.py'), run_name='__main__')")
    reply = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(staged)], cwd=staged,
                           capture_output=True, timeout=30)
    if reply.returncode:
        raise PolicyError(f"clean-directory witness failed:\n{reply.stderr.decode(errors='replace')[-3500:]}")
    report = json.loads(reply.stdout)
    require(report["tenacity"] == expected_tenacity, "witness dependency differs from catalog pin")
    return report


def export_bundle(selection_toml: Path, catalog: Path, destination: Path) -> ExportReceipt:
    require(destination.suffix == ".zip" and not destination.exists(), "choose a new ZIP destination")
    raw = read(selection_toml, MAX_POLICY_BYTES)
    policy = parse_policy(raw)
    descriptor, descriptor_raw, references = load_source(catalog, {p.kind for p in policy.profiles.values()})
    files = {"selection.toml": raw, "catalog.toml": descriptor_raw, "README.md": read(ROOT / "STARTER.md", MEMBER_LIMIT),
             **{name: read(ROOT / name, MEMBER_LIMIT) for name in ("retry_runtime.py", "witness.py", "requirements.lock")},
             **references}
    index = _file_index(files)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        temp = Path(temp)
        staged = temp / "staged"
        for name, data in files.items():
            path = staged / member_name(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        report = _qualify(staged, descriptor["tenacity"])
        manifest = {"version": 1, "name": policy.name, "catalog": policy.catalog,
                    "catalog_sha256": digest(descriptor_raw), "source_sha256": descriptor["source_sha256"],
                    "source_manifest_sha256": descriptor["manifest_sha256"], "selection_sha256": policy.sha256,
                    "qualification": report, "files": index}
        candidate = temp / "candidate.zip"
        with ZipFile(candidate, "x", compression=ZIP_STORED) as archive:
            for name, content in sorted((files | {"manifest.json": json_bytes(manifest)}).items()):
                info = ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, content)
        receipt = verify_bundle(candidate)
        os.link(candidate, destination)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("selection", type=Path)
    export.add_argument("destination", type=Path)
    export.add_argument("--catalog", type=Path, default=ROOT / "catalog.toml")
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    verify.add_argument("--sha256")
    args = parser.parse_args()
    try:
        receipt = (export_bundle(args.selection, args.catalog, args.destination) if args.command == "export"
                   else verify_bundle(args.archive, expected_sha256=args.sha256))
    except (ValueError, KeyError, OSError, BadZipFile, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Export denied: {error}\n")
    print(json_bytes(asdict(receipt)).decode(), end="")


if __name__ == "__main__":
    main()
