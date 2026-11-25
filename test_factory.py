import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from factory import AdmissionError, Registry, canonical, export, verify


ROOT = Path(__file__).resolve().parent
SELECTIONS = ROOT / "selections"


class FactoryTests(unittest.TestCase):
    def test_audit_and_known_branch_coverage(self):
        registry = Registry()
        result = registry.audit()
        self.assertEqual(result["preserved_files"], 1969)
        self.assertEqual(result["registry_entries"], 33)
        self.assertEqual(set(result["factory_bindings"]), set(registry.entries))
        self.assertEqual({item["branch"] for item in registry.entries.values()},
                         {"behavioral", "creational", "structural", "database", "resilience"})

    def test_unqualified_composition_cannot_publish(self):
        with TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "denied.zip"
            hold = export(Registry(), SELECTIONS / "unqualified-composition.toml", artifact)
            self.assertEqual(hold["status"], "HOLD")
            self.assertEqual({hold["reason"] for hold in hold["holds"]},
                             {"COMPOSITION_WITNESS_REQUIRED"})
            self.assertFalse(artifact.exists())

    def test_registry_receipt_binds_selection_and_same_runtime(self):
        registry = Registry()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            builds = []
            for choice in ("ooda-starter", "ooda-all"):
                output = root / (choice + ".zip")
                receipt_path = root / (choice + ".receipt.json")
                receipt = export(registry, SELECTIONS / (choice + ".toml"), output)
                self.assertEqual(receipt["status"], "QUALIFIED")
                receipt_path.write_bytes(canonical(receipt))
                self.assertEqual(verify(registry, output, receipt_path)["status"], "PASS")
                with ZipFile(output) as archive:
                    builds.append(json.loads(archive.read("manifest.json")))
            self.assertEqual(builds[0]["files"]["retry_runtime.py"], builds[1]["files"]["retry_runtime.py"])
            self.assertNotEqual(builds[0]["selection_sha256"], builds[1]["selection_sha256"])
            self.assertEqual(len(builds[0]["qualification"]["profiles"]), 2)
            self.assertEqual(len(builds[1]["qualification"]["profiles"]), 9)

    def test_configuration_cannot_escape_the_registry(self):
        original = (SELECTIONS / "ooda-starter.toml").read_bytes()
        with TemporaryDirectory() as temporary:
            selection = Path(temporary) / "outside.toml"
            selection.write_bytes(original.replace(
                b"patterns/resilience_ooda/selections/ooda-starter.toml", b"../ooda-starter.toml"))
            with self.assertRaises(AdmissionError):
                Registry().resolve(selection)

    def test_binding_identity_and_setting_set_fail_before_export(self):
        selection = (SELECTIONS / "behavioral-strategy.toml").read_text(encoding="utf-8")
        baseline = (ROOT / "bindings" / "RDP-B01.toml").read_text(encoding="utf-8")
        with TemporaryDirectory(dir=ROOT) as temporary:
            directory = Path(temporary)
            policy = directory / "binding.toml"
            request = directory / "selection.toml"
            output = directory / "denied.zip"
            request.write_text(selection.replace("bindings/RDP-B01.toml", policy.relative_to(ROOT).as_posix()),
                               encoding="utf-8")
            for candidate, reason in (
                (baseline.replace('pattern = "RDP-B01"', 'pattern = "RDP-B02"'), "VALUE_NOT_ADMITTED"),
                (baseline + "\nunregistered = true\n", "UNDECLARED_OR_MISSING_SETTING"),
                (baseline.replace('algorithm = "scan"\n', ""), "UNDECLARED_OR_MISSING_SETTING"),
            ):
                with self.subTest(reason=reason):
                    policy.write_text(candidate, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, reason):
                        export(Registry(), request, output)
                    self.assertFalse(output.exists())

    def test_database_policy_changes_driver_and_retry_effect(self):
        selection = (SELECTIONS / "postgres-transaction.toml").read_text(encoding="utf-8")
        baseline = (ROOT / "bindings" / "PG-PAT-005.toml").read_text(encoding="utf-8")
        registry = Registry()
        with TemporaryDirectory(dir=ROOT) as temporary:
            directory = Path(temporary)
            policy = directory / "binding.toml"
            request = directory / "selection.toml"
            output = directory / "transaction.zip"
            request.write_text(selection.replace("bindings/PG-PAT-005.toml", policy.relative_to(ROOT).as_posix()),
                               encoding="utf-8")
            policy.write_text(baseline.replace("attempts = 3", 'attempts = "2"'), encoding="utf-8")
            with self.assertRaisesRegex(AdmissionError, "INTEGER_NOT_ADMITTED"):
                export(registry, request, output)
            self.assertFalse(output.exists())
            policy.write_text(baseline.replace("attempts = 3", "attempts = 2").replace("psycopg-sync", "psycopg-async"),
                              encoding="utf-8")
            receipt = export(registry, request, output)
            receipt_path = directory / "receipt.json"
            receipt_path.write_bytes(canonical(receipt))
            self.assertEqual(verify(registry, output, receipt_path)["status"], "PASS")
            with ZipFile(output) as bundle:
                report = json.loads(bundle.read("manifest.json"))["qualification"]
            self.assertEqual(report["observed"], {"attempts": 2, "driver": "psycopg-async"})
            self.assertEqual(report["undeclared_setting"], "DENY")


if __name__ == "__main__":
    unittest.main()
