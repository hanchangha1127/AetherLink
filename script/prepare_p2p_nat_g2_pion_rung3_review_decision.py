#!/usr/bin/env python3
"""Prepare the deterministic G2 Pion rung-three review-plan decision.

This preparation-only tool is deliberately incapable of reading or writing a
file.  It does not inspect the retained archive and grants no review execution
authority.  ``--check`` is the default; ``--emit-decision`` writes the already
validated decision JSON to stdout only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, Mapping, Sequence


DOCUMENT_TYPE = "aetherlink.g2-pion-rung3-offline-source-review-decision"
SCHEMA_VERSION = "1.0"
DECISION_ID = "g2-pion-ice-v4.3.0-offline-source-review-decision-v1"
RECORDED_DATE = "2026-07-23"
STATUS = "rung3_review_plan_recorded_execution_not_authorized"
RESULT = "retained_archive_metadata_bound_preparation_only"
NEXT_ACTION = "prepare_separate_versioned_rung3_review_execution_permit"

POLICY_BINDING = {
    "path": (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/preparation-sandbox-policy-v1.json"
    ),
    "rawSha256": "c615da9fb80d7af0162077503b55663cf428aaee434cef61a67807c234ea3558",
    "semanticSha256": "bf5de358234c03a5bfc96b66d4fd8b5f0464328f4733820899ce0f93219be64a",
    "bindingSource": "compile_time_constants_only_policy_file_not_read",
}

ARCHIVE_METADATA = {
    "receiptPath": (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-two/source-acquisition-receipt-v1.json"
    ),
    "archiveMetadataJsonPointer": "/archive",
    "archiveEvidenceId": "G2R2E009",
    "archivePathCopiedIntoDecision": False,
    "expectedBytes": 293023,
    "entryCount": 129,
    "fileCount": 129,
    "totalUncompressedBytes": 1131286,
    "rawSha256": "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
    "moduleH1": "h1:X8l4s9zV2HeTKX33nulWAFXAEo5KhIVzOsY62/3t/LM=",
    "goModH1": "h1:obAyD+J+Hzs7QA7Y8YXHp5uIn6gb7z87pKedXZkrcFU=",
    "modulePrefix": "github.com/pion/ice/v4@v4.3.0/",
    "modulePath": "github.com/pion/ice/v4",
    "version": "v4.3.0",
    "tag": "v4.3.0",
    "commitSha1": "1e8716372f2bb52e45bf2a7172e4fb1004251c46",
    "treeSha1": "df59c87a634cfea261582cd9932554663112a975",
    "retained": True,
    "archiveReadByThisDecision": False,
    "archiveMaterializedByThisDecision": False,
    "sourceReviewedByThisDecision": False,
}

PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)

PREDECESSOR_BINDINGS = {
    "restrictedForkProfile": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/restricted-fork-profile.json"
        ),
        "rawSha256": "10e9436ae9b8f24c4447d12f8087b4f121810841ae33526e08fcc3d862d60a0f",
        "semanticSha256": "9c929d186eedb10cc890d5540597724d6df1d719f174ed1965c79e4d50324be6",
        "status": "rung1_profile_complete_candidate_not_selected",
        "implementationStatus": "not_implemented",
        "verificationStatus": "design_validator_passed_runtime_not_executed",
    },
    "sourceAcquisitionReceiptV1": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-two/source-acquisition-receipt-v1.json"
        ),
        "rawSha256": "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6",
    },
    "sourceAcquisitionProgressV2": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-two/source-acquisition-progress-v2.json"
        ),
        "rawSha256": "df1ad52bc6fff294b9bb54fd94a8eaacd76d9ff2b179be4a6752a867d229196f",
    },
    "evidenceManifestV3": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-two/evidence-manifest-v3.json"
        ),
        "rawSha256": "8ed1a2667153f77270531d7c373f5f61ed9eb9080bceab7c804c9b686259537e",
        "semanticSha256": "61bfeb7f12bdbea38c73d7a1581f5ceada31bfc9b0ef64ee25e97f8c5c8d2221",
        "collectionSha256": "0e5e41990ed8b46dd40dba9808f29f40e007142ed0ae77408d4d8afa6f4142a0",
    },
    "canonicalDocumentSupersessionV2": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-two/canonical-document-supersession-v2.json"
        ),
        "rawSha256": "3a2b74ecde45b69204b9687904a4f88d731dfc532046e472ec22a4873765309a",
        "semanticSha256": "1c1245ceb52e0f2b90fcd89934b02fedaf3985466b4e4b53d9c1821d85921932",
    },
    "canonicalEvidenceManifestV5": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-two/evidence-manifest-v5.json"
        ),
        "rawSha256": "203e88cf73ad358fd6c73d8bb8d988efa966ffa67573d6e7dda9c03a2fe01f89",
        "semanticSha256": "fd738ae8de9909adf6d9dd915d4d861998c06bde97b10cb9e87c4cc9adea9d80",
        "collectionSha256": "adb1fbce766b0750e186285024156abea290d80763eea142420192aa8261d0a8",
    },
}

FORWARD_ONLY_BINDINGS = {
    "progress": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-three/offline-source-review-progress-v1.json"
        ),
        "progressId": "g2-pion-ice-v4.3.0-offline-source-review-progress-v1",
        "binding": "forward_identity_only_no_sha256",
    },
    "manifest": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-three/evidence-manifest-v1.json"
        ),
        "manifestId": "g2-pion-ice-v4.3.0-rung3-decision-evidence-manifest-v1",
        "binding": "forward_identity_only_no_sha256",
    },
}

PROFILE_RUNG3_VERIFICATION_IDS = (
    "g2-r3-egress-path-coverage",
    "g2-r3-ingress-path-coverage",
    "g2-r3-address-and-resolution-adversarial",
    "g2-r3-turn-tls-service-identity",
    "g2-r3-secure-session-promotion",
    "g2-r3-resource-and-event-bounds",
    "g2-r3-secret-free-diagnostics",
    "g2-r3-deadline-shutdown",
)

REVIEW_TOPICS = (
    "regular_file_inventory_with_size_and_sha256",
    "go_lexical_and_ast_like_token_scan_without_execution",
    "go_mod_and_go_sum_dependency_metadata_parsing",
    "license_and_notice_inventory_without_legal_conclusion",
    "egress_path_candidate_mapping",
    "ingress_path_candidate_mapping",
    "secret_free_logging_candidate_mapping",
    "concurrency_resource_and_event_bound_candidate_mapping",
    "deadline_close_and_revocation_candidate_mapping",
    "seven_patch_unit_coverage_mapping",
)

ARCHIVE_REJECTION_RULES = (
    "exact_raw_size_or_sha256_mismatch",
    "prefix_path_or_entry_count_drift",
    "path_traversal_absolute_backslash_control_or_non_nfc_name",
    "exact_name_nfc_casefold_or_file_directory_collision",
    "symlink_hardlink_special_nonregular_or_executable_entry",
    "encrypted_zip64_multidisk_comment_trailing_hidden_or_duplicate_data",
    "local_central_header_flag_method_name_crc_or_size_mismatch",
    "single_file_total_uncompressed_or_compression_ratio_limit_exceeded",
)

REVIEW_LIMITS = {
    "maximumArchiveBytes": 524288,
    "maximumEntries": 4096,
    "maximumCentralDirectoryBytes": 4194304,
    "maximumPathBytes": 1024,
    "maximumPathComponents": 32,
    "maximumComponentBytes": 255,
    "maximumSingleFileBytes": 4194304,
    "maximumTotalUncompressedBytes": 67108864,
    "maximumTextFileBytes": 2097152,
    "maximumCompressionRatio": 200,
    "maximumRecordedHitsPerPatchUnit": 512,
    "maximumJsonReportBytes": 2097152,
}

FALSE_BOUNDARY_KEYS = (
    "filesystemRead",
    "filesystemWrite",
    "archiveOpened",
    "archiveRead",
    "archiveExtracted",
    "archiveMaterialized",
    "sourceReviewed",
    "sourceExecuted",
    "sourcePatched",
    "sourceFileWritten",
    "dependencyInstalled",
    "packageManagerInvoked",
    "compilerInvoked",
    "codeLoaded",
    "subprocessInvoked",
    "shellInvoked",
    "socketCreated",
    "networkUsed",
    "dnsUsed",
    "gitOperationPerformed",
    "librarySelected",
    "reviewExecutionAuthorized",
    "compileAuthorized",
    "runtimeNetworkAuthorized",
    "deviceExecutionAuthorized",
    "productionDeploymentAuthorized",
    "repositoryOwnerAuthenticationRequired",
    "externalIdentityProofRequired",
    "userActionRequired",
)


class DecisionValidationError(ValueError):
    """The deterministic preparation payload violated its closed schema."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole canonical JSON encoding used by this tool."""

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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _decision_core() -> dict[str, Any]:
    return {
        "documentType": DOCUMENT_TYPE,
        "schemaVersion": SCHEMA_VERSION,
        "decisionId": DECISION_ID,
        "recordedDate": RECORDED_DATE,
        "status": STATUS,
        "result": RESULT,
        "nextAction": NEXT_ACTION,
        "policyBinding": dict(POLICY_BINDING),
        "predecessorBindings": {
            key: dict(value) for key, value in PREDECESSOR_BINDINGS.items()
        },
        "forwardOnlyBindings": {
            key: dict(value) for key, value in FORWARD_ONLY_BINDINGS.items()
        },
        "archiveBinding": dict(ARCHIVE_METADATA),
        "preparationScope": {
            "kind": "metadata_only_review_plan",
            "sourceOfValues": "compile_time_constants_only",
            "evidenceBasis": "static_contract_and_mock_isolation_tests_not_os_sandbox_attestation",
            "repositoryFilesRead": 0,
            "repositoryFilesWritten": 0,
            "archiveBytesRead": 0,
            "stdoutIsOnlyEmissionSurface": True,
        },
        "futureExecutionPermitRequirements": {
            "separateVersionedPermitRequired": True,
            "exactArchiveIdentityMustBeRevalidatedFromOneNoFollowFileDescriptor": True,
            "ownerOnlyTemporaryAndReportStorageRequired": True,
            "exclusiveClaimAndAtomicNoReplacePublicationRequired": True,
            "deterministicBoundedJsonReportsOnly": True,
            "archiveRejectionRules": list(ARCHIVE_REJECTION_RULES),
            "resourceLimits": dict(REVIEW_LIMITS),
        },
        "plannedStaticReview": {
            "reviewTopics": list(REVIEW_TOPICS),
            "patchUnits": list(PATCH_UNITS),
            "profileVerificationUnits": [
                {"id": unit_id, "status": "planned_not_performed"}
                for unit_id in PROFILE_RUNG3_VERIFICATION_IDS
            ],
            "coverageMeaning": "candidate_locations_only_not_proof_of_coverage_or_closure",
            "goScanMeaning": "lexical_and_ast_like_inventory_not_type_control_or_data_flow_proof",
            "licenseMeaning": "inventory_only_not_legal_conclusion",
        },
        "futureExecutionProhibitions": {
            "networkSocketOrDns": True,
            "subprocessOrShell": True,
            "gitPackageManagerOrCompiler": True,
            "sourceExecutionOrPatchWrite": True,
            "unboundedOrNonJsonOutput": True,
        },
        "decisionBoundary": {key: False for key in FALSE_BOUNDARY_KEYS},
        "personalProjectBoundary": {
            "technicalSafetyGatesRemainRequired": True,
            "repositoryOwnerAuthenticationIsNotATechnicalGate": True,
            "noAuthenticationOrUserActionRequested": True,
        },
    }


