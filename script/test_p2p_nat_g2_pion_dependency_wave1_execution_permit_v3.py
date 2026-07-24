#!/usr/bin/env python3
"""Synthetic mutation tests for the dependency wave-one v3 permit checker."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
CHECKER_PATH = (
    SCRIPT_DIR
    / "check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v3.py"
)
SPEC = importlib.util.spec_from_file_location("wave1_v3_permit_checker", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v3 permit checker")
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


class DependencyWaveOneV3PermitCheckerTests(unittest.TestCase):
    """Every test operates on an owner-controlled, no-network synthetic root."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        paths = {
            *checker.EXPECTED_FIXED_RAW_SHA256,
            *(path for _, path in checker.TOOL_ROWS),
        }
        for relative in sorted(paths):
            source = checker.ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)

        checker_raw = (self.root / checker.CHECKER_PATH).read_bytes()
        checker_digest = hashlib.sha256(checker_raw).hexdigest()
        runner_path = self.root / checker.RUNNER_PATH
        runner_text = runner_path.read_text(encoding="utf-8")
        pattern = re.compile(
            r'(EXPECTED_PERMIT_CHECKER_RAW_SHA256\s*=\s*\(\s*")[^"]+("\s*\))'
        )
        runner_text, replacements = pattern.subn(
            rf"\g<1>{checker_digest}\g<2>",
            runner_text,
            count=1,
        )
        if replacements != 1:
            raise RuntimeError("cannot bind fixture runner to checker")
        runner_path.write_text(runner_text, encoding="utf-8")

        self.write_fresh_permit()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def fixture_raw(self) -> dict[str, bytes]:
        return {
            path: (self.root / path).read_bytes()
            for _, path in checker.TOOL_ROWS
        }

    def write_fresh_permit(self) -> None:
        source = checker.strict_json(
            (self.root / checker.SOURCE_DECISION_PATH).read_bytes(),
            "fixture source",
        )
        recovery = checker.strict_json(
            (self.root / checker.RECOVERY_PATH).read_bytes(),
            "fixture recovery",
        )
        document = checker.build_expected_permit(
            source,
            recovery,
            self.fixture_raw(),
        )
        path = self.root / checker.PERMIT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json_bytes(document))

    def mutate_permit(
        self,
        mutation,
        *,
        rebind: bool = True,
    ) -> None:
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

    def assert_rejected(self, expected_code: str) -> None:
        with self.assertRaises(Exception) as context:
            checker.validate_repository(self.root)
        self.assertEqual(getattr(context.exception, "code", None), expected_code)

    def test_01_baseline_synthetic_permit_passes(self) -> None:
        result = checker.validate_repository(self.root)
        self.assertTrue(result["v3ExecutionAuthorized"])
        self.assertTrue(result["namespaceInitiallyClean"])
        self.assertTrue(result["v1PermitConsumed"])
        self.assertTrue(result["v2PermitConsumed"])
        self.assertEqual(result["testCounts"][checker.RUNNER_TEST_PATH], 45)
        self.assertEqual(result["testCounts"][checker.CHECKER_TEST_PATH], 39)

    def test_02_absent_permit_preflight_is_not_authorized(self) -> None:
        (self.root / checker.PERMIT_PATH).unlink()
        status, exit_code = checker.preflight_status(self.root)
        self.assertEqual(exit_code, 1)
        self.assertEqual(status["status"], "permit_absent_not_authorized")
        self.assertFalse(status["validationPassed"])
        self.assertFalse(status["v3ExecutionAuthorized"])
        self.assertEqual(status["networkOperationCount"], 0)
        self.assertEqual(status["fileWriteCount"], 0)

    def test_03_duplicate_permit_key_is_rejected(self) -> None:
        path = self.root / checker.PERMIT_PATH
        raw = path.read_bytes().replace(
            b'{"absoluteResourceLimits":',
            b'{"schemaVersion":"3.0","absoluteResourceLimits":',
            1,
        )
        path.write_bytes(raw)
        self.assert_rejected("E_JSON")

    def test_04_content_binding_mismatch_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value.update({"scope": "drift"}),
            rebind=False,
        )
        self.assert_rejected("E_BINDING")

    def test_05_status_drift_is_rejected_after_rebinding(self) -> None:
        self.mutate_permit(lambda value: value.update({"status": "drift"}))
        self.assert_rejected("E_STATE")

    def test_06_authentication_escalation_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["personalProjectBoundary"].update(
                {"externalAuthenticationRequired": True}
            )
        )
        self.assert_rejected("E_AUTHORITY")

    def test_07_source_decision_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.SOURCE_DECISION_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RAW_BINDING")

    def test_08_recovery_decision_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.RECOVERY_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RAW_BINDING")

    def test_09_recovery_checker_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.RECOVERY_CHECKER_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_rejected("E_RAW_BINDING")

    def test_10_recovery_checker_test_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.RECOVERY_TEST_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_rejected("E_RAW_BINDING")

    def test_11_v1_claim_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.V1_CLAIM_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RAW_BINDING")

    def test_12_v1_failure_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.V1_FAILURE_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RAW_BINDING")

    def test_13_v2_claim_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.V2_CLAIM_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RAW_BINDING")

    def test_14_v2_failure_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.V2_FAILURE_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RAW_BINDING")

    def test_15_symlink_and_hardlink_terminal_files_are_rejected(self) -> None:
        path = self.root / checker.V2_CLAIM_PATH
        original = path.read_bytes()
        mode = path.stat().st_mode & 0o777
        path.unlink()
        target = path.with_name(path.name + ".target")
        target.write_bytes(original)
        os.chmod(target, mode)
        path.symlink_to(target.name)
        self.assert_rejected("E_FILESYSTEM")
        path.unlink()
        os.link(target, path)
        self.assert_rejected("E_FILESYSTEM")

    def test_16_runner_checker_path_pin_drift_is_rejected(self) -> None:
        path = self.root / checker.RUNNER_PATH
        text = path.read_text(encoding="utf-8").replace(
            checker.CHECKER_PATH,
            "script/wrong_checker.py",
            1,
        )
        path.write_text(text, encoding="utf-8")
        self.assert_rejected("E_TOOL")

    def test_17_runner_checker_hash_pin_drift_is_rejected(self) -> None:
        path = self.root / checker.RUNNER_PATH
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(
            (self.root / checker.CHECKER_PATH).read_bytes()
        ).hexdigest()
        path.write_text(text.replace(digest, "0" * 64, 1), encoding="utf-8")
        self.assert_rejected("E_TOOL")

    def test_18_runner_test_count_drift_is_rejected(self) -> None:
        path = self.root / checker.RUNNER_TEST_PATH
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("    def test_", "    def removed_test_", 1),
            encoding="utf-8",
        )
        self.assert_rejected("E_TOOL")

    def test_19_independent_readback_checker_drift_is_rejected(self) -> None:
        path = self.root / checker.READBACK_CHECKER_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_rejected("E_RAW_BINDING")

    def test_20_independent_readback_tests_drift_is_rejected(self) -> None:
        path = self.root / checker.READBACK_TEST_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        self.assert_rejected("E_RAW_BINDING")

    def test_21_tool_binding_order_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["toolBindings"].reverse()
        )
        self.assert_rejected("E_TOOL")

    def test_22_checker_self_raw_binding_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["toolBindings"][6].update(
                {"rawSha256": "0" * 64}
            )
        )
        self.assert_rejected("E_TOOL")

    def test_23_checker_test_raw_binding_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["toolBindings"][7].update(
                {"rawSha256": "0" * 64}
            )
        )
        self.assert_rejected("E_TOOL")

    def test_24_runner_binding_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["runnerBinding"].update(
                {"rawSha256": "0" * 64}
            )
        )
        self.assert_rejected("E_TOOL")

    def test_25_exact_38_request_count_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["requestContract"].update(
                {"requestCount": 37}
            )
        )
        self.assert_rejected("E_REQUEST")

    def test_26_mod_then_zip_order_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["requestContract"].update(
                {"resourceOrderPerTuple": ["zip", "mod"]}
            )
        )
        self.assert_rejected("E_REQUEST")

    def test_27_derived_mod_url_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["requestContract"]["orderedRequests"][0].update(
                {"url": "https://proxy.golang.org/wrong/@v/v1.0.0.mod"}
            )
        )
        self.assert_rejected("E_REQUEST")

    def test_28_expected_h1_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["requestContract"]["orderedRequests"][1].update(
                {"expectedH1": "h1:" + "A" * 43 + "="}
            )
        )
        self.assert_rejected("E_REQUEST")

    def test_29_absolute_limit_weakening_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["absoluteResourceLimits"].update(
                {"maximumZipResponseBytesPerTuple": 33_554_432}
            )
        )
        self.assert_rejected("E_LIMIT")

    def test_30_acquisition_41_path_set_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["reservedRegularFilePaths"][
                "acquisitionPublication"
            ]["paths"].pop()
        )
        self.assert_rejected("E_RESERVED_PATH")

    def test_31_post_readback_43_count_drift_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["reservedRegularFilePaths"][
                "postReadbackPublication"
            ].update({"count": 42})
        )
        self.assert_rejected("E_RESERVED_PATH")

    def test_32_v1_or_v2_reuse_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["oneUseConsumption"].update(
                {"v1OrV2ArtifactReuseAllowed": True}
            )
        )
        self.assert_rejected("E_ONE_USE")

    def test_33_runtime_network_escalation_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["networkAuthority"].update(
                {"runtimeNetworkAuthorized": True}
            )
        )
        self.assert_rejected("E_AUTHORITY")

    def test_34_false_closure_is_rejected(self) -> None:
        self.mutate_permit(
            lambda value: value["closure"].update(
                {"dependencyClosureComplete": True}
            )
        )
        self.assert_rejected("E_CLOSURE")

    def test_35_final_identity_barrier_detects_mutation(self) -> None:
        path = self.root / checker.PERMIT_PATH

        def mutate_after_first_pass() -> None:
            path.write_bytes(path.read_bytes() + b" ")

        with self.assertRaises(Exception) as context:
            checker.validate_repository(
                self.root,
                before_final_barrier=mutate_after_first_pass,
            )
        self.assertEqual(getattr(context.exception, "code", None), "E_TOCTOU")

    def test_36_coherent_terminal_namespace_is_left_to_runner(self) -> None:
        claim = self.root / checker.V3_CLAIM_PATH
        failure = self.root / checker.V3_FAILURE_PATH
        claim.parent.mkdir(parents=True, exist_ok=True)
        failure.parent.mkdir(parents=True, exist_ok=True)
        claim.write_bytes(b'{"terminal":"claim"}\n')
        failure.write_bytes(b'{"terminal":"failure"}\n')
        os.chmod(claim, 0o600)
        os.chmod(failure, 0o600)
        result = checker.validate_repository(self.root)
        self.assertTrue(result["v3ExecutionAuthorized"])
        self.assertFalse(result["namespaceInitiallyClean"])
        self.assertEqual(result["v3ArtifactKinds"][checker.V3_CLAIM_PATH], "file")
        self.assertEqual(result["v3ArtifactKinds"][checker.V3_FAILURE_PATH], "file")

    def test_37_reader_contract_byte_drift_is_rejected(self) -> None:
        path = self.root / checker.PERMIT_READER_PATH
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_rejected("E_RAW_BINDING")

    def test_38_symlinked_reader_contract_is_rejected(self) -> None:
        path = self.root / checker.PERMIT_READER_PATH
        original = path.read_bytes()
        mode = path.stat().st_mode & 0o777
        path.unlink()
        target = path.with_name(path.name + ".target")
        target.write_bytes(original)
        os.chmod(target, mode)
        path.symlink_to(target.name)
        self.assert_rejected("E_FILESYSTEM")

    def test_39_reader_contract_final_barrier_detects_mutation(self) -> None:
        path = self.root / checker.PERMIT_READER_PATH

        def mutate_after_first_pass() -> None:
            path.write_bytes(path.read_bytes() + b" ")

        with self.assertRaises(Exception) as context:
            checker.validate_repository(
                self.root,
                before_final_barrier=mutate_after_first_pass,
            )
        self.assertEqual(getattr(context.exception, "code", None), "E_TOCTOU")


if __name__ == "__main__":
    unittest.main()
