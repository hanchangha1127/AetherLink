#!/usr/bin/env python3
"""Mutation tests for the dependency wave-one v1 recovery decision."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent
CHECKER_PATH = (
    SCRIPT_DIR / "check_p2p_nat_g2_pion_dependency_wave1_recovery_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location("wave1_recovery_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


class DependencyWaveOneRecoveryDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for relative in checker.EXPECTED_RAW_SHA256:
            source = checker.ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
        (self.root / checker.V1_WAVE_DIRECTORY).mkdir(parents=True, exist_ok=True)
        os.chmod(self.root / checker.CLAIM_PATH, 0o600)
        os.chmod(self.root / checker.FAILURE_PATH, 0o600)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_rejected(
        self,
        expected_code: str,
        *,
        callback=None,
    ) -> None:
        with self.assertRaises(checker.CheckError) as context:
            checker.validate_repository(
                self.root,
                before_final_barrier=callback,
            )
        self.assertEqual(context.exception.code, expected_code)

    def rewrite_json(
        self,
        relative: str,
        mutation,
        *,
        rebind_content: bool = False,
    ) -> tuple[str, str | None]:
        path = self.root / relative
        original_size = path.stat().st_size
        document = json.loads(path.read_text(encoding="utf-8"))
        mutation(document)
        content_digest: str | None = None
        if rebind_content:
            payload = dict(document)
            payload.pop("contentBinding", None)
            content_digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
            document["contentBinding"]["sha256"] = content_digest
        raw = canonical_json_bytes(document)
        if (
            relative in {checker.CLAIM_PATH, checker.FAILURE_PATH}
            and len(raw) <= original_size
        ):
            raw = raw[:-1] + (b" " * (original_size - len(raw))) + b"\n"
        path.write_bytes(raw)
        if relative in {checker.CLAIM_PATH, checker.FAILURE_PATH}:
            os.chmod(path, 0o600)
        return hashlib.sha256(raw).hexdigest(), content_digest

    def test_01_baseline(self) -> None:
        result = checker.validate_repository(self.root)
        self.assertEqual(result["responseBodyCompletedCount"], 2)
        self.assertEqual(result["validatedAndStagedTupleCount"], 1)
        self.assertEqual(
            result["derivedFailedTuple"]["tupleId"],
            checker.EXPECTED_TUPLE_ID,
        )
        self.assertFalse(result["v2ExecutionAuthorized"])
        self.assertFalse(result["externalAuthenticationRequired"])

    def test_02_duplicate_recovery_json_key_is_rejected(self) -> None:
        path = self.root / checker.RECOVERY_PATH
        raw = path.read_bytes().replace(
            b'{\n  "documentType":',
            b'{\n  "schemaVersion":"1.0",\n  "documentType":',
            1,
        )
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.RECOVERY_PATH: digest},
        ):
            self.assert_rejected("E_JSON")

    def test_03_claim_binding_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.CLAIM_PATH,
            lambda value: value.update({"permitContentSha256": "0" * 64}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.CLAIM_PATH: digest},
        ):
            self.assert_rejected("E_CLAIM")

    def test_04_claim_retry_rule_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.CLAIM_PATH,
            lambda value: value.update({"rule": "retry_allowed"}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.CLAIM_PATH: digest},
        ):
            self.assert_rejected("E_CLAIM")

    def test_05_failure_attempt_count_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_PATH,
            lambda value: value.update({"attemptedRequestCount": 1}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_06_failure_completed_count_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_PATH,
            lambda value: value.update({"completedRequestCount": 2}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_07_failure_tuple_invention_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_PATH,
            lambda value: value.update({"failedTupleId": 0}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_08_failure_retry_escalation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_PATH,
            lambda value: value.update({"automaticRetryAllowed": True}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_09_failure_authentication_escalation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_PATH,
            lambda value: value.update({"externalAuthenticationRequired": True}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def recovery_mutation(self, mutation) -> tuple[str, str]:
        raw_digest, content_digest = self.rewrite_json(
            checker.RECOVERY_PATH,
            mutation,
            rebind_content=True,
        )
        if content_digest is None:
            raise AssertionError("missing recovery content digest")
        return raw_digest, content_digest

    def assert_recovery_mutation_rejected(
        self,
        mutation,
        expected_code: str,
    ) -> None:
        raw_digest, content_digest = self.recovery_mutation(mutation)
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.RECOVERY_PATH: raw_digest},
        ), mock.patch.object(
            checker,
            "EXPECTED_RECOVERY_CONTENT_SHA256",
            content_digest,
        ):
            self.assert_rejected(expected_code)

    def test_10_derived_tuple_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["failureInterpretation"].update(
                {"derivedFailedTupleId": "wave1-001-c7683a099605"}
            ),
            "E_DERIVATION",
        )

    def test_11_response_body_counter_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["failureInterpretation"].update(
                {"responseBodyCompletedCount": 1}
            ),
            "E_DERIVATION",
        )

    def test_12_failed_entry_identity_invention_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["failureInterpretation"].update(
                {"failedEntryIdentityEstablished": True}
            ),
            "E_DERIVATION",
        )

    def test_13_root_cause_authentication_drift_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["rootCause"].update(
                {"authenticationRelated": True}
            ),
            "E_POLICY",
        )

    def test_14_ratio_policy_threshold_substitution_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV2Policy"].update(
                {"compressionRatioPolicy": "raise_threshold_to_1000"}
            ),
            "E_POLICY",
        )

    def test_15_absolute_file_limit_weakening_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV2Policy"][
                "absoluteLimitsRetained"
            ].update({"maximumSingleFileBytes": 33554432}),
            "E_POLICY",
        )

    def test_16_floating_point_telemetry_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV2Policy"][
                "requiredCompressionTelemetry"
            ].update({"floatingPointRatioForbidden": False}),
            "E_POLICY",
        )

    def test_17_legacy_counter_reintroduction_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV2Policy"][
                "requiredCounterSchema"
            ].update({"legacyCompletedRequestCountForbidden": False}),
            "E_POLICY",
        )

    def test_18_v1_retry_authorization_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["v1PreservationContract"].update(
                {"v1RunnerExecuteAllowed": True}
            ),
            "E_PRESERVATION",
        )

    def test_19_v1_claim_deletion_authorization_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["v1PreservationContract"].update(
                {"v1ClaimDeletionAllowed": True}
            ),
            "E_PRESERVATION",
        )

    def test_20_v2_claim_path_collision_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["v2NamespaceContract"].update(
                {"claimPath": checker.CLAIM_PATH}
            ),
            "E_NAMESPACE",
        )

    def test_21_network_authority_escalation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["authority"].update({"networkAuthorized": True}),
            "E_AUTHORITY",
        )

    def test_22_user_authentication_escalation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["personalProjectBoundary"].update(
                {"externalAuthenticationRequired": True}
            ),
            "E_AUTHORITY",
        )

    def test_23_false_wave_closure_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["closure"].update({"waveAcquired": True}),
            "E_CLOSURE",
        )

    def test_24_v1_staging_residue_is_rejected(self) -> None:
        (self.root / checker.V1_STAGING_PARENT / ".wave-1-v1-staging-test").mkdir()
        self.assert_rejected("E_TERMINAL_STATE")

    def test_25_v1_wave_output_residue_is_rejected(self) -> None:
        path = self.root / checker.V1_WAVE_DIRECTORY / "unexpected.zip"
        path.write_bytes(b"not retained")
        self.assert_rejected("E_TERMINAL_STATE")

    def test_26_v1_success_receipt_presence_is_rejected(self) -> None:
        path = self.root / checker.V1_SUCCESS_PATH
        path.write_bytes(b"{}\n")
        self.assert_rejected("E_TERMINAL_STATE")

    def test_27_v1_manifest_presence_is_rejected(self) -> None:
        path = self.root / checker.V1_MANIFEST_PATH
        path.write_bytes(b"{}\n")
        self.assert_rejected("E_TERMINAL_STATE")

    def test_28_claim_hardlink_is_rejected(self) -> None:
        os.link(
            self.root / checker.CLAIM_PATH,
            self.root / checker.V1_STAGING_PARENT / "claim-hardlink",
        )
        self.assert_rejected("E_FILESYSTEM")

    def test_29_failure_symlink_is_rejected(self) -> None:
        path = self.root / checker.FAILURE_PATH
        target = path.with_name("failure-target.json")
        path.rename(target)
        path.symlink_to(target.name)
        self.assert_rejected("E_FILESYSTEM")

    def test_30_replace_after_read_is_rejected(self) -> None:
        def replace(_reader) -> None:
            path = self.root / checker.RECOVERY_PATH
            replacement = path.with_name(path.name + ".replacement")
            shutil.copy2(path, replacement)
            os.replace(replacement, path)

        self.assert_rejected("E_TOCTOU", callback=replace)

    def test_31_late_v1_terminal_artifact_insertion_is_rejected(self) -> None:
        def insert(_reader) -> None:
            path = self.root / checker.V1_SUCCESS_PATH
            path.write_bytes(b"{}\n")

        self.assert_rejected("E_TERMINAL_STATE", callback=insert)


if __name__ == "__main__":
    unittest.main()
