#!/usr/bin/env python3
"""Mutation tests for the dependency wave-one v2 execution permit."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
CHECKER_PATH = (
    SCRIPT_DIR
    / "check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v2.py"
)
SPEC = importlib.util.spec_from_file_location("wave1_v2_permit_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v2 permit checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

RECOVERY_CHECKER_PATH = SCRIPT_DIR / Path(checker.RECOVERY_CHECKER_PATH).name
RECOVERY_SPEC = importlib.util.spec_from_file_location(
    "wave1_recovery_checker_for_v2_tests",
    RECOVERY_CHECKER_PATH,
)
if RECOVERY_SPEC is None or RECOVERY_SPEC.loader is None:
    raise RuntimeError("cannot load recovery checker")
recovery = importlib.util.module_from_spec(RECOVERY_SPEC)
RECOVERY_SPEC.loader.exec_module(recovery)


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


class DependencyWaveOneV2PermitCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        paths = set(recovery.EXPECTED_RAW_SHA256)
        paths.add(recovery.RECOVERY_READER_PATH)
        paths.update(path for _, path in checker.EXPECTED_TOOL_ROWS)
        paths.update(
            {
                checker.PERMIT_PATH,
                checker.PERMIT_READER_PATH,
                checker.RECOVERY_PATH,
                checker.RECOVERY_READER_PATH,
                checker.SOURCE_DECISION_PATH,
            }
        )
        for relative in sorted(paths):
            source = checker.ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
        (self.root / recovery.V1_WAVE_DIRECTORY).mkdir(
            parents=True,
            exist_ok=True,
        )
        os.chmod(self.root / recovery.CLAIM_PATH, 0o600)
        os.chmod(self.root / recovery.FAILURE_PATH, 0o600)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_rejected(self, expected_code: str) -> None:
        with self.assertRaises(Exception) as context:
            checker.validate_repository(self.root)
        self.assertEqual(getattr(context.exception, "code", None), expected_code)

    def mutate_permit(self, mutation, *, rebind: bool = True) -> None:
        path = self.root / checker.PERMIT_PATH
        document = json.loads(path.read_text(encoding="utf-8"))
        mutation(document)
        if rebind:
            unsigned = dict(document)
            unsigned.pop("contentBinding", None)
            document["contentBinding"]["sha256"] = hashlib.sha256(
                canonical_json_bytes(unsigned)
            ).hexdigest()
        path.write_bytes(canonical_json_bytes(document))

    def test_01_baseline(self) -> None:
        result = checker.validate_repository(self.root)
        self.assertTrue(result["v1PermitConsumed"])
        self.assertTrue(result["v2ExecutionAuthorized"])
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertEqual(result["runnerTestCount"], 28)
        self.assertEqual(result["checkerTestCount"], 20)

    def test_02_duplicate_permit_key_is_rejected(self) -> None:
        path = self.root / checker.PERMIT_PATH
        raw = path.read_bytes().replace(
            b'{\n  "documentType":',
            b'{\n  "schemaVersion":"2.0",\n  "documentType":',
            1,
        )
        path.write_bytes(raw)
        self.assert_rejected("E_JSON")

    def test_03_external_authentication_escalation_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["personalProjectBoundary"].update(
                {"externalAuthenticationRequired": True}
            )
        )
        self.assert_rejected("E_AUTHORITY")

    def test_04_v1_retry_authorization_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["recoveryBinding"].update(
                {"v1RunnerExecuteAllowed": True}
            )
        )
        self.assert_rejected("E_RECOVERY")

    def test_05_recovery_bytes_drift_is_rejected(self) -> None:
        path = self.root / checker.RECOVERY_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RECOVERY")

    def test_06_source_decision_bytes_drift_is_rejected(self) -> None:
        path = self.root / checker.SOURCE_DECISION_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RECOVERY")

    def test_07_tool_binding_hash_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["toolBindings"][3].update(
                {"rawSha256": "0" * 64}
            )
        )
        self.assert_rejected("E_TOOL")

    def test_08_interpreter_command_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["interpreterIsolationContract"][
                "executeCommand"
            ].remove("-I")
        )
        self.assert_rejected("E_RUNTIME")

    def test_09_v2_claim_path_collision_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["oneUseConsumption"].update(
                {"claimPath": checker.V1_CLAIM_PATH}
            )
        )
        self.assert_rejected("E_ONE_USE")

    def test_10_automatic_retry_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["oneUseConsumption"].update(
                {"automaticRetryAllowed": True}
            )
        )
        self.assert_rejected("E_ONE_USE")

    def test_11_alternate_network_host_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["networkAuthority"].update(
                {"authorizedHost": "example.invalid"}
            )
        )
        self.assert_rejected("E_AUTHORITY")

    def test_12_runtime_network_authority_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["networkAuthority"].update(
                {"runtimeNetworkAuthorized": True}
            )
        )
        self.assert_rejected("E_AUTHORITY")

    def test_13_ratio_rejection_reintroduction_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["archiveValidationContract"].update(
                {"compressionRatioRejectionAllowed": True}
            )
        )
        self.assert_rejected("E_ARCHIVE")

    def test_14_floating_point_ratio_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["telemetryPolicy"].update(
                {"floatingPointRatioAllowed": True}
            )
        )
        self.assert_rejected("E_TELEMETRY")

    def test_15_absolute_limit_weakening_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["absoluteResourceLimits"].update(
                {"maximumSingleFileBytes": 33554432}
            )
        )
        self.assert_rejected("E_LIMIT")

    def test_16_legacy_counter_reintroduction_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["telemetryPolicy"].update(
                {"legacyCompletedRequestCountForbidden": False}
            )
        )
        self.assert_rejected("E_TELEMETRY")

    def test_17_v2_receipt_path_collision_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["receiptFailureManifestContract"].update(
                {"failureReceiptPath": checker.V1_FAILURE_PATH}
            )
        )
        self.assert_rejected("E_RECEIPT")

    def test_18_false_closure_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["closure"].update(
                {"dependencyClosureComplete": True}
            )
        )
        self.assert_rejected("E_CLOSURE")

    def test_19_permit_reader_authentication_drift_is_rejected(self) -> None:
        path = self.root / checker.PERMIT_READER_PATH
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("No user authentication is required", "Login required"),
            encoding="utf-8",
        )
        self.assert_rejected("E_READER")

    def test_20_symlinked_v2_runner_is_rejected(self) -> None:
        path = self.root / checker.RUNNER_PATH
        target = path.with_name(path.name + ".target")
        path.rename(target)
        path.symlink_to(target.name)
        self.assert_rejected("E_FILESYSTEM")


if __name__ == "__main__":
    unittest.main()
