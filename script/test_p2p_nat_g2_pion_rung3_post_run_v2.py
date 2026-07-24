#!/usr/bin/env python3
"""Synthetic-only tests for the G2 Pion rung-three v2 post-run readback."""

from __future__ import annotations

import ast
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung3_post_run_v2.py"
SOURCE_BODY_SENTINEL = "SYNTHETIC_SOURCE_BODY_MUST_NEVER_APPEAR_42a1"


def read_exact_source(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(os.fspath(path), flags)
    try:
        before = os.fstat(descriptor)
        remaining = before.st_size + 1
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if len(raw) != before.st_size or (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        ) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise RuntimeError("checker source changed while loading")
        return raw
    finally:
        os.close(descriptor)


CHECKER_SOURCE = read_exact_source(CHECKER_PATH)
CHECKER = ModuleType("g2_pion_rung3_post_run_v2_checker_under_test")
CHECKER.__file__ = os.fspath(CHECKER_PATH)
CHECKER.__package__ = None
exec(
    compile(
        CHECKER_SOURCE,
        os.fspath(CHECKER_PATH),
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    ),
    CHECKER.__dict__,
    CHECKER.__dict__,
)


SYNTHETIC_ARCHIVE_BYTES = 321
SYNTHETIC_ARCHIVE_SHA256 = hashlib.sha256(b"synthetic archive identity").hexdigest()
SYNTHETIC_TOTAL_UNCOMPRESSED_BYTES = 77
SYNTHETIC_ENTRIES = [
    {
        "path": "LICENSE",
        "bytes": 31,
        "sha256": hashlib.sha256(b"synthetic license metadata only").hexdigest(),
        "category": "license_or_notice",
        "creatorSystem": 0,
        "externalAttributes": "00000020",
        "modeSource": "synthetic_read_only_regular_mode",
        "effectiveUnixMode": "100444",
    },
    {
        "path": "review.go",
        "bytes": 46,
        "sha256": hashlib.sha256(
            f"unrecorded {SOURCE_BODY_SENTINEL}".encode()
        ).hexdigest(),
        "category": "go_source",
        "creatorSystem": 3,
        "externalAttributes": "81a40000",
        "modeSource": "archive_unix_mode",
        "effectiveUnixMode": "100644",
    },
]


def synthetic_tree_sha256() -> str:
    rows = [
        f"{entry['path']}\0{entry['bytes']}\0{entry['sha256']}\n".encode("utf-8")
        for entry in SYNTHETIC_ENTRIES
    ]
    return hashlib.sha256(b"".join(sorted(rows))).hexdigest()


def bound_document(document: dict[str, object], scope: str) -> dict[str, object]:
    payload = copy.deepcopy(document)
    payload.pop("contentBinding", None)
    result = copy.deepcopy(document)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": CHECKER.sha256_bytes(CHECKER.canonical_json_bytes(payload)),
    }
    return result


