"""Mutation isolation guards protect the source tree even when a catalog entry is malformed."""

from pathlib import Path

import pytest

from tools.admission_evidence import source_snapshot
from tools.mutation_models import Mutation, Patch
from tools.mutation_storage import apply_mutation, freeze_source, mutation_path


def source_tree(root):
    path = Path(root) / "src/hmt_pg_patterns/guard.py"
    path.parent.mkdir(parents=True)
    path.write_text("def guard(value):\n    return value > 0\n")
    return path


def test_frozen_copy_has_independent_bytes_and_original_is_unchanged(tmp_path):
    source, copy = tmp_path / "source", tmp_path / "copy"
    original = source_tree(source)
    before = source_snapshot(source)
    copied = freeze_source(source, copy)
    assert copied["files"] == before["files"]
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    mutant = Mutation(
        "isolation",
        "PG-ADMIT-005",
        Patch("src/hmt_pg_patterns/guard.py", "value > 0", "value < 0"),
        "test",
    )
    saved = apply_mutation(copy, mutant, evidence)
    assert original.read_bytes() == saved
    assert (copy / mutant.patch.path).read_bytes() != saved
    (copy / mutant.patch.path).write_bytes(saved)
    assert source_snapshot(copy)["files"] == before["files"]
    assert source_snapshot(source)["files"] == before["files"]


@pytest.mark.parametrize(
    "name",
    [
        "",
        "/tmp/forbidden.py",
        "../guard.py",
        "src/../../guard.py",
        "tests/guard.py",
        "src/guard.txt",
    ],
)
def test_patch_target_cannot_escape_owned_copy(tmp_path, name):
    source_tree(tmp_path / "copy")
    with pytest.raises(ValueError, match="MUTATION_(PATH|SOURCE)"):
        mutation_path(tmp_path / "copy", Patch(name, "guard", "bad"))


def test_symlink_patch_target_cannot_touch_original(tmp_path):
    original = source_tree(tmp_path / "original")
    target = tmp_path / "copy/src/alias.py"
    target.parent.mkdir(parents=True)
    target.symlink_to(original)
    before = original.read_bytes()
    with pytest.raises(ValueError, match="MUTATION_PATH_OUTSIDE_COPY"):
        mutation_path(tmp_path / "copy", Patch("src/alias.py", "guard", "bad"))
    assert original.read_bytes() == before


def test_unviable_anchor_and_syntax_never_modify_source(tmp_path):
    path = source_tree(tmp_path / "copy")
    before = path.read_bytes()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    for old, new, error in (("absent", "False", ValueError), ("value > 0", "(", SyntaxError)):
        mutant = Mutation(
            "bad", "PG-ADMIT-005", Patch("src/hmt_pg_patterns/guard.py", old, new), "test"
        )
        with pytest.raises(error):
            apply_mutation(tmp_path / "copy", mutant, evidence)
        assert path.read_bytes() == before
