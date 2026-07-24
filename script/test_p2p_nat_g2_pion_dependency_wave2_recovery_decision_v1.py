#!/usr/bin/env python3
"""Offline regression tests for the Wave2 v1 preclaim recovery decision."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    ROOT
    / "script/check_p2p_nat_g2_pion_dependency_wave2_recovery_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave2_recovery_v1_tests_target",
    CHECKER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)
COMMON = CHECKER.COMMON


class WaveTwoRecoveryDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(
            (ROOT / CHECKER.RECOVERY_PATH).read_text(encoding="utf-8")
        )

    def mutated(self, callback):
        value = copy.deepcopy(self.document)
        callback(value)
        return value

    def test_01_document_is_valid(self) -> None:
        CHECKER.validate_recovery_document(self.document)

    def test_02_content_binding_is_exact(self) -> None:
        self.assertEqual(
            COMMON.validate_content_binding(
                self.document,
                scope="decision_without_contentBinding",
            ),
            CHECKER.EXPECTED_RECOVERY_CONTENT_SHA256,
        )

    def test_03_status_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(lambda d: d.__setitem__("status", "selected"))
            )

    def test_04_result_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(lambda d: d.__setitem__("result", "passed"))
            )

    def test_05_network_count_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(
                    lambda d: d["observedV1State"].__setitem__(
                        "networkRequestAttemptCount",
                        1,
                    )
                )
            )

    def test_06_claim_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(
                    lambda d: d["observedV1State"].__setitem__(
                        "claimCreated",
                        True,
                    )
                )
            )

    def test_07_v1_retry_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(
                    lambda d: d["v1PreservationContract"].__setitem__(
                        "v1RetryAllowed",
                        True,
                    )
                )
            )

    def test_08_adapter_policy_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(
                    lambda d: d["selectedV2Policy"].__setitem__(
                        "singleExactRootIdentityAdapterRequired",
                        False,
                    )
                )
            )
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(
                    lambda d: d["v1RevocationContract"].__setitem__(
                        "automaticRetryAllowed",
                        True,
                    )
                )
            )

    def test_09_runner_adapter_wiring_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(
                    lambda d: d["selectedV2Policy"].__setitem__(
                        "runnerAndReadbackMustUseAdapter",
                        False,
                    )
                )
            )

    def test_10_authentication_drift_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(
                self.mutated(
                    lambda d: d["personalProjectBoundary"].__setitem__(
                        "externalAuthenticationRequired",
                        True,
                    )
                )
            )

    def test_11_current_v1_namespace_is_absent(self) -> None:
        self.assertTrue(
            all(
                CHECKER.path_absent(ROOT, path)
                for path in CHECKER.V1_TERMINAL_PATHS
            )
        )
        sentinel = ROOT / CHECKER.V1_REVOCATION_SENTINEL_PATH
        self.assertTrue(sentinel.is_file())
        self.assertEqual(
            COMMON.sha256_bytes(sentinel.read_bytes()),
            CHECKER.EXPECTED_V1_REVOCATION_SENTINEL_RAW_SHA256,
        )

    def test_12_current_v2_namespace_is_absent(self) -> None:
        self.assertTrue(
            all(
                CHECKER.path_absent(ROOT, path)
                for path in CHECKER.V2_TERMINAL_PATHS
            )
        )
        result = CHECKER.validate_repository(
            ROOT,
            require_v2_clean=False,
        )
        self.assertFalse(result["v2NamespaceCleanRequired"])

    def test_13_actual_compatibility_preflight_passes(self) -> None:
        result = CHECKER.validate_repository(ROOT)
        self.assertTrue(result["rootCauseReproduced"])
        self.assertTrue(result["adaptedRootOpenClosePassed"])
        self.assertTrue(result["v1TechnicalExecutionBlocked"])
        self.assertTrue(result["v1RevocationSentinelRetained"])
        self.assertFalse(result["v2ExecutionAuthorized"])

    def test_14_checker_has_no_network_or_process_calls(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        for token in (
            "urllib.",
            "socket.",
            "subprocess.",
            "os.system(",
        ):
            self.assertNotIn(token, source)

    def test_15_checker_has_no_write_calls(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        for token in (
            "write_text(",
            "write_bytes(",
            "os.write(",
            "os.mkdir(",
            "os.rename(",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
