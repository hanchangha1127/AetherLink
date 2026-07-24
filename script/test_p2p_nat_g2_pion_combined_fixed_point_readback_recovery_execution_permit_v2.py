#!/usr/bin/env python3
"""Tests for the combined recovery readback permit v2."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (sys.flags.isolated and sys.flags.dont_write_bytecode and sys.flags.no_site):
    raise RuntimeError("tests require `python3 -I -B -S`")

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v2.py"
)
SPEC = importlib.util.spec_from_file_location("recovery_permit_v2", PATH)
assert SPEC and SPEC.loader
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class RecoveryPermitV2Tests(unittest.TestCase):
    def test_01_live_exact_permit(self) -> None:
        expected, summary = P.evaluate(True)
        actual = json.loads((P.ROOT / P.PERMIT_PATH).read_bytes())
        self.assertEqual(actual, expected)
        self.assertTrue(summary["validationPassed"])
        self.assertFalse(summary["readbackRecordingAuthorized"])
        self.assertFalse(summary["recordable"])
        self.assertTrue(summary["namespaceRecordableShape"])
        self.assertFalse(summary["executionAuthorized"])
        self.assertFalse(summary["freshRecomputationPerformed"])
        self.assertEqual(summary["archiveMemberDecodeCount"], 0)

    def test_02_exact_recovery_and_tool_freeze(self) -> None:
        context = P.ExecutionAuthorityContext(
            P.ROOT,
            include_permit=True,
            phase="recordable",
        )
        try:
            expected = P.expected_permit(context)
            self.assertEqual(
                expected["recoveryDecisionBinding"]["rawSha256"],
                P.EXPECTED_RECOVERY_RAW,
            )
            self.assertEqual(
                P.normalized_recorder_sha256(
                    context.package.raw[P.RECORDER_PATH]
                ),
                P.EXPECTED_RECORDER_NORMALIZED_SHA256,
            )
        finally:
            context.close()

    def test_03_normalized_parser_rejects_rebinds(self) -> None:
        good = (
            'EXPECTED_PERMIT_CHECKER_RAW_SHA256 = "' + "a" * 64 + '"\n'
        )
        value, start, end = P.unique_module_string_assignment(
            good,
            P.REVERSE_PIN_NAME,
        )
        self.assertEqual(value, "a" * 64)
        self.assertEqual(end - start, 64)
        bad = (
            good + 'EXPECTED_PERMIT_CHECKER_RAW_SHA256 = "' + "b" * 64 + '"\n',
            good + "\ndef f(EXPECTED_PERMIT_CHECKER_RAW_SHA256):\n pass\n",
            "def f():\n EXPECTED_PERMIT_CHECKER_RAW_SHA256 = "
            + '"' + "a" * 64 + '"\n',
            "EXPECTED_PERMIT_CHECKER_RAW_SHA256 = '"
            + "a" * 64 + "'\n",
            "EXPECTED_PERMIT_CHECKER_RAW_SHA256 = f\""
            + "a" * 64 + "\"\n",
            good
            + "\nmatch {}:\n case {**EXPECTED_PERMIT_CHECKER_RAW_SHA256}:\n"
            + "  pass\n",
            good
            + "\nmatch []:\n case [*EXPECTED_PERMIT_CHECKER_RAW_SHA256]:\n"
            + "  pass\n",
            good
            + "\nmatch None:\n case EXPECTED_PERMIT_CHECKER_RAW_SHA256:\n"
            + "  pass\n",
        )
        for source in bad:
            with self.assertRaises(P.PermitError):
                P.unique_module_string_assignment(source, P.REVERSE_PIN_NAME)

    def namespace(self, root: Path):
        os.chmod(root, 0o700)
        (root / P.DEPENDENCY_ROOT).mkdir(parents=True)
        (root / P.BASE).mkdir(parents=True)
        return P.RECOVERY.TRUST.HeldNamespace(root)

    def test_04_exhaustive_phase_table_and_collisions(self) -> None:
        for phase in (
            "recordable",
            "after_claim",
            "failure",
            "after_receipt",
            "complete",
        ):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                namespace = self.namespace(root)
                try:
                    for path, present in zip(P.V2_PATHS, P.phase_shape(phase)):
                        if present:
                            target = root / path
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(b"x")
                    self.assertEqual(P.classify_phase(namespace), phase)
                    if phase not in {"recordable", "complete"}:
                        collision = {
                            "after_claim": P.V2_MANIFEST_PATH,
                            "failure": P.V2_RECEIPT_PATH,
                            "after_receipt": P.V2_FAILURE_PATH,
                        }[phase]
                        target = root / collision
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(b"x")
                        self.assertEqual(P.classify_phase(namespace), "blocked")
                finally:
                    namespace.close()

    def test_05_retained_dirfd_sees_swap_restore_and_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            namespace = self.namespace(root)
            dependency = root / P.DEPENDENCY_ROOT
            moved = dependency.with_name("dependencies-held")
            try:
                dependency.rename(moved)
                dependency.mkdir()
                (moved / P.V2_CLAIM_PATH.rsplit("/", 1)[-1]).write_bytes(b"x")
                (moved / f"{P.V2_STAGING_PREFIX}x").mkdir()
                self.assertEqual(P.classify_phase(namespace), "after_claim")
                self.assertIn(
                    f"{P.V2_STAGING_PREFIX}x",
                    P.RECOVERY.held_dependency_names(namespace),
                )
            finally:
                dependency.rmdir()
                moved.rename(dependency)
                namespace.final_barrier()
                namespace.close()

    def test_06_authority_mutation_fails(self) -> None:
        context = P.ExecutionAuthorityContext(
            P.ROOT,
            include_permit=True,
            phase="recordable",
        )
        try:
            expected = P.expected_permit(context)
        finally:
            context.close()
        changed = copy.deepcopy(expected)
        changed["authority"]["networkAuthorized"] = True
        self.assertNotEqual(changed, expected)
        changed = copy.deepcopy(expected)
        changed["oneUseContract"]["secondInvocationResumeAllowed"] = True
        self.assertNotEqual(changed, expected)
        self.assertFalse(
            expected["oneUseContract"]["formalRecordAttemptAuthorized"]
        )
        self.assertNotIn(
            "claimBeforeArchiveMemberOpenOrDecode",
            expected["oneUseContract"],
        )
        observation = expected["priorDraftDiagnosticObservation"]
        self.assertTrue(observation["freshRecomputationOccurred"])
        self.assertTrue(
            observation["freshRecomputationOccurredBeforeClaim"]
        )
        self.assertFalse(observation["acceptedAsEvidence"])
        self.assertEqual(observation["fileWriteCount"], 0)
        self.assertEqual(
            observation["authorityConsumptionState"],
            "consumed_or_uncertain",
        )
        for key in (
            "oneOfflineReadbackAuthorized",
            "claimWriteAuthorized",
            "receiptOrFailureWriteAuthorized",
            "manifestOnSuccessWriteAuthorized",
        ):
            self.assertFalse(expected["authority"][key])
        self.assertEqual(
            expected["nextAction"],
            "prepare_separate_v3_recovery_decision_and_one_use_permit",
        )

    def test_06a_wrong_reverse_pin_fails_tool_freeze(self) -> None:
        context = P.ExecutionAuthorityContext(
            P.ROOT,
            include_permit=True,
            phase="recordable",
        )
        try:
            recorder = context.package.raw[P.RECORDER_PATH]
            context.package.raw[P.RECORDER_PATH] = recorder.replace(
                P.sha256(context.package.raw[P.THIS_CHECKER_PATH]).encode(),
                b"f" * 64,
                1,
            )
            with self.assertRaises(P.PermitError) as caught:
                P.expected_permit(context)
            self.assertEqual(caught.exception.code, "E_TOOL_FREEZE")
        finally:
            context.close()

    def test_07_direct_payload_calls_and_forbidden_calls(self) -> None:
        source = PATH.read_text()
        for token in (
            "self.decision_checker.expected_payload(",
            "self.original_permit_checker.expected_payload(self)",
            "validate_decision_bytes(",
            "validate_permit_bytes(",
        ):
            self.assertIn(token, source)
        for token in (
            ".expected_decision(",
            ".evaluate(",
            ".check_repository(",
            "generate_candidate(",
        ):
            self.assertNotIn(token, source)

    def test_08_reader_and_static_forbidden_surfaces(self) -> None:
        self.assertEqual((P.ROOT / P.PERMIT_READER_PATH).read_bytes(), P.READER_BYTES)
        self.assertNotIn(
            b"claim before archive-member decode",
            P.READER_BYTES,
        )
        self.assertIn(
            b"authority as consumed or\nuncertain",
            P.READER_BYTES,
        )
        self.assertIn(b"separate v3 recovery decision", P.READER_BYTES)
        source = PATH.read_text()
        for token in (
            "urllib.",
            "socket.",
            "subprocess.",
            "write_text(",
            "write_bytes(",
            "os.write(",
        ):
            self.assertNotIn(token, source)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=P.ROOT,
            capture_output=True,
            check=False,
        )

    def test_09_print_cmp_default_and_invalid_cli(self) -> None:
        printed = self.run_cli("--print-expected")
        self.assertEqual(printed.returncode, 0)
        self.assertEqual(printed.stderr, b"")
        self.assertEqual(printed.stdout, (P.ROOT / P.PERMIT_PATH).read_bytes())
        default = self.run_cli()
        self.assertEqual(default.returncode, 0)
        self.assertTrue(json.loads(default.stdout)["validationPassed"])
        invalid = self.run_cli("--secret-value")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"secret-value", invalid.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
