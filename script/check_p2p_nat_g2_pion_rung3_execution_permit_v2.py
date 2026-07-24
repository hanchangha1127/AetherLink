#!/usr/bin/env python3
"""Validate and safely load the G2 Pion rung-three v2 permit toolchain.

The checker reads only an exact repository allowlist.  It has no build or
archive capability, follows no symlinks, writes nothing, and never imports the
runner.  The review adapter retains exact base-validator bytes in a closure and
passes them as the first argument to the exact creator-policy-v2 API.
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
import stat
import sys
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG2 = f"{BASE}/rung-two"
RUNG3 = f"{BASE}/rung-three"

RECEIPT_PATH = f"{RUNG2}/source-acquisition-receipt-v1.json"
FAILURE_PATH = f"{RUNG3}/offline-source-review-execution-failure-v1.json"
PROGRESS_PATH = f"{RUNG3}/offline-source-review-progress-v2.json"
SUPERSESSION_PATH = f"{RUNG3}/canonical-document-supersession-v2.json"
FAILURE_CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_failure.py"
FAILURE_CHECKER_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_execution_failure.py"
PREDECESSOR_MANIFEST_PATH = f"{RUNG3}/evidence-manifest-v5.json"

POLICY_PATH = f"{RUNG3}/review-execution-policy-v2.json"
PERMIT_PATH = f"{RUNG3}/offline-source-review-execution-permit-v2.json"
CORE_MANIFEST_PATH = f"{RUNG3}/execution-permit-core-manifest-v6.json"
CHECKER_MANIFEST_PATH = f"{RUNG3}/execution-permit-checker-manifest-v7.json"
BASE_VALIDATOR_PATH = "script/p2p_nat_g2_pion_offline_zip.py"
BASE_VALIDATOR_TEST_PATH = "script/test_p2p_nat_g2_pion_offline_zip.py"
OVERLAY_PATH = "script/p2p_nat_g2_pion_offline_zip_creator_policy_v2.py"
OVERLAY_TEST_PATH = "script/test_p2p_nat_g2_pion_offline_zip_creator_policy_v2.py"
RUNNER_PATH = "script/run_p2p_nat_g2_pion_rung3_offline_review_v2_once.py"
RUNNER_TEST_PATH = "script/test_run_p2p_nat_g2_pion_rung3_offline_review_v2_once.py"
CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_permit_v2.py"
CHECKER_TEST_PATH = "script/test_p2p_nat_g2_pion_rung3_execution_permit_v2.py"

EXPECTED_DATE = "2026-07-23"
EXPECTED_STATUS = "rung3_bounded_static_inventory_v2_execution_authorized_not_consumed"
EXPECTED_RESULT = (
    "separate_single_use_bounded_static_candidate_location_inventory_v2_"
    "authorized_not_executed"
)
EXPECTED_NEXT_ACTION = "execute_bound_rung3_static_candidate_location_inventory_v2_once"
EXPECTED_SCOPE = (
    "separate_single_use_offline_archive_read_and_bounded_static_candidate_"
    "location_inventory_only_not_full_rung3_semantic_review"
)

EXPECTED_RECEIPT_RAW = "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6"
EXPECTED_FAILURE_RAW = "ec1883c9ca264e79120bf24a1624e661254beade219280122895ce05cbe1ec05"
EXPECTED_FAILURE_SEMANTIC = "e13e2ceb158842a72cfe3b4ed76b9933225f7be169a46cda74c3ba76d682a7b3"
EXPECTED_PROGRESS_RAW = "a58e491f19707c0d4fef4401aa27ff74fdcf473f71d79025e794e4ca538ddd65"
EXPECTED_PROGRESS_SEMANTIC = "e73ee097dc42c6de26b4ae935bc78ee2304f15ce2bfcd78b6edd8c8961423b23"
EXPECTED_SUPERSESSION_RAW = "d224fb87352447ff30bcf33e3498ae37fc68a2c9fd8380a167efb2f7552e7750"
EXPECTED_SUPERSESSION_SEMANTIC = "2514334023680b5118c6fc354710ddb04337b2bd59c63424ae8500ed9fe65a87"
EXPECTED_PREDECESSOR_RAW = "dff78fb4949174f453d81e49d1cc411b49da7386469085d8326971f71c6fa93f"
EXPECTED_PREDECESSOR_SEMANTIC = "6c541fed6d8d8f204f14f2809110b665763140a61ad77e8da943acad096c32bb"
EXPECTED_PREDECESSOR_COLLECTION = "6b15cd7e339b3a6be43b834733fc0ff9faf868910a9bf5ee35fe5597b0d1f91b"

EXPECTED_POLICY_RAW = "208b572af2ab2fb425e28ddb8ac74a4044e80643a426a22cf3a1c19f4fbf84c0"
EXPECTED_POLICY_SEMANTIC = "539d131ff1979ce1985efe3056242e3eb0bd6b1d1a9295a14daadb84e0de371e"
EXPECTED_PERMIT_RAW = "7f125ecc7d6e6d0a597cb4cddecebf37eaad5e0a8f614d1019603b4e952f9a06"
EXPECTED_PERMIT_SEMANTIC = "3164cbf4b25f75c9689ad47db50776ba4fbbe7c4b315dfa5bcfbbba01e5c0321"
EXPECTED_CORE_RAW = "443c6d918b94329692f1ed57a989263ae38f939120752103c47e852c50f83e73"
EXPECTED_CORE_SEMANTIC = "861c04832e845be2066632697f1a5b8eb3085157328351cde5fdc052c6c00240"
EXPECTED_CORE_COLLECTION = "cf53cf2b33ab07ec539a97a4f8f43cc84e32848e9fbfb2ae8669250529312f41"

EXPECTED_BASE_RAW = "9daef717b30337191ee9902110bdf4455babacb261acab9124d37de72fa8988b"
EXPECTED_BASE_TEST_RAW = "49b4b99ec194186848fc127c10caa140e96260e7530830acc7781bfcb6a8a035"
EXPECTED_OVERLAY_RAW = "52e593d919066e7657acf20e1027c9c4a7753b16746c7f20e2eb62557fb0a2fc"
EXPECTED_OVERLAY_TEST_RAW = "1cbb7886b1a4b8130af3926941728aecddf764d94fd546c18c12f54ef4159d9c"

MAX_TRACKED_FILE_BYTES = 8 * 1024 * 1024
HEX_SHA256 = __import__("re").compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = __import__("re").compile(r"^__PENDING_[A-Z0-9_]+__$")

PREDECESSOR_BINDINGS = {
    "failureEvidenceManifestV5": {
        "path": PREDECESSOR_MANIFEST_PATH,
        "rawSha256": EXPECTED_PREDECESSOR_RAW,
        "semanticSha256": EXPECTED_PREDECESSOR_SEMANTIC,
        "collectionSha256": EXPECTED_PREDECESSOR_COLLECTION,
    },
    "executionFailureV1": {
        "path": FAILURE_PATH,
        "rawSha256": EXPECTED_FAILURE_RAW,
        "semanticSha256": EXPECTED_FAILURE_SEMANTIC,
    },
    "executionProgressV2": {
        "path": PROGRESS_PATH,
        "rawSha256": EXPECTED_PROGRESS_RAW,
        "semanticSha256": EXPECTED_PROGRESS_SEMANTIC,
    },
    "canonicalSupersessionV2": {
        "path": SUPERSESSION_PATH,
        "rawSha256": EXPECTED_SUPERSESSION_RAW,
        "semanticSha256": EXPECTED_SUPERSESSION_SEMANTIC,
    },
}

FAILURE_ARTIFACT_PATHS = (
    FAILURE_PATH,
    PROGRESS_PATH,
    SUPERSESSION_PATH,
    FAILURE_CHECKER_PATH,
    FAILURE_CHECKER_TEST_PATH,
)
AUTHORITY_READ_ALLOWLIST = frozenset(
    {
        RECEIPT_PATH,
        *FAILURE_ARTIFACT_PATHS,
        PREDECESSOR_MANIFEST_PATH,
        POLICY_PATH,
        PERMIT_PATH,
        CORE_MANIFEST_PATH,
        BASE_VALIDATOR_PATH,
        BASE_VALIDATOR_TEST_PATH,
        OVERLAY_PATH,
        OVERLAY_TEST_PATH,
    }
)
OBSERVATIONAL_READ_ALLOWLIST = frozenset(
    {
        CHECKER_MANIFEST_PATH,
        RUNNER_PATH,
        RUNNER_TEST_PATH,
        CHECKER_PATH,
        CHECKER_TEST_PATH,
    }
)
TRACKED_READ_ALLOWLIST = AUTHORITY_READ_ALLOWLIST | OBSERVATIONAL_READ_ALLOWLIST


class CheckError(ValueError):
    """Closed permit evidence or tool bytes failed validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
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


