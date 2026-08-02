#!/usr/bin/env python3
"""Tests for the independent current-unsealed recovery evidence checker."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script import check_macos_current_unsealed_install_recovery_evidence as checker


class CurrentUnsealedRecoveryEvidencePortableTests(unittest.TestCase):
    """Clean-checkout-safe checker contract and snapshot regressions."""

    def snapshot_fixture(
        self, root: Path, payload: bytes = b"held-evidence"
    ) -> tuple[dict[Path, checker.FileSpec], dict[Path, checker.DirectorySpec]]:
        sealed = root / "sealed"
        sealed.mkdir(mode=0o700)
        value = sealed / "value.bin"
        value.write_bytes(payload)
        value.chmod(0o600)
        files = {
            Path("sealed/value.bin"): checker.FileSpec(
                len(payload), hashlib.sha256(payload).hexdigest(), 0o600, True
            )
        }
        directories = {
            Path("sealed"): checker.DirectorySpec(
                0o700, frozenset({"value.bin"})
            )
        }
        return files, directories

    def test_source_closure_is_exact_and_excludes_checker_files(self) -> None:
        self.assertEqual(
            set(checker.EXECUTION_SOURCE_CLOSURE),
            set(checker.EXECUTION_SOURCE_SPECS),
        )
        self.assertEqual(len(checker.EXECUTION_SOURCE_CLOSURE), 11)
        self.assertFalse(
            {
                "check_macos_current_unsealed_install_recovery_evidence.py",
                "test_check_macos_current_unsealed_install_recovery_evidence.py",
            }
            & {path.name for path in checker.EXECUTION_SOURCE_CLOSURE}
        )

    def test_strict_json_rejects_duplicate_noncanonical_and_nonfinite(self) -> None:
        invalid_payloads = (
            b'{"a":1,"a":2}\n',
            b'{ "a":1}\n',
            b'{"a":NaN}\n',
            b'[]\n',
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(checker.EvidenceError):
                checker.parse_canonical_json(payload, label="fixture")

    def test_file_and_directory_specs_reject_type_aliases(self) -> None:
        with self.assertRaises(ValueError):
            checker.FileSpec(True, "0" * 64, 0o600)
        with self.assertRaises(ValueError):
            checker.DirectorySpec(True, frozenset())
        with self.assertRaises(ValueError):
            checker.DirectorySpec(0o700, {"value.bin"})

    def test_snapshot_holds_and_reads_one_physical_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files, directories = self.snapshot_fixture(root)
            with checker.pinned_payloads(
                files, directories, root=root
            ) as payloads:
                self.assertEqual(payloads[Path("sealed/value.bin")], b"held-evidence")

    def test_snapshot_rejects_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files, directories = self.snapshot_fixture(root)
            alias = root / "sealed/alias.bin"
            os.link(root / "sealed/value.bin", alias)
            directories[Path("sealed")] = checker.DirectorySpec(
                0o700, frozenset({"value.bin", "alias.bin"})
            )
            with self.assertRaises(checker.EvidenceError):
                checker.RepositorySnapshot(root, files, directories)

    def test_snapshot_rejects_symlink_file_and_ancestor(self) -> None:
        for symlink_ancestor in (False, True):
            with self.subTest(symlink_ancestor=symlink_ancestor):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    files, directories = self.snapshot_fixture(root)
                    if symlink_ancestor:
                        (root / "sealed").rename(root / "physical")
                        (root / "sealed").symlink_to("physical", target_is_directory=True)
                    else:
                        value = root / "sealed/value.bin"
                        value.rename(root / "sealed/physical.bin")
                        value.symlink_to("physical.bin")
                    with self.assertRaises((checker.EvidenceError, OSError)):
                        checker.RepositorySnapshot(root, files, directories)

    def test_snapshot_rejects_closed_directory_inventory_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files, directories = self.snapshot_fixture(root)
            extra = root / "sealed/extra.bin"
            extra.write_bytes(b"extra")
            extra.chmod(0o600)
            with self.assertRaises(checker.EvidenceError):
                checker.RepositorySnapshot(root, files, directories)

    def test_snapshot_rejects_file_replacement_during_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = b"x" * (checker.READ_CHUNK_BYTES + 1)
            files, directories = self.snapshot_fixture(root, payload)
            snapshot = checker.RepositorySnapshot(root, files, directories)
            real_read = os.read
            replaced = False

            def replacing_read(descriptor: int, size: int) -> bytes:
                nonlocal replaced
                chunk = real_read(descriptor, size)
                if chunk and not replaced:
                    replacement = root / "sealed/replacement.bin"
                    replacement.write_bytes(payload)
                    replacement.chmod(0o600)
                    os.replace(replacement, root / "sealed/value.bin")
                    replaced = True
                return chunk

            try:
                with patch.object(checker.os, "read", side_effect=replacing_read):
                    with self.assertRaises(checker.EvidenceError):
                        snapshot.read_all()
            finally:
                snapshot.close()

    def test_snapshot_rejects_same_byte_aba_path_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files, directories = self.snapshot_fixture(root)
            value = root / "sealed/value.bin"
            original = root / "sealed/original.bin"
            replacement = root / "sealed/replacement.bin"
            snapshot = checker.RepositorySnapshot(root, files, directories)
            try:
                snapshot.read_all()
                value.rename(original)
                replacement.write_bytes(b"held-evidence")
                replacement.chmod(0o600)
                replacement.rename(value)
                value.unlink()
                original.rename(value)
                with self.assertRaises(checker.EvidenceError):
                    snapshot.verify_unchanged()
            finally:
                snapshot.close()

    def test_snapshot_rejects_ancestor_replacement_before_final_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files, directories = self.snapshot_fixture(root)
            snapshot = checker.RepositorySnapshot(root, files, directories)
            try:
                snapshot.read_all()
                (root / "sealed").rename(root / "old-sealed")
                (root / "sealed").mkdir(mode=0o700)
                replacement = root / "sealed/value.bin"
                replacement.write_bytes(b"held-evidence")
                replacement.chmod(0o600)
                with self.assertRaises(checker.EvidenceError):
                    snapshot.verify_unchanged()
            finally:
                snapshot.close()

    def test_cli_rejects_arguments(self) -> None:
        self.assertEqual(checker.main(["unexpected"]), 2)


class CurrentUnsealedRecoveryEvidenceCheckerTests(unittest.TestCase):
    """Historical exact-generation tests requiring the closed local bytes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.result_payload = (checker.ROOT / checker.RESULT_RELATIVE).read_bytes()
        cls.receipt_payload = (checker.ROOT / checker.RECEIPT_RELATIVE).read_bytes()
        cls.source_receipt_payload = (
            checker.ROOT / checker.OUTPUT_ROOT_RELATIVE / "source-receipt.json"
        ).read_bytes()
        cls.app_identity = {
            "fileCount": 9,
            "sha256": checker.EXPECTED_APP_TREE_SHA256,
            "size": 21_444_161,
        }
        cls.dsym_identity = {
            "fileCount": 3,
            "sha256": checker.EXPECTED_DSYM_TREE_SHA256,
            "size": 38_283_827,
        }

    def validate_mutated_result(self, result: dict[str, object]) -> None:
        with self.assertRaises(checker.EvidenceError):
            checker.validate_payloads(
                result_payload=checker.canonical_json_bytes(result),
                receipt_payload=self.receipt_payload,
                source_receipt_payload=self.source_receipt_payload,
                app_identity=self.app_identity,
                dsym_identity=self.dsym_identity,
            )

    def test_canonical_repository_evidence_passes(self) -> None:
        self.assertEqual(
            checker.check(),
            {
                "appSha256": checker.EXPECTED_APP_TREE_SHA256,
                "dSYMSha256": checker.EXPECTED_DSYM_TREE_SHA256,
                "resultSha256": checker.RESULT_SHA256,
                "sourceSha256": checker.EXPECTED_SOURCE_SHA256,
            },
        )

    def test_predecessor_evidence_closure_rejects_omission_and_replacement(
        self,
    ) -> None:
        expected_names = {
            "macos-current-source-unsealed-build-24-clean-home-install-"
            "state-recovery-v1-source-closure-one.json",
            "macos-current-source-unsealed-build-24-clean-home-install-"
            "state-recovery-repeatability-v1-source-closure-one.json",
            "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
            "process-state-recovery-v1-source-closure-two.json",
            "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
            "process-state-recovery-repeatability-v1-source-closure-two.json",
            "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
            "process-state-recovery-v1-source-closure-three.json",
            "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
            "process-state-recovery-repeatability-v1-source-closure-three.json",
            "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
            "process-state-recovery-v1-source-closure-four.json",
            "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
            "process-state-recovery-repeatability-v1-source-closure-four.json",
        }
        self.assertEqual(
            {path.name for path in checker.PREDECESSOR_EVIDENCE_PATHS},
            expected_names,
        )
        self.assertEqual(
            set(checker.PREDECESSOR_EVIDENCE_PATHS),
            set(checker.PREDECESSOR_EVIDENCE_SPECS),
        )
        self.assertTrue(
            set(checker.PREDECESSOR_EVIDENCE_PATHS)
            <= set(checker.all_file_specs())
        )
        self.assertTrue(
            all(
                spec.mode == 0o600 and not spec.capture
                for spec in checker.PREDECESSOR_EVIDENCE_SPECS.values()
            )
        )

        omitted = dict(checker.PREDECESSOR_EVIDENCE_SPECS)
        omitted.pop(checker.PREDECESSOR_EVIDENCE_PATHS[-1])
        with patch.object(checker, "PREDECESSOR_EVIDENCE_SPECS", omitted):
            with self.assertRaisesRegex(checker.EvidenceError, "predecessor"):
                checker.all_file_specs()

        selected = checker.PREDECESSOR_EVIDENCE_PATHS[0]
        replaced = dict(checker.PREDECESSOR_EVIDENCE_SPECS)
        original = replaced[selected]
        replaced[selected] = checker.FileSpec(
            original.size, "0" * 64, original.mode, original.capture
        )
        with patch.object(checker, "PREDECESSOR_EVIDENCE_SPECS", replaced):
            with self.assertRaises(checker.EvidenceError):
                checker.check()

    def test_real_documents_are_canonical_and_cross_bound(self) -> None:
        checker.validate_payloads(
            result_payload=self.result_payload,
            receipt_payload=self.receipt_payload,
            source_receipt_payload=self.source_receipt_payload,
            app_identity=self.app_identity,
            dsym_identity=self.dsym_identity,
        )

    def test_result_rejects_boolean_integer_alias(self) -> None:
        result = checker.parse_canonical_json(
            self.result_payload, label="lifecycle result"
        )
        result["schemaVersion"] = True
        self.validate_mutated_result(result)

    def test_result_rejects_integer_boolean_alias(self) -> None:
        result = checker.parse_canonical_json(
            self.result_payload, label="lifecycle result"
        )
        result["qualification"]["canonicalG6ExitClaimed"] = 0
        self.validate_mutated_result(result)

    def test_result_rejects_unknown_key_and_false_claim_mutation(self) -> None:
        result = checker.parse_canonical_json(
            self.result_payload, label="lifecycle result"
        )
        result["unexpected"] = None
        self.validate_mutated_result(result)

        result = checker.parse_canonical_json(
            self.result_payload, label="lifecycle result"
        )
        result["qualification"]["canonicalG6ExitClaimed"] = True
        self.validate_mutated_result(result)

    def test_result_rejects_abrupt_process_claim_mutations(self) -> None:
        mutations = (
            (("abruptTermination", "exitCode"), 0),
            (("abruptTermination", "signalNumber"), True),
            (("abruptTermination", "processReaped"), False),
            (
                (
                    "abruptTermination",
                    "installedExecutableDescriptorHeldAcrossSignal",
                ),
                False,
            ),
            (
                (
                    "abruptTermination",
                    "runningExecutableCodeIdentityMatchedHeldBytes",
                ),
                False,
            ),
            (
                (
                    "abruptTermination",
                    "capturedLogsRevalidatedAfterReap",
                ),
                False,
            ),
            (("lifecycle", "runs", 1, "exitCode"), 0),
            (
                (
                    "stateRecovery",
                    "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination",
                ),
                False,
            ),
        )
        for path, value in mutations:
            result = checker.parse_canonical_json(
                self.result_payload, label="lifecycle result"
            )
            target: object = result
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = value
            with self.subTest(path=path):
                self.validate_mutated_result(result)

    def test_result_rejects_app_dsym_and_source_receipt_rebinding(self) -> None:
        for path in (
            ("generation", "app", "sha256"),
            ("generation", "dSYM", "sha256"),
            ("generation", "sourceReceipt", "sha256"),
        ):
            result = checker.parse_canonical_json(
                self.result_payload, label="lifecycle result"
            )
            target = result
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = "0" * 64
            with self.subTest(path=path):
                self.validate_mutated_result(result)

    def test_receipt_rejects_alias_and_result_rebinding(self) -> None:
        for path, value in (
            (("runCount",), True),
            (("resultBytesEqual",), 1),
            (("canonicalResult", "sha256"), "0" * 64),
        ):
            receipt = checker.parse_canonical_json(
                self.receipt_payload, label="repeatability receipt"
            )
            target = receipt
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(checker.EvidenceError):
                checker.validate_payloads(
                    result_payload=self.result_payload,
                    receipt_payload=checker.canonical_json_bytes(receipt),
                    source_receipt_payload=self.source_receipt_payload,
                    app_identity=self.app_identity,
                    dsym_identity=self.dsym_identity,
                )

    def test_source_receipt_rejects_source_identity_mutation(self) -> None:
        source_receipt = checker.parse_canonical_json(
            self.source_receipt_payload, label="source receipt"
        )
        source_receipt["source"]["fileCount"] = True
        with self.assertRaises(checker.EvidenceError):
            checker.validate_payloads(
                result_payload=self.result_payload,
                receipt_payload=self.receipt_payload,
                source_receipt_payload=checker.canonical_json_bytes(source_receipt),
                app_identity=self.app_identity,
                dsym_identity=self.dsym_identity,
            )

if __name__ == "__main__":
    unittest.main()
