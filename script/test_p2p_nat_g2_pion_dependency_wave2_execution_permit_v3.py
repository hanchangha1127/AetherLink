#!/usr/bin/env python3
"""Offline regression tests for the wave-two execution permit checker."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    ROOT
    / "script/check_p2p_nat_g2_pion_dependency_wave2_execution_permit_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave2_permit_checker_tests_target",
    CHECKER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)
COMMON = CHECKER.COMMON


class WaveTwoPermitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = CHECKER.print_expected(ROOT)

    def rebound(self, value: dict) -> dict:
        payload = copy.deepcopy(value)
        payload.pop("contentBinding", None)
        value["contentBinding"] = {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": "permit_without_contentBinding",
            "sha256": COMMON.sha256_bytes(
                COMMON.canonical_json_bytes(payload)
            ),
        }
        return value

    def mutate(self, callback) -> dict:
        value = copy.deepcopy(self.expected)
        callback(value)
        return self.rebound(value)

    def assert_rejected(self, value: dict) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.validate_permit_document(value, self.expected)

    def test_01_expected_permit_is_valid(self) -> None:
        CHECKER.validate_permit_document(self.expected, self.expected)
        binding = self.expected["decisionBinding"]
        self.assertEqual(
            binding["orderedResourceSetSha256"],
            COMMON.EXPECTED_V3_ORDERED_RESOURCE_SET_SHA256,
        )
        self.assertNotEqual(
            binding["sourceOrderedResourceSetSha256"],
            binding["orderedResourceSetSha256"],
        )
        self.assertEqual(
            self.expected["recoveryDecisionBinding"][
                "v1RevocationSentinelRawSha256"
            ],
            COMMON.EXPECTED_V1_REVOCATION_SENTINEL_RAW_SHA256,
        )

    def test_02_exact_request_count(self) -> None:
        self.assertEqual(self.expected["requestContract"]["requestCount"], 30)
        self.assertEqual(
            len(self.expected["requestContract"]["orderedRequests"]),
            30,
        )

    def test_03_exact_tuple_count(self) -> None:
        self.assertEqual(self.expected["requestContract"]["tupleCount"], 15)

    def test_04_ordinals_are_exact(self) -> None:
        rows = self.expected["requestContract"]["orderedRequests"]
        self.assertEqual(
            [row["requestOrdinal"] for row in rows],
            list(range(1, 31)),
        )

    def test_05_each_tuple_is_mod_then_zip(self) -> None:
        rows = self.expected["requestContract"]["orderedRequests"]
        self.assertEqual(
            [row["resourceKind"] for row in rows],
            ["mod", "zip"] * 15,
        )

    def test_06_selected_false_tuples_are_preserved(self) -> None:
        rows = self.expected["requestContract"]["orderedRequests"]
        self.assertEqual(
            sum(not row["selectedByGraphAlgorithm"] for row in rows),
            20,
        )

    def test_07_request_reorder_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"]["orderedRequests"].reverse()
            )
        )

    def test_08_request_removal_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"]["orderedRequests"].pop()
            )
        )

    def test_09_mod_zip_swap_is_rejected(self) -> None:
        def mutation(document):
            rows = document["requestContract"]["orderedRequests"]
            rows[0], rows[1] = rows[1], rows[0]
        self.assert_rejected(self.mutate(mutation))

    def test_10_url_query_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"]["orderedRequests"][0].__setitem__(
                    "url",
                    d["requestContract"]["orderedRequests"][0]["url"] + "?x=1",
                )
            )
        )

    def test_11_alternate_host_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"]["orderedRequests"][0].__setitem__(
                    "url",
                    d["requestContract"]["orderedRequests"][0]["url"].replace(
                        "proxy.golang.org",
                        "example.invalid",
                    ),
                )
            )
        )

    def test_12_h1_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"]["orderedRequests"][0].__setitem__(
                    "expectedH1",
                    "h1:" + "A" * 44,
                )
            )
        )

    def test_13_output_name_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"]["orderedRequests"][0].__setitem__(
                    "outputFileName",
                    "foreign.mod",
                )
            )
        )

    def test_14_redirect_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"].__setitem__(
                    "redirectAllowed",
                    True,
                )
            )
        )

    def test_15_retry_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"].__setitem__(
                    "retryAllowed",
                    True,
                )
            )
        )

    def test_16_ambient_proxy_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"].__setitem__(
                    "ambientProxyAllowed",
                    True,
                )
            )
        )

    def test_17_credentials_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["requestContract"].__setitem__(
                    "credentialsAllowed",
                    True,
                )
            )
        )

    def test_18_user_action_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["personalProjectBoundary"].__setitem__(
                    "userActionRequired",
                    True,
                )
            )
        )

    def test_19_external_auth_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["personalProjectBoundary"].__setitem__(
                    "externalAuthenticationRequired",
                    True,
                )
            )
        )

    def test_20_owner_proof_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["personalProjectBoundary"].__setitem__(
                    "repositoryOwnerIdentityProofRequired",
                    True,
                )
            )
        )

    def test_21_runtime_network_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["networkAuthority"].__setitem__(
                    "runtimeNetworkAuthorized",
                    True,
                )
            )
        )

    def test_22_source_extraction_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["filesystemWriteAuthority"].__setitem__(
                    "sourceExtractionAuthorized",
                    True,
                )
            )
        )

    def test_23_request_limit_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["absoluteResourceLimits"].__setitem__(
                    "maximumRequestCount",
                    31,
                )
            )
        )

    def test_24_aggregate_limit_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["absoluteResourceLimits"].__setitem__(
                    "maximumAggregateResponseBytes",
                    67_108_865,
                )
            )
        )

    def test_25_historical_ratio_is_non_gating_and_exact(self) -> None:
        self.assertNotIn(
            "maximumCompressionRatio",
            self.expected["absoluteResourceLimits"],
        )
        zip_contract = self.expected["resourceValidationContract"]["zip"]
        self.assertEqual(
            zip_contract["compressionRatioPolicy"],
            "non_gating_bounded_telemetry",
        )
        self.assertFalse(zip_contract["compressionRatioRejectionAllowed"])
        self.assert_rejected(
            self.mutate(
                lambda d: d["resourceValidationContract"]["zip"].__setitem__(
                    "historicalV2ComparisonRatio",
                    201,
                )
            )
        )

    def test_26_counter_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["counterContract"]["successValues"].__setitem__(
                    "networkRequestAttemptCount",
                    29,
                )
            )
        )

    def test_27_claim_path_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["oneUseConsumption"].__setitem__(
                    "claimPath",
                    "foreign",
                )
            )
        )

    def test_28_second_execution_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["oneUseConsumption"].__setitem__(
                    "secondExecutionAllowed",
                    True,
                )
            )
        )

    def test_29_readback_network_escalation_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["independentReadbackContract"].__setitem__(
                    "networkAllowed",
                    True,
                )
            )
        )

    def test_30_fixed_point_promotion_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["closure"].__setitem__(
                    "graphFixedPointReached",
                    True,
                )
            )
        )

    def test_31_tool_binding_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["toolBindings"][0].__setitem__(
                    "rawSha256",
                    "0" * 64,
                )
            )
        )

    def test_32_root_identity_drift_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(
                lambda d: d["repositoryRootIdentity"].__setitem__(
                    "inode",
                    d["repositoryRootIdentity"]["inode"] + 1,
                )
            )
        )

    def test_33_reserved_path_count_is_exact(self) -> None:
        reserved = self.expected["reservedRegularFilePaths"]
        self.assertEqual(reserved["acquisitionPublication"]["count"], 33)
        self.assertEqual(len(reserved["acquisitionPublication"]["paths"]), 33)
        self.assertEqual(reserved["postReadbackPublication"]["count"], 35)
        self.assertEqual(len(reserved["postReadbackPublication"]["paths"]), 35)

    def test_34_unknown_top_level_key_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d.__setitem__("unexpected", False))
        )

    def test_35_nonclaim_removal_is_rejected(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["nonClaims"].pop())
        )

    def test_36_stale_content_binding_is_rejected(self) -> None:
        value = copy.deepcopy(self.expected)
        value["status"] = "drift"
        self.assert_rejected(value)

    def test_37_duplicate_json_key_is_rejected(self) -> None:
        raw = COMMON.canonical_json_bytes(self.expected)
        raw = raw.replace(
            b'"schemaVersion":"1.0"',
            b'"schemaVersion":"1.0","schemaVersion":"1.0"',
            1,
        )
        with self.assertRaises(COMMON.Wave2Failure):
            COMMON.strict_json(raw)

    def test_38_nan_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            COMMON.strict_json(b'{"x":NaN}\\n')

    def test_39_checker_is_read_only_and_offline(self) -> None:
        tree = ast.parse(CHECKER_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "http",
                    "requests",
                    "socket",
                    "subprocess",
                    "urllib",
                }
            )
        )

    def test_40_checker_has_no_write_or_process_calls(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("write_text(", source)
        self.assertNotIn("write_bytes(", source)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("subprocess.", source)

    def test_41_actual_permit_and_namespace_preflight(self) -> None:
        checked = CHECKER.validate_repository(
            ROOT,
            require_clean_namespace=True,
        )
        self.assertTrue(checked["executionAuthorized"])
        self.assertEqual(checked["requestCount"], 30)
        self.assertFalse(checked["externalAuthenticationRequired"])
        self.assertFalse(checked["userActionRequired"])
        self.assertEqual(
            set(checked["repositoryRootIdentity"]),
            {"device", "inode", "uid", "mode"},
        )

    def test_42_v2_consumed_terminal_is_directly_bound(self) -> None:
        terminal = self.expected["consumedV2TerminalBinding"]
        self.assertEqual(
            terminal["claim"]["rawSha256"],
            COMMON.EXPECTED_V2_CLAIM_RAW_SHA256,
        )
        self.assertEqual(
            terminal["failureReceipt"]["rawSha256"],
            COMMON.EXPECTED_V2_FAILURE_RECEIPT_RAW_SHA256,
        )
        self.assertEqual(
            terminal["failureReceipt"]["failureCode"],
            "E_ZIP_COMPRESSION_RATIO",
        )
        self.assertFalse(terminal["v2RunnerExecuteAllowed"])
        self.assertFalse(terminal["v2PermitReuseAllowed"])
        self.assertFalse(terminal["v2PartialResumeAllowed"])

    def test_43_deadline_and_telemetry_contracts_are_explicit(self) -> None:
        validation = self.expected["resourceValidationContract"]
        self.assertTrue(validation["zipInspectionUnderWholeWaveHardDeadline"])
        self.assertTrue(
            validation["prepublicationInventoryUnderWholeWaveHardDeadline"]
        )
        self.assertTrue(
            validation["postPublicationVerificationUnderWholeWaveHardDeadline"]
        )
        readback = self.expected["independentReadbackContract"]
        self.assertTrue(readback["recomputeCompressionTelemetryExactly"])
        self.assertTrue(readback["compressionTelemetryIsNonGating"])

    def test_44_all_runner_and_readback_reverse_pin_drifts_are_rejected(
        self,
    ) -> None:
        base = {
            CHECKER.THIS_CHECKER_PATH: (
                ROOT / CHECKER.THIS_CHECKER_PATH
            ).read_bytes(),
            CHECKER.RUNNER_PATH: (ROOT / CHECKER.RUNNER_PATH).read_bytes(),
            CHECKER.READBACK_CHECKER_PATH: (
                ROOT / CHECKER.READBACK_CHECKER_PATH
            ).read_bytes(),
        }

        class FakeInputs:
            def __init__(self, values):
                self.values = values

            def raw(self, path):
                return self.values[path]

        for path, expected in (
            (
                CHECKER.RUNNER_PATH,
                CHECKER.EXPECTED_COMMON_RAW_SHA256,
            ),
            (
                CHECKER.RUNNER_PATH,
                COMMON.sha256_bytes(base[CHECKER.THIS_CHECKER_PATH]),
            ),
            (
                CHECKER.READBACK_CHECKER_PATH,
                CHECKER.EXPECTED_COMMON_RAW_SHA256,
            ),
            (
                CHECKER.READBACK_CHECKER_PATH,
                COMMON.sha256_bytes(base[CHECKER.THIS_CHECKER_PATH]),
            ),
        ):
            values = dict(base)
            source = values[path].decode("utf-8", errors="strict")
            self.assertEqual(source.count(f'"{expected}"'), 1)
            values[path] = source.replace(
                f'"{expected}"',
                f'"{"0" * 64}"',
                1,
            ).encode()
            with self.subTest(path=path, expected=expected):
                with self.assertRaises(COMMON.Wave2Failure) as caught:
                    CHECKER.validate_runner_reverse_pins(
                        FakeInputs(values)
                    )
                self.assertEqual(caught.exception.code, "E_REVERSE_BINDING")

    def test_45_repository_validation_invokes_reverse_pin_gate(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        function = source[
            source.index("def validate_repository("):
            source.index("def print_expected(")
        ]
        self.assertEqual(
            function.count("validate_runner_reverse_pins(inputs)"),
            1,
        )

    def test_46_full_transitive_v1_authority_is_held(self) -> None:
        actual = {
            binding["path"]: binding
            for binding in CHECKER.preparation_bindings(
                include_permit=True,
            )
        }
        expected_paths = {
            row["path"]
            for row in (
                *CHECKER.RECOVERY_V1_CHECKER_BOOTSTRAP.V1_BINDINGS,
                *CHECKER.V1_PERMIT_CHECKER_BOOTSTRAP.preparation_bindings(
                    include_permit=True,
                ),
            )
        }
        self.assertTrue(expected_paths.issubset(actual))
        for path, expected_sha256 in (
            (
                CHECKER.RECOVERY_CHECKER_PATH,
                CHECKER.EXPECTED_RECOVERY_CHECKER_RAW_SHA256,
            ),
            (
                CHECKER.V2_PERMIT_CHECKER_PATH,
                CHECKER.EXPECTED_V2_PERMIT_CHECKER_RAW_SHA256,
            ),
            (
                CHECKER.RECOVERY_V1_CHECKER_PATH,
                CHECKER.EXPECTED_RECOVERY_V1_CHECKER_RAW_SHA256,
            ),
            (
                CHECKER.V1_PERMIT_CHECKER_PATH,
                CHECKER.EXPECTED_V1_PERMIT_CHECKER_RAW_SHA256,
            ),
        ):
            self.assertEqual(
                actual[path].get("rawSha256"),
                expected_sha256,
            )


if __name__ == "__main__":
    unittest.main()
