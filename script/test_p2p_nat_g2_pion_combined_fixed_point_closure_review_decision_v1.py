#!/usr/bin/env python3
"""Mutation tests for the Combined V18 fixed-point closure decision."""

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
        "check_p2p_nat_g2_pion_combined_fixed_point_"
        "closure_review_decision_v1.py"
    )
)
SPEC = importlib.util.spec_from_file_location(
    "g2_pion_combined_fixed_point_closure_review_decision_v1",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load closure-review checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class StdoutCapture:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()


class CombinedFixedPointClosureReviewDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = checker.expected_decision()
        cls.decision_raw = (
            checker.ROOT / checker.DECISION_PATH
        ).read_bytes()
        cls.reader_raw = (checker.ROOT / checker.READER_PATH).read_bytes()

    def test_01_baseline_validates_exact_on_disk_package(self) -> None:
        result = checker.check_repository(checker.ROOT)
        self.assertTrue(result["validationPassed"])
        self.assertTrue(result["onDiskExactEqualityVerified"])
        self.assertTrue(result["dependencyFixedPointReached"])
        self.assertFalse(result["dependencySourceReviewed"])
        self.assertFalse(result["dependencyClosureComplete"])
        self.assertFalse(result["semanticClosureComplete"])
        self.assertEqual(result["openCanonicalFindingCount"], 19)
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        self.assertFalse(result["gitWriteAuthorized"])

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

    def test_03_content_binding_and_mutations_fail_closed(self) -> None:
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

        mutated = copy.deepcopy(parsed)
        mutated["closure"]["dependencyClosureComplete"] = True
        mutated.pop("contentBinding")
        rebound = checker.content_bound(mutated)
        with self.assertRaises(checker.CheckError) as caught:
            checker.validate_decision_bytes(
                checker.canonical_bytes(rebound),
                self.expected,
            )
        self.assertEqual(caught.exception.code, "E_DECISION")

    def test_04_duplicate_nonfinite_and_noncanonical_json_fail(self) -> None:
        duplicate = self.decision_raw.replace(
            b'{"authority":',
            b'{"schemaVersion":"duplicate","authority":',
            1,
        )
        with self.assertRaises(checker.CheckError) as caught:
            checker.strict_json(duplicate)
        self.assertEqual(caught.exception.code, "E_JSON")

        with self.assertRaises(checker.CheckError) as caught:
            checker.strict_json(b'{"value":NaN}\n')
        self.assertEqual(caught.exception.code, "E_JSON")

        noncanonical = json.dumps(
            self.expected,
            indent=2,
            ensure_ascii=True,
        ).encode() + b"\n"
        with self.assertRaises(checker.CheckError) as caught:
            checker.validate_decision_bytes(
                noncanonical,
                self.expected,
            )
        self.assertEqual(caught.exception.code, "E_CANONICAL_DECISION")

    def test_05_exact_predecessor_and_v18_tool_pins_hold(self) -> None:
        evidence = self.expected["evidenceBindings"]
        bindings = (
            evidence["patchAndDependencyClosureDecision"],
            evidence["semanticSourceReviewClassifications"],
            evidence["semanticSourceReviewResult"],
            evidence["combinedV18Checker"],
            evidence["combinedV18Tests"],
            evidence["closureReviewTests"],
            evidence["reader"],
        )
        for binding in bindings:
            raw = (checker.ROOT / binding["path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(),
                binding["rawSha256"],
            )
        self.assertEqual(
            checker.sha256(
                checker.normalized_v18_checker_bytes(
                    (
                        checker.ROOT
                        / evidence["combinedV18Checker"]["path"]
                    ).read_bytes()
                )
            ),
            evidence["combinedV18Checker"]["normalizedSelfSha256"],
        )
        self.assertEqual(
            checker.sha256(
                checker.normalized_self_bytes(CHECKER_PATH.read_bytes())
            ),
            evidence["closureReviewChecker"]["normalizedSelfSha256"],
        )

    def test_06_fixed_point_scope_and_seals_are_exact(self) -> None:
        review = self.expected["fixedPointReview"]
        evidence = self.expected["evidenceBindings"]
        self.assertEqual(review["heldSourceInputCount"], 369)
        self.assertEqual(review["exactInputInventoryCount"], 379)
        self.assertEqual(review["moduleVersionTupleCount"], 184)
        self.assertEqual(review["archiveCount"], 185)
        self.assertEqual(review["archiveEntryCount"], 72_304)
        self.assertEqual(review["exactFrontier"], [])
        self.assertEqual(review["newTupleCount"], 0)
        self.assertEqual(review["unmappedExternalImportCount"], 0)
        self.assertEqual(
            review["unresolvedDeclaredExternalImportCount"],
            0,
        )
        self.assertTrue(review["fixedPointReached"])
        self.assertTrue(review["canonicalGraphEqualityVerified"])
        self.assertFalse(
            review["candidateArtifactPersistedByThisDecision"]
        )
        self.assertEqual(
            evidence["candidateContentSha256"],
            checker.V18_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            evidence["graphSha256"],
            checker.V18_GRAPH_SHA256,
        )
        self.assertEqual(
            evidence["frontierSha256"],
            hashlib.sha256(b"[]\n").hexdigest(),
        )

    def test_07_operation_counters_remain_read_only(self) -> None:
        review = self.expected["fixedPointReview"]
        self.assertEqual(review["fullSourceReconstructionCount"], 34)
        self.assertEqual(review["archiveOpenCount"], 4_792)
        self.assertEqual(review["independentGraphAlgorithmCount"], 68)
        self.assertEqual(
            set(review["operationCounters"].values()),
            {0},
        )

    def test_08_test_history_does_not_claim_clean_24_of_24(self) -> None:
        evidence = self.expected["testEvidence"]
        self.assertEqual(
            evidence["postSealDryLatentFastBoundary"],
            {"passed": 18, "total": 18},
        )
        full_class = evidence["genuineFullClass"]
        self.assertEqual((full_class["passed"], full_class["total"]), (23, 24))
        self.assertEqual(
            full_class["soleError"],
            "test_13_legacy_wave9_compatibility_remains_exact_and_bounded",
        )
        self.assertFalse(full_class["cleanPostFixFullClassRerunClaimed"])
        self.assertEqual(
            evidence["correctedIsolatedTest13"],
            {"passed": 1, "total": 1},
        )
        self.assertFalse(
            self.expected["nonClaims"][
                "testEvidenceIsCleanPostFixFullClassRerun"
            ]
        )

    def test_09_all_19_findings_remain_open(self) -> None:
        findings = self.expected["findingDisposition"]
        self.assertEqual(findings["canonicalFindingCount"], 19)
        self.assertEqual(findings["patchRequiredCount"], 7)
        self.assertEqual(findings["unresolvedCount"], 12)
        self.assertEqual(findings["closedByThisDecisionCount"], 0)
        self.assertTrue(findings["allCanonicalFindingsRemainOpen"])
        self.assertTrue(findings["allFindingIdsBoundByExactPredecessors"])

    def test_10_only_dependency_fixed_point_closure_flag_is_true(self) -> None:
        closure = self.expected["closure"]
        self.assertTrue(closure["dependencyFixedPointReached"])
        for key, value in closure.items():
            if key != "dependencyFixedPointReached":
                self.assertFalse(value, key)

    def test_11_authority_requires_no_authentication_or_user_action(
        self,
    ) -> None:
        authority = self.expected["authority"]
        self.assertTrue(authority["decisionRecorded"])
        for key, value in authority.items():
            if key != "decisionRecorded":
                self.assertFalse(value, key)
        for key in (
            "externalAuthenticationRequired",
            "repositoryOwnerIdentityProofRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "approvalRequired",
            "userActionRequired",
        ):
            self.assertFalse(authority[key])

    def test_12_nonclaims_and_next_action_are_narrow(self) -> None:
        self.assertEqual(
            set(self.expected["nonClaims"].values()),
            {False},
        )
        self.assertEqual(
            self.expected["nextAction"],
            (
                "prepare_separate_fixed_point_snapshot_"
                "dependency_source_and_license_review_decision"
            ),
        )

    def test_13_reader_is_exact_and_preserves_the_boundary(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.reader_raw).hexdigest(),
            checker.READER_SHA256,
        )
        text = self.reader_raw.decode("utf-8")
        normalized_text = " ".join(text.split())
        for phrase in (
            "dependency graph fixed point accepted",
            "19 canonical semantic findings",
            "does not claim a clean post-fix 24/24 full-class rerun",
            "external authentication",
            "user action",
        ):
            self.assertIn(phrase, normalized_text)

    def test_14_checker_static_surface_has_no_active_capability(self) -> None:
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
                {
                    "http",
                    "requests",
                    "socket",
                    "subprocess",
                    "urllib",
                }
            )
        )
        self.assertEqual(banned_calls, [])

    def test_15_path_symlink_and_hardlink_inputs_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular"
            regular.write_bytes(b"ok")
            self.assertEqual(
                checker.read_stable_regular_file(root, "regular"),
                b"ok",
            )

            symlink = root / "symlink"
            symlink.symlink_to(regular)
            with self.assertRaises(checker.CheckError):
                checker.read_stable_regular_file(root, "symlink")

            hardlink = root / "hardlink"
            os.link(regular, hardlink)
            with self.assertRaises(checker.CheckError):
                checker.read_stable_regular_file(root, "regular")

            with self.assertRaises(checker.CheckError):
                checker.read_stable_regular_file(root, "../escape")


if __name__ == "__main__":
    unittest.main()
