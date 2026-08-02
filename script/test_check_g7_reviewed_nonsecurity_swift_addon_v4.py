#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "script/check_g7_reviewed_nonsecurity_swift_addon_v4.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "script.check_g7_reviewed_nonsecurity_swift_addon_v4",
    MODULE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load reviewed Swift V4 add-on checker")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ReviewedNonsecuritySwiftAddonV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.partition, failures = MODULE.contract_inputs()
        if failures or cls.partition is None:
            raise AssertionError(f"current V4 contract inputs failed: {failures}")

    def test_current_partition_is_complete_and_exact(self) -> None:
        partition = self.partition
        self.assertEqual(len(partition.discovered), 2_173)
        self.assertEqual(len(partition.antecedent_distinct), 1_120)
        self.assertEqual(len(partition.reviewed_input), 1_053)
        self.assertEqual(len(partition.selected), 53)
        self.assertEqual(len(partition.excluded_by_scope), 913)
        self.assertEqual(len(partition.excluded_external), 87)
        self.assertEqual(len(partition.remaining), 1_000)
        self.assertEqual(len(partition.distinct_after_addon), 1_173)
        self.assertEqual(
            set(partition.selected)
            | set(partition.excluded_by_scope)
            | set(partition.excluded_external),
            set(partition.reviewed_input),
        )
        self.assertFalse(set(partition.selected) & set(partition.antecedent_distinct))

    def test_manifest_raw_bytes_sorting_and_identity_hash_are_exact(self) -> None:
        identities, failures = MODULE.load_reviewed_tests()
        self.assertEqual(failures, [])
        self.assertIsNotNone(identities)
        assert identities is not None
        raw = MODULE.REVIEWED_IDENTITY_PATH.read_bytes()
        self.assertEqual(len(raw), MODULE.REVIEWED_IDENTITY_BYTES)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"\r", raw)
        self.assertEqual(tuple(sorted(identities)), identities)
        self.assertEqual(len(set(identities)), 53)
        self.assertEqual(
            MODULE.manifest_sha256(identities),
            MODULE.NEW_TEST_MANIFEST_SHA256,
        )

    def test_manifest_wrong_mode_and_symlink_are_rejected(self) -> None:
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-v4-manifest-test-",
            dir=build_root,
        ) as temporary:
            root = Path(temporary)
            physical = root / "manifest.txt"
            physical.write_bytes(MODULE.REVIEWED_IDENTITY_PATH.read_bytes())
            physical.chmod(0o600)
            with mock.patch.object(MODULE, "REVIEWED_IDENTITY_PATH", physical):
                identities, failures = MODULE.load_reviewed_tests()
            self.assertIsNone(identities)
            self.assertTrue(any("mode must be 0644" in item for item in failures))

            physical.chmod(0o644)
            link = root / "manifest-link.txt"
            link.symlink_to(physical)
            with mock.patch.object(MODULE, "REVIEWED_IDENTITY_PATH", link):
                identities, failures = MODULE.load_reviewed_tests()
            self.assertIsNone(identities)
            self.assertTrue(any("single-link regular file" in item for item in failures))

            hard_link = root / "manifest-hard-link.txt"
            os.link(physical, hard_link)
            with mock.patch.object(MODULE, "REVIEWED_IDENTITY_PATH", hard_link):
                identities, failures = MODULE.load_reviewed_tests()
            self.assertIsNone(identities)
            self.assertTrue(any("single-link regular file" in item for item in failures))

    def test_selected_module_counts_are_exact(self) -> None:
        for prefix, expected in MODULE.SELECTED_MODULE_COUNTS.items():
            with self.subTest(prefix=prefix):
                self.assertEqual(
                    sum(
                        identity.startswith(prefix)
                        for identity in self.partition.selected
                    ),
                    expected,
                )
        self.assertEqual(sum(MODULE.SELECTED_MODULE_COUNTS.values()), 53)
        self.assertEqual(sum(MODULE.SELECTED_CLASS_COUNTS.values()), 53)

    def test_result_class_counts_reject_boolean_integer_alias(self) -> None:
        mutated_counts = dict(MODULE.SELECTED_CLASS_COUNTS)
        mutated_counts["LocalRuntimeMessageRouterTests"] = True
        test_config = replace(
            MODULE.CONFIG,
            selected_class_counts=mutated_counts,
            candidate_antecedent_failures=lambda: [],
        )
        failures = MODULE.engine.selection_count_failures(
            test_config,
            self.partition,
        )
        self.assertTrue(any("exact-integer" in item for item in failures), failures)
        with (
            mock.patch.object(MODULE, "CONFIG", test_config),
            mock.patch.object(
                MODULE.product_ci,
                "g7_nonsecurity_swift_network_sandbox_self_test",
                return_value=[],
            ),
        ):
            command, environment, failures = MODULE.runner_contract(self.partition)
            self.assertIsNone(command)
            self.assertIsNone(environment)
            self.assertTrue(any("exact-integer" in item for item in failures))
            payload, failures = MODULE.result_payload(self.partition)
            self.assertIsNone(payload)
            self.assertTrue(any("exact-integer" in item for item in failures))

    def test_external_and_scope_classification_hashes_are_exact(self) -> None:
        discovered, failures = MODULE.addon_v3.addon_v2.load_discovered_tests()
        self.assertEqual(failures, [])
        assert discovered is not None
        antecedent, failures = MODULE.reconstruct_v3_partition(discovered)
        self.assertEqual(failures, [])
        assert antecedent is not None
        external = antecedent.excluded_external
        self.assertEqual(external, self.partition.excluded_external)
        self.assertEqual(
            MODULE.manifest_sha256(external),
            MODULE.EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            MODULE.manifest_sha256(self.partition.excluded_by_scope),
            MODULE.EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            MODULE.manifest_sha256(self.partition.remaining),
            MODULE.REMAINING_TEST_MANIFEST_SHA256,
        )

    def test_exact_regex_selects_only_the_53_identities(self) -> None:
        pattern = MODULE.exact_filter(self.partition.selected)
        selected = tuple(
            identity
            for identity in self.partition.discovered
            if re.search(pattern, identity)
        )
        self.assertEqual(selected, self.partition.selected)
        first = self.partition.selected[0]
        self.assertIsNone(re.search(pattern, first + "Lookalike"))
        self.assertIsNone(re.search(pattern, "Prefix" + first))

    def test_runner_is_serial_network_denied_exact_and_bounded(self) -> None:
        command, failures = MODULE.runner_command(self.partition)
        self.assertEqual(failures, [])
        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(
            command[:8],
            (
                "/usr/bin/sandbox-exec",
                "-p",
                "(version 1)(allow default)(deny network*)",
                "/usr/bin/swift",
                "test",
                "--disable-sandbox",
                "--no-parallel",
                "--filter",
            ),
        )
        self.assertNotIn("--skip", command)
        environment, failures = MODULE.product_ci.g7_nonsecurity_swift_environment()
        self.assertEqual(failures, [])
        assert environment is not None
        self.assertLessEqual(
            MODULE.command_environment_footprint(command, environment),
            MODULE.COMMAND_AND_ENVIRONMENT_MAX_BYTES,
        )

    def test_runner_contract_rejects_one_byte_smaller_footprint_bound(self) -> None:
        command, failures = MODULE.runner_command(self.partition)
        self.assertEqual(failures, [])
        assert command is not None
        environment, failures = MODULE.product_ci.g7_nonsecurity_swift_environment()
        self.assertEqual(failures, [])
        assert environment is not None
        footprint = MODULE.command_environment_footprint(command, environment)
        bounded_config = replace(
            MODULE.CONFIG,
            command_and_environment_max_bytes=footprint - 1,
            candidate_antecedent_failures=lambda: [],
        )
        with (
            mock.patch.object(MODULE, "CONFIG", bounded_config),
            mock.patch.object(
                MODULE.product_ci,
                "g7_nonsecurity_swift_network_sandbox_self_test",
                return_value=[],
            ),
        ):
            observed_command, observed_environment, failures = MODULE.runner_contract(
                self.partition
            )
        self.assertIsNone(observed_command)
        self.assertIsNone(observed_environment)
        self.assertTrue(any("footprint exceeds" in failure for failure in failures))

    def test_output_directory_symlink_and_open_mode_are_rejected(self) -> None:
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-v4-directory-test-",
            dir=build_root,
        ) as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir(mode=0o700)
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            failures = MODULE.physical_output_directory_failures(
                link,
                create=False,
            )
            self.assertTrue(any("physical directory" in item for item in failures))

            open_directory = root / "open"
            open_directory.mkdir(mode=0o755)
            open_directory.chmod(0o755)
            failures = MODULE.physical_output_directory_failures(
                open_directory,
                create=False,
            )
            self.assertTrue(any("mode must be 0700" in item for item in failures))

    def test_same_count_selected_identity_substitution_fails(self) -> None:
        discovered, failures = MODULE.addon_v3.addon_v2.load_discovered_tests()
        self.assertEqual(failures, [])
        assert discovered is not None
        antecedent, failures = MODULE.reconstruct_v3_partition(discovered)
        self.assertEqual(failures, [])
        assert antecedent is not None
        values = list(self.partition.selected)
        values[0] = self.partition.excluded_by_scope[0]
        observed, failures = MODULE.partition_shape_failures(
            discovered,
            antecedent,
            selected=tuple(sorted(values)),
        )
        self.assertIsNone(observed)
        self.assertTrue(any("manifest SHA-256 differs" in failure for failure in failures))

    def test_duplicate_selected_identity_fails(self) -> None:
        discovered, failures = MODULE.addon_v3.addon_v2.load_discovered_tests()
        self.assertEqual(failures, [])
        assert discovered is not None
        antecedent, failures = MODULE.reconstruct_v3_partition(discovered)
        self.assertEqual(failures, [])
        assert antecedent is not None
        observed, failures = MODULE.partition_shape_failures(
            discovered,
            antecedent,
            selected=self.partition.selected + (self.partition.selected[0],),
        )
        self.assertIsNone(observed)
        self.assertTrue(any("sorted and unique" in failure for failure in failures))

    def test_antecedent_candidate_and_exact_three_file_delta_pass(self) -> None:
        self.assertEqual(MODULE.candidate_antecedent_failures(), [])
        self.assertEqual(
            MODULE.ADDON_RELATIVE_PATHS,
            (
                Path("script/check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
                Path("script/g7_nonsecurity_swift_successor_engine.py"),
                Path("script/test_check_g7_reviewed_nonsecurity_swift_addon_v4.py"),
            ),
        )
        self.assertEqual(len(MODULE.EXACT_SOURCE_FILES), len(set(MODULE.EXACT_SOURCE_FILES)))
        for relative in MODULE.ADDON_RELATIVE_PATHS:
            self.assertIn(MODULE.ROOT / relative, MODULE.EXACT_SOURCE_FILES)
        self.assertIn(MODULE.ANTECEDENT_PATH, MODULE.EXACT_SOURCE_FILES)
        self.assertIn(MODULE.REVIEWED_IDENTITY_PATH, MODULE.EXACT_SOURCE_FILES)
        self.assertIn(MODULE.EXECUTION_CONTRACT_PATH, MODULE.EXACT_SOURCE_FILES)
        self.assertEqual(
            MODULE.CANDIDATE_INTEGRATION_RELATIVE_PATHS,
            (
                Path("script/check_g7_nonsecurity_merge_full_candidate_v4.py"),
                Path("script/run_g7_nonsecurity_merge_full_candidate_v4.py"),
                Path("script/test_g7_nonsecurity_merge_full_candidate_v4.py"),
            ),
        )
        self.assertEqual(len(MODULE.ANTECEDENT_PROJECTION_RELATIVE_PATHS), 6)
        self.assertEqual(
            set(MODULE.ANTECEDENT_PROJECTION_RELATIVE_PATHS),
            set(MODULE.ADDON_RELATIVE_PATHS)
            | set(MODULE.CANDIDATE_INTEGRATION_RELATIVE_PATHS),
        )
        for relative in MODULE.CANDIDATE_INTEGRATION_RELATIVE_PATHS:
            self.assertNotIn(MODULE.ROOT / relative, MODULE.EXACT_SOURCE_FILES)

    def test_every_incomplete_or_duplicate_delta_is_rejected(self) -> None:
        for omitted in MODULE.ANTECEDENT_PROJECTION_RELATIVE_PATHS:
            with self.subTest(omitted=omitted):
                failures = MODULE._candidate_antecedent_failures_for_delta(
                    tuple(
                        path
                        for path in MODULE.ANTECEDENT_PROJECTION_RELATIVE_PATHS
                        if path != omitted
                    )
                )
                self.assertTrue(
                    any("source snapshot" in failure for failure in failures),
                    failures,
                )
        failures = MODULE._candidate_antecedent_failures_for_delta(
            MODULE.ANTECEDENT_PROJECTION_RELATIVE_PATHS
            + (MODULE.ANTECEDENT_PROJECTION_RELATIVE_PATHS[0],)
        )
        self.assertTrue(any("duplicates" in failure for failure in failures))
        failures = MODULE._candidate_antecedent_failures_for_delta(
            MODULE.ANTECEDENT_PROJECTION_RELATIVE_PATHS
            + (Path("script/check_product_ci.py"),)
        )
        self.assertTrue(any("source snapshot" in failure for failure in failures))

    def test_boolean_count_is_rejected(self) -> None:
        failures = MODULE.exact_set_failures(
            "fixture",
            ("FixtureTests.Suite/testOne",),
            True,
            MODULE.manifest_sha256(("FixtureTests.Suite/testOne",)),
        )
        self.assertTrue(any("exact integer" in failure for failure in failures))

    def test_run_wrapper_forwards_exact_source_and_no_exclusions(self) -> None:
        expected_tests = self.partition.selected
        with (
            mock.patch.object(
                MODULE.engine,
                "physical_output_directory_failures",
                return_value=[],
            ),
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
                self.partition,
                ("fixture-command",),
                {"LC_ALL": "C"},
            )
        self.assertEqual((status, failures), (0, []))
        self.assertEqual(marker.call_args.kwargs["exact_files"], MODULE.EXACT_SOURCE_FILES)
        self.assertEqual(marker.call_args.kwargs["excluded_tests"], ())
        self.assertEqual(marker.call_args.kwargs["expected_count"], 53)
        self.assertEqual(snapshot.call_args.kwargs["excluded_tests"], ())
        self.assertEqual(publish.call_args.kwargs["expected_tests"], expected_tests)

    def test_execution_contract_round_trip_and_mutations(self) -> None:
        command, failures = MODULE.runner_command(self.partition)
        self.assertEqual(failures, [])
        assert command is not None
        environment, failures = MODULE.product_ci.g7_nonsecurity_swift_environment()
        self.assertEqual(failures, [])
        assert environment is not None
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-v4-execution-test-",
            dir=build_root,
        ) as temporary:
            contract_path = Path(temporary) / "execution-contract.json"
            test_config = replace(
                MODULE.CONFIG,
                execution_contract_path=contract_path,
            )
            with mock.patch.object(MODULE, "CONFIG", test_config):
                failures = MODULE.write_execution_contract(
                    self.partition,
                    command,
                    environment,
                )
                self.assertEqual(failures, [])
                document = json.loads(contract_path.read_bytes())
                self.assertEqual(document["contract"], MODULE.EXECUTION_CONTRACT)
                self.assertEqual(document["runtimeExpected"]["tests"], 53)
                self.assertEqual(document["filterExcluded"], 0)
                for field, value in (
                    ("tests", 52),
                    ("tests", True),
                    ("testcaseManifestSha256", "0" * 64),
                ):
                    with self.subTest(field=field, value=value):
                        mutated = json.loads(MODULE.canonical_json_bytes(document))
                        mutated["runtimeExpected"][field] = value
                        contract_path.write_bytes(MODULE.canonical_json_bytes(mutated))
                        contract_path.chmod(0o600)
                        observed = MODULE.execution_contract_failures(
                            self.partition,
                            command,
                            expected_environment=environment,
                        )
                        self.assertTrue(
                            any("command/profile/selection differs" in item for item in observed),
                            observed,
                        )
                contract_path.write_bytes(MODULE.canonical_json_bytes(document))
                contract_path.chmod(0o600)
                self.assertEqual(
                    MODULE.execution_contract_failures(
                        self.partition,
                        command,
                        expected_environment=environment,
                    ),
                    [],
                )

    def test_result_payload_pins_v4_partition_and_limitations(self) -> None:
        def fixture_record(
            _config: object,
            path: Path,
            *,
            maximum_bytes: int,
        ) -> dict[str, object]:
            self.assertGreater(maximum_bytes, 0)
            return {
                "bytes": 1,
                "mode": (
                    0o644
                    if path == MODULE.REVIEWED_IDENTITY_PATH
                    else 0o600
                ),
                "path": path.relative_to(MODULE.ROOT).as_posix(),
                "sha256": "0" * 64,
            }

        with (
            mock.patch.object(MODULE.engine, "stable_record", side_effect=fixture_record),
            mock.patch.object(
                MODULE.engine,
                "physical_output_directory_failures",
                return_value=[],
            ),
        ):
            payload, failures = MODULE.result_payload(self.partition)
        self.assertEqual(failures, [])
        assert payload is not None
        self.assertEqual(payload["contract"], MODULE.CONTRACT)
        self.assertEqual(payload["schemaVersion"], 1)
        expected = {
            "antecedentDistinct": (1_120, MODULE.ANTECEDENT_DISTINCT_TEST_MANIFEST_SHA256),
            "discovered": (2_173, MODULE.DISCOVERED_TEST_MANIFEST_SHA256),
            "distinctAfterAddon": (1_173, MODULE.DISTINCT_AFTER_ADDON_TEST_MANIFEST_SHA256),
            "excludedByScope": (913, MODULE.EXCLUDED_BY_SCOPE_TEST_MANIFEST_SHA256),
            "excludedExternal": (87, MODULE.EXCLUDED_EXTERNAL_TEST_MANIFEST_SHA256),
            "newExecuted": (53, MODULE.NEW_TEST_MANIFEST_SHA256),
            "remaining": (1_000, MODULE.REMAINING_TEST_MANIFEST_SHA256),
            "reviewedInput": (1_053, MODULE.REVIEWED_INPUT_TEST_MANIFEST_SHA256),
        }
        for key, (tests, digest) in expected.items():
            self.assertEqual(payload["partition"][key]["tests"], tests)
            self.assertEqual(payload["partition"][key]["manifestSha256"], digest)
        self.assertEqual(payload["scope"]["unclassifiedTests"], 0)
        self.assertTrue(all(value is False for value in payload["limitations"].values()))

    def test_result_payload_rejects_non_private_runtime_artifact_mode(self) -> None:
        def fixture_record(
            _config: object,
            path: Path,
            *,
            maximum_bytes: int,
        ) -> dict[str, object]:
            del maximum_bytes
            mode = 0o644 if path == MODULE.REVIEWED_IDENTITY_PATH else 0o600
            if path == MODULE.BINDING_PATH:
                mode = 0o644
            return {
                "bytes": 1,
                "mode": mode,
                "path": path.relative_to(MODULE.ROOT).as_posix(),
                "sha256": "0" * 64,
            }

        with (
            mock.patch.object(MODULE.engine, "stable_record", side_effect=fixture_record),
            mock.patch.object(
                MODULE.engine,
                "physical_output_directory_failures",
                return_value=[],
            ),
        ):
            payload, failures = MODULE.result_payload(self.partition)
        self.assertIsNone(payload)
        self.assertTrue(any("artifact mode differs: binding" in item for item in failures))

    def test_result_readback_rejects_stale_count_hash_and_boolean(self) -> None:
        record = {
            "bytes": 1,
            "mode": 0o600,
            "path": "fixture",
            "sha256": "0" * 64,
        }
        def fixture_record(
            _config: object,
            path: Path,
            *,
            maximum_bytes: int,
        ) -> dict[str, object]:
            del maximum_bytes
            return {
                **record,
                "mode": (
                    0o644
                    if path == MODULE.REVIEWED_IDENTITY_PATH
                    else 0o600
                ),
            }

        with (
            mock.patch.object(MODULE.engine, "stable_record", side_effect=fixture_record),
            mock.patch.object(
                MODULE.engine,
                "physical_output_directory_failures",
                return_value=[],
            ),
        ):
            expected, failures = MODULE.result_payload(self.partition)
        self.assertEqual(failures, [])
        assert expected is not None
        mutations = (
            ("count", lambda value: value["partition"]["newExecuted"].__setitem__("tests", 52)),
            ("hash", lambda value: value["partition"]["newExecuted"].__setitem__("manifestSha256", "0" * 64)),
            ("boolean", lambda value: value["partition"]["newExecuted"].__setitem__("tests", True)),
        )
        build_root = MODULE.ROOT / ".build"
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-v4-result-test-",
            dir=build_root,
        ) as temporary:
            result_path = Path(temporary) / "result.json"
            for label, mutate in mutations:
                with self.subTest(label=label):
                    stale = json.loads(MODULE.canonical_json_bytes(expected))
                    mutate(stale)
                    result_path.write_bytes(MODULE.canonical_json_bytes(stale))
                    result_path.chmod(0o600)
                    test_config = replace(
                        MODULE.CONFIG,
                        result_path=result_path,
                        candidate_antecedent_failures=lambda: [],
                    )
                    with (
                        mock.patch.object(MODULE, "CONFIG", test_config),
                        mock.patch.object(
                            MODULE.product_ci,
                            "swift_focused_test_binding_failures",
                            return_value=[],
                        ),
                        mock.patch.object(
                            MODULE.engine,
                            "runner_command",
                            return_value=(("fixture-command",), []),
                        ),
                        mock.patch.object(
                            MODULE.engine,
                            "execution_contract_failures",
                            return_value=[],
                        ),
                        mock.patch.object(
                            MODULE.engine,
                            "result_payload",
                            return_value=(expected, []),
                        ),
                    ):
                        observed = MODULE.result_failures(self.partition)
                    self.assertTrue(
                        any("exactly bind current evidence" in item for item in observed),
                        observed,
                    )


if __name__ == "__main__":
    unittest.main()
