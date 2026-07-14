#!/usr/bin/env python3
"""Mutation tests for the Phase A libjuice compile-only contract validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from script import check_p2p_nat_libjuice_compile_only as CHECKER


ROOT = Path(__file__).resolve().parents[1]


def replace_once(raw, old, new):
    before, separator, after = raw.partition(old)
    if not separator:
        raise AssertionError("replacement marker missing")
    return before + new + after


class LibjuiceCompileOnlyContractMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = CHECKER.load_json(CHECKER.ARTIFACT_JSON_PATH)

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.LibjuiceCompileOnlyValidationError):
            CHECKER.validate_document(candidate)

    def test_canonical_blocked_state_returns_success_without_compilation(self) -> None:
        status = self.canonical["currentStatus"]
        self.assertEqual("blocked_missing_reviewed_source", status["android_macos_compile_only_integration"])
        self.assertEqual("not_executed", status["executionStatus"])
        self.assertEqual("absent", status["evidenceStatus"])
        self.assertEqual([], status["compilationEvidence"])
        CHECKER.validate_source_documents()
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_owned_python_ast()
        CHECKER.validate_artifact_hashes()
        self.assertEqual(0, CHECKER.main())

    def test_duplicate_keys_nonstandard_numbers_and_invalid_json_fail(self) -> None:
        raw = CHECKER.ARTIFACT_JSON_PATH.read_text(encoding="utf-8")
        duplicate_root = replace_once(
            raw,
            '  "schemaVersion": "1.0",',
            '  "schemaVersion": "2.0",\n  "schemaVersion": "1.0",',
        )
        duplicate_nested = replace_once(
            raw,
            '    "executionStatus": "not_executed",',
            '    "executionStatus": "executed",\n    "executionStatus": "not_executed",',
        )
        for candidate in (duplicate_root, duplicate_nested, '{"value": NaN}', '{"value": Infinity}', "{"):
            with self.subTest(candidate=candidate[:48]):
                with self.assertRaises(CHECKER.LibjuiceCompileOnlyValidationError):
                    CHECKER.parse_json(candidate, "mutation")

    def test_top_level_exact_keys_identifiers_and_types_are_closed(self) -> None:
        self.assert_rejected(lambda value: value.pop("abiBoundary"))
        self.assert_rejected(lambda value: value.update({"runtime": {}}))
        for key, mutation in (
            ("documentType", "other"),
            ("schemaVersion", 1.0),
            ("contractId", "v2"),
            ("profileId", "other"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation: value.update({key: mutation})
                )

    def test_approval_references_and_hash_pins_reject_any_drift(self) -> None:
        for parent, key, mutation in (
            ("sourceReview", "path", "review-v2.json"),
            ("sourceReview", "reviewId", "other"),
            ("sourceReview", "sha256", "0" * 64),
            ("sourceDecision", "path", "decision-v2.json"),
            ("sourceDecision", "decisionId", "other"),
            ("sourceDecision", "sha256", "1" * 64),
            ("sourceHandoff", "path", "handoff-v3.json"),
            ("sourceHandoff", "handoffId", "other"),
            ("sourceHandoff", "sha256", "f" * 64),
        ):
            with self.subTest(parent=parent, key=key):
                self.assert_rejected(
                    lambda value, parent=parent, key=key, mutation=mutation:
                    value[parent].update({key: mutation})
                )
        for path, expected in CHECKER.SOURCE_SHA256.items():
            raw = path.read_bytes()
            self.assertEqual(expected, CHECKER.hash_bytes(raw))
            with self.assertRaises(CHECKER.LibjuiceCompileOnlyValidationError):
                CHECKER.validate_bytes_hash(raw + b"\n", expected, path.name)

    def test_offline_intake_is_future_link_only_and_untrusted_now(self) -> None:
        intake = self.canonical["offlineSourceIntake"]
        self.assertEqual("offline-source-intake-v1.json", intake["path"])
        self.assertEqual(
            "production_p2p_nat_v1_phase_a_libjuice_offline_source_intake_v1",
            intake["artifactId"],
        )
        self.assertEqual(CHECKER.SOURCE_SHA256[CHECKER.OFFLINE_INTAKE_PATH], intake["sha256"])
        self.assertEqual("blocked_missing_offline_source", intake["currentDeclaredStatus"])
        self.assertEqual("absent", intake["sourcePresence"])
        self.assertEqual("not_started", intake["auditStatus"])
        self.assertEqual("not_started", intake["compileStatus"])
        self.assertIs(True, intake["linkedArtifactPresent"])
        for key, mutation in (
            ("path", "other.json"),
            ("artifactId", "other"),
            ("sha256", "0" * 64),
            ("requiredBeforeReviewedManifest", False),
            ("currentDeclaredStatus", "ready"),
            ("sourcePresence", "present"),
            ("auditStatus", "complete"),
            ("compileStatus", "passed"),
            ("linkedArtifactPresent", False),
            ("linkedArtifactPresent", 1),
            ("linkageRule", "link_in_place"),
        ):
            with self.subTest(key=key, mutation=mutation):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["offlineSourceIntake"].update({key: mutation})
                )

    def test_current_status_cannot_claim_execution_or_evidence(self) -> None:
        for key, mutation in (
            ("android_macos_compile_only_integration", "passed"),
            ("executionStatus", "executed"),
            ("evidenceStatus", "present"),
            ("compilationEvidence", [{"target": "arm64"}]),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["currentStatus"].update({key: mutation})
                )
        for key, expected in CHECKER.EXPECTED_CURRENT_STATUS["recordedEnvironmentSnapshot"].items():
            mutation = not expected
            if key in {"recordedAt", "scope"}:
                mutation = "drifted"
            with self.subTest(observation=key, case="value"):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["currentStatus"]["recordedEnvironmentSnapshot"].update({key: mutation})
                )
            if type(expected) is bool:
                with self.subTest(observation=key, case="integer-confusion"):
                    self.assert_rejected(
                        lambda value, key=key, expected=expected:
                        value["currentStatus"]["recordedEnvironmentSnapshot"].update({
                            key: int(expected)
                        })
                    )

    def test_authorization_has_exact_true_contract_gates_and_false_execution_gates(self) -> None:
        true_keys = {
            key for key, expected in CHECKER.EXPECTED_AUTHORIZATION.items() if expected is True
        }
        false_keys = {
            key for key, expected in CHECKER.EXPECTED_AUTHORIZATION.items() if expected is False
        }
        self.assertEqual(
            {"contractDefinitionAuthorized", "compileOnlyIntegrationAuthorizedByApprovalChain"},
            true_keys,
        )
        self.assertEqual(13, len(false_keys))
        for key in true_keys:
            for mutation in (False, 1, None, "true"):
                with self.subTest(key=key, mutation=mutation):
                    self.assert_rejected(
                        lambda value, key=key, mutation=mutation:
                        value["authorization"].update({key: mutation})
                    )
        for key in false_keys:
            for mutation in (True, 0, None, "false"):
                with self.subTest(key=key, mutation=mutation):
                    self.assert_rejected(
                        lambda value, key=key, mutation=mutation:
                        value["authorization"].update({key: mutation})
                    )
        self.assert_rejected(lambda value: value["authorization"].update({"networkAllowed": False}))

    def test_reviewed_source_manifest_requires_exact_ordered_no_glob_inputs(self) -> None:
        prerequisite = self.canonical["reviewedSourceManifestPrerequisite"]
        self.assertEqual(CHECKER.EXPECTED_MANIFEST_KEYS, prerequisite["manifestMustPinExactKeys"])
        for index, key in enumerate(CHECKER.EXPECTED_MANIFEST_KEYS):
            with self.subTest(required_pin=key):
                self.assert_rejected(
                    lambda value, index=index:
                    value["reviewedSourceManifestPrerequisite"]["manifestMustPinExactKeys"].pop(index)
                )
        for key, mutation in (
            ("required", False),
            ("currentStatus", "reviewed"),
            ("approvalRequiredBeforeCompilation", False),
            ("sourceDiscovery", "glob"),
            ("globDiscoveryAllowed", True),
            ("directoryScanDiscoveryAllowed", True),
            ("implicitSourceFilesAllowed", True),
            ("implicitBuildDefinesAllowed", True),
            ("manifestHashRequired", False),
            ("independentReviewRequired", False),
            ("failureRule", "continue"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["reviewedSourceManifestPrerequisite"].update({key: mutation})
                )

    def test_future_procedure_is_direct_compile_archive_nm_and_never_executes(self) -> None:
        contract = self.canonical["futureCompilationContract"]
        self.assertEqual("direct_compile_each_exact_source_then_static_archive", contract["strategy"])
        self.assertEqual(
            "nm_over_static_archive_without_loading_or_executing_code",
            contract["symbolInspection"],
        )
        false_keys = {
            key for key, expected in CHECKER.EXPECTED_FUTURE_COMPILATION.items()
            if expected is False
        }
        self.assertEqual(16, len(false_keys))
        for key in false_keys:
            for mutation in (True, 0, None, "false"):
                with self.subTest(key=key, mutation=mutation):
                    self.assert_rejected(
                        lambda value, key=key, mutation=mutation:
                        value["futureCompilationContract"].update({key: mutation})
                    )
        for key, mutation in (
            ("strategy", "cmake_build"),
            ("compileInvocation", "compile_and_link"),
            ("archiveInvocation", "shared_library"),
            ("sourceOrder", "glob_order"),
            ("buildDefines", "defaults_allowed"),
            ("failureRule", "download_fallback"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["futureCompilationContract"].update({key: mutation})
                )

    def test_android_matrix_requires_min_sdk_26_two_abis_and_exact_ndk_tools(self) -> None:
        android = self.canonical["platformMatrix"]["android"]
        self.assertEqual(26, android["minimumSdk"])
        self.assertEqual(["arm64-v8a", "x86_64"], [item["abi"] for item in android["abis"]])
        for mutation in (25, 27, 26.0, True):
            with self.subTest(minimum_sdk=mutation):
                self.assert_rejected(
                    lambda value, mutation=mutation:
                    value["platformMatrix"]["android"].update({"minimumSdk": mutation})
                )
        self.assert_rejected(lambda value: value["platformMatrix"]["android"]["abis"].pop())
        self.assert_rejected(lambda value: value["platformMatrix"]["android"]["abis"].reverse())
        self.assert_rejected(
            lambda value: value["platformMatrix"]["android"]["abis"][0].update({
                "targetTriple": "aarch64-linux-android27"
            })
        )
        for index, pin in enumerate(CHECKER.EXPECTED_ANDROID["requiredExactPins"]):
            with self.subTest(pin=pin):
                self.assert_rejected(
                    lambda value, index=index:
                    value["platformMatrix"]["android"]["requiredExactPins"].pop(index)
                )

    def test_macos_matrix_requires_14_two_architectures_and_exact_tool_sdk_hashes(self) -> None:
        macos = self.canonical["platformMatrix"]["macos"]
        self.assertEqual("14.0", macos["minimumDeploymentTarget"])
        self.assertEqual(
            ["arm64", "x86_64"],
            [item["architecture"] for item in macos["architectures"]],
        )
        for mutation in (14.0, "13.0", "15.0", None):
            with self.subTest(target=mutation):
                self.assert_rejected(
                    lambda value, mutation=mutation:
                    value["platformMatrix"]["macos"].update({"minimumDeploymentTarget": mutation})
                )
        self.assert_rejected(lambda value: value["platformMatrix"]["macos"]["architectures"].pop())
        self.assert_rejected(lambda value: value["platformMatrix"]["macos"]["architectures"].reverse())
        for index, pin in enumerate(CHECKER.EXPECTED_MACOS["requiredExactPins"]):
            with self.subTest(pin=pin):
                self.assert_rejected(
                    lambda value, index=index:
                    value["platformMatrix"]["macos"]["requiredExactPins"].pop(index)
                )
        self.assert_rejected(
            lambda value: value["platformMatrix"].update({"crossPlatformRule": "per_platform_abi"})
        )

    def test_abi_boundary_rejects_ownership_threading_error_and_authority_drift(self) -> None:
        self.assertEqual(10, len(CHECKER.EXPECTED_EXPORTS))
        for key in (
            "opaqueHandleRule", "fixedWidthIntegerRule", "bufferRule", "numericEndpointRule",
            "allocatorOwnershipRule", "callbackThreadingRule", "cancellationRule", "teardownRule",
            "errorRule", "symbolVisibilityRule", "routeTokenBoundaryRule",
            "applicationPayloadBoundaryRule",
        ):
            with self.subTest(rule=key):
                self.assert_rejected(lambda value, key=key: value["abiBoundary"].pop(key))
        for key in ("routeTokenAuthorityAllowed", "applicationPayloadAuthorityAllowed"):
            for mutation in (True, 0, None, "false"):
                with self.subTest(key=key, mutation=mutation):
                    self.assert_rejected(
                        lambda value, key=key, mutation=mutation:
                        value["abiBoundary"].update({key: mutation})
                    )
        for index, symbol in enumerate(CHECKER.EXPECTED_EXPORTS):
            with self.subTest(symbol=symbol):
                self.assert_rejected(
                    lambda value, index=index: value["abiBoundary"]["exactExportAllowlist"].pop(index)
                )
        self.assert_rejected(
            lambda value: value["abiBoundary"]["exactExportAllowlist"].append("juice_create")
        )

    def test_outputs_are_only_objects_archives_nm_and_content_free_digests(self) -> None:
        policy = self.canonical["outputPolicy"]
        self.assertEqual(CHECKER.EXPECTED_ALLOWED_OUTPUTS, policy["allowedArtifactClasses"])
        self.assertEqual(CHECKER.EXPECTED_LOG_KEYS, policy["contentFreeLogExactKeys"])
        for index, artifact_class in enumerate(CHECKER.EXPECTED_ALLOWED_OUTPUTS):
            with self.subTest(artifact_class=artifact_class):
                self.assert_rejected(
                    lambda value, index=index: value["outputPolicy"]["allowedArtifactClasses"].pop(index)
                )
        for index, key in enumerate(CHECKER.EXPECTED_LOG_KEYS):
            with self.subTest(log_key=key):
                self.assert_rejected(
                    lambda value, index=index: value["outputPolicy"]["contentFreeLogExactKeys"].pop(index)
                )
        for key, expected in CHECKER.EXPECTED_OUTPUT_POLICY.items():
            if expected is False:
                with self.subTest(prohibition=key):
                    self.assert_rejected(
                        lambda value, key=key: value["outputPolicy"].update({key: True})
                    )
        self.assert_rejected(
            lambda value: value["outputPolicy"]["allowedArtifactClasses"].append("executable")
        )
        for mutation in (256, 255.0, True):
            with self.subTest(maximum_exit_code=mutation):
                self.assert_rejected(
                    lambda value, mutation=mutation:
                    value["outputPolicy"].update({"maximumExitCode": mutation})
                )

    def test_fake_artifacts_and_in_place_transition_remain_prohibited(self) -> None:
        for index, artifact in enumerate(CHECKER.EXPECTED_PROHIBITED_ARTIFACTS):
            with self.subTest(artifact=artifact):
                self.assert_rejected(
                    lambda value, index=index: value["prohibitedRepositoryArtifacts"].pop(index)
                )
        for index, requirement in enumerate(CHECKER.EXPECTED_TRANSITION["blockedStateExitRequires"]):
            with self.subTest(requirement=requirement):
                self.assert_rejected(
                    lambda value, index=index:
                    value["transitionPolicy"]["blockedStateExitRequires"].pop(index)
                )
        for key in (
            "inPlaceStatusMutationAllowed", "fallbackDownloadAllowed",
            "fallbackLibrarySelectionAllowed", "phaseBUnlockAllowed", "productionUnlockAllowed",
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key: value["transitionPolicy"].update({key: True})
                )

    def test_json_and_markdown_hashes_are_exactly_pinned(self) -> None:
        for path, expected in CHECKER.ARTIFACT_SHA256.items():
            raw = path.read_bytes()
            self.assertEqual(expected, CHECKER.hash_bytes(raw))
            with self.assertRaises(CHECKER.LibjuiceCompileOnlyValidationError):
                CHECKER.validate_bytes_hash(raw + b"\n", expected, path.name)
        self.assert_rejected(lambda value: value["immutability"].update({"recordState": "open"}))
        self.assert_rejected(lambda value: value["immutability"]["coveredArtifacts"].pop())

    def test_ast_scanner_rejects_process_network_native_and_dynamic_capabilities(self) -> None:
        forbidden_sources = (
            "import socket\nsocket.socket()\n",
            "import socket as channel\nchannel.socket()\n",
            "from socket import create_connection as connect\nconnect(('127.0.0.1', 9))\n",
            "import subprocess\nsubprocess.run(['true'])\n",
            "from subprocess import Popen as launch\nlaunch(['true'])\n",
            "import os\nos.system('true')\n",
            "from os import system as invoke\ninvoke('true')\n",
            "import urllib.request\nurllib.request.urlopen('https://example.invalid')\n",
            "import http.client\nhttp.client.HTTPConnection('example.invalid')\n",
            "import requests\nrequests.get('https://example.invalid')\n",
            "import ctypes\nctypes.CDLL('library')\n",
            "import _socket\n_socket.socket()\n",
            "import _posixsubprocess\n_posixsubprocess.fork_exec()\n",
            "import shutil\nshutil.unpack_archive('source.tar.gz', 'source')\n",
            "from pathlib import os\nos.execl('/bin/true', 'true')\nos.remove('source')\n",
            "from pathlib import Path\nPath('source').replace('moved')\n",
            "from pathlib import Path\nraw = Path('source')\nraw.replace('moved')\n",
            "from script import unreviewed_helper\n",
            "from pathlib import Path\nPath('x').write_text('payload')\n",
            "import importlib\nimportlib.import_module('socket')\n",
            "import builtins\nbuiltins.__import__('socket')\n",
            "__import__('socket')\n",
            "eval('1 + 1')\n",
            "exec('value = 1')\n",
            "compile('value = 1', '<dynamic>', 'exec')\n",
            "getattr(object(), 'field')\n",
            "setattr(object(), 'field', 1)\n",
            "globals()['__builtins__']\n",
            "sys.modules['socket']\n",
            "runner.run(['true'])\n",
            "client.urlopen('https://example.invalid')\n",
            "loader.CDLL('library')\n",
        )
        for index, raw in enumerate(forbidden_sources):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.LibjuiceCompileOnlyValidationError):
                    CHECKER.validate_ast_source(raw, f"mutation-{index}.py")
        CHECKER.validate_ast_source(
            "import ast\nimport hashlib\nimport json\nfrom pathlib import Path\n"
            "value = hashlib.sha256(b'x').hexdigest()\n",
            "static-only.py",
        )

    def test_recursive_exact_rejects_bool_int_and_int_float_confusion(self) -> None:
        for actual, expected in (
            (False, 0), (0, False), (1, True), (True, 1), (26.0, 26), (255.0, 255)
        ):
            with self.subTest(actual=actual, expected=expected):
                with self.assertRaises(CHECKER.LibjuiceCompileOnlyValidationError):
                    CHECKER.recursive_exact(actual, expected, "type-confusion")

    def test_json_round_trip_preserves_the_exact_contract(self) -> None:
        round_trip = json.loads(json.dumps(self.canonical))
        CHECKER.validate_document(round_trip)


if __name__ == "__main__":
    unittest.main()
