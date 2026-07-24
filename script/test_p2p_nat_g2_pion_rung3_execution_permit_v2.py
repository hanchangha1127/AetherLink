#!/usr/bin/env python3
"""No-archive tests for the G2 rung-three v2 execution-permit checker."""

from __future__ import annotations

import ast
import copy
import inspect
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_RELATIVE_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_permit_v2.py"
CHECKER_PATH = ROOT / CHECKER_RELATIVE_PATH
CHECKER_BYTES = CHECKER_PATH.read_bytes()
CHECKER_CODE = compile(
    CHECKER_BYTES,
    CHECKER_RELATIVE_PATH,
    "exec",
    flags=0,
    dont_inherit=True,
    optimize=0,
)
CHECKER = types.ModuleType("g2_rung3_v2_execution_permit_checker_under_test")
CHECKER.__dict__.update(
    {
        "__cached__": None,
        "__file__": str(CHECKER_PATH),
        "__loader__": None,
        "__package__": None,
    }
)
exec(CHECKER_CODE, CHECKER.__dict__, CHECKER.__dict__)


class V2ExecutionPermitCheckerTests(unittest.TestCase):
    def read_json(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_01_runner_api_is_exact(self) -> None:
        validate_signature = inspect.signature(CHECKER.validate_repository)
        loader_signature = inspect.signature(CHECKER.load_validated_review_modules)
        self.assertEqual(tuple(validate_signature.parameters), ("root",))
        self.assertEqual(tuple(loader_signature.parameters), ("root",))
        self.assertEqual(validate_signature.parameters["root"].default, CHECKER.ROOT)
        self.assertEqual(loader_signature.parameters["root"].default, CHECKER.ROOT)

    def test_02_strict_json_rejects_duplicate_cr_missing_lf_and_nonfinite(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":NaN}\n',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.strict_json(raw, "fixture")

    def test_03_safe_read_allowlist_excludes_build_and_archives(self) -> None:
        self.assertFalse(any(path.startswith("build/") for path in CHECKER.TRACKED_READ_ALLOWLIST))
        self.assertFalse(any(path.endswith(".zip") for path in CHECKER.TRACKED_READ_ALLOWLIST))
        self.assertTrue(
            CHECKER.AUTHORITY_READ_ALLOWLIST.isdisjoint(
                CHECKER.OBSERVATIONAL_READ_ALLOWLIST
            )
        )
        for unsafe in (
            "build/offline-source/archive.zip",
            "../escape",
            "/absolute",
            "docs\\escape",
        ):
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_relative_path(unsafe)

    def test_04_safe_reader_rejects_symlink_and_hardlink(self) -> None:
        for variant in ("symlink", "hardlink"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target = root / "target"
                target.write_bytes(b"safe\n")
                path = root / CHECKER.CHECKER_PATH
                path.parent.mkdir(parents=True)
                if variant == "symlink":
                    path.symlink_to(target)
                    pattern = "safe read failed"
                else:
                    os.link(target, path)
                    pattern = "single link"
                with self.assertRaisesRegex(CHECKER.CheckError, pattern):
                    CHECKER.SafeTrackedReader(root).read(CHECKER.CHECKER_PATH)

    def test_05_creator_policy_is_exact_and_rejects_mutation(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        CHECKER.validate_policy(policy)
        self.assertEqual(
            policy["creatorMetadataPolicy"]["acceptedMsDosRegularFileExternalAttributes"],
            ["00", "01", "20", "21"],
        )
        self.assertEqual(
            policy["creatorMetadataPolicy"]["syntheticReadOnlyRegularMode"],
            "100444",
        )
        self.assertIn(
            "not_archive_or_filesystem_mode_evidence",
            policy["creatorMetadataPolicy"]["syntheticModeMeaning"],
        )
        mutated = copy.deepcopy(policy)
        mutated["creatorMetadataPolicy"]["acceptedMsDosRegularFileExternalAttributes"].append("02")
        with self.assertRaisesRegex(CHECKER.CheckError, "creator metadata policy"):
            CHECKER.validate_policy(mutated)

    def test_06_exact_seven_to_eight_crosswalk_is_preserved(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        plan = policy["reviewPlan"]
        self.assertEqual(len(plan["patchUnits"]), 7)
        self.assertEqual(len(plan["verificationUnits"]), 8)
        self.assertEqual(plan["patchUnits"], CHECKER.EXPECTED_PATCH_UNITS)
        self.assertEqual(plan["verificationUnits"], CHECKER.EXPECTED_VERIFICATION_UNITS)
        self.assertEqual(plan["verificationCrosswalk"], CHECKER.EXPECTED_CROSSWALK)

    def test_07_v1_is_consumed_immutable_and_v2_names_are_distinct(self) -> None:
        permit = self.read_json(CHECKER.PERMIT_PATH)
        boundary = permit["predecessorFailureBoundary"]
        self.assertTrue(boundary["permitV1Consumed"])
        self.assertFalse(boundary["permitV1RetryAllowed"])
        self.assertTrue(boundary["permitV1ClaimRetained"])
        self.assertFalse(boundary["permitV1MutationAllowed"])
        output = permit["outputContract"]
        self.assertEqual(output["directory"], "build/offline-source/pion-ice-v4.3.0/review-v2")
        self.assertEqual(
            output["claimFileName"],
            ".g2-pion-ice-v4.3.0-rung3-offline-review-v2.claim",
        )
        self.assertTrue(output["temporaryBackingFilesRetainedOnSuccessOrFailure"])
        self.assertFalse(output["temporaryNameDeletionAllowed"])
        self.assertEqual(output["publishedFinalLinkCount"], 2)
        self.assertTrue(output["sameUidHostileConcurrentFilesystemMutationOutOfScope"])
        self.assertTrue(
            output["runtimePublicationRequiresPostRunReadbackForCanonicalEvidence"]
        )
        self.assertNotIn("review-v1", json.dumps(output, sort_keys=True))

    def test_08_no_identity_or_user_action_gate_and_all_completion_claims_false(self) -> None:
        for path in (CHECKER.POLICY_PATH, CHECKER.PERMIT_PATH):
            document = self.read_json(path)
            personal = document["personalProjectBoundary"]
            self.assertFalse(personal["repositoryOwnerAuthenticationRequired"])
            self.assertFalse(personal["externalIdentityProofRequired"])
            self.assertFalse(personal["userActionRequired"])
            self.assertTrue(personal["productEndpointAuthenticationRequired"])
            self.assertIn("runtime_product_boundary_only", personal["productEndpointAuthenticationMeaning"])
            self.assertTrue(all(value is False for value in document["nonClaims"].values()))

    def test_09_compiler_accounting_is_unambiguous(self) -> None:
        for path in (CHECKER.POLICY_PATH, CHECKER.PERMIT_PATH):
            document = self.read_json(path)
            accounting = document["compilerAccounting"]
            self.assertEqual(accounting, CHECKER.EXPECTED_COMPILER_ACCOUNTING)
            self.assertEqual(accounting["preflightVerifiedAuxiliaryToolModulePythonCompileCount"], 1)
            self.assertEqual(accounting["executionVerifiedAuxiliaryToolModulePythonCompileCount"], 3)
            self.assertEqual(accounting["reviewedSourceCompilerInvocationCount"], 0)
            isolation = document["interpreterIsolationContract"]
            self.assertEqual(isolation, CHECKER.EXPECTED_ISOLATION)
            self.assertEqual(isolation["requiredSysFlags"]["no_site"], 1)
            self.assertFalse(isolation["systemSiteInitializationAllowed"])
            self.assertFalse(isolation["sitePackagesAllowed"])
            self.assertTrue(isolation["trustedInterpreterStdlibBytecodeReadAllowed"])

    def test_10_source_ast_boundaries_pass_and_forbidden_mutations_fail(self) -> None:
        base = (ROOT / CHECKER.BASE_VALIDATOR_PATH).read_bytes()
        overlay = (ROOT / CHECKER.OVERLAY_PATH).read_bytes()
        runner = (ROOT / CHECKER.RUNNER_PATH).read_bytes()
        CHECKER.validate_base_source(base)
        CHECKER.validate_overlay_source(overlay)
        CHECKER.validate_runner_source(runner)
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_base_source(base + b"\nimport socket\n")
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_overlay_source(overlay + b"\nopen('x')\n")
        with self.assertRaises(CHECKER.CheckError):
            CHECKER.validate_runner_source(runner + b"\nimport subprocess\n")

    def test_11_overlay_api_has_base_bytes_first(self) -> None:
        source = (ROOT / CHECKER.OVERLAY_PATH).read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "inspect_module_zip"
        )
        self.assertGreaterEqual(len(function.args.args), 2)
        self.assertEqual(function.args.args[0].arg, "base_validator_source")
        self.assertEqual(function.args.args[1].arg, "raw_archive")

    def test_12_repository_and_adapter_validation_pass_without_archive(self) -> None:
        observed: list[str] = []
        original_read = CHECKER.SafeTrackedReader.read

        def read_probe(reader, path):
            observed.append(path)
            return original_read(reader, path)

        with mock.patch.object(CHECKER.SafeTrackedReader, "read", read_probe):
            result = CHECKER.validate_repository(ROOT)
            adapter = CHECKER.load_validated_review_modules(ROOT)
        self.assertEqual(
            set(result),
            {"permit", "permitRawSha256", "permitSemanticSha256"},
        )
        self.assertEqual(result["permitRawSha256"], CHECKER.EXPECTED_PERMIT_RAW)
        self.assertTrue(set(observed).isdisjoint(CHECKER.OBSERVATIONAL_READ_ALLOWLIST))
        self.assertTrue(set(observed) <= CHECKER.AUTHORITY_READ_ALLOWLIST)
        self.assertTrue(callable(adapter.inspect_module_zip))
        closure_values = [
            cell.cell_contents
            for cell in adapter.inspect_module_zip.__closure__ or ()
        ]
        self.assertTrue(
            any(
                isinstance(value, bytes)
                and CHECKER.sha256_bytes(value) == CHECKER.EXPECTED_BASE_RAW
                for value in closure_values
            )
        )

    def test_13_core_and_checker_manifests_are_acyclic(self) -> None:
        core = self.read_json(CHECKER.CORE_MANIFEST_PATH)
        checker = self.read_json(CHECKER.CHECKER_MANIFEST_PATH)
        core_paths = [row["path"] for row in core["artifacts"]]
        self.assertEqual(
            [row["evidenceId"] for row in core["artifacts"]],
            [f"G2R3E{index:03d}" for index in range(28, 34)],
        )
        self.assertNotIn(CHECKER.RUNNER_PATH, core_paths)
        self.assertNotIn(CHECKER.RUNNER_TEST_PATH, core_paths)
        self.assertNotIn(CHECKER.CHECKER_PATH, core_paths)
        self.assertNotIn(CHECKER.CHECKER_TEST_PATH, core_paths)
        self.assertEqual(
            [row["evidenceId"] for row in checker["artifacts"]],
            [f"G2R3E{index:03d}" for index in range(34, 38)],
        )
        self.assertEqual(
            checker["predecessorManifestBinding"]["path"],
            CHECKER.CORE_MANIFEST_PATH,
        )
        self.assertNotIn("rawSha256", checker.get("trustBoundary", {}))
        self.assertFalse(checker["trustBoundary"]["executionAuthority"])
        self.assertFalse(checker["trustBoundary"]["requiredForPermitValidation"])
        self.assertFalse(checker["trustBoundary"]["requiredForPermitExecution"])

    def test_14_checker_source_has_no_build_or_archive_read_literal(self) -> None:
        source = CHECKER_BYTES.decode("utf-8")
        self.assertNotIn("build/offline-source/pion-ice-v4.3.0/original", source)
        self.assertFalse(any(path.endswith(".zip") for path in CHECKER.TRACKED_READ_ALLOWLIST))
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertTrue(imports.isdisjoint({"socket", "subprocess", "urllib", "requests"}))

    def test_15_evidence_suite_is_separate_and_runner_pins_checker_bytes(self) -> None:
        result = CHECKER.validate_evidence_suite(ROOT)
        self.assertTrue(result["observationalEvidenceValidated"])
        runner_source = (ROOT / CHECKER.RUNNER_PATH).read_text(encoding="utf-8")
        checker_hash = CHECKER.sha256_bytes(CHECKER_BYTES)
        self.assertIn(checker_hash, runner_source)
        runner_test_source = (ROOT / CHECKER.RUNNER_TEST_PATH).read_text(encoding="utf-8")
        self.assertIn('"EXPECTED_CHECKER_RAW_SHA256", "0" * 64', runner_test_source)
        self.assertIn("raw digest mismatch", runner_test_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
