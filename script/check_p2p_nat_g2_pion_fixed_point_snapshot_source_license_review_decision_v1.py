#!/usr/bin/env python3
"""Validate the exact fixed-point snapshot source/license review decision."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "review-decision checker requires unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-fixed-point-snapshot-"
    "source-license-review-decision-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-fixed-point-snapshot-"
    "source-license-review-decision-v1.md"
)
CLOSURE_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "closure-review-decision-v1.json"
)
CLOSURE_READER_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "closure-review-decision-v1.md"
)
CLOSURE_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "closure_review_decision_v1.py"
)
CLOSURE_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_combined_fixed_point_"
    "closure_review_decision_v1.py"
)
IMPLEMENTATION_DECISION_PATH = (
    f"{BASE}/implementation-or-dependency-review-decision-v1.json"
)
STAGED_PLAN_PATH = (
    f"{BASE}/implementation-or-dependency-review-decision-v1/"
    "implementation/staged-fixed-point-source-closure.md"
)
ADAPTER_PATH = (
    "script/check_p2p_nat_g2_pion_fixed_point_snapshot_"
    "source_license_review_v1.py"
)
ADAPTER_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_fixed_point_snapshot_"
    "source_license_review_v1.py"
)
PINNED_RUNNER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_fixed_point_snapshot_"
    "source_license_review_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_fixed_point_snapshot_"
    "source_license_review_decision_v1.py"
)

DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-fixed-point-snapshot-"
    "dependency-source-and-license-review-decision-v1"
)
CLOSURE_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-v18-"
    "fixed-point-closure-review-decision-v1"
)

READER_RAW_SHA256 = (
    "28748d2e4220d171205d9e95ca5d235ec705f89d77a83da37a1afe0c10fd99e2"
)
CLOSURE_DECISION_RAW_SHA256 = (
    "affc2b60fd76b07a6e5af94a9492c5b0954d743ed26160e08fab970fbbbd42bd"
)
CLOSURE_DECISION_CONTENT_SHA256 = (
    "9d58b2d1411df8d3a33ae31d5b1868528bdc1b2949574a9d21e48c380666659b"
)
CLOSURE_READER_RAW_SHA256 = (
    "115668753e3b468858456e38f4572ec26784950d5cf41b1d75ae41318f00fe78"
)
CLOSURE_CHECKER_NORMALIZED_SHA256 = (
    "ba52ee4e9ed4fb58fd7b74a55b0702bfe88ea367a98005f1c09a786001098362"
)
CLOSURE_TESTS_RAW_SHA256 = (
    "2ed1acdf9bbdf89c1ca3cce797f3bbc42baf1652d2f131e1be80f3c55d11bd64"
)
IMPLEMENTATION_DECISION_RAW_SHA256 = (
    "6a14603c02c9aa9d9d78377b1c38a9f0d47391c0ac1ff8eea1769198ddc13ff8"
)
IMPLEMENTATION_DECISION_CONTENT_SHA256 = (
    "359e8e51ba3568f7f66bec4222149ef8b28162f35f4868f3d4a78ae4f4b5c7a6"
)
STAGED_PLAN_RAW_SHA256 = (
    "22d7cfbc2db9e34fab641167d227e650cb490dcfd9a402a4dff86e1f967234bc"
)
ADAPTER_RAW_SHA256 = (
    "830dab8a1e7fc8e3d5d2170232ade32ab9600594e18f9aae174027f4e4a8191c"
)
ADAPTER_NORMALIZED_SHA256 = (
    "dd426c7d4094908fcdc8e05822723853878495368ee98af56fdf4ad5d2d41fb0"
)
ADAPTER_TESTS_RAW_SHA256 = (
    "eaff69c534d7dfe9c503cdeea4b291aefdd3f1c8bea07d2bb94ae67762f9b9e8"
)
PINNED_RUNNER_RAW_SHA256 = (
    "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
)
SELF_NORMALIZED_SHA256 = (
    "574d294f0e4381957f823050fe2bbf4c4be0ade2ca714eeaa0583304eec5c4b3"
)
DECISION_TESTS_RAW_SHA256 = (
    "ea5692a7429076ebd2623d1b07433674ee5458019e8a95035e8221f0a8b02306"
)

V18_CANDIDATE_CONTENT_SHA256 = (
    "9dce50013314ec8934ad52ac57cb0de92e982c2334303fc77289f01bc9c285fb"
)
V18_GRAPH_SHA256 = (
    "a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba"
)
V18_FRONTIER_SHA256 = (
    "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570"
)
V18_INPUT_SET_SHA256 = (
    "321c50408978ff6b8795c17b51b53cd1dabf8f124e4a691c42cb2eb4fd961ded"
)
V18_SOURCE_BINDINGS_SHA256 = (
    "622a644a86e6ffe4596a3186034fbf141d964f34b5f3044f1b175db716d099f7"
)
V18_EXACT_INPUT_INVENTORY_SHA256 = (
    "a349cd67bd0f3355146b7008c5fcf595f79801bc1d7f8ab6d85f69178e565cda"
)
ADAPTER_REVIEW_BINDING_SET_SHA256 = (
    "3423f30722a5d9be67774be1b3dc7f25544ddd9b452c914e891085f0e3e24d23"
)
PROVIDER_GRAPH_CANONICAL_SHA256 = (
    "98cded658dc479296a5672bb26fbcacfbd1bb9314c7d186a6f0bc8a83d25c482"
)
PROVIDER_COVERAGE_SHA256 = (
    "7bb38b4396173308627878a664fb2bcb17397efb54c3349343ba349b47be1a7f"
)
PROVIDER_SOURCE_SURFACE_SHA256 = (
    "6f279a4e3ca5bc010e68150d57df561462818ccc81492636724b356172bf90fd"
)
PROVIDER_NARROW_LICENSE_SHA256 = (
    "4e6990198706a1b408b118473cd0b56ffd61c2626ea2d5bd654f4b0f97cb4e7d"
)
PROVIDER_SPECIAL_SOURCE_SHA256 = (
    "861f99fd8ca01f4224047869585ce7faf9f6e960deb3dcc221bba920f2a8e162"
)
PROVIDER_MODULE_METADATA_SHA256 = (
    "5454e8d2bc745c62891cd29f351f2073be826437f287c35e84b71d2270f5c9de"
)

MAXIMUM_FILE_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 2 * 1024 * 1024


class CheckError(RuntimeError):
    """A deterministic fail-closed validation error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CheckError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "E_JSON")
        result[key] = value
    return result


