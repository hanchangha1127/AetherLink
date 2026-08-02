#!/usr/bin/env python3
"""Tests for independent production-append recovery evidence readback."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from script import (
    check_macos_runtime_chat_production_append_abrupt_recovery_evidence as check,
)


class ProductionAppendAbruptRecoveryEvidenceTests(unittest.TestCase):
    def write_owner_only(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(0o600)

    def write_fixture(
        self,
        directory: Path,
        *,
        result: dict[str, object] | None = None,
        receipt: dict[str, object] | None = None,
        root: Path = check.ROOT,
    ) -> tuple[Path, Path, dict[str, object], bytes]:
        fixture_result = result or check.expected_result(
            check.current_source_inputs(root=root)
        )
        result_bytes = check.canonical_bytes(fixture_result)
        fixture_receipt = receipt or check.expected_receipt(result_bytes)
        result_path = directory / "result.json"
        receipt_path = directory / "repeatability.json"
        self.write_owner_only(result_path, result_bytes)
        self.write_owner_only(
            receipt_path,
            check.canonical_bytes(fixture_receipt),
        )
        return result_path, receipt_path, fixture_result, result_bytes

    def test_exact_current_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result_path, receipt_path, _, result_bytes = self.write_fixture(
                Path(temporary_name)
            )
            observed = check.check_evidence(result_path, receipt_path)
        self.assertEqual(observed["status"], "passed")
        self.assertEqual(observed["resultByteCount"], len(result_bytes))
        self.assertEqual(
            observed["resultSha256"],
            hashlib.sha256(result_bytes).hexdigest(),
        )

    def test_boolean_integer_alias_is_rejected(self) -> None:
        result = check.expected_result(check.current_source_inputs())
        result["abruptTermination"]["dirtyDatabaseBeforeRecovery"][
            "eventCount"
        ] = True
        with tempfile.TemporaryDirectory() as temporary_name:
            directory = Path(temporary_name)
            result_path, receipt_path, _, _ = self.write_fixture(
                directory,
                result=result,
            )
            with self.assertRaises(check.EvidenceError):
                check.check_evidence(result_path, receipt_path)

    def test_duplicate_json_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            directory = Path(temporary_name)
            result_path, receipt_path, _, _ = self.write_fixture(directory)
            duplicate = (
                result_path.read_bytes()[:-2]
                + b',"status":"duplicate"}\n'
            )
            self.write_owner_only(result_path, duplicate)
            with self.assertRaisesRegex(
                check.EvidenceError,
                "repeats a JSON key",
            ):
                check.check_evidence(result_path, receipt_path)

    def test_repeatability_digest_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            directory = Path(temporary_name)
            result_path, receipt_path, _, result_bytes = self.write_fixture(
                directory
            )
            receipt = check.expected_receipt(result_bytes)
            receipt["resultSha256"] = "0" * 64
            self.write_owner_only(receipt_path, check.canonical_bytes(receipt))
            with self.assertRaisesRegex(
                check.EvidenceError,
                "does not bind",
            ):
                check.check_evidence(result_path, receipt_path)

    def test_source_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            temporary_root = Path(temporary_name) / "source"
            for relative_path in check.SOURCE_INPUT_PATHS:
                destination = temporary_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((check.ROOT / relative_path).read_bytes())
            evidence_root = Path(temporary_name) / "evidence"
            result_path, receipt_path, _, _ = self.write_fixture(
                evidence_root,
                root=temporary_root,
            )
            changed_path = temporary_root / check.SOURCE_INPUT_PATHS[0]
            changed_path.write_bytes(changed_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(
                check.EvidenceError,
                "current source",
            ):
                check.check_evidence(
                    result_path,
                    receipt_path,
                    root=temporary_root,
                )

    def test_non_owner_only_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            result_path, receipt_path, _, _ = self.write_fixture(
                Path(temporary_name)
            )
            result_path.chmod(0o644)
            with self.assertRaisesRegex(
                check.EvidenceError,
                "identity is invalid",
            ):
                check.check_evidence(result_path, receipt_path)

    def test_symlink_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            directory = Path(temporary_name)
            result_path, receipt_path, _, _ = self.write_fixture(directory)
            symlink_path = directory / "result-link.json"
            os.symlink(result_path, symlink_path)
            with self.assertRaises(check.EvidenceError):
                check.check_evidence(symlink_path, receipt_path)

    def test_exact_equal_rejects_nested_type_aliases(self) -> None:
        self.assertFalse(check.exact_equal({"count": True}, {"count": 1}))
        self.assertFalse(check.exact_equal({"count": 1}, {"count": True}))
        self.assertTrue(check.exact_equal({"count": 1}, {"count": 1}))


if __name__ == "__main__":
    unittest.main()
