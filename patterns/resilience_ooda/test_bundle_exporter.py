from dataclasses import asdict
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from bundle_exporter import export_bundle, member_name, verify_bundle
from retry_runtime import PolicyError, load_policy


ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "catalog.toml"
STARTER = ROOT / "selections" / "ooda-starter.toml"
FULL = ROOT / "selections" / "all-configurations.toml"


class ExportTests(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.directory = Path(scratch.name)

    def test_flat_reproducible_export_and_clean_replay(self):
        first, second = (self.directory / f"{name}.zip" for name in ("first", "second"))
        receipt = export_bundle(STARTER, CATALOG, first)
        repeated = export_bundle(STARTER, CATALOG, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(receipt, repeated)
        self.assertEqual(receipt, verify_bundle(first, expected_sha256=receipt.archive_sha256))
        unpacked = self.directory / "unpacked"
        with ZipFile(first) as archive:
            self.assertIn("selection.toml", archive.namelist())
            self.assertIn("reference/core_example_configs/tenacity_stopping_conditions.py", archive.namelist())
            self.assertNotIn("reference/core_example_configs/tenacity_logging_hooks.py", archive.namelist())
            archive.extractall(unpacked)
        result = subprocess.run([sys.executable, "-B", "witness.py"], cwd=unpacked, capture_output=True, check=True)
        self.assertIn(b'"status": "PASS"', result.stdout)

    def test_full_selection_exercises_all_configurations(self):
        receipt = export_bundle(FULL, CATALOG, self.directory / "full.zip")
        self.assertEqual(set(receipt.qualified_profiles), set(load_policy(FULL).profiles))
        self.assertEqual(len(asdict(receipt)["qualified_profiles"]), 9)

    def test_policy_denial_creates_no_zip(self):
        baseline = STARTER.read_bytes()
        invalid = (
            baseline.replace(b'kind = "ooda"', b'kind = "missing"'),
            baseline.replace(b"window_ns = 10_000_000_000", b"window_ns = 750_000_000"),
            baseline.replace(b"attempts = 3", b"attempts = true", 1),
            baseline.replace(b"backoff_ms = 0", b"backoff_ms = 0\narbitrary_hook = true"),
        )
        selection = self.directory / "invalid.toml"
        destination = self.directory / "denied.zip"
        for value in invalid:
            with self.subTest(value=value):
                selection.write_bytes(value)
                with self.assertRaises(PolicyError):
                    export_bundle(selection, CATALOG, destination)
                self.assertFalse(destination.exists())

    def test_archive_pin_and_member_mutation_are_detected(self):
        archive = self.directory / "good.zip"
        altered = self.directory / "altered.zip"
        receipt = export_bundle(STARTER, CATALOG, archive)
        with ZipFile(archive) as source, ZipFile(altered, "x") as changed:
            for info in source.infolist():
                data = source.read(info)
                if info.filename == "README.md":
                    data += b"changed"
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                changed.writestr(info, data)
        with self.assertRaisesRegex(PolicyError, "export digest mismatch"):
            verify_bundle(altered, expected_sha256=receipt.archive_sha256)
        with self.assertRaisesRegex(PolicyError, "bundle file digest mismatch"):
            verify_bundle(altered)

    def test_unsafe_paths_are_rejected(self):
        for name in ("../outside.py", "/absolute.txt", "C:/x", r"folder\file", "AUX.txt", "dir//member"):
            with self.subTest(name=name), self.assertRaises(PolicyError):
                member_name(name)


if __name__ == "__main__":
    unittest.main()
