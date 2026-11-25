"""Copy a bounded source population; only isolated copies receive mutations."""

import ast
import difflib
from pathlib import Path

from .admission_evidence import file_digest, source_snapshot, write_json


def freeze_source(root, target):
    """Preserve exact source bytes and reject drift while making the frozen copy."""
    root, target = Path(root).resolve(), Path(target).resolve()
    snapshot = source_snapshot(root)
    target.mkdir(parents=True, exist_ok=False)
    for relative in snapshot["files"]:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / relative).read_bytes())
    copied = source_snapshot(target)
    if copied["files"] != snapshot["files"] or source_snapshot(root)["files"] != snapshot["files"]:
        raise ValueError("SOURCE_CHANGED_DURING_FREEZE")
    return snapshot


def mutation_path(root, patch):
    """Reject absolute paths, traversal, symlinks, and patches outside code or SQL."""
    root, relative = Path(root).resolve(), Path(patch.path)
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[0] not in {"src", "sql"}
    ):
        raise ValueError("MUTATION_PATH_OUTSIDE_COPY")
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("MUTATION_PATH_OUTSIDE_COPY")
    if path.suffix not in {".py", ".sql"}:
        raise ValueError("MUTATION_SOURCE_KIND")
    return path


def apply_mutation(root, mutation, folder):
    """Replace exactly one admitted anchor and preserve its full unified diff."""
    path = mutation_path(root, mutation.patch)
    original = path.read_bytes()
    if len(original) > 65536:
        raise ValueError("MUTATION_FILE_SIZE_BOUND")
    text = original.decode("utf-8")
    patch = mutation.patch
    if text.count(patch.before) != 1:
        raise ValueError("MUTATION_ANCHOR_DRIFT")
    changed = text.replace(patch.before, patch.after)
    if path.suffix == ".py":
        ast.parse(changed, filename=patch.path)
    diff = difflib.unified_diff(
        text.splitlines(keepends=True),
        changed.splitlines(keepends=True),
        fromfile=patch.path,
        tofile=patch.path + ".mutated",
    )
    with (folder / "mutation.patch").open("x", encoding="utf-8") as stream:
        stream.write("".join(diff))
    before = file_digest(path)
    path.write_text(changed, encoding="utf-8")
    write_json(
        folder / "patch_receipt.json",
        {"path": patch.path, "before_sha256": before, "after_sha256": file_digest(path)},
    )
    return original
