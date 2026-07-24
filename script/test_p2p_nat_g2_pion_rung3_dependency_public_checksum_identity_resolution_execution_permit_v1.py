#!/usr/bin/env python3
"""Tests for the one-use public checksum identity-resolution permit."""

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

import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_execution_permit_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "public_identity_execution_permit_v1",
    PATH,
)
assert SPEC and SPEC.loader
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class PublicChecksumIdentityExecutionPermitV1Tests(unittest.TestCase):
    def expected(self):
        return P.evaluate(False)[0]

    def test_01_live_exact_permit(self) -> None:
        expected, summary = P.evaluate(True)
        self.assertEqual(
            json.loads((P.ROOT / P.PERMIT_PATH).read_bytes()),
            expected,
        )
        self.assertTrue(summary["validationPassed"])
        self.assertTrue(summary["networkAuthorized"])
        self.assertEqual(summary["authorizedHost"], "sum.golang.org")
        self.assertEqual(summary["maximumRequestCount"], 129)
        self.assertFalse(summary["sourceAcquisitionAuthorized"])

    def test_02_prior_decision_package_is_exactly_pinned(self) -> None:
        decision = self.expected()["decisionBinding"]
        self.assertEqual(
            {row["path"]: row["rawSha256"] for row in decision["files"]},
            P.EXPECTED_DECISION_RAW,
        )
        self.assertEqual(
            decision["decisionContentSha256"],
            P.EXPECTED_DECISION_CONTENT,
        )
        self.assertEqual(
            decision["requiredStatus"],
            "strict_deterministic_adaptive_sumdb_fsm_selected_"
            "execution_not_authorized",
        )

    def test_03_checkpoint_key_tree_and_files_are_exact(self) -> None:
        checkpoint = self.expected()["trustedCheckpoint"]
        self.assertEqual(
            {row["path"]: row["rawSha256"] for row in checkpoint["files"]},
            P.DECISION.EXPECTED_RUNG2_RAW,
        )
        self.assertEqual(checkpoint["verifierKey"], P.DECISION.SUMDB_VERIFIER_KEY)
        self.assertEqual(checkpoint["oldTreeSize"], 57_871_495)
        self.assertEqual(
            checkpoint["oldRootHashBase64"],
            P.DECISION.OLD_ROOT_HASH_BASE64,
        )
        self.assertTrue(checkpoint["existingValidatorReverified"])

    def test_04_target_keeps_only_zip_identity_unknown(self) -> None:
        target = self.expected()["target"]
        self.assertEqual(target["module"], "github.com/kr/pty")
        self.assertEqual(target["version"], "v1.1.1")
        self.assertEqual(target["heldGoModH1"], P.DECISION.TARGET_MOD_H1)
        self.assertIsNone(target["moduleZipH1"])
        self.assertFalse(target["unknownValueHardcoded"])

    def test_05_claim_is_durable_one_use_and_non_resumable(self) -> None:
        claim = self.expected()["oneUseConsumption"]
        self.assertEqual(claim["initialState"], "authorized_not_consumed")
        self.assertEqual(claim["claimPath"], P.CLAIM_PATH)
        self.assertTrue(claim["claimCreatedExclusivelyBeforeNetwork"])
        self.assertTrue(claim["claimFsyncedBeforeNetwork"])
        self.assertTrue(claim["claimPersistsAfterAnyNetworkAttempt"])
        self.assertTrue(claim["claimUncertaintyConsumesPermit"])
        self.assertFalse(claim["secondExecutionAllowed"])
        self.assertFalse(claim["automaticRetryAllowed"])
        self.assertFalse(claim["partialResumeAllowed"])
        self.assertFalse(claim["backfillAllowed"])

    def test_06_request_surface_is_exact_direct_https_and_auth_free(self) -> None:
        request = self.expected()["requestContract"]
        lookup = request["lookup"]
        self.assertEqual(lookup["method"], "GET")
        self.assertEqual(lookup["host"], "sum.golang.org")
        self.assertEqual(
            lookup["path"],
            "/lookup/github.com/kr/pty@v1.1.1",
        )
        self.assertEqual(lookup["requestOrdinal"], 1)
        self.assertEqual(request["tiles"]["method"], "GET")
        self.assertFalse(request["tiles"]["requestBodyAllowed"])
        self.assertFalse(request["tiles"]["rangeHeaderAllowed"])
        self.assertTrue(request["directHttpsOnly"])
        self.assertEqual(request["port"], 443)
        for key in (
            "ambientProxyAllowed",
            "redirectAllowed",
            "alternateMirrorAllowed",
            "authenticationChallengeHandlingAllowed",
            "authorizationHeaderAllowed",
            "proxyAuthorizationHeaderAllowed",
            "cookieAllowed",
            "clientCertificateAllowed",
            "credentialsAllowed",
            "queryAllowed",
            "fragmentAllowed",
            "retryAllowed",
            "requestBodyAllowed",
            "rangeHeaderAllowed",
            "moduleProxyAllowed",
            "moduleOrZipRequestAllowed",
        ):
            self.assertFalse(request[key], key)

    def test_07_absolute_caps_and_wall_timer_are_exact(self) -> None:
        limits = self.expected()["absoluteResourceLimits"]
        self.assertEqual(limits["maximumTotalRequestCount"], 129)
        self.assertEqual(limits["maximumLookupRequestCount"], 1)
        self.assertEqual(limits["maximumDerivedTileRequestCount"], 128)
        self.assertEqual(limits["maximumAggregateResponseBodyBytes"], 4_194_304)
        self.assertEqual(limits["maximumLookupResponseBodyBytes"], 65_536)
        self.assertEqual(limits["maximumTileResponseBodyBytes"], 8_192)
        self.assertEqual(limits["maximumHeaderBytesPerResponse"], 16_384)
        self.assertEqual(limits["perRequestDeadlineMilliseconds"], 15_000)
        self.assertEqual(limits["wholeAttemptDeadlineMilliseconds"], 120_000)
        self.assertTrue(limits["wholeAttemptSignalTimerRequired"])

    def test_08_strict_record_and_tree_proofs_are_required(self) -> None:
        verification = self.expected()["strictVerificationContract"]
        self.assertEqual(verification["lookupRecordTargetLineCount"], 2)
        self.assertEqual(
            verification["lineOrder"],
            ["module_zip_h1", "go_mod_h1"],
        )
        self.assertEqual(verification["maximumSignedTreeSize"], 2**62)
        self.assertTrue(verification["pinnedKeySignedTreeRequiredBeforeTiles"])
        self.assertTrue(verification["recordInclusionRequired"])
        self.assertIn("exact_old_root", verification["equalTreeRule"])
        self.assertIn("consistency", verification["growthRule"])
        self.assertFalse(
            verification["unusedDuplicateOrConflictingProofHashAllowed"]
        )
        self.assertFalse(verification["keyRotationAllowed"])
        self.assertFalse(verification["trustOnFirstUseAllowed"])

    def test_09_authority_binding_is_carried_to_all_outputs(self) -> None:
        binding = self.expected()["authorityBindingContract"]
        self.assertTrue(binding["stableNoFollowReadBeforeClaim"])
        self.assertTrue(binding["permitRawAndContentSha256Required"])
        self.assertTrue(binding["checkerRawSha256Required"])
        self.assertTrue(binding["runnerRawSha256Required"])
        self.assertTrue(
            binding[
                "sameBindingRequiredInClaimEvidenceReceiptFailureAndManifest"
            ]
        )
        self.assertTrue(binding["runnerReversePinsCheckerRawSha256"])
        self.assertEqual(
            binding["checkerPinsNormalizedRunnerSha256"],
            P.EXPECTED_RUNNER_NORMALIZED_SHA256,
        )

    def test_10_write_and_execution_authority_are_metadata_only(self) -> None:
        filesystem = self.expected()["filesystemWriteAuthority"]
        self.assertTrue(filesystem["claimWriteAuthorized"])
        self.assertTrue(filesystem["ownerOnlyStagingWriteAuthorized"])
        self.assertTrue(filesystem["metadataEvidenceWriteAuthorized"])
        self.assertTrue(filesystem["failedStagingRetainedForForensics"])
        self.assertFalse(filesystem["failedStagingCleanupAuthorized"])
        self.assertFalse(filesystem["sourceAcceptedDirectoryWriteAuthorized"])
        self.assertFalse(filesystem["sourceWriteAuthorized"])
        execution = self.expected()["executionBoundary"]
        self.assertTrue(execution["metadataOnly"])
        for key in (
            "sourceAcquisitionAuthorized",
            "moduleProxyAuthorized",
            "moduleOrZipAcquisitionAuthorized",
            "archiveExtractionAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "compileAuthorized",
            "goCommandAuthorized",
            "packageManagerAuthorized",
            "subprocessAuthorized",
            "gitOperationAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "productRuntimeNetworkAuthorized",
        ):
            self.assertFalse(execution[key], key)

    def test_11_terminal_is_mutually_exclusive_and_manifest_is_last(self) -> None:
        terminal = self.expected()["terminalContract"]
        self.assertTrue(terminal["successAndFailureMutuallyExclusive"])
        self.assertTrue(terminal["manifestWrittenLast"])
        self.assertTrue(terminal["failureBeforeSuccessManifestOnly"])
        self.assertTrue(terminal["boundedFailureReasonCodesOnly"])
        self.assertTrue(terminal["proofHashListsOrCanonicalAggregateRequired"])
        self.assertFalse(
            terminal["rawResponseHeadersBodiesOrErrorsInTerminalJsonAllowed"]
        )
        self.assertFalse(terminal["runnerMayClaimIndependentReadback"])
        self.assertTrue(terminal["independentReadbackRequired"])

    def test_12_runner_normalized_hash_and_reverse_pin_are_exact(self) -> None:
        runner = (P.ROOT / P.RUNNER_PATH).read_bytes()
        checker = (P.ROOT / P.THIS_CHECKER_PATH).read_bytes()
        self.assertEqual(
            P.sha256(P.normalized_runner_bytes(runner)),
            P.EXPECTED_RUNNER_NORMALIZED_SHA256,
        )
        P.validate_runner_semantics(runner, checker)
        source = runner.decode()
        self.assertIn(
            f'EXPECTED_PERMIT_CHECKER_RAW = "{P.sha256(checker)}"',
            source,
        )

    def test_13_runner_semantic_and_reverse_pin_mutations_fail(self) -> None:
        runner = (P.ROOT / P.RUNNER_PATH).read_bytes()
        checker = (P.ROOT / P.THIS_CHECKER_PATH).read_bytes()
        mutations = (
            runner.replace(
                b"http.client.HTTPSConnection",
                b"http.client.HTTPConnection ",
                1,
            ),
            runner.replace(
                P.sha256(checker).encode(),
                b"0" * 64,
                1,
            ),
        )
        for changed in mutations:
            with self.assertRaises(P.PermitError):
                P.validate_runner_semantics(changed, checker)

    def test_14_unknown_zip_h1_is_not_literal_in_six_file_package(self) -> None:
        paths = (
            P.PERMIT_PATH,
            P.READER_PATH,
            P.THIS_CHECKER_PATH,
            P.THIS_TESTS_PATH,
            P.RUNNER_PATH,
            P.RUNNER_TESTS_PATH,
        )
        pattern = re.compile(r"h1:[A-Za-z0-9+/]{43}=")
        observed = {
            match
            for path in paths
            for match in pattern.findall((P.ROOT / path).read_text())
        }
        self.assertEqual(observed, {P.DECISION.TARGET_MOD_H1})

    def test_15_namespace_is_absent_before_execution(self) -> None:
        self.expected()
        for path in (P.CLAIM_PATH, P.FINAL_ROOT, *P.TERMINAL_PATHS):
            self.assertFalse((P.ROOT / path).exists(), path)
        dependency = P.ROOT / P.DEPENDENCY_ROOT
        self.assertFalse(
            any(
                child.name.startswith(P.STAGING_PREFIX)
                for child in dependency.iterdir()
            )
        )

    def test_16_held_named_file_swap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            target = root / "held/checkpoint.json"
            target.parent.mkdir()
            target.write_bytes(b'{"value":1}\n')
            os.chmod(target, 0o600)
            held_type = P.DECISION.WAVE3.PERMIT.DECISION.V2.RECOVERY.TRUST.HeldSet
            held = held_type(
                root,
                [
                    {
                        "path": "held/checkpoint.json",
                        "rawSha256": P.sha256(target.read_bytes()),
                        "maximumBytes": 1024,
                        "ownerOnly": True,
                    }
                ],
            )
            moved = target.with_name("checkpoint.held")
            try:
                target.rename(moved)
                target.write_bytes(moved.read_bytes())
                os.chmod(target, 0o600)
                with self.assertRaises(Exception):
                    held.final_barrier()
            finally:
                target.unlink()
                moved.rename(target)
                held.close()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=P.ROOT,
            capture_output=True,
            check=False,
        )

    def test_17_canonical_cli_default_preflight_print_and_invalid(self) -> None:
        for args in ((), ("--preflight",)):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0)
            summary = json.loads(result.stdout)
            self.assertTrue(summary["validationPassed"])
            self.assertTrue(summary["networkAuthorized"])
            self.assertEqual(result.stderr, b"")
        printed = self.run_cli("--print-expected")
        self.assertEqual(printed.returncode, 0)
        self.assertEqual(
            printed.stdout,
            (P.ROOT / P.PERMIT_PATH).read_bytes(),
        )
        invalid = self.run_cli("--execute")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"execute", invalid.stdout)

    def test_18_bool_integer_and_rebound_mutations_fail_exact_bytes(self) -> None:
        expected = self.expected()
        mutations = (
            ("networkAuthority", "productNetworkAuthorized", 0),
            ("networkAuthority", "sumDbIdentityResolutionHttpsAuthorized", 1),
            ("counterContract", "initialValues", None),
        )
        for section, key, value in mutations:
            changed = copy.deepcopy(expected)
            if section == "counterContract":
                changed[section][key]["subprocessCount"] = False
            else:
                changed[section][key] = value
            self.assertEqual(changed, expected, (section, key))
            with self.assertRaises(P.PermitError):
                P.verify_bound_bytes(P.canonical_bytes(changed), expected, "E_PERMIT")
            payload = copy.deepcopy(changed)
            payload.pop("contentBinding")
            rebound = P.content_bound(payload)
            with self.assertRaises(P.PermitError):
                P.verify_bound_bytes(P.canonical_bytes(rebound), expected, "E_PERMIT")

    def test_19_no_external_source_or_auth_endpoint_literal(self) -> None:
        paths = (
            P.PERMIT_PATH,
            P.READER_PATH,
            P.THIS_CHECKER_PATH,
            P.RUNNER_PATH,
        )
        combined = "\n".join((P.ROOT / path).read_text() for path in paths)
        self.assertNotIn("https://proxy.golang.org", combined)
        self.assertNotIn("Authorization: ", combined)
        self.assertNotIn("Proxy-Authorization: ", combined)
        self.assertNotIn(".zip?", combined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