@contextmanager
def synthetic_constants():
    names_and_values = {
        "EXPECTED_ARCHIVE_BYTES": SYNTHETIC_ARCHIVE_BYTES,
        "EXPECTED_ARCHIVE_SHA256": SYNTHETIC_ARCHIVE_SHA256,
        "EXPECTED_ENTRY_COUNT": len(SYNTHETIC_ENTRIES),
        "EXPECTED_FILE_COUNT": len(SYNTHETIC_ENTRIES),
        "EXPECTED_TOTAL_UNCOMPRESSED_BYTES": SYNTHETIC_TOTAL_UNCOMPRESSED_BYTES,
    }
    originals = {name: getattr(CHECKER, name) for name in names_and_values}
    try:
        for name, value in names_and_values.items():
            setattr(CHECKER, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(CHECKER, name, value)


def make_result(claim_sha256: str) -> dict[str, object]:
    result: dict[str, object] = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-result",
        "schemaVersion": "2.0",
        "reviewId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-v2",
        "recordedDate": "2026-07-23",
        "status": "rung3_v2_candidate_inventory_recorded_awaiting_completion_manifest",
        "result": "bounded_candidate_location_inventory_recorded_semantic_review_not_performed",
        "nextAction": "publish_bound_v2_completion_manifest",
        "contentBinding": {},
        "permitBinding": {
            "path": CHECKER.PERMIT_PATH,
            "permitId": CHECKER.EXPECTED_PERMIT_ID,
            "rawSha256": CHECKER.EXPECTED_PERMIT_RAW_SHA256,
            "semanticSha256": CHECKER.EXPECTED_PERMIT_SEMANTIC_SHA256,
            "consumed": True,
        },
        "claimBinding": {
            "path": f"{CHECKER.OUTPUT_DIRECTORY}/{CHECKER.CLAIM_NAME}",
            "sha256": claim_sha256,
            "retained": True,
            "automaticRetryAllowed": False,
        },
        "archiveEvidence": {
            "receiptPath": CHECKER.RECEIPT_PATH,
            "absolutePathRecorded": False,
            "archiveEvidenceId": "G2R2E009",
            "bytes": SYNTHETIC_ARCHIVE_BYTES,
            "rawSha256": SYNTHETIC_ARCHIVE_SHA256,
            "mode": "0600",
            "linkCount": 1,
            "entryCount": len(SYNTHETIC_ENTRIES),
            "fileCount": len(SYNTHETIC_ENTRIES),
            "totalUncompressedBytes": SYNTHETIC_TOTAL_UNCOMPRESSED_BYTES,
            "modulePrefix": CHECKER.MODULE_PREFIX,
            "readThroughOneStableNoFollowFileDescriptor": True,
            "filesystemExtracted": False,
        },
        "creatorMetadataPolicy": {
            "policyVersion": "2.0",
            "semantics": CHECKER.EXPECTED_CREATOR_POLICY_SEMANTICS,
            "msDosCreatorSystem": 0,
            "unixCreatorSystem": 3,
            "msDosRegularFileCount": 1,
            "unixEntryCount": 1,
            "acceptedDosExternalAttributes": ["20"],
            "allowedDosAttributeMask": "21",
            "syntheticReadOnlyRegularMode": "100444",
            "filesystemExtractionAllowed": False,
            "sourceExecutionAllowed": False,
            "perPathProvenanceRecordedInSourceInventory": True,
        },
        "sourceInventory": {
            "treeSha256": synthetic_tree_sha256(),
            "entryCount": len(SYNTHETIC_ENTRIES),
            "sourceFilesObserved": 1,
            "entries": copy.deepcopy(SYNTHETIC_ENTRIES),
        },
        "dependencyMetadata": {
            "goMod": {
                "modulePath": "github.com/pion/ice/v4",
                "goVersion": "1.23",
                "toolchain": None,
                "requires": [{
                    "module": "example.invalid/dependency",
                    "version": "v1.2.3",
                    "indirect": False,
                }],
            },
            "goSum": {
                "recordCount": 1,
                "records": [{
                    "module": "example.invalid/dependency",
                    "version": "v1.2.3",
                    "h1": f"h1:{'A' * 43}=",
                }],
            },
            "inventoryOnlyNoDependencyAcquisition": True,
        },
        "licenseAndNoticeInventory": {
            "meaning": "inventory_only_not_legal_conclusion",
            "fileCount": 1,
            "files": [{
                "path": "LICENSE",
                "bytes": SYNTHETIC_ENTRIES[0]["bytes"],
                "sha256": SYNTHETIC_ENTRIES[0]["sha256"],
            }],
        },
        "patchUnitCandidateInventory": [
            {
                "patchUnit": patch_unit,
                "meaning": "lexical_candidate_locations_only_not_type_control_or_data_flow_proof",
                "hitCount": 1,
                "hits": [{
                    "path": "review.go",
                    "line": index + 1,
                    "ruleId": sorted(CHECKER.RULE_IDS[patch_unit])[0],
                }],
            }
            for index, patch_unit in enumerate(CHECKER.PATCH_UNITS)
        ],
        "profileVerificationUnits": [
            {
                "id": verification_id,
                "relatedPatchUnits": list(
                    CHECKER.VERIFICATION_CROSSWALK[verification_id]
                ),
                "status": "candidate_location_crosswalk_recorded_required_check_not_executed",
                "meaning": "candidate_location_crosswalk_only_not_semantic_review_or_required_check_evidence",
            }
            for verification_id in CHECKER.VERIFICATION_IDS
        ],
        "publicationCompletion": {
            "complete": False,
            "completionManifestRequired": True,
            "completionManifestPath": (
                f"{CHECKER.OUTPUT_DIRECTORY}/{CHECKER.MANIFEST_NAME}"
            ),
            "meaning": "this_result_is_explicitly_incomplete_without_the_bound_v2_completion_manifest",
        },
        "operationCounters": {
            "claimCreateCount": 1,
            "archiveOpenCount": 1,
            "archiveReadPassCount": 1,
            "archiveEntryEnumerationCount": 1,
            "reviewAdapterInvocationCount": 1,
            "materializationCount": 0,
            "sourceObservationCount": 1,
            "sourceWriteCount": 0,
            "sourceExecuteCount": 0,
            "subprocessCount": 0,
            "shellCount": 0,
            "dnsCount": 0,
            "networkOperationCount": 0,
            "socketCreateCount": 0,
            "gitOperationCount": 0,
            "packageManagerInvocationCount": 0,
            "reviewedSourceCompilerInvocationCount": 0,
            "verifiedAuxiliaryToolModulePythonCompileCount": 3,
            "deviceOperationCount": 0,
        },
        "executionBoundary": {
            "boundedCandidateLocationInventoryPerformed": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "archiveExtracted": False,
            "sourceMaterialized": False,
            "sourcePatched": False,
            "sourceExecuted": False,
            "dependencyInstalled": False,
            "reviewedSourceCompiled": False,
            "subprocessInvoked": False,
            "shellInvoked": False,
            "dnsUsed": False,
            "networkUsed": False,
            "socketCreated": False,
            "gitOperationPerformed": False,
            "deviceExecutionPerformed": False,
            "productionDeploymentAuthorized": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationRequired": True,
        },
        "evidenceBoundary": {
            "evidenceClass": "bounded_offline_static_inventory_not_os_sandbox_attestation",
            "sourceBodiesRecorded": False,
            "absoluteArchivePathRecorded": False,
            "secretsOrCredentialsRecorded": False,
            "controlOrDataFlowProven": False,
            "typeCorrectnessProven": False,
            "coverageProven": False,
            "licenseConclusionMade": False,
            "reviewedSourceCompileOrRuntimeEvidencePresent": False,
        },
        "personalProjectBoundary": {
            "technicalSafetyGatesRemainRequired": True,
            "repositoryOwnerAuthenticationIsNotATechnicalGate": True,
            "noAuthenticationOrUserActionRequested": True,
        },
    }
    return bound_document(result, "result_without_contentBinding")


