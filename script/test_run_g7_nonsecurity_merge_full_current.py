from __future__ import annotations

import re
import tempfile
import unittest
from unittest import mock

from script import run_g7_nonsecurity_merge_full_current as current


class CurrentRunPartitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.partition, cls.failures = current.reconstruct_partition()

    def require_partition(self) -> current.CurrentRunPartition:
        self.assertEqual(self.failures, [])
        self.assertIsNotNone(self.partition)
        return self.partition  # type: ignore[return-value]

    def test_partition_matches_reviewed_union(self) -> None:
        partition = self.require_partition()
        self.assertEqual(len(partition.discovered), 2_175)
        self.assertEqual(len(partition.historical_discovered), 2_173)
        self.assertEqual(len(partition.focused), 218)
        self.assertEqual(len(partition.expanded), 247)
        self.assertEqual(len(partition.base_distinct), 393)
        self.assertEqual(len(partition.v2_new), 626)
        self.assertEqual(len(partition.v2_current_new), 628)
        self.assertEqual(len(partition.v3_new), 97)
        self.assertEqual(len(partition.v4_new), 53)
        self.assertEqual(len(partition.v5_new), 26)
        self.assertEqual(len(partition.v6_new), 7)
        self.assertEqual(len(partition.v7_new), 1)
        self.assertEqual(len(partition.current_additions), 2)
        self.assertEqual(len(partition.local_socket_excluded), 4)
        self.assertEqual(len(partition.selected), 1_205)
        self.assertEqual(len(partition.not_executed), 970)
        self.assertEqual(
            current.manifest_sha256(partition.selected),
            current.SELECTED_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            current.manifest_sha256(partition.not_executed),
            current.NOT_EXECUTED_TEST_MANIFEST_SHA256,
        )

    def test_additive_components_are_disjoint_and_complete(self) -> None:
        partition = self.require_partition()
        components = (
            set(partition.base_distinct),
            set(partition.v2_new),
            set(partition.v3_new),
            set(partition.v4_new),
            set(partition.v5_new),
            set(partition.v6_new),
            set(partition.v7_new),
            set(partition.current_additions),
        )
        for index, left in enumerate(components):
            for right in components[index + 1 :]:
                self.assertFalse(left & right)
        self.assertEqual(set().union(*components), set(partition.selected))
        self.assertEqual(
            set(partition.v2_current_new),
            set(partition.v2_new) | set(partition.current_additions),
        )
        self.assertEqual(
            len(set(partition.focused) & set(partition.expanded)),
            current.FOCUSED_EXPANDED_OVERLAP_COUNT,
        )

    def test_local_socket_boundary_is_exact_and_not_selected(self) -> None:
        partition = self.require_partition()
        exclusions = set(current.LOCAL_SOCKET_EXCLUSION_IDENTITIES)
        historical_focused = {
            identity
            for identity in partition.discovered
            if re.search(current.product_ci.SWIFT_FILTER, identity)
        }
        self.assertEqual(
            historical_focused - set(partition.focused),
            exclusions,
        )
        self.assertTrue(exclusions <= set(partition.not_executed))
        self.assertFalse(exclusions & set(partition.selected))
        self.assertEqual(
            current.manifest_sha256(tuple(sorted(exclusions))),
            current.LOCAL_SOCKET_EXCLUSION_TEST_MANIFEST_SHA256,
        )

    def test_parent_adds_only_exact_local_socket_contribution(self) -> None:
        partition = self.require_partition()
        parent, failures = current.parent_partition(partition)
        self.assertEqual(failures, [])
        self.assertIsNotNone(parent)
        parent = parent or {}
        self.assertEqual(len(parent["focusedCarrier"]), 222)
        self.assertEqual(len(parent["focusedCarrierOverlap"]), 218)
        self.assertEqual(len(parent["localSocketExecuted"]), 4)
        self.assertEqual(len(parent["noSocketExecuted"]), 1_205)
        self.assertEqual(len(parent["reviewedExecuted"]), 1_209)
        self.assertEqual(len(parent["remaining"]), 966)
        self.assertEqual(
            current.manifest_sha256(parent["reviewedExecuted"]),
            current.PARENT_REVIEWED_TEST_MANIFEST_SHA256,
        )
        self.assertEqual(
            current.manifest_sha256(parent["remaining"]),
            current.PARENT_REMAINING_TEST_MANIFEST_SHA256,
        )
        self.assertFalse(
            set(parent["localSocketExecuted"])
            & set(parent["noSocketExecuted"])
        )
        self.assertEqual(
            set(parent["reviewedExecuted"]) | set(parent["remaining"]),
            set(partition.discovered),
        )

    def test_parent_payload_keeps_canonical_exit_claims_false(self) -> None:
        partition = self.require_partition()
        payload, failures = current.compose_parent_payload(
            partition,
            artifacts={"fixture": {}},
            focused_source_inputs={"count": 1, "sha256": "a" * 64},
            no_socket_source_inputs={"count": 1, "sha256": "b" * 64},
        )
        self.assertEqual(failures, [])
        self.assertIsNotNone(payload)
        payload = payload or {}
        limitations = payload["limitations"]
        self.assertTrue(limitations["localSocketExecutionClaimed"])
        self.assertFalse(limitations["externalNetworkDeniedClaimed"])
        self.assertFalse(limitations["completeSwiftSuiteClaimed"])
        self.assertFalse(limitations["canonicalMergeFullClaimed"])
        self.assertFalse(limitations["canonicalG7ExitClaimed"])
        self.assertIs(type(payload["schemaVersion"]), int)
        self.assertIs(
            type(payload["execution"]["childSwiftInvocations"]),
            int,
        )

    def test_combined_filter_selects_union_once_without_skip(self) -> None:
        partition = self.require_partition()
        command, failures = current.command_and_filter_failures(partition)
        self.assertEqual(failures, [])
        self.assertIsNotNone(command)
        command = command or ()
        self.assertNotIn("--skip", command)
        self.assertEqual(command[:4], (
            "/usr/bin/sandbox-exec",
            "-p",
            "(version 1)(allow default)(deny network*)",
            "/usr/bin/swift",
        ))
        selected = tuple(
            sorted(
                identity
                for identity in partition.discovered
                if re.search(command[-1], identity)
            )
        )
        self.assertEqual(selected, partition.selected)
        self.assertLessEqual(
            len(command[-1].encode("utf-8")),
            current.FILTER_MAX_BYTES,
        )

    def test_broad_filter_mutation_is_rejected(self) -> None:
        partition = self.require_partition()
        with mock.patch.object(current, "combined_filter", return_value=r".*"):
            command, failures = current.command_and_filter_failures(partition)
        self.assertIsNone(command)
        self.assertTrue(any("exact reviewed union" in failure for failure in failures))

    def test_filter_max_plus_one_is_rejected(self) -> None:
        partition = self.require_partition()
        with mock.patch.object(
            current,
            "combined_filter",
            return_value="x" * (current.FILTER_MAX_BYTES + 1),
        ):
            command, failures = current.command_and_filter_failures(partition)
        self.assertIsNone(command)
        self.assertTrue(any("byte bound" in failure for failure in failures))

    def test_execution_contract_records_exact_types_and_footprint(self) -> None:
        partition = self.require_partition()
        command, failures = current.command_and_filter_failures(partition)
        self.assertEqual(failures, [])
        self.assertIsNotNone(command)
        environment = {"LANG": "C", "LC_ALL": "C"}
        payload = current.execution_contract_payload(
            partition,
            command or (),
            environment,
        )
        self.assertIs(type(payload["schemaVersion"]), int)
        self.assertIs(type(payload["singleSwiftInvocation"]), bool)
        self.assertIs(type(payload["networkDenyProbePassed"]), bool)
        self.assertEqual(payload["commandAndEnvironmentBytes"], current.command_environment_footprint(command or (), environment))
        selection = payload["selection"]
        self.assertIsInstance(selection, dict)
        self.assertEqual(selection["selected"]["tests"], 1_205)  # type: ignore[index]
        self.assertEqual(selection["notExecuted"]["tests"], 970)  # type: ignore[index]
        self.assertEqual(selection["localSocketExcluded"]["tests"], 4)  # type: ignore[index]
        self.assertEqual(selection["currentV2Delta"]["tests"], 2)  # type: ignore[index]
        self.assertEqual(selection["v2CurrentNew"]["tests"], 628)  # type: ignore[index]
        self.assertEqual(selection["v5New"]["tests"], 26)  # type: ignore[index]
        self.assertEqual(selection["v6New"]["tests"], 7)  # type: ignore[index]
        self.assertEqual(selection["v7New"]["tests"], 1)  # type: ignore[index]

    def test_discovery_order_exception_does_not_weaken_selected_order(self) -> None:
        partition = self.require_partition()
        self.assertNotEqual(partition.discovered, tuple(sorted(partition.discovered)))
        self.assertEqual(
            current.exact_set_failures(
                "discovery",
                partition.discovered,
                2_175,
                current.DISCOVERED_TEST_MANIFEST_SHA256,
                require_sorted=False,
            ),
            [],
        )
        self.assertTrue(
            any(
                "sorted" in failure
                for failure in current.exact_set_failures(
                    "discovery",
                    partition.discovered,
                    2_175,
                    current.DISCOVERED_TEST_MANIFEST_SHA256,
                )
            )
        )
        self.assertEqual(partition.selected, tuple(sorted(partition.selected)))

    def test_current_namespace_does_not_overwrite_historical_candidates(self) -> None:
        relative_paths = {
            path.relative_to(current.ROOT).as_posix()
            for path in (
                current.EXECUTION_CONTRACT_PATH,
                current.RUN_MARKER_PATH,
                current.CONSOLE_PATH,
                current.BINDING_PATH,
                current.RESULT_PATH,
                current.PARENT_RESULT_PATH,
            )
        }
        self.assertEqual(len(relative_paths), 6)
        self.assertTrue(
            all("merge-full-current-run-v1" in path for path in relative_paths)
        )
        self.assertTrue(all("candidate-v" not in path for path in relative_paths))

    def test_source_binding_includes_both_implementations_and_tests(self) -> None:
        relative_paths = set(current.TRACKED_EXACT_SOURCE_RELATIVE_PATHS)
        self.assertIn(
            current.Path("script/run_g7_nonsecurity_merge_full_current.py"),
            relative_paths,
        )
        self.assertIn(
            current.Path("script/check_g7_nonsecurity_merge_full_current.py"),
            relative_paths,
        )
        self.assertIn(
            current.Path("script/test_run_g7_nonsecurity_merge_full_current.py"),
            relative_paths,
        )
        self.assertIn(
            current.Path("script/test_check_g7_nonsecurity_merge_full_current.py"),
            relative_paths,
        )
        self.assertIn(current.V5_IDENTITY_RELATIVE_PATH, relative_paths)
        self.assertIn(current.V6_IDENTITY_RELATIVE_PATH, relative_paths)
        self.assertIn(current.V7_IDENTITY_RELATIVE_PATH, relative_paths)

    def test_v5_manifest_is_exact_and_inside_the_prior_parent_remainder(self) -> None:
        partition = self.require_partition()
        identities, failures = current.load_v5_tests()
        self.assertEqual(failures, [])
        self.assertEqual(identities, partition.v5_new)
        prior_selected = (
            set(partition.selected)
            - set(partition.v5_new)
            - set(partition.v6_new)
            - set(partition.v7_new)
        )
        prior_remaining = (
            set(partition.discovered)
            - prior_selected
            - set(partition.local_socket_excluded)
        )
        self.assertTrue(set(partition.v5_new) <= prior_remaining)
        self.assertFalse(set(partition.v5_new) & prior_selected)
        self.assertFalse(
            set(partition.v5_new) & set(partition.local_socket_excluded)
        )

    def test_v6_manifest_is_exact_and_inside_the_prior_parent_remainder(self) -> None:
        partition = self.require_partition()
        identities, failures = current.load_v6_tests()
        self.assertEqual(failures, [])
        self.assertEqual(identities, partition.v6_new)
        prior_selected = (
            set(partition.selected)
            - set(partition.v6_new)
            - set(partition.v7_new)
        )
        prior_remaining = (
            set(partition.discovered)
            - prior_selected
            - set(partition.local_socket_excluded)
        )
        self.assertTrue(set(partition.v6_new) <= prior_remaining)
        self.assertFalse(set(partition.v6_new) & prior_selected)
        self.assertFalse(
            set(partition.v6_new) & set(partition.local_socket_excluded)
        )

    def test_v7_manifest_is_exact_and_inside_the_prior_parent_remainder(self) -> None:
        partition = self.require_partition()
        identities, failures = current.load_v7_tests()
        self.assertEqual(failures, [])
        self.assertEqual(identities, partition.v7_new)
        prior_selected = set(partition.selected) - set(partition.v7_new)
        prior_remaining = (
            set(partition.discovered)
            - prior_selected
            - set(partition.local_socket_excluded)
        )
        self.assertTrue(set(partition.v7_new) <= prior_remaining)
        self.assertFalse(set(partition.v7_new) & prior_selected)
        self.assertFalse(
            set(partition.v7_new) & set(partition.local_socket_excluded)
        )

    def test_failure_context_is_bounded_and_keeps_assertion_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = current.Path(directory) / "console.log"
            log_path.write_text(
                "ordinary line\n"
                "error: XCTAssertEqual failed: expected 1 got 2\n"
                + "tail line\n" * 100,
                encoding="utf-8",
            )
            context = current.swift_failure_context(log_path)
        self.assertIsNotNone(context)
        self.assertIn("XCTAssertEqual failed", context or "")
        self.assertLessEqual(
            len((context or "").splitlines()),
            current.FAILURE_CONTEXT_MAX_LINES + 1,
        )
        self.assertLessEqual(
            len((context or "")),
            current.FAILURE_CONTEXT_MAX_CHARACTERS
            + len("G7 current-run bounded failure context:\n"),
        )


if __name__ == "__main__":
    unittest.main()
