#!/usr/bin/env python3
"""Isolation and schema tests for the preparation-only G2 rung-three decision."""

from __future__ import annotations

import ast
import builtins
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "script/prepare_p2p_nat_g2_pion_rung3_review_decision.py"
SPEC = importlib.util.spec_from_file_location("g2_rung3_decision_preparer", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to import G2 rung-three decision preparer")
PREPARER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARER)


class G2PionRungThreeDecisionPreparationTests(unittest.TestCase):
    def test_01_source_surface_has_no_filesystem_archive_process_or_network_import(self) -> None:
        source = SCRIPT_PATH.read_bytes()
        self.assertNotIn(b"build/", source)
        self.assertNotIn(b".zip", source)
        self.assertNotIn(b"retainedArchivePath", source)
        tree = ast.parse(source.decode("utf-8"))
        imports: set[str] = set()
        calls: set[str] = set()
        argument_flags: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
                    if node.func.attr == "add_argument":
                        argument_flags.extend(
                            argument.value
                            for argument in node.args
                            if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                        )
        self.assertTrue(
            imports.isdisjoint(
                {
                    "asyncio", "ctypes", "http", "multiprocessing", "os", "pathlib",
                    "requests", "shutil", "socket", "subprocess", "urllib", "zipfile",
                }
            )
        )
        self.assertTrue(
            calls.isdisjoint(
                {
                    "open", "read_bytes", "read_text", "write_bytes", "write_text",
                    "compile", "eval", "exec", "popen", "run", "system", "urlopen",
                }
            )
        )
        self.assertEqual(sorted(argument_flags), ["--check", "--emit-decision"])
        for forbidden in ("--execute", "--archive", "--output", "--path"):
            self.assertNotIn(forbidden, argument_flags)

    def test_02_decision_has_exact_required_state_result_and_next_action(self) -> None:
        decision = PREPARER.validate_decision(PREPARER.build_decision())
        self.assertEqual(
            decision["status"],
            "rung3_review_plan_recorded_execution_not_authorized",
        )
        self.assertEqual(
            decision["result"],
            "retained_archive_metadata_bound_preparation_only",
        )
        self.assertEqual(
            decision["nextAction"],
            "prepare_separate_versioned_rung3_review_execution_permit",
        )
        self.assertFalse(decision["archiveBinding"]["archiveReadByThisDecision"])
        self.assertFalse(decision["archiveBinding"]["archiveMaterializedByThisDecision"])
        self.assertFalse(decision["archiveBinding"]["sourceReviewedByThisDecision"])

    def test_03_decision_is_byte_deterministic_and_fresh_per_call(self) -> None:
        first = PREPARER.build_decision()
        second = PREPARER.build_decision()
        self.assertEqual(
            PREPARER.canonical_json_bytes(first),
            PREPARER.canonical_json_bytes(second),
        )
        first["plannedStaticReview"]["patchUnits"].append("mutation")
        self.assertEqual(len(second["plannedStaticReview"]["patchUnits"]), 7)

    def test_04_content_binding_covers_exact_core(self) -> None:
        decision = PREPARER.build_decision()
        core = {key: value for key, value in decision.items() if key != "contentBinding"}
        self.assertEqual(
            decision["contentBinding"]["sha256"],
            PREPARER.sha256_bytes(PREPARER.canonical_json_bytes(core)),
        )
        self.assertRegex(decision["contentBinding"]["sha256"], r"^[0-9a-f]{64}$")

    def test_05_all_execution_and_authentication_boundary_flags_are_false(self) -> None:
        decision = PREPARER.build_decision()
        self.assertEqual(set(decision["decisionBoundary"]), set(PREPARER.FALSE_BOUNDARY_KEYS))
        self.assertTrue(
            all(value is False for value in decision["decisionBoundary"].values())
        )
        self.assertFalse(decision["decisionBoundary"]["reviewExecutionAuthorized"])
        self.assertFalse(decision["decisionBoundary"]["repositoryOwnerAuthenticationRequired"])
        self.assertFalse(decision["decisionBoundary"]["externalIdentityProofRequired"])
        self.assertFalse(decision["decisionBoundary"]["userActionRequired"])

    def test_06_exact_seven_patch_units_and_required_review_dimensions_are_planned(self) -> None:
        decision = PREPARER.build_decision()
        units = decision["plannedStaticReview"]["patchUnits"]
        self.assertEqual(len(units), 7)
        self.assertEqual(len(set(units)), 7)
        self.assertEqual(units, list(PREPARER.PATCH_UNITS))
        topics = decision["plannedStaticReview"]["reviewTopics"]
        self.assertIn("go_lexical_and_ast_like_token_scan_without_execution", topics)
        self.assertIn("go_mod_and_go_sum_dependency_metadata_parsing", topics)
        self.assertIn("license_and_notice_inventory_without_legal_conclusion", topics)
        self.assertEqual(
            decision["plannedStaticReview"]["profileVerificationUnits"],
            [
                {"id": unit_id, "status": "planned_not_performed"}
                for unit_id in PREPARER.PROFILE_RUNG3_VERIFICATION_IDS
            ],
        )

    def test_07_archive_metadata_is_bound_without_observation(self) -> None:
        decision = PREPARER.build_decision()
        binding = decision["archiveBinding"]
        self.assertEqual(binding["expectedBytes"], 293023)
        self.assertEqual(binding["entryCount"], 129)
        self.assertEqual(binding["fileCount"], 129)
        self.assertEqual(binding["totalUncompressedBytes"], 1131286)
        self.assertEqual(
            binding["rawSha256"],
            "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
        )
        self.assertEqual(binding["modulePrefix"], "github.com/pion/ice/v4@v4.3.0/")
        self.assertEqual(binding["treeSha1"], "df59c87a634cfea261582cd9932554663112a975")
        self.assertEqual(binding["moduleH1"], "h1:X8l4s9zV2HeTKX33nulWAFXAEo5KhIVzOsY62/3t/LM=")
        self.assertEqual(binding["goModH1"], "h1:obAyD+J+Hzs7QA7Y8YXHp5uIn6gb7z87pKedXZkrcFU=")
        self.assertTrue(binding["retained"])
        self.assertEqual(binding["archiveEvidenceId"], "G2R2E009")
        self.assertEqual(binding["archiveMetadataJsonPointer"], "/archive")
        self.assertFalse(binding["archivePathCopiedIntoDecision"])
        self.assertNotIn("retainedArchivePath", binding)
        self.assertEqual(
            decision["preparationScope"]["archiveBytesRead"], 0
        )
        self.assertEqual(
            decision["policyBinding"],
            {
                "path": "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/preparation-sandbox-policy-v1.json",
                "rawSha256": "c615da9fb80d7af0162077503b55663cf428aaee434cef61a67807c234ea3558",
                "semanticSha256": "bf5de358234c03a5bfc96b66d4fd8b5f0464328f4733820899ce0f93219be64a",
                "bindingSource": "compile_time_constants_only_policy_file_not_read",
            },
        )
        predecessors = decision["predecessorBindings"]
        self.assertEqual(set(predecessors), set(PREPARER.PREDECESSOR_BINDINGS))
        profile = predecessors["restrictedForkProfile"]
        self.assertEqual(profile["status"], "rung1_profile_complete_candidate_not_selected")
        self.assertEqual(profile["implementationStatus"], "not_implemented")
        self.assertEqual(
            profile["verificationStatus"],
            "design_validator_passed_runtime_not_executed",
        )
        self.assertNotIn("result", profile)
        self.assertEqual(
            predecessors["canonicalEvidenceManifestV5"]["collectionSha256"],
            "adb1fbce766b0750e186285024156abea290d80763eea142420192aa8261d0a8",
        )
        for forward in decision["forwardOnlyBindings"].values():
            self.assertEqual(forward["binding"], "forward_identity_only_no_sha256")
            self.assertFalse(any("sha256" in key.casefold() for key in forward))

    def test_08_strict_validation_rejects_unknown_missing_or_changed_values(self) -> None:
        mutations = []
        unknown = PREPARER.build_decision()
        unknown["unknown"] = False
        mutations.append(unknown)
        missing = PREPARER.build_decision()
        del missing["nextAction"]
        mutations.append(missing)
        changed = PREPARER.build_decision()
        changed["status"] = "execution_authorized"
        mutations.append(changed)
        type_changed = PREPARER.build_decision()
        type_changed["preparationScope"]["repositoryFilesRead"] = False
        mutations.append(type_changed)
        for mutation in mutations:
            with self.subTest(keys=sorted(mutation)):
                with self.assertRaises(PREPARER.DecisionValidationError):
                    PREPARER.validate_decision(mutation)

    def test_09_strict_validation_rejects_digest_and_boundary_mutation(self) -> None:
        digest_mutation = PREPARER.build_decision()
        digest_mutation["contentBinding"]["sha256"] = "0" * 64
        with self.assertRaises(PREPARER.DecisionValidationError):
            PREPARER.validate_decision(digest_mutation)
        boundary_mutation = PREPARER.build_decision()
        boundary_mutation["decisionBoundary"]["archiveRead"] = True
        with self.assertRaises(PREPARER.DecisionValidationError):
            PREPARER.validate_decision(boundary_mutation)

    def test_10_check_mode_is_default_and_emits_only_validation_json(self) -> None:
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdout", stdout):
            self.assertEqual(PREPARER.main([]), 0)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["status"], "passed")
        self.assertFalse(output["archiveRead"])
        self.assertFalse(output["filesystemRead"])
        self.assertFalse(output["filesystemWrite"])
        self.assertFalse(output["repositoryOwnerAuthenticationRequired"])
        self.assertFalse(output["externalIdentityProofRequired"])
        self.assertTrue(output["productEndpointAuthenticationRequired"])
        self.assertFalse(output["userActionRequired"])
        self.assertFalse(PREPARER.build_decision()["decisionBoundary"]["filesystemRead"])
        self.assertFalse(PREPARER.build_decision()["decisionBoundary"]["filesystemWrite"])

    def test_11_explicit_check_matches_default(self) -> None:
        default_stdout = io.StringIO()
        explicit_stdout = io.StringIO()
        with mock.patch.object(sys, "stdout", default_stdout):
            self.assertEqual(PREPARER.main([]), 0)
        with mock.patch.object(sys, "stdout", explicit_stdout):
            self.assertEqual(PREPARER.main(["--check"]), 0)
        self.assertEqual(default_stdout.getvalue(), explicit_stdout.getvalue())

    def test_12_emit_decision_writes_canonical_payload_to_stdout_only(self) -> None:
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdout", stdout):
            self.assertEqual(PREPARER.main(["--emit-decision"]), 0)
        emitted = stdout.getvalue().encode("ascii")
        self.assertNotIn(b"build/", emitted)
        self.assertNotIn(b".zip", emitted)
        self.assertNotIn(b"retainedArchivePath", emitted)
        decision = json.loads(emitted)
        PREPARER.validate_decision(decision)
        self.assertEqual(emitted, PREPARER.canonical_json_bytes(decision))

    def test_13_forbidden_cli_surfaces_are_absent_and_fail_parsing(self) -> None:
        for forbidden in ("--execute", "--archive", "--output", "--path"):
            with self.subTest(flag=forbidden):
                with (
                    mock.patch.object(sys, "stderr", io.StringIO()),
                    self.assertRaises(SystemExit) as raised,
                ):
                    PREPARER.main([forbidden])
                self.assertEqual(raised.exception.code, 2)

    def test_14_runtime_mock_hooks_observe_zero_file_archive_process_network_or_git_access(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(sys, "stdout", stdout),
            mock.patch.object(builtins, "open", side_effect=AssertionError("file open forbidden")) as open_mock,
            mock.patch.object(Path, "open", side_effect=AssertionError("Path.open forbidden")) as path_open,
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read forbidden")) as read_bytes,
            mock.patch.object(Path, "read_text", side_effect=AssertionError("read forbidden")) as read_text,
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write forbidden")) as write_bytes,
            mock.patch.object(Path, "write_text", side_effect=AssertionError("write forbidden")) as write_text,
            mock.patch.object(os, "open", side_effect=AssertionError("os.open forbidden")) as os_open,
            mock.patch.object(zipfile, "ZipFile", side_effect=AssertionError("ZIP access forbidden")) as zip_open,
            mock.patch.object(socket, "socket", side_effect=AssertionError("socket forbidden")) as socket_mock,
            mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")) as dns_mock,
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process forbidden")) as popen_mock,
            mock.patch.object(subprocess, "run", side_effect=AssertionError("process forbidden")) as run_mock,
            mock.patch.object(subprocess, "check_output", side_effect=AssertionError("Git/process forbidden")) as output_mock,
        ):
            self.assertEqual(PREPARER.main(["--emit-decision"]), 0)
        for observed in (
            open_mock, path_open, read_bytes, read_text, write_bytes, write_text,
            os_open, zip_open, socket_mock, dns_mock, popen_mock, run_mock, output_mock,
        ):
            observed.assert_not_called()
        self.assertEqual(
            json.loads(stdout.getvalue())["status"],
            "rung3_review_plan_recorded_execution_not_authorized",
        )

    def test_15_build_and_validate_are_pure_under_the_same_mock_hooks(self) -> None:
        expected = PREPARER.canonical_json_bytes(PREPARER.build_decision())
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("file open forbidden")) as open_mock,
            mock.patch.object(os, "open", side_effect=AssertionError("os.open forbidden")) as os_open,
            mock.patch.object(zipfile, "ZipFile", side_effect=AssertionError("ZIP access forbidden")) as zip_open,
            mock.patch.object(socket, "socket", side_effect=AssertionError("socket forbidden")) as socket_mock,
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process forbidden")) as popen_mock,
        ):
            actual = PREPARER.canonical_json_bytes(
                PREPARER.validate_decision(PREPARER.build_decision())
            )
        self.assertEqual(actual, expected)
        for observed in (open_mock, os_open, zip_open, socket_mock, popen_mock):
            observed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
