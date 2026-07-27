#!/usr/bin/env python3
"""Tests for the Wave17 acquisition readback permit package."""

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
import errno
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock
import unicodedata


NETWORK_ATTEMPTS: list[str] = []


def _deny_test_network(*_args, **_kwargs):
    NETWORK_ATTEMPTS.append("network")
    raise AssertionError(
        "offline Wave17 readback tests must never create network connections"
    )


http.client.HTTPSConnection = _deny_test_network
socket.create_connection = _deny_test_network


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave17_"
    "readback_execution_permit_v1.py"
)
SPEC = importlib.util.spec_from_file_location("wave17_readback_permit_tests", PATH)
C = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(C)


def _synthetic_package_raw() -> tuple[dict[str, bytes], str, str]:
    checker_raw = (C.ROOT / C.THIS_CHECKER_PATH).read_bytes()
    reverse_pin = hashlib.sha256(checker_raw).hexdigest()
    functions = (
        "load_readback_checker",
        "_open_to_owner",
        "_close_owned_fd",
        "_close_owned_fds",
        "create_readback_claim",
        "verify_snapshot",
        "validate_mod",
        "validate_zip",
        "atomic_publish",
        "preflight",
        "execute",
        "validate_argument_vector",
    )
    recorder_lines = [
        f'EXPECTED_READBACK_CHECKER_RAW = "{reverse_pin}"',
        "CONTRACT_MARKERS = (",
        *[
            f"    {token!r},"
            for token in (
                "os.O_EXCL",
                "O_NOFOLLOW",
                "os.fsync",
                "renameatx_np",
                "ZIP_CENTRAL_HEADER",
                "zlib.decompressobj",
                "MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP",
                "MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL",
                "signal.pthread_sigmask",
                "execute_success_recorded",
                "consumed_success_reporting_failed",
                "E_POST_SUCCESS_REPORTING",
                "allow_abbrev=False",
            )
        ],
        ")",
        *[f"def {name}():\n    pass" for name in functions],
        "",
    ]
    reader_raw = b"synthetic Wave17 readback reader\\n"
    recorder_raw = "\n".join(recorder_lines).encode()
    raw = {
        C.READER_PATH: reader_raw,
        C.THIS_CHECKER_PATH: checker_raw,
        C.THIS_TESTS_PATH:
            (C.ROOT / C.THIS_TESTS_PATH).read_bytes(),
        C.RECORDER_PATH: recorder_raw,
        C.RECORDER_TESTS_PATH: b"synthetic recorder tests\\n",
    }
    return (
        raw,
        hashlib.sha256(reader_raw).hexdigest(),
        hashlib.sha256(C.normalized_recorder(recorder_raw)).hexdigest(),
    )


def _synthetic_permit() -> tuple[dict[str, object], dict[str, bytes]]:
    raw, reader_digest, recorder_digest = _synthetic_package_raw()
    with (
        mock.patch.object(C, "EXPECTED_READER_RAW", reader_digest),
        mock.patch.object(
            C,
            "EXPECTED_RECORDER_NORMALIZED_SHA256",
            recorder_digest,
        ),
    ):
        permit = C.content_bound(C.expected_payload_from_package(raw))
    return permit, raw