def make_manifest(
    claim_sha256: str, result: dict[str, object], result_raw: bytes
) -> dict[str, object]:
    digest = CHECKER.sha256_bytes(result_raw)
    manifest: dict[str, object] = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-runtime-manifest",
        "schemaVersion": "2.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-runtime-manifest-v2",
        "recordedDate": "2026-07-23",
        "status": "rung3_v2_candidate_location_inventory_committed_semantic_review_not_performed",
        "result": "bounded_v2_candidate_location_inventory_publication_committed_semantic_review_not_performed",
        "nextAction": "prepare_separate_versioned_rung3_semantic_source_review_decision",
        "contentBinding": {},
        "permitRawSha256": CHECKER.EXPECTED_PERMIT_RAW_SHA256,
        "claimSha256": claim_sha256,
        "archiveRawSha256": SYNTHETIC_ARCHIVE_SHA256,
        "resultBinding": {
            "path": f"{CHECKER.OUTPUT_DIRECTORY}/{CHECKER.RESULT_NAME}",
            "bytes": len(result_raw),
            "rawSha256": digest,
            "requiredStatus": result["status"],
        },
        "artifacts": [{
            "path": f"{CHECKER.OUTPUT_DIRECTORY}/{CHECKER.RESULT_NAME}",
            "role": "bounded_offline_static_review_v2_result",
            "bytes": len(result_raw),
            "rawSha256": digest,
        }],
        "publication": {
            "soleCompletionMarker": True,
            "boundResultPublicationComplete": True,
            "boundedCandidateLocationInventoryPerformed": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "ownerOnlyDirectoryMode": "0700",
            "fileMode": "0600",
            "atomicNoReplace": True,
            "directoryFsyncRequired": True,
            "temporaryBackingFilesRetained": True,
            "temporaryNameDeletionAllowed": False,
            "publishedFileLinkCount": 2,
            "runtimePublicationRequiresPostRunReadbackForCanonicalEvidence": True,
            "sameUidHostileConcurrentFilesystemMutationOutOfScope": True,
            "sourceMaterializationCount": 0,
        },
        "executionBoundary": {
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationRequired": True,
        },
    }
    return bound_document(manifest, "manifest_without_contentBinding")


