#!/usr/bin/env python3
"""Tests for the public checksum identity-resolution decision."""

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
import re
import subprocess
import tempfile
import unittest


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_decision_v1.py"
)
SPEC = importlib.util.spec_from_file_location("public_identity_decision_v1", PATH)
assert SPEC and SPEC.loader
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)


class PublicChecksumIdentityDecisionV1Tests(unittest.TestCase):
    def expected(self):
        return D.evaluate(False)[0]

    def test_01_live_exact_decision(self) -> None:
        expected, summary = D.evaluate(True)
        self.assertEqual(
            json.loads((D.ROOT / D.DECISION_PATH).read_bytes()),
            expected,
        )
        self.assertTrue(summary["validationPassed"])
        self.assertFalse(summary["networkAuthorized"])
        self.assertFalse(summary["moduleZipH1Resolved"])
        self.assertEqual(summary["maximumFutureRequestCount"], 129)

    def test_02_wave3_four_exact_pins_and_gap(self) -> None:
        decision = self.expected()
        self.assertEqual(
            {
                row["path"]: row["rawSha256"]
                for row in decision["wave3Binding"]["files"]
            },
            D.EXPECTED_WAVE3_RAW,
        )
        self.assertEqual(
            decision["wave3Binding"]["decisionContentSha256"],
            D.EXPECTED_WAVE3_CONTENT,
        )
        gap = decision["targetIdentityGap"]
        self.assertEqual(gap["module"], "github.com/kr/pty")
        self.assertEqual(gap["version"], "v1.1.1")
        self.assertEqual(gap["heldGoModH1"], D.TARGET_MOD_H1)
        self.assertIsNone(gap["moduleZipH1"])
        self.assertFalse(gap["unknownValueHardcoded"])

    def test_03_checkpoint_pins_key_tree_and_existing_validator(self) -> None:
        checkpoint = self.expected()["trustedChecksumDatabaseCheckpoint"]
        self.assertEqual(
            {row["path"]: row["rawSha256"] for row in checkpoint["files"]},
            D.EXPECTED_RUNG2_RAW,
        )
        self.assertEqual(checkpoint["verifierKey"], D.SUMDB_VERIFIER_KEY)
        self.assertEqual(checkpoint["treeSize"], 57_871_495)
        self.assertEqual(
            checkpoint["rootHashBase64"],
            D.OLD_ROOT_HASH_BASE64,
        )
        self.assertEqual(
            checkpoint["signatureBase64"],
            D.OLD_SIGNATURE_BASE64,
        )
        self.assertTrue(checkpoint["existingValidatorReverified"])
        D.RUNG2.validate_repository()

    def test_04_all_execution_auth_and_write_authorities_are_false(self) -> None:
        authority = self.expected()["authority"]
        allowed_true = {"decisionRecorded"}
        for key, value in authority.items():
            self.assertEqual(value, key in allowed_true, key)
        self.assertFalse(authority["networkAuthorized"])
        self.assertFalse(authority["filesystemMutationAuthorized"])
        self.assertFalse(authority["sourceAcquisitionAuthorized"])

    def test_05_lookup_request_is_exact_and_auth_free(self) -> None:
        request = self.expected()["plannedLookupRequest"]
        self.assertEqual(request["requestCount"], 1)
        self.assertEqual(request["method"], "GET")
        self.assertEqual(request["host"], "sum.golang.org")
        self.assertEqual(
            request["path"],
            "/lookup/github.com/kr/pty@v1.1.1",
        )
        self.assertEqual(
            request["url"],
            "https://sum.golang.org/lookup/github.com/kr/pty@v1.1.1",
        )
        for key in (
            "redirectAllowed",
            "ambientProxyAllowed",
            "authenticationChallengeHandlingAllowed",
            "authorizationHeaderAllowed",
            "proxyAuthorizationHeaderAllowed",
            "cookieAllowed",
            "clientCertificateAllowed",
            "credentialsAllowed",
            "queryAllowed",
            "fragmentAllowed",
            "retryAllowed",
        ):
            self.assertFalse(request[key], key)

    def test_06_caps_and_deadlines_are_exact(self) -> None:
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

    def test_07_adaptive_tile_path_grammar_is_narrow(self) -> None:
        for path in (
            "/tile/8/0/000",
            "/tile/8/1/001.p/1",
            "/tile/8/2/x001/234",
            "/tile/8/3/x001/x002/003.p/255",
        ):
            self.assertTrue(D.valid_tile_path(path), path)
        for path in (
            "/tile/7/0/000",
            "/tile/8/data/000",
            "/tile/8/0/0",
            "/tile/8/0/000.p/0",
            "/tile/8/0/000.p/256",
            "/tile/8/0/000?x=1",
            "/latest",
            "/lookup/github.com/kr/pty@v1.1.1",
            "/github.com/kr/pty/@v/v1.1.1.zip",
        ):
            self.assertFalse(D.valid_tile_path(path), path)

    def test_08_record_contract_rejects_empty_unrelated_extra_duplicate(self) -> None:
        contract = self.expected()["strictLookupRecordContract"]
        self.assertEqual(contract["exactTargetLineCount"], 2)
        self.assertEqual(
            contract["lineOrder"],
            ["module_zip_h1", "go_mod_h1"],
        )
        self.assertEqual(contract["extraRecordRejectionClass"], "GO-2026-4984")
        for key in (
            "emptyRecordAllowed",
            "unrelatedRecordAllowed",
            "duplicateRecordAllowed",
            "extraRecordAllowed",
            "trailingRecordBytesAllowed",
            "carriageReturnAllowed",
            "nulAllowed",
        ):
            self.assertFalse(contract[key], key)
        self.assertEqual(
            contract["moduleZipH1CanonicalBase64DecodedBytes"],
            32,
        )
        self.assertEqual(contract["moduleZipH1PrefixRequired"], "h1:")

    def test_09_tree_rollback_equal_and_growth_rules_are_closed(self) -> None:
        contract = self.expected()["signedNoteAndTreeContract"]
        self.assertIn("less_than_57871495_fails", contract["rollbackRule"])
        self.assertIn("exact_old_root", contract["equalSizeRule"])
        self.assertIn("valid_old_to_new", contract["growthRule"])
        self.assertFalse(contract["equalSizeDifferentRootAllowed"])
        self.assertFalse(contract["keyRotationAllowed"])
        self.assertFalse(contract["trustOnFirstUseAllowed"])

    def test_10_no_unknown_zip_h1_literal_in_new_package(self) -> None:
        paths = (
            D.DECISION_PATH,
            D.READER_PATH,
            D.THIS_CHECKER_PATH,
            D.THIS_TESTS_PATH,
        )
        pattern = re.compile(r"h1:[A-Za-z0-9+/]{43}=")
        observed = {
            match
            for path in paths
            for match in pattern.findall((D.ROOT / path).read_text())
        }
        self.assertEqual(observed, {D.TARGET_MOD_H1})

    def test_11_no_source_proxy_module_or_zip_url(self) -> None:
        decision = self.expected()
        encoded = D.canonical_bytes(decision).decode()
        self.assertNotIn("proxy.golang.org", encoded)
        self.assertNotIn("/@v/", encoded)
        proof = decision["adaptiveProofTileContract"]
        self.assertFalse(proof["sourceEndpointAllowed"])
        self.assertFalse(proof["dataTilesAllowed"])
        self.assertFalse(proof["latestEndpointAllowed"])
        self.assertFalse(proof["secondLookupAllowed"])

    def test_12_checkpoint_and_wave3_mutations_fail_closed(self) -> None:
        context = D.DecisionContext(D.ROOT, include_decision=True)
        try:
            original = context.checkpoint.raw[D.RUNG2_PROVENANCE_PATH]
            context.checkpoint.raw[D.RUNG2_PROVENANCE_PATH] = original.replace(
                D.OLD_ROOT_HASH_BASE64.encode(),
                b"A" * len(D.OLD_ROOT_HASH_BASE64),
                1,
            )
            with self.assertRaises(D.DecisionError):
                D.expected_payload(context)
        finally:
            context.close()
        context = D.DecisionContext(D.ROOT, include_decision=True)
        try:
            original = context.wave3.package.raw[D.WAVE3_DECISION_PATH]
            context.wave3.package.raw[D.WAVE3_DECISION_PATH] = original + b"x"
            with self.assertRaises(D.DecisionError):
                D.expected_payload(context)
        finally:
            context.close()

    def test_13_key_gap_authority_and_cap_mutations_do_not_match(self) -> None:
        expected = self.expected()
        for kind in ("key", "gap", "authority", "cap", "path"):
            changed = copy.deepcopy(expected)
            changed.pop("contentBinding")
            if kind == "key":
                changed["trustedChecksumDatabaseCheckpoint"][
                    "verifierKey"
                ] += "x"
            elif kind == "gap":
                changed["targetIdentityGap"]["moduleZipH1"] = "unknown"
            elif kind == "authority":
                changed["authority"]["networkAuthorized"] = True
            elif kind == "cap":
                changed["absoluteResourceLimits"][
                    "maximumTotalRequestCount"
                ] = 130
            else:
                changed["plannedLookupRequest"]["path"] = "/latest"
            self.assertNotEqual(D.content_bound(changed), expected, kind)

    def test_14_namespace_is_metadata_only_and_absent(self) -> None:
        namespace = self.expected()["metadataOnlyNamespaceReservation"]
        self.assertTrue(namespace["metadataOnly"])
        self.assertFalse(namespace["sourceAcceptedDirectory"])
        self.assertTrue(namespace["allCurrentlyAbsent"])
        for path in (D.CLAIM_PATH, D.FINAL_ROOT, *D.FUTURE_DOCS):
            self.assertFalse((D.ROOT / path).exists(), path)
        dependency = D.ROOT / D.DEPENDENCY_ROOT
        self.assertFalse(
            any(
                path.name.startswith(D.STAGING_PREFIX)
                for path in dependency.iterdir()
            )
        )

    def test_15_held_file_named_fd_swap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            relative = "held/checkpoint.json"
            target = root / relative
            target.parent.mkdir()
            target.write_bytes(b'{"value":1}\n')
            os.chmod(target, 0o600)
            binding = {
                "path": relative,
                "rawSha256": D.sha256(target.read_bytes()),
                "maximumBytes": 1024,
                "ownerOnly": True,
            }
            held_type = D.WAVE3.PERMIT.DECISION.V2.RECOVERY.TRUST.HeldSet
            held = held_type(root, [binding])
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
            cwd=D.ROOT,
            capture_output=True,
            check=False,
        )

    def test_16_canonical_cli_default_print_and_invalid(self) -> None:
        default = self.run_cli()
        self.assertEqual(default.returncode, 0)
        summary = json.loads(default.stdout)
        self.assertTrue(summary["validationPassed"])
        self.assertFalse(summary["networkAuthorized"])
        printed = self.run_cli("--print-expected")
        self.assertEqual(printed.returncode, 0)
        self.assertEqual(
            printed.stdout,
            (D.ROOT / D.DECISION_PATH).read_bytes(),
        )
        invalid = self.run_cli("--execute")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"execute", invalid.stdout)

    def test_17_checker_has_no_network_write_or_subprocess_surface(self) -> None:
        source = PATH.read_text()
        for token in (
            "socket.",
            "urllib.",
            "http.client",
            "subprocess.",
            "os.write(",
            "O_CREAT",
            "O_TRUNC",
            "proxy.golang.org",
            "/@v/",
        ):
            self.assertNotIn(token, source)

    def test_18_strict_json_content_and_adaptive_invariants(self) -> None:
        with self.assertRaises(D.DecisionError):
            D.strict_json(b'{"a":1,"a":2}\n')
        expected = self.expected()
        design = expected["selectedFutureDesign"]
        self.assertTrue(design["singleClaimCoversLookupAndDerivedTiles"])
        self.assertTrue(design["claimMustBeDurableBeforeNetwork"])
        self.assertTrue(design["claimPersistsAfterAnyNetworkAttempt"])
        self.assertFalse(design["automaticRetryAllowed"])
        self.assertFalse(design["resumeAllowed"])
        self.assertFalse(design["backfillAllowed"])
        proof = expected["adaptiveProofTileContract"]
        self.assertTrue(proof["pathSetMustBeUnique"])
        self.assertTrue(proof["pathSetMustBeMinimalForBothProofs"])

    def test_19_nested_bool_integer_type_confusion_is_rejected(self) -> None:
        expected = self.expected()
        mutations = (
            ("authority", "networkAuthorized", 0),
            ("authority", "decisionRecorded", 1),
            ("operationCounters", "networkOperationCount", False),
            (
                "operationCounters",
                "existingRungTwoValidatorRunCount",
                True,
            ),
        )
        for section, key, value in mutations:
            changed = copy.deepcopy(expected)
            changed[section][key] = value
            self.assertEqual(changed, expected, (section, key))
            raw = D.canonical_bytes(changed)
            self.assertEqual(
                json.loads(raw)[section][key],
                value,
                (section, key),
            )
            with self.assertRaises(D.DecisionError) as rejected:
                D.verify_decision_bytes(raw, expected)
            self.assertEqual(rejected.exception.code, "E_DECISION")

            rebound_payload = copy.deepcopy(changed)
            rebound_payload.pop("contentBinding")
            rebound = D.content_bound(rebound_payload)
            with self.assertRaises(D.DecisionError):
                D.verify_decision_bytes(D.canonical_bytes(rebound), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
