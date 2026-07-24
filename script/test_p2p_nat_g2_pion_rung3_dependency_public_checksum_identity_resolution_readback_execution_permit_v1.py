#!/usr/bin/env python3
"""Tests for the offline SumDB identity readback execution permit."""

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
    raise RuntimeError("tests require `python3 -I -B -S`")

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_readback_execution_permit_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "sumdb_identity_readback_permit_v1_tests",
    PATH,
)
assert SPEC and SPEC.loader
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class ReadbackExecutionPermitV1Tests(unittest.TestCase):
    def expected(self):
        expected, summary = P.evaluate(True)
        self.assertTrue(summary["validationPassed"])
        return expected

    def test_01_live_permit_is_exact_canonical_content_bound(self):
        expected = self.expected()
        raw = (P.ROOT / P.PERMIT_PATH).read_bytes()
        self.assertEqual(raw, P.canonical_bytes(expected))
        self.assertEqual(
            expected["contentBinding"]["sha256"],
            P.sha256(P.canonical_bytes({
                key: value
                for key, value in expected.items()
                if key != "contentBinding"
            })),
        )

    def test_02_execution_snapshot_freezes_authority_and_attempt(self):
        snapshot = self.expected()["executionSnapshot"]
        self.assertEqual(snapshot["attemptId"], P.ATTEMPT_ID)
        self.assertEqual(len(snapshot["executionAuthority"]), 3)
        self.assertEqual(
            snapshot["executionPermitContentSha256"],
            "41f2050c3e8a702da66adfdf5c890604756c7fa0e708d4b9fb062c8f5693a7fb",
        )
        self.assertEqual(snapshot["executionClaim"], P.EXECUTION_CLAIM)
        self.assertEqual(snapshot["executionReceipt"], P.EXECUTION_RECEIPT)
        self.assertEqual(snapshot["executionManifest"], P.EXECUTION_MANIFEST)

    def test_03_exact_eleven_file_inventory_is_frozen(self):
        directory = self.expected()["executionSnapshot"]["evidenceDirectory"]
        self.assertEqual(directory["exactFileCount"], 11)
        self.assertEqual(directory["files"], P.EVIDENCE_FILES)
        self.assertEqual(len(directory["files"]), 11)
        self.assertEqual(
            {Path(row["path"]).name for row in directory["files"]},
            {
                "evidence.json",
                "lookup.response",
                *{
                    f"tile-{index:03d}-{suffix}.bin"
                    for index, suffix in enumerate(
                        (
                            "433f370775408752",
                            "a942e5993ab9ac53",
                            "11e688bd3f4b0938",
                            "784dcfa494c65600",
                            "46424d628236beba",
                            "27561b7ea9397973",
                            "39dff99d869ebfa2",
                            "17efcc63092f321b",
                            "63afe683110cb0e6",
                        ),
                        1,
                    )
                },
            },
        )

    def test_04_all_frozen_files_have_exact_live_shape(self):
        for row in P.ALL_FROZEN_FILES:
            with self.subTest(path=row["path"]):
                item = P.HeldFile(P.ROOT / row["path"], row)
                item.close()

    def test_05_readback_is_durable_one_use(self):
        claim = self.expected()["oneUseConsumption"]
        self.assertEqual(claim["claimPath"], P.READBACK_CLAIM_PATH)
        self.assertEqual(claim["claimMode"], "0600")
        self.assertTrue(claim["claimCreatedExclusivelyBeforeFrozenInputReadback"])
        self.assertTrue(claim["claimFsyncedBeforeFrozenInputReadback"])
        self.assertTrue(claim["claimPersistsAfterSuccessFailureOrUncertainty"])
        for key in (
            "secondExecutionAllowed",
            "retryAllowed",
            "resumeAllowed",
            "replacementAllowed",
            "backfillAllowed",
        ):
            self.assertFalse(claim[key], key)

    def test_06_network_auth_source_and_user_action_are_forbidden(self):
        boundary = self.expected()["executionBoundary"]
        self.assertTrue(boundary["offlineReadbackOnly"])
        for key, value in boundary.items():
            if key != "offlineReadbackOnly":
                self.assertFalse(value, key)

    def test_07_independent_verification_contract_is_complete(self):
        contract = self.expected()["verificationContract"]
        for key, value in contract.items():
            if key in (
                "executionCheckerOrRunnerInvocationAllowed",
                "executionRunnerImportAllowed",
            ):
                self.assertFalse(value, key)
            else:
                self.assertTrue(value, key)

    def test_08_outputs_are_atomic_no_replace_and_manifest_last(self):
        output = self.expected()["outputContract"]
        self.assertEqual(output["receiptPath"], P.READBACK_RECEIPT_PATH)
        self.assertEqual(output["manifestPath"], P.READBACK_MANIFEST_PATH)
        self.assertTrue(output["receiptWrittenBeforeManifest"])
        self.assertTrue(output["manifestWrittenLast"])
        self.assertTrue(output["atomicNoReplaceRequired"])
        self.assertFalse(output["successOutputBeforeAllVerificationAllowed"])
        self.assertFalse(output["failureOutputAuthorized"])

    def test_09_authority_binding_and_reverse_pin_are_closed(self):
        expected = self.expected()
        binding = expected["authorityBindingContract"]
        recorder = (P.ROOT / P.RECORDER_PATH).read_bytes()
        checker = (P.ROOT / P.THIS_CHECKER_PATH).read_bytes()
        self.assertEqual(
            P.sha256(P.normalized_recorder_bytes(recorder)),
            binding["checkerPinsNormalizedRecorderSha256"],
        )
        P.validate_recorder_semantics(recorder, checker)
        self.assertIn(
            f'EXPECTED_READBACK_CHECKER_RAW = "{P.sha256(checker)}"',
            recorder.decode(),
        )

    def test_10_recorder_has_no_network_runner_or_auth_surface(self):
        source = (P.ROOT / P.RECORDER_PATH).read_text()
        for forbidden in (
            "http.client",
            "HTTPSConnection",
            "urlopen",
            "socket.",
            "subprocess",
            "proxy.golang.org",
            "identity_v1_once",
            "Authorization",
            "credential",
            "password",
        ):
            self.assertNotIn(forbidden, source)
        for required in (
            "verify_ed25519_signature",
            "derive_independent_plan",
            "verify_inclusion_path",
            "verify_consistency_path",
            "os.O_EXCL",
            "renameatx_np",
        ):
            self.assertIn(required, source)

    def test_11_readback_namespace_is_absent(self):
        self.expected()
        for path in (
            P.READBACK_CLAIM_PATH,
            P.READBACK_RECEIPT_PATH,
            P.READBACK_MANIFEST_PATH,
        ):
            self.assertFalse((P.ROOT / path).exists(), path)

    def test_12_consumed_execution_namespace_is_expected_not_rejected(self):
        self.expected()
        self.assertTrue((P.ROOT / P.EXECUTION_CLAIM["path"]).exists())
        self.assertTrue((P.ROOT / P.EXECUTION_RECEIPT["path"]).exists())
        self.assertTrue((P.ROOT / P.EXECUTION_MANIFEST["path"]).exists())

    def test_13_canonical_cli_default_preflight_print_and_invalid(self):
        command = ["python3", "-I", "-B", "-S", P.THIS_CHECKER_PATH]
        default = subprocess.run(
            command,
            cwd=P.ROOT,
            check=True,
            capture_output=True,
        ).stdout
        preflight = subprocess.run(
            [*command, "--preflight"],
            cwd=P.ROOT,
            check=True,
            capture_output=True,
        ).stdout
        printed = subprocess.run(
            [*command, "--print-expected"],
            cwd=P.ROOT,
            check=True,
            capture_output=True,
        ).stdout
        self.assertEqual(default, preflight)
        self.assertEqual(printed, (P.ROOT / P.PERMIT_PATH).read_bytes())
        rejected = subprocess.run(
            [*command, "--invalid"],
            cwd=P.ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(
            json.loads(rejected.stdout)["failureCode"],
            "E_ARGUMENT",
        )

    def test_14_permit_mutation_fails_exact_content(self):
        expected = self.expected()
        changed = dict(expected)
        changed["status"] = "mutated"
        with self.assertRaises(P.PermitError):
            P.verify_bound_bytes(P.canonical_bytes(changed), expected)

    def test_15_recorder_or_reverse_pin_mutation_fails(self):
        recorder = (P.ROOT / P.RECORDER_PATH).read_bytes()
        checker = (P.ROOT / P.THIS_CHECKER_PATH).read_bytes()
        mutations = (
            recorder.replace(b"renameatx_np", b"renameatx_xx", 1),
            recorder.replace(P.sha256(checker).encode(), b"0" * 64, 1),
        )
        for changed in mutations:
            with self.subTest():
                with self.assertRaises(P.PermitError):
                    P.validate_recorder_semantics(changed, checker)

    def test_16_frozen_byte_or_mode_drift_is_rejected(self):
        row = P.EXECUTION_CLAIM
        with tempfile.TemporaryDirectory(dir=P.ROOT / "build") as temporary:
            path = Path(temporary) / "claim"
            path.write_bytes(
                (P.ROOT / row["path"]).read_bytes() + b"x"
            )
            os.chmod(path, 0o600)
            changed = {
                **row,
                "path": str(path.relative_to(P.ROOT)),
            }
            with self.assertRaises(P.PermitError):
                item = P.HeldFile(path, changed)
                item.close()

    def test_17_reader_and_tools_are_exactly_bound(self):
        expected = self.expected()
        self.assertEqual(
            expected["readerDocumentBinding"]["rawSha256"],
            hashlib.sha256((P.ROOT / P.READER_PATH).read_bytes()).hexdigest(),
        )
        tools = {
            row["path"]: row["rawSha256"]
            for row in expected["toolBindings"]
        }
        self.assertEqual(
            set(tools),
            {
                P.THIS_CHECKER_PATH,
                P.THIS_TESTS_PATH,
                P.RECORDER_PATH,
                P.RECORDER_TESTS_PATH,
            },
        )
        for path, digest in tools.items():
            self.assertEqual(
                hashlib.sha256((P.ROOT / path).read_bytes()).hexdigest(),
                digest,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
