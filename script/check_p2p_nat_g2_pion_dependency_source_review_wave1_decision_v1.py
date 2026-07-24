#!/usr/bin/env python3
"""Validate the bounded G2 dependency source-review wave-one decision.

This checker binds the completed v3 acquisition/readback set to the next
staged fixed-point work package.  It validates preparation only: it does not
inspect archive members, materialize source, execute code, use the network, or
write files.
"""

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
            "dependency source-review decision checker requires unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_source_review_wave1_decision_v1.py"
)
TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_source_review_wave1_decision_v1.py"
)
DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-review-wave1-decision-v1.json"
)
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-source-review-wave1-decision-v1"
)
POST_VERIFIER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3_post_verify_v3.py"
)
POST_VERIFIER_RAW_SHA256 = (
    "27b7ebbac46cd0e4a08b1dd87feabe1e1cd90c79d0c3a0ee1d5b5366f4a0d895"
)
POST_VERIFIER_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3_post_verify_v3.py"
)
POST_VERIFIER_TESTS_RAW_SHA256 = (
    "5bdda8fae3229907b2c224a81a217a62c1899917fb3f64781add39101806a786"
)
IMPLEMENTATION_DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "implementation-or-dependency-review-decision-v1.json"
)
IMPLEMENTATION_DECISION_RAW_SHA256 = (
    "6a14603c02c9aa9d9d78377b1c38a9f0d47391c0ac1ff8eea1769198ddc13ff8"
)
IMPLEMENTATION_PLAN_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "implementation-or-dependency-review-decision-v1/implementation/"
    "staged-fixed-point-source-closure.md"
)
IMPLEMENTATION_PLAN_RAW_SHA256 = (
    "22d7cfbc2db9e34fab641167d227e650cb490dcfd9a402a4dff86e1f967234bc"
)
SOURCE_DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
SOURCE_DECISION_RAW_SHA256 = (
    "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
)
ACQUISITION_RECEIPT_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-receipt-v3.json"
)
ACQUISITION_RECEIPT_RAW_SHA256 = (
    "10d63291813d66c1d7c9edaf7108842113bccbc2a84f799ddafe3f02a820f3b3"
)
ACQUISITION_MANIFEST_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-manifest-v3.json"
)
ACQUISITION_MANIFEST_RAW_SHA256 = (
    "9763dd83e46a57404bbd3d4c18ecf2f151bdf4e1c17ba3131e4b726b32a54e6b"
)
READBACK_RECEIPT_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-v1.json"
)
READBACK_RECEIPT_RAW_SHA256 = (
    "63c7db8fce4a1c5c26dba84c22be9ea79afda95afb76506a10457e1ac9e910e0"
)
READBACK_MANIFEST_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json"
)
READBACK_MANIFEST_RAW_SHA256 = (
    "a62e1cc1508a127fa1f5cb4a5009cf7ddeae87ef40172d1c7327c51f8cbc3b96"
)
POST_DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-"
    "post-verification-decision-v3.json"
)
POST_DECISION_RAW_SHA256 = (
    "9ad7b632782131c9ac9c327fc40942dab08eb3e6b308f582dbee1650ba8f76ba"
)
ROOT_ARCHIVE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
ROOT_ARCHIVE_RAW_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
FINAL_DIRECTORY_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-1-v3/accepted"
)
ORDERED_SOURCE_SET_SHA256 = (
    "2b0176d6d2b800c9a2abd34bf06279403e6f008bd3475ff45970abf11e843246"
)
MAXIMUM_TOOL_BYTES = 2_097_152
MAXIMUM_JSON_BYTES = 2_097_152
MAXIMUM_PLAN_BYTES = 262_144
MAXIMUM_ROOT_ARCHIVE_BYTES = 16_777_216


