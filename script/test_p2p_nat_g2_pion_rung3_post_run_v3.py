#!/usr/bin/env python3
"""Synthetic-only tests for the independent G2 rung-three v3 readback."""

from __future__ import annotations

import ast
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung3_post_run_v3.py"
CHECKER_SOURCE = CHECKER_PATH.read_bytes()
CHECKER = ModuleType("g2_pion_rung3_post_run_v3_checker_under_test")
CHECKER.__file__ = os.fspath(CHECKER_PATH)
CHECKER.__package__ = None
exec(
    compile(CHECKER_SOURCE, os.fspath(CHECKER_PATH), "exec", flags=0, dont_inherit=True, optimize=0),
    CHECKER.__dict__,
    CHECKER.__dict__,
)

SOURCE_BODY_SENTINEL = "SOURCE_BODY_MUST_NEVER_APPEAR_64e92d"
SYNTHETIC_ARCHIVE_BYTES = 321
SYNTHETIC_ARCHIVE_SHA256 = hashlib.sha256(b"synthetic archive v3").hexdigest()
SYNTHETIC_TOTAL_BYTES = 93
ENTRIES = [
    {
        "path": "LICENSE",
        "bytes": 31,
        "sha256": hashlib.sha256(b"license metadata").hexdigest(),
        "category": "license_or_notice",
        "creatorSystem": 0,
        "externalAttributes": "00000020",
        "modeSource": "synthetic_read_only_regular_mode",
        "effectiveUnixMode": "100444",
    },
    {
        "path": "go.mod",
        "bytes": 16,
        "sha256": hashlib.sha256(b"module metadata").hexdigest(),
        "category": "go_module_metadata",
        "creatorSystem": 3,
        "externalAttributes": "81a40000",
        "modeSource": "archive_unix_mode",
        "effectiveUnixMode": "100644",
    },
    {
        "path": "review.go",
        "bytes": 46,
        "sha256": hashlib.sha256(f"unrecorded {SOURCE_BODY_SENTINEL}".encode()).hexdigest(),
        "category": "go_source",
        "creatorSystem": 3,
        "externalAttributes": "81a40000",
        "modeSource": "archive_unix_mode",
        "effectiveUnixMode": "100644",
    },
]


def tree_sha256() -> str:
    rows = [
        f"{entry['path']}\0{entry['bytes']}\0{entry['sha256']}\n".encode()
        for entry in ENTRIES
    ]
    return hashlib.sha256(b"".join(sorted(rows))).hexdigest()


