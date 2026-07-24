#!/usr/bin/env python3
"""Mutation tests for the dependency wave-one v2 recovery decision."""

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
    SCRIPT_DIR / "check_p2p_nat_g2_pion_dependency_wave1_recovery_decision_v2.py"
)
SPEC = importlib.util.spec_from_file_location("wave1_recovery_v2_checker", CHECKER_PATH)
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


class DependencyWaveOneRecoveryDecisionV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for relative in checker.EXPECTED_RAW_SHA256:
            source = checker.ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
        (self.root / checker.DEPENDENCY_PARENT / "wave-1").mkdir(
            parents=True,
            exist_ok=True,
        )
        (self.root / checker.DEPENDENCY_PARENT / "wave-1-v2").mkdir(
            parents=True,
            exist_ok=True,
        )
        for relative in (
            checker.CLAIM_V1_PATH,
            checker.FAILURE_V1_PATH,
            checker.CLAIM_V2_PATH,
            checker.FAILURE_V2_PATH,
        ):
            os.chmod(self.root / relative, 0o600)

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
            relative
            in {
                checker.CLAIM_V1_PATH,
                checker.FAILURE_V1_PATH,
                checker.CLAIM_V2_PATH,
                checker.FAILURE_V2_PATH,
            }
            and len(raw) <= original_size
        ):
            raw = raw[:-1] + (b" " * (original_size - len(raw))) + b"\n"
        path.write_bytes(raw)
        if relative in {
            checker.CLAIM_V1_PATH,
            checker.FAILURE_V1_PATH,
            checker.CLAIM_V2_PATH,
            checker.FAILURE_V2_PATH,
        }:
            os.chmod(path, 0o600)
        return hashlib.sha256(raw).hexdigest(), content_digest

    def assert_recovery_mutation_rejected(
        self,
        mutation,
        expected_code: str,
    ) -> None:
        raw_digest, content_digest = self.rewrite_json(
            checker.RECOVERY_PATH,
            mutation,
            rebind_content=True,
        )
        if content_digest is None:
            raise AssertionError("missing recovery content digest")
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.RECOVERY_PATH: raw_digest},
        ), mock.patch.object(
            checker,
            "EXPECTED_RECOVERY_CONTENT_SHA256",
            content_digest,
        ):
            self.assert_rejected(expected_code)

    def test_01_baseline(self) -> None:
        result = checker.validate_repository(self.root)
        self.assertEqual(result["failedTupleId"], checker.EXPECTED_TUPLE_ID)
        self.assertEqual(result["networkRequestAttemptCount"], 11)
        self.assertEqual(result["v3MaximumRequestCount"], 38)
        self.assertEqual(result["v3ExpectedRetainedResourceCount"], 38)
        self.assertFalse(result["v3ExecutionAuthorized"])
        self.assertFalse(result["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])

    def test_02_duplicate_recovery_json_key_is_rejected(self) -> None:
        path = self.root / checker.RECOVERY_PATH
        raw = path.read_bytes().replace(
            b'{\n  "documentType":',
            b'{\n  "schemaVersion":"2.0",\n  "documentType":',
            1,
        )
        path.write_bytes(raw)
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.RECOVERY_PATH: hashlib.sha256(raw).hexdigest()},
        ):
            self.assert_rejected("E_JSON")

    def test_03_claim_permit_binding_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.CLAIM_V2_PATH,
            lambda value: value.update({"permitContentSha256": "0" * 64}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.CLAIM_V2_PATH: digest},
        ):
            self.assert_rejected("E_CLAIM")

    def test_04_claim_retry_rule_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.CLAIM_V2_PATH,
            lambda value: value.update({"rule": "retry_allowed"}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.CLAIM_V2_PATH: digest},
        ):
            self.assert_rejected("E_CLAIM")

    def test_05_failure_counter_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_V2_PATH,
            lambda value: value.update({"responseBodyCompletedCount": 10}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_V2_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_06_failure_code_mutation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_V2_PATH,
            lambda value: value.update({"failureCode": "E_AUTH"}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_V2_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_07_failure_authentication_escalation_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_V2_PATH,
            lambda value: value.update({"externalAuthenticationRequired": True}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_V2_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_08_failure_accepted_artifact_invention_is_rejected(self) -> None:
        digest, _ = self.rewrite_json(
            checker.FAILURE_V2_PATH,
            lambda value: value.update({"acceptedArtifactCount": 1}),
        )
        with mock.patch.dict(
            checker.EXPECTED_RAW_SHA256,
            {checker.FAILURE_V2_PATH: digest},
        ):
            self.assert_rejected("E_FAILURE")

    def test_09_status_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value.update({"status": "ready"}),
            "E_RECOVERY",
        )

    def test_10_auth_root_cause_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["rootCause"].update(
                {"authenticationRelated": True}
            ),
            "E_ROOT_CAUSE",
        )

    def test_11_resource_order_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"].update(
                {"resourceOrderPerTuple": ["zip", "mod"]}
            ),
            "E_POLICY",
        )

    def test_12_request_ordinal_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["requestOrdinalRule"].update(
                {"mod": "two_times_tuple_order"}
            ),
            "E_POLICY",
        )

    def test_13_request_count_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"].update(
                {"maximumRequestCount": 19}
            ),
            "E_POLICY",
        )

    def test_14_embedded_mod_parity_removal_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["zipResource"].update(
                {"embeddedRootGoModMustMatchExternalModWhenPresent": False}
            ),
            "E_POLICY",
        )

    def test_15_mod_h1_removal_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["modResource"].update(
                {"goModH1MatchRequired": False}
            ),
            "E_POLICY",
        )

    def test_16_mod_utf8_removal_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["modResource"].update(
                {"utf8Required": False}
            ),
            "E_POLICY",
        )

    def test_17_mod_aggregate_limit_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["absoluteLimits"].update(
                {"maximumAggregateModResponseBytes": 19922944}
            ),
            "E_LIMITS",
        )

    def test_18_whole_deadline_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["absoluteLimits"].update(
                {"wholeWaveDeadlineMilliseconds": 0}
            ),
            "E_LIMITS",
        )

    def test_19_ambient_proxy_escalation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["requestPolicy"].update(
                {"ambientProxyAllowed": True}
            ),
            "E_REQUEST_POLICY",
        )

    def test_20_retry_escalation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["requestPolicy"].update(
                {"automaticRetryAllowed": True}
            ),
            "E_REQUEST_POLICY",
        )

    def test_21_success_counter_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["requiredCounterSchema"][
                "successValues"
            ].update({"validatedModResourceCount": 18}),
            "E_COUNTERS",
        )

    def test_22_failure_retry_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["failureContract"].update(
                {"automaticRetryAllowed": True}
            ),
            "E_ATOMICITY",
        )

    def test_23_success_retained_count_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["successContract"].update(
                {"retainedResourceCount": 19}
            ),
            "E_ATOMICITY",
        )

    def test_24_forbidden_go_command_mutation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["selectedV3Policy"]["forbiddenOperations"].update(
                {"goCommand": False}
            ),
            "E_SCOPE",
        )

    def test_25_v2_execute_reenable_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["v1AndV2PreservationContract"].update(
                {"v2RunnerExecuteAllowed": True}
            ),
            "E_PRESERVATION",
        )

    def test_26_namespace_reuse_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["v3NamespaceContract"].update(
                {"claimPath": checker.CLAIM_V2_PATH}
            ),
            "E_NAMESPACE",
        )

    def test_27_network_authority_escalation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["authority"].update({"networkAuthorized": True}),
            "E_AUTHORITY",
        )

    def test_28_user_authentication_requirement_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["personalProjectBoundary"].update(
                {"externalAuthenticationRequired": True}
            ),
            "E_AUTH_BOUNDARY",
        )

    def test_29_closure_invention_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["closure"].update({"waveAcquired": True}),
            "E_CLOSURE",
        )

    def test_30_runner_self_readback_escalation_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["independentReadbackContract"].update(
                {"runnerSelfCheckQualifiesAsIndependentReadback": True}
            ),
            "E_READBACK",
        )

    def test_31_reserved_file_count_scope_drift_is_rejected(self) -> None:
        self.assert_recovery_mutation_rejected(
            lambda value: value["independentReadbackContract"].update(
                {"regularFileCountMeaning": "recursive_directory_entry_count"}
            ),
            "E_READBACK",
        )

    def test_32_unexpected_v3_claim_is_rejected(self) -> None:
        path = self.root / checker.V3_CLAIM_PATH
        path.write_text("unexpected", encoding="utf-8")
        self.assert_rejected("E_NAMESPACE")

    def test_33_unexpected_v2_success_is_rejected(self) -> None:
        path = self.root / checker.V2_SUCCESS_PATH
        path.write_text("unexpected", encoding="utf-8")
        self.assert_rejected("E_NAMESPACE")

    def test_34_staging_artifact_is_rejected(self) -> None:
        path = self.root / checker.DEPENDENCY_PARENT / ".wave-1-v3-staging-x"
        path.mkdir()
        self.assert_rejected("E_NAMESPACE")

    def test_35_claim_symlink_is_rejected(self) -> None:
        claim = self.root / checker.CLAIM_V2_PATH
        claim.unlink()
        claim.symlink_to(self.root / checker.CLAIM_V1_PATH)
        self.assert_rejected("E_FILESYSTEM")

    def test_36_claim_hardlink_is_rejected(self) -> None:
        extra = self.root / checker.DEPENDENCY_PARENT / "extra-hardlink"
        os.link(self.root / checker.CLAIM_V2_PATH, extra)
        self.assert_rejected("E_FILESYSTEM")

    def test_37_claim_mode_drift_is_rejected(self) -> None:
        os.chmod(self.root / checker.CLAIM_V2_PATH, 0o644)
        self.assert_rejected("E_TERMINAL")

    def test_38_markdown_raw_drift_is_rejected(self) -> None:
        path = self.root / checker.RECOVERY_READER_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_rejected("E_RAW_BINDING")

    def test_39_final_barrier_detects_mutation(self) -> None:
        path = self.root / checker.RECOVERY_PATH

        def mutate_after_validation() -> None:
            path.write_bytes(path.read_bytes() + b" ")

        self.assert_rejected("E_TOCTOU", callback=mutate_after_validation)


if __name__ == "__main__":
    unittest.main()