def reject_float(_: str) -> Any:
    raise CheckError("E_JSON")


def reject_constant(_: str) -> Any:
    raise CheckError("E_JSON")


def strict_json(raw: bytes) -> dict[str, Any]:
    require(len(raw) <= MAXIMUM_JSON_BYTES, "E_JSON")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=strict_object,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def safe_relative(value: str) -> str:
    require(
        type(value) is str
        and value
        and not value.startswith("/")
        and "\\" not in value
        and "\x00" not in value,
        "E_PATH",
    )
    parts = value.split("/")
    require(
        all(part not in {"", ".", ".."} for part in parts)
        and PurePosixPath(value).as_posix() == value,
        "E_PATH",
    )
    return value


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def read_stable_regular_file(
    root: Path,
    relative: str,
    maximum_bytes: int = MAXIMUM_FILE_BYTES,
) -> bytes:
    path = root / safe_relative(relative)
    try:
        before = os.lstat(path)
    except OSError as error:
        raise CheckError("E_FILE") from error
    require(
        stat.S_ISREG(before.st_mode)
        and before.st_uid == os.getuid()
        and before.st_nlink == 1
        and before.st_mode & 0o022 == 0
        and 0 <= before.st_size <= maximum_bytes,
        "E_FILE",
    )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        require(
            file_identity(opened) == file_identity(before),
            "E_FILE",
        )
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            require(bool(chunk), "E_FILE")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(descriptor, 1) == b"", "E_FILE")
    except OSError as error:
        raise CheckError("E_FILE") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as error:
        raise CheckError("E_FILE") from error
    require(file_identity(after) == file_identity(before), "E_FILE")
    raw = b"".join(chunks)
    require(len(raw) == before.st_size, "E_FILE")
    return raw