def bound(document: dict[str, object], scope: str) -> dict[str, object]:
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
    values = {
        "EXPECTED_ARCHIVE_BYTES": SYNTHETIC_ARCHIVE_BYTES,
        "EXPECTED_ARCHIVE_SHA256": SYNTHETIC_ARCHIVE_SHA256,
        "EXPECTED_ENTRY_COUNT": len(ENTRIES),
        "EXPECTED_FILE_COUNT": len(ENTRIES),
        "EXPECTED_TOTAL_UNCOMPRESSED_BYTES": SYNTHETIC_TOTAL_BYTES,
    }
    originals = {name: getattr(CHECKER, name) for name in values}
    try:
        for name, value in values.items():
            setattr(CHECKER, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(CHECKER, name, value)


def representatives(rule_id: str, count: int) -> list[dict[str, object]]:
    rows = [
        {
            "path": "review.go",
            "line": line,
            "ruleId": rule_id,
            "rankSha256": CHECKER.representative_rank_sha256("review.go", line, rule_id),
        }
        for line in range(1, min(count, 8) + 1)
    ]
    rows.sort(
        key=lambda row: (
            row["rankSha256"],
            row["path"].encode(),
            row["line"],
            row["ruleId"].encode(),
        )
    )
    return rows


def candidate_inventory(*, large: bool = True) -> dict[str, object]:
    patch_rows = []
    overall_hits = 0
    overall_recorded = 0
    for unit_index, (patch_unit, expected_rules) in enumerate(CHECKER.REVIEW_RULES.items()):
        rule_rows = []
        unit_hits = 0
        unit_recorded = 0
        for rule_index, (rule_id, regex) in enumerate(expected_rules):
            total = 513 if large and unit_index == 0 and rule_index == 0 else 1
            reps = representatives(rule_id, total)
            recorded = len(reps)
            rule_rows.append({
                "ruleId": rule_id,
                "regex": regex,
                "totalHitCount": total,
                "recordedRepresentativeCount": recorded,
                "omittedHitCount": total - recorded,
                "truncated": total > recorded,
                "representatives": reps,
            })
            unit_hits += total
            unit_recorded += recorded
        patch_rows.append({
            "patchUnit": patch_unit,
            "meaning": CHECKER.LEXICAL_MEANING,
            "totalHitCount": unit_hits,
            "recordedRepresentativeCount": unit_recorded,
            "omittedHitCount": unit_hits - unit_recorded,
            "truncated": unit_hits > unit_recorded,
            "completeObservationSha256": hashlib.sha256(patch_unit.encode()).hexdigest(),
            "rules": rule_rows,
        })
        overall_hits += unit_hits
        overall_recorded += unit_recorded
    return {
        "schemaVersion": "3.0",
        "meaning": CHECKER.LEXICAL_MEANING,
        "sourceEntryCount": 1,
        "sourceTotalBytes": ENTRIES[2]["bytes"],
        "sourceLogicalLineCount": 600,
        "representativeLimitPerRule": 8,
        "completeObservationEncodingVersion": 1,
        "representativeRankEncodingVersion": 1,
        "totals": {
            "hitCount": overall_hits,
            "recordedRepresentativeCount": overall_recorded,
            "omittedHitCount": overall_hits - overall_recorded,
            "truncated": overall_hits > overall_recorded,
        },
        "patchUnits": patch_rows,
    }


def zero_first_candidate_unit(result: dict[str, object]) -> None:
    candidate = result["patchUnitCandidateInventory"]
    unit = candidate["patchUnits"][0]
    removed_hits = unit["totalHitCount"]
    removed_recorded = unit["recordedRepresentativeCount"]
    for rule in unit["rules"]:
        rule["totalHitCount"] = 0
        rule["recordedRepresentativeCount"] = 0
        rule["omittedHitCount"] = 0
        rule["truncated"] = False
        rule["representatives"] = []
    unit["totalHitCount"] = 0
    unit["recordedRepresentativeCount"] = 0
    unit["omittedHitCount"] = 0
    unit["truncated"] = False
    totals = candidate["totals"]
    totals["hitCount"] -= removed_hits
    totals["recordedRepresentativeCount"] -= removed_recorded
    totals["omittedHitCount"] = (
        totals["hitCount"] - totals["recordedRepresentativeCount"]
    )
    totals["truncated"] = (
        totals["hitCount"] > totals["recordedRepresentativeCount"]
    )


def exceed_rule_line_ceiling_consistently(result: dict[str, object]) -> None:
    candidate = result["patchUnitCandidateInventory"]
    unit = candidate["patchUnits"][0]
    rule = unit["rules"][0]
    old_total = rule["totalHitCount"]
    new_total = candidate["sourceLogicalLineCount"] + 1
    delta = new_total - old_total
    rule["totalHitCount"] = new_total
    rule["omittedHitCount"] = new_total - rule["recordedRepresentativeCount"]
    rule["truncated"] = True
    unit["totalHitCount"] += delta
    unit["omittedHitCount"] = (
        unit["totalHitCount"] - unit["recordedRepresentativeCount"]
    )
    unit["truncated"] = True
    candidate["totals"]["hitCount"] += delta
    candidate["totals"]["omittedHitCount"] = (
        candidate["totals"]["hitCount"]
        - candidate["totals"]["recordedRepresentativeCount"]
    )
    candidate["totals"]["truncated"] = True


def claim_raw() -> bytes:
    return CHECKER.canonical_json_bytes(CHECKER.EXPECTED_CLAIM)


def make_result(claim_digest: str, *, large: bool = True) -> dict[str, object]:
    result: dict[str, object] = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-result",
        "schemaVersion": "3.0",
        "reviewId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-v3",
        "recordedDate": "2026-07-23",
        "status": "rung3_v3_exact_lexical_candidate_aggregation_recorded_awaiting_completion_manifest",
        "result": "bounded_exact_candidate_totals_digests_and_ranked_representatives_recorded_semantic_review_not_performed",
        "nextAction": "publish_bound_v3_completion_manifest",
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
            "sha256": claim_digest,
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
            "entryCount": len(ENTRIES),
            "fileCount": len(ENTRIES),
            "totalUncompressedBytes": SYNTHETIC_TOTAL_BYTES,
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
            "unixEntryCount": 2,
            "acceptedDosExternalAttributes": ["20"],
            "allowedDosAttributeMask": "21",
            "syntheticReadOnlyRegularMode": "100444",
            "filesystemExtractionAllowed": False,
            "sourceExecutionAllowed": False,
            "perPathProvenanceRecordedInSourceInventory": True,
        },
        "sourceInventory": {
            "treeSha256": tree_sha256(),
            "entryCount": len(ENTRIES),
            "sourceFilesObserved": 1,
            "entries": copy.deepcopy(ENTRIES),
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
                "bytes": ENTRIES[0]["bytes"],
                "sha256": ENTRIES[0]["sha256"],
            }],
        },
        "patchUnitCandidateInventory": candidate_inventory(large=large),
        "profileVerificationUnits": [
            {
                "id": verification_id,
                "relatedPatchUnits": list(CHECKER.VERIFICATION_CROSSWALK[verification_id]),
                "status": "candidate_location_crosswalk_recorded_required_check_not_executed",
                "meaning": "candidate_location_crosswalk_only_not_semantic_review_or_required_check_evidence",
            }
            for verification_id in CHECKER.VERIFICATION_IDS
        ],
        "publicationCompletion": {
            "complete": False,
            "completionManifestRequired": True,
            "completionManifestPath": f"{CHECKER.OUTPUT_DIRECTORY}/{CHECKER.MANIFEST_NAME}",
            "meaning": "this_result_is_explicitly_incomplete_without_the_bound_v3_completion_manifest",
        },
        "operationCounters": {
            "claimCreateCount": 1,
            "archiveOpenCount": 1,
            "archiveReadPassCount": 1,
            "archiveEntryEnumerationCount": 1,
            "reviewAdapterInvocationCount": 2,
            "candidateAggregatorInvocationCount": 1,
            "candidateIndependentValidationPassCount": 1,
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
            "verifiedAuxiliaryToolModulePythonCompileCount": 4,
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
            "sourceLineDigestsRecorded": False,
            "absoluteArchivePathRecorded": False,
            "secretsOrCredentialsRecorded": False,
            "completeLexicalCandidateTotalsRecorded": True,
            "completeObservationDigestsRecordedPerPatchUnit": True,
            "candidateAggregationIndependentlyRecomputedByRunner": True,
            "representativeLimitPerRule": 8,
            "unboundedCandidateListRecorded": False,
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
    return bound(result, "result_without_contentBinding")


def make_manifest(claim_digest: str, result: dict[str, object], result_bytes: bytes) -> dict[str, object]:
    result_digest = CHECKER.sha256_bytes(result_bytes)
    manifest: dict[str, object] = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-runtime-manifest",
        "schemaVersion": "3.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-runtime-manifest-v3",
        "recordedDate": "2026-07-23",
        "status": "rung3_v3_exact_lexical_candidate_aggregation_committed_semantic_review_not_performed",
        "result": "bounded_v3_exact_candidate_totals_digests_and_ranked_representatives_publication_committed_semantic_review_not_performed",
        "nextAction": "prepare_separate_versioned_rung3_semantic_source_review_decision",
        "contentBinding": {},
        "permitRawSha256": CHECKER.EXPECTED_PERMIT_RAW_SHA256,
        "claimSha256": claim_digest,
        "archiveRawSha256": SYNTHETIC_ARCHIVE_SHA256,
        "resultBinding": {
            "path": f"{CHECKER.OUTPUT_DIRECTORY}/{CHECKER.RESULT_NAME}",
            "bytes": len(result_bytes),
            "rawSha256": result_digest,
            "requiredStatus": result["status"],
        },
        "artifacts": [{
            "path": f"{CHECKER.OUTPUT_DIRECTORY}/{CHECKER.RESULT_NAME}",
            "role": "bounded_offline_static_review_v3_result",
            "bytes": len(result_bytes),
            "rawSha256": result_digest,
        }],
        "publication": {
            "soleCompletionMarker": True,
            "boundResultPublicationComplete": True,
            "boundedCandidateLocationInventoryPerformed": True,
            "exactCandidateTotalsAndDigestsRecorded": True,
            "rankedRepresentativesRecordedPerRule": True,
            "representativeLimitPerRule": 8,
            "unboundedCandidateListRecorded": False,
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
    return bound(manifest, "manifest_without_contentBinding")


def write_exclusive(path: Path, raw: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(
        os.fspath(path),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(path, mode, follow_symlinks=False)


@contextmanager
def synthetic_publication(*, result_mutator=None, manifest_mutator=None, large: bool = True):
    with tempfile.TemporaryDirectory(prefix="aetherlink-v3-postrun-") as temporary:
        root = Path(temporary).resolve()
        output = root.joinpath(*CHECKER.OUTPUT_DIRECTORY_PARTS)
        output.mkdir(parents=True)
        os.chmod(output, 0o700)
        claim_bytes = claim_raw()
        claim_digest = CHECKER.sha256_bytes(claim_bytes)
        result = make_result(claim_digest, large=large)
        if result_mutator is not None:
            result_mutator(result)
            result = bound(result, "result_without_contentBinding")
        result_bytes = CHECKER.canonical_json_bytes(result)
        manifest = make_manifest(claim_digest, result, result_bytes)
        if manifest_mutator is not None:
            manifest_mutator(manifest)
            manifest = bound(manifest, "manifest_without_contentBinding")
        manifest_bytes = CHECKER.canonical_json_bytes(manifest)
        write_exclusive(output / CHECKER.CLAIM_NAME, claim_bytes)
        write_exclusive(output / CHECKER.TEMP_RESULT_NAME, result_bytes)
        os.link(output / CHECKER.TEMP_RESULT_NAME, output / CHECKER.RESULT_NAME, follow_symlinks=False)
        write_exclusive(output / CHECKER.TEMP_MANIFEST_NAME, manifest_bytes)
        os.link(output / CHECKER.TEMP_MANIFEST_NAME, output / CHECKER.MANIFEST_NAME, follow_symlinks=False)
        yield root, output


class ContractTests(unittest.TestCase):
    def test_source_is_outside_authority_and_has_no_enumeration_or_write_api(self):
        tree = ast.parse(CHECKER_SOURCE)
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue({"listdir", "scandir", "walk", "glob", "rglob"}.isdisjoint(calls))
        self.assertNotIn(b"execution-permit-core-manifest-v9", CHECKER_SOURCE)
        self.assertNotIn(b"execution-permit-checker-manifest-v10", CHECKER_SOURCE)
        self.assertNotIn(b"run_p2p_nat_g2_pion_rung3_offline_review_v3_once", CHECKER_SOURCE)

    def test_strict_canonical_json_rejects_duplicate_cr_missing_lf_nonfinite_and_spacing(self):
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":NaN}\n',
            b'{ "a":1}\n',
        ):
            with self.subTest(raw=raw), self.assertRaises(CHECKER.CheckError):
                CHECKER.strict_canonical_json(raw, "fixture")


class PublicationTests(unittest.TestCase):
    def test_valid_513_plus_truncated_publication_passes_with_read_only_fixed_names(self):
        with synthetic_constants(), synthetic_publication(large=True) as (root, _output):
            real_open = CHECKER.os.open
            flags_seen = []

            def probe(path, flags, *args, **kwargs):
                flags_seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(CHECKER.os, "open", side_effect=probe), \
                    mock.patch.object(CHECKER.os, "listdir", side_effect=AssertionError()), \
                    mock.patch.object(CHECKER.os, "scandir", side_effect=AssertionError()):
                result = CHECKER.check_post_run(root)
        self.assertEqual(result["fixedNameReadCount"], 5)
        self.assertEqual(result["directoryEnumerationCount"], 0)
        self.assertEqual(result["archiveOpenCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertFalse(
            result["candidateCompleteObservationDigestIndependentlyReproduced"]
        )
        self.assertFalse(result["candidateCountsIndependentlyReproduced"])
        self.assertFalse(
            result["candidateRepresentativeRuleMatchesIndependentlyReproduced"]
        )
        self.assertFalse(
            result["candidateLowestRankSelectionIndependentlyReproduced"]
        )
        write_mask = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        self.assertTrue(all(flags & write_mask == 0 for flags in flags_seen))

    def test_missing_each_fixed_name_fails_closed(self):
        for name in CHECKER.FIXED_READ_NAMES:
            with self.subTest(name=name), synthetic_constants(), synthetic_publication() as (root, output):
                os.unlink(output / name)
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_post_run(root)

    def test_symlink_mode_and_hardlink_pair_swaps_fail_closed(self):
        with synthetic_constants(), synthetic_publication() as (root, output):
            os.chmod(output / CHECKER.CLAIM_NAME, 0o644)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)
        with synthetic_constants(), synthetic_publication() as (root, output):
            os.unlink(output / CHECKER.RESULT_NAME)
            os.symlink(CHECKER.TEMP_RESULT_NAME, output / CHECKER.RESULT_NAME)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)
        with synthetic_constants(), synthetic_publication() as (root, output):
            result_bytes = (output / CHECKER.RESULT_NAME).read_bytes()
            os.unlink(output / CHECKER.RESULT_NAME)
            write_exclusive(output / CHECKER.RESULT_NAME, result_bytes)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

    def assert_result_mutation_rejected(self, mutator):
        with synthetic_constants(), synthetic_publication(result_mutator=mutator) as (root, _output):
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)

    def test_candidate_arithmetic_bool_rank_regex_digest_path_and_line_mutations_fail(self):
        mutators = [
            lambda result: result["patchUnitCandidateInventory"]["totals"].__setitem__("hitCount", True),
            lambda result: result["patchUnitCandidateInventory"]["patchUnits"][0]["rules"][0].__setitem__("omittedHitCount", 0),
            lambda result: result["patchUnitCandidateInventory"]["patchUnits"][0]["rules"][0]["representatives"][0].__setitem__("rankSha256", "0" * 64),
            lambda result: result["patchUnitCandidateInventory"]["patchUnits"][0]["rules"][0].__setitem__("regex", ".*"),
            lambda result: result["patchUnitCandidateInventory"]["patchUnits"][0].__setitem__("completeObservationSha256", "xyz"),
            lambda result: result["patchUnitCandidateInventory"]["patchUnits"][0]["rules"][0]["representatives"][0].__setitem__("path", "../review.go"),
            lambda result: result["patchUnitCandidateInventory"]["patchUnits"][0]["rules"][0]["representatives"][0].__setitem__("line", 601),
            lambda result: result["patchUnitCandidateInventory"].__setitem__(
                "sourceLogicalLineCount",
                CHECKER.MAXIMUM_TOTAL_LOGICAL_LINES + 1,
            ),
            zero_first_candidate_unit,
            exceed_rule_line_ceiling_consistently,
        ]
        for mutator in mutators:
            with self.subTest(mutator=mutator):
                self.assert_result_mutation_rejected(mutator)

    def test_inventory_dependency_license_creator_secret_body_and_completion_mutations_fail(self):
        mutators = [
            lambda result: result["sourceInventory"].__setitem__("treeSha256", "0" * 64),
            lambda result: result["dependencyMetadata"]["goMod"].__setitem__("modulePath", "ghp_" + "A" * 24),
            lambda result: result["licenseAndNoticeInventory"].__setitem__("files", []),
            lambda result: result["creatorMetadataPolicy"].__setitem__("policyVersion", "1.0"),
            lambda result: result["personalProjectBoundary"].__setitem__("note", SOURCE_BODY_SENTINEL),
            lambda result: result["publicationCompletion"].__setitem__("complete", True),
            lambda result: result["operationCounters"].__setitem__("networkOperationCount", 1),
            lambda result: result["executionBoundary"].__setitem__("semanticSourceReviewPerformed", True),
        ]
        for mutator in mutators:
            with self.subTest(mutator=mutator):
                self.assert_result_mutation_rejected(mutator)

    def test_manifest_binding_hash_completion_and_order_mutations_fail(self):
        mutators = [
            lambda manifest: manifest["resultBinding"].__setitem__("rawSha256", "0" * 64),
            lambda manifest: manifest["publication"].__setitem__("soleCompletionMarker", False),
            lambda manifest: manifest["publication"].__setitem__("publishedFileLinkCount", 1),
            lambda manifest: manifest.__setitem__("claimSha256", "0" * 64),
        ]
        for mutator in mutators:
            with self.subTest(mutator=mutator), synthetic_constants(), synthetic_publication(manifest_mutator=mutator) as (root, _output):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_post_run(root)

    def test_content_binding_and_noncanonical_publication_fail(self):
        with synthetic_constants(), synthetic_publication() as (root, output):
            raw = (output / CHECKER.RESULT_NAME).read_bytes()
            os.unlink(output / CHECKER.RESULT_NAME)
            os.unlink(output / CHECKER.TEMP_RESULT_NAME)
            poisoned = raw.replace(b'"sha256":"', b'"sha256":"0', 1)
            write_exclusive(output / CHECKER.TEMP_RESULT_NAME, poisoned)
            os.link(output / CHECKER.TEMP_RESULT_NAME, output / CHECKER.RESULT_NAME)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_post_run(root)


if __name__ == "__main__":
    unittest.main()
