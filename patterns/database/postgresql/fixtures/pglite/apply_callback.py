"""Apply one hash-bound fixture callback hook; preserve upstream bytes before edit."""

import argparse
import hashlib
import json
from pathlib import Path

UPSTREAM = "c4e70a0a9f71c5a0509e863d9ed87f8723c96d7c1dfea2b20de0e423d09356d1"
PATCHED = "13dd30ac3ddc65d1f7f25c51b6a2fd37158480acaa753bd9eef0ce244207cca3"
OLD = "let a=g(this,j).length-g(this,U);return a>n&&(a=n),this.mod.HEAPU8.set(g(this,j).subarray(g(this,U),g(this,U)+a),_),S(this,U,g(this,U)+a),a"
NEW = "let a=g(this,j).length-g(this,U);if(a===0&&this._hmtFixtureReadMore){const b=this._hmtFixtureReadMore(n);this.mod.HEAPU8.set(b,_);return b.length}return a>n&&(a=n),this.mod.HEAPU8.set(g(this,j).subarray(g(this,U),g(this,U)+a),_),S(this,U,g(this,U)+a),a"


def apply(root: Path) -> str:
    """Refuse every upstream or transformed byte sequence except the recorded pair."""
    packages = root / "node_modules" / "@electric-sql"
    for name, version in (("pglite", "0.5.15"), ("pglite-socket", "0.2.18")):
        actual = json.loads((packages / name / "package.json").read_text())["version"]
        if actual != version:
            raise ValueError("FIXTURE_PACKAGE_VERSION_MISMATCH")
    target = packages / "pglite" / "dist" / "chunk-O74Z5DUS.js"
    original = target.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest == PATCHED:
        return "fixture callback already applied and hash verified"
    if digest != UPSTREAM:
        raise ValueError("FIXTURE_UPSTREAM_HASH_MISMATCH")
    text = original.decode()
    if text.count(OLD) != 1:
        raise ValueError("FIXTURE_PATCH_TARGET_COUNT")
    patched = text.replace(OLD, NEW).encode()
    if hashlib.sha256(patched).hexdigest() != PATCHED:
        raise ValueError("FIXTURE_PATCH_OUTPUT_HASH_MISMATCH")
    snapshot = root / "upstream-snapshots" / "pglite-0.5.15-chunk-O74Z5DUS.js"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if snapshot.exists() and snapshot.read_bytes() != original:
        raise ValueError("FIXTURE_UPSTREAM_SNAPSHOT_CONFLICT")
    snapshot.write_bytes(original)
    target.write_bytes(patched)
    return "fixture callback applied; upstream preserved and both hashes verified"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("npm_root", type=Path)
    print(apply(parser.parse_args().npm_root.resolve()))


if __name__ == "__main__":
    main()