def semantic_sha256(parsed: Any) -> str:
    return sha256_bytes(
        json.dumps(
            parsed,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def strict_json(data: bytes, label: str) -> Any:
    require(data.endswith(b"\n") and not data.endswith(b"\n\n"), f"{label}: one final LF required")
    require(b"\r" not in data, f"{label}: CR forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        parsed = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CheckError(f"{label}: non-finite value {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid strict JSON: {error}") from error
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


def unresolved_placeholders(value: Any, label: str = "$") -> list[str]:
    if type(value) is str:
        return [label] if PLACEHOLDER.fullmatch(value) else []
    if type(value) is list:
        return [
            item
            for index, child in enumerate(value)
            for item in unresolved_placeholders(child, f"{label}[{index}]")
        ]
    if type(value) is dict:
        return [
            item
            for key, child in value.items()
            for item in unresolved_placeholders(child, f"{label}.{key}")
        ]
    return []


def validate_relative_path(
    path: str,
    allowed_paths: frozenset[str] = TRACKED_READ_ALLOWLIST,
) -> tuple[str, ...]:
    require(type(path) is str and path in allowed_paths, f"unlisted read forbidden: {path}")
    require("\\" not in path and "\x00" not in path, f"unsafe path: {path}")
    pure = PurePosixPath(path)
    require(not pure.is_absolute(), f"absolute path forbidden: {path}")
    require(pure.parts and all(part not in ("", ".", "..") for part in pure.parts), f"unsafe path: {path}")
    require(pure.parts[0] != "build", f"build read forbidden: {path}")
    require(
        not path.lower().endswith((".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z")),
        f"archive read forbidden: {path}",
    )
    return pure.parts


class SafeTrackedReader:
    """Component-wise no-follow stable reader for the exact allowlist."""

    def __init__(
        self,
        root: Path,
        allowed_paths: frozenset[str] = TRACKED_READ_ALLOWLIST,
    ) -> None:
        self.root = root
        self.allowed_paths = allowed_paths
        self.cache: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        parts = validate_relative_path(path, self.allowed_paths)
        if path in self.cache:
            return self.cache[path]
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
        file_flags = os.O_RDONLY | nofollow
        root_fd = os.open(os.fspath(self.root), directory_flags)
        parent_fd = root_fd
        directories: list[int] = []
        try:
            for component in parts[:-1]:
                next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
                directories.append(next_fd)
                parent_fd = next_fd
            file_fd = os.open(parts[-1], file_flags, dir_fd=parent_fd)
            try:
                before = os.fstat(file_fd)
                require(stat.S_ISREG(before.st_mode), f"{path}: regular file required")
                require(before.st_nlink == 1, f"{path}: single link required")
                require(0 <= before.st_size <= MAX_TRACKED_FILE_BYTES, f"{path}: size out of bounds")
                remaining = before.st_size
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(file_fd, min(65_536, remaining))
                    require(bool(chunk), f"{path}: unexpected EOF")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                require(os.read(file_fd, 1) == b"", f"{path}: grew during read")
                after = os.fstat(file_fd)
                fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
                require(
                    all(getattr(before, field) == getattr(after, field) for field in fields),
                    f"{path}: changed during read",
                )
                data = b"".join(chunks)
            finally:
                os.close(file_fd)
        except OSError as error:
            raise CheckError(f"{path}: safe read failed: {error}") from error
        finally:
            for descriptor in reversed(directories):
                os.close(descriptor)
            os.close(root_fd)
        self.cache[path] = data
        return data

    def json(self, path: str) -> Any:
        return strict_json(self.read(path), path)


def verify_json_binding(reader: SafeTrackedReader, binding: Any, expected: Mapping[str, str], label: str) -> Any:
    exact_keys(binding, set(expected), label)
    require(binding == expected, f"{label}: binding mismatch")
    raw = reader.read(expected["path"])
    parsed = strict_json(raw, expected["path"])
    require(sha256_bytes(raw) == expected["rawSha256"], f"{label}: raw digest mismatch")
    require(semantic_sha256(parsed) == expected["semanticSha256"], f"{label}: semantic digest mismatch")
    if "collectionSha256" in expected:
        require(parsed.get("collectionSha256") == expected["collectionSha256"], f"{label}: collection mismatch")
    return parsed


def collection_sha256(artifacts: Sequence[Mapping[str, Any]]) -> str:
    payload = "".join(
        f"{row['evidenceId']}\t{row['sha256']}\t{row['path']}\n"
        for row in artifacts
    ).encode("utf-8")
    return sha256_bytes(payload)


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
EXPECTED_CROSSWALK = [
    {"verificationId": "g2-r3-egress-path-coverage", "patchUnitIndexes": [0, 4, 5, 6]},
    {"verificationId": "g2-r3-ingress-path-coverage", "patchUnitIndexes": [0, 2, 4, 6]},
    {"verificationId": "g2-r3-address-and-resolution-adversarial", "patchUnitIndexes": [4, 5]},
    {"verificationId": "g2-r3-turn-tls-service-identity", "patchUnitIndexes": [1, 5]},
    {"verificationId": "g2-r3-secure-session-promotion", "patchUnitIndexes": [6]},
    {"verificationId": "g2-r3-resource-and-event-bounds", "patchUnitIndexes": [2, 3]},
    {"verificationId": "g2-r3-secret-free-diagnostics", "patchUnitIndexes": [1]},
    {"verificationId": "g2-r3-deadline-shutdown", "patchUnitIndexes": [3]},
]
EXPECTED_CREATOR_POLICY = {
    "acceptedCreatorSystems": [0, 3],
    "msDosCreatorSystem": 0,
    "unixCreatorSystem": 3,
    "acceptedMsDosRegularFileExternalAttributes": ["00", "01", "20", "21"],
    "msDosHighAttributeBitsMustBeZero": True,
    "msDosDirectoryAllowed": False,
    "syntheticReadOnlyRegularMode": "100444",
    "syntheticModeMeaning": "in_memory_validation_provenance_only_not_archive_or_filesystem_mode_evidence",
    "archiveExtractionAllowed": False,
}
EXPECTED_PERSONAL_BOUNDARY = {
    "technicalSafetyGatesRemainRequired": True,
    "repositoryOwnerAuthenticationIsNotATechnicalGate": True,
    "repositoryOwnerAuthenticationRequired": False,
    "externalIdentityProofRequired": False,
    "userActionRequired": False,
    "productEndpointAuthenticationRequired": True,
    "productEndpointAuthenticationMeaning": "runtime_product_boundary_only_not_repository_owner_or_execution_permit_authentication",
}
EXPECTED_NONCLAIMS = {
    "archiveReadPerformed": False,
    "sourceReviewPerformed": False,
    "semanticSourceReviewPerformed": False,
    "candidateLocationInventoryPerformed": False,
    "rungThreeComplete": False,
    "candidateSelected": False,
    "librarySelected": False,
    "dependencyClosureComplete": False,
    "releaseReady": False,
    "productionReleaseAuthorized": False,
}
EXPECTED_ISOLATION = {
    "preflightCommand": ["python3", "-I", "-B", "-S", RUNNER_PATH, "--check-permit"],
    "executionCommand": ["python3", "-I", "-B", "-S", RUNNER_PATH, "--execute-permit"],
    "requiredSysFlags": {
        "isolated": 1,
        "dont_write_bytecode": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "no_site": 1,
        "optimize": 0,
    },
    "ambientPythonPathAllowed": False,
    "systemSiteInitializationAllowed": False,
    "sitePackagesAllowed": False,
    "projectToolBytecodeReadAllowed": False,
    "projectToolBytecodeWriteAllowed": False,
    "trustedInterpreterStdlibBytecodeReadAllowed": True,
    "trustedInterpreterStdlibBytecodeWriteAllowed": False,
    "runnerEarlyGuardRequired": True,
}
EXPECTED_COMPILER_ACCOUNTING = {
    "preflightVerifiedAuxiliaryToolModulePythonCompileCount": 1,
    "executionVerifiedAuxiliaryToolModulePythonCompileCount": 3,
    "executionCompiledModules": ["permit_checker", "creator_policy_overlay", "private_base_validator"],
    "reviewedSourceCompilerInvocationCount": 0,
}


def validate_predecessor_manifest(document: Any, reader: SafeTrackedReader) -> None:
    require(document["manifestId"] == "g2-pion-ice-v4.3.0-rung3-execution-failure-evidence-manifest-v5", "v5 manifest id")
    require(document["collectionSha256"] == EXPECTED_PREDECESSOR_COLLECTION, "v5 collection pin")
    artifacts = document.get("artifacts")
    require(type(artifacts) is list and len(artifacts) == 5, "v5 artifact count")
    require([row.get("path") for row in artifacts] == list(FAILURE_ARTIFACT_PATHS), "v5 artifact paths")
    for row in artifacts:
        exact_keys(row, {"evidenceId", "path", "sha256", "role"}, "v5 artifact")
        require(row["sha256"] == sha256_bytes(reader.read(row["path"])), "v5 artifact digest")
    require(collection_sha256(artifacts) == EXPECTED_PREDECESSOR_COLLECTION, "v5 collection recompute")
    boundary = document.get("failureBoundary")
    require(
        type(boundary) is dict
        and boundary.get("permitVersionOneConsumed") is True
        and boundary.get("automaticRetryAllowed") is False
        and boundary.get("completed") is False
        and boundary.get("rungThreeComplete") is False,
        "v5 failure boundary",
    )


def validate_policy(document: Any) -> None:
    exact_keys(
        document,
        {
            "documentType", "schemaVersion", "policyId", "recordedDate", "status",
            "evidenceBasis", "scope", "predecessorFailureBoundary",
            "creatorMetadataPolicy", "reviewPlan", "runtimePaths", "cliContract",
            "interpreterIsolationContract", "archiveOpenContract",
            "consumptionContract", "outputContract", "archiveRejectionRules",
            "resourceLimits", "capabilityBoundary", "compilerAccounting",
            "personalProjectBoundary", "nonClaims",
        },
        "policy",
    )
    require(document["documentType"] == "aetherlink.g2-pion-rung3-offline-source-review-execution-policy", "policy type")
    require(document["schemaVersion"] == "2.0", "policy schema")
    require(document["policyId"] == "g2-pion-ice-v4.3.0-offline-source-review-execution-policy-v2", "policy id")
    require(document["recordedDate"] == EXPECTED_DATE, "policy date")
    require(document["scope"] == EXPECTED_SCOPE, "policy scope")
    require(document["creatorMetadataPolicy"] == EXPECTED_CREATOR_POLICY, "creator metadata policy")
    plan = document["reviewPlan"]
    require(plan["patchUnits"] == EXPECTED_PATCH_UNITS, "seven patch units")
    require(plan["verificationUnits"] == EXPECTED_VERIFICATION_UNITS, "eight verification units")
    require(plan["verificationCrosswalk"] == EXPECTED_CROSSWALK, "7-to-8 crosswalk")
    require(document["interpreterIsolationContract"] == EXPECTED_ISOLATION, "policy isolation")
    require(document["compilerAccounting"] == EXPECTED_COMPILER_ACCOUNTING, "policy compiler accounting")
    require(document["personalProjectBoundary"] == EXPECTED_PERSONAL_BOUNDARY, "policy personal boundary")
    require(document["nonClaims"] == EXPECTED_NONCLAIMS, "policy non-claims")
    require(document["outputContract"]["directory"].endswith("/review-v2"), "policy v2 output")
    require(
        {
            key: document["outputContract"][key]
            for key in (
                "temporaryBackingFilesRetainedOnSuccessOrFailure",
                "temporaryNameDeletionAllowed",
                "publishedFinalLinkCount",
                "sameUidHostileConcurrentFilesystemMutationOutOfScope",
                "runtimePublicationRequiresPostRunReadbackForCanonicalEvidence",
            )
        }
        == {
            "temporaryBackingFilesRetainedOnSuccessOrFailure": True,
            "temporaryNameDeletionAllowed": False,
            "publishedFinalLinkCount": 2,
            "sameUidHostileConcurrentFilesystemMutationOutOfScope": True,
            "runtimePublicationRequiresPostRunReadbackForCanonicalEvidence": True,
        },
        "policy retained backing-file publication boundary",
    )
    require("review-v1" not in json.dumps(document["outputContract"], sort_keys=True), "policy must not target v1")
    require(document["predecessorFailureBoundary"] == {
        "permitV1Consumed": True,
        "permitV1RetryAllowed": False,
        "permitV1ClaimRetained": True,
        "permitV1MutationAllowed": False,
        "v2UsesDistinctOutputDirectoryAndNames": True,
    }, "policy v1 immutable boundary")


def validate_archive_binding(binding: Any, reader: SafeTrackedReader) -> None:
    require(type(binding) is dict and "path" not in binding, "permit must not copy archive path")
    expected = {
        "receiptPath": RECEIPT_PATH,
        "receiptRawSha256": EXPECTED_RECEIPT_RAW,
        "archiveMetadataJsonPointer": "/archive",
        "archivePathJsonPointer": "/archive/path",
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
    require(binding == expected, "archive identity binding")
    receipt_raw = reader.read(RECEIPT_PATH)
    require(sha256_bytes(receipt_raw) == EXPECTED_RECEIPT_RAW, "receipt raw pin")
    archive = strict_json(receipt_raw, RECEIPT_PATH).get("archive")
    require(type(archive) is dict, "receipt archive metadata")
    require(
        archive.get("bytes") == 293023
        and archive.get("entryCount") == 129
        and archive.get("fileCount") == 129
        and archive.get("totalUncompressedBytes") == 1131286
        and archive.get("filesystemExtracted") is False
        and archive.get("sourceReviewPerformed") is False,
        "receipt archive identity",
    )


EXPECTED_TOOL_BINDINGS = {
    "baseValidator": {"path": BASE_VALIDATOR_PATH, "rawSha256": EXPECTED_BASE_RAW},
    "baseValidatorTest": {"path": BASE_VALIDATOR_TEST_PATH, "rawSha256": EXPECTED_BASE_TEST_RAW},
    "creatorPolicyOverlay": {"path": OVERLAY_PATH, "rawSha256": EXPECTED_OVERLAY_RAW},
    "creatorPolicyOverlayTest": {"path": OVERLAY_TEST_PATH, "rawSha256": EXPECTED_OVERLAY_TEST_RAW},
}


def validate_permit(document: Any, raw: bytes, reader: SafeTrackedReader) -> None:
    exact_keys(
        document,
        {
            "documentType", "schemaVersion", "permitId", "recordedDate", "status",
            "result", "nextAction", "scope", "contentBinding", "authorityBindings",
            "archiveIdentityBinding", "toolBindings", "policyBinding",
            "executionTrustBoundary",
            "predecessorFailureBoundary", "singleUseConsumption",
            "creatorMetadataPolicy", "interpreterIsolationContract",
            "capabilityBoundary", "compilerAccounting", "reviewPlanBinding",
            "outputContract", "personalProjectBoundary", "nonClaims",
        },
        "permit",
    )
    require(document["documentType"] == "aetherlink.g2-pion-rung3-offline-source-review-execution-permit", "permit type")
    require(document["schemaVersion"] == "2.0", "permit schema")
    require(document["permitId"] == "g2-pion-ice-v4.3.0-offline-source-review-execution-permit-v2", "permit id")
    require((document["recordedDate"], document["status"], document["result"], document["nextAction"], document["scope"])
            == (EXPECTED_DATE, EXPECTED_STATUS, EXPECTED_RESULT, EXPECTED_NEXT_ACTION, EXPECTED_SCOPE), "permit identity")
    content = document["contentBinding"]
    exact_keys(content, {"algorithm", "canonicalization", "scope", "sha256"}, "permit content binding")
    core = {key: value for key, value in document.items() if key != "contentBinding"}
    require(content == {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(core)),
    }, "permit content binding")
    authority = exact_keys(document["authorityBindings"], set(PREDECESSOR_BINDINGS), "permit authority")
    for label, expected in PREDECESSOR_BINDINGS.items():
        verify_json_binding(reader, authority[label], expected, label)
    validate_archive_binding(document["archiveIdentityBinding"], reader)
    require(document["toolBindings"] == EXPECTED_TOOL_BINDINGS, "permit tool bindings")
    for binding in EXPECTED_TOOL_BINDINGS.values():
        require(sha256_bytes(reader.read(binding["path"])) == binding["rawSha256"], "tool raw binding")
    require(document["policyBinding"] == {
        "path": POLICY_PATH,
        "rawSha256": EXPECTED_POLICY_RAW,
        "semanticSha256": EXPECTED_POLICY_SEMANTIC,
    }, "permit policy binding")
    require(document["executionTrustBoundary"] == {
        "invokedRunnerIsLocalTrustRoot": True,
        "runnerAuthenticatedBy": "direct_local_invocation",
        "checkerAuthenticatedBy": "runner_embedded_raw_sha256",
        "checkerManifestExecutionAuthority": False,
    }, "permit execution trust boundary")
    require(document["creatorMetadataPolicy"] == EXPECTED_CREATOR_POLICY, "permit creator policy")
    require(document["interpreterIsolationContract"] == EXPECTED_ISOLATION, "permit isolation")
    require(document["compilerAccounting"] == EXPECTED_COMPILER_ACCOUNTING, "permit compiler accounting")
    require(document["reviewPlanBinding"] == {
        "policyPath": POLICY_PATH,
        "policySemanticSha256": EXPECTED_POLICY_SEMANTIC,
        "patchUnitCount": 7,
        "verificationUnitCount": 8,
        "crosswalkPreservedExactlyFromPermitV1": True,
    }, "permit review plan binding")
    require(document["personalProjectBoundary"] == EXPECTED_PERSONAL_BOUNDARY, "permit personal boundary")
    require(document["nonClaims"] == EXPECTED_NONCLAIMS, "permit non-claims")
    require(document["predecessorFailureBoundary"]["permitV1RetryAllowed"] is False, "v1 retry forbidden")
    require(document["predecessorFailureBoundary"]["permitV1MutationAllowed"] is False, "v1 mutation forbidden")
    require(document["outputContract"]["directory"] == "build/offline-source/pion-ice-v4.3.0/review-v2", "v2 output directory")
    require(document["outputContract"]["claimFileName"] == ".g2-pion-ice-v4.3.0-rung3-offline-review-v2.claim", "v2 claim")
    require(
        document["outputContract"]["temporaryBackingFilesRetainedOnSuccessOrFailure"] is True
        and document["outputContract"]["temporaryNameDeletionAllowed"] is False
        and document["outputContract"]["publishedFinalLinkCount"] == 2
        and document["outputContract"]["sameUidHostileConcurrentFilesystemMutationOutOfScope"] is True
        and document["outputContract"]["runtimePublicationRequiresPostRunReadbackForCanonicalEvidence"] is True,
        "permit retained backing-file publication boundary",
    )
    require(sha256_bytes(raw) == EXPECTED_PERMIT_RAW, "permit raw pin")
    require(semantic_sha256(document) == EXPECTED_PERMIT_SEMANTIC, "permit semantic pin")


CORE_ARTIFACTS = [
    ("G2R3E028", PERMIT_PATH, "separate_single_use_v2_bounded_static_candidate_location_inventory_execution_permit", EXPECTED_PERMIT_RAW),
    ("G2R3E029", POLICY_PATH, "v2_creator_metadata_and_bounded_inventory_execution_policy", EXPECTED_POLICY_RAW),
    ("G2R3E030", BASE_VALIDATOR_PATH, "base_pure_bounded_zip_validator", EXPECTED_BASE_RAW),
    ("G2R3E031", BASE_VALIDATOR_TEST_PATH, "base_validator_synthetic_mutation_tests", EXPECTED_BASE_TEST_RAW),
    ("G2R3E032", OVERLAY_PATH, "exact_creator_zero_regular_file_policy_overlay", EXPECTED_OVERLAY_RAW),
    ("G2R3E033", OVERLAY_TEST_PATH, "creator_policy_overlay_synthetic_tests", EXPECTED_OVERLAY_TEST_RAW),
]


def validate_manifest_rows(document: Any, expected: Sequence[tuple[str, str, str, str]], reader: SafeTrackedReader, label: str) -> None:
    artifacts = document.get("artifacts")
    require(type(artifacts) is list and len(artifacts) == len(expected), f"{label} artifacts")
    require(document.get("artifactCount") == len(expected), f"{label} artifact count")
    for row, (evidence_id, path, role, digest) in zip(artifacts, expected):
        exact_keys(row, {"evidenceId", "path", "sha256", "role"}, f"{label} artifact")
        require(row == {"evidenceId": evidence_id, "path": path, "sha256": digest, "role": role}, f"{label} artifact row")
        require(sha256_bytes(reader.read(path)) == digest, f"{label} actual artifact digest")
    require(document.get("collectionSha256") == collection_sha256(artifacts), f"{label} collection")


def validate_core_manifest(document: Any, raw: bytes, reader: SafeTrackedReader) -> None:
    exact_keys(
        document,
        {
            "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
            "result", "nextAction", "artifactScope", "predecessorManifestBinding",
            "artifactCount", "orderingRule", "collectionDigestAlgorithm",
            "collectionSha256", "artifacts", "executionBoundary",
        },
        "core manifest",
    )
    require(document["manifestId"] == "g2-pion-ice-v4.3.0-rung3-execution-permit-core-evidence-manifest-v6", "core id")
    require(
        document["artifactScope"]
        == "execution_authority_core_without_runner_checker_or_evidence_manifest_cycle",
        "core authority scope",
    )
    require((document["status"], document["result"], document["nextAction"]) == (EXPECTED_STATUS, EXPECTED_RESULT, EXPECTED_NEXT_ACTION), "core status")
    require(document["predecessorManifestBinding"] == PREDECESSOR_BINDINGS["failureEvidenceManifestV5"], "core predecessor")
    validate_manifest_rows(document, CORE_ARTIFACTS, reader, "core")
    require(document["collectionSha256"] == EXPECTED_CORE_COLLECTION, "core collection pin")
    require(sha256_bytes(raw) == EXPECTED_CORE_RAW, "core raw pin")
    require(semantic_sha256(document) == EXPECTED_CORE_SEMANTIC, "core semantic pin")
    boundary = document["executionBoundary"]
    require(
        boundary["permitConsumed"] is False
        and boundary["v1PermitRetryAllowed"] is False
        and boundary["v1ClaimRetainedAndImmutable"] is True
        and boundary["archiveReadPerformed"] is False
        and boundary["candidateLocationInventoryPerformed"] is False
        and boundary["semanticSourceReviewPerformed"] is False
        and boundary["rungThreeComplete"] is False
        and boundary["candidateSelected"] is False
        and boundary["librarySelected"] is False
        and boundary["releaseReady"] is False
        and boundary["reviewedSourceCompilerInvocationAllowed"] is False
        and boundary["preflightVerifiedAuxiliaryToolModulePythonCompileCount"] == 1
        and boundary["executionVerifiedAuxiliaryToolModulePythonCompileCount"] == 3
        and boundary["repositoryOwnerAuthenticationRequired"] is False
        and boundary["externalIdentityProofRequired"] is False
        and boundary["userActionRequired"] is False,
        "core execution boundary",
    )


def validate_checker_manifest(document: Any, reader: SafeTrackedReader) -> None:
    exact_keys(
        document,
        {
            "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
            "result", "nextAction", "artifactScope", "predecessorManifestBinding",
            "artifactCount", "orderingRule", "collectionDigestAlgorithm",
            "collectionSha256", "artifacts", "trustBoundary",
        },
        "checker manifest",
    )
    require(document["manifestId"] == "g2-pion-ice-v4.3.0-rung3-execution-permit-checker-evidence-manifest-v7", "checker id")
    require(
        document["artifactScope"]
        == "observational_execution_toolchain_evidence_not_execution_authority",
        "checker evidence scope",
    )
    require((document["status"], document["result"], document["nextAction"]) == (EXPECTED_STATUS, EXPECTED_RESULT, EXPECTED_NEXT_ACTION), "checker status")
    require(document["predecessorManifestBinding"] == {
        "path": CORE_MANIFEST_PATH,
        "rawSha256": EXPECTED_CORE_RAW,
        "semanticSha256": EXPECTED_CORE_SEMANTIC,
        "collectionSha256": EXPECTED_CORE_COLLECTION,
    }, "checker predecessor")
    artifacts = document["artifacts"]
    require(type(artifacts) is list and len(artifacts) == 4 and document["artifactCount"] == 4, "checker artifacts")
    identities = [
        ("G2R3E034", RUNNER_PATH, "observational_directly_invoked_v2_runner"),
        ("G2R3E035", RUNNER_TEST_PATH, "observational_v2_runner_synthetic_tests"),
        ("G2R3E036", CHECKER_PATH, "strict_no_archive_v2_execution_permit_checker"),
        ("G2R3E037", CHECKER_TEST_PATH, "v2_checker_schema_digest_loader_and_safe_read_tests"),
    ]
    for row, identity in zip(artifacts, identities):
        exact_keys(row, {"evidenceId", "path", "sha256", "role"}, "checker artifact")
        require((row["evidenceId"], row["path"], row["role"]) == identity, "checker artifact identity")
        require(HEX_SHA256.fullmatch(row["sha256"]) is not None, "checker artifact digest")
        require(row["sha256"] == sha256_bytes(reader.read(row["path"])), "checker artifact actual digest")
    require(document["collectionSha256"] == collection_sha256(artifacts), "checker collection")
    require(document["trustBoundary"] == {
        "executionAuthority": False,
        "requiredForPermitValidation": False,
        "requiredForPermitExecution": False,
        "absenceOrDriftDoesNotInvalidatePermitCore": True,
        "invokedRunnerIsLocalTrustRoot": True,
        "runnerAuthenticatedBy": "direct_local_invocation",
        "checkerAuthenticatedBy": "runner_embedded_raw_sha256",
        "checkerSelfAuthenticationClaimed": False,
        "checkerManifestSelfAuthenticationClaimed": False,
        "artifactHashesAreObservational": True,
    }, "checker trust boundary")


def parse_source(raw: bytes, label: str) -> tuple[str, ast.Module]:
    try:
        source = raw.decode("utf-8", errors="strict")
        return source, ast.parse(source, filename=label)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise CheckError(f"{label}: invalid source: {error}") from error


def source_imports_calls(tree: ast.AST) -> tuple[set[str], list[tuple[str, ast.Call]]]:
    imports: set[str] = set()
    calls: list[tuple[str, ast.Call]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append((node.func.id, node))
            elif isinstance(node.func, ast.Attribute):
                calls.append((node.func.attr, node))
    return imports, calls


def validate_base_source(raw: bytes) -> None:
    _source, tree = parse_source(raw, BASE_VALIDATOR_PATH)
    imports, calls = source_imports_calls(tree)
    forbidden_imports = {"os", "pathlib", "importlib", "ctypes", "http", "mmap", "requests", "shutil", "socket", "subprocess", "tempfile", "urllib"}
    forbidden_calls = {"open", "eval", "exec", "compile", "input", "system", "popen", "urlopen"}
    require(imports.isdisjoint(forbidden_imports), "base forbidden imports")
    require({name for name, _ in calls}.isdisjoint(forbidden_calls), "base forbidden calls")


def enclosing_function(tree: ast.Module) -> dict[ast.AST, str | None]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    result: dict[ast.AST, str | None] = {}
    for node in ast.walk(tree):
        current = parents.get(node)
        name = None
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = current.name
                break
            current = parents.get(current)
        result[node] = name
    return result


def validate_overlay_source(raw: bytes) -> None:
    source, tree = parse_source(raw, OVERLAY_PATH)
    imports, calls = source_imports_calls(tree)
    require(imports == {"__future__", "builtins", "hashlib", "types"}, f"overlay imports drifted: {sorted(imports)}")
    forbidden_calls = {"open", "eval", "input", "system", "popen", "urlopen"}
    require({name for name, _ in calls}.isdisjoint(forbidden_calls), "overlay forbidden call")
    scopes = enclosing_function(tree)
    for name in ("compile", "exec"):
        matches = [node for call_name, node in calls if call_name == name]
        require(len(matches) == 1 and scopes[matches[0]] == "_load_private_base_validator", f"overlay {name} boundary")
    require("def inspect_module_zip(\n    base_validator_source: bytes,\n    raw_archive: bytes," in source, "overlay base-bytes-first API")
    require("external_attributes >> 8 == 0" in source, "overlay high-bit rejection")
    require("ALLOWED_MS_DOS_FILE_ATTRIBUTES = DOS_READ_ONLY | DOS_ARCHIVE" in source, "overlay DOS mask")
    require("SYNTHETIC_READ_ONLY_REGULAR_MODE = 0o100444" in source, "overlay synthetic mode")


def validate_runner_source(raw: bytes) -> None:
    source, tree = parse_source(raw, RUNNER_PATH)
    imports, calls = source_imports_calls(tree)
    require(imports.isdisjoint({"ctypes", "http", "importlib", "mmap", "requests", "socket", "subprocess", "urllib"}), "runner forbidden imports")
    require({name for name, _ in calls}.isdisjoint({"eval", "input", "system", "popen", "urlopen"}), "runner forbidden calls")
    require("validate_repository" in source and "load_validated_review_modules" in source, "runner checker API")
    require(
        "flags.no_site == 1" in source
        and "python3 -I -B -S" in source
        and "EXPECTED_CHECKER_RAW_SHA256" in source,
        "runner isolation or checker raw authority pin",
    )
    require("review-v2" in source and ".g2-pion-ice-v4.3.0-rung3-offline-review-v2.claim" in source, "runner v2 names")
    require(".g2-pion-ice-v4.3.0-rung3-offline-review-v1.claim" not in source, "runner v1 claim access forbidden")
    module_body = list(tree.body)
    if module_body and isinstance(module_body[0], ast.Expr) and isinstance(module_body[0].value, ast.Constant) and isinstance(module_body[0].value.value, str):
        module_body = module_body[1:]
    require(
        len(module_body) >= 5
        and isinstance(module_body[0], ast.ImportFrom)
        and module_body[0].module == "__future__"
        and isinstance(module_body[1], ast.Import)
        and module_body[1].names[0].name == "sys"
        and isinstance(module_body[2], ast.Assign)
        and isinstance(module_body[3], ast.FunctionDef)
        and module_body[3].name == "require_isolated_interpreter"
        and isinstance(module_body[4], ast.Expr),
        "runner early isolation preamble",
    )
    scopes = enclosing_function(tree)
    for name in ("compile", "exec"):
        matches = [node for call_name, node in calls if call_name == name]
        require(len(matches) == 1 and scopes[matches[0]] == "load_checker_trust_root", f"runner {name} boundary")


OVERLAY_IMPORT_ALLOWLIST = frozenset({"__future__", "builtins", "hashlib", "types"})
OVERLAY_BUILTIN_ALLOWLIST = frozenset(
    {
        "BaseException", "RuntimeError", "UnicodeDecodeError", "__build_class__",
        "bool", "bytes", "callable", "compile", "dict", "exec", "frozenset",
        "getattr", "int", "isinstance", "len", "set", "sorted", "str", "tuple", "type",
    }
)


def _validated_authority_reader(
    root: Path,
) -> tuple[SafeTrackedReader, dict[str, Any], str, str]:
    """Validate only the acyclic execution-authority core."""

    reader = SafeTrackedReader(root, AUTHORITY_READ_ALLOWLIST)
    policy_raw = reader.read(POLICY_PATH)
    policy = strict_json(policy_raw, POLICY_PATH)
    permit_raw = reader.read(PERMIT_PATH)
    permit = strict_json(permit_raw, PERMIT_PATH)
    predecessor = reader.json(PREDECESSOR_MANIFEST_PATH)
    core_raw = reader.read(CORE_MANIFEST_PATH)
    core = strict_json(core_raw, CORE_MANIFEST_PATH)
    all_documents = (policy, permit, predecessor, core)
    placeholders = [item for index, document in enumerate(all_documents) for item in unresolved_placeholders(document, f"document[{index}]")]
    require(not placeholders, f"unresolved placeholders: {placeholders}")
    require(sha256_bytes(policy_raw) == EXPECTED_POLICY_RAW, "policy raw pin")
    require(semantic_sha256(policy) == EXPECTED_POLICY_SEMANTIC, "policy semantic pin")
    validate_predecessor_manifest(predecessor, reader)
    validate_policy(policy)
    validate_permit(permit, permit_raw, reader)
    validate_core_manifest(core, core_raw, reader)
    base_raw = reader.read(BASE_VALIDATOR_PATH)
    overlay_raw = reader.read(OVERLAY_PATH)
    validate_base_source(base_raw)
    validate_overlay_source(overlay_raw)
    return reader, permit, sha256_bytes(permit_raw), semantic_sha256(permit)


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    """Validate exact schemas, bindings, manifests, and source capabilities."""

    _reader, permit, permit_raw, permit_semantic = _validated_authority_reader(root)
    return {
        "permit": permit,
        "permitRawSha256": permit_raw,
        "permitSemanticSha256": permit_semantic,
    }


def load_validated_review_modules(root: Path = ROOT) -> types.ModuleType:
    """Return an adapter retaining exact private base bytes in one closure."""

    reader, _permit, _permit_raw, _permit_semantic = _validated_authority_reader(root)
    base_validator_source = reader.read(BASE_VALIDATOR_PATH)
    overlay_source = reader.read(OVERLAY_PATH)
    require(sha256_bytes(base_validator_source) == EXPECTED_BASE_RAW, "base bytes drifted before adapter load")
    require(sha256_bytes(overlay_source) == EXPECTED_OVERLAY_RAW, "overlay bytes drifted before adapter load")
    original_import = builtins.__import__

    def guarded_import(name, globals_value=None, locals_value=None, fromlist=(), level=0):
        require(level == 0, f"overlay relative import forbidden: {name}")
        require(name in OVERLAY_IMPORT_ALLOWLIST, f"overlay import outside allowlist: {name}")
        return original_import(name, globals_value, locals_value, fromlist, level)

    safe_builtins = {name: getattr(builtins, name) for name in OVERLAY_BUILTIN_ALLOWLIST}
    safe_builtins["__import__"] = guarded_import
    overlay = types.ModuleType("g2_pion_offline_zip_creator_policy_v2_validated")
    overlay.__dict__.update(
        {
            "__builtins__": safe_builtins,
            "__cached__": None,
            "__file__": OVERLAY_PATH,
            "__loader__": None,
            "__package__": None,
        }
    )
    code = compile(overlay_source, OVERLAY_PATH, "exec", flags=0, dont_inherit=True, optimize=0)
    exec(code, overlay.__dict__, overlay.__dict__)
    inspect = getattr(overlay, "inspect_module_zip", None)
    require(callable(inspect), "overlay inspect_module_zip missing")

    def inspect_module_zip(raw_archive: bytes, *, module_prefix: str, limits=None):
        return inspect(
            base_validator_source,
            raw_archive,
            module_prefix=module_prefix,
            limits=limits,
        )

    adapter = types.ModuleType("g2_pion_offline_zip_v2_validated_adapter")
    adapter.inspect_module_zip = inspect_module_zip
    return adapter


def validate_evidence_suite(root: Path = ROOT) -> dict[str, Any]:
    """Validate observational runner/checker evidence outside runtime authority."""

    authority = validate_repository(root)
    reader = SafeTrackedReader(root, TRACKED_READ_ALLOWLIST)
    checker_manifest = reader.json(CHECKER_MANIFEST_PATH)
    require(
        not unresolved_placeholders(checker_manifest, "checkerManifest"),
        "checker manifest contains unresolved placeholders",
    )
    validate_checker_manifest(checker_manifest, reader)
    validate_runner_source(reader.read(RUNNER_PATH))
    return {
        **authority,
        "checkerManifestCollectionSha256": checker_manifest["collectionSha256"],
        "observationalEvidenceValidated": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        result = validate_evidence_suite()
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
                "observationalEvidenceValidated": result["observationalEvidenceValidated"],
                "permitConsumptionState": "not_inspected",
                "reviewedSourceCompilerInvocationCount": 0,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
