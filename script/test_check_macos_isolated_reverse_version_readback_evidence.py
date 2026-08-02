#!/usr/bin/env python3
"""Tests for the independent reverse-version evidence checker."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script import check_macos_isolated_reverse_version_readback_evidence as checker


class ReverseVersionEvidenceCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result_payload = (checker.ROOT / checker.RESULT_RELATIVE).read_bytes()
        cls.receipt_payload = (checker.ROOT / checker.RECEIPT_RELATIVE).read_bytes()
        cls.predecessor_result_payload = (
            checker.ROOT / checker.PREDECESSOR_RESULT_RELATIVE
        ).read_bytes()
        cls.predecessor_receipt_payload = (
            checker.ROOT / checker.PREDECESSOR_RECEIPT_RELATIVE
        ).read_bytes()
        cls.earlier_predecessor_result_payload = (
            checker.ROOT / checker.EARLIER_PREDECESSOR_RESULT_RELATIVE
        ).read_bytes()
        cls.earlier_predecessor_receipt_payload = (
            checker.ROOT / checker.EARLIER_PREDECESSOR_RECEIPT_RELATIVE
        ).read_bytes()
        cls.earliest_predecessor_result_payload = (
            checker.ROOT / checker.EARLIEST_PREDECESSOR_RESULT_RELATIVE
        ).read_bytes()
        cls.earliest_predecessor_receipt_payload = (
            checker.ROOT / checker.EARLIEST_PREDECESSOR_RECEIPT_RELATIVE
        ).read_bytes()
        cls.original_result_payload = (
            checker.ROOT / checker.ORIGINAL_RESULT_RELATIVE
        ).read_bytes()
        cls.original_receipt_payload = (
            checker.ROOT / checker.ORIGINAL_RECEIPT_RELATIVE
        ).read_bytes()

    def mutated_result(self, mutate: object) -> bytes:
        value = json.loads(self.result_payload)
        mutate(value)
        return checker.canonical_json_bytes(value)

    def mutated_result_value(self, mutate: object) -> dict[str, object]:
        value = json.loads(self.result_payload)
        mutate(value)
        return value

    def mutated_receipt(self, mutate: object) -> bytes:
        value = json.loads(self.receipt_payload)
        mutate(value)
        return checker.canonical_json_bytes(value)

    def mutated_receipt_value(self, mutate: object) -> dict[str, object]:
        value = json.loads(self.receipt_payload)
        mutate(value)
        return value

    def test_current_evidence_passes_full_pinned_readback(self) -> None:
        checker.check()

    def test_supplied_current_payloads_pass(self) -> None:
        checker.validate_evidence_payloads(
            self.result_payload,
            self.receipt_payload,
        )

    def test_five_generation_successor_chain_preserves_evidence_bytes(self) -> None:
        checker.validate_predecessor_preservation(
            self.result_payload,
            self.receipt_payload,
            self.predecessor_result_payload,
            self.predecessor_receipt_payload,
            successor_result_file_name=checker.RESULT_RELATIVE.name,
            predecessor_result_file_name=checker.PREDECESSOR_RESULT_RELATIVE.name,
        )
        checker.validate_predecessor_preservation(
            self.predecessor_result_payload,
            self.predecessor_receipt_payload,
            self.earlier_predecessor_result_payload,
            self.earlier_predecessor_receipt_payload,
            successor_result_file_name=checker.PREDECESSOR_RESULT_RELATIVE.name,
            predecessor_result_file_name=checker.EARLIER_PREDECESSOR_RESULT_RELATIVE.name,
        )
        checker.validate_predecessor_preservation(
            self.earlier_predecessor_result_payload,
            self.earlier_predecessor_receipt_payload,
            self.earliest_predecessor_result_payload,
            self.earliest_predecessor_receipt_payload,
            successor_result_file_name=checker.EARLIER_PREDECESSOR_RESULT_RELATIVE.name,
            predecessor_result_file_name=checker.EARLIEST_PREDECESSOR_RESULT_RELATIVE.name,
        )
        checker.validate_predecessor_preservation(
            self.earliest_predecessor_result_payload,
            self.earliest_predecessor_receipt_payload,
            self.original_result_payload,
            self.original_receipt_payload,
            successor_result_file_name=checker.EARLIEST_PREDECESSOR_RESULT_RELATIVE.name,
            predecessor_result_file_name=checker.ORIGINAL_RESULT_RELATIVE.name,
        )
        self.assertEqual(
            self.result_payload,
            self.predecessor_result_payload,
        )
        self.assertEqual(
            self.predecessor_result_payload,
            self.earlier_predecessor_result_payload,
        )
        self.assertEqual(
            self.earlier_predecessor_result_payload,
            self.earliest_predecessor_result_payload,
        )
        self.assertEqual(
            self.earliest_predecessor_result_payload,
            self.original_result_payload,
        )
        for successor_payload, predecessor_payload in (
            (self.receipt_payload, self.predecessor_receipt_payload),
            (
                self.predecessor_receipt_payload,
                self.earlier_predecessor_receipt_payload,
            ),
            (
                self.earlier_predecessor_receipt_payload,
                self.earliest_predecessor_receipt_payload,
            ),
            (
                self.earliest_predecessor_receipt_payload,
                self.original_receipt_payload,
            ),
        ):
            successor_receipt = json.loads(successor_payload)
            predecessor_receipt = json.loads(predecessor_payload)
            self.assertNotEqual(successor_payload, predecessor_payload)
            successor_receipt["canonicalResult"]["fileName"] = (
                predecessor_receipt["canonicalResult"]["fileName"]
            )
            self.assertEqual(successor_receipt, predecessor_receipt)

    def test_five_evidence_generations_are_all_pinned(self) -> None:
        evidence_paths = {
            checker.RESULT_RELATIVE,
            checker.RECEIPT_RELATIVE,
            checker.PREDECESSOR_RESULT_RELATIVE,
            checker.PREDECESSOR_RECEIPT_RELATIVE,
            checker.EARLIER_PREDECESSOR_RESULT_RELATIVE,
            checker.EARLIER_PREDECESSOR_RECEIPT_RELATIVE,
            checker.EARLIEST_PREDECESSOR_RESULT_RELATIVE,
            checker.EARLIEST_PREDECESSOR_RECEIPT_RELATIVE,
            checker.ORIGINAL_RESULT_RELATIVE,
            checker.ORIGINAL_RECEIPT_RELATIVE,
        }
        self.assertTrue(evidence_paths.issubset(checker.PINNED_FILES))
        for path in evidence_paths:
            with self.subTest(path=path):
                spec = checker.PINNED_FILES[path]
                self.assertEqual(spec.mode, 0o600)
                self.assertTrue(spec.capture)

    def test_five_generation_preservation_rejects_mutated_middle_result(self) -> None:
        mutated = bytearray(self.earlier_predecessor_result_payload)
        mutated[-2] ^= 1
        with self.assertRaises(checker.EvidenceError):
            checker.validate_predecessor_preservation(
                self.predecessor_result_payload,
                self.predecessor_receipt_payload,
                bytes(mutated),
                self.earlier_predecessor_receipt_payload,
                successor_result_file_name=checker.PREDECESSOR_RESULT_RELATIVE.name,
                predecessor_result_file_name=checker.EARLIER_PREDECESSOR_RESULT_RELATIVE.name,
            )

    def test_noncanonical_and_duplicate_json_are_rejected(self) -> None:
        with self.assertRaisesRegex(checker.EvidenceError, "canonical"):
            checker.validate_evidence_payloads(
                self.result_payload + b" ",
                self.receipt_payload,
            )
        duplicate = self.result_payload.replace(
            b'"schemaVersion":1,',
            b'"schemaVersion":1,"schemaVersion":1,',
            1,
        )
        self.assertNotEqual(duplicate, self.result_payload)
        with self.assertRaisesRegex(checker.EvidenceError, "duplicate JSON key"):
            checker.validate_evidence_payloads(duplicate, self.receipt_payload)

    def test_result_exact_type_and_false_claim_mutations_are_rejected(self) -> None:
        mutations = {
            "schema_bool": lambda value: value.__setitem__("schemaVersion", True),
            "rollback_claim": lambda value: value["qualification"].__setitem__(
                "productRollbackQualificationClaimed", True
            ),
            "security_claim": lambda value: value["qualification"].__setitem__(
                "securityEvidenceProduced", True
            ),
            "launch_ordinal_bool": lambda value: value["launchServices"]["runs"][0].__setitem__(
                "ordinal", True
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), self.assertRaises(checker.EvidenceError):
                checker.validate_result(self.mutated_result_value(mutate))

    def test_result_sequence_archive_and_state_mutations_are_rejected(self) -> None:
        mutations = {
            "sequence": lambda value: value["releaseSequence"].reverse(),
            "archive": lambda value: value["archiveReadback"]["current"][
                "snapshotFiles"
            ]["aetherlink-1.0.0+24-local-v1.zip"].__setitem__("size", 1),
            "state": lambda value: value["stateReadback"].__setitem__(
                "bytesAndModesUnchangedAcrossManualReplacement", False
            ),
            "tree": lambda value: value["installation"]["restoredCurrentTree"].__setitem__(
                "sha256", "0" * 64
            ),
            "canary": lambda value: value["canary"].__setitem__(
                "eventJsonSize", 1
            ),
            "cleanup": lambda value: value["cleanup"].__setitem__(
                "removalCount", 2
            ),
            "isolation": lambda value: value["isolation"].__setitem__(
                "preexistingBundleApplicationsPreserved", False
            ),
            "release": lambda value: value["releases"]["historical"]["app"].__setitem__(
                "buildNumber", 24
            ),
            "limitation": lambda value: value["limitations"].pop(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), self.assertRaises(checker.EvidenceError):
                checker.validate_result(self.mutated_result_value(mutate))

    def test_receipt_type_identity_and_scope_mutations_are_rejected(self) -> None:
        mutations = {
            "run_count_bool": lambda value: value.__setitem__("runCount", True),
            "identity": lambda value: value["canonicalResult"].__setitem__(
                "sha256", "0" * 64
            ),
            "run_identity": lambda value: value["runs"][1].__setitem__(
                "size", checker.RESULT_SIZE + 1
            ),
            "scope": lambda value: value.__setitem__("scope", "product-rollback"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), self.assertRaises(checker.EvidenceError):
                checker.validate_receipt(self.mutated_receipt_value(mutate))

    def test_result_receipt_supplied_byte_crossbinding_is_independent(self) -> None:
        mutated = self.mutated_result(
            lambda value: value["qualification"].__setitem__(
                "productRollbackQualificationClaimed", True
            )
        )
        with (
            patch.object(checker, "validate_result", return_value=None),
            self.assertRaisesRegex(
                checker.EvidenceError,
                "receipt does not bind the supplied result bytes",
            ),
        ):
            checker.validate_evidence_payloads(mutated, self.receipt_payload)

    def test_execution_source_closure_membership_is_exactly_pinned(self) -> None:
        expected = {
            Path("script/run_macos_isolated_reverse_version_readback_smoke.py"),
            Path("script/run_macos_isolated_upgrade_smoke.py"),
            Path("script/run_macos_clean_home_installed_app_smoke.py"),
            Path("script/run_macos_clean_home_installed_state_recovery_smoke.py"),
            Path("script/run_macos_isolated_uninstall_reinstall_smoke.py"),
            Path("script/run_macos_packaged_app_state_recovery_smoke.py"),
            Path("script/run_macos_packaged_app_lifecycle_smoke.py"),
            Path("script/check_release_version_ledger.py"),
            Path("script/check_release_artifact_archive.py"),
            Path("script/check_release_compliance.py"),
        }
        self.assertEqual(set(checker.EXECUTION_SOURCE_CLOSURE), expected)
        self.assertTrue(expected.issubset(checker.PINNED_FILES))

    def test_current_release_archive_checker_identity_is_pinned(self) -> None:
        relative = Path("script/check_release_artifact_archive.py")
        source = (checker.ROOT / relative).read_bytes()
        spec = checker.PINNED_FILES[relative]
        self.assertEqual(len(source), spec.size)
        self.assertEqual(hashlib.sha256(source).hexdigest(), spec.sha256)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            copy = root / relative
            copy.parent.mkdir(parents=True)
            copy.write_bytes(source[:-1] + bytes([source[-1] ^ 1]))
            copy.chmod(spec.mode)
            with self.assertRaisesRegex(checker.EvidenceError, "bytes changed"):
                with checker.pinned_file_payloads({relative: spec}, root=root):
                    pass

    def test_ledger_and_checksum_sidecar_are_exact(self) -> None:
        ledger = (checker.ROOT / "release/version-ledger.tsv").read_bytes()
        checker.validate_ledger(ledger)
        with self.assertRaises(checker.EvidenceError):
            checker.validate_ledger(ledger.replace(b"24\t1.0.0", b"25\t1.0.0"))

        release_id = "aetherlink-1.0.0+24-local-v1"
        archive_sha = checker.ARCHIVE_SNAPSHOT_EXPECTED["current"][
            f"{release_id}.zip"
        ]["sha256"]
        sidecar = (
            checker.ROOT
            / f"dist/releases/{release_id}/{release_id}.zip.sha256"
        ).read_bytes()
        checker.validate_checksum_sidecar(
            sidecar,
            release_id=release_id,
            archive_sha256=archive_sha,
        )
        with self.assertRaises(checker.EvidenceError):
            checker.validate_checksum_sidecar(
                sidecar.replace(archive_sha.encode(), b"0" * 64),
                release_id=release_id,
                archive_sha256=archive_sha,
            )

    def test_exact_comparison_rejects_bool_integer_alias(self) -> None:
        self.assertFalse(checker.exact_equal(True, 1))
        self.assertFalse(
            checker.exact_equal({"count": 1}, {"count": True})
        )

    def test_small_pinned_reader_rejects_mode_and_symlink_ancestor(self) -> None:
        payload = b"fixture-evidence\n"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            evidence = root / "evidence.json"
            evidence.write_bytes(payload)
            evidence.chmod(0o600)
            specs = {
                Path("evidence.json"): checker.FileSpec(
                    len(payload), digest, 0o600, True
                )
            }
            with checker.pinned_file_payloads(specs, root=root) as captured:
                self.assertEqual(captured[Path("evidence.json")], payload)

            evidence.chmod(0o666)
            with self.assertRaisesRegex(checker.EvidenceError, "identity differs"):
                with checker.pinned_file_payloads(specs, root=root):
                    pass

            real = root / "real"
            real.mkdir()
            nested = real / "nested.json"
            nested.write_bytes(payload)
            nested.chmod(0o600)
            alias = root / "alias"
            alias.symlink_to(real, target_is_directory=True)
            alias_specs = {
                Path("alias/nested.json"): checker.FileSpec(
                    len(payload), digest, 0o600, True
                )
            }
            with self.assertRaisesRegex(checker.EvidenceError, "symlink ancestor"):
                with checker.pinned_file_payloads(alias_specs, root=root):
                    pass

    def test_pinned_reader_rejects_read_time_path_replacement(self) -> None:
        payload = b"x" * (1024 * 1024 + 17)
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            evidence = root / "evidence.bin"
            evidence.write_bytes(payload)
            evidence.chmod(0o600)
            specs = {
                Path("evidence.bin"): checker.FileSpec(
                    len(payload), digest, 0o600, False
                )
            }
            original_read = checker.os.read
            replaced = False

            def replace_after_first_read(descriptor: int, size: int) -> bytes:
                nonlocal replaced
                chunk = original_read(descriptor, size)
                if chunk and not replaced:
                    replaced = True
                    old = root / "held-old.bin"
                    evidence.rename(old)
                    evidence.write_bytes(payload)
                    evidence.chmod(0o600)
                return chunk

            with (
                patch.object(checker.os, "read", side_effect=replace_after_first_read),
                self.assertRaisesRegex(
                    checker.EvidenceError,
                    "pinned file (bytes|identity) changed",
                ),
            ):
                with checker.pinned_file_payloads(specs, root=root):
                    pass

    def test_pinned_reader_rejects_read_time_symlink_ancestor_replacement(
        self,
    ) -> None:
        payload = b"y" * (1024 * 1024 + 17)
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / "directory"
            directory.mkdir()
            evidence = directory / "evidence.bin"
            evidence.write_bytes(payload)
            evidence.chmod(0o600)
            specs = {
                Path("directory/evidence.bin"): checker.FileSpec(
                    len(payload), digest, 0o600, False
                )
            }
            original_read = checker.os.read
            replaced = False

            def replace_ancestor_after_first_read(
                descriptor: int,
                size: int,
            ) -> bytes:
                nonlocal replaced
                chunk = original_read(descriptor, size)
                if chunk and not replaced:
                    replaced = True
                    held_directory = root / "held-directory"
                    directory.rename(held_directory)
                    directory.symlink_to(
                        held_directory,
                        target_is_directory=True,
                    )
                return chunk

            with (
                patch.object(
                    checker.os,
                    "read",
                    side_effect=replace_ancestor_after_first_read,
                ),
                self.assertRaisesRegex(
                    checker.EvidenceError,
                    "identity changed",
                ),
            ):
                with checker.pinned_file_payloads(specs, root=root):
                    pass


if __name__ == "__main__":
    unittest.main()
