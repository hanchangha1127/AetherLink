#!/usr/bin/env python3
"""Offline mutation tests for the consumed G2 Pion rung-two receipt."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung2_acquisition_receipt.py"
SPEC = importlib.util.spec_from_file_location("g2_pion_rung2_receipt_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load G2 Pion rung-two receipt checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class G2PionRungTwoAcquisitionReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = CHECKER.BASE.load_json(CHECKER.RECEIPT_PATH)
        cls.progress = CHECKER.BASE.load_json(CHECKER.PROGRESS_PATH)
        cls.manifest = CHECKER.BASE.load_json(CHECKER.MANIFEST_PATH)
        cls.canonical_sync_manifest = CHECKER.BASE.load_json(
            CHECKER.CANONICAL_SYNC_MANIFEST_PATH
        )
        cls.canonical_semantic_sync_manifest = CHECKER.BASE.load_json(
            CHECKER.CANONICAL_SEMANTIC_SYNC_MANIFEST_PATH
        )

    def assert_receipt_rejected(self, mutation) -> None:
        document = copy.deepcopy(self.receipt)
        mutation(document)
        with self.assertRaises(CHECKER.ReceiptValidationError):
            CHECKER.validate_receipt_document(document, semantic=False)

    def assert_progress_rejected(self, mutation) -> None:
        document = copy.deepcopy(self.progress)
        mutation(document)
        with self.assertRaises(CHECKER.ReceiptValidationError):
            CHECKER.validate_progress_document(document, semantic=False)

    def assert_manifest_rejected(self, mutation) -> None:
        document = copy.deepcopy(self.manifest)
        mutation(document)
        with self.assertRaises(CHECKER.ReceiptValidationError):
            CHECKER.validate_manifest_document(document, semantic=False)

    def assert_canonical_sync_manifest_rejected(self, mutation) -> None:
        document = copy.deepcopy(self.canonical_sync_manifest)
        mutation(document)
        with self.assertRaises(CHECKER.ReceiptValidationError):
            CHECKER.validate_canonical_sync_manifest_document(
                document, semantic=False
            )

    def assert_canonical_semantic_sync_manifest_rejected(self, mutation) -> None:
        document = copy.deepcopy(self.canonical_semantic_sync_manifest)
        mutation(document)
        with self.assertRaises(CHECKER.ReceiptValidationError):
            CHECKER.validate_canonical_semantic_sync_manifest_document(
                document, semantic=False, verify_superseded_artifact_files=False
            )

    def test_01_current_repository_receipt_passes_offline(self) -> None:
        CHECKER.validate_repository()

    def test_02_receipt_top_level_unknown_and_missing_keys_fail(self) -> None:
        self.assert_receipt_rejected(lambda value: value.update({"unknown": False}))
        self.assert_receipt_rejected(lambda value: value.pop("archive"))

    def test_03_receipt_request_count_url_and_bool_int_drift_fail(self) -> None:
        mutations = (
            lambda value: value["request"].update({"requestCount": 2}),
            lambda value: value["request"].update({"requestCount": True}),
            lambda value: value["request"].update({"url": "https://example.invalid/x"}),
            lambda value: value["request"].update({"redirectCount": 1}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_receipt_rejected(mutation)

    def test_04_receipt_checksum_or_success_flag_drift_fails(self) -> None:
        mutations = (
            lambda value: value["verification"].update({"rawSha256": "0" * 64}),
            lambda value: value["verification"].update({"moduleH1Matches": False}),
            lambda value: value["verification"].update({"allRequiredChecksPassed": False}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_receipt_rejected(mutation)

    def test_05_receipt_extraction_selection_and_auth_escalation_fail(self) -> None:
        mutations = (
            lambda value: value["archive"].update({"filesystemExtracted": True}),
            lambda value: value["executionBoundary"].update({"candidateSelected": True}),
            lambda value: value["executionBoundary"].update({"librarySelected": True}),
            lambda value: value["executionBoundary"].update({"externalIdentityProofRequired": True}),
            lambda value: value["executionBoundary"].update({"repositoryOwnerAuthenticationRequired": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_receipt_rejected(mutation)

    def test_06_progress_supersession_and_receipt_binding_drift_fail(self) -> None:
        mutations = (
            lambda value: value["supersedes"].update({"sha256": "0" * 64}),
            lambda value: value["receiptBinding"].update({"sha256": "0" * 64}),
            lambda value: value["decisionBinding"].update({"status": "bound"}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_progress_rejected(mutation)

    def test_07_progress_permit_request_and_archive_state_drift_fail(self) -> None:
        mutations = (
            lambda value: value["acquisitionSummary"].update({"requestCount": 0}),
            lambda value: value["acquisitionSummary"].update({"permitConsumed": False}),
            lambda value: value["acquisitionSummary"].update({"archiveExtracted": True}),
            lambda value: value["acquisitionSummary"].update({"fileCount": 128}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_progress_rejected(mutation)

    def test_08_progress_authority_escalation_and_rung_three_execution_fail(self) -> None:
        mutations = (
            lambda value: value["executionBoundary"].update({"additionalSourceAcquisitionAllowed": True}),
            lambda value: value["executionBoundary"].update({"compilerInvocationAllowed": True}),
            lambda value: value["executionBoundary"].update({"runtimeNetworkIoAllowed": True}),
            lambda value: value["executionBoundary"].update({"rungThreeOfflineReviewExecutionAllowed": True}),
            lambda value: value["executionBoundary"].update({"userActionRequired": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_progress_rejected(mutation)

    def test_09_manifest_unknown_missing_and_artifact_count_drift_fail(self) -> None:
        self.assert_manifest_rejected(lambda value: value.update({"unknown": False}))
        self.assert_manifest_rejected(lambda value: value.pop("artifacts"))
        self.assert_manifest_rejected(lambda value: value.update({"artifactCount": 4}))
        self.assert_canonical_sync_manifest_rejected(
            lambda value: value.update({"unknown": False})
        )
        self.assert_canonical_sync_manifest_rejected(
            lambda value: value.update({"artifactCount": 6})
        )
        self.assert_canonical_semantic_sync_manifest_rejected(
            lambda value: value.update({"unknown": False})
        )
        self.assert_canonical_semantic_sync_manifest_rejected(
            lambda value: value.update({"artifactCount": 3})
        )

    def test_10_manifest_reordered_path_and_hash_rows_fail(self) -> None:
        def reorder(value) -> None:
            value["artifacts"][0], value["artifacts"][1] = (
                value["artifacts"][1], value["artifacts"][0]
            )

        mutations = (
            reorder,
            lambda value: value["artifacts"][2].update({"path": "build/wrong.zip"}),
            lambda value: value["artifacts"][4].update({"sha256": "0" * 64}),
            lambda value: value.update({"collectionSha256": "0" * 64}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_manifest_rejected(mutation)
        self.assert_canonical_sync_manifest_rejected(
            lambda value: value["artifacts"][1].update({"sha256": "0" * 64})
        )
        self.assert_canonical_sync_manifest_rejected(
            lambda value: value.update({"collectionSha256": "0" * 64})
        )
        self.assert_canonical_semantic_sync_manifest_rejected(
            lambda value: value["artifacts"][0].update({"sha256": "0" * 64})
        )
        self.assert_canonical_semantic_sync_manifest_rejected(
            lambda value: value.update({"collectionSha256": "0" * 64})
        )

    def test_11_manifest_execution_or_identity_claim_escalation_fails(self) -> None:
        mutations = (
            lambda value: value.update({"archiveExtracted": True}),
            lambda value: value.update({"sourceReviewPerformed": True}),
            lambda value: value.update({"candidateSelected": True}),
            lambda value: value.update({"externalIdentityProofRequired": True}),
            lambda value: value.update({"repositoryOwnerAuthenticationRequired": True}),
            lambda value: value.update({"rungThreeOfflineReviewExecutionAllowed": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assert_manifest_rejected(mutation)
        for mutation in (
            lambda value: value.update({"archiveExtracted": True}),
            lambda value: value.update({"sourceReviewPerformed": True}),
            lambda value: value.update({"rungThreeOfflineReviewExecutionAllowed": True}),
            lambda value: value.update({"repositoryOwnerAuthenticationRequired": True}),
        ):
            self.assert_canonical_sync_manifest_rejected(mutation)
            self.assert_canonical_semantic_sync_manifest_rejected(mutation)

    def test_12_duplicate_names_and_nonfinite_numbers_fail_strict_parsing(self) -> None:
        invalid_documents = (
            '{"a":1,"a":2}',
            '{"value":NaN}',
            '{"value":Infinity}',
            '{"value":-Infinity}',
        )
        for raw in invalid_documents:
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.ReceiptValidationError):
                    CHECKER.BASE.parse_json(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
