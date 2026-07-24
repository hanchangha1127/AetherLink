#!/usr/bin/env python3
"""Offline regression tests for the Wave2 v2 terminal recovery decision."""

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
    / "script/check_p2p_nat_g2_pion_dependency_wave2_recovery_decision_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave2_recovery_v2_tests_target",
    CHECKER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)
COMMON = CHECKER.COMMON


class WaveTwoRecoveryDecisionV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(
            (ROOT / CHECKER.RECOVERY_PATH).read_text(encoding="utf-8")
        )

    def mutated(self, callback):
        value = copy.deepcopy(self.document)
        callback(value)
        return value

    def rejected(self, value) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_recovery_document(value)

    def test_01_document_and_content_binding_are_exact(self) -> None:
        CHECKER.validate_recovery_document(self.document)
        self.assertEqual(
            COMMON.validate_content_binding(
                self.document,
                scope="decision_without_contentBinding",
            ),
            CHECKER.EXPECTED_RECOVERY_CONTENT_SHA256,
        )

    def test_02_status_result_and_next_action_drift_are_rejected(self) -> None:
        for key in ("status", "result", "nextAction"):
            self.rejected(
                self.mutated(lambda d, k=key: d.__setitem__(k, "drift"))
            )

    def test_03_claim_hash_size_and_retry_drift_are_rejected(self) -> None:
        for key, value in (
            ("rawSha256", "0" * 64),
            ("byteSize", 754),
            ("automaticRetryAllowed", True),
        ):
            self.rejected(
                self.mutated(
                    lambda d, k=key, v=value: d[
                        "terminalFailureBindings"
                    ]["claimV2"].__setitem__(k, v)
                )
            )

    def test_04_failure_context_and_counters_are_exact(self) -> None:
        for key, value in (
            ("failureCode", "E_INTERNAL"),
            ("failedRequestOrdinal", 3),
            ("failedTupleOrder", 1),
            ("networkRequestAttemptCount", 5),
            ("validatedZipResourceCount", 2),
        ):
            self.rejected(
                self.mutated(
                    lambda d, k=key, v=value: d[
                        "terminalFailureBindings"
                    ]["failureReceiptV2"].__setitem__(k, v)
                )
            )

    def test_05_unknown_actual_ratio_cannot_be_claimed(self) -> None:
        self.rejected(
            self.mutated(
                lambda d: d["failureInterpretation"].__setitem__(
                    "actualCompressionRatioRecorded",
                    True,
                )
            )
        )
        self.rejected(
            self.mutated(
                lambda d: d["failureInterpretation"].__setitem__(
                    "safeNumericObservations",
                    {"entryUncompressedBytes": 1},
                )
            )
        )

    def test_06_telemetry_is_exact_integer_and_non_gating(self) -> None:
        for key, value in (
            ("policy", "gating"),
            ("historicalV2ComparisonRatio", 201),
            ("divisionOrFloatingPointAllowed", True),
            ("ratioUsedAsRejectionGate", True),
            ("entryNameOrBodyRecorded", True),
        ):
            self.rejected(
                self.mutated(
                    lambda d, k=key, v=value: d["selectedV3Policy"][
                        "compressionTelemetry"
                    ].__setitem__(k, v)
                )
            )

    def test_07_absolute_bound_weakening_is_rejected(self) -> None:
        for key in (
            "maximumZipResponseBytesPerTuple",
            "maximumAggregateResponseBytes",
            "maximumEntriesPerArchive",
            "maximumAggregateEntries",
            "maximumSingleFileBytes",
            "maximumUncompressedBytesPerArchive",
            "maximumAggregateUncompressedBytes",
            "wholeWaveDeadlineMilliseconds",
        ):
            self.rejected(
                self.mutated(
                    lambda d, k=key: d["selectedV3Policy"][
                        "absoluteLimits"
                    ].__setitem__(
                        k,
                        d["selectedV3Policy"]["absoluteLimits"][k] + 1,
                    )
                )
            )

    def test_08_v2_reuse_resume_or_retry_is_rejected(self) -> None:
        for key in (
            "v2ResponseOrStagingReuseAllowed",
            "v2PartialResumeAllowed",
        ):
            self.rejected(
                self.mutated(
                    lambda d, k=key: d["selectedV3Policy"].__setitem__(
                        k,
                        True,
                    )
                )
            )
        for key in (
            "v2PermitReuseAllowed",
            "v2RunnerExecuteAllowed",
            "v2AutomaticRetryAllowed",
            "v2StagingResumeAllowed",
        ):
            self.rejected(
                self.mutated(
                    lambda d, k=key: d[
                        "v1AndV2PreservationContract"
                    ].__setitem__(k, True)
                )
            )

    def test_09_v3_projection_digest_drift_is_rejected(self) -> None:
        self.rejected(
            self.mutated(
                lambda d: d["v3NamespaceContract"].__setitem__(
                    "v3OrderedResourceSetSha256",
                    "0" * 64,
                )
            )
        )

    def test_10_personal_project_authentication_drift_is_rejected(self) -> None:
        for key in (
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "credentialsAllowed",
            "privateKeyRequired",
            "signatureRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ):
            self.rejected(
                self.mutated(
                    lambda d, k=key: d[
                        "personalProjectBoundary"
                    ].__setitem__(k, True)
                )
            )

    def test_11_exact_terminal_files_are_bound(self) -> None:
        inputs = COMMON.HeldInputSet(ROOT, CHECKER.recovery_bindings())
        try:
            claim, failure = CHECKER.validate_v2_terminal(inputs, ROOT)
            self.assertEqual(claim["permitContentSha256"], CHECKER.EXPECTED_V2_PERMIT_CONTENT_SHA256)
            self.assertEqual(failure["failureCode"], "E_ZIP_COMPRESSION_RATIO")
        finally:
            inputs.close()

    def test_12_v3_namespace_is_currently_clean(self) -> None:
        self.assertTrue(
            all(
                CHECKER.path_absent(ROOT, path)
                for path in CHECKER.V3_TERMINAL_PATHS
            )
        )

    def test_13_repository_terminal_preflight_passes(self) -> None:
        result = CHECKER.validate_repository(ROOT)
        self.assertTrue(result["v2TerminalStateValid"])
        self.assertTrue(result["v2PermitConsumed"])
        self.assertFalse(result["v2RetryAuthorized"])
        self.assertFalse(result["v3ExecutionAuthorized"])

    def test_14_checker_has_no_network_or_process_calls(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        for token in ("urllib.", "socket.", "subprocess.", "os.system("):
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