def build_decision() -> dict[str, Any]:
    """Build a fresh deterministic decision without any external observation."""

    core = _decision_core()
    core_bytes = canonical_json_bytes(core)
    decision = dict(core)
    decision["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256_bytes(core_bytes),
    }
    return decision


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionValidationError(message)


def _require_exact(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise DecisionValidationError(f"{label} differs from the closed decision template")


def validate_decision(value: Any) -> dict[str, Any]:
    """Strictly validate exact keys, values, ordering, limits, and core digest."""

    _require(type(value) is dict, "decision must be an object")
    expected = build_decision()
    _require_exact(set(value), set(expected), "top-level keys")
    for key in expected:
        _require_exact(value[key], expected[key], key)

    _require(len(value["plannedStaticReview"]["patchUnits"]) == 7, "exactly seven patch units required")
    _require(
        len(set(value["plannedStaticReview"]["patchUnits"])) == 7,
        "patch units must be unique",
    )
    _require(
        all(type(item) is str and item for item in value["plannedStaticReview"]["reviewTopics"]),
        "review topics must be nonempty strings",
    )
    _require(
        [item["id"] for item in value["plannedStaticReview"]["profileVerificationUnits"]]
        == list(PROFILE_RUNG3_VERIFICATION_IDS),
        "all eight profile rung-three verification units are required in exact order",
    )
    for key, item in value["decisionBoundary"].items():
        _require(type(item) is bool and item is False, f"decisionBoundary.{key} must be false")
    for key, item in value["futureExecutionProhibitions"].items():
        _require(type(item) is bool and item is True, f"futureExecutionProhibitions.{key} must be true")
    for key, item in value["futureExecutionPermitRequirements"]["resourceLimits"].items():
        _require(type(item) is int and item > 0, f"resource limit {key} must be a positive integer")

    binding = value["contentBinding"]
    _require(
        re.fullmatch(r"[0-9a-f]{64}", binding["sha256"]) is not None,
        "content binding must be lowercase SHA-256",
    )
    core = {key: item for key, item in value.items() if key != "contentBinding"}
    _require_exact(
        binding["sha256"],
        sha256_bytes(canonical_json_bytes(core)),
        "content binding digest",
    )
    _require(
        len(canonical_json_bytes(value)) <= 65536,
        "preparation decision exceeds its fixed 64 KiB ceiling",
    )
    return value


def _check_result(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.g2-pion-rung3-review-decision-preparation-check",
        "schemaVersion": SCHEMA_VERSION,
        "status": "passed",
        "decisionId": decision["decisionId"],
        "decisionStatus": decision["status"],
        "decisionCanonicalSha256": sha256_bytes(canonical_json_bytes(decision)),
        "archiveRead": False,
        "filesystemRead": False,
        "filesystemWrite": False,
        "networkOrDnsUsed": False,
        "subprocessUsed": False,
        "gitOperationPerformed": False,
        "compilerInvoked": False,
        "repositoryOwnerAuthenticationRequired": False,
        "externalIdentityProofRequired": False,
        "productEndpointAuthenticationRequired": True,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--emit-decision", action="store_true")
    args = parser.parse_args(argv)
    try:
        decision = validate_decision(build_decision())
        output = decision if args.emit_decision else _check_result(decision)
        sys.stdout.write(canonical_json_bytes(output).decode("ascii"))
        return 0
    except (DecisionValidationError, TypeError, ValueError) as error:
        failure = {
            "documentType": "aetherlink.g2-pion-rung3-review-decision-preparation-check",
            "schemaVersion": SCHEMA_VERSION,
            "status": "failed_closed",
            "reason": str(error),
            "repositoryOwnerAuthenticationRequired": False,
            "externalIdentityProofRequired": False,
            "productEndpointAuthenticationRequired": True,
            "userActionRequired": False,
        }
        sys.stdout.write(canonical_json_bytes(failure).decode("ascii"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
