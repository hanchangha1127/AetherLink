#!/usr/bin/env python3
"""Portable tests for the current-unsealed main-branch lifecycle checker."""

from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script import check_macos_current_unsealed_ci_lifecycle as checker
from script import check_macos_current_unsealed_install_recovery_evidence as closed


class CurrentUnsealedCILifecyclePortableTests(unittest.TestCase):
    @staticmethod
    def report() -> dict[str, object]:
        source = {
            "algorithm": closed.SOURCE_ALGORITHM,
            "fileCount": 271,
            "sha256": "1" * 64,
        }
        report: dict[str, object] = {
            "app": {
                "fileCount": 9,
                "sha256": "2" * 64,
                "size": 21_000_000,
            },
            "architecture": "arm64",
            "buildNumber": 24,
            "bundleId": "dev.aetherlink.companion",
            "dSYM": {
                "fileCount": 3,
                "sha256": "3" * 64,
                "size": 38_000_000,
            },
            "locales": ["en", "fr", "ja", "ko", "zh-hans"],
            "marketingVersion": "1.0.0",
            "minimumSystemVersion": "14.0",
            "outerBundleSeal": "absent",
            "source": source,
            "sourceReceipt": {},
            "uuid": "11111111-2222-3333-4444-555555555555",
        }
        source_receipt_payload = closed.canonical_json_bytes(
            checker.expected_source_receipt(report)
        )
        report["sourceReceipt"] = {
            "sha256": hashlib.sha256(source_receipt_payload).hexdigest(),
            "size": len(source_receipt_payload),
        }
        return report

    @classmethod
    def payloads(
        cls,
    ) -> tuple[bytes, bytes, bytes, dict[str, object]]:
        return cls.payloads_for_report(cls.report())

    @staticmethod
    def payloads_for_report(
        report: dict[str, object],
    ) -> tuple[bytes, bytes, bytes, dict[str, object]]:
        report = copy.deepcopy(report)
        app = report["app"]
        dsym = report["dSYM"]
        source_receipt = closed.canonical_json_bytes(
            checker.expected_source_receipt(report)
        )
        source_receipt_identity = {
            "sha256": hashlib.sha256(source_receipt).hexdigest(),
            "size": len(source_receipt),
        }
        report["sourceReceipt"] = source_receipt_identity
        assert isinstance(app, dict)
        assert isinstance(dsym, dict)
        result = closed.canonical_json_bytes(
            checker.expected_current_result(
                report=report,
                app_identity=app,
                dsym_identity=dsym,
                source_receipt_identity=source_receipt_identity,
            )
        )
        result_identity = {
            "sha256": hashlib.sha256(result).hexdigest(),
            "size": len(result),
        }
        receipt = closed.canonical_json_bytes(
            checker.expected_current_receipt(result_identity)
        )
        return result, receipt, source_receipt, report

    def validate(
        self,
        result: bytes,
        receipt: bytes,
        source_receipt: bytes,
        report: dict[str, object],
        *,
        held_source: dict[str, object] | None = None,
    ) -> dict[str, object]:
        app = report["app"]
        dsym = report["dSYM"]
        source = report["source"] if held_source is None else held_source
        assert isinstance(app, dict)
        assert isinstance(dsym, dict)
        assert isinstance(source, dict)
        return checker.validate_current_run_payloads(
            result_payload=result,
            receipt_payload=receipt,
            source_receipt_payload=source_receipt,
            app_identity=app,
            dsym_identity=dsym,
            held_source=source,
            report=report,
        )

    def test_dynamic_generation_payloads_are_cross_bound(self) -> None:
        result, receipt, source_receipt, report = self.payloads()
        identity = self.validate(result, receipt, source_receipt, report)
        self.assertEqual(identity["size"], len(result))
        self.assertEqual(identity["sha256"], hashlib.sha256(result).hexdigest())

    def test_result_source_mutation_is_rejected(self) -> None:
        result, receipt, source_receipt, report = self.payloads()
        document = closed.parse_canonical_json(result, label="fixture result")
        generation = document["generation"]
        assert isinstance(generation, dict)
        source = generation["source"]
        assert isinstance(source, dict)
        source["sha256"] = "9" * 64
        with self.assertRaises(closed.EvidenceError):
            self.validate(
                closed.canonical_json_bytes(document),
                receipt,
                source_receipt,
                report,
            )

    def test_source_receipt_and_report_drift_is_rejected(self) -> None:
        _result, _receipt, _source_receipt, report = self.payloads()
        held_source = copy.deepcopy(report["source"])
        assert isinstance(held_source, dict)
        mutated = copy.deepcopy(report)
        source = mutated["source"]
        assert isinstance(source, dict)
        source["fileCount"] = 272
        result, receipt, source_receipt, mutated = self.payloads_for_report(mutated)
        with self.assertRaises(closed.EvidenceError):
            self.validate(
                result,
                receipt,
                source_receipt,
                mutated,
                held_source=held_source,
            )

    def test_receipt_filename_and_exact_boolean_mutations_are_rejected(self) -> None:
        result, receipt, source_receipt, report = self.payloads()
        for key, value in (
            ("fileName", "other.json"),
            ("resultBytesEqual", 1),
        ):
            document = closed.parse_canonical_json(
                receipt,
                label="fixture receipt",
            )
            if key == "fileName":
                canonical = document["canonicalResult"]
                assert isinstance(canonical, dict)
                canonical[key] = value
            else:
                document[key] = value
            with self.subTest(key=key):
                with self.assertRaises(closed.EvidenceError):
                    self.validate(
                        result,
                        closed.canonical_json_bytes(document),
                        source_receipt,
                        report,
                    )

    def test_dynamic_snapshot_binds_held_bytes_and_rejects_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "evidence.json"
            path.write_bytes(b"evidence\n")
            path.chmod(0o600)
            policies = {
                Path("evidence.json"): checker.FilePolicy(
                    expected_mode=0o600,
                    maximum_bytes=32,
                    capture=True,
                )
            }
            with checker.CurrentRunSnapshot(
                root,
                policies,
                {},
            ) as snapshot:
                payloads = snapshot.read_all()
                spec = snapshot.file_specs[Path("evidence.json")]
                self.assertEqual(payloads[Path("evidence.json")], b"evidence\n")
                self.assertEqual(spec.size, 9)
                self.assertEqual(spec.mode, 0o600)
                self.assertTrue(spec.capture)
                expected_digest = hashlib.sha256(
                    b"evidence.json\0"
                    b"644\0"
                    b"9\0"
                    + hashlib.sha256(b"evidence\n").hexdigest().encode("ascii")
                    + b"\n"
                ).hexdigest()
                self.assertEqual(
                    checker.held_source_snapshot_summary(
                        (Path("evidence.json"),),
                        snapshot.file_specs,
                    ),
                    {
                        "algorithm": closed.SOURCE_ALGORITHM,
                        "fileCount": 1,
                        "sha256": expected_digest,
                    },
                )
                snapshot.verify_unchanged()

                replacement = root / "replacement"
                replacement.write_bytes(b"evidence\n")
                replacement.chmod(0o600)
                os.replace(replacement, path)
                with self.assertRaises(closed.EvidenceError):
                    snapshot.verify_unchanged()

            real_read = os.read
            replacement_during_acquisition = root / "replacement-during-acquisition"
            replacement_triggered = False

            def replace_during_first_read(
                descriptor: int,
                maximum: int,
            ) -> bytes:
                nonlocal replacement_triggered
                if not replacement_triggered:
                    replacement_triggered = True
                    replacement_during_acquisition.write_bytes(b"evidence\n")
                    replacement_during_acquisition.chmod(0o600)
                    os.replace(replacement_during_acquisition, path)
                return real_read(descriptor, maximum)

            with patch.object(
                checker.os,
                "read",
                side_effect=replace_during_first_read,
            ):
                with self.assertRaises(closed.EvidenceError):
                    checker.CurrentRunSnapshot(root, policies, {})
            self.assertTrue(replacement_triggered)

    def test_dynamic_snapshot_rejects_link_mode_and_size_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original"
            original.write_bytes(b"payload")
            original.chmod(0o600)
            symlink = root / "symlink"
            symlink.symlink_to(original)
            hardlink = root / "hardlink"
            os.link(original, hardlink)
            wrong_mode = root / "wrong-mode"
            wrong_mode.write_bytes(b"payload")
            wrong_mode.chmod(0o644)
            rows = (
                (Path("symlink"), 0o600, 32),
                (Path("original"), 0o600, 32),
                (Path("wrong-mode"), 0o600, 32),
                (Path("wrong-mode"), 0o644, 3),
            )
            for relative, mode, maximum in rows:
                with self.subTest(relative=relative, maximum=maximum):
                    with self.assertRaises((closed.EvidenceError, OSError)):
                        checker.CurrentRunSnapshot(
                            root,
                            {
                                relative: checker.FilePolicy(
                                    expected_mode=mode,
                                    maximum_bytes=maximum,
                                )
                            },
                            {},
                        )

        for invalid_paths in (
            (),
            (Path("b"), Path("a")),
            (Path("a"), Path("a")),
        ):
            with self.subTest(source_paths=invalid_paths):
                with self.assertRaises(closed.EvidenceError):
                    checker.current_run_file_policies(
                        source_paths=invalid_paths,
                    )

    def test_result_directory_contract_is_private_and_closed(self) -> None:
        files = {
            checker.RESULT_RELATIVE: closed.FileSpec(1, "1" * 64, 0o600),
            checker.RECEIPT_RELATIVE: closed.FileSpec(1, "2" * 64, 0o600),
        }
        spec = checker.current_run_directory_specs(files)[
            checker.RESULT_DIRECTORY_RELATIVE
        ]
        self.assertEqual(spec.mode, 0o700)
        self.assertEqual(
            spec.entries,
            frozenset({"result.json", "repeatability.json"}),
        )

    def test_cli_rejects_arguments(self) -> None:
        self.assertEqual(checker.main(["unexpected"]), 2)


if __name__ == "__main__":
    unittest.main()
