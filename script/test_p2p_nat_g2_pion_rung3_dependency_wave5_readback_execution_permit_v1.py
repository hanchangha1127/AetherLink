#!/usr/bin/env python3
"""Tests for the Wave5 acquisition readback permit package."""

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

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import unicodedata


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave5_"
    "readback_execution_permit_v1.py"
)
SPEC = importlib.util.spec_from_file_location("wave5_readback_permit_tests", PATH)
C = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(C)


class Wave5ReadbackPermitTests(unittest.TestCase):
    def test_01_frozen_snapshot_constants_are_exact(self):
        self.assertEqual(C.ATTEMPT_ID, "ed050bd13835ab1f9fecc0dd3cfb6e12")
        self.assertEqual(len(C.ACQUISITION_AUTHORITY), 12)
        self.assertEqual(len(C.ACCEPTED_FILES), 30)
        self.assertEqual(
            sum(row["bytes"] for row in C.ACCEPTED_FILES),
            26_123_889,
        )
        self.assertEqual(
            [Path(row["path"]).suffix for row in C.ACCEPTED_FILES],
            [".mod", ".zip"] * 15,
        )
        self.assertEqual(
            {Path(row["path"]).name for row in C.ACCEPTED_FILES},
            {name for name, _, _ in C._ACCEPTED_ROWS},
        )
        payload = C.frozen_snapshot_payload()
        self.assertEqual(payload["frozenFileCount"], 46)
        self.assertEqual(payload["selectedTupleCount"], 0)
        self.assertEqual(payload["aggregateZipEntryCount"], 6_038)
        self.assertEqual(
            payload["aggregateZipUncompressedBytes"],
            101_774_573,
        )
        self.assertEqual(
            payload["acceptedResourceHashSetCanonicalSha256"],
            "b929d977644f7502a27340f2817957a95fb0ddcc885ee9222a525132939fa226",
        )

    def test_02_live_frozen_bytes_modes_and_inventory_validate(self):
        C.audit_frozen_snapshot()

    def test_03_exact_package_and_package_only_preflight(self):
        expected, summary = C.evaluate(True, True)
        self.assertTrue(summary["validationPassed"])
        self.assertEqual(summary["acceptedResourceCount"], 30)
        self.assertTrue(summary["completionAppliesToRetainedSnapshot"])
        self.assertFalse(
            summary[
                "currentPathIdentityGuaranteedThroughManifestPublication"
            ]
        )
        package = C.package_preflight_for_recorder()
        self.assertFalse(package["frozenAcquisitionInputOpened"])
        self.assertEqual(
            package["permitContentSha256"],
            expected["contentBinding"]["sha256"],
        )

    def test_04_permit_json_is_strict_canonical_and_content_bound(self):
        raw = (C.ROOT / C.PERMIT_PATH).read_bytes()
        value = C.strict_json(raw)
        self.assertEqual(raw, C.canonical_bytes(value))
        C.verify_bound(raw, value)

    def test_05_authority_is_offline_and_authentication_free(self):
        permit, _ = C.evaluate(True, False)
        authority = permit["authority"]
        self.assertTrue(authority["offlineReadbackAuthorizedOnce"])
        verification = permit["verificationContract"]
        self.assertEqual(verification["completeVerificationPassCount"], 2)
        self.assertEqual(verification["retainedFdPreManifestBarrierCount"], 3)
        self.assertEqual(
            verification["retainedFdPreManifestBarriers"],
            [
                "complete_snapshot_and_claim_immediately_before_receipt",
                "complete_snapshot_claim_and_receipt_after_receipt",
                (
                    "complete_snapshot_claim_and_receipt_"
                    "immediately_before_manifest_publication"
                ),
            ],
        )
        self.assertTrue(
            verification[
                "allRequiredPreManifestBarriersCompleteImmediatelyBeforeManifestPublication"
            ]
        )
        self.assertFalse(
            verification["requiredFallibleBarrierAfterManifest"]
        )
        self.assertTrue(
            verification[
                "claimCreationFdHeldAtImmediatelyBeforeManifestBarrier"
            ]
        )
        self.assertTrue(verification["completionAppliesToRetainedSnapshot"])
        self.assertFalse(
            verification[
                "currentPathIdentityGuaranteedThroughManifestPublication"
            ]
        )
        self.assertFalse(
            verification[
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ]
        )
        for removed in (
            "readbackClaimHeldThroughManifestPublication",
            "claimCreationFdContinuouslyHeldThroughManifestPublication",
            "readbackReceiptHeldThroughManifestPublication",
        ):
            self.assertNotIn(removed, verification)
        output = permit["outputContract"]
        self.assertTrue(output["completionAppliesToRetainedSnapshot"])
        self.assertFalse(
            output["currentPathIdentityGuaranteedThroughManifestPublication"]
        )
        self.assertFalse(
            output[
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ]
        )
        self.assertEqual(
            permit["outputContract"]["publicationOrder"],
            [
                "rename_no_replace",
                "parent_directory_fsync",
                "final_name_no_follow_reopen_and_source_inode_verification",
                "return",
            ],
        )
        for key in (
            "networkAuthorized",
            "dnsAuthorized",
            "socketAuthorized",
            "proxyAuthorized",
            "authenticationRequired",
            "credentialRequired",
            "externalAuthenticationRequired",
            "repositoryOwnerIdentityProofRequired",
            "passwordRequired",
            "privateKeyRequired",
            "signatureRequired",
            "tokenRequired",
            "sourceAcquisitionAuthorized",
            "sourceExtractionAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "compileAuthorized",
            "packageManagerAuthorized",
            "subprocessAuthorized",
            "gitOperationAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "userActionRequired",
        ):
            self.assertFalse(authority[key], key)

    def test_06_recorder_cycle_and_independence_are_exact(self):
        raw = C.package_raw(False)
        C.validate_recorder(raw[C.RECORDER_PATH], raw[C.THIS_CHECKER_PATH])
        source = raw[C.RECORDER_PATH].decode()
        self.assertNotIn("importlib", source)
        self.assertNotIn("subprocess", source)
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertFalse(
            imports.intersection({"http", "socket", "ssl", "urllib", "requests"})
        )

    def test_07_claim_precedes_snapshot_open_in_execute_source(self):
        source = (C.ROOT / C.RECORDER_PATH).read_text()
        claim = source.index(
            "claim, claim_creation_fd = create_readback_claim("
        )
        snapshot = source.index("snapshot = snapshot_factory(root)")
        self.assertLess(claim, snapshot)
        self.assertLess(
            source.index("namespace.hold_claim(claim, claim_creation_fd)"),
            snapshot,
        )
        self.assertIn("first = verify_snapshot(snapshot)", source)
        self.assertIn("second = verify_snapshot(snapshot)", source)

    def test_08_contract_mutations_change_exact_content(self):
        raw = C.package_raw(False)
        original = C.content_bound(C.expected_payload_from_package(raw))
        for mutation in (
            ("attempt",),
            ("aggregate",),
            ("authority",),
            ("claim",),
        ):
            changed = copy.deepcopy(original)
            if mutation[0] == "attempt":
                changed["frozenAcquisitionSnapshot"]["attemptId"] = "0" * 32
            elif mutation[0] == "aggregate":
                changed["frozenAcquisitionSnapshot"]["aggregateAcceptedBytes"] += 1
            elif mutation[0] == "authority":
                changed["authority"]["networkAuthorized"] = True
            else:
                changed["oneUseConsumption"]["claimPath"] += ".other"
            self.assertNotEqual(C.canonical_bytes(changed), C.canonical_bytes(original))

    def test_09_broken_symlink_occupies_readback_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / C.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True)
            (root / C.BASE).mkdir(parents=True)
            target.symlink_to(root / "missing")
            with self.assertRaises(C.PermitError) as caught:
                C.readback_namespace_absent(root)
            self.assertEqual(caught.exception.code, "E_CONSUMED")

    def test_10_frozen_file_aggregate_binding_is_reproducible(self):
        payload = C.frozen_snapshot_payload()
        frozen = [
            *C.ACQUISITION_AUTHORITY,
            C.ACQUISITION_CLAIM,
            C.EVIDENCE_FILE,
            *C.ACCEPTED_FILES,
            C.ACQUISITION_RECEIPT,
            C.ACQUISITION_MANIFEST,
        ]
        self.assertEqual(
            payload["frozenFilesCanonicalSha256"],
            hashlib.sha256(C.canonical_bytes(frozen)).hexdigest(),
        )

    def test_11_invalid_cli_fails_closed_without_write_authority(self):
        with self.assertRaises(C.PermitError):
            C.Parser(add_help=False).parse_args(["--unknown"])
        self.assertFalse(os.path.lexists(C.ROOT / C.READBACK_CLAIM_PATH))

    def test_12_namespace_states_and_stale_temporary_names_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claim = root / C.READBACK_CLAIM_PATH
            receipt = root / C.READBACK_RECEIPT_PATH
            manifest = root / C.READBACK_MANIFEST_PATH
            claim.parent.mkdir(parents=True)
            receipt.parent.mkdir(parents=True)

            def clear():
                for path in (claim, receipt, manifest):
                    path.unlink(missing_ok=True)
                for child in receipt.parent.iterdir():
                    if C.has_portable_prefix(
                        [child.name],
                        C.READBACK_TEMP_PREFIXES,
                    ):
                        child.unlink()

            self.assertEqual(C.readback_namespace_state(root), "absent")
            for expected, occupied in (
                ("claim_only", (claim,)),
                ("receipt_only", (claim, receipt)),
                ("complete", (claim, receipt, manifest)),
                ("inconsistent", (receipt,)),
            ):
                clear()
                for path in occupied:
                    path.write_bytes(b"x")
                self.assertEqual(C.readback_namespace_state(root), expected)
                with self.assertRaises(C.PermitError) as caught:
                    C.readback_namespace_absent(root)
                self.assertEqual(caught.exception.code, "E_CONSUMED")
                self.assertEqual(caught.exception.state, expected)

            clear()
            stale = receipt.parent / (C.READBACK_TEMP_PREFIXES[0] + "stale")
            stale.symlink_to(root / "missing")
            self.assertEqual(
                C.readback_namespace_state(root),
                "stale_temporary_namespace",
            )
            with self.assertRaises(C.PermitError) as caught:
                C.readback_namespace_absent(root)
            self.assertEqual(caught.exception.state, "stale_temporary_namespace")
            stale.unlink()

            nfd = (
                C.READBACK_TEMP_PREFIXES[0].upper()
                + unicodedata.normalize("NFD", "é")
            )
            nfc = (
                C.READBACK_TEMP_PREFIXES[0].upper()
                + unicodedata.normalize("NFC", "é")
            )
            self.assertEqual(C.portable_name(nfd), C.portable_name(nfc))
            self.assertTrue(
                C.has_portable_prefix(
                    [C.STAGING_PREFIX.upper() + nfd[-2:]],
                    [C.STAGING_PREFIX],
                )
            )
            for variant in (nfd, nfc):
                candidate = receipt.parent / variant
                candidate.symlink_to(root / "missing")
                self.assertEqual(
                    C.readback_namespace_state(root),
                    "stale_temporary_namespace",
                )
                candidate.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