def write_exclusive(path: Path, raw: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(
        os.fspath(path),
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
        mode,
    )
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise RuntimeError("synthetic fixture short write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(path, mode, follow_symlinks=False)


def create_documents() -> tuple[bytes, dict[str, object], bytes, dict[str, object], bytes]:
    claim_raw = CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM)
    claim_sha256 = CHECKER.sha256_bytes(claim_raw)
    result = make_result(claim_sha256)
    result_raw = CHECKER.canonical_json_bytes(result)
    manifest = make_manifest(claim_sha256, result, result_raw)
    manifest_raw = CHECKER.canonical_json_bytes(manifest)
    return claim_raw, result, result_raw, manifest, manifest_raw


@contextmanager
def synthetic_publication(
    *,
    result_mutator=None,
    manifest_mutator=None,
):
    with tempfile.TemporaryDirectory(prefix="aetherlink-g2-r3-postrun-") as temporary:
        root = Path(temporary).resolve()
        output = root.joinpath(*CHECKER.OUTPUT_DIRECTORY_PARTS)
        output.mkdir(parents=True)
        os.chmod(output, 0o700)
        claim_raw, result, _result_raw, _manifest, _manifest_raw = create_documents()
        if result_mutator is not None:
            result_mutator(result)
            result = bound_document(result, "result_without_contentBinding")
        result_raw = CHECKER.canonical_json_bytes(result)
        claim_sha256 = CHECKER.sha256_bytes(claim_raw)
        manifest = make_manifest(claim_sha256, result, result_raw)
        if manifest_mutator is not None:
            manifest_mutator(manifest)
            manifest = bound_document(manifest, "manifest_without_contentBinding")
        manifest_raw = CHECKER.canonical_json_bytes(manifest)
        write_exclusive(output / CHECKER.CLAIM_NAME, claim_raw)
        write_exclusive(output / CHECKER.TEMP_RESULT_NAME, result_raw)
        os.link(
            output / CHECKER.TEMP_RESULT_NAME,
            output / CHECKER.RESULT_NAME,
            follow_symlinks=False,
        )
        write_exclusive(output / CHECKER.TEMP_MANIFEST_NAME, manifest_raw)
        os.link(
            output / CHECKER.TEMP_MANIFEST_NAME,
            output / CHECKER.MANIFEST_NAME,
            follow_symlinks=False,
        )
        yield root, output


class ContractTests(unittest.TestCase):
    def test_source_has_no_preexecution_authority_or_enumeration_capability(self):
        tree = ast.parse(CHECKER_SOURCE)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn(
            "run_p2p_nat_g2_pion_rung3_offline_review_v2_once", imported
        )
        self.assertNotIn(
            "check_p2p_nat_g2_pion_rung3_execution_permit_v2", imported
        )
        forbidden_calls = {"listdir", "scandir", "walk", "glob", "rglob"}
        observed_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(forbidden_calls.isdisjoint(observed_calls))
        self.assertNotIn(b"review-execution-policy-v2.json", CHECKER_SOURCE)
        self.assertNotIn(b"source-acquisition-receipt-v1.json\")", CHECKER_SOURCE)

    def test_strict_json_rejects_duplicate_cr_missing_lf_nonfinite_and_whitespace(self):
        samples = (
            b'{"a":1,"a":2}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":NaN}\n',
            b'{ "a":1}\\n',
        )
        for raw in samples:
            with self.subTest(raw=raw), self.assertRaises(CHECKER.CheckError):
                CHECKER.strict_canonical_json(raw, "synthetic")


class PublicationTests(unittest.TestCase):
    def test_valid_complete_publication_passes_without_writes_or_enumeration(self):
        with synthetic_constants(), synthetic_publication() as (root, _output):
            real_open = CHECKER.os.open
            observed_flags: list[int] = []

            def open_probe(path, flags, *args, **kwargs):
                observed_flags.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(CHECKER.os, "open", side_effect=open_probe), \
                    mock.patch.object(
                        CHECKER.os,
                        "listdir",
                        side_effect=AssertionError("directory enumeration forbidden"),
                    ), \
                    mock.patch.object(
                        CHECKER.os,
                        "scandir",
                        side_effect=AssertionError("directory enumeration forbidden"),
                    ):
                observed = CHECKER.check_post_run(root)
        self.assertEqual(observed["fixedNameReadCount"], 5)
        self.assertEqual(observed["directoryEnumerationCount"], 0)
        self.assertEqual(observed["archiveOpenCount"], 0)
        self.assertEqual(observed["fileWriteCount"], 0)
        write_mask = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        self.assertTrue(all(flags & write_mask == 0 for flags in observed_flags))
        self.assertTrue(observed["manifestWasValidatedLastAsSoleCompletionMarker"])

    def test_missing_any_fixed_name_fails_closed(self):
        for name in CHECKER.FIXED_READ_NAMES:
            with self.subTest(name=name), synthetic_constants(), \
                    synthetic_publication() as (root, output):
                (output / name).unlink()
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_post_run(root)

    def test_wrong_mode_symlink_and_wrong_hardlink_relationship_fail(self):
        with synthetic_constants(), synthetic_publication() as (root, output):
            os.chmod(output / CHECKER.RESULT_NAME, 0o640)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

        with synthetic_constants(), synthetic_publication() as (root, output):
            result = output / CHECKER.RESULT_NAME
            result.unlink()
            os.symlink(CHECKER.TEMP_RESULT_NAME, result)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

        with synthetic_constants(), synthetic_publication() as (root, output):
            result = output / CHECKER.RESULT_NAME
            raw = result.read_bytes()
            result.unlink()
            write_exclusive(result, raw)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

    def test_claim_must_have_one_link_and_final_pairs_exactly_two(self):
        with synthetic_constants(), synthetic_publication() as (root, output):
            os.link(output / CHECKER.CLAIM_NAME, output / "extra-claim-link")
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

        with synthetic_constants(), synthetic_publication() as (root, output):
            os.link(output / CHECKER.RESULT_NAME, output / "extra-result-link")
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

    def test_symlinked_output_ancestor_and_wrong_directory_mode_fail(self):
        with synthetic_constants(), synthetic_publication() as (root, output):
            os.chmod(output, 0o750)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

        with tempfile.TemporaryDirectory(
            prefix="aetherlink-g2-r3-postrun-link-"
        ) as temporary:
            root = Path(temporary).resolve()
            real_build = root / "real-build"
            output = real_build.joinpath(*CHECKER.OUTPUT_DIRECTORY_PARTS[1:])
            output.mkdir(parents=True)
            os.chmod(output, 0o700)
            os.symlink(real_build, root / "build")
            with synthetic_constants(), self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)