class DecisionError(RuntimeError):
    """A closed decision-validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def reject_float(_: str) -> Any:
    raise DecisionError("floating-point JSON values are forbidden")


def reject_constant(_: str) -> Any:
    raise DecisionError("non-finite JSON values are forbidden")


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "duplicate JSON key")
        result[key] = value
    return result


def validate_json_values(value: Any, label: str) -> None:
    if value is None or type(value) in {bool, str}:
        return
    if type(value) is int:
        require(-(2**63) <= value <= 2**63 - 1, f"{label}: integer range")
        return
    if type(value) is list:
        for item in value:
            validate_json_values(item, label)
        return
    if type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, f"{label}: object key type")
            validate_json_values(item, label)
        return
    if type(value) is float:
        require(math.isfinite(value), f"{label}: finite number")
    raise DecisionError(f"{label}: unsupported JSON value")


def strict_json(raw: bytes, label: str) -> Any:
    require(len(raw) <= MAXIMUM_JSON_BYTES, f"{label}: byte limit")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=strict_object,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionError(f"{label}: invalid JSON") from error
    validate_json_values(value, label)
    return value


def canonical_json_bytes(value: Any) -> bytes:
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


def path_components(relative: str) -> list[str]:
    require(
        type(relative) is str
        and relative
        and not relative.startswith("/")
        and "\x00" not in relative,
        "invalid relative path",
    )
    components = relative.split("/")
    require(
        all(component not in {"", ".", ".."} for component in components),
        "unsafe relative path",
    )
    return components


def open_directory(parent_fd: int, component: str) -> int:
    return os.open(
        component,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | os.O_CLOEXEC
        | os.O_NONBLOCK,
        dir_fd=parent_fd,
    )


def read_fd(fd: int, size: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while offset < size:
        chunk = os.pread(fd, min(1_048_576, size - offset), offset)
        require(chunk, "unexpected EOF")
        chunks.append(chunk)
        offset += len(chunk)
    require(os.pread(fd, 1, size) == b"", "file grew during read")
    return b"".join(chunks)


def read_held(
    root: Path,
    relative: str,
    *,
    maximum_bytes: int,
    owner_only: bool = False,
) -> bytes:
    components = path_components(relative)
    root_fd = os.open(
        root,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | os.O_CLOEXEC
        | os.O_NONBLOCK,
    )
    directory_fds = [root_fd]
    directory_identities: list[tuple[int, int]] = []
    file_fd: int | None = None
    try:
        root_stat = os.fstat(root_fd)
        require(stat.S_ISDIR(root_stat.st_mode), "root is not a directory")
        directory_identities.append((root_stat.st_dev, root_stat.st_ino))
        current_fd = root_fd
        for component in components[:-1]:
            current_fd = open_directory(current_fd, component)
            directory_fds.append(current_fd)
            current_stat = os.fstat(current_fd)
            require(
                stat.S_ISDIR(current_stat.st_mode),
                f"{relative}: non-directory ancestor",
            )
            directory_identities.append(
                (current_stat.st_dev, current_stat.st_ino)
            )
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=current_fd,
        )
        before = os.fstat(file_fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and 0 <= before.st_size <= maximum_bytes,
            f"{relative}: regular single-link bounded file required",
        )
        if owner_only:
            require(
                before.st_uid == os.getuid()
                and stat.S_IMODE(before.st_mode) & 0o077 == 0,
                f"{relative}: owner-only file required",
            )
        first = read_fd(file_fd, before.st_size)
        second = read_fd(file_fd, before.st_size)
        require(first == second, f"{relative}: unstable bytes")
        after = os.fstat(file_fd)
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
                before.st_mode,
                before.st_nlink,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
                after.st_mode,
                after.st_nlink,
            ),
            f"{relative}: file identity changed",
        )

        verify_root = os.open(
            root,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
            | os.O_NONBLOCK,
        )
        verify_fds = [verify_root]
        try:
            verify_current = verify_root
            verify_stat = os.fstat(verify_current)
            require(
                (verify_stat.st_dev, verify_stat.st_ino)
                == directory_identities[0],
                f"{relative}: root identity changed",
            )
            for index, component in enumerate(components[:-1], start=1):
                verify_current = open_directory(verify_current, component)
                verify_fds.append(verify_current)
                verify_stat = os.fstat(verify_current)
                require(
                    (verify_stat.st_dev, verify_stat.st_ino)
                    == directory_identities[index],
                    f"{relative}: ancestor identity changed",
                )
            name_stat = os.stat(
                components[-1],
                dir_fd=verify_current,
                follow_symlinks=False,
            )
            require(
                stat.S_ISREG(name_stat.st_mode)
                and (name_stat.st_dev, name_stat.st_ino)
                == (before.st_dev, before.st_ino),
                f"{relative}: final name identity changed",
            )
        finally:
            for fd in reversed(verify_fds):
                os.close(fd)
        return first
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for fd in reversed(directory_fds):
            os.close(fd)


def binding(path: str, raw_sha256: str) -> dict[str, str]:
    return {"path": path, "rawSha256": raw_sha256}


def expected_decision() -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-bounded-dependency-source-review-wave1-decision"
        ),
        "schemaVersion": "1.0",
        "decisionId": DECISION_ID,
        "recordedDate": "2026-07-24",
        "status": (
            "dependency_source_review_wave1_decision_recorded_"
            "execution_not_authorized"
        ),
        "result": (
            "fixed_hash_v3_intake_bound_wp4_graph_frontier_"
            "review_contract_prepared"
        ),
        "predecessorBindings": {
            "implementationDecision": binding(
                IMPLEMENTATION_DECISION_PATH,
                IMPLEMENTATION_DECISION_RAW_SHA256,
            ),
            "stagedFixedPointPlan": binding(
                IMPLEMENTATION_PLAN_PATH,
                IMPLEMENTATION_PLAN_RAW_SHA256,
            ),
            "sourceIdentityDecision": binding(
                SOURCE_DECISION_PATH,
                SOURCE_DECISION_RAW_SHA256,
            ),
            "acquisitionReceipt": binding(
                ACQUISITION_RECEIPT_PATH,
                ACQUISITION_RECEIPT_RAW_SHA256,
            ),
            "acquisitionManifest": binding(
                ACQUISITION_MANIFEST_PATH,
                ACQUISITION_MANIFEST_RAW_SHA256,
            ),
            "readbackReceipt": binding(
                READBACK_RECEIPT_PATH,
                READBACK_RECEIPT_RAW_SHA256,
            ),
            "readbackManifest": binding(
                READBACK_MANIFEST_PATH,
                READBACK_MANIFEST_RAW_SHA256,
            ),
            "postVerificationDecision": binding(
                POST_DECISION_PATH,
                POST_DECISION_RAW_SHA256,
            ),
            "postVerifier": binding(
                POST_VERIFIER_PATH,
                POST_VERIFIER_RAW_SHA256,
            ),
            "postVerifierTests": binding(
                POST_VERIFIER_TESTS_PATH,
                POST_VERIFIER_TESTS_RAW_SHA256,
            ),
        },
        "sourceSetBinding": {
            "rootModule": "github.com/pion/ice/v4",
            "rootVersion": "v4.3.0",
            "rootUpstreamCommit": (
                "1e8716372f2bb52e45bf2a7172e4fb1004251c46"
            ),
            "rootArchivePath": ROOT_ARCHIVE_PATH,
            "rootArchiveRawSha256": ROOT_ARCHIVE_RAW_SHA256,
            "rootSourceTreeSha256": (
                "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
            ),
            "rootGoModRawSha256": (
                "5044428710b5a718aad517eed5c08e1933378efa3d9b4245853cfb312560aca4"
            ),
            "rootGoSumRawSha256": (
                "b47d7d5f3bb8c8b85b3283585f97ea6bd0a8b97427b49068b9f5685ddd953887"
            ),
            "dependencyDirectoryPath": FINAL_DIRECTORY_PATH,
            "dependencyTupleCount": 19,
            "retainedResourceCount": 38,
            "retainedZipCount": 19,
            "retainedModCount": 19,
            "observedRegularFileCount": 43,
            "aggregateRawByteSize": 13178024,
            "aggregateZipRawByteSize": 13174173,
            "aggregateModRawByteSize": 3851,
            "aggregateEntryCount": 2907,
            "aggregateUncompressedByteCount": 31851201,
            "orderedSourceSetSha256": ORDERED_SOURCE_SET_SHA256,
            "resourceRowsBoundByAcquisitionReceipt": True,
            "terminalV1V2V3EvidenceMustRemainImmutable": True,
        },
        "profileBinding": {
            "sourceDecisionPath": SOURCE_DECISION_PATH,
            "sourceDecisionRawSha256": SOURCE_DECISION_RAW_SHA256,
            "goVersion": "1.24.0",
            "compilerConstraint": "gc",
            "profileMode": "union_of_exact_android_and_macos_v1_profiles",
            "profileIds": [
                "android_api_26_through_36_arm64_v8a",
                "macos_14_or_newer_arm64",
            ],
            "graphAlgorithm": "go1.24_mvs_profile_union_fixed_point_v1",
            "fixedPointRule": (
                "zero_new_selected_tuples_and_two_independent_equal_"
                "node_edge_and_graph_digests"
            ),
        },
        "workPackage": {
            "planWorkPackage": "WP4_expand_exact_graph_to_fixed_point",
            "executionUnit": "review_wave1_frontier_discovery_v1",
            "scope": (
                "module_metadata_graph_candidate_license_native_inventory_only"
            ),
            "rootPackageSeedsByProfile": {
                "android_api_26_through_36_arm64_v8a": [
                    "github.com/pion/ice/v4"
                ],
                "macos_14_or_newer_arm64": ["github.com/pion/ice/v4"],
            },
            "inputRootModuleCount": 1,
            "inputDependencyModuleCount": 19,
            "inputArchiveCount": 20,
            "inputModResourceCount": 19,
            "filesystemExtractionRequired": False,
            "inMemoryArchiveInspectionRequired": True,
            "sourceExecutionRequired": False,
            "packageManagerRequired": False,
            "compilerRequired": False,
            "networkRequired": False,
            "twoIndependentGraphReconstructionsRequired": True,
            "newSelectedTupleRequiresNewVersionedAcquisitionDecision": True,
            "zeroNewTupleAloneProvesFixedPoint": False,
        },
        "futureExecutionContract": {
            "oneUsePermitRequired": True,
            "runnerAndTestsMustBeByteBoundByPermit": True,
            "archiveMemberMaterializationAllowed": False,
            "boundedInMemoryArchiveMemberDecodingAllowed": True,
            "sourceTextStaticInspectionAllowed": True,
            "sourceOrGeneratorExecutionAllowed": False,
            "testHookOrBuildScriptExecutionAllowed": False,
            "goCommandAllowed": False,
            "subprocessAllowed": False,
            "socketOrNetworkAllowed": False,
            "orderedSteps": [
                "revalidate_fixed_hash_v3_intake",
                "read_root_and_19_dependency_archives_in_memory",
                "classify_profile_reachable_files_and_imports",
                "parse_exact_module_metadata",
                "resolve_profile_union_package_and_module_edges",
                "apply_minimum_version_selection_and_context_quarantine",
                "record_new_tuple_frontier_and_ordered_graph_digests",
                "record_license_native_generated_and_build_script_inventory",
                "publish_result_then_manifest_last",
                "run_separate_independent_readback",
            ],
            "firstMismatchRule": (
                "stop_publish_bounded_failure_no_partial_result_"
                "require_new_versioned_decision"
            ),
        },
        "classificationContract": {
            "productionProfiles": [
                "android_api_26_through_36_arm64_v8a",
                "macos_14_or_newer_arm64",
            ],
            "excludedClasses": [
                "test_files",
                "external_test_packages",
                "examples",
                "commands",
                "tools",
                "benchmarks",
                "fuzz_entry_points",
            ],
            "separatelyClassifiedClasses": [
                "generated_source",
                "assembly",
                "cgo",
                "native_source",
                "vendored_source",
                "build_scripts",
                "license_and_notice",
                "checksum_only_context",
                "replaced",
                "excluded",
            ],
            "requiredOutputs": [
                "source_inventory",
                "profile_package_nodes",
                "profile_import_edges",
                "module_nodes",
                "module_edges",
                "new_tuple_frontier",
                "license_notice_inventory",
                "native_generated_build_script_inventory",
                "ordered_node_edge_and_graph_digests",
                "review_input_coverage",
            ],
            "disagreementRule": "retain_unresolved_and_keep_closure_false",
        },
        "resourceLimits": {
            "maximumInputArchives": 20,
            "maximumDependencyResources": 38,
            "maximumEntriesPerArchive": 16384,
            "maximumAggregateEntries": 131072,
            "maximumSingleFileBytes": 16777216,
            "maximumAggregateCompressedBytes": 134217728,
            "maximumAggregateUncompressedBytes": 1073741824,
            "maximumPathBytes": 1024,
            "maximumPathComponents": 64,
            "maximumComponentBytes": 255,
            "maximumGraphNodes": 512,
            "maximumGraphEdges": 4096,
            "maximumPackageNodes": 65536,
            "maximumImportEdges": 262144,
            "maximumLicenseNoticeFiles": 4096,
            "maximumReviewInputFiles": 131072,
            "maximumResultOrFailureBytes": 8388608,
        },
        "plannedArtifacts": {
            "resultPath": (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-review-wave1-result-v1.json"
            ),
            "failurePath": (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-review-wave1-failure-v1.json"
            ),
            "manifestPath": (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-review-wave1-manifest-v1.json"
            ),
            "manifestWrittenLast": True,
            "partialResultAllowed": False,
            "independentReadbackRequired": True,
        },
        "decisionChecker": {
            "checkerPath": SELF_PATH,
            "checkerTestsPath": TESTS_PATH,
            "futureExecutionPermitMustBindCheckerAndTestsRawSha256": True,
            "archiveInspectionPerformed": False,
            "networkOperationCount": 0,
            "fileWriteCount": 0,
        },
        "authority": {
            "decisionRecorded": True,
            "reviewExecutionAuthorized": False,
            "inMemoryArchiveInspectionAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "sourceModificationAuthorized": False,
            "packageManagerAuthorized": False,
            "compilerAuthorized": False,
            "sourceLoadAuthorized": False,
            "sourceExecutionAuthorized": False,
            "subprocessAuthorized": False,
            "socketAuthorized": False,
            "networkAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "gitWriteAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "closure": {
            "openFindingCount": 19,
            "patchRequiredFindingCount": 7,
            "unresolvedFindingCount": 12,
            "findingsClosedByDecision": 0,
            "graphFixedPointReached": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
        },
        "nonClaims": {
            "preparationIsReviewExecution": False,
            "sourceSetIsProductionReachabilityProof": False,
            "oneWaveIsFixedPointEvidence": False,
            "staticReviewIsCompileEvidence": False,
            "staticReviewIsRuntimeOrNetworkEvidence": False,
            "dependencyReviewSelectsCandidateOrLibrary": False,
            "executionPermitAuthenticationRequired": False,
            "permitIsLocalContentBoundWorkflowControl": True,
            "repositoryIdentityProofRequired": False,
            "productEndpointAuthenticationEvaluatedByThisDecision": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            "productEndpointAuthenticationUserInputRequiredForThisDecision": (
                False
            ),
            "userSuppliedCredentialOrTokenRequired": False,
            "userSuppliedSignatureOrKeyMaterialRequired": False,
        },
        "nextAction": (
            "prepare_separate_dependency_source_review_wave1_"
            "runner_tests_and_execution_permit"
        ),
    }


def validate_decision_document(
    decision: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    binding_value = decision.get("contentBinding")
    require(
        type(binding_value) is dict
        and set(binding_value)
        == {"algorithm", "canonicalization", "scope", "sha256"},
        "decision content binding schema",
    )
    require(
        type(binding_value["algorithm"]) is str
        and binding_value["algorithm"] == "sha256"
        and type(binding_value["canonicalization"]) is str
        and binding_value["canonicalization"]
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and type(binding_value["scope"]) is str
        and binding_value["scope"] == "decision_without_contentBinding"
        and type(binding_value["sha256"]) is str,
        "decision content binding fields",
    )
    actual = dict(decision)
    actual.pop("contentBinding")
    actual_canonical = canonical_json_bytes(actual)
    expected_canonical = canonical_json_bytes(expected)
    require(
        binding_value["sha256"] == sha256_bytes(actual_canonical),
        "decision content binding mismatch",
    )
    require(
        actual_canonical == expected_canonical,
        "decision exact typed contract mismatch",
    )


def validate_bound_file(
    root: Path,
    path: str,
    raw_sha256: str,
    maximum_bytes: int,
    *,
    owner_only: bool = False,
) -> bytes:
    raw = read_held(
        root,
        path,
        maximum_bytes=maximum_bytes,
        owner_only=owner_only,
    )
    require(sha256_bytes(raw) == raw_sha256, f"{path}: raw SHA-256 mismatch")
    return raw


def validate_state(root: Path = ROOT) -> dict[str, Any]:
    read_held(
        root,
        SELF_PATH,
        maximum_bytes=MAXIMUM_TOOL_BYTES,
    )
    read_held(
        root,
        TESTS_PATH,
        maximum_bytes=MAXIMUM_TOOL_BYTES,
    )
    bound_raw: dict[str, bytes] = {}
    for path, digest, maximum, owner_only in (
        (
            POST_VERIFIER_PATH,
            POST_VERIFIER_RAW_SHA256,
            MAXIMUM_TOOL_BYTES,
            False,
        ),
        (
            POST_VERIFIER_TESTS_PATH,
            POST_VERIFIER_TESTS_RAW_SHA256,
            MAXIMUM_TOOL_BYTES,
            False,
        ),
        (
            IMPLEMENTATION_DECISION_PATH,
            IMPLEMENTATION_DECISION_RAW_SHA256,
            MAXIMUM_JSON_BYTES,
            False,
        ),
        (
            IMPLEMENTATION_PLAN_PATH,
            IMPLEMENTATION_PLAN_RAW_SHA256,
            MAXIMUM_PLAN_BYTES,
            False,
        ),
        (
            SOURCE_DECISION_PATH,
            SOURCE_DECISION_RAW_SHA256,
            MAXIMUM_JSON_BYTES,
            False,
        ),
        (
            ACQUISITION_RECEIPT_PATH,
            ACQUISITION_RECEIPT_RAW_SHA256,
            MAXIMUM_JSON_BYTES,
            True,
        ),
        (
            ACQUISITION_MANIFEST_PATH,
            ACQUISITION_MANIFEST_RAW_SHA256,
            MAXIMUM_JSON_BYTES,
            True,
        ),
        (
            READBACK_RECEIPT_PATH,
            READBACK_RECEIPT_RAW_SHA256,
            MAXIMUM_JSON_BYTES,
            True,
        ),
        (
            READBACK_MANIFEST_PATH,
            READBACK_MANIFEST_RAW_SHA256,
            MAXIMUM_JSON_BYTES,
            True,
        ),
        (
            POST_DECISION_PATH,
            POST_DECISION_RAW_SHA256,
            MAXIMUM_JSON_BYTES,
            False,
        ),
        (
            ROOT_ARCHIVE_PATH,
            ROOT_ARCHIVE_RAW_SHA256,
            MAXIMUM_ROOT_ARCHIVE_BYTES,
            True,
        ),
    ):
        bound_raw[path] = validate_bound_file(
            root,
            path,
            digest,
            maximum,
            owner_only=owner_only,
        )

    source_decision = strict_json(
        bound_raw[SOURCE_DECISION_PATH],
        "source identity decision",
    )
    require(
        type(source_decision) is dict
        and source_decision.get("productionProfiles", {})
        .get("graphAlgorithm", {})
        .get("name")
        == "go1.24_mvs_profile_union_fixed_point_v1",
        "frozen graph algorithm mismatch",
    )
    receipt = strict_json(
        bound_raw[ACQUISITION_RECEIPT_PATH],
        "acquisition receipt",
    )
    require(
        type(receipt) is dict
        and type(receipt.get("sources")) is list
        and len(receipt["sources"]) == 19
        and [row.get("order") for row in receipt["sources"]]
        == list(range(1, 20))
        and len({row.get("tupleId") for row in receipt["sources"]}) == 19
        and receipt.get("acceptedTupleCount") == 19
        and receipt.get("acceptedArtifactCount") == 38
        and receipt.get("validatedZipResourceCount") == 19
        and receipt.get("validatedModResourceCount") == 19
        and receipt.get("aggregateRawByteSize") == 13178024
        and receipt.get("aggregateZipRawByteSize") == 13174173
        and receipt.get("aggregateModRawByteSize") == 3851
        and receipt.get("aggregateEntryCount") == 2907
        and receipt.get("aggregateUncompressedByteCount") == 31851201
        and receipt.get("orderedSourceSetSha256")
        == ORDERED_SOURCE_SET_SHA256,
        "acquisition receipt source set mismatch",
    )
    for row in receipt["sources"]:
        require(
            type(row) is dict
            and type(row.get("module")) is str
            and type(row.get("version")) is str
            and type(row.get("modOutputFileName")) is str
            and type(row.get("zipOutputFileName")) is str
            and type(row.get("modRawByteSize")) is int
            and type(row.get("zipRawByteSize")) is int
            and type(row.get("modRawSha256")) is str
            and len(row["modRawSha256"]) == 64
            and type(row.get("zipRawSha256")) is str
            and len(row["zipRawSha256"]) == 64
            and type(row.get("moduleZipH1")) is str
            and row["moduleZipH1"].startswith("h1:")
            and type(row.get("goModH1")) is str
            and row["goModH1"].startswith("h1:"),
            "acquisition receipt source row mismatch",
        )
    readback_receipt = strict_json(
        bound_raw[READBACK_RECEIPT_PATH],
        "readback receipt",
    )
    readback_manifest = strict_json(
        bound_raw[READBACK_MANIFEST_PATH],
        "readback manifest",
    )
    require(
        type(readback_receipt) is dict
        and readback_receipt.get("status")
        == "wave1_v3_independent_readback_complete_manifest_pending"
        and readback_receipt.get("retainedResourceCount") == 38
        and readback_receipt.get("retainedZipCount") == 19
        and readback_receipt.get("retainedModCount") == 19
        and readback_receipt.get("orderedSourceSetSha256")
        == ORDERED_SOURCE_SET_SHA256
        and type(readback_manifest) is dict
        and readback_manifest.get("status")
        == "wave1_v3_independent_readback_publication_complete"
        and readback_manifest.get("postReadbackRegularFileCount") == 43
        and readback_manifest.get("retainedResourceCount") == 38
        and readback_manifest.get("independentReadbackPassed") is True
        and readback_manifest.get("nextAction")
        == "prepare_separate_dependency_source_review_wave",
        "independent readback state mismatch",
    )

    decision_raw = read_held(
        root,
        DECISION_PATH,
        maximum_bytes=MAXIMUM_JSON_BYTES,
        owner_only=False,
    )
    decision = strict_json(decision_raw, "dependency source-review decision")
    require(type(decision) is dict, "dependency source-review decision: object")
    expected = expected_decision()
    validate_decision_document(decision, expected)
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-source-review-wave1-decision-preflight"
        ),
        "schemaVersion": "1.0",
        "decisionId": DECISION_ID,
        "status": (
            "dependency_source_review_wave1_decision_ready_"
            "execution_not_authorized"
        ),
        "validationPassed": True,
        "inputArchiveCount": 20,
        "dependencyTupleCount": 19,
        "retainedResourceCount": 38,
        "observedRegularFileCount": 43,
        "orderedSourceSetSha256": ORDERED_SOURCE_SET_SHA256,
        "graphFixedPointReached": False,
        "dependencyClosureComplete": False,
        "candidateSelected": False,
        "librarySelected": False,
        "reviewExecutionAuthorized": False,
        "networkOperationCount": 0,
        "fileWriteCount": 0,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": expected["nextAction"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = validate_state(args.root)
    except (
        DecisionError,
        OSError,
    ) as error:
        result = {
            "documentType": (
                "aetherlink.g2-pion-dependency-source-review-wave1-"
                "decision-preflight"
            ),
            "schemaVersion": "1.0",
            "status": "failed_closed",
            "validationPassed": False,
            "error": str(error),
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        print(canonical_json_bytes(result).decode("utf-8"), end="")
        return 1
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
