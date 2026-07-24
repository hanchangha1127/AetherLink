#!/usr/bin/env python3
"""Validate the G2 Pion rung-three offline-review execution permit.

This checker has no archive capability. It reads only the closed set of
repository evidence and implementation files declared below, follows no
symlinks, writes nothing, and never imports or executes the review runner.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG2 = f"{BASE}/rung-two"
RUNG3 = f"{BASE}/rung-three"

PROFILE_PATH = f"{BASE}/restricted-fork-profile.json"
ARCHIVE_RECEIPT_PATH = f"{RUNG2}/source-acquisition-receipt-v1.json"
RUNG2_PROGRESS_PATH = f"{RUNG2}/source-acquisition-progress-v2.json"
RUNG2_MANIFEST_V3_PATH = f"{RUNG2}/evidence-manifest-v3.json"
RUNG2_MANIFEST_V5_PATH = f"{RUNG2}/evidence-manifest-v5.json"
PREPARATION_DECISION_PATH = f"{RUNG3}/offline-source-review-decision-v1.json"
PREPARATION_PROGRESS_PATH = f"{RUNG3}/offline-source-review-progress-v1.json"
PREPARATION_POLICY_PATH = f"{RUNG3}/preparation-sandbox-policy-v1.json"
PREPARATION_MANIFEST_V1_PATH = f"{RUNG3}/evidence-manifest-v1.json"
PREPARATION_SUPERSESSION_V1_PATH = f"{RUNG3}/canonical-document-supersession-v1.json"
PREPARATION_MANIFEST_V2_PATH = f"{RUNG3}/evidence-manifest-v2.json"

POLICY_PATH = f"{RUNG3}/review-execution-policy-v1.json"
PERMIT_PATH = f"{RUNG3}/offline-source-review-execution-permit-v1.json"
CORE_MANIFEST_PATH = f"{RUNG3}/execution-permit-core-manifest-v3.json"
CHECKER_MANIFEST_PATH = f"{RUNG3}/execution-permit-checker-manifest-v4.json"
RUNNER_PATH = "script/run_p2p_nat_g2_pion_rung3_offline_review_once.py"
RUNNER_TEST_PATH = "script/test_run_p2p_nat_g2_pion_rung3_offline_review_once.py"
PURE_MODULE_PATH = "script/p2p_nat_g2_pion_offline_zip.py"
PURE_MODULE_TEST_PATH = "script/test_p2p_nat_g2_pion_offline_zip.py"
CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_permit.py"
CHECKER_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_execution_permit.py"

ARCHIVE_METADATA_JSON_POINTER = "/archive"
ARCHIVE_PATH_JSON_POINTER = "/archive/path"

EXPECTED_STATUS = "rung3_bounded_static_inventory_execution_authorized_not_consumed"
EXPECTED_RESULT = "single_use_bounded_static_candidate_location_inventory_authorized_not_executed"
EXPECTED_NEXT_ACTION = "execute_bound_rung3_static_candidate_location_inventory_once"
EXPECTED_DATE = "2026-07-23"
EXPECTED_EVIDENCE_BASIS = (
    "static_contract_and_synthetic_tests_not_os_sandbox_attestation"
)
EXPECTED_SCOPE = (
    "single_use_offline_archive_read_and_bounded_static_candidate_location_"
    "inventory_only_not_full_rung3_semantic_review"
)
EXPECTED_REVIEW_SCOPE = (
    "bounded_static_candidate_location_inventory_not_full_rung3_semantic_review"
)

# Patch these only after the runner/module suite and JSON artifacts are final.
# CORE_MANIFEST does not contain this checker, so pinning it here is acyclic.
EXPECTED_POLICY_RAW_SHA256 = "bd96633f41e2a11164746c31645bc6c6d37737da6664151c3dd9072d07f2dfba"
EXPECTED_POLICY_SEMANTIC_SHA256 = (
    "ad24dfd8a45aa45f7691eb6a5df21caaa4af183bc280c7f9e1f76cf1cc1ea71f"
)
EXPECTED_PERMIT_RAW_SHA256 = "13d1760477a07c32424f101fad98e85584c6a4335fb64e65992e099c750a756b"
EXPECTED_PERMIT_SEMANTIC_SHA256 = "c28e798a1e953ffa291c9f9d7397ca377b3bc780b8a137325b0363951a083aac"
EXPECTED_RUNNER_RAW_SHA256 = "592e5dfdbd6a2cb8cb373b7186d8c5c573501d0b026c522c94beccf5620ee0c5"
EXPECTED_RUNNER_TEST_RAW_SHA256 = "1796359bdbbccfe36b8ad6e8904836207b981486e99a477f5707d01772184d9e"
EXPECTED_PURE_MODULE_RAW_SHA256 = "9daef717b30337191ee9902110bdf4455babacb261acab9124d37de72fa8988b"
EXPECTED_PURE_MODULE_TEST_RAW_SHA256 = "49b4b99ec194186848fc127c10caa140e96260e7530830acc7781bfcb6a8a035"
EXPECTED_CORE_MANIFEST_RAW_SHA256 = "5da37c6101ea9eee4f12074c76cfdd97bb74f4a6e30dad2edddc1d788e415e09"
EXPECTED_CORE_MANIFEST_SEMANTIC_SHA256 = (
    "179eaf84db4b6500d41d560474d802e3930dbfe671163ef307062aa94bb3ee8f"
)
EXPECTED_CORE_MANIFEST_COLLECTION_SHA256 = (
    "2073107b2cd994097270a28907ee8bbb562e8647ecba992f5e13b8c9b7adb2c0"
)
EXPECTED_CHECKER_TEST_RAW_SHA256 = "f9462eaba9dc5afef92f15c54158db6ef0ee6e6b24a35ded9e1789004ec055e7"

PLACEHOLDER = re.compile(r"^__PENDING_[A-Z0-9_]+__$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_TRACKED_FILE_BYTES = 8 * 1024 * 1024
AMBIGUOUS_COMPILER_KEYS = frozenset(
    {"compilerInvocationAllowed", "compileAuthorized"}
)

EXPECTED_RESOURCE_LIMITS = {
    "maximumArchiveBytes": 524288,
    "maximumCentralDirectoryBytes": 4194304,
    "maximumComponentBytes": 255,
    "maximumCompressionRatio": 200,
    "maximumEntries": 4096,
    "maximumJsonReportBytes": 2097152,
    "maximumPathBytes": 1024,
    "maximumPathComponents": 32,
    "maximumRecordedHitsPerPatchUnit": 512,
    "maximumSingleFileBytes": 4194304,
    "maximumTextFileBytes": 2097152,
    "maximumTotalUncompressedBytes": 67108864,
}
EXPECTED_REJECTION_RULES = [
    "exact_raw_size_or_sha256_mismatch",
    "prefix_path_or_entry_count_drift",
    "path_traversal_absolute_backslash_control_or_non_nfc_name",
    "exact_name_nfc_casefold_or_file_directory_collision",
    "symlink_hardlink_special_nonregular_or_executable_entry",
    "encrypted_zip64_multidisk_comment_trailing_hidden_or_duplicate_data",
    "local_central_header_flag_method_name_crc_or_size_mismatch",
    "single_file_total_uncompressed_or_compression_ratio_limit_exceeded",
]
EXPECTED_CAPABILITY_BOUNDARY = {
    "boundedStaticCandidateInventoryExecutionAuthorized": True,
    "archiveOpenAllowed": True,
    "archiveReadAllowed": True,
    "archiveEntryEnumerationAllowed": True,
    "deterministicJsonReportPublicationAllowed": True,
    "archiveExtractionAllowed": False,
    "sourceFileMaterializationAllowed": False,
    "sourceExecutionAllowed": False,
    "sourcePatchWriteAllowed": False,
    "dependencyInstallationAllowed": False,
    "packageManagerAllowed": False,
    "reviewedSourceCompilerInvocationAllowed": False,
    "reviewedSourceCodeLoadingAllowed": False,
    "verifiedPinnedReviewToolModuleLoadingAllowed": True,
    "verifiedAuxiliaryToolModulePythonCompileAllowed": True,
    "childSubprocessAllowed": False,
    "shellAllowed": False,
    "dnsAllowed": False,
    "socketCreationAllowed": False,
    "networkIoAllowed": False,
    "gitOperationAllowed": False,
    "deviceOperationAllowed": False,
    "productionDeploymentAllowed": False,
}
EXPECTED_PERSONAL_BOUNDARY = {
    "technicalSafetyGatesRemainRequired": True,
    "repositoryOwnerAuthenticationIsNotATechnicalGate": True,
    "repositoryOwnerAuthenticationRequired": False,
    "externalIdentityProofRequired": False,
    "userActionRequired": False,
    "productEndpointAuthenticationRequired": True,
}
EXPECTED_OUTPUT_CONTRACT = {
    "directory": "build/offline-source/pion-ice-v4.3.0/review-v1",
    "claimFileName": ".g2-pion-ice-v4.3.0-rung3-offline-review-v1.claim",
    "resultFileName": "offline-source-review-result-v1.json",
    "manifestFileName": "offline-source-review-manifest-v1.json",
    "sourceMaterializationAllowed": False,
    "sourceBodyCopiedToReport": False,
    "deterministicBoundedJsonOnly": True,
    "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
    "directoryMode": "0700",
    "fileMode": "0600",
    "maximumBytesPerJsonFile": 2097152,
    "absolutePathsAllowedInOutput": False,
    "secretsAllowedInOutput": False,
    "atomicNoReplacePublicationRequired": True,
    "ownerOnlyStorageRequired": True,
    "resultIsCompletionMarker": False,
    "manifestIsSoleCompletionMarker": True,
    "manifestRequiresResultHashMatch": True,
    "partialPublicationIsIncomplete": True,
}
EXPECTED_INTERPRETER_ISOLATION_CONTRACT = {
    "preflightCommand": [
        "python3", "-I", "-B", RUNNER_PATH, "--check-permit",
    ],
    "executionCommand": [
        "python3", "-I", "-B", RUNNER_PATH, "--execute-permit",
    ],
    "requiredSysFlags": {
        "isolated": 1,
        "dont_write_bytecode": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "optimize": 0,
    },
    "ambientPythonPathAllowed": False,
    "bytecodeReadOrWriteAllowed": False,
    "runnerEarlyGuardRequired": True,
}
EXPECTED_PATCH_UNITS = [
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
]
EXPECTED_VERIFICATION_UNITS = [
    {"id": "g2-r3-egress-path-coverage", "status": "required_check_not_executed"},
    {"id": "g2-r3-ingress-path-coverage", "status": "required_check_not_executed"},
    {"id": "g2-r3-address-and-resolution-adversarial", "status": "required_check_not_executed"},
    {"id": "g2-r3-turn-tls-service-identity", "status": "required_check_not_executed"},
    {"id": "g2-r3-secure-session-promotion", "status": "required_check_not_executed"},
    {"id": "g2-r3-resource-and-event-bounds", "status": "required_check_not_executed"},
    {"id": "g2-r3-secret-free-diagnostics", "status": "required_check_not_executed"},
    {"id": "g2-r3-deadline-shutdown", "status": "required_check_not_executed"},
]
VERIFICATION_CROSSWALK = [
    {"verificationId": "g2-r3-egress-path-coverage", "patchUnitIndexes": [0, 4, 5, 6]},
    {"verificationId": "g2-r3-ingress-path-coverage", "patchUnitIndexes": [0, 2, 4, 6]},
    {"verificationId": "g2-r3-address-and-resolution-adversarial", "patchUnitIndexes": [4, 5]},
    {"verificationId": "g2-r3-turn-tls-service-identity", "patchUnitIndexes": [1, 5]},
    {"verificationId": "g2-r3-secure-session-promotion", "patchUnitIndexes": [6]},
    {"verificationId": "g2-r3-resource-and-event-bounds", "patchUnitIndexes": [2, 3]},
    {"verificationId": "g2-r3-secret-free-diagnostics", "patchUnitIndexes": [1]},
    {"verificationId": "g2-r3-deadline-shutdown", "patchUnitIndexes": [3]},
]
EXPECTED_REVIEW_TOPICS = [
    "regular_file_inventory_with_size_and_sha256",
    "go_lexical_and_ast_like_candidate_location_inventory_without_execution",
    "go_mod_and_go_sum_dependency_metadata_inventory",
    "license_and_notice_inventory_without_legal_conclusion",
    "egress_path_candidate_mapping",
    "ingress_path_candidate_mapping",
    "secret_free_logging_candidate_mapping",
    "concurrency_resource_and_event_bound_candidate_mapping",
    "deadline_close_and_revocation_candidate_mapping",
    "seven_patch_unit_candidate_location_mapping",
]
EXPECTED_REVIEW_PLAN = {
    "scope": EXPECTED_REVIEW_SCOPE,
    "coverageMeaning": "candidate_locations_only_not_proof_of_coverage_or_closure",
    "goScanMeaning": "lexical_and_ast_like_inventory_not_type_control_or_data_flow_proof",
    "licenseMeaning": "inventory_only_not_legal_conclusion",
    "semanticReviewMeaning": "not_performed_by_this_permit",
    "patchUnits": EXPECTED_PATCH_UNITS,
    "verificationUnits": EXPECTED_VERIFICATION_UNITS,
    "verificationCrosswalk": VERIFICATION_CROSSWALK,
    "reviewTopics": EXPECTED_REVIEW_TOPICS,
}

PREDECESSOR_ANCHORS: dict[str, dict[str, str]] = {
    "restrictedForkProfile": {
        "path": PROFILE_PATH,
        "rawSha256": "10e9436ae9b8f24c4447d12f8087b4f121810841ae33526e08fcc3d862d60a0f",
        "semanticSha256": "9c929d186eedb10cc890d5540597724d6df1d719f174ed1965c79e4d50324be6",
    },
    "rungTwoReceipt": {
        "path": ARCHIVE_RECEIPT_PATH,
        "rawSha256": "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6",
        "semanticSha256": "304a0b246050e446da9d25d9778c6cc05153c10d353d4b01963e2c566ab37880",
    },
    "rungTwoProgressV2": {
        "path": RUNG2_PROGRESS_PATH,
        "rawSha256": "df1ad52bc6fff294b9bb54fd94a8eaacd76d9ff2b179be4a6752a867d229196f",
        "semanticSha256": "d984cdbae6be447bf04e8f643687c8b2fd23e670c5826538b1b3f352ef470309",
    },
    "rungTwoManifestV3": {
        "path": RUNG2_MANIFEST_V3_PATH,
        "rawSha256": "8ed1a2667153f77270531d7c373f5f61ed9eb9080bceab7c804c9b686259537e",
        "semanticSha256": "61bfeb7f12bdbea38c73d7a1581f5ceada31bfc9b0ef64ee25e97f8c5c8d2221",
        "collectionSha256": "0e5e41990ed8b46dd40dba9808f29f40e007142ed0ae77408d4d8afa6f4142a0",
    },
    "rungTwoManifestV5": {
        "path": RUNG2_MANIFEST_V5_PATH,
        "rawSha256": "203e88cf73ad358fd6c73d8bb8d988efa966ffa67573d6e7dda9c03a2fe01f89",
        "semanticSha256": "fd738ae8de9909adf6d9dd915d4d861998c06bde97b10cb9e87c4cc9adea9d80",
        "collectionSha256": "adb1fbce766b0750e186285024156abea290d80763eea142420192aa8261d0a8",
    },
    "preparationDecision": {
        "path": PREPARATION_DECISION_PATH,
        "rawSha256": "8e2c60b977ee139644c372581e066bfa720d4c5bf1c1809d34b142917abdfa16",
        "semanticSha256": "fe816c45fb080a619bfad426406618952adbc2fd909b6d02f90e4de172b4d5c5",
    },
    "preparationProgress": {
        "path": PREPARATION_PROGRESS_PATH,
        "rawSha256": "651f8145ae91f7861b21565394db28b1608657c9bffd9a3e921aeafbff1fbabf",
        "semanticSha256": "e29a3745ec2a43bfdce0959d5b96baee679af2fb902dc6989436830cf59bd515",
    },
    "preparationPolicy": {
        "path": PREPARATION_POLICY_PATH,
        "rawSha256": "c615da9fb80d7af0162077503b55663cf428aaee434cef61a67807c234ea3558",
        "semanticSha256": "bf5de358234c03a5bfc96b66d4fd8b5f0464328f4733820899ce0f93219be64a",
    },
    "preparationManifestV1": {
        "path": PREPARATION_MANIFEST_V1_PATH,
        "rawSha256": "6bde9587aa11c7087cc955f2e6e8829477b805a596142cc353417cffee272dee",
        "semanticSha256": "7e43f2f265cfcae12cb5f4cd42e4cce256d275d83086af184264c64c9a46e636",
        "collectionSha256": "a999e692f02151010e2a3f194da4eb158282e4c3a85d01dc0f6188b7a52c0e05",
    },
    "preparationSupersessionV1": {
        "path": PREPARATION_SUPERSESSION_V1_PATH,
        "rawSha256": "ec57f0712309ef459b19e8155ce4450bb4b2d81c32b04e4a97e242f6824735bd",
        "semanticSha256": "fb9204ae5800964de278988d6969c234762b2f750efe17014f4d53631ef946f9",
    },
    "preparationManifestV2": {
        "path": PREPARATION_MANIFEST_V2_PATH,
        "rawSha256": "4098a043ff2ef5b897430c9207e62d475ebcfd3edfc8c9e1c95857f8c73a3525",
        "semanticSha256": "d4d736f85a19070aa4b3e6ca49a8ee0cb03096e75174caf865af2659ed88386b",
        "collectionSha256": "49b517e8f35b4db4537de193e0b68b3d6aa9dde173aa080edd8adb122af6567a",
    },
}

TRACKED_READ_ALLOWLIST = frozenset(
    {
        *(item["path"] for item in PREDECESSOR_ANCHORS.values()),
        POLICY_PATH,
        PERMIT_PATH,
        CORE_MANIFEST_PATH,
        CHECKER_MANIFEST_PATH,
        RUNNER_PATH,
        RUNNER_TEST_PATH,
        PURE_MODULE_PATH,
        PURE_MODULE_TEST_PATH,
        CHECKER_PATH,
        CHECKER_TEST_PATH,
    }
)


class CheckError(ValueError):
    """The permit or its closed evidence set failed validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict, f"{label} must be object")
    require(set(value) == expected, f"{label} exact keys mismatch")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def semantic_sha256(data: bytes, parsed: Any) -> str:
    payload = json.dumps(
        parsed,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def strict_json(data: bytes, label: str) -> Any:
    require(data.endswith(b"\n"), f"{label}: final LF required")
    require(b"\r" not in data, f"{label}: CR forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise CheckError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise CheckError(f"{label}: non-finite JSON number {value}")

    try:
        parsed = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid JSON: {error}") from error
    reject_nonfinite(parsed, label)
    return parsed


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite float")
    elif type(value) is list:
        for item in value:
            reject_nonfinite(item, label)
    elif type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(item, label)


def reject_ambiguous_compiler_semantics(value: Any, label: str) -> None:
    if type(value) is list:
        for index, item in enumerate(value):
            reject_ambiguous_compiler_semantics(item, f"{label}[{index}]")
    elif type(value) is dict:
        for key, item in value.items():
            require(
                key not in AMBIGUOUS_COMPILER_KEYS,
                f"{label}: ambiguous compiler key forbidden: {key}",
            )
            if key == "forbiddenCapabilities" and type(item) is list:
                require(
                    "compiler" not in item,
                    f"{label}: ambiguous compiler capability forbidden",
                )
            reject_ambiguous_compiler_semantics(item, f"{label}.{key}")


def validate_relative_path(path: str) -> tuple[str, ...]:
    require(type(path) is str, "path must be string")
    require(path in TRACKED_READ_ALLOWLIST, f"unlisted read forbidden: {path}")
    require("\\" not in path and "\x00" not in path, f"unsafe path: {path}")
    pure = PurePosixPath(path)
    require(not pure.is_absolute(), f"absolute path forbidden: {path}")
    require(
        pure.parts and all(part not in ("", ".", "..") for part in pure.parts),
        f"unsafe path: {path}",
    )
    require(pure.parts[0] != "build", f"build read forbidden: {path}")
    require(
        not path.lower().endswith((".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z")),
        f"archive read forbidden: {path}",
    )
    return pure.parts


class SafeTrackedReader:
    """Component-wise no-follow reader for the closed tracked evidence set."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.cache: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        parts = validate_relative_path(path)
        if path in self.cache:
            return self.cache[path]
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
        file_flags = os.O_RDONLY | nofollow
        root_fd = os.open(os.fspath(self.root), directory_flags)
        parent_fd = root_fd
        opened_dirs: list[int] = []
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, directory_flags, dir_fd=parent_fd)
                opened_dirs.append(next_fd)
                parent_fd = next_fd
            file_fd = os.open(parts[-1], file_flags, dir_fd=parent_fd)
            try:
                before = os.fstat(file_fd)
                require(stat.S_ISREG(before.st_mode), f"{path}: regular file required")
                require(before.st_nlink == 1, f"{path}: single link required")
                require(
                    0 <= before.st_size <= MAX_TRACKED_FILE_BYTES,
                    f"{path}: size out of bounds",
                )
                remaining = before.st_size
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(file_fd, min(65536, remaining))
                    require(bool(chunk), f"{path}: unexpected EOF")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(file_fd, 1) == b"", f"{path}: grew during read")
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
                    f"{path}: changed during read",
                )
                data = b"".join(chunks)
            finally:
                os.close(file_fd)
        except OSError as error:
            raise CheckError(f"{path}: safe read failed: {error}") from error
        finally:
            for fd in reversed(opened_dirs):
                os.close(fd)
            os.close(root_fd)
        self.cache[path] = data
        return data

    def json(self, path: str) -> Any:
        return strict_json(self.read(path), path)


def unresolved_placeholders(value: Any, label: str = "$") -> list[str]:
    found: list[str] = []
    if type(value) is str and PLACEHOLDER.fullmatch(value):
        found.append(label)
    elif type(value) is list:
        for index, item in enumerate(value):
            found.extend(unresolved_placeholders(item, f"{label}[{index}]"))
    elif type(value) is dict:
        for key, item in value.items():
            found.extend(unresolved_placeholders(item, f"{label}.{key}"))
    return found


def require_digest(value: Any, label: str) -> str:
    require(type(value) is str and HEX_SHA256.fullmatch(value) is not None, f"{label}: SHA-256 required")
    return value


def require_resolved_digest_constants() -> None:
    values = {
        "EXPECTED_POLICY_RAW_SHA256": EXPECTED_POLICY_RAW_SHA256,
        "EXPECTED_POLICY_SEMANTIC_SHA256": EXPECTED_POLICY_SEMANTIC_SHA256,
        "EXPECTED_PERMIT_RAW_SHA256": EXPECTED_PERMIT_RAW_SHA256,
        "EXPECTED_PERMIT_SEMANTIC_SHA256": EXPECTED_PERMIT_SEMANTIC_SHA256,
        "EXPECTED_RUNNER_RAW_SHA256": EXPECTED_RUNNER_RAW_SHA256,
        "EXPECTED_RUNNER_TEST_RAW_SHA256": EXPECTED_RUNNER_TEST_RAW_SHA256,
        "EXPECTED_PURE_MODULE_RAW_SHA256": EXPECTED_PURE_MODULE_RAW_SHA256,
        "EXPECTED_PURE_MODULE_TEST_RAW_SHA256": EXPECTED_PURE_MODULE_TEST_RAW_SHA256,
        "EXPECTED_CORE_MANIFEST_RAW_SHA256": EXPECTED_CORE_MANIFEST_RAW_SHA256,
        "EXPECTED_CORE_MANIFEST_SEMANTIC_SHA256": EXPECTED_CORE_MANIFEST_SEMANTIC_SHA256,
        "EXPECTED_CORE_MANIFEST_COLLECTION_SHA256": EXPECTED_CORE_MANIFEST_COLLECTION_SHA256,
        "EXPECTED_CHECKER_TEST_RAW_SHA256": EXPECTED_CHECKER_TEST_RAW_SHA256,
    }
    unresolved = [name for name, value in values.items() if not HEX_SHA256.fullmatch(value)]
    require(not unresolved, f"unresolved checker digest constants: {', '.join(unresolved)}")


def verify_json_binding(
    reader: SafeTrackedReader,
    binding: Any,
    expected: Mapping[str, str],
    label: str,
) -> None:
    require_exact_keys(binding, set(expected), label)
    require(binding == expected, f"{label}: pinned binding mismatch")
    raw = reader.read(expected["path"])
    parsed = strict_json(raw, expected["path"])
    require(sha256_bytes(raw) == expected["rawSha256"], f"{label}: raw digest mismatch")
    require(
        semantic_sha256(raw, parsed) == expected["semanticSha256"],
        f"{label}: semantic digest mismatch",
    )
    if "collectionSha256" in expected:
        require(
            type(parsed) is dict
            and parsed.get("collectionSha256") == expected["collectionSha256"],
            f"{label}: collection digest mismatch",
        )


def verify_raw_binding(
    reader: SafeTrackedReader,
    binding: Any,
    expected_path: str,
    expected_digest: str,
    label: str,
) -> None:
    require_exact_keys(binding, {"path", "rawSha256"}, label)
    require(binding["path"] == expected_path, f"{label}: path mismatch")
    require_digest(binding["rawSha256"], f"{label}.rawSha256")
    require(binding["rawSha256"] == expected_digest, f"{label}: pinned digest mismatch")
    require(sha256_bytes(reader.read(expected_path)) == expected_digest, f"{label}: actual digest mismatch")


def collection_sha256(artifacts: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    for artifact in artifacts:
        rows.append(
            f"{artifact['evidenceId']}\t{artifact['sha256']}\t{artifact['path']}\n"
        )
    return sha256_bytes("".join(rows).encode("utf-8"))


def validate_policy(document: Any) -> None:
    reject_ambiguous_compiler_semantics(document, "policy")
    require_exact_keys(
        document,
        {
            "documentType", "schemaVersion", "policyId", "recordedDate", "status",
            "evidenceBasis", "scope", "reviewPlan", "runtimePaths", "cliContract",
            "interpreterIsolationContract",
            "archiveOpenContract", "consumptionContract", "outputContract",
            "forbiddenCapabilities", "archiveRejectionRules", "resourceLimits",
            "capabilityBoundary", "personalProjectBoundary",
        },
        "policy",
    )
    expected_scalars = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-execution-policy",
        "schemaVersion": "1.0",
        "policyId": "g2-pion-ice-v4.3.0-offline-source-review-execution-policy-v1",
        "recordedDate": EXPECTED_DATE,
        "status": "bounded_static_candidate_inventory_policy_recorded_execution_not_started",
        "evidenceBasis": EXPECTED_EVIDENCE_BASIS,
        "scope": EXPECTED_SCOPE,
    }
    for key, expected in expected_scalars.items():
        require(document[key] == expected, f"policy.{key} mismatch")
    require(
        document["runtimePaths"]
        == {
            "runner": RUNNER_PATH,
            "runnerTest": RUNNER_TEST_PATH,
            "pureModule": PURE_MODULE_PATH,
            "pureModuleTest": PURE_MODULE_TEST_PATH,
            "permitChecker": CHECKER_PATH,
            "permitCheckerTest": CHECKER_TEST_PATH,
        },
        "policy.runtimePaths mismatch",
    )
    require(
        document["cliContract"]
        == {
            "allowedModes": ["--check-permit", "--execute-permit"],
            "defaultMode": "--check-permit",
            "pathArgumentsAllowed": False,
            "outputArgumentsAllowed": False,
            "environmentOverridesAllowed": False,
        },
        "policy.cliContract mismatch",
    )
    require(
        document["interpreterIsolationContract"]
        == EXPECTED_INTERPRETER_ISOLATION_CONTRACT,
        "policy.interpreterIsolationContract mismatch",
    )
    require(document["reviewPlan"] == EXPECTED_REVIEW_PLAN, "policy.reviewPlan mismatch")
    require(
        document["archiveOpenContract"]
        == {
            "locatorSource": "pinned_receipt_json_pointer_only",
            "componentWiseNoFollowRequired": True,
            "regularFileRequired": True,
            "singleLinkRequired": True,
            "ownerUidMustMatchCurrentUser": True,
            "exactMode": "0600",
            "singleFileDescriptorHeldThroughIdentityAndReview": True,
            "beforeAfterFstatIdentityMustMatch": True,
            "pathReopenAllowed": False,
        },
        "policy.archiveOpenContract mismatch",
    )
    require(
        document["consumptionContract"]
        == {
            "maximumExecutionAttempts": 1,
            "automaticRetryAllowed": False,
            "claimCreatedBeforeArchiveOpen": True,
            "claimCreateFlags": "O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW",
            "claimMode": "0600",
            "claimRetainedOnSuccessOrFailure": True,
            "failureRequiresNewVersionedPermit": True,
        },
        "policy.consumptionContract mismatch",
    )
    require(
        document["forbiddenCapabilities"]
        == [
            "archive_extraction", "source_file_materialization",
            "source_execution", "source_patch_write", "dependency_installation",
            "package_manager", "reviewed_source_compiler",
            "reviewed_source_dynamic_code_loading",
            "child_subprocess", "shell", "dns", "socket", "network", "git",
            "device", "deployment",
        ],
        "policy.forbiddenCapabilities mismatch",
    )
    require(document["archiveRejectionRules"] == EXPECTED_REJECTION_RULES, "policy rejection rules mismatch")
    require(document["resourceLimits"] == EXPECTED_RESOURCE_LIMITS, "policy limits mismatch")
    require(document["capabilityBoundary"] == EXPECTED_CAPABILITY_BOUNDARY, "policy capability boundary mismatch")
    require(document["personalProjectBoundary"] == EXPECTED_PERSONAL_BOUNDARY, "policy personal boundary mismatch")
    output = document["outputContract"]
    require_exact_keys(
        output,
        {
            "directory", "claimFileName", "resultFileName", "manifestFileName",
            "sourceMaterializationAllowed", "sourceBodyCopiedToReport",
            "deterministicBoundedJsonOnly", "canonicalization",
            "temporaryDirectoryMode", "finalDirectoryMode", "temporaryFileMode",
            "finalFileMode", "maximumBytesPerJsonFile",
            "absolutePathsAllowedInOutput", "secretsAllowedInOutput",
            "atomicNoReplacePublicationRequired", "fileAndDirectoryFsyncRequired",
            "resultIsCompletionMarker", "manifestIsSoleCompletionMarker",
            "manifestRequiresResultHashMatch", "partialPublicationIsIncomplete",
        },
        "policy.outputContract",
    )
    require(output["directory"] == EXPECTED_OUTPUT_CONTRACT["directory"], "policy output directory mismatch")
    require(output["claimFileName"] == EXPECTED_OUTPUT_CONTRACT["claimFileName"], "policy claim mismatch")
    require(output["resultFileName"] == EXPECTED_OUTPUT_CONTRACT["resultFileName"], "policy result mismatch")
    require(output["manifestFileName"] == EXPECTED_OUTPUT_CONTRACT["manifestFileName"], "policy manifest mismatch")
    require(output["maximumBytesPerJsonFile"] == 2097152, "policy output size mismatch")
    require(output["finalDirectoryMode"] == "0700" and output["finalFileMode"] == "0600", "policy output modes mismatch")
    for key in ("sourceMaterializationAllowed", "sourceBodyCopiedToReport", "absolutePathsAllowedInOutput", "secretsAllowedInOutput"):
        require(output[key] is False, f"policy.outputContract.{key} must be false")
    for key in ("deterministicBoundedJsonOnly", "atomicNoReplacePublicationRequired", "fileAndDirectoryFsyncRequired"):
        require(output[key] is True, f"policy.outputContract.{key} must be true")
    require(
        output
        == {
            "directory": EXPECTED_OUTPUT_CONTRACT["directory"],
            "claimFileName": EXPECTED_OUTPUT_CONTRACT["claimFileName"],
            "resultFileName": EXPECTED_OUTPUT_CONTRACT["resultFileName"],
            "manifestFileName": EXPECTED_OUTPUT_CONTRACT["manifestFileName"],
            "sourceMaterializationAllowed": False,
            "sourceBodyCopiedToReport": False,
            "deterministicBoundedJsonOnly": True,
            "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "temporaryDirectoryMode": "0700",
            "finalDirectoryMode": "0700",
            "temporaryFileMode": "0600",
            "finalFileMode": "0600",
            "maximumBytesPerJsonFile": 2097152,
            "absolutePathsAllowedInOutput": False,
            "secretsAllowedInOutput": False,
            "atomicNoReplacePublicationRequired": True,
            "fileAndDirectoryFsyncRequired": True,
            "resultIsCompletionMarker": False,
            "manifestIsSoleCompletionMarker": True,
            "manifestRequiresResultHashMatch": True,
            "partialPublicationIsIncomplete": True,
        },
        "policy.outputContract mismatch",
    )


def validate_archive_identity(binding: Any) -> None:
    expected = {
        "receiptPath": ARCHIVE_RECEIPT_PATH,
        "receiptRawSha256": PREDECESSOR_ANCHORS["rungTwoReceipt"]["rawSha256"],
        "archiveMetadataJsonPointer": ARCHIVE_METADATA_JSON_POINTER,
        "archivePathJsonPointer": ARCHIVE_PATH_JSON_POINTER,
        "archivePathCopiedIntoPermit": False,
        "archiveEvidenceId": "G2R2E009",
        "expectedBytes": 293023,
        "rawSha256": "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
        "entryCount": 129,
        "fileCount": 129,
        "totalUncompressedBytes": 1131286,
        "modulePath": "github.com/pion/ice/v4",
        "version": "v4.3.0",
        "commitSha1": "1e8716372f2bb52e45bf2a7172e4fb1004251c46",
        "treeSha1": "df59c87a634cfea261582cd9932554663112a975",
        "moduleH1": "h1:X8l4s9zV2HeTKX33nulWAFXAEo5KhIVzOsY62/3t/LM=",
        "goModH1": "h1:obAyD+J+Hzs7QA7Y8YXHp5uIn6gb7z87pKedXZkrcFU=",
    }
    require_exact_keys(binding, set(expected), "permit.archiveIdentityBinding")
    require(binding == expected, "permit archive identity mismatch")


def validate_permit(document: Any, raw: bytes, reader: SafeTrackedReader) -> None:
    reject_ambiguous_compiler_semantics(document, "permit")
    require_exact_keys(
        document,
        {
            "documentType", "schemaVersion", "permitId", "recordedDate", "status",
            "result", "nextAction", "scope", "contentBinding", "authorityBindings",
            "archiveIdentityBinding", "runnerBinding", "policyBinding",
            "singleUseConsumption", "interpreterIsolationContract",
            "capabilityBoundary", "reviewPlan",
            "archiveRejectionRules", "resourceLimits", "outputContract",
            "personalProjectBoundary", "nonClaims",
        },
        "permit",
    )
    expected_identity = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-execution-permit",
        "schemaVersion": "1.0",
        "permitId": "g2-pion-ice-v4.3.0-offline-source-review-execution-permit-v1",
        "recordedDate": EXPECTED_DATE,
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "scope": EXPECTED_SCOPE,
    }
    for key, expected in expected_identity.items():
        require(document[key] == expected, f"permit.{key} mismatch")
    require(b".zip" not in raw.lower(), "permit must not copy archive path")
    content = require_exact_keys(
        document["contentBinding"],
        {"algorithm", "canonicalization", "scope", "sha256"},
        "permit.contentBinding",
    )
    require(
        content["algorithm"] == "sha256"
        and content["canonicalization"] == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and content["scope"] == "permit_without_contentBinding",
        "permit content binding contract mismatch",
    )
    core = {key: value for key, value in document.items() if key != "contentBinding"}
    require(content["sha256"] == sha256_bytes(canonical_json_bytes(core)), "permit content digest mismatch")
    authority = require_exact_keys(
        document["authorityBindings"], set(PREDECESSOR_ANCHORS), "permit.authorityBindings"
    )
    for label, expected in PREDECESSOR_ANCHORS.items():
        verify_json_binding(reader, authority[label], expected, f"permit.authorityBindings.{label}")
    validate_archive_identity(document["archiveIdentityBinding"])
    runner = require_exact_keys(
        document["runnerBinding"],
        {"runner", "runnerTest", "pureModule", "pureModuleTest"},
        "permit.runnerBinding",
    )
    verify_raw_binding(reader, runner["runner"], RUNNER_PATH, EXPECTED_RUNNER_RAW_SHA256, "permit.runner")
    verify_raw_binding(reader, runner["runnerTest"], RUNNER_TEST_PATH, EXPECTED_RUNNER_TEST_RAW_SHA256, "permit.runnerTest")
    verify_raw_binding(reader, runner["pureModule"], PURE_MODULE_PATH, EXPECTED_PURE_MODULE_RAW_SHA256, "permit.pureModule")
    verify_raw_binding(reader, runner["pureModuleTest"], PURE_MODULE_TEST_PATH, EXPECTED_PURE_MODULE_TEST_RAW_SHA256, "permit.pureModuleTest")
    policy_binding = require_exact_keys(
        document["policyBinding"],
        {"path", "rawSha256", "semanticSha256"},
        "permit.policyBinding",
    )
    require(
        policy_binding
        == {
            "path": POLICY_PATH,
            "rawSha256": EXPECTED_POLICY_RAW_SHA256,
            "semanticSha256": EXPECTED_POLICY_SEMANTIC_SHA256,
        },
        "permit policy binding mismatch",
    )
    policy_raw = reader.read(POLICY_PATH)
    policy_json = strict_json(policy_raw, POLICY_PATH)
    require(sha256_bytes(policy_raw) == EXPECTED_POLICY_RAW_SHA256, "policy raw digest mismatch")
    require(semantic_sha256(policy_raw, policy_json) == EXPECTED_POLICY_SEMANTIC_SHA256, "policy semantic digest mismatch")
    require(
        document["singleUseConsumption"]
        == {
            "maximumExecutionAttempts": 1,
            "automaticRetryAllowed": False,
            "claimCreatedBeforeArchiveOpen": True,
            "claimRetainedOnSuccessOrFailure": True,
            "failureRequiresNewVersionedPermit": True,
        },
        "permit single-use contract mismatch",
    )
    require(
        document["interpreterIsolationContract"]
        == EXPECTED_INTERPRETER_ISOLATION_CONTRACT,
        "permit interpreter isolation contract mismatch",
    )
    require(document["capabilityBoundary"] == EXPECTED_CAPABILITY_BOUNDARY, "permit capability boundary mismatch")
    require(document["archiveRejectionRules"] == EXPECTED_REJECTION_RULES, "permit rejection rules mismatch")
    require(document["resourceLimits"] == EXPECTED_RESOURCE_LIMITS, "permit limits mismatch")
    require(document["outputContract"] == EXPECTED_OUTPUT_CONTRACT, "permit output contract mismatch")
    require(document["personalProjectBoundary"] == EXPECTED_PERSONAL_BOUNDARY, "permit personal boundary mismatch")
    require(document["reviewPlan"] == EXPECTED_REVIEW_PLAN, "permit review plan mismatch")
    require(
        document["nonClaims"]
        == {
            "archiveReadPerformed": False,
            "sourceReviewPerformed": False,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "dependencyClosureComplete": False,
            "reviewedSourceCompileAuthorized": False,
            "runtimeNetworkAuthorized": False,
            "productionDeploymentAuthorized": False,
        },
        "permit non-claims mismatch",
    )


CORE_ARTIFACTS = [
    ("G2R3E015", PERMIT_PATH, "single_use_bounded_static_candidate_location_inventory_execution_permit", EXPECTED_PERMIT_RAW_SHA256),
    ("G2R3E016", POLICY_PATH, "bounded_static_candidate_location_inventory_execution_policy", EXPECTED_POLICY_RAW_SHA256),
    ("G2R3E017", PURE_MODULE_PATH, "pure_bounded_zip_validation_and_candidate_location_inventory_module", EXPECTED_PURE_MODULE_RAW_SHA256),
    ("G2R3E018", PURE_MODULE_TEST_PATH, "pure_zip_module_synthetic_mutation_tests", EXPECTED_PURE_MODULE_TEST_RAW_SHA256),
    ("G2R3E019", RUNNER_PATH, "single_use_nofollow_bounded_candidate_inventory_runner", EXPECTED_RUNNER_RAW_SHA256),
    ("G2R3E020", RUNNER_TEST_PATH, "runner_claim_fd_and_no_replace_synthetic_tests", EXPECTED_RUNNER_TEST_RAW_SHA256),
]
CHECKER_ARTIFACTS = [
    ("G2R3E021", CHECKER_PATH, "strict_no_archive_execution_permit_checker"),
    ("G2R3E022", CHECKER_TEST_PATH, "execution_permit_checker_schema_digest_and_safe_read_tests"),
]


def validate_manifest_common(
    document: Any,
    *,
    label: str,
    document_type: str,
    manifest_id: str,
    artifact_scope: str,
    expected_artifacts: Sequence[tuple[str, str, str]],
    reader: SafeTrackedReader,
) -> None:
    require_exact_keys(
        document,
        {
            "documentType", "schemaVersion", "manifestId", "recordedDate",
            "status", "result", "nextAction", "artifactScope",
            "predecessorManifestBinding", "artifactCount", "orderingRule",
            "collectionDigestAlgorithm", "collectionSha256", "artifacts",
            "executionBoundary" if label == "coreManifest" else "trustBoundary",
        },
        label,
    )
    expected_identity = {
        "documentType": document_type,
        "schemaVersion": "1.0",
        "manifestId": manifest_id,
        "recordedDate": EXPECTED_DATE,
        "status": EXPECTED_STATUS,
        "result": EXPECTED_RESULT,
        "nextAction": EXPECTED_NEXT_ACTION,
        "artifactScope": artifact_scope,
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_path_newline",
    }
    for key, expected in expected_identity.items():
        require(document[key] == expected, f"{label}.{key} mismatch")
    artifacts = document["artifacts"]
    require(type(artifacts) is list, f"{label}.artifacts must be list")
    require(document["artifactCount"] == len(expected_artifacts), f"{label}.artifactCount mismatch")
    require(len(artifacts) == len(expected_artifacts), f"{label}.artifacts length mismatch")
    rows = []
    for artifact, (evidence_id, path, role) in zip(artifacts, expected_artifacts):
        require_exact_keys(artifact, {"evidenceId", "path", "sha256", "role"}, f"{label}.artifact")
        require(
            (artifact["evidenceId"], artifact["path"], artifact["role"])
            == (evidence_id, path, role),
            f"{label}: artifact row mismatch",
        )
        require_digest(artifact["sha256"], f"{label}.{evidence_id}.sha256")
        require(
            artifact["sha256"] == sha256_bytes(reader.read(path)),
            f"{label}.{evidence_id}: artifact digest mismatch",
        )
        rows.append(artifact)
    require(document["collectionSha256"] == collection_sha256(rows), f"{label}: collection digest mismatch")


def validate_core_manifest(document: Any, raw: bytes, reader: SafeTrackedReader) -> None:
    reject_ambiguous_compiler_semantics(document, "coreManifest")
    validate_manifest_common(
        document,
        label="coreManifest",
        document_type="aetherlink.g2-pion-rung3-execution-permit-core-evidence-manifest",
        manifest_id="g2-pion-ice-v4.3.0-rung3-execution-permit-core-evidence-manifest-v3",
        artifact_scope="execution_permit_core_without_checker_self_hash_cycle",
        expected_artifacts=[item[:3] for item in CORE_ARTIFACTS],
        reader=reader,
    )
    predecessor = document["predecessorManifestBinding"]
    verify_json_binding(
        reader,
        predecessor,
        PREDECESSOR_ANCHORS["preparationManifestV2"],
        "coreManifest.predecessor",
    )
    for artifact, expected in zip(document["artifacts"], CORE_ARTIFACTS):
        require(artifact["sha256"] == expected[3], f"coreManifest.{expected[0]} pinned digest mismatch")
    require(document["collectionSha256"] == EXPECTED_CORE_MANIFEST_COLLECTION_SHA256, "core manifest pinned collection mismatch")
    require(sha256_bytes(raw) == EXPECTED_CORE_MANIFEST_RAW_SHA256, "core manifest raw pin mismatch")
    require(semantic_sha256(raw, document) == EXPECTED_CORE_MANIFEST_SEMANTIC_SHA256, "core manifest semantic pin mismatch")
    require(
        document["executionBoundary"]
        == {
            "boundedStaticCandidateInventoryExecutionAuthorized": True,
            "permitConsumed": False,
            "archiveReadPerformed": False,
            "sourceReviewPerformed": False,
            "candidateSelected": False,
            "librarySelected": False,
            "dependencyInstallationAllowed": False,
            "reviewedSourceCompilerInvocationAllowed": False,
            "verifiedPinnedReviewToolModuleLoadingAllowed": True,
            "verifiedAuxiliaryToolModulePythonCompileAllowed": True,
            "socketCreationAllowed": False,
            "networkIoAllowed": False,
            "gitOperationAllowed": False,
            "deviceOperationAllowed": False,
            "productionDeploymentAllowed": False,
            "repositoryOwnerAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationRequired": True,
        },
        "core execution boundary mismatch",
    )


def validate_checker_manifest(document: Any, reader: SafeTrackedReader) -> None:
    reject_ambiguous_compiler_semantics(document, "checkerManifest")
    validate_manifest_common(
        document,
        label="checkerManifest",
        document_type="aetherlink.g2-pion-rung3-execution-permit-checker-evidence-manifest",
        manifest_id="g2-pion-ice-v4.3.0-rung3-execution-permit-checker-evidence-manifest-v4",
        artifact_scope="execution_permit_checker_evidence_separate_from_pinned_core",
        expected_artifacts=CHECKER_ARTIFACTS,
        reader=reader,
    )
    predecessor = require_exact_keys(
        document["predecessorManifestBinding"],
        {"path", "rawSha256", "semanticSha256", "collectionSha256"},
        "checkerManifest.predecessor",
    )
    require(
        predecessor
        == {
            "path": CORE_MANIFEST_PATH,
            "rawSha256": EXPECTED_CORE_MANIFEST_RAW_SHA256,
            "semanticSha256": EXPECTED_CORE_MANIFEST_SEMANTIC_SHA256,
            "collectionSha256": EXPECTED_CORE_MANIFEST_COLLECTION_SHA256,
        },
        "checker manifest predecessor mismatch",
    )
    trust = document["trustBoundary"]
    require(
        trust
        == {
            "invokedCheckerBytesAreLocalTrustRoot": True,
            "checkerSelfAuthenticationClaimed": False,
            "checkerImportsRunner": False,
            "reviewedSourceCompilerInvocationAllowed": False,
            "verifiedPinnedReviewToolModuleLoadingAllowed": True,
            "verifiedAuxiliaryToolModulePythonCompileAllowed": True,
            "archiveReadByCheckerAllowed": False,
            "buildDirectoryReadByCheckerAllowed": False,
            "networkAllowed": False,
            "gitAllowed": False,
        },
        "checker manifest trust boundary mismatch",
    )
    validate_checker_test_binding(document, reader)


def validate_checker_test_binding(document: Any, reader: SafeTrackedReader) -> None:
    """Pin the checker test without introducing a checker self-hash constant."""

    require(type(document) is dict, "checker manifest must be object")
    artifacts = document.get("artifacts")
    require(type(artifacts) is list and len(artifacts) == 2, "checker manifest artifacts mismatch")
    binding = artifacts[1]
    require_exact_keys(
        binding,
        {"evidenceId", "path", "sha256", "role"},
        "checkerManifest.checkerTest",
    )
    require(
        (
            binding["evidenceId"],
            binding["path"],
            binding["role"],
        )
        == (
            "G2R3E022",
            CHECKER_TEST_PATH,
            "execution_permit_checker_schema_digest_and_safe_read_tests",
        ),
        "checker test artifact identity mismatch",
    )
    require(
        binding["sha256"] == EXPECTED_CHECKER_TEST_RAW_SHA256,
        "checker test pinned digest mismatch",
    )
    require(
        sha256_bytes(reader.read(CHECKER_TEST_PATH)) == EXPECTED_CHECKER_TEST_RAW_SHA256,
        "checker test actual digest mismatch",
    )


def validate_runner_source(raw: bytes) -> None:
    try:
        source = raw.decode("utf-8")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise CheckError(f"runner source invalid: {error}") from error
    imports: set[str] = set()
    calls: set[str] = set()
    flags: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
                if node.func.attr == "add_argument":
                    flags.extend(
                        arg.value
                        for arg in node.args
                        if isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)
                        and arg.value.startswith("--")
                    )
    forbidden_imports = {
        "ctypes", "http", "importlib", "mmap", "multiprocessing", "requests",
        "socket", "subprocess", "urllib",
    }
    forbidden_calls = {
        "eval", "input", "popen", "system", "urlopen",
    }
    require(imports.isdisjoint(forbidden_imports), f"runner forbidden imports: {sorted(imports & forbidden_imports)}")
    require(calls.isdisjoint(forbidden_calls), f"runner forbidden calls: {sorted(calls & forbidden_calls)}")
    for forbidden_text in (
        "SourceFileLoader",
        "spec_from_file_location",
        "module_from_spec",
    ):
        require(forbidden_text not in source, f"runner forbidden loader API: {forbidden_text}")
    require(sorted(set(flags)) == ["--check-permit", "--execute-permit"], "runner CLI flags mismatch")
    require("validate_repository" in source, "runner must call permit checker validate_repository")
    module_body = list(tree.body)
    if (
        module_body
        and isinstance(module_body[0], ast.Expr)
        and isinstance(module_body[0].value, ast.Constant)
        and isinstance(module_body[0].value.value, str)
    ):
        module_body = module_body[1:]
    require(len(module_body) >= 5, "runner isolation preamble missing")
    future_import, sys_import, bytecode_assignment, isolation_definition, isolation_call = module_body[:5]
    require(
        isinstance(future_import, ast.ImportFrom)
        and future_import.module == "__future__"
        and [(item.name, item.asname) for item in future_import.names]
        == [("annotations", None)],
        "runner preamble must begin with future annotations import",
    )
    require(
        isinstance(sys_import, ast.Import)
        and [(item.name, item.asname) for item in sys_import.names] == [("sys", None)],
        "runner preamble must import only sys before isolation",
    )
    require(
        isinstance(bytecode_assignment, ast.Assign)
        and len(bytecode_assignment.targets) == 1
        and isinstance(bytecode_assignment.targets[0], ast.Attribute)
        and isinstance(bytecode_assignment.targets[0].value, ast.Name)
        and bytecode_assignment.targets[0].value.id == "sys"
        and bytecode_assignment.targets[0].attr == "dont_write_bytecode"
        and isinstance(bytecode_assignment.value, ast.Constant)
        and bytecode_assignment.value.value is True,
        "runner preamble must set sys.dont_write_bytecode true",
    )
    require(
        isinstance(isolation_definition, ast.FunctionDef)
        and isolation_definition.name == "require_isolated_interpreter",
        "runner isolation function must precede all other imports",
    )
    require(
        isinstance(isolation_call, ast.Expr)
        and isinstance(isolation_call.value, ast.Call)
        and isinstance(isolation_call.value.func, ast.Name)
        and isolation_call.value.func.id == "require_isolated_interpreter"
        and not isolation_call.value.args
        and not isolation_call.value.keywords,
        "runner must call isolation guard before all other imports",
    )
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    main_function = functions.get("main")
    isolation_function = functions.get("require_isolated_interpreter")
    require(main_function is not None, "runner main function missing")
    require(isolation_function is not None, "runner isolation guard function missing")
    body = list(main_function.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    require(bool(body), "runner main body missing")
    first = body[0]
    require(
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Call)
        and isinstance(first.value.func, ast.Name)
        and first.value.func.id == "require_isolated_interpreter"
        and not first.value.args
        and not first.value.keywords,
        "runner main must invoke require_isolated_interpreter first",
    )
    flag_aliases = {
        target.id
        for node in ast.walk(isolation_function)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
        and node.value.attr == "flags"
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    observed_flags = {
        node.attr
        for node in ast.walk(isolation_function)
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "sys"
            and node.value.attr == "flags"
        )
        or (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in flag_aliases
        )
    }
    require(
        observed_flags
        >= {
            "isolated",
            "dont_write_bytecode",
            "ignore_environment",
            "no_user_site",
            "optimize",
        },
        "runner isolation guard must inspect every required sys.flags field",
    )
    parent: dict[ast.AST, ast.AST] = {}
    for ancestor in ast.walk(tree):
        for child in ast.iter_child_nodes(ancestor):
            parent[child] = ancestor

    def enclosing_function(node: ast.AST) -> str | None:
        current = parent.get(node)
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current.name
            current = parent.get(current)
        return None

    sensitive_calls: dict[str, list[ast.Call]] = {"compile": [], "exec": []}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in sensitive_calls:
            sensitive_calls[node.func.id].append(node)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in sensitive_calls:
            raise CheckError(f"runner attribute call to {node.func.attr} forbidden")
    for name, items in sensitive_calls.items():
        require(len(items) == 1, f"runner must call {name} exactly once")
        require(
            enclosing_function(items[0]) == "load_checker_trust_root",
            f"runner {name} call allowed only in load_checker_trust_root",
        )
    loader = functions.get("load_checker_trust_root")
    require(loader is not None, "runner checker trust-root loader missing")
    read_calls = [
        node
        for node in ast.walk(loader)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "read_stable_checker_source"
    ]
    require(len(read_calls) == 1, "runner must read stable checker source exactly once")
    raw_names = {
        target.id
        for node in ast.walk(loader)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "read_stable_checker_source"
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    require(len(raw_names) == 1, "runner stable checker bytes must have one local name")
    compile_call = sensitive_calls["compile"][0]
    require(
        bool(compile_call.args)
        and isinstance(compile_call.args[0], ast.Name)
        and compile_call.args[0].id in raw_names,
        "runner compile must consume the exact stable checker bytes",
    )
    code_names = {
        target.id
        for node in ast.walk(loader)
        if isinstance(node, ast.Assign)
        and node.value is compile_call
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    require(len(code_names) == 1, "runner compiled checker code must have one local name")
    exec_call = sensitive_calls["exec"][0]
    require(
        bool(exec_call.args)
        and isinstance(exec_call.args[0], ast.Name)
        and exec_call.args[0].id in code_names,
        "runner exec must consume only the code compiled from stable checker bytes",
    )


def validate_pure_module_source(raw: bytes) -> None:
    """Reject filesystem, process, and network capabilities in the pure module."""

    try:
        source = raw.decode("utf-8")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise CheckError(f"pure module source invalid: {error}") from error
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    forbidden_imports = {
        "os", "pathlib", "importlib", "ctypes", "fcntl", "glob", "http",
        "mmap", "multiprocessing", "requests", "shutil", "socket",
        "subprocess", "tempfile", "urllib",
    }
    forbidden_calls = {
        "open", "eval", "exec", "compile", "input", "system", "popen",
        "urlopen",
    }
    require(
        imports.isdisjoint(forbidden_imports),
        f"pure module forbidden imports: {sorted(imports & forbidden_imports)}",
    )
    require(
        calls.isdisjoint(forbidden_calls),
        f"pure module forbidden calls: {sorted(calls & forbidden_calls)}",
    )


PURE_MODULE_IMPORT_ALLOWLIST = frozenset(
    {
        "__future__",
        "collections",
        "collections.abc",
        "hashlib",
        "struct",
        "typing",
        "unicodedata",
        "zlib",
    }
)
PURE_MODULE_BUILTIN_ALLOWLIST = frozenset(
    {
        "RuntimeError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "__build_class__",
        "any",
        "bool",
        "bytearray",
        "bytes",
        "dict",
        "enumerate",
        "int",
        "isinstance",
        "len",
        "list",
        "ord",
        "range",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
    }
)


def load_validated_pure_module(root: Path = ROOT) -> types.ModuleType:
    """Load the exact pinned pure-module bytes without a path reopen or pyc."""

    reader = SafeTrackedReader(root)
    raw = reader.read(PURE_MODULE_PATH)
    require_digest(EXPECTED_PURE_MODULE_RAW_SHA256, "EXPECTED_PURE_MODULE_RAW_SHA256")
    require(
        sha256_bytes(raw) == EXPECTED_PURE_MODULE_RAW_SHA256,
        "pure module raw digest mismatch before in-memory load",
    )
    validate_pure_module_source(raw)
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_value: Mapping[str, Any] | None = None,
        locals_value: Mapping[str, Any] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> Any:
        require(level == 0, f"pure module relative import forbidden: {name}")
        require(
            name in PURE_MODULE_IMPORT_ALLOWLIST,
            f"pure module import outside allowlist: {name}",
        )
        return original_import(name, globals_value, locals_value, fromlist, level)

    safe_builtins = {
        name: getattr(builtins, name)
        for name in PURE_MODULE_BUILTIN_ALLOWLIST
    }
    safe_builtins["__import__"] = guarded_import
    module = types.ModuleType("g2_pion_offline_zip")
    module.__dict__.update(
        {
            "__builtins__": safe_builtins,
            "__file__": PURE_MODULE_PATH,
            "__package__": None,
        }
    )
    code = compile(
        raw,
        PURE_MODULE_PATH,
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    )
    exec(code, module.__dict__, module.__dict__)
    return module


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    """Validate the permit suite and return the exact permit identity.

    The runner calls this before claim creation or any archive path resolution.
    """

    reader = SafeTrackedReader(root)
    policy = reader.json(POLICY_PATH)
    permit_raw = reader.read(PERMIT_PATH)
    permit = strict_json(permit_raw, PERMIT_PATH)
    core_raw = reader.read(CORE_MANIFEST_PATH)
    core_manifest = strict_json(core_raw, CORE_MANIFEST_PATH)
    checker_manifest = reader.json(CHECKER_MANIFEST_PATH)
    unresolved = []
    for label, value in (
        ("policy", policy),
        ("permit", permit),
        ("coreManifest", core_manifest),
        ("checkerManifest", checker_manifest),
    ):
        unresolved.extend(unresolved_placeholders(value, label))
    require(not unresolved, f"unresolved artifact placeholders: {', '.join(unresolved)}")
    require_resolved_digest_constants()
    require(sha256_bytes(permit_raw) == EXPECTED_PERMIT_RAW_SHA256, "permit raw pin mismatch")
    require(semantic_sha256(permit_raw, permit) == EXPECTED_PERMIT_SEMANTIC_SHA256, "permit semantic pin mismatch")
    validate_policy(policy)
    validate_permit(permit, permit_raw, reader)
    validate_core_manifest(core_manifest, core_raw, reader)
    validate_checker_manifest(checker_manifest, reader)
    validate_runner_source(reader.read(RUNNER_PATH))
    validate_pure_module_source(reader.read(PURE_MODULE_PATH))
    return {
        "permit": permit,
        "permitRawSha256": sha256_bytes(permit_raw),
        "permitSemanticSha256": semantic_sha256(permit_raw, permit),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        result = validate_repository()
    except CheckError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "passed",
                "permitId": result["permit"]["permitId"],
                "permitRawSha256": result["permitRawSha256"],
                "permitSemanticSha256": result["permitSemanticSha256"],
                "archiveRead": False,
                "buildDirectoryRead": False,
                "runnerImported": False,
                "permitConsumptionState": "not_inspected",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
