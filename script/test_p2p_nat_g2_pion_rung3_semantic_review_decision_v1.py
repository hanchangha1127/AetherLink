#!/usr/bin/env python3
"""Mutation tests for the G2 Pion semantic-review v1 decision checker."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError("semantic-review decision tests require `python3 -I -B -S`")


require_isolated_interpreter()

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from typing import Any, Callable


ROOT = Path(os.path.abspath(__file__)).parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung3_semantic_review_decision_v1.py"


def load_checker() -> dict[str, Any]:
    source = CHECKER_PATH.read_bytes()
    namespace: dict[str, Any] = {
        "__file__": os.fspath(CHECKER_PATH),
        "__name__": "_aetherlink_tested_semantic_review_decision_v1",
        "__package__": None,
    }
    exec(
        compile(
            source,
            os.fspath(CHECKER_PATH.relative_to(ROOT)),
            "exec",
            dont_inherit=True,
            optimize=0,
        ),
        namespace,
    )
    return namespace


C = load_checker()


def reseal_decision(value: dict[str, Any]) -> bytes:
    payload = copy.deepcopy(value)
    payload.pop("contentBinding")
    encoded = C["canonical_json_bytes"](payload)
    value["contentBinding"]["sha256"] = hashlib.sha256(encoded).hexdigest()
    return C["canonical_json_bytes"](value)


class SemanticReviewDecisionV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = C["FixedTrackedReader"](ROOT).read_all()

    def assert_check_error(self, callback: Callable[[], Any]) -> None:
        with self.assertRaises(C["CheckError"]):
            callback()

    def mutate_decision(self, mutation: Callable[[dict[str, Any]], None]) -> dict[str, bytes]:
        raw = dict(self.raw)
        decision = copy.deepcopy(json.loads(raw[C["DECISION_PATH"]]))
        mutation(decision)
        raw[C["DECISION_PATH"]] = reseal_decision(decision)
        return raw

    def validate_without_raw_pins(self, raw: dict[str, bytes]) -> dict[str, Any]:
        return C["validate_documents"](raw, enforce_pins=False)

    def test_01_repository_passes_with_tracked_only_zero_side_effect_counters(self) -> None:
        result = C["validate_repository"](ROOT)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["trackedFileReadCount"], 7)
        self.assertEqual(result["goSourceFileCount"], 100)
        self.assertEqual(result["lexicalObservationCount"], 4701)
        for key in (
            "buildReadCount",
            "archiveReadCount",
            "markdownReadCount",
            "networkOperationCount",
            "deviceOperationCount",
            "gitOperationCount",
            "fileWriteCount",
        ):
            self.assertEqual(result[key], 0)
        self.assertFalse(result["authenticationOrUserActionRequired"])

    def test_02_authentication_or_user_action_escalation_is_rejected(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            boundary = value["personalProjectBoundary"]
            boundary["repositoryOwnerAuthenticationRequired"] = True
            boundary["externalIdentityProofRequired"] = True
            boundary["executionPermitAuthenticationRequired"] = True
            boundary["executionPermitDocumentRequired"] = True
            boundary["userActionRequired"] = True

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_03_mutable_markdown_binding_is_rejected(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["predecessorBindings"][0]["path"] = "docs/roadmap.md"

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_04_representative_only_review_contract_is_rejected(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            coverage = value["reviewCoverage"]
            coverage["allLexicalObservationsRequired"] = False
            coverage["lexicalObservationTotals"]["totalHitCount"] = 144
            coverage["allGoSourceBodiesRequired"] = False

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_05_archive_count_tree_and_observation_hash_drift_are_rejected(self) -> None:
        mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
            lambda value: value["archiveIdentity"].__setitem__("rawSha256", "0" * 64),
            lambda value: value["archiveIdentity"].__setitem__("entryCount", 128),
            lambda value: value["archiveIdentity"].__setitem__("sourceTreeSha256", "1" * 64),
            lambda value: value["reviewCoverage"]["patchUnits"][0].__setitem__(
                "completeObservationSha256", "2" * 64
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                raw = self.mutate_decision(mutation)
                self.assert_check_error(lambda raw=raw: self.validate_without_raw_pins(raw))

    def test_06_example_source_misclassification_is_rejected(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["reviewCoverage"]["sourceClasses"] = {
                "production": 53,
                "test": 44,
                "example": 3,
            }
            value["semanticContract"]["sourceClassificationPrecedence"] = [
                "test",
                "example",
                "production",
            ]
            value["semanticContract"]["sourceClassificationRules"]["examplePathPrefix"] = (
                "example/"
            )

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_07_one_use_zero_hit_must_remain_a_missing_mechanism_gap(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            handling = value["semanticContract"]["oneUseZeroHitHandling"]
            handling["missingRequiredMechanismGapRequired"] = False
            handling["notAVulnerabilityConclusionByItself"] = False

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_08_dependency_candidate_and_library_overclaims_are_rejected(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["semanticContract"]["dependencyClosureComplete"] = True
            value["nonClaims"]["dependencyClosureComplete"] = True
            value["nonClaims"]["candidateSelected"] = True
            value["nonClaims"]["librarySelected"] = True
            value["nonClaims"]["rungThreeComplete"] = True

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_09_forbidden_execution_operations_are_rejected(self) -> None:
        forbidden = (
            "archiveExtractionAllowed",
            "codeLoadingAllowed",
            "compilerInvocationAllowed",
            "dependencyInstallationAllowed",
            "deviceOperationAllowed",
            "dnsAllowed",
            "gitOperationAllowed",
            "networkAllowed",
            "packageManagerAllowed",
            "reviewedSourceExecutionAllowed",
            "shellAllowed",
            "socketCreationAllowed",
            "sourceMaterializationAllowed",
            "sourcePatchWriteAllowed",
            "subprocessAllowed",
        )
        for key in forbidden:
            with self.subTest(key=key):
                raw = self.mutate_decision(
                    lambda value, key=key: value["operationBoundary"].__setitem__(key, True)
                )
                self.assert_check_error(lambda raw=raw: self.validate_without_raw_pins(raw))

    def test_10_two_pass_disagreement_must_force_unresolved(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["reviewCoverage"]["reviewPasses"] = ["primary"]
            value["semanticContract"]["disagreementResolution"] = "primary_wins"
            value["semanticContract"]["dispositions"].remove("unresolved")
            value["semanticContract"]["reviewPassesShareOneImmutableInMemorySnapshot"] = False
            value["semanticContract"][
                "eachReviewPassCoversAllGoSourceBodiesAndLexicalObservations"
            ] = False

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_11_repeatable_analysis_cannot_weaken_exclusive_publication(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            value["operationBoundary"]["analysisMayRepeatBeforeExclusivePublication"] = False
            value["publicationContract"]["exclusiveNoReplacePublicationRequired"] = False

        raw = self.mutate_decision(mutate)
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_12_strict_json_and_canonical_decision_encoding_are_enforced(self) -> None:
        for malformed in (
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":1}\n\n',
        ):
            with self.subTest(raw=malformed):
                self.assert_check_error(lambda malformed=malformed: C["strict_json"](malformed, "mutation"))
        raw = dict(self.raw)
        decision = json.loads(raw[C["DECISION_PATH"]])
        raw[C["DECISION_PATH"]] = (
            json.dumps(decision, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        ).encode()
        self.assert_check_error(lambda: self.validate_without_raw_pins(raw))

    def test_13_allowlist_rejects_build_archive_markdown_and_traversal(self) -> None:
        for path in (
            "build/output.json",
            "tracked/source.zip",
            "docs/roadmap.md",
            "../outside.json",
            "/absolute.json",
        ):
            with self.subTest(path=path):
                self.assert_check_error(lambda path=path: C["_safe_parts"](path))

    def test_14_stable_reader_rejects_symlinked_tracked_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_text("{}\n", encoding="utf-8")
            decision = root / C["DECISION_PATH"]
            decision.parent.mkdir(parents=True)
            decision.symlink_to(target)
            reader = C["FixedTrackedReader"](root)
            self.assert_check_error(lambda: reader.read(C["DECISION_PATH"]))

    def test_15_raw_pin_and_self_hash_drift_fail_closed(self) -> None:
        raw = dict(self.raw)
        decision = bytearray(raw[C["DECISION_PATH"]])
        decision[-2:-1] = b" "
        raw[C["DECISION_PATH"]] = bytes(decision)
        self.assert_check_error(lambda: C["validate_documents"](raw))


if __name__ == "__main__":
    unittest.main(verbosity=2)