class SemanticMutationTests(unittest.TestCase):
    def assert_result_mutation_rejected(self, mutator) -> None:
        with synthetic_constants(), synthetic_publication(
            result_mutator=mutator
        ) as (root, _output):
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

    def assert_manifest_mutation_rejected(self, mutator) -> None:
        with synthetic_constants(), synthetic_publication(
            manifest_mutator=mutator
        ) as (root, _output):
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

    def test_permit_and_claim_bindings_are_exact(self):
        self.assert_result_mutation_rejected(
            lambda result: result["permitBinding"].__setitem__("rawSha256", "0" * 64)
        )
        self.assert_result_mutation_rejected(
            lambda result: result["claimBinding"].__setitem__("sha256", "1" * 64)
        )
        self.assert_manifest_mutation_rejected(
            lambda manifest: manifest.__setitem__("permitRawSha256", "0" * 64)
        )

    def test_result_binding_sha_bytes_status_and_artifact_are_exact(self):
        for key, value in (
            ("rawSha256", "0" * 64),
            ("bytes", 1),
            ("requiredStatus", "other"),
        ):
            with self.subTest(key=key):
                self.assert_manifest_mutation_rejected(
                    lambda manifest, key=key, value=value:
                    manifest["resultBinding"].__setitem__(key, value)
                )
        self.assert_manifest_mutation_rejected(
            lambda manifest: manifest["artifacts"][0].__setitem__(
                "rawSha256", "0" * 64
            )
        )

    def test_completion_marker_semantics_cannot_be_promoted_or_weakened(self):
        self.assert_result_mutation_rejected(
            lambda result: result["publicationCompletion"].__setitem__(
                "complete", True
            )
        )
        for key, value in (
            ("soleCompletionMarker", False),
            ("boundResultPublicationComplete", False),
            ("temporaryBackingFilesRetained", False),
            ("temporaryNameDeletionAllowed", True),
            ("publishedFileLinkCount", 1),
            ("runtimePublicationRequiresPostRunReadbackForCanonicalEvidence", False),
        ):
            with self.subTest(key=key):
                self.assert_manifest_mutation_rejected(
                    lambda manifest, key=key, value=value:
                    manifest["publication"].__setitem__(key, value)
                )

    def test_creator_metadata_unsafe_modes_and_counts_are_rejected(self):
        self.assert_result_mutation_rejected(
            lambda result: result["sourceInventory"]["entries"][0].__setitem__(
                "externalAttributes", "00000010"
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["sourceInventory"]["entries"][1].__setitem__(
                "effectiveUnixMode", "100755"
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["creatorMetadataPolicy"].__setitem__(
                "msDosRegularFileCount", 2
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["dependencyMetadata"]["goSum"].__setitem__(
                "recordCount", True
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["patchUnitCandidateInventory"][0].__setitem__(
                "hitCount", True
            )
        )

    def test_absolute_paths_source_bodies_and_secret_like_values_are_rejected(self):
        self.assert_result_mutation_rejected(
            lambda result: result["sourceInventory"]["entries"][1].__setitem__(
                "path", "/tmp/review.go"
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["sourceInventory"]["entries"][1].__setitem__(
                "sourceBody", SOURCE_BODY_SENTINEL
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["dependencyMetadata"]["goMod"]["requires"][0].__setitem__(
                "version", "Bearer abcdefghijklmnop"
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["dependencyMetadata"]["goSum"]["records"][0].__setitem__(
                "h1", "github_pat_abcdefghijklmnopqrstuvwxyz012345"
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: result["dependencyMetadata"]["goMod"]["requires"][0].__setitem__(
                "version", "v1.2.3-sk-ABCDEFGHIJKLMNOPQRSTUVWX"
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: (
                result["sourceInventory"]["entries"][0].__setitem__("bytes", 30),
                result["sourceInventory"].__setitem__(
                    "treeSha256",
                    CHECKER.sha256_bytes(b"LICENSE\0" + b"30\0" + (
                        result["sourceInventory"]["entries"][0]["sha256"]
                        + "\nreview.go\0"
                        + str(result["sourceInventory"]["entries"][1]["bytes"])
                        + "\0"
                        + result["sourceInventory"]["entries"][1]["sha256"]
                        + "\n"
                    ).encode("utf-8")),
                ),
            )
        )
        self.assert_result_mutation_rejected(
            lambda result: (
                result["licenseAndNoticeInventory"].__setitem__("fileCount", 0),
                result["licenseAndNoticeInventory"].__setitem__("files", []),
            )
        )
        claim_raw, _result, result_raw, _manifest, manifest_raw = create_documents()
        self.assertNotIn(SOURCE_BODY_SENTINEL.encode(), claim_raw)
        self.assertNotIn(SOURCE_BODY_SENTINEL.encode(), result_raw)
        self.assertNotIn(SOURCE_BODY_SENTINEL.encode(), manifest_raw)

    def test_nonclaim_boundaries_cannot_be_promoted(self):
        for section, key in (
            ("executionBoundary", "semanticSourceReviewPerformed"),
            ("executionBoundary", "rungThreeComplete"),
            ("evidenceBoundary", "sourceBodiesRecorded"),
            ("evidenceBoundary", "secretsOrCredentialsRecorded"),
        ):
            with self.subTest(section=section, key=key):
                self.assert_result_mutation_rejected(
                    lambda result, section=section, key=key:
                    result[section].__setitem__(key, True)
                )


if __name__ == "__main__":
    unittest.main()