def normalized_constant_bytes(raw: bytes, name: str) -> bytes:
    marker = f'{name} = (\n    "'.encode("ascii")
    start = raw.find(marker)
    require(start >= 0, "E_NORMALIZED")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    require(
        payload_end - payload_start == 64
        and raw.find(marker, payload_start) < 0,
        "E_NORMALIZED",
    )
    return raw[:payload_start] + b"0" * 64 + raw[payload_end:]


def content_bound(body: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(body)
    require("contentBinding" not in value, "E_CONTENT")
    value["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "decision_without_contentBinding",
        "sha256": sha256(canonical_bytes(dict(body))),
    }
    return value


def expected_decision() -> dict[str, Any]:
    body = {
        "documentType": (
            "aetherlink.g2-pion-fixed-point-snapshot-dependency-"
            "source-and-license-review-decision"
        ),
        "schemaVersion": "1.0",
        "decisionId": DECISION_ID,
        "status": (
            "exact_fixed_point_snapshot_local_read_only_two_pass_"
            "review_authorized_adapter_validated_reviews_not_performed"
        ),
        "decision": (
            "authorize_exact_local_read_only_two_pass_snapshot_review_only"
        ),
        "result": (
            "exact_369_input_adapter_preflight_tests_and_full_scan_"
            "validated_no_source_license_security_review_result"
        ),
        "scope": (
            "exact_combined_v18_retained_snapshot_local_read_only_"
            "profile_source_license_security_review_preparation"
        ),
        "predecessorBindings": {
            "closureDecision": {
                "path": CLOSURE_DECISION_PATH,
                "decisionId": CLOSURE_DECISION_ID,
                "rawSha256": CLOSURE_DECISION_RAW_SHA256,
                "contentSha256": CLOSURE_DECISION_CONTENT_SHA256,
                "requiredNextAction": (
                    "prepare_separate_fixed_point_snapshot_dependency_"
                    "source_and_license_review_decision"
                ),
            },
            "closureReader": {
                "path": CLOSURE_READER_PATH,
                "rawSha256": CLOSURE_READER_RAW_SHA256,
            },
            "closureChecker": {
                "path": CLOSURE_CHECKER_PATH,
                "normalizedSelfSha256":
                    CLOSURE_CHECKER_NORMALIZED_SHA256,
            },
            "closureTests": {
                "path": CLOSURE_TESTS_PATH,
                "rawSha256": CLOSURE_TESTS_RAW_SHA256,
            },
            "implementationOrDependencyReviewDecision": {
                "path": IMPLEMENTATION_DECISION_PATH,
                "rawSha256": IMPLEMENTATION_DECISION_RAW_SHA256,
                "contentSha256":
                    IMPLEMENTATION_DECISION_CONTENT_SHA256,
                "selectedTreatmentUnit": (
                    "dependency_source_license_security_closure_review"
                ),
            },
            "stagedFixedPointSourceClosurePlan": {
                "path": STAGED_PLAN_PATH,
                "rawSha256": STAGED_PLAN_RAW_SHA256,
                "selectedOptionId": "staged-fixed-point-source-closure",
            },
        },
        "toolBindings": {
            "snapshotReviewAdapter": {
                "path": ADAPTER_PATH,
                "rawSha256": ADAPTER_RAW_SHA256,
                "normalizedSelfSha256": ADAPTER_NORMALIZED_SHA256,
            },
            "snapshotReviewAdapterTests": {
                "path": ADAPTER_TESTS_PATH,
                "rawSha256": ADAPTER_TESTS_RAW_SHA256,
                "passed": 14,
                "total": 14,
            },
            "pinnedReviewRunner": {
                "path": PINNED_RUNNER_PATH,
                "rawSha256": PINNED_RUNNER_RAW_SHA256,
                "writeEntryPointsRemovedBeforeUse": True,
            },
            "decisionReader": {
                "path": READER_PATH,
                "rawSha256": READER_RAW_SHA256,
            },
            "decisionChecker": {
                "path": SELF_PATH,
                "normalizedSelfSha256": SELF_NORMALIZED_SHA256,
            },
            "decisionTests": {
                "path": DECISION_TESTS_PATH,
                "rawSha256": DECISION_TESTS_RAW_SHA256,
            },
        },
        "snapshotBinding": {
            "sourceInputCount": 369,
            "moduleVersionTupleCount": 184,
            "archiveCount": 185,
            "archiveEntryCount": 72_304,
            "aggregateRawBytes": 356_092_640,
            "aggregateUncompressedBytes": 1_359_347_284,
            "maximumArchiveBytes": 9_237_329,
            "maximumEntriesPerArchive": 2_065,
            "maximumEntryBytes": 5_477_310,
            "maximumPathUtf8Bytes": 174,
            "maximumUncompressedBytesPerArchive": 41_103_581,
            "goFileCountBySuffix": 58_478,
            "assemblyFileCountBySuffix": 1_528,
            "nativeFileCountBySuffix": 110,
            "binaryFileCountBySuffix": 144,
            "broadLicenseCandidateCountByName": 362,
            "inputSetSha256": V18_INPUT_SET_SHA256,
            "sourceBindingsSha256": V18_SOURCE_BINDINGS_SHA256,
            "exactInputInventorySha256":
                V18_EXACT_INPUT_INVENTORY_SHA256,
            "reviewBindingSetSha256":
                ADAPTER_REVIEW_BINDING_SET_SHA256,
            "candidateContentSha256": V18_CANDIDATE_CONTENT_SHA256,
            "frontierSha256": V18_FRONTIER_SHA256,
            "profiles": [
                {
                    "profileId":
                        "android_api_26_through_36_arm64_v8a",
                    "goos": "android",
                    "goarch": "arm64",
                    "goVersion": "1.24",
                    "compiler": "gc",
                    "cgoEnabled": True,
                    "apiMinimum": 26,
                    "apiMaximum": 36,
                },
                {
                    "profileId": "macos_14_or_newer_arm64",
                    "goos": "darwin",
                    "goarch": "arm64",
                    "goVersion": "1.24",
                    "compiler": "gc",
                    "cgoEnabled": True,
                    "minimumOsMajor": 14,
                },
            ],
        },
        "validatedAdapterProjection": {
            "preflightValidationPassed": True,
            "adapterTestsPassed": 14,
            "adapterTestsTotal": 14,
            "fullScanValidationPassed": True,
            "stdoutProjectionPersisted": False,
            "moduleCoverageCount": 185,
            "moduleCoverageSha256": PROVIDER_COVERAGE_SHA256,
            "sourceFileCount": 58_478,
            "sourceSurfaceSha256": PROVIDER_SOURCE_SURFACE_SHA256,
            "pinnedRunnerNarrowLicenseCandidateCount": 195,
            "pinnedRunnerNarrowLicenseInventorySha256":
                PROVIDER_NARROW_LICENSE_SHA256,
            "broadLicenseCandidateCountByName": 362,
            "specialSourceCount": 11_150,
            "specialSourceInventorySha256":
                PROVIDER_SPECIAL_SOURCE_SHA256,
            "moduleMetadataCount": 185,
            "moduleMetadataSha256":
                PROVIDER_MODULE_METADATA_SHA256,
            "graph": {
                "algorithm": "go1.24_mvs_profile_union_fixed_point_v1",
                "graphSha256": V18_GRAPH_SHA256,
                "canonicalProjectionSha256":
                    PROVIDER_GRAPH_CANONICAL_SHA256,
                "graphNodeCount": 132,
                "graphEdgeCount": 1_047,
                "moduleNodeCount": 185,
                "moduleEdgeCount": 471,
                "selectedVersionCount": 33,
                "newTupleCount": 0,
                "unmappedExternalImportCount": 0,
                "unresolvedDeclaredExternalImportCount": 0,
                "fixedPointReached": True,
            },
            "compatibility": {
                "wave9PinnedLegacyBuildCompatibilityCount": 2,
                "malformedNonProductionGoFixtureCompatibilityCount": 30,
                "exactHashPathClassAndCountBounded": True,
            },
            "operationCounters": {
                "metadataPreflightZipArchiveOpenCount": 369,
                "delegatedFullScanZipArchiveOpenCount": 185,
                "totalZipArchiveOpenCount": 554,
                "archiveExtractionCount": 0,
                "sourceExecutionCount": 0,
                "sourceCompilationCount": 0,
                "subprocessCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
            },
        },
        "reviewContract": {
            "requiredModel": "GPT-5.6 Sol",
            "independentPassCountRequired": 2,
            "independentPassCountCompleted": 0,
            "sameImmutableByteBindingsRequired": True,
            "passesMayReadEachOtherBeforeBothComplete": False,
            "passOutputsAttestAuthority": False,
            "allSelectedVerticesRequireReview": True,
            "allProductionReachableBodiesRequireBothPasses": True,
            "generatedNativeCgoAssemblyAndBuildScriptsRequireCoverage": True,
            "licenseCandidateRuleIsSpdxConclusion": False,
            "staticReviewClaimsRuntimeBehavior": False,
            "disagreementDisposition": "unresolved",
            "unknownLicenseDisposition": "unresolved",
            "missingBodyDisposition": "unresolved",
            "ambiguousReachabilityDisposition": "unresolved",
            "graphDriftDisposition": "unresolved",
            "securityBlockerDisposition": "unresolved",
        },
        "authority": {
            "decisionRecorded": True,
            "localReadOnlyInspectionAuthorized": True,
            "retainedSourceByteReadAuthorized": True,
            "boundedInMemoryArchiveDecodeAuthorized": True,
            "boundedStaticSourceInspectionAuthorized": True,
            "buildProfileClassificationAuthorized": True,
            "stdoutOnlyProjectionAuthorized": True,
            "twoIndependentGpt56SolReviewsAuthorized": True,
            "acquisitionAuthorized": False,
            "fileWriteAuthorized": False,
            "publicationAuthorized": False,
            "manifestWriteAuthorized": False,
            "oneUseClaimWriteAuthorized": False,
            "readbackWriteAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "sourceMaterializationAuthorized": False,
            "sourceModificationAuthorized": False,
            "retainedSourceLoadOrExecutionAuthorized": False,
            "generatorTestHookOrBuildScriptExecutionAuthorized": False,
            "packageManagerAuthorized": False,
            "goCommandAuthorized": False,
            "compilerAuthorized": False,
            "shellOrSubprocessAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "networkAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "gitWriteAuthorized": False,
            "externalAuthenticationRequired": False,
            "repositoryOwnerIdentityProofRequired": False,
            "signatureRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "approvalRequired": False,
            "userActionRequired": False,
        },
        "outputContract": {
            "stdoutOnly": True,
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "documentTypes": [
                (
                    "aetherlink.g2-pion-fixed-point-snapshot-"
                    "source-license-review-preflight"
                ),
                (
                    "aetherlink.g2-pion-fixed-point-snapshot-"
                    "source-license-review-input"
                ),
                (
                    "aetherlink.g2-pion-fixed-point-snapshot-"
                    "source-license-review-error"
                ),
            ],
            "persistentOutputPathReserved": False,
            "preflightArtifactProduced": False,
            "reviewInputArtifactProduced": False,
            "reviewPassAArtifactProduced": False,
            "reviewPassBArtifactProduced": False,
            "reconciliationArtifactProduced": False,
            "sourceManifestProduced": False,
            "licenseInventoryProduced": False,
            "spdx23SbomProduced": False,
            "resultOrFailureArtifactProduced": False,
            "futurePersistentArtifactsPlannedOnly": [
                "independent_review_pass_a",
                "independent_review_pass_b",
                "disagreement_reconciliation",
                "source_provenance_profile_manifest",
                "license_inventory",
                "spdx_2_3_sbom",
                "result_or_failure",
            ],
        },
        "closure": {
            "dependencyFixedPointReached": True,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "licenseCompatibilityReviewed": False,
            "securityReviewComplete": False,
            "spdxSbomComplete": False,
            "sourceManifestComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "releaseReady": False,
        },
        "findingDisposition": {
            "canonicalFindingCount": 19,
            "patchRequiredCount": 7,
            "unresolvedCount": 12,
            "closedByThisDecisionCount": 0,
            "allCanonicalFindingsRemainOpen": True,
        },
        "nonClaims": {
            "adapterProjectionIsSourceReviewResult": False,
            "adapterProjectionIsSpdxSbom": False,
            "adapterProjectionIsLicenseCompatibilityDecision": False,
            "adapterProjectionIsSecurityAcceptance": False,
            "decisionClosesAnyCanonicalFinding": False,
            "decisionCompletesDependencyOrSemanticClosure": False,
            "decisionCompletesRungThreeOrV1": False,
            "decisionSelectsCandidateOrLibrary": False,
            "personalProjectRequiresOwnerAuthentication": False,
            "retainedSourceByteReadAuthorizesExecutableLoading": False,
            "toolModuleLoadingExecutesRetainedSource": False,
        },
        "nextAction": (
            "perform_two_independent_gpt_5_6_sol_fixed_point_snapshot_"
            "source_license_security_review_passes"
        ),
    }
    return content_bound(body)


def validate_decision_bytes(
    raw: bytes,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = strict_json(raw)
    require(raw == canonical_bytes(parsed), "E_CANONICAL_DECISION")
    without_binding = dict(parsed)
    binding = without_binding.pop("contentBinding", None)
    require(
        type(binding) is dict
        and binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": "decision_without_contentBinding",
            "sha256": sha256(canonical_bytes(without_binding)),
        },
        "E_CONTENT",
    )
    require(parsed == expected, "E_DECISION")
    return parsed


def validate_predecessors(
    closure_raw: bytes,
    implementation_raw: bytes,
) -> None:
    closure = strict_json(closure_raw)
    authority = closure.get("authority")
    require(
        closure.get("decisionId") == CLOSURE_DECISION_ID
        and closure.get("contentBinding", {}).get("sha256")
        == CLOSURE_DECISION_CONTENT_SHA256
        and closure.get("closure", {}).get(
            "dependencyFixedPointReached"
        )
        is True
        and closure.get("nextAction")
        == (
            "prepare_separate_fixed_point_snapshot_dependency_"
            "source_and_license_review_decision"
        )
        and type(authority) is dict
        and authority.get("externalAuthenticationRequired") is False
        and authority.get("userActionRequired") is False,
        "E_CLOSURE",
    )
    implementation = strict_json(implementation_raw)
    selections = implementation.get("treatmentUnitSelections")
    plan = implementation.get("implementationPlanBinding")
    require(
        implementation.get("contentBinding", {}).get("sha256")
        == IMPLEMENTATION_DECISION_CONTENT_SHA256
        and type(selections) is list
        and sum(
            type(row) is dict
            and row.get("selected") is True
            and row.get("unitId")
            == "dependency_source_license_security_closure_review"
            for row in selections
        )
        == 1
        and type(plan) is dict
        and plan.get("path") == STAGED_PLAN_PATH
        and plan.get("rawSha256") == STAGED_PLAN_RAW_SHA256
        and plan.get("selectedOptionId")
        == "staged-fixed-point-source-closure"
        and plan.get("planPrepared") is True
        and plan.get("planExecuted") is False,
        "E_IMPLEMENTATION",
    )


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    decision_raw = read_stable_regular_file(root, DECISION_PATH)
    reader_raw = read_stable_regular_file(root, READER_PATH)
    closure_raw = read_stable_regular_file(root, CLOSURE_DECISION_PATH)
    closure_reader_raw = read_stable_regular_file(
        root,
        CLOSURE_READER_PATH,
    )
    closure_checker_raw = read_stable_regular_file(
        root,
        CLOSURE_CHECKER_PATH,
    )
    closure_tests_raw = read_stable_regular_file(
        root,
        CLOSURE_TESTS_PATH,
    )
    implementation_raw = read_stable_regular_file(
        root,
        IMPLEMENTATION_DECISION_PATH,
    )
    staged_plan_raw = read_stable_regular_file(root, STAGED_PLAN_PATH)
    adapter_raw = read_stable_regular_file(root, ADAPTER_PATH)
    adapter_tests_raw = read_stable_regular_file(
        root,
        ADAPTER_TESTS_PATH,
    )
    runner_raw = read_stable_regular_file(root, PINNED_RUNNER_PATH)
    self_raw = read_stable_regular_file(root, SELF_PATH)
    decision_tests_raw = read_stable_regular_file(
        root,
        DECISION_TESTS_PATH,
    )

    require(sha256(reader_raw) == READER_RAW_SHA256, "E_READER")
    require(
        sha256(closure_raw) == CLOSURE_DECISION_RAW_SHA256,
        "E_CLOSURE",
    )
    require(
        sha256(closure_reader_raw) == CLOSURE_READER_RAW_SHA256,
        "E_CLOSURE_READER",
    )
    require(
        sha256(
            normalized_constant_bytes(
                closure_checker_raw,
                "SELF_NORMALIZED_SHA256",
            )
        )
        == CLOSURE_CHECKER_NORMALIZED_SHA256,
        "E_CLOSURE_CHECKER",
    )
    require(
        sha256(closure_tests_raw) == CLOSURE_TESTS_RAW_SHA256,
        "E_CLOSURE_TESTS",
    )
    require(
        sha256(implementation_raw)
        == IMPLEMENTATION_DECISION_RAW_SHA256,
        "E_IMPLEMENTATION",
    )
    require(
        sha256(staged_plan_raw) == STAGED_PLAN_RAW_SHA256,
        "E_STAGED_PLAN",
    )
    require(
        sha256(adapter_raw) == ADAPTER_RAW_SHA256
        and sha256(
            normalized_constant_bytes(
                adapter_raw,
                "SELF_NORMALIZED_SHA256",
            )
        )
        == ADAPTER_NORMALIZED_SHA256,
        "E_ADAPTER",
    )
    require(
        sha256(adapter_tests_raw) == ADAPTER_TESTS_RAW_SHA256,
        "E_ADAPTER_TESTS",
    )
    require(
        sha256(runner_raw) == PINNED_RUNNER_RAW_SHA256,
        "E_RUNNER",
    )
    require(
        sha256(
            normalized_constant_bytes(
                self_raw,
                "SELF_NORMALIZED_SHA256",
            )
        )
        == SELF_NORMALIZED_SHA256,
        "E_SELF",
    )
    require(
        sha256(decision_tests_raw) == DECISION_TESTS_RAW_SHA256,
        "E_DECISION_TESTS",
    )
    validate_predecessors(closure_raw, implementation_raw)
    expected = expected_decision()
    decision = validate_decision_bytes(decision_raw, expected)
    return {
        "documentType": (
            "aetherlink.g2-pion-fixed-point-snapshot-"
            "source-license-review-decision-check"
        ),
        "schemaVersion": "1.0",
        "validationPassed": True,
        "onDiskExactEqualityVerified": True,
        "decisionId": decision["decisionId"],
        "dependencyFixedPointReached": True,
        "independentPassCountCompleted": 0,
        "dependencySourceReviewed": False,
        "licenseCompatibilityReviewed": False,
        "securityReviewComplete": False,
        "rungThreeComplete": False,
        "releaseReady": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "gitWriteAuthorized": False,
        "fileWriteAuthorized": False,
        "nextAction": decision["nextAction"],
    }


def error_result(code: str) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-fixed-point-snapshot-"
            "source-license-review-decision-check-error"
        ),
        "schemaVersion": "1.0",
        "status": "verification_failed",
        "error": code,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "gitWriteAuthorized": False,
        "fileWriteAuthorized": False,
    }


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CheckError("E_ARGUMENT")


def parse_arguments(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-expected",
        action="store_true",
        help="print the exact canonical decision JSON",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = parse_arguments(argv)
        result = (
            expected_decision()
            if arguments.print_expected
            else check_repository(ROOT)
        )
        sys.stdout.buffer.write(canonical_bytes(result))
        sys.stdout.buffer.flush()
        return 0
    except CheckError as error:
        sys.stdout.buffer.write(canonical_bytes(error_result(error.code)))
        sys.stdout.buffer.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
