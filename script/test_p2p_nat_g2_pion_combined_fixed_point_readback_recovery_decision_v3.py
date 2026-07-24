#!/usr/bin/env python3
"""Tests for the replacement recovery decision-only package v3."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (sys.flags.isolated and sys.flags.dont_write_bytecode and sys.flags.no_site):
    raise RuntimeError("tests require `python3 -I -B -S`")

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_decision_v3.py"
)
SPEC = importlib.util.spec_from_file_location("recovery_decision_v3", PATH)
assert SPEC and SPEC.loader
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


class RecoveryDecisionV3Tests(unittest.TestCase):
    def test_01_live_exact_decision_package(self) -> None:
        expected, summary = C.evaluate(True)
        actual = json.loads((C.ROOT / C.DECISION_PATH).read_bytes())
        self.assertEqual(actual, expected)
        self.assertTrue(summary["validationPassed"])
        self.assertFalse(summary["readbackRecordingAuthorized"])
        self.assertFalse(summary["executionAuthorized"])
        self.assertEqual(summary["archiveMemberDecodeCount"], 0)
        self.assertEqual(summary["fileWriteCount"], 0)

    def test_02_exact_v2_decision_and_closure_bindings(self) -> None:
        expected, _ = C.evaluate(False)
        self.assertEqual(
            expected["v2RecoveryDecisionBinding"]["contentSha256"],
            C.V2.EXPECTED_RECOVERY_CONTENT,
        )
        self.assertEqual(
            {
                row["path"]: row["rawSha256"]
                for row in expected["v2ClosureBinding"]["files"]
            },
            C.V2_EXPECTED_RAW,
        )
        self.assertEqual(
            expected["v2ClosureBinding"]["permitContentSha256"],
            C.V2_EXPECTED_CONTENT,
        )
        self.assertEqual(
            expected["historicalDraftObservation"],
            json.loads((C.ROOT / C.V2_PERMIT_PATH).read_bytes())[
                "priorDraftDiagnosticObservation"
            ],
        )

    def test_03_original_69_source_and_terminal_are_exact(self) -> None:
        expected, _ = C.evaluate(False)
        original = expected["originalEvidenceBinding"]
        self.assertEqual(original["heldSourceInputCount"], 69)
        self.assertEqual(
            original["claimRawSha256"],
            C.V2.RECOVERY.EXPECTED_CLAIM_RAW_SHA256,
        )
        self.assertEqual(
            original["resultRawSha256"],
            C.V2.RECOVERY.EXPECTED_RESULT_RAW_SHA256,
        )
        self.assertEqual(
            original["manifestRawSha256"],
            C.V2.RECOVERY.EXPECTED_MANIFEST_RAW_SHA256,
        )
        self.assertEqual(original["newTupleCount"], 16)
        self.assertFalse(original["fixedPointReached"])

    def test_04_all_authority_is_false_and_next_action_is_bounded(self) -> None:
        expected, _ = C.evaluate(False)
        self.assertTrue(expected["authority"])
        self.assertTrue(all(value is False for value in expected["authority"].values()))
        self.assertEqual(
            expected["status"],
            "replacement_recovery_selected_execution_not_authorized",
        )
        self.assertEqual(expected["result"], expected["status"])
        self.assertEqual(
            expected["nextAction"],
            "prepare_separate_v3_one_use_execution_permit_package",
        )

    def test_05_v3_output_and_staging_collision_fail_closed(self) -> None:
        context = C.DecisionContext(C.ROOT, include_decision=True)
        absent = C.V2.RECOVERY.absent_from_held_namespace
        names = C.V2.RECOVERY.held_dependency_names
        try:
            with mock.patch.object(
                C.V2.RECOVERY,
                "absent_from_held_namespace",
                side_effect=lambda namespace, path: (
                    False if path == C.V3_CLAIM_PATH else absent(namespace, path)
                ),
            ):
                with self.assertRaises(C.DecisionError):
                    context.require_namespace()
            with mock.patch.object(
                C.V2.RECOVERY,
                "held_dependency_names",
                side_effect=lambda namespace: (
                    names(namespace) + [C.V3_STAGING_PREFIX + "injected"]
                ),
            ):
                with self.assertRaises(C.DecisionError):
                    context.require_namespace()
        finally:
            context.close()

    def test_06_current_namespace_is_all_absent(self) -> None:
        expected, _ = C.evaluate(False)
        namespace = expected["currentNamespace"]
        self.assertTrue(namespace)
        self.assertTrue(all(value is False for value in namespace.values()))
        for path in C.V3_OUTPUT_PATHS:
            self.assertFalse((C.ROOT / path).exists(), path)

    def test_07_reader_and_static_surface_are_exact(self) -> None:
        self.assertEqual((C.ROOT / C.READER_PATH).read_bytes(), C.READER_BYTES)
        source = PATH.read_text(encoding="utf-8")
        for token in (
            "os.write(",
            "O_CREAT",
            "O_EXCL",
            "generate_candidate(",
            "fresh_validate",
            "ZipFile",
            "archive.open(",
            "subprocess.",
            ".evaluate(",
            "write_text(",
            "write_bytes(",
        ):
            self.assertNotIn(token, source)

    def test_08_schema_authority_and_history_mutations_fail_equality(self) -> None:
        expected, _ = C.evaluate(False)
        for changed in (
            {**expected, "status": "authorized"},
            {
                **expected,
                "authority": {
                    **expected["authority"],
                    "executionAuthorized": True,
                },
            },
            {
                **expected,
                "historicalDraftObservation": {
                    **expected["historicalDraftObservation"],
                    "acceptedAsEvidence": True,
                },
            },
        ):
            self.assertNotEqual(C.canonical_bytes(changed), C.canonical_bytes(expected))
        payload = copy.deepcopy(expected)
        binding = payload.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            C.sha256(C.canonical_bytes(payload)),
        )

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=C.ROOT,
            capture_output=True,
            check=False,
        )

    def test_09_print_default_and_invalid_cli_are_canonical(self) -> None:
        printed = self.run_cli("--print-expected")
        self.assertEqual(printed.returncode, 0)
        self.assertEqual(printed.stderr, b"")
        self.assertEqual(printed.stdout, (C.ROOT / C.DECISION_PATH).read_bytes())
        default = self.run_cli()
        self.assertEqual(default.returncode, 0)
        self.assertEqual(default.stderr, b"")
        self.assertTrue(json.loads(default.stdout)["validationPassed"])
        invalid = self.run_cli("--secret-value")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"secret-value", invalid.stdout)

    def test_10_tool_bindings_match_current_package(self) -> None:
        expected, _ = C.evaluate(False)
        bindings = expected["toolBindings"]
        self.assertEqual(
            bindings["reader"]["rawSha256"],
            C.sha256((C.ROOT / C.READER_PATH).read_bytes()),
        )
        self.assertEqual(
            bindings["checker"]["rawSha256"],
            C.sha256(PATH.read_bytes()),
        )
        self.assertEqual(
            bindings["tests"]["rawSha256"],
            C.sha256(Path(__file__).read_bytes()),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
