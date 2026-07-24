#!/usr/bin/env python3
"""Synthetic regression tests for the verification-only readback checker."""

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
import importlib.util
import os
from pathlib import Path
import unittest


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
CHECKER_PATH = (
    SCRIPT_DIRECTORY
    / "check_p2p_nat_g2_pion_dependency_source_review_wave1_readback_v1.py"
)
RECORDER_PATH = (
    SCRIPT_DIRECTORY
    / "record_p2p_nat_g2_pion_dependency_source_review_wave1_readback_v1.py"
)
RECORDER_TESTS_PATH = (
    SCRIPT_DIRECTORY
    / "test_record_p2p_nat_g2_pion_dependency_source_review_"
    "wave1_readback_v1.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_module("dependency_review_readback_checker", CHECKER_PATH)
recorder = load_module("dependency_review_readback_recorder_for_tests", RECORDER_PATH)
fixture_module = load_module(
    "dependency_review_readback_recorder_fixture", RECORDER_TESTS_PATH
)
SyntheticReviewFixture = fixture_module.SyntheticReviewFixture
graph_for = fixture_module.graph_for


def rebind(
    document: dict[str, object],
    scope: str,
) -> dict[str, object]:
    value = dict(document)
    value.pop("contentBinding", None)
    return checker.content_bound(value, scope)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class ReadbackVerificationTests(unittest.TestCase):
    def completed(self, route: str = "fixed_point_candidate"):
        fixture = SyntheticReviewFixture(route)
        recorder.record_readback(fixture.root)
        return fixture

    def test_01_three_routes_are_independently_verified(self) -> None:
        for route in checker.ROUTES:
            fixture = self.completed(route)
            try:
                output = checker.validate_state(fixture.root)
                self.assertTrue(output["validationPassed"])
                self.assertEqual(output["route"], route)
                self.assertEqual(
                    output["status"],
                    (
                        "dependency_source_review_wave1_independent_"
                        f"readback_verified_{route}"
                    ),
                )
                self.assertTrue(output["verificationOnly"])
                self.assertFalse(output["recordModeExposed"])
                self.assertEqual(output["fileWriteCount"], 0)
                self.assertEqual(output["networkOperationCount"], 0)
                self.assertEqual(
                    output["nextAction"],
                    checker.ROUTES[route]["manifestNextAction"],
                )
            finally:
                fixture.close()

    def test_02_verification_changes_no_bytes(self) -> None:
        fixture = self.completed()
        try:
            before = snapshot(fixture.root)
            checker.validate_state(fixture.root)
            after = snapshot(fixture.root)
            self.assertEqual(before, after)
        finally:
            fixture.close()

    def test_03_claim_receipt_and_manifest_mutations_fail_closed(self) -> None:
        for relative, scope, field in (
            (
                checker.READBACK_CLAIM_PATH,
                "readback_claim_without_contentBinding",
                "route",
            ),
            (
                checker.READBACK_RECEIPT_PATH,
                "readback_receipt_without_contentBinding",
                "nextAction",
            ),
            (
                checker.READBACK_MANIFEST_PATH,
                "readback_manifest_without_contentBinding",
                "nextAction",
            ),
        ):
            fixture = self.completed()
            try:
                path = fixture.root / relative
                document = checker.strict_json(path.read_bytes(), "mutation")
                document[field] = "mutated"
                document = rebind(document, scope)
                path.write_bytes(checker.canonical_json_bytes(document))
                path.chmod(0o600)
                with self.assertRaises(checker.VerificationError):
                    checker.validate_state(fixture.root)
            finally:
                fixture.close()

    def test_04_original_result_and_review_manifest_drift_fail_closed(
        self,
    ) -> None:
        fixture = self.completed()
        try:
            path = fixture.root / checker.RESULT_PATH
            path.write_bytes(path.read_bytes()[:-1] + b" \n")
            with self.assertRaises(checker.VerificationError):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()
        fixture = self.completed()
        try:
            path = fixture.root / checker.REVIEW_MANIFEST_PATH
            document = checker.strict_json(path.read_bytes(), "manifest")
            document["graphSha256"] = "0" * 64
            document = rebind(document, "manifest_without_contentBinding")
            path.write_bytes(checker.canonical_json_bytes(document))
            path.chmod(0o600)
            with self.assertRaises(checker.VerificationError):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()

    def test_05_graph_count_digest_projection_and_reconstruction_rejected(
        self,
    ) -> None:
        baseline = graph_for("new_tuple_wave_required", mixed_external=True)
        mutations = []
        value = copy.deepcopy(baseline)
        value["graphEdgeCount"] = True
        mutations.append(value)
        value = copy.deepcopy(baseline)
        value["moduleGraphAndFrontierSha256"] = "0" * 64
        mutations.append(value)
        value = copy.deepcopy(baseline)
        value["selectedVersions"][0]["version"] = "v9.9.9"
        mutations.append(value)
        value = copy.deepcopy(baseline)
        value["exactFrontier"] = []
        mutations.append(value)
        value = copy.deepcopy(baseline)
        value["unmappedExternalImports"] = []
        mutations.append(value)
        value = copy.deepcopy(baseline)
        value["reconstructions"][0]["algorithm"] = (
            "version_vertex_monotone_full_set_scan"
        )
        mutations.append(value)
        value = copy.deepcopy(baseline)
        value["versionSpecificVertexTraversal"] = False
        mutations.append(value)
        value = copy.deepcopy(baseline)
        value["algorithm"] = "go1.24_mvs_version_vertex_profile_union_v2"
        mutations.append(value)
        for graph in mutations:
            with self.subTest(index=mutations.index(graph)):
                with self.assertRaises(checker.VerificationError):
                    checker.validate_graph(graph)

    def test_06_route_precedence_and_fixed_point_derivation(self) -> None:
        mixed = graph_for("new_tuple_wave_required", mixed_external=True)
        self.assertEqual(
            checker.validate_graph(mixed)["route"],
            "new_tuple_wave_required",
        )
        external = graph_for("external_import_resolution_required")
        self.assertEqual(
            checker.validate_graph(external)["route"],
            "external_import_resolution_required",
        )
        fixed = graph_for("fixed_point_candidate")
        self.assertTrue(checker.validate_graph(fixed)["fixedPointCandidate"])
        fixed["fixedPointReached"] = False
        with self.assertRaises(checker.VerificationError):
            checker.validate_graph(fixed)

    def test_07_partial_missing_or_unsafe_readback_outputs_fail_closed(
        self,
    ) -> None:
        fixture = self.completed()
        try:
            (fixture.root / checker.READBACK_MANIFEST_PATH).unlink()
            with self.assertRaises((checker.VerificationError, OSError)):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()
        fixture = self.completed()
        try:
            receipt = fixture.root / checker.READBACK_RECEIPT_PATH
            raw = receipt.read_bytes()
            receipt.unlink()
            target = receipt.with_name(".receipt-target")
            target.write_bytes(raw)
            target.chmod(0o600)
            receipt.symlink_to(target)
            with self.assertRaises((checker.VerificationError, OSError)):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()
        fixture = self.completed()
        try:
            claim = fixture.root / checker.READBACK_CLAIM_PATH
            claim.chmod(0o644)
            with self.assertRaises(checker.VerificationError):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()

    def test_08_hardlink_final_name_and_ancestor_replacement_fail_closed(
        self,
    ) -> None:
        fixture = self.completed()
        try:
            receipt = fixture.root / checker.READBACK_RECEIPT_PATH
            raw = receipt.read_bytes()
            sibling = receipt.with_name(".hardlink-source")
            sibling.write_bytes(raw)
            sibling.chmod(0o600)
            receipt.unlink()
            os.link(sibling, receipt)
            with self.assertRaises(checker.VerificationError):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()
        fixture = self.completed()
        try:
            with checker.VerificationInputs(fixture.root) as state:
                result = fixture.root / checker.RESULT_PATH
                replacement = result.with_name(".replacement")
                replacement.write_bytes(result.read_bytes())
                replacement.chmod(0o600)
                os.replace(replacement, result)
                with self.assertRaises(checker.VerificationError):
                    state.final_barrier()
        finally:
            fixture.close()
        fixture = self.completed()
        try:
            with checker.VerificationInputs(fixture.root) as state:
                ancestor = fixture.root / "docs" / "security-hardening"
                moved = fixture.root / "docs" / ".security-hardening-moved"
                os.rename(ancestor, moved)
                ancestor.mkdir()
                ancestor.chmod(0o755)
                with self.assertRaises((checker.VerificationError, OSError)):
                    state.final_barrier()
        finally:
            fixture.close()

    def test_09_bound_tool_and_no_auth_drift_fail_closed(self) -> None:
        fixture = self.completed()
        try:
            tool = fixture.root / checker.TOOL_PATHS["readback_checker"]
            tool.write_bytes(tool.read_bytes() + b"# drift\n")
            with self.assertRaises(checker.VerificationError):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()
        fixture = self.completed()
        try:
            receipt_path = fixture.root / checker.READBACK_RECEIPT_PATH
            receipt = checker.strict_json(
                receipt_path.read_bytes(), "receipt"
            )
            receipt["personalProjectBoundary"][
                "externalAuthenticationRequired"
            ] = True
            receipt = rebind(
                receipt, "readback_receipt_without_contentBinding"
            )
            receipt_path.write_bytes(checker.canonical_json_bytes(receipt))
            receipt_path.chmod(0o600)
            with self.assertRaises(checker.VerificationError):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()

    def test_10_strict_json_rejects_duplicates_float_and_noncanonical(
        self,
    ) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":1.0}\n',
            b'{"a":Infinity}\n',
        ):
            with self.assertRaises(checker.VerificationError):
                checker.strict_json(raw, "strict")
        canonical = checker.content_bound({"a": 1}, "x")
        raw = checker.canonical_json_bytes(canonical)
        with self.assertRaises(checker.VerificationError):
            checker.validate_content_binding(
                canonical, raw[:-1] + b" \n", "x", "noncanonical"
            )

    def test_11_verifier_has_no_record_or_write_surface(self) -> None:
        source = CHECKER_PATH.read_text()
        tree = ast.parse(source)
        imported = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imported.isdisjoint(
                {
                    "zipfile",
                    "tarfile",
                    "socket",
                    "subprocess",
                    "urllib",
                    "http",
                    "ssl",
                    "requests",
                    "aiohttp",
                    "importlib",
                    "runpy",
                }
            )
        )
        attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        self.assertTrue(
            attributes.isdisjoint(
                {
                    "write",
                    "write_bytes",
                    "write_text",
                    "O_WRONLY",
                    "O_RDWR",
                    "O_CREAT",
                    "O_EXCL",
                }
            )
        )
        functions = {
            node.name
            for node in tree.body
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        }
        self.assertNotIn("record_readback", functions)
        self.assertNotIn("write_exclusive", functions)
        self.assertNotIn("zipfile", source)

    def test_12_recovery_and_historical_binding_drift_fail_closed(
        self,
    ) -> None:
        for relative in (
            checker.V1_RECOVERY_DECISION_PATH,
            checker.RECOVERY_DECISION_PATH,
            checker.V1_PERMIT_PATH,
            checker.V1_REVIEW_CLAIM_PATH,
            checker.V1_FAILURE_PATH,
            checker.V2_PERMIT_PATH,
            checker.V2_REVIEW_CLAIM_PATH,
            checker.V2_FAILURE_PATH,
        ):
            fixture = self.completed()
            try:
                path = fixture.root / relative
                path.write_bytes(path.read_bytes()[:-1] + b" \n")
                with self.assertRaises(checker.VerificationError):
                    checker.validate_state(fixture.root)
            finally:
                fixture.close()

    def test_13_historical_absence_and_current_failure_are_enforced(
        self,
    ) -> None:
        for relative in (
            *checker.expected_v1_absent_paths(),
            *checker.expected_v2_absent_paths(),
        ):
            fixture = self.completed()
            try:
                path = fixture.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"historical backfill\n")
                path.chmod(0o600)
                with self.assertRaises(checker.VerificationError):
                    checker.validate_state(fixture.root)
            finally:
                fixture.close()
        fixture = self.completed()
        try:
            self.assertTrue((fixture.root / checker.V1_FAILURE_PATH).is_file())
            self.assertTrue((fixture.root / checker.V2_FAILURE_PATH).is_file())
            self.assertTrue(checker.validate_state(fixture.root)["validationPassed"])
            path = fixture.root / checker.FAILURE_PATH
            path.write_bytes(b"current v3 failure\n")
            path.chmod(0o600)
            with self.assertRaises(checker.VerificationError):
                checker.validate_state(fixture.root)
        finally:
            fixture.close()

    def test_14_receipt_and_manifest_carry_recovery_history(self) -> None:
        fixture = self.completed()
        try:
            expected_recovery = {
                "path": checker.RECOVERY_DECISION_PATH,
                "rawSha256": checker.sha256_bytes(
                    (fixture.root / checker.RECOVERY_DECISION_PATH).read_bytes()
                ),
                "contentSha256": fixture.recovery[
                    "contentBinding"
                ]["sha256"],
                "decisionId": checker.RECOVERY_DECISION_ID,
                "requiredStatus": checker.RECOVERY_DECISION_STATUS,
            }
            for relative in (
                checker.READBACK_RECEIPT_PATH,
                checker.READBACK_MANIFEST_PATH,
            ):
                document = checker.strict_json(
                    (fixture.root / relative).read_bytes(),
                    "readback output",
                )
                self.assertEqual(
                    document["recoveryDecisionBinding"],
                    expected_recovery,
                )
                self.assertEqual(
                    document["priorRecoveryDecisionBinding"],
                    fixture.recovery["priorRecoveryDecisionBinding"],
                )
                self.assertEqual(
                    document["failedAttemptBindings"],
                    fixture.recovery["failedAttemptBindings"],
                )
                self.assertEqual(
                    document["failedAttemptNamespaceContracts"],
                    fixture.recovery["failedAttemptNamespaceContracts"],
                )
        finally:
            fixture.close()

    def test_15_permit_validation_matches_recorder_safety_contract(self) -> None:
        fixture = SyntheticReviewFixture()
        try:
            mutations = (
                (
                    "manifestContract",
                    "independentReadbackRequired",
                    False,
                ),
                (
                    "authority",
                    "sourceMaterializationAuthorized",
                    True,
                ),
            )
            for section, field, value in mutations:
                permit = copy.deepcopy(fixture.permit)
                permit[section][field] = value
                permit = rebind(permit, "permit_without_contentBinding")
                raw = checker.canonical_json_bytes(permit)
                with self.subTest(field=field):
                    with self.assertRaises(checker.VerificationError):
                        checker.validate_permit(permit, raw)
        finally:
            fixture.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
