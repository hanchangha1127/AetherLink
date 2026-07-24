#!/usr/bin/env python3
"""Tests for the one-use replacement recovery permit v3."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (sys.flags.isolated and sys.flags.dont_write_bytecode and sys.flags.no_site):
    raise RuntimeError("tests require `python3 -I -B -S`")

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
    "readback_recovery_execution_permit_v3.py"
)
SPEC = importlib.util.spec_from_file_location("recovery_permit_v3", PATH)
assert SPEC and SPEC.loader
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class RecoveryPermitV3Tests(unittest.TestCase):
    def test_01_live_exact_permit(self) -> None:
        expected, summary = P.evaluate(True)
        self.assertEqual(
            json.loads((P.ROOT / P.PERMIT_PATH).read_bytes()), expected
        )
        self.assertTrue(summary["validationPassed"])
        self.assertTrue(summary["recordable"])
        self.assertTrue(summary["readbackRecordingAuthorized"])
        self.assertFalse(summary["executionAuthorized"])
        self.assertFalse(summary["freshRecomputationPerformed"])
        self.assertEqual(summary["archiveMemberDecodeCount"], 0)

    def test_02_decision_v2_closure_and_original_bindings(self) -> None:
        expected, _ = P.evaluate(False)
        self.assertEqual(
            expected["decisionBinding"]["rawSha256"],
            P.EXPECTED_DECISION_RAW,
        )
        self.assertEqual(
            expected["decisionBinding"]["contentSha256"],
            P.EXPECTED_DECISION_CONTENT,
        )
        self.assertEqual(expected["originalEvidenceBinding"]["heldSourceInputCount"], 69)
        self.assertEqual(
            expected["v2ClosureBinding"]["authorityConsumptionState"],
            "consumed_or_uncertain",
        )

    def test_03_ast_freeze_rejects_rebinding_and_patterns(self) -> None:
        good = 'EXPECTED_PERMIT_CHECKER_RAW_SHA256 = "' + "a" * 64 + '"\n'
        value, start, end = P.unique_module_string_assignment(
            good, P.REVERSE_PIN_NAME
        )
        self.assertEqual(value, "a" * 64)
        self.assertEqual(end - start, 64)
        for bad in (
            good + 'EXPECTED_PERMIT_CHECKER_RAW_SHA256 = "' + "b" * 64 + '"\n',
            good + "\ndef f(EXPECTED_PERMIT_CHECKER_RAW_SHA256):\n pass\n",
            good
            + "\nmatch {}:\n case {**EXPECTED_PERMIT_CHECKER_RAW_SHA256}:\n"
            + "  pass\n",
            "EXPECTED_PERMIT_CHECKER_RAW_SHA256 = '" + "a" * 64 + "'\n",
        ):
            with self.assertRaises(P.PermitError):
                P.unique_module_string_assignment(bad, P.REVERSE_PIN_NAME)

    def test_04_exact_phase_state_machine_and_collisions(self) -> None:
        for phase in (
            "recordable",
            "after_claim",
            "failure",
            "after_receipt",
            "complete",
        ):
            self.assertEqual(len(P.phase_shape(phase)), 4)
        self.assertEqual(P.phase_shape("recordable"), (False,) * 4)
        self.assertEqual(P.phase_shape("complete"), (True, True, False, True))
        shapes = {
            P.phase_shape(phase)
            for phase in (
                "recordable",
                "after_claim",
                "failure",
                "after_receipt",
                "complete",
            )
        }
        self.assertEqual(len(shapes), 5)

    def test_05_all_nonreadback_authority_is_false(self) -> None:
        expected, _ = P.evaluate(False)
        authority = expected["authority"]
        for key in (
            "originalEvaluationAuthorized",
            "networkAuthorized",
            "gitWriteAuthorized",
            "sourceExecutionAuthorized",
            "filesystemExtractionAuthorized",
            "subprocessAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "externalAuthenticationRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ):
            self.assertFalse(authority[key])
        self.assertTrue(authority["oneOfflineReadbackAuthorized"])

    def test_06_no_retry_resume_or_backfill(self) -> None:
        expected, _ = P.evaluate(False)
        contract = expected["oneUseContract"]
        for key in (
            "automaticRetryAllowed",
            "resumeAllowed",
            "claimBackfillAllowed",
            "receiptBackfillAllowed",
            "manifestBackfillAllowed",
            "failureAfterReceiptAttemptAllowed",
        ):
            self.assertFalse(contract[key])
        changed = copy.deepcopy(expected)
        changed["oneUseContract"]["resumeAllowed"] = True
        self.assertNotEqual(changed, expected)

    def test_07_reader_and_checker_are_static(self) -> None:
        self.assertEqual((P.ROOT / P.PERMIT_READER_PATH).read_bytes(), P.READER_BYTES)
        source = PATH.read_text(encoding="utf-8")
        for token in (
            "os.write(",
            "O_CREAT",
            "generate_candidate(",
            "ZipFile",
            "archive.open(",
            "subprocess.",
            ".evaluate(",
        ):
            self.assertNotIn(token, source)

    def test_08_wrong_reverse_pin_fails_freeze(self) -> None:
        context = P.PermitContext(P.ROOT, include_permit=True, phase="recordable")
        try:
            raw = context.package.raw[P.RECORDER_PATH]
            context.package.raw[P.RECORDER_PATH] = raw.replace(
                P.sha256(context.package.raw[P.THIS_CHECKER_PATH]).encode(),
                b"f" * 64,
                1,
            )
            with self.assertRaises(P.PermitError):
                P.expected_payload(context)
        finally:
            context.close()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=P.ROOT,
            capture_output=True,
            check=False,
        )

    def test_09_print_default_invalid_are_canonical(self) -> None:
        printed = self.run_cli("--print-expected")
        self.assertEqual(printed.returncode, 0)
        self.assertEqual(printed.stdout, (P.ROOT / P.PERMIT_PATH).read_bytes())
        default = self.run_cli()
        self.assertEqual(default.returncode, 0)
        self.assertTrue(json.loads(default.stdout)["validationPassed"])
        invalid = self.run_cli("--secret")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"secret", invalid.stdout)

    def test_10_v3_output_namespace_is_currently_absent(self) -> None:
        for path in P.V3_PATHS:
            self.assertFalse((P.ROOT / path).exists(), path)
        self.assertEqual(P.evaluate(False)[0]["status"], "replacement_recovery_readback_authorized_once_not_consumed")

    def test_11_physical_v2_closure_mutation_is_rejected(self) -> None:
        context = P.PermitContext(P.ROOT, include_permit=True, phase="recordable")
        try:
            raw = context.v2_closure.raw[P.DECISION.V2_PERMIT_PATH]
            document = P.strict_json(raw)
            document["priorDraftDiagnosticObservation"][
                "authorityConsumptionState"
            ] = "not_consumed"
            context.v2_closure.raw[P.DECISION.V2_PERMIT_PATH] = (
                P.canonical_bytes(document)
            )
            with self.assertRaises(P.PermitError):
                context.validate_v2_closure()
        finally:
            context.close()

    def test_12_physical_v2_closure_fd_swap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            for binding in P.v2_closure_bindings():
                target = root / binding["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((P.ROOT / binding["path"]).read_bytes())
            held = P.DECISION.V2.RECOVERY.TRUST.HeldSet(
                root,
                P.v2_closure_bindings(),
            )
            target = root / P.DECISION.V2_PERMIT_PATH
            moved = target.with_name(target.name + ".held")
            try:
                target.rename(moved)
                target.write_bytes(moved.read_bytes())
                with self.assertRaises(Exception):
                    held.final_barrier()
            finally:
                target.unlink()
                moved.rename(target)
                held.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
