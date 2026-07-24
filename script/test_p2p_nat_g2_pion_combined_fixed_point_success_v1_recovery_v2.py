#!/usr/bin/env python3
"""Tests for the permanently closed recovery readback v2 authority."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (sys.flags.isolated and sys.flags.dont_write_bytecode and sys.flags.no_site):
    raise RuntimeError("tests require `python3 -I -B -S`")

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_combined_fixed_point_success_v1_recovery_v2.py"
)
SPEC = importlib.util.spec_from_file_location("recovery_readback_v2", PATH)
assert SPEC and SPEC.loader
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class RecoveryReadbackV2ClosureTests(unittest.TestCase):
    def test_01_live_default_check_is_static_closed_and_read_only(self) -> None:
        result = R.check()
        self.assertTrue(result["validationPassed"])
        self.assertFalse(result["recordable"])
        self.assertTrue(result["namespaceRecordableShape"])
        self.assertEqual(
            result["status"],
            "v2_authority_consumed_or_uncertain_static_closure_validated",
        )
        self.assertFalse(result["freshRecomputationPerformed"])
        self.assertEqual(result["archiveMemberDecodeCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertEqual(result["newTupleCount"], 16)
        self.assertFalse(result["fixedPointReached"])

    def test_02_exact_closure_permit_and_prior_observation(self) -> None:
        checker = R.load_permit_checker(R.ROOT)
        permit, summary = checker.evaluate(True)
        R.validate_closed_authority(permit)
        self.assertFalse(summary["readbackRecordingAuthorized"])
        self.assertFalse(summary["recordable"])
        self.assertFalse(summary["executionAuthorized"])
        observation = permit["priorDraftDiagnosticObservation"]
        self.assertEqual(
            observation["priorPermitRawSha256"],
            "bf14e46c6c43a1e247d702aba742adecd4e1a10b05dc688cd57e5f04e8fdbbda",
        )
        self.assertEqual(
            observation["priorPermitContentSha256"],
            "6b64282e170973fb86000e56d7a189e9a9b5a26b7fea71bfbb0ee16f00304296",
        )
        self.assertEqual(
            observation["priorPermitCheckerRawSha256"],
            "c5c3bc2065b4d31a127a138dd30eb458e1a000c57dc6f53d9404636c988983bf",
        )
        self.assertEqual(
            observation["priorRecorderRawSha256"],
            "bfa2fb3a887a95f7d1c3e8e56287f01b27666f28a34d8a663a5a2e81b462b7fc",
        )
        self.assertEqual(
            observation["priorRecorderTestsRawSha256"],
            "0d6881a7e1281bffbc91c835f14e97ce257caa96831456eb9b05dcc3615b4cc6",
        )
        self.assertEqual(
            observation["observedStatus"],
            "recordable_fresh_validation_passed",
        )
        self.assertTrue(observation["freshRecomputationOccurredBeforeClaim"])
        self.assertFalse(observation["acceptedAsEvidence"])
        self.assertFalse(observation["claimCreated"])
        self.assertFalse(observation["receiptCreated"])
        self.assertFalse(observation["failureCreated"])
        self.assertFalse(observation["manifestCreated"])
        self.assertEqual(observation["fileWriteCount"], 0)
        self.assertEqual(
            observation["authorityConsumptionState"],
            "consumed_or_uncertain",
        )

    def test_03_closure_module_has_no_write_or_recompute_capability(self) -> None:
        source = PATH.read_text(encoding="utf-8")
        for token in (
            "os.write(",
            "O_CREAT",
            "O_EXCL",
            "fresh_validate",
            "generate_candidate",
            "ZipFile",
            "archive.open(",
            "secrets.",
            "write_text(",
            "write_bytes(",
            "retained_write_exclusive",
            "publish_failure_transaction",
        ):
            self.assertNotIn(token, source)

    def test_04_record_refuses_after_static_authority_gate(self) -> None:
        snapshot = mock.Mock(return_value=(object(), {}, {}, {}))
        with mock.patch.object(R, "closure_snapshot", snapshot):
            with self.assertRaises(R.ReadbackError) as caught:
                R.record(Path("/not-used"))
        self.assertEqual(caught.exception.code, "E_AUTHORITY_CONSUMED")
        self.assertEqual(caught.exception.phase, "record")
        snapshot.assert_called_once_with(Path("/not-used"))

    def test_05_every_post_closure_artifact_phase_fails_closed(self) -> None:
        for phase in (
            "after_claim",
            "failure",
            "after_receipt",
            "complete",
            "blocked",
        ):
            with (
                self.subTest(phase=phase),
                mock.patch.object(R, "load_permit_checker", return_value=object()),
                mock.patch.object(R, "observed_phase", return_value=phase),
            ):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.closure_snapshot(Path("/not-used"))
                self.assertEqual(
                    caught.exception.code,
                    "E_UNAUTHORIZED_POST_CLOSURE_ARTIFACT",
                )

    def test_06_authority_and_observation_mutations_fail(self) -> None:
        checker = R.load_permit_checker(R.ROOT)
        permit, _ = checker.evaluate(True)
        for path, value in (
            (("authority", "claimWriteAuthorized"), True),
            (("authority", "oneOfflineReadbackAuthorized"), True),
            (
                (
                    "priorDraftDiagnosticObservation",
                    "authorityConsumptionState",
                ),
                "not_consumed",
            ),
            (("oneUseContract", "formalRecordAttemptAuthorized"), True),
        ):
            changed = copy.deepcopy(permit)
            changed[path[0]][path[1]] = value
            with self.assertRaises(R.ReadbackError):
                R.validate_closed_authority(changed)

    def test_07_bootstrap_reverse_pin_is_exact(self) -> None:
        checker = R.load_permit_checker(R.ROOT)
        raw = (R.ROOT / R.PERMIT_CHECKER_PATH).read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            R.EXPECTED_PERMIT_CHECKER_RAW_SHA256,
        )
        permit, _ = checker.evaluate(True)
        self.assertEqual(
            permit["toolBindings"]["permitChecker"]["rawSha256"],
            R.EXPECTED_PERMIT_CHECKER_RAW_SHA256,
        )

    def test_08_authority_error_is_canonical_and_non_authorizing(self) -> None:
        document = R.error_document(
            R.ReadbackError("E_AUTHORITY_CONSUMED", "record")
        )
        raw = (
            json.dumps(
                document,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        self.assertEqual(json.loads(raw), document)
        self.assertFalse(document["automaticRetryAllowed"])
        self.assertFalse(document["networkUsed"])
        self.assertFalse(document["externalAuthenticationRequired"])

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=R.ROOT,
            capture_output=True,
            check=False,
        )

    def test_09_live_cli_check_and_invalid_cli(self) -> None:
        checked = self.run_cli("--check")
        self.assertEqual(checked.returncode, 0)
        self.assertEqual(checked.stderr, b"")
        value = json.loads(checked.stdout)
        self.assertFalse(value["recordable"])
        self.assertFalse(value["freshRecomputationPerformed"])
        self.assertEqual(value["archiveMemberDecodeCount"], 0)
        self.assertEqual(value["fileWriteCount"], 0)
        invalid = self.run_cli("--private-secret")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"private-secret", invalid.stdout)

    def test_10_v2_output_namespace_remains_exactly_absent(self) -> None:
        checker = R.load_permit_checker(R.ROOT)
        for path in checker.V2_PATHS:
            self.assertFalse((R.ROOT / path).exists(), path)
        self.assertEqual(R.observed_phase(R.ROOT, checker), "recordable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
