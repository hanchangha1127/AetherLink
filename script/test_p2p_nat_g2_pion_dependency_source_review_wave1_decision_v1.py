#!/usr/bin/env python3
"""Regression tests for the G2 dependency source-review wave-one decision."""

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

import copy
from contextlib import redirect_stdout
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
    / "check_p2p_nat_g2_pion_dependency_source_review_wave1_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "dependency_source_review_wave1_decision_v1_checker",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load decision checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class DependencySourceReviewWaveOneDecisionV1Tests(unittest.TestCase):
    def bound_decision(self) -> dict[str, object]:
        expected = CHECKER.expected_decision()
        decision = copy.deepcopy(expected)
        decision["contentBinding"] = {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": "decision_without_contentBinding",
            "sha256": CHECKER.sha256_bytes(
                CHECKER.canonical_json_bytes(expected)
            ),
        }
        return decision

    def test_01_predecessors_remain_byte_exact(self) -> None:
        bindings = CHECKER.expected_decision()["predecessorBindings"]
        for binding in bindings.values():
            relative = binding["path"]
            raw = CHECKER.ROOT.joinpath(relative).read_bytes()
            with self.subTest(relative=relative):
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(),
                    binding["rawSha256"],
                )
        root_archive = CHECKER.ROOT / CHECKER.ROOT_ARCHIVE_PATH
        self.assertEqual(
            hashlib.sha256(root_archive.read_bytes()).hexdigest(),
            CHECKER.ROOT_ARCHIVE_RAW_SHA256,
        )

    def test_02_recorded_decision_is_exact_and_content_bound(self) -> None:
        raw = CHECKER.ROOT.joinpath(CHECKER.DECISION_PATH).read_bytes()
        decision = CHECKER.strict_json(raw, "recorded decision")
        expected = CHECKER.expected_decision()
        CHECKER.validate_decision_document(decision, expected)
        self.assertEqual(decision, self.bound_decision())

    def test_03_rebound_semantic_mutation_is_rejected(self) -> None:
        expected = CHECKER.expected_decision()
        decision = self.bound_decision()
        decision["workPackage"]["inputArchiveCount"] = 21
        unbound = dict(decision)
        unbound.pop("contentBinding")
        decision["contentBinding"]["sha256"] = CHECKER.sha256_bytes(
            CHECKER.canonical_json_bytes(unbound)
        )
        with self.assertRaisesRegex(
            CHECKER.DecisionError,
            "exact typed contract",
        ):
            CHECKER.validate_decision_document(decision, expected)

    def test_04_boolean_integer_confusion_is_rejected(self) -> None:
        expected = CHECKER.expected_decision()
        decision = self.bound_decision()
        decision["workPackage"]["inputRootModuleCount"] = True
        unbound = dict(decision)
        unbound.pop("contentBinding")
        decision["contentBinding"]["sha256"] = CHECKER.sha256_bytes(
            CHECKER.canonical_json_bytes(unbound)
        )
        with self.assertRaises(CHECKER.DecisionError):
            CHECKER.validate_decision_document(decision, expected)

    def test_05_strict_json_rejects_ambiguous_numbers_and_keys(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":1.0}\n',
            b'{"a":NaN}\n',
            b'{"a":Infinity}\n',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.DecisionError):
                    CHECKER.strict_json(raw, "mutation")

    def test_06_scope_and_exact_source_totals_are_frozen(self) -> None:
        decision = CHECKER.expected_decision()
        source_set = decision["sourceSetBinding"]
        work_package = decision["workPackage"]
        self.assertEqual(source_set["dependencyTupleCount"], 19)
        self.assertEqual(source_set["retainedResourceCount"], 38)
        self.assertEqual(source_set["aggregateRawByteSize"], 13_178_024)
        self.assertEqual(source_set["aggregateEntryCount"], 2_907)
        self.assertEqual(
            source_set["aggregateUncompressedByteCount"],
            31_851_201,
        )
        self.assertEqual(
            work_package["scope"],
            "module_metadata_graph_candidate_license_native_inventory_only",
        )
        for seeds in work_package["rootPackageSeedsByProfile"].values():
            self.assertEqual(seeds, ["github.com/pion/ice/v4"])

    def test_07_decision_requires_no_user_auth_or_action(self) -> None:
        decision = CHECKER.expected_decision()
        authority = decision["authority"]
        non_claims = decision["nonClaims"]
        self.assertFalse(authority["externalAuthenticationRequired"])
        self.assertFalse(authority["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(authority["userActionRequired"])
        self.assertFalse(authority["reviewExecutionAuthorized"])
        self.assertFalse(authority["gitWriteAuthorized"])
        self.assertFalse(
            non_claims["executionPermitAuthenticationRequired"]
        )
        self.assertTrue(
            non_claims["permitIsLocalContentBoundWorkflowControl"]
        )
        self.assertFalse(
            non_claims["productEndpointAuthenticationEvaluatedByThisDecision"]
        )
        self.assertTrue(
            non_claims["productEndpointAuthenticationIsSeparateRuntimeInvariant"]
        )
        self.assertFalse(
            non_claims[
                "productEndpointAuthenticationUserInputRequiredForThisDecision"
            ]
        )
        self.assertFalse(
            non_claims["userSuppliedCredentialOrTokenRequired"]
        )
        self.assertFalse(
            non_claims["userSuppliedSignatureOrKeyMaterialRequired"]
        )

    def test_08_all_closure_and_selection_claims_remain_false(self) -> None:
        closure = CHECKER.expected_decision()["closure"]
        self.assertEqual(closure["openFindingCount"], 19)
        self.assertEqual(closure["findingsClosedByDecision"], 0)
        for key in (
            "graphFixedPointReached",
            "dependencySourceReviewed",
            "dependencyClosureComplete",
            "semanticClosureComplete",
            "rungThreeComplete",
            "candidateSelected",
            "librarySelected",
        ):
            self.assertFalse(closure[key], key)

    def test_09_checker_exposes_no_review_execution_surface(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("--execute", source)
        for write_surface in (
            ".write_bytes(",
            ".write_text(",
            "os.mkdir(",
            "os.makedirs(",
            "os.rename(",
            "os.replace(",
            "os.unlink(",
        ):
            self.assertNotIn(write_surface, source)
        self.assertFalse(hasattr(CHECKER, "zipfile"))
        self.assertFalse(hasattr(CHECKER, "socket"))
        self.assertFalse(hasattr(CHECKER, "urllib"))
        self.assertFalse(hasattr(CHECKER, "subprocess"))

    def test_10_live_preflight_is_read_only(self) -> None:
        watched = [
            CHECKER.ROOT / CHECKER.DECISION_PATH,
            CHECKER.ROOT / CHECKER.READBACK_RECEIPT_PATH,
            CHECKER.ROOT / CHECKER.READBACK_MANIFEST_PATH,
        ]
        before = [path.read_bytes() for path in watched]
        result = CHECKER.validate_state(CHECKER.ROOT)
        after = [path.read_bytes() for path in watched]
        self.assertEqual(before, after)
        self.assertTrue(result["validationPassed"])
        self.assertEqual(result["networkOperationCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertFalse(result["reviewExecutionAuthorized"])
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])

    def test_11_future_execution_binding_is_non_circular(self) -> None:
        checker = CHECKER.expected_decision()["decisionChecker"]
        self.assertEqual(checker["checkerPath"], CHECKER.SELF_PATH)
        self.assertEqual(checker["checkerTestsPath"], CHECKER.TESTS_PATH)
        self.assertTrue(
            checker[
                "futureExecutionPermitMustBindCheckerAndTestsRawSha256"
            ]
        )
        self.assertNotIn("checkerRawSha256", checker)
        self.assertNotIn("checkerTestsRawSha256", checker)

    def test_12_preflight_cli_has_one_read_only_mode(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            parser_result = CHECKER.main(["--preflight"])
        self.assertEqual(parser_result, 0)
        self.assertTrue(json.loads(output.getvalue())["validationPassed"])
        self.assertEqual(
            CHECKER.expected_decision()["nextAction"],
            "prepare_separate_dependency_source_review_wave1_"
            "runner_tests_and_execution_permit",
        )

    def test_13_held_read_rejects_links_and_relaxed_owner_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_bytes(b"fixed")

            (root / "symbolic").symlink_to(target)
            with self.assertRaises(OSError):
                CHECKER.read_held(
                    root,
                    "symbolic",
                    maximum_bytes=16,
                )

            os.link(target, root / "hard")
            with self.assertRaisesRegex(
                CHECKER.DecisionError,
                "single-link",
            ):
                CHECKER.read_held(
                    root,
                    "hard",
                    maximum_bytes=16,
                )

            (root / "hard").unlink()
            target.chmod(0o644)
            with self.assertRaisesRegex(
                CHECKER.DecisionError,
                "owner-only",
            ):
                CHECKER.read_held(
                    root,
                    "target",
                    maximum_bytes=16,
                    owner_only=True,
                )

    def test_14_held_read_rejects_name_and_ancestor_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_bytes(b"fixed")
            original_stat = CHECKER.os.stat
            replaced = False

            def replace_final_name(*args: object, **kwargs: object) -> object:
                nonlocal replaced
                if not replaced and kwargs.get("follow_symlinks") is False:
                    replaced = True
                    target.unlink()
                    target.write_bytes(b"fixed")
                return original_stat(*args, **kwargs)

            with mock.patch.object(
                CHECKER.os,
                "stat",
                side_effect=replace_final_name,
            ):
                with self.assertRaisesRegex(
                    CHECKER.DecisionError,
                    "final name identity changed",
                ):
                    CHECKER.read_held(
                        root,
                        "target",
                        maximum_bytes=16,
                    )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ancestor = root / "ancestor"
            ancestor.mkdir()
            (ancestor / "target").write_bytes(b"fixed")
            original_open_directory = CHECKER.open_directory
            call_count = 0

            def replace_ancestor(parent_fd: int, component: str) -> int:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    ancestor.rename(root / "old-ancestor")
                    ancestor.mkdir()
                    (ancestor / "target").write_bytes(b"fixed")
                return original_open_directory(parent_fd, component)

            with mock.patch.object(
                CHECKER,
                "open_directory",
                side_effect=replace_ancestor,
            ):
                with self.assertRaisesRegex(
                    CHECKER.DecisionError,
                    "ancestor identity changed",
                ):
                    CHECKER.read_held(
                        root,
                        "ancestor/target",
                        maximum_bytes=16,
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
