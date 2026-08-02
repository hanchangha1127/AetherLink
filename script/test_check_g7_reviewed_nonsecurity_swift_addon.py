#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "script/check_g7_reviewed_nonsecurity_swift_addon.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "script.check_g7_reviewed_nonsecurity_swift_addon",
    MODULE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load reviewed Swift add-on checker")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ReviewedNonsecuritySwiftAddonTests(unittest.TestCase):
    def test_current_partition_and_antecedent_pass(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        self.assertIsNotNone(partition)
        assert partition is not None
        self.assertEqual(len(partition.base_new), 311)
        self.assertEqual(len(partition.method_reviewed), 315)
        self.assertEqual(len(partition.runner_reviewed), 711)
        self.assertEqual(len(partition.new), 626)
        self.assertEqual(len(partition.distinct_after_addon), 1023)
        self.assertEqual(len(partition.not_executed), 1150)

    def test_method_manifest_is_exact_and_category_partitioned(self) -> None:
        identities, failures = MODULE.load_reviewed_method_tests()
        self.assertEqual(failures, [])
        self.assertIsNotNone(identities)
        assert identities is not None
        router = tuple(
            identity
            for identity in identities
            if identity.startswith(MODULE.ROUTER_REVIEWED_PREFIX)
        )
        ui = tuple(identity for identity in identities if identity not in set(router))
        self.assertEqual(len(router), 246)
        self.assertEqual(len(ui), 69)
        self.assertEqual(
            MODULE.manifest_sha256(router),
            MODULE.ROUTER_REVIEWED_METHOD_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            MODULE.manifest_sha256(ui),
            MODULE.UI_REVIEWED_METHOD_TEST_MANIFEST_SHA256,
        )

    def test_router_category_same_count_manifest_substitution_fails(self) -> None:
        identities, failures = MODULE.load_reviewed_method_tests()
        self.assertEqual(failures, [])
        assert identities is not None
        values = list(identities)
        router_index = next(
            index
            for index, identity in enumerate(values)
            if identity.startswith(MODULE.ROUTER_REVIEWED_PREFIX)
        )
        values[router_index] = (
            MODULE.ROUTER_REVIEWED_PREFIX + "testSyntheticRouterManifestDrift"
        )
        self._assert_category_manifest_substitution_fails(
            values,
            "reviewed Router method Swift manifest SHA-256 differs",
        )

    def test_ui_category_same_count_manifest_substitution_fails(self) -> None:
        identities, failures = MODULE.load_reviewed_method_tests()
        self.assertEqual(failures, [])
        assert identities is not None
        values = list(identities)
        ui_prefix = next(iter(MODULE.UI_REVIEWED_SUITE_COUNTS))
        ui_index = next(
            index
            for index, identity in enumerate(values)
            if identity.startswith(ui_prefix)
        )
        values[ui_index] = ui_prefix + "testSyntheticUiManifestDrift"
        self._assert_category_manifest_substitution_fails(
            values,
            "reviewed UI method Swift manifest SHA-256 differs",
        )

    def _assert_category_manifest_substitution_fails(
        self,
        identities: list[str],
        expected_failure: str,
    ) -> None:
        canonical_identities = tuple(sorted(identities))
        data = ("\n".join(canonical_identities) + "\n").encode("ascii")
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-addon-manifest-test-",
            dir=build_root,
        ) as temporary:
            manifest_path = Path(temporary) / "identities.txt"
            manifest_path.write_bytes(data)
            with (
                mock.patch.object(MODULE, "REVIEWED_METHOD_PATH", manifest_path),
                mock.patch.object(MODULE, "REVIEWED_METHOD_BYTES", len(data)),
                mock.patch.object(
                    MODULE,
                    "REVIEWED_METHOD_RAW_SHA256",
                    MODULE.hashlib.sha256(data).hexdigest(),
                ),
                mock.patch.object(
                    MODULE,
                    "REVIEWED_METHOD_TEST_MANIFEST_SHA256",
                    MODULE.manifest_sha256(canonical_identities),
                ),
            ):
                observed, failures = MODULE.load_reviewed_method_tests()
        self.assertIsNone(observed)
        self.assertIn(expected_failure, failures)

    def test_runner_selects_exact_new_partition(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        command, environment, failures = MODULE.runner_contract(partition)
        self.assertEqual(failures, [])
        self.assertIsNotNone(command)
        self.assertIsNotNone(environment)
        assert command is not None
        assert environment is not None
        self.assertEqual(command[6], "--no-parallel")
        self.assertEqual(command[7], "--filter")
        self.assertEqual(command[9], "--skip")
        self.assertEqual(command[8], MODULE.runner_include_filter(partition))
        self.assertLessEqual(
            MODULE.command_environment_footprint(command, environment),
            MODULE.COMMAND_AND_ENVIRONMENT_MAX_BYTES,
        )

    def test_runner_rejects_broadened_include_filter(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        with mock.patch.object(MODULE, "COMPANION_REVIEWED_FILTER", r".*"):
            _, _, failures = MODULE.runner_contract(partition)
        self.assertTrue(
            any("include filter differs" in failure for failure in failures)
        )

    def test_runner_rejects_invalid_include_filter(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        with mock.patch.object(MODULE, "COMPANION_REVIEWED_FILTER", r"("):
            _, failures = MODULE.runner_command(partition)
        self.assertTrue(any("regex is invalid" in failure for failure in failures))

    def test_runner_excludes_mixed_suite_nonmanifest_and_lookalikes(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        include_filter = MODULE.runner_include_filter(partition)
        mixed_prefixes = (MODULE.ROUTER_REVIEWED_PREFIX,) + tuple(
            MODULE.UI_REVIEWED_SUITE_COUNTS
        )
        mixed_suite_discovered = {
            identity
            for identity in partition.discovered
            if identity.startswith(mixed_prefixes)
        }
        nonmanifest = mixed_suite_discovered - set(partition.method_reviewed)
        self.assertEqual(len(nonmanifest), 422)
        self.assertTrue(
            all(MODULE.re.search(include_filter, identity) is None for identity in nonmanifest)
        )
        identity = partition.method_reviewed[0]
        self.assertIsNone(MODULE.re.search(include_filter, "Prefix" + identity))
        self.assertIsNone(MODULE.re.search(include_filter, identity + "Suffix"))

    def test_runner_rejects_footprint_one_byte_above_cap(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        command, failures = MODULE.runner_command(partition)
        self.assertEqual(failures, [])
        assert command is not None
        environment, failures = MODULE.product_ci.g7_nonsecurity_swift_environment()
        self.assertEqual(failures, [])
        assert environment is not None
        footprint = MODULE.command_environment_footprint(command, environment)
        with (
            mock.patch.object(
                MODULE,
                "COMMAND_AND_ENVIRONMENT_MAX_BYTES",
                footprint - 1,
            ),
            mock.patch.object(MODULE, "candidate_antecedent_failures", return_value=[]),
            mock.patch.object(
                MODULE.product_ci,
                "g7_nonsecurity_swift_network_sandbox_self_test",
                return_value=[],
            ),
        ):
            observed_command, observed_environment, failures = MODULE.runner_contract(
                partition
            )
        self.assertIsNone(observed_command)
        self.assertIsNone(observed_environment)
        self.assertTrue(any("footprint exceeds" in failure for failure in failures))

    def test_same_count_identity_substitution_fails(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        values = list(partition.discovered)
        values[values.index(partition.new[0])] = (
            "CompanionCoreTests.RuntimeDocumentIndexStoreTests/testMutatedIdentity"
        )
        observed, failures = MODULE.partition_shape_failures(tuple(values))
        self.assertIsNone(observed)
        self.assertTrue(
            any("manifest SHA-256 differs" in failure for failure in failures)
        )

    def test_same_count_method_manifest_substitution_fails(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        values = list(partition.method_reviewed)
        values[0] = partition.not_executed[0]
        observed, failures = MODULE.partition_shape_failures(
            partition.discovered,
            reviewed_methods=tuple(values),
        )
        self.assertIsNone(observed)
        self.assertTrue(
            any(
                "method reviewed Swift manifest SHA-256 differs" in failure
                for failure in failures
            )
        )

    def test_duplicate_identity_fails(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        observed, failures = MODULE.partition_shape_failures(
            partition.discovered + (partition.discovered[0],)
        )
        self.assertIsNone(observed)
        self.assertTrue(any("duplicates" in failure for failure in failures))

    def test_incomplete_delta_projection_fails(self) -> None:
        for omitted in MODULE.ADDON_RELATIVE_PATHS:
            with self.subTest(omitted=omitted):
                failures = MODULE._candidate_antecedent_failures_for_delta(
                    tuple(
                        path
                        for path in MODULE.ADDON_RELATIVE_PATHS
                        if path != omitted
                    )
                )
                self.assertTrue(failures)
                self.assertTrue(
                    any("source snapshot" in failure for failure in failures)
                )

    def test_duplicate_delta_path_fails(self) -> None:
        failures = MODULE._candidate_antecedent_failures_for_delta(
            MODULE.ADDON_RELATIVE_PATHS + (MODULE.ADDON_RELATIVE_PATHS[0],)
        )
        self.assertTrue(any("duplicates" in failure for failure in failures))

    def test_exact_source_membership_and_antecedent_command_ids(self) -> None:
        self.assertEqual(
            MODULE.ADDON_RELATIVE_PATHS,
            (
                Path("script/check_g7_nonsecurity_merge_full_candidate_v2.py"),
                Path("script/check_g7_reviewed_nonsecurity_swift_addon.py"),
                Path("script/g7_reviewed_nonsecurity_swift_addon_identities_v2.txt"),
                Path("script/run_g7_nonsecurity_merge_full_candidate_v2.py"),
                Path("script/test_check_g7_reviewed_nonsecurity_swift_addon.py"),
                Path("script/test_g7_nonsecurity_merge_full_candidate_v2.py"),
            ),
        )
        self.assertEqual(len(MODULE.EXACT_SOURCE_FILES), len(set(MODULE.EXACT_SOURCE_FILES)))
        for relative in MODULE.ADDON_RELATIVE_PATHS:
            self.assertIn(MODULE.ROOT / relative, MODULE.EXACT_SOURCE_FILES)
        self.assertIn(MODULE.ANTECEDENT_PATH, MODULE.EXACT_SOURCE_FILES)
        self.assertIn(MODULE.EXECUTION_CONTRACT_PATH, MODULE.EXACT_SOURCE_FILES)
        antecedent = json.loads(MODULE.ANTECEDENT_PATH.read_bytes())
        command_ids = tuple(command["id"] for command in antecedent["commands"])
        self.assertEqual(len(command_ids), 67)
        self.assertEqual(command_ids, MODULE.antecedent.EXPECTED_COMMAND_IDS)
        self.assertEqual(
            MODULE.OUTPUT_ROOT,
            MODULE.ROOT / ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v2",
        )
        self.assertNotEqual(
            MODULE.OUTPUT_ROOT,
            MODULE.ROOT / ".build/aetherlink-g7-reviewed-nonsecurity-swift-addon-v1",
        )

    def test_boolean_count_is_rejected(self) -> None:
        failures = MODULE.exact_set_failures(
            "fixture",
            ("FixtureTests.Suite/testOne",),
            True,
            MODULE.manifest_sha256(("FixtureTests.Suite/testOne",)),
        )
        self.assertTrue(any("exact integer" in failure for failure in failures))

    def test_run_wrapper_forwards_exact_addon_source_contract(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        expected_tests = partition.new
        with (
            mock.patch.object(
                MODULE.product_ci,
                "swift_focused_test_run_marker_failures",
                return_value=[],
            ) as marker,
            mock.patch.object(
                MODULE.product_ci,
                "swift_focused_test_list_snapshot",
                return_value=({}, expected_tests, []),
            ) as snapshot,
            mock.patch.object(
                MODULE.product_ci,
                "run_and_publish_swift_focused_log",
                return_value=(0, []),
            ) as publish,
        ):
            status, failures = MODULE.run_addon_tests(
                partition,
                ("fixture-command",),
                {"LC_ALL": "C"},
            )
        self.assertEqual((status, failures), (0, []))
        self.assertEqual(marker.call_args.kwargs["exact_files"], MODULE.EXACT_SOURCE_FILES)
        self.assertEqual(marker.call_args.kwargs["excluded_tests"], partition.overlap)
        self.assertEqual(marker.call_args.kwargs["expected_count"], 626)
        self.assertEqual(
            marker.call_args.kwargs["expected_manifest_sha256"],
            MODULE.NEW_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            marker.call_args.kwargs["filter_pattern"],
            MODULE.runner_include_filter(partition),
        )
        self.assertEqual(snapshot.call_args.kwargs["expected_count"], 626)
        self.assertEqual(
            snapshot.call_args.kwargs["expected_manifest_sha256"],
            MODULE.NEW_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(snapshot.call_args.kwargs["excluded_tests"], partition.overlap)
        self.assertEqual(publish.call_args.kwargs["expected_tests"], expected_tests)

    def test_execution_contract_round_trip_and_command_mutation(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        command, environment, failures = MODULE.runner_contract(partition)
        self.assertEqual(failures, [])
        assert command is not None
        assert environment is not None
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-addon-execution-test-",
            dir=build_root,
        ) as temporary:
            contract_path = Path(temporary) / "execution-contract.json"
            with mock.patch.object(MODULE, "EXECUTION_CONTRACT_PATH", contract_path):
                failures = MODULE.write_execution_contract(
                    partition,
                    command,
                    environment,
                )
                self.assertEqual(failures, [])
                document = json.loads(contract_path.read_bytes())
                self.assertEqual(
                    document["contract"],
                    "aetherlink-g7-reviewed-nonsecurity-swift-execution-v2",
                )
                self.assertEqual(
                    document["runtimeExpected"],
                    {
                        "errors": 0,
                        "failures": 0,
                        "skipped": 0,
                        "testcaseManifestSha256": MODULE.NEW_TEST_MANIFEST_SHA256,
                        "tests": 626,
                    },
                )
                self.assertEqual(
                    document["selection"],
                    {
                        "baseNewManifestSha256": MODULE.BASE_NEW_TEST_MANIFEST_SHA256,
                        "baseNewTests": 311,
                        "methodManifestSha256": (
                            MODULE.REVIEWED_METHOD_TEST_MANIFEST_SHA256
                        ),
                        "methodManifestTests": 315,
                        "runnerManifestSha256": (
                            MODULE.RUNNER_REVIEWED_TEST_MANIFEST_SHA256
                        ),
                        "runnerTestsBeforeExclusion": 711,
                    },
                )
                self.assertEqual(
                    document["commandAndEnvironmentBytes"],
                    MODULE.command_environment_footprint(command, environment),
                )
                self.assertEqual(
                    document["commandAndEnvironmentMaximumBytes"],
                    MODULE.COMMAND_AND_ENVIRONMENT_MAX_BYTES,
                )
                document["command"][6] = "--parallel"
                contract_path.write_bytes(MODULE.canonical_json_bytes(document))
                contract_path.chmod(0o600)
                failures = MODULE.execution_contract_failures(
                    partition,
                    command,
                    expected_environment=environment,
                )
        self.assertTrue(
            any("command/profile/selection differs" in failure for failure in failures)
        )

    def test_execution_contract_rejects_stale_v1_test_count(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        command, environment, failures = MODULE.runner_contract(partition)
        self.assertEqual(failures, [])
        assert command is not None
        assert environment is not None
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-addon-stale-execution-test-",
            dir=build_root,
        ) as temporary:
            contract_path = Path(temporary) / "execution-contract.json"
            with mock.patch.object(MODULE, "EXECUTION_CONTRACT_PATH", contract_path):
                failures = MODULE.write_execution_contract(
                    partition,
                    command,
                    environment,
                )
                self.assertEqual(failures, [])
                document = json.loads(contract_path.read_bytes())
                document["runtimeExpected"]["tests"] = 311
                contract_path.write_bytes(MODULE.canonical_json_bytes(document))
                contract_path.chmod(0o600)
                failures = MODULE.execution_contract_failures(
                    partition,
                    command,
                    expected_environment=environment,
                )
        self.assertTrue(
            any("command/profile/selection differs" in failure for failure in failures)
        )

    def test_result_readback_rejects_mutated_canonical_document(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        expected = {
            "contract": "fixture-add-on-result",
            "result": "passed",
            "schemaVersion": 1,
        }
        mutated = json.loads(MODULE.canonical_json_bytes(expected))
        mutated["result"] = "failed"
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-addon-result-test-",
            dir=build_root,
        ) as temporary:
            result_path = Path(temporary) / "result.json"
            result_path.write_bytes(MODULE.canonical_json_bytes(mutated))
            result_path.chmod(0o600)
            with (
                mock.patch.object(MODULE, "RESULT_PATH", result_path),
                mock.patch.object(
                    MODULE,
                    "candidate_antecedent_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    MODULE.product_ci,
                    "swift_focused_test_binding_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    MODULE,
                    "runner_command",
                    return_value=(("fixture-command",), []),
                ),
                mock.patch.object(
                    MODULE,
                    "execution_contract_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    MODULE,
                    "result_payload",
                    return_value=(expected, []),
                ),
            ):
                failures = MODULE.result_failures(partition)
        self.assertTrue(
            any("exactly bind current evidence" in failure for failure in failures)
        )

    def test_result_payload_pins_v2_counts_and_review_kinds(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        def fixture_record(path: Path, *, maximum_bytes: int) -> dict[str, object]:
            self.assertGreater(maximum_bytes, 0)
            return {
                "bytes": 1,
                "mode": 0o600,
                "path": path.relative_to(MODULE.ROOT).as_posix(),
                "sha256": "0" * 64,
            }

        with mock.patch.object(MODULE, "stable_record", side_effect=fixture_record):
            payload, failures = MODULE.result_payload(partition)
        self.assertEqual(failures, [])
        assert payload is not None
        self.assertEqual(payload["contract"], "aetherlink-g7-reviewed-nonsecurity-swift-addon-v2")
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(
            set(payload["artifacts"]),
            {
                "antecedent",
                "binding",
                "console",
                "executionContract",
                "reviewedMethodManifest",
                "runMarker",
                "testList",
            },
        )
        self.assertEqual(
            payload["artifacts"]["reviewedMethodManifest"]["path"],
            MODULE.REVIEWED_METHOD_RELATIVE_PATH.as_posix(),
        )
        expected_partition = {
            "antecedent": (397, MODULE.ANTECEDENT_TEST_MANIFEST_SHA256),
            "discovered": (2173, MODULE.DISCOVERED_TEST_MANIFEST_SHA256),
            "distinctAfterAddon": (
                1023,
                MODULE.DISTINCT_AFTER_ADDON_MANIFEST_SHA256,
            ),
            "newExecuted": (626, MODULE.NEW_TEST_MANIFEST_SHA256),
            "notExecuted": (1150, MODULE.NOT_EXECUTED_TEST_MANIFEST_SHA256),
            "reviewedAllowlist": (958, MODULE.REVIEWED_TEST_MANIFEST_SHA256),
        }
        for key, (tests, manifest_sha256) in expected_partition.items():
            self.assertEqual(payload["partition"][key]["tests"], tests)
            self.assertEqual(
                payload["partition"][key]["manifestSha256"],
                manifest_sha256,
            )
        review_kinds = payload["partition"]["newExecutedByReviewKind"]
        self.assertEqual(review_kinds["suiteReviewed"]["tests"], 311)
        self.assertEqual(review_kinds["exactMethods"]["tests"], 315)
        self.assertEqual(
            review_kinds["suiteReviewed"]["manifestSha256"],
            MODULE.BASE_NEW_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            review_kinds["exactMethods"]["manifestSha256"],
            MODULE.REVIEWED_METHOD_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            payload["scope"]["exactMethodReviewedRouterTests"],
            246,
        )
        self.assertEqual(
            payload["scope"][
                "exactMethodReviewedUiAccessibilityLocalizationRenderTests"
            ],
            69,
        )
        self.assertTrue(all(value is False for value in payload["limitations"].values()))

    def test_result_readback_rejects_stale_v1_partition_counts(self) -> None:
        partition, failures = MODULE.contract_inputs()
        self.assertEqual(failures, [])
        assert partition is not None
        record = {
            "bytes": 1,
            "mode": 0o600,
            "path": "fixture",
            "sha256": "0" * 64,
        }
        with mock.patch.object(MODULE, "stable_record", return_value=record):
            expected, failures = MODULE.result_payload(partition)
        self.assertEqual(failures, [])
        assert expected is not None
        stale = json.loads(MODULE.canonical_json_bytes(expected))
        stale["partition"]["newExecuted"]["tests"] = 311
        stale["partition"]["distinctAfterAddon"]["tests"] = 708
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-addon-stale-result-test-",
            dir=build_root,
        ) as temporary:
            result_path = Path(temporary) / "result.json"
            result_path.write_bytes(MODULE.canonical_json_bytes(stale))
            result_path.chmod(0o600)
            with (
                mock.patch.object(MODULE, "RESULT_PATH", result_path),
                mock.patch.object(
                    MODULE,
                    "candidate_antecedent_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    MODULE.product_ci,
                    "swift_focused_test_binding_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    MODULE,
                    "runner_command",
                    return_value=(("fixture-command",), []),
                ),
                mock.patch.object(
                    MODULE,
                    "execution_contract_failures",
                    return_value=[],
                ),
                mock.patch.object(
                    MODULE,
                    "result_payload",
                    return_value=(expected, []),
                ),
            ):
                failures = MODULE.result_failures(partition)
        self.assertTrue(
            any("exactly bind current evidence" in failure for failure in failures)
        )


if __name__ == "__main__":
    unittest.main()