class Wave17ReadbackPermitTests(unittest.TestCase):
    def tearDown(self) -> None:
        self.assertEqual(NETWORK_ATTEMPTS, [])

    def test_01_frozen_snapshot_constants_are_exact(self):
        self.assertEqual(C.ATTEMPT_ID, "117fb836380658986632911b9508e274")
        self.assertEqual(
            C.READBACK_CLAIM_PATH,
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-17-v1-readback.claim"
            ),
        )
        self.assertEqual(
            C.ACQUISITION_CLAIM_PATH,
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-17-v1.claim"
            ),
        )
        self.assertNotEqual(
            C.READBACK_CLAIM_PATH,
            C.ACQUISITION_CLAIM_PATH,
        )
        self.assertEqual(C.FINAL_DIRECTORY["linkCount"], 4)
        self.assertEqual(C.FINAL_DIRECTORY["exactEntries"], [
            "accepted",
            "evidence.json",
        ])
        self.assertEqual(C.ACCEPTED_DIRECTORY["linkCount"], 4)
        self.assertEqual(C.ACCEPTED_DIRECTORY["exactFileCount"], 2)
        self.assertEqual(len(C.ACQUISITION_AUTHORITY), 15)
        self.assertEqual(len(C.ACCEPTED_FILES), 2)
        self.assertEqual(
            sum(row["bytes"] for row in C.ACCEPTED_FILES),
            3_450_700,
        )
        self.assertEqual(
            sum(
                row["bytes"]
                for row in C.ACCEPTED_FILES
                if Path(row["path"]).suffix == ".mod"
            ),
            301,
        )
        self.assertEqual(
            sum(
                row["bytes"]
                for row in C.ACCEPTED_FILES
                if Path(row["path"]).suffix == ".zip"
            ),
            3_450_399,
        )
        self.assertEqual(
            [Path(row["path"]).suffix for row in C.ACCEPTED_FILES],
            [".mod", ".zip"],
        )
        self.assertEqual(
            [Path(row["path"]).name for row in C.ACCEPTED_FILES],
            [
                "001-8bd04ea612cec9787131.mod",
                "001-8bd04ea612cec9787131.zip",
            ],
        )
        acquisition_permit_path = (
            f"{C.BASE}/bounded-dependency-source-acquisition-wave17-"
            "execution-permit-v1.json"
        )
        acquisition_permit = C.strict_json(
            C.stable_read(acquisition_permit_path)
        )
        resources = acquisition_permit["requestContract"]["resources"]
        modules = [row["module"] for row in resources]
        expected_modules = ["golang.org/x/tools"]
        self.assertEqual(
            modules,
            [module for module in expected_modules for _ in range(2)],
        )
        self.assertEqual(
            {row["module"] for row in resources},
            set(expected_modules),
        )
        payload = C.frozen_snapshot_payload()
        self.assertEqual(payload["frozenFileCount"], 21)
        self.assertEqual(
            payload["frozenFilesCanonicalSha256"],
            "bea9d0c6a260407e34524b5aced01cf9a334c36a6f882350e57f02107b1008c8",
        )
        self.assertEqual(payload["selectedTupleCount"], 0)
        self.assertEqual(payload["selectedRequestOrdinals"], [])
        self.assertEqual(payload["aggregateZipEntryCount"], 1_550)
        self.assertEqual(
            payload["aggregateZipUncompressedBytes"],
            9_108_004,
        )
        self.assertEqual(
            payload["acceptedResourceHashSetCanonicalSha256"],
            "7bee498b9c53d5d834fad61a2862162791ad46f45471199389046fb466c16cfa",
        )
        authority_paths = {
            row["path"] for row in C.ACQUISITION_AUTHORITY
        }
        self.assertIn(
            "script/check_p2p_nat_g2_pion_combined_fixed_point_v15.py",
            authority_paths,
        )
        self.assertIn(
            "script/test_p2p_nat_g2_pion_combined_fixed_point_v15.py",
            authority_paths,
        )
        self.assertIn(
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-16-v1.claim"
            ),
            authority_paths,
        )
        v15 = acquisition_permit["predecessorBindings"][
            "combinedFixedPointV15"
        ]
        bound_authority_rows = [
            *acquisition_permit["decisionBinding"]["files"],
            {
                "path": v15["checkerPath"],
                "rawSha256": v15["checkerRawSha256"],
            },
            {
                "path": v15["testsPath"],
                "rawSha256": v15["testsRawSha256"],
            },
            v15["wave16NamespaceAnchor"],
            acquisition_permit["readerDocumentBinding"],
            *acquisition_permit["toolBindings"],
            *acquisition_permit["primitiveBindings"],
        ]
        self.assertEqual(len(bound_authority_rows), 14)
        self.assertEqual(
            {row["path"] for row in bound_authority_rows},
            authority_paths - {acquisition_permit_path},
        )
        self.assertFalse(
            any("_candidate_v1.py" in path for path in authority_paths)
        )
        self.assertEqual(
            payload["identityBindings"]["resourcesCanonicalSha256"],
            C.EXPECTED_RESOURCES_CANONICAL,
        )
        self.assertEqual(
            payload["predecessorBindings"]["combinedFixedPointV15"][
                "contentSha256"
            ],
            C.EXPECTED_V15_CONTENT,
        )
        self.assertFalse(
            any(
                "combined_fixed_point_v" + "10.py" in path
                for path in authority_paths
            )
        )

    def test_02_live_frozen_bytes_modes_and_inventory_validate(self):
        C.audit_frozen_snapshot()

    def test_03_materialized_package_is_sealed_and_exact(self):
        permit_path = C.ROOT / C.PERMIT_PATH
        if not C.is_sealed():
            self.assertEqual(C.EXPECTED_READER_RAW, C.PLACEHOLDER_SHA256)
            self.assertEqual(
                C.EXPECTED_RECORDER_NORMALIZED_SHA256,
                C.PLACEHOLDER_SHA256,
            )
            self.assertFalse(permit_path.exists())
            return
        if not permit_path.exists():
            self.assertEqual(
                C.EXPECTED_READER_RAW,
                C.sha256((C.ROOT / C.READER_PATH).read_bytes()),
            )
            self.assertEqual(
                C.EXPECTED_RECORDER_NORMALIZED_SHA256,
                C.sha256(
                    C.normalized_recorder(
                        (C.ROOT / C.RECORDER_PATH).read_bytes()
                    )
                ),
            )
            return
        self.assertEqual(
            C.EXPECTED_READER_RAW,
            C.sha256((C.ROOT / C.READER_PATH).read_bytes()),
        )
        self.assertEqual(
            C.EXPECTED_RECORDER_NORMALIZED_SHA256,
            C.sha256(
                C.normalized_recorder(
                    (C.ROOT / C.RECORDER_PATH).read_bytes()
                )
            ),
        )
        permit, summary = C.evaluate(True)
        permit_raw = permit_path.read_bytes()
        self.assertEqual(permit_raw, C.canonical_bytes(permit))
        self.assertEqual(C.strict_json(permit_raw), permit)
        self.assertTrue(summary["validationPassed"])
        self.assertTrue(summary["frozenSnapshotVerified"])
        preflight = C.package_preflight_for_recorder()
        self.assertEqual(
            preflight["permitRawSha256"],
            C.sha256(permit_raw),
        )
        self.assertFalse(preflight["frozenAcquisitionInputOpened"])
        self.assertEqual(preflight["networkRequestAttemptCount"], 0)
        self.assertEqual(C.readback_namespace_state(), "absent")
        self.assertFalse(os.path.lexists(C.ROOT / C.READBACK_CLAIM_PATH))

    def test_04_synthetic_permit_is_strict_canonical_and_content_bound(self):
        permit, _ = _synthetic_permit()
        raw = C.canonical_bytes(permit)
        value = C.strict_json(raw)
        self.assertEqual(raw, C.canonical_bytes(value))
        C.verify_bound(raw, value)

    def test_05_authority_is_offline_and_authentication_free(self):
        permit, _ = _synthetic_permit()
        authority = permit["authority"]
        self.assertTrue(authority["offlineReadbackAuthorizedOnce"])
        package_paths = [
            permit["readerDocumentBinding"]["path"],
            *(row["path"] for row in permit["toolBindings"]),
        ]
        self.assertEqual(len(package_paths), 5)
        self.assertEqual(len(set(package_paths)), 5)
        self.assertEqual(
            set(package_paths),
            {
                C.READER_PATH,
                C.THIS_CHECKER_PATH,
                C.THIS_TESTS_PATH,
                C.RECORDER_PATH,
                C.RECORDER_TESTS_PATH,
            },
        )
        interpreter = permit["interpreterContract"]
        self.assertEqual(
            interpreter["command"],
            [
                "python3",
                "-I",
                "-B",
                "-S",
                C.RECORDER_PATH,
                "--execute",
            ],
        )
        self.assertEqual(
            interpreter["productionExactArgv"],
            ["--execute"],
        )
        self.assertEqual(
            interpreter["readOnlyPreflightExactArgv"],
            ["--preflight"],
        )
        for key in (
            "additionalArgumentsAllowed",
            "duplicateArgumentsAllowed",
            "abbreviatedArgumentsAllowed",
        ):
            self.assertIs(interpreter[key], False, key)
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
        self.assertTrue(
            verification[
                "executeSuccessRecordedBeforeStdoutReporting"
            ]
        )
        self.assertEqual(
            verification["postSuccessReportingFailure"],
            {
                "status": "consumed_success_reporting_failed",
                "failureCode": "E_POST_SUCCESS_REPORTING",
                "failurePhase": "reporting",
                "retryAllowed": False,
                "readbackPublicationComplete": True,
                "completionAppliesToRetainedSnapshot": True,
            },
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
        self.assertTrue(
            output["executeSuccessRecordedBeforeStdoutReporting"]
        )
        self.assertEqual(
            output["postSuccessReportingFailureStatus"],
            "consumed_success_reporting_failed",
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
            "ownerProofRequired",
            "accountRequired",
            "ownerRequired",
            "sshRequired",
            "gpgRequired",
            "passwordRequired",
            "privateKeyRequired",
            "signatureRequired",
            "tokenRequired",
            "cookieRequired",
            "clientCertificateRequired",
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
        raw, reader_digest, recorder_digest = _synthetic_package_raw()
        with (
            mock.patch.object(C, "EXPECTED_READER_RAW", reader_digest),
            mock.patch.object(
                C,
                "EXPECTED_RECORDER_NORMALIZED_SHA256",
                recorder_digest,
            ),
        ):
            C.validate_recorder(
                raw[C.RECORDER_PATH],
                raw[C.THIS_CHECKER_PATH],
            )
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
        recorder = C.ROOT / C.RECORDER_PATH
        if not recorder.exists():
            self.assertFalse(C.is_sealed())
            return
        source = recorder.read_text()
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

    def test_08_contract_mutations_are_rebound_and_rejected(self):
        original, _ = _synthetic_permit()
        for mutation in (
            "attempt",
            "aggregate",
            "authority",
            "claim",
            "permit_extra",
            "authority_extra",
            "authority_bool_int",
            "count_bool_int",
        ):
            changed = copy.deepcopy(original)
            if mutation == "attempt":
                changed["frozenAcquisitionSnapshot"]["attemptId"] = (
                    "fff8d6073748eab6fd1a05c79c57a84f"
                )
            elif mutation == "aggregate":
                changed["frozenAcquisitionSnapshot"]["aggregateAcceptedBytes"] += 1
            elif mutation == "authority":
                changed["authority"]["networkAuthorized"] = True
            elif mutation == "claim":
                changed["oneUseConsumption"]["claimPath"] += ".other"
            elif mutation == "permit_extra":
                changed["unknown"] = False
            elif mutation == "authority_extra":
                changed["authority"]["unknown"] = False
            elif mutation == "authority_bool_int":
                changed["authority"]["networkAuthorized"] = 0
            else:
                changed["frozenAcquisitionSnapshot"]["frozenFileCount"] = True
            changed.pop("contentBinding")
            rebound = C.content_bound(changed)
            with self.assertRaises(C.PermitError) as caught:
                C.verify_bound(C.canonical_bytes(rebound), original)
            self.assertEqual(caught.exception.code, "E_PERMIT")

    def test_08_wave17_cardinality_hash_aggregate_and_limit_drift_rejects(self):
        original, _ = _synthetic_permit()
        snapshot = original["frozenAcquisitionSnapshot"]

        def stale_wave16_frozen_25(value):
            value["frozenAcquisitionSnapshot"]["frozenFileCount"] = 25

        def authority_14(value):
            authority = value["frozenAcquisitionSnapshot"][
                "acquisitionAuthority"
            ]
            value["frozenAcquisitionSnapshot"]["acquisitionAuthority"] = [
                row
                for row in authority
                if not row["path"].endswith("/.wave-16-v1.claim")
            ]

        def bound_rows_14(value):
            predecessor = value["frozenAcquisitionSnapshot"][
                "predecessorBindings"
            ]["combinedFixedPointV15"]
            predecessor.pop("wave16NamespaceAnchor")

        def predecessor_v14(value):
            predecessors = value["frozenAcquisitionSnapshot"][
                "predecessorBindings"
            ]
            predecessors["combinedFixedPointV14"] = predecessors.pop(
                "combinedFixedPointV15"
            )

        def wave16_aggregates(value):
            value["frozenAcquisitionSnapshot"].update(
                {
                    "aggregateModBytes": 452,
                    "aggregateZipBytes": 11_475_192,
                    "aggregateAcceptedBytes": 11_475_644,
                    "aggregateZipEntryCount": 948,
                    "aggregateZipUncompressedBytes": 46_464_212,
                }
            )

        def wave16_hashes(value):
            value["frozenAcquisitionSnapshot"].update(
                {
                    "frozenFilesCanonicalSha256": (
                        "b8863a58dd5db814afe94eb101c166e4"
                        "f5bfb92d9b8197dbe3e32a3b1f0e99c4"
                    ),
                    "acceptedResourceHashSetCanonicalSha256": (
                        "f80997e5ef21d4b556667abc2fa016785"
                        "bcd234dc7a79dc028f70c7d35a36159"
                    ),
                }
            )

        def stale_wave16_limits(value):
            value["resourceLimits"].update(
                {
                    "maximumAcceptedResourceCount": 6,
                    "maximumAggregateModBytes": 3 * 1024 * 1024,
                    "maximumAggregateZipBytes": 48 * 1024 * 1024,
                    "maximumAggregateAcceptedBytes": 51 * 1024 * 1024,
                    "maximumZipEntriesAcrossAll": 60_000,
                    "maximumZipUncompressedBytesAcrossAll":
                        384 * 1024 * 1024,
                }
            )

        self.assertEqual(snapshot["frozenFileCount"], 21)
        self.assertEqual(len(snapshot["acquisitionAuthority"]), 15)
        for mutation in (
            stale_wave16_frozen_25,
            authority_14,
            bound_rows_14,
            predecessor_v14,
            wave16_aggregates,
            wave16_hashes,
            stale_wave16_limits,
        ):
            changed = copy.deepcopy(original)
            mutation(changed)
            changed.pop("contentBinding")
            rebound = C.content_bound(changed)
            with self.assertRaises(C.PermitError) as caught:
                C.verify_bound(C.canonical_bytes(rebound), original)
            self.assertEqual(caught.exception.code, "E_PERMIT")
        package_paths = (
            C.THIS_CHECKER_PATH,
            C.THIS_TESTS_PATH,
            C.RECORDER_PATH,
            C.RECORDER_TESTS_PATH,
            C.READER_PATH,
            C.PERMIT_PATH,
        )
        for package_path in package_paths:
            path = C.ROOT / package_path
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("golang.org/x/" + "mod", source)
            self.assertNotIn("golang.org/x/" + "net", source)
            self.assertNotIn("golang.org/x/" + "sync", source)
            self.assertNotIn("golang.org/x/" + "sys", source)
            self.assertNotIn("golang.org/x/" + "telemetry", source)
        for production_path in (
            C.THIS_CHECKER_PATH,
            C.RECORDER_PATH,
            C.READER_PATH,
            C.PERMIT_PATH,
        ):
            path = C.ROOT / production_path
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("combinedFixedPointV" + "14", source)
            self.assertNotIn(".wave-" + "15-v1.claim", source)

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
            for prefix in C.READBACK_TEMP_PREFIXES:
                stale = receipt.parent / (prefix + "stale")
                stale.symlink_to(root / "missing")
                self.assertEqual(
                    C.readback_namespace_state(root),
                    "stale_temporary_namespace",
                )
                with self.assertRaises(C.PermitError) as caught:
                    C.readback_namespace_absent(root)
                self.assertEqual(
                    caught.exception.state,
                    "stale_temporary_namespace",
                )
                stale.unlink()

                nfd = (
                    prefix.upper()
                    + unicodedata.normalize("NFD", "é")
                )
                nfc = (
                    prefix.upper()
                    + unicodedata.normalize("NFC", "é")
                )
                self.assertEqual(
                    C.portable_name(nfd),
                    C.portable_name(nfc),
                )
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

    def test_13_intermediate_component_replacement_fails_barrier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "a" / "b"
            nested.mkdir(parents=True, mode=0o700)
            traversal = C.HeldTraversal(root)
            try:
                traversal.directory("a/b")
                (root / "a").rename(root / "old-a")
                (root / "a" / "b").mkdir(parents=True, mode=0o700)
                with self.assertRaises(C.PermitError) as caught:
                    traversal.barrier()
                self.assertEqual(caught.exception.code, "E_PATH")
            finally:
                traversal.close()

    def test_14_partial_component_open_and_restore_error_close_all_fds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a" / "b").mkdir(parents=True, mode=0o700)
            before = len(os.listdir("/dev/fd"))
            traversal = C.HeldTraversal(root)
            original = traversal._validate_directory
            calls = 0

            def reject_second(info):
                nonlocal calls
                calls += 1
                original(info)
                if calls == 2:
                    raise C.PermitError("E_SYNTHETIC")

            try:
                with mock.patch.object(
                    traversal,
                    "_validate_directory",
                    side_effect=reject_second,
                ):
                    with self.assertRaises(C.PermitError):
                        traversal.directory("a/b")
            finally:
                traversal.close()
            self.assertEqual(len(os.listdir("/dev/fd")), before)

            traversal = C.HeldTraversal(root)
            traversal.directory("a/b")
            owned = tuple(traversal.owned)
            real_mask = C.signal.pthread_sigmask

            def restore_then_raise(how, mask):
                result = real_mask(how, mask)
                if how == C.signal.SIG_SETMASK:
                    raise RuntimeError("synthetic restore error")
                return result

            with mock.patch.object(
                C.signal,
                "pthread_sigmask",
                side_effect=restore_then_raise,
            ):
                with self.assertRaises(RuntimeError):
                    traversal.close()
            for fd in owned:
                with self.assertRaises(OSError):
                    os.fstat(fd)

    def test_15_close_retains_observably_open_fd_and_is_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traversal = C.HeldTraversal(root)
            root_fd = traversal.root_fd
            real_close = C.os.close

            def refuse_root_close(fd):
                if fd == root_fd:
                    raise OSError(errno.EIO, "synthetic close failure")
                return real_close(fd)

            with mock.patch.object(
                C.os,
                "close",
                side_effect=refuse_root_close,
            ):
                with self.assertRaises(OSError):
                    traversal.close()
            self.assertFalse(traversal.closed)
            self.assertIn(root_fd, traversal.owned)
            os.fstat(root_fd)

            traversal.close()
            self.assertTrue(traversal.closed)
            self.assertEqual(traversal.owned, [])
            with self.assertRaises(OSError):
                os.fstat(root_fd)

    def test_16_claim_observation_survives_traversal_close_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claim = root / C.READBACK_CLAIM_PATH
            claim.parent.mkdir(parents=True, mode=0o700)
            (root / C.BASE).mkdir(parents=True, mode=0o700)
            claim.write_bytes(b"observed")
            real_close = C.HeldTraversal.close

            def close_then_fail(traversal):
                real_close(traversal)
                raise RuntimeError("synthetic traversal cleanup")

            with mock.patch.object(
                C.HeldTraversal,
                "close",
                side_effect=close_then_fail,
                autospec=True,
            ):
                with self.assertRaises(C.PermitError) as caught:
                    C.readback_namespace_state(root)
            self.assertEqual(caught.exception.code, "E_CONSUMED")
            self.assertEqual(caught.exception.state, "claim_only")


if __name__ == "__main__":
    unittest.main(verbosity=2)
