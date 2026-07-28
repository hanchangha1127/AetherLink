#!/usr/bin/env python3
"""Mutation tests for the fixed-point snapshot review decision."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("tests require unoptimized `python3 -I -B -S`")

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / (
        "check_p2p_nat_g2_pion_fixed_point_snapshot_"
        "source_license_review_decision_v1.py"
    )
)
SPEC = importlib.util.spec_from_file_location(
    "g2_pion_fixed_point_snapshot_source_license_review_decision_v1",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load fixed-point snapshot review checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class StdoutCapture:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()


class FixedPointSnapshotSourceLicenseReviewDecisionTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = checker.expected_decision()
        cls.decision_raw = (
            checker.ROOT / checker.DECISION_PATH
        ).read_bytes()

    def rebound(self, value: dict[str, object]) -> bytes:
        mutated = copy.deepcopy(value)
        mutated.pop("contentBinding", None)
        return checker.canonical_bytes(checker.content_bound(mutated))

    def test_01_baseline_validates_exact_on_disk_package(self) -> None:
        result = checker.check_repository(checker.ROOT)
        self.assertTrue(result["validationPassed"])
        self.assertTrue(result["onDiskExactEqualityVerified"])
        self.assertTrue(result["dependencyFixedPointReached"])
        self.assertEqual(result["independentPassCountCompleted"], 0)
        self.assertFalse(result["dependencySourceReviewed"])
        self.assertFalse(result["licenseCompatibilityReviewed"])
        self.assertFalse(result["securityReviewComplete"])
        self.assertFalse(result["rungThreeComplete"])
        self.assertFalse(result["releaseReady"])
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        self.assertFalse(result["gitWriteAuthorized"])
        self.assertFalse(result["fileWriteAuthorized"])

    def test_02_print_expected_matches_canonical_disk_bytes(self) -> None:
        capture = StdoutCapture()
        with mock.patch.object(sys, "stdout", capture):
            result = checker.main(["--print-expected"])
        self.assertEqual(result, 0)
        self.assertEqual(capture.buffer.getvalue(), self.decision_raw)
        self.assertEqual(
            self.decision_raw,
            checker.canonical_bytes(self.expected),
        )

    def test_03_content_binding_and_critical_mutations_fail_closed(
        self,
    ) -> None:
        parsed = checker.validate_decision_bytes(
            self.decision_raw,
            self.expected,
        )
        without = dict(parsed)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            checker.sha256(checker.canonical_bytes(without)),
        )

        mutations = (
            lambda value: value["closure"].__setitem__(
                "dependencySourceReviewed",
                True,
            ),
            lambda value: value["authority"].__setitem__(
                "externalAuthenticationRequired",
                True,
            ),
            lambda value: value["authority"].__setitem__(
                "gitWriteAuthorized",
                True,
            ),
            lambda value: value["authority"].__setitem__(
                "networkAuthorized",
                True,
            ),
            lambda value: value["authority"].__setitem__(
                "filesystemExtractionAuthorized",
                True,
            ),
            lambda value: value["authority"].__setitem__(
                "retainedSourceLoadOrExecutionAuthorized",
                True,
            ),
            lambda value: value["reviewContract"].__setitem__(
                "independentPassCountCompleted",
                1,
            ),
            lambda value: value["outputContract"].__setitem__(
                "spdx23SbomProduced",
                True,
            ),
            lambda value: value["snapshotBinding"].__setitem__(
                "sourceInputCount",
                368,
            ),
            lambda value: value["validatedAdapterProjection"][
                "graph"
            ].__setitem__("graphSha256", "0" * 64),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                mutated = copy.deepcopy(parsed)
                mutate(mutated)
                with self.assertRaises(checker.CheckError) as raised:
                    checker.validate_decision_bytes(
                        self.rebound(mutated),
                        self.expected,
                    )
                self.assertEqual(raised.exception.code, "E_DECISION")

    def test_04_duplicate_nonfinite_and_noncanonical_json_fail(
        self,
    ) -> None:
        duplicate = self.decision_raw.replace(
            b'{"authority":',
            b'{"authority":{"duplicate":true},"authority":',
            1,
        )
        with self.assertRaises(checker.CheckError) as raised:
            checker.strict_json(duplicate)
        self.assertEqual(raised.exception.code, "E_JSON")

        with self.assertRaises(checker.CheckError) as raised:
            checker.strict_json(b'{"value":NaN}\n')
        self.assertEqual(raised.exception.code, "E_JSON")

        noncanonical = json.dumps(
            self.expected,
            ensure_ascii=True,
            indent=2,
        ).encode("utf-8") + b"\n"
        with self.assertRaises(checker.CheckError) as raised:
            checker.validate_decision_bytes(
                noncanonical,
                self.expected,
            )
        self.assertEqual(
            raised.exception.code,
            "E_CANONICAL_DECISION",
        )

    def test_05_predecessor_and_tool_byte_seals_are_exact(self) -> None:
        predecessor = self.expected["predecessorBindings"]
        tools = self.expected["toolBindings"]
        raw_bindings = (
            predecessor["closureDecision"],
            predecessor["closureReader"],
            predecessor["closureTests"],
            predecessor["implementationOrDependencyReviewDecision"],
            predecessor["stagedFixedPointSourceClosurePlan"],
            tools["snapshotReviewAdapter"],
            tools["snapshotReviewAdapterTests"],
            tools["pinnedReviewRunner"],
            tools["decisionReader"],
            tools["decisionTests"],
        )
        for binding in raw_bindings:
            raw = (checker.ROOT / binding["path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(),
                binding["rawSha256"],
            )
        adapter_raw = (
            checker.ROOT / tools["snapshotReviewAdapter"]["path"]
        ).read_bytes()
        self.assertEqual(
            checker.sha256(
                checker.normalized_constant_bytes(
                    adapter_raw,
                    "SELF_NORMALIZED_SHA256",
                )
            ),
            tools["snapshotReviewAdapter"]["normalizedSelfSha256"],
        )
        self.assertEqual(
            checker.sha256(
                checker.normalized_constant_bytes(
                    CHECKER_PATH.read_bytes(),
                    "SELF_NORMALIZED_SHA256",
                )
            ),
            tools["decisionChecker"]["normalizedSelfSha256"],
        )

    def test_06_snapshot_and_profiles_are_exact(self) -> None:
        snapshot = self.expected["snapshotBinding"]
        self.assertEqual(snapshot["sourceInputCount"], 369)
        self.assertEqual(snapshot["moduleVersionTupleCount"], 184)
        self.assertEqual(snapshot["archiveCount"], 185)
        self.assertEqual(snapshot["archiveEntryCount"], 72_304)
        self.assertEqual(snapshot["aggregateRawBytes"], 356_092_640)
        self.assertEqual(
            snapshot["aggregateUncompressedBytes"],
            1_359_347_284,
        )
        self.assertEqual(snapshot["goFileCountBySuffix"], 58_478)
        self.assertEqual(
            snapshot["broadLicenseCandidateCountByName"],
            362,
        )
        self.assertEqual(
            snapshot["reviewBindingSetSha256"],
            checker.ADAPTER_REVIEW_BINDING_SET_SHA256,
        )
        self.assertEqual(len(snapshot["profiles"]), 2)
        self.assertEqual(
            {row["profileId"] for row in snapshot["profiles"]},
            {
                "android_api_26_through_36_arm64_v8a",
                "macos_14_or_newer_arm64",
            },
        )
        self.assertEqual(
            {row["goVersion"] for row in snapshot["profiles"]},
            {"1.24"},
        )

    def test_07_adapter_projection_and_graph_are_exact(self) -> None:
        projection = self.expected["validatedAdapterProjection"]
        self.assertTrue(projection["preflightValidationPassed"])
        self.assertTrue(projection["fullScanValidationPassed"])
        self.assertEqual(
            (projection["adapterTestsPassed"], projection["adapterTestsTotal"]),
            (14, 14),
        )
        self.assertFalse(projection["stdoutProjectionPersisted"])
        self.assertEqual(projection["moduleCoverageCount"], 185)
        self.assertEqual(projection["sourceFileCount"], 58_478)
        self.assertEqual(
            projection["pinnedRunnerNarrowLicenseCandidateCount"],
            195,
        )
        self.assertEqual(
            projection["broadLicenseCandidateCountByName"],
            362,
        )
        self.assertEqual(projection["specialSourceCount"], 11_150)
        graph = projection["graph"]
        self.assertEqual(graph["graphSha256"], checker.V18_GRAPH_SHA256)
        self.assertEqual(graph["graphNodeCount"], 132)
        self.assertEqual(graph["graphEdgeCount"], 1_047)
        self.assertEqual(graph["moduleNodeCount"], 185)
        self.assertEqual(graph["moduleEdgeCount"], 471)
        self.assertEqual(graph["selectedVersionCount"], 33)
        self.assertTrue(graph["fixedPointReached"])
        self.assertEqual(graph["newTupleCount"], 0)

    def test_08_compatibility_and_operation_counters_are_bounded(
        self,
    ) -> None:
        projection = self.expected["validatedAdapterProjection"]
        compatibility = projection["compatibility"]
        self.assertEqual(
            compatibility["wave9PinnedLegacyBuildCompatibilityCount"],
            2,
        )
        self.assertEqual(
            compatibility[
                "malformedNonProductionGoFixtureCompatibilityCount"
            ],
            30,
        )
        self.assertTrue(
            compatibility["exactHashPathClassAndCountBounded"]
        )
        counters = projection["operationCounters"]
        self.assertEqual(
            (
                counters["metadataPreflightZipArchiveOpenCount"],
                counters["delegatedFullScanZipArchiveOpenCount"],
                counters["totalZipArchiveOpenCount"],
            ),
            (369, 185, 554),
        )
        for key in (
            "archiveExtractionCount",
            "sourceExecutionCount",
            "sourceCompilationCount",
            "subprocessCount",
            "networkOperationCount",
            "fileWriteCount",
        ):
            self.assertEqual(counters[key], 0, key)

    def test_09_two_pass_contract_is_pending_and_nonattesting(self) -> None:
        contract = self.expected["reviewContract"]
        self.assertEqual(contract["requiredModel"], "GPT-5.6 Sol")
        self.assertEqual(contract["independentPassCountRequired"], 2)
        self.assertEqual(contract["independentPassCountCompleted"], 0)
        self.assertTrue(contract["sameImmutableByteBindingsRequired"])
        self.assertFalse(
            contract["passesMayReadEachOtherBeforeBothComplete"]
        )
        self.assertFalse(contract["passOutputsAttestAuthority"])
        self.assertEqual(contract["disagreementDisposition"], "unresolved")
        self.assertEqual(contract["unknownLicenseDisposition"], "unresolved")

    def test_10_authority_is_local_and_never_requires_auth(self) -> None:
        authority = self.expected["authority"]
        true_keys = {
            key for key, value in authority.items() if value is True
        }
        self.assertEqual(
            true_keys,
            {
                "decisionRecorded",
                "localReadOnlyInspectionAuthorized",
                "retainedSourceByteReadAuthorized",
                "boundedInMemoryArchiveDecodeAuthorized",
                "boundedStaticSourceInspectionAuthorized",
                "buildProfileClassificationAuthorized",
                "stdoutOnlyProjectionAuthorized",
                "twoIndependentGpt56SolReviewsAuthorized",
            },
        )
        for key in (
            "externalAuthenticationRequired",
            "repositoryOwnerIdentityProofRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "approvalRequired",
            "userActionRequired",
            "gitWriteAuthorized",
            "networkAuthorized",
            "fileWriteAuthorized",
        ):
            self.assertFalse(authority[key], key)

    def test_11_closure_output_and_findings_remain_open(self) -> None:
        closure = self.expected["closure"]
        self.assertTrue(closure["dependencyFixedPointReached"])
        for key, value in closure.items():
            if key != "dependencyFixedPointReached":
                self.assertFalse(value, key)
        output = self.expected["outputContract"]
        self.assertTrue(output["stdoutOnly"])
        for key, value in output.items():
            if key.endswith("Produced"):
                self.assertFalse(value, key)
        findings = self.expected["findingDisposition"]
        self.assertEqual(findings["canonicalFindingCount"], 19)
        self.assertEqual(findings["patchRequiredCount"], 7)
        self.assertEqual(findings["unresolvedCount"], 12)
        self.assertEqual(findings["closedByThisDecisionCount"], 0)
        self.assertTrue(findings["allCanonicalFindingsRemainOpen"])

    def test_12_nonclaims_and_next_action_are_narrow(self) -> None:
        self.assertEqual(set(self.expected["nonClaims"].values()), {False})
        self.assertEqual(
            self.expected["nextAction"],
            (
                "perform_two_independent_gpt_5_6_sol_fixed_point_snapshot_"
                "source_license_security_review_passes"
            ),
        )

    def test_13_stable_reader_rejects_links_and_writable_modes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular"
            regular.write_bytes(b"ok")
            regular.chmod(0o600)
            self.assertEqual(
                checker.read_stable_regular_file(root, "regular", 2),
                b"ok",
            )
            symlink = root / "symlink"
            symlink.symlink_to(regular)
            with self.assertRaises(checker.CheckError):
                checker.read_stable_regular_file(root, "symlink", 2)
            hardlink = root / "hardlink"
            os.link(regular, hardlink)
            with self.assertRaises(checker.CheckError):
                checker.read_stable_regular_file(root, "regular", 2)
            writable = root / "writable"
            writable.write_bytes(b"no")
            writable.chmod(0o620)
            with self.assertRaises(checker.CheckError):
                checker.read_stable_regular_file(root, "writable", 2)
            with self.assertRaises(checker.CheckError):
                checker.read_stable_regular_file(root, "../escape", 2)

    def test_14_error_output_never_requests_authentication(self) -> None:
        result = checker.error_result("E_TEST")
        self.assertEqual(result["error"], "E_TEST")
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        self.assertFalse(result["gitWriteAuthorized"])
        self.assertFalse(result["fileWriteAuthorized"])

    def test_15_checker_has_no_write_network_or_subprocess_surface(
        self,
    ) -> None:
        tree = ast.parse(CHECKER_PATH.read_bytes())
        imported_roots: set[str] = set()
        banned_calls: list[str] = []
        banned_attributes = {
            "chmod",
            "execv",
            "execve",
            "fork",
            "link",
            "mkdir",
            "popen",
            "remove",
            "rename",
            "replace",
            "rmdir",
            "spawn",
            "symlink",
            "system",
            "unlink",
            "write_bytes",
            "write_text",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "compile",
                    "eval",
                    "exec",
                }:
                    banned_calls.append(node.func.id)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in banned_attributes
                ):
                    banned_calls.append(node.func.attr)
        self.assertTrue(
            imported_roots.isdisjoint(
                {"http", "requests", "socket", "subprocess", "urllib"}
            )
        )
        self.assertEqual(banned_calls, [])


if __name__ == "__main__":
    unittest.main()
