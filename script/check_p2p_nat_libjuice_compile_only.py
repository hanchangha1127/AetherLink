#!/usr/bin/env python3
"""Validate the blocked Phase A libjuice compile-only C ABI contract."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_JSON_PATH = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/"
    "phase-a/libjuice-compile-only-contract-v1.json"
)
ARTIFACT_MARKDOWN_PATH = ARTIFACT_JSON_PATH.with_suffix(".md")
SOURCE_REVIEW_PATH = ARTIFACT_JSON_PATH.parents[1] / "review-v1.json"
SOURCE_DECISION_PATH = ARTIFACT_JSON_PATH.parents[1] / "decision-v1.json"
SOURCE_HANDOFF_PATH = ARTIFACT_JSON_PATH.parents[2] / "implementation/handoff-v4.json"
OFFLINE_INTAKE_PATH = ARTIFACT_JSON_PATH.parent / "offline-source-intake-v1.json"
CHECKER_PATH = ROOT / "script/check_p2p_nat_libjuice_compile_only.py"
TEST_PATH = ROOT / "script/test_p2p_nat_libjuice_compile_only.py"

SOURCE_SHA256 = {
    SOURCE_REVIEW_PATH: "744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62",
    SOURCE_DECISION_PATH: "1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228",
    SOURCE_HANDOFF_PATH: "b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd",
    OFFLINE_INTAKE_PATH: "3359624f1fa1474b2bfd2acd4e3591fd1e0a8cd5840cda4372327f25dfc68850",
}
ARTIFACT_SHA256 = {
    ARTIFACT_JSON_PATH: "2664736c7b783d650eabcd8bc4ad5391babd456d3b7df596dff2171eba7d84b4",
    ARTIFACT_MARKDOWN_PATH: "6e181de962f961ccf1b35f020e83e2cceb3829e13bf824c7fa68f17677d09420",
}

TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "contractId", "profileId", "sourceReview",
    "sourceDecision", "sourceHandoff", "offlineSourceIntake", "currentStatus",
    "authorization", "reviewedSourceManifestPrerequisite", "futureCompilationContract",
    "platformMatrix", "abiBoundary", "outputPolicy", "prohibitedRepositoryArtifacts",
    "transitionPolicy", "immutability",
}

EXPECTED_CURRENT_STATUS = {
    "android_macos_compile_only_integration": "blocked_missing_reviewed_source",
    "executionStatus": "not_executed",
    "evidenceStatus": "absent",
    "compilationEvidence": [],
    "recordedEnvironmentSnapshot": {
        "recordedAt": "2026-07-13",
        "scope": "creation_time_filesystem_observation_not_revalidated_by_static_contract_checker",
        "libjuiceSourcePresent": False,
        "libjuiceHeaderPresent": False,
        "nativeBuildIntegrationPresent": False,
        "androidNdkInstalled": False,
        "androidCmakeInstalled": False,
        "appleClangPresent": True,
        "compilationEvidencePresent": False,
    },
}

EXPECTED_AUTHORIZATION = {
    "contractDefinitionAuthorized": True,
    "compileOnlyIntegrationAuthorizedByApprovalChain": True,
    "currentCompilerInvocationAuthorized": False,
    "currentArchiveInvocationAuthorized": False,
    "sourceAcquisitionNetworkIOAllowed": False,
    "sourceExecutionAllowed": False,
    "configureExecutionAllowed": False,
    "testExecutableBuildAllowed": False,
    "testExecutionAllowed": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIOAllowed": False,
    "dnsAllowed": False,
    "proxyAllowed": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
}

EXPECTED_MANIFEST_KEYS = [
    "upstreamRepositoryIdentity", "releaseTag", "commitSha", "archiveSha256",
    "sourceTreeSha256", "licenseFilePathsAndSha256", "orderedSourceFilesAndSha256",
    "orderedPublicHeadersAndSha256", "orderedPrivateHeadersAndSha256",
    "generatedFilesAndSha256", "transitiveDependencyClosure", "exactBuildDefines",
    "exactIncludeDirectories", "exactCompilerFlags", "exactSymbolExportAllowlist",
    "androidNdkVersionAndPackageSha256", "androidToolPathsAndSha256",
    "macosClangSdkToolPathsAndSha256",
]

EXPECTED_SOURCE_PREREQUISITE = {
    "required": True,
    "currentStatus": "absent",
    "approvalRequiredBeforeCompilation": True,
    "manifestMustPinExactKeys": EXPECTED_MANIFEST_KEYS,
    "sourceDiscovery": "ordered_manifest_entries_only",
    "globDiscoveryAllowed": False,
    "directoryScanDiscoveryAllowed": False,
    "implicitSourceFilesAllowed": False,
    "implicitBuildDefinesAllowed": False,
    "manifestHashRequired": True,
    "independentReviewRequired": True,
    "failureRule": "remain_blocked_missing_reviewed_source",
}

EXPECTED_FUTURE_COMPILATION = {
    "activationRule": (
        "new_versioned_contract_after_completed_intake_and_reviewed_exact_source_manifest_hash_pins"
    ),
    "strategy": "direct_compile_each_exact_source_then_static_archive",
    "compileMode": "compile_only_c11",
    "compileInvocation": "one_direct_compiler_dash_c_invocation_per_ordered_manifest_source",
    "archiveInvocation": "one_static_archive_created_from_the_exact_ordered_object_list",
    "symbolInspection": "nm_over_static_archive_without_loading_or_executing_code",
    "configureAllowed": False,
    "cmakeExecutionAllowed": False,
    "gradleNativeBuildWiringAllowed": False,
    "swiftPackageManagerWiringAllowed": False,
    "testExecutableLinkAllowed": False,
    "sourceExecutionAllowed": False,
    "ctestAllowed": False,
    "nativeTestsAllowed": False,
    "smokeExecutionAllowed": False,
    "socketCreationAllowed": False,
    "networkIOAllowed": False,
    "dnsAllowed": False,
    "proxyAllowed": False,
    "environmentProxyAllowed": False,
    "urlFetchAllowed": False,
    "redirectAllowed": False,
    "sourceOrder": "exact_reviewed_manifest_order",
    "buildDefines": "exact_reviewed_manifest_values_only",
    "failureRule": "fail_closed_without_fallback_download_configure_link_or_execution",
}

EXPECTED_ANDROID = {
    "minimumSdk": 26,
    "proofMode": "compile_objects_archive_and_nm_only",
    "abis": [
        {"abi": "arm64-v8a", "targetTriple": "aarch64-linux-android26"},
        {"abi": "x86_64", "targetTriple": "x86_64-linux-android26"},
    ],
    "requiredExactPins": [
        "ndkVersion", "ndkPackageSha256", "clangPath", "clangSha256", "llvmArPath",
        "llvmArSha256", "llvmNmPath", "llvmNmSha256", "sysrootPath", "sysrootDigest",
        "orderedSourceFilesAndSha256", "orderedObjectFiles", "exactBuildDefines",
        "exactIncludeDirectories", "exactCompilerFlags",
    ],
    "sameCAbiRequiredAcrossAbis": True,
}

EXPECTED_MACOS = {
    "minimumDeploymentTarget": "14.0",
    "proofMode": "compile_objects_archive_and_nm_only",
    "architectures": [
        {"architecture": "arm64", "target": "arm64-apple-macos14.0"},
        {"architecture": "x86_64", "target": "x86_64-apple-macos14.0"},
    ],
    "requiredExactPins": [
        "appleClangVersion", "clangPath", "clangSha256", "arPath", "arSha256", "nmPath",
        "nmSha256", "sdkVersion", "sdkPath", "sdkDigest", "orderedSourceFilesAndSha256",
        "orderedObjectFiles", "exactBuildDefines", "exactIncludeDirectories",
        "exactCompilerFlags",
    ],
    "sameCAbiRequiredAcrossArchitectures": True,
}

EXPECTED_EXPORTS = [
    "aetherlink_juice_abi_version",
    "aetherlink_juice_context_create",
    "aetherlink_juice_context_cancel",
    "aetherlink_juice_context_destroy",
    "aetherlink_juice_agent_create",
    "aetherlink_juice_agent_set_numeric_endpoint",
    "aetherlink_juice_agent_cancel",
    "aetherlink_juice_agent_destroy",
    "aetherlink_juice_buffer_release",
    "aetherlink_juice_error_string",
]

EXPECTED_ABI = {
    "language": "c11",
    "opaqueHandleRule": "public_header_exposes_only_incomplete_struct_pointer_handles",
    "fixedWidthIntegerRule": "cross_boundary_integer_fields_use_stdint_fixed_width_types_only",
    "bufferRule": (
        "every_buffer_is_pointer_plus_explicit_size_t_length_with_no_sentinel_or_implicit_length"
    ),
    "numericEndpointRule": (
        "endpoint_input_is_numeric_address_family_packed_address_bytes_and_uint16_port_only_"
        "no_hostname_url_or_route_token"
    ),
    "allocatorOwnershipRule": (
        "creator_owned_handles_have_explicit_destroy_and_each_buffer_has_one_documented_allocator_"
        "and_release_owner"
    ),
    "callbackThreadingRule": (
        "callbacks_identify_the_single_documented_callback_thread_and_must_not_reenter_destroy_or_"
        "transfer_ownership"
    ),
    "cancellationRule": (
        "cancel_is_idempotent_nonblocking_and_followed_by_bounded_teardown_before_destroy_returns"
    ),
    "teardownRule": (
        "destroy_unregisters_callbacks_releases_owned_memory_and_permits_no_callback_after_return"
    ),
    "errorRule": (
        "errors_are_int32_t_numeric_codes_in_the_closed_range_0_through_255_with_unknown_mapped_to_255"
    ),
    "symbolVisibilityRule": (
        "compile_with_hidden_visibility_by_default_and_export_only_the_exact_allowlist"
    ),
    "exactExportAllowlist": EXPECTED_EXPORTS,
    "routeTokenAuthorityAllowed": False,
    "applicationPayloadAuthorityAllowed": False,
    "routeTokenBoundaryRule": "routeToken_must_not_cross_or_configure_the_c_abi_boundary",
    "applicationPayloadBoundaryRule": (
        "the_adapter_must_not_accept_interpret_authorize_encrypt_decrypt_or_emit_application_payload"
    ),
}

EXPECTED_ALLOWED_OUTPUTS = [
    "object_file", "static_archive", "nm_symbol_report",
    "content_free_command_tool_source_digest_log",
]
EXPECTED_LOG_KEYS = [
    "targetId", "stepId", "commandTemplateSha256", "toolSha256", "sourceManifestSha256",
    "sourceFileSha256", "objectFileSha256", "archiveSha256", "symbolReportSha256",
    "exitCode", "diagnosticDigest",
]

EXPECTED_OUTPUT_POLICY = {
    "allowedArtifactClasses": EXPECTED_ALLOWED_OUTPUTS,
    "contentFreeLogExactKeys": EXPECTED_LOG_KEYS,
    "rawCommandLineRetentionAllowed": False,
    "environmentRetentionAllowed": False,
    "sourceContentRetentionAllowed": False,
    "applicationContentRetentionAllowed": False,
    "packetContentRetentionAllowed": False,
    "executableArtifactAllowed": False,
    "sharedLibraryArtifactAllowed": False,
    "testArtifactAllowed": False,
    "runtimeLogAllowed": False,
    "maximumExitCode": 255,
    "digestFormat": "sha256_lowercase_hex",
}

EXPECTED_PROHIBITED_ARTIFACTS = [
    "fabricated_juice_header", "fabricated_c_adapter_header", "fabricated_c_adapter_source",
    "cmake_wiring", "gradle_native_wiring", "swiftpm_wiring", "test_executable",
    "runtime_smoke_harness",
]

EXPECTED_TRANSITION = {
    "blockedStateExitRequires": [
        "completed_offline_source_intake_with_exact_hash_pin",
        "independently_reviewed_exact_source_manifest_with_exact_hash_pin",
        "new_versioned_compile_only_contract",
        "all_four_platform_targets_have_exact_tool_and_source_pins",
    ],
    "inPlaceStatusMutationAllowed": False,
    "fallbackDownloadAllowed": False,
    "fallbackLibrarySelectionAllowed": False,
    "nextStateOnAnyMissingPin": "blocked_missing_reviewed_source",
    "phaseBUnlockAllowed": False,
    "productionUnlockAllowed": False,
}

REVIEW_AUTHORIZATION = {
    "librarySelectionAuthorized": False,
    "harnessImplementationAuthorized": False,
    "networkIOAllowed": False,
    "socketExecutionAuthorized": False,
    "productionDeploymentAuthorized": False,
    "nextHandoffAuthorized": False,
}
DECISION_AUTHORIZATION = {
    "conditionalLibrarySelectionAuthorized": True,
    "offlineSourceInspectionAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "compileOnlyIntegrationAuthorized": True,
    "phaseAHarnessImplementationAuthorized": True,
    "controlledSpikeNetworkIOAllowed": False,
    "controlledSpikeSocketExecutionAuthorized": False,
    "phaseBExecutionAuthorized": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
    "handoffV4CreationAuthorized": True,
}
HANDOFF_AUTHORIZATION = {
    "implementationAuthorized": True,
    "conditionalLibrarySelectionAuthorized": True,
    "offlineSourceInspectionAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "compileOnlyIntegrationAuthorized": True,
    "phaseAHarnessImplementationAuthorized": True,
    "controlledSpikeNetworkIOAllowed": False,
    "controlledSpikeSocketExecutionAuthorized": False,
    "phaseBExecutionAuthorized": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
}

ALLOWED_IMPORTS = {"ast", "copy", "hashlib", "json", "sys", "unittest"}
ALLOWED_FROM_IMPORTS = {
    "__future__": {"annotations"},
    "pathlib": {"Path"},
    "typing": {"Any"},
    "script": {"check_p2p_nat_libjuice_compile_only"},
}
FORBIDDEN_DYNAMIC_NAMES = {
    "__builtins__", "__import__", "eval", "exec", "compile", "getattr", "setattr",
    "globals", "locals", "vars", "open",
}
FORBIDDEN_BARE_CALL_NAMES = {
    "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp", "Popen", "run",
    "call", "check_call", "check_output", "urlopen", "HTTPConnection", "HTTPSConnection",
    "create_connection", "socket", "CDLL", "PyDLL", "import_module", "unpack_archive",
    "make_archive", "extract", "extractall", "write_text", "write_bytes", "mkdir",
    "touch", "unlink", "rename", "replace", "chmod", "symlink_to", "hardlink_to",
    "link_to", "open", "rmdir", "rmtree", "execl", "execle", "execlp",
    "execlpe", "execv", "execve", "execvp", "execvpe", "fork_exec",
}
FORBIDDEN_QUALIFIED_REFERENCES = {"sys.modules"}


class LibjuiceCompileOnlyValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise LibjuiceCompileOnlyValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object contains duplicate name {key!r}")
        result[key] = value
    return result


def reject_nonstandard_number(value: str) -> None:
    fail(f"JSON contains non-standard number {value!r}")


def parse_json(raw: str, label: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=reject_duplicate_names,
            parse_constant=reject_nonstandard_number,
        )
    except json.JSONDecodeError as error:
        fail(f"{label}: invalid JSON: {error}")


def load_json(path: Path) -> Any:
    try:
        return parse_json(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
    except (OSError, UnicodeError) as error:
        fail(f"{path.relative_to(ROOT)}: {error}")


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label}: expected object, got {type(value).__name__}")
    actual = set(value)
    if actual != expected:
        fail(
            f"{label}: keys differ; missing={sorted(expected - actual)} "
            f"unknown={sorted(actual - expected)}"
        )
    return value


def recursive_exact(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected):
        fail(f"{label}: expected exact type {type(expected).__name__}, got {type(actual).__name__}")
    if isinstance(expected, dict):
        exact_keys(actual, set(expected), label)
        for key, expected_value in expected.items():
            recursive_exact(actual[key], expected_value, f"{label}.{key}")
        return
    if isinstance(expected, list):
        if len(actual) != len(expected):
            fail(f"{label}: expected exactly {len(expected)} entries, got {len(actual)}")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            recursive_exact(actual_item, expected_item, f"{label}[{index}]")
        return
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_bytes_hash(raw: bytes, expected: str, label: str) -> None:
    actual = hash_bytes(raw)
    if actual != expected:
        fail(f"{label}: SHA-256 drifted; expected {expected}, got {actual}")


def validate_file_hash(path: Path, expected: str) -> None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        fail(f"{path.relative_to(ROOT)}: {error}")
    validate_bytes_hash(raw, expected, str(path.relative_to(ROOT)))


def validate_source_documents() -> None:
    for path, digest in SOURCE_SHA256.items():
        validate_file_hash(path, digest)

    review = load_json(SOURCE_REVIEW_PATH)
    recursive_exact(
        review.get("reviewId"),
        "production_p2p_nat_v1_controlled_network_spike_review_v1",
        "review.reviewId",
    )
    recursive_exact(review.get("authorization"), REVIEW_AUTHORIZATION, "review.authorization")

    decision = load_json(SOURCE_DECISION_PATH)
    recursive_exact(
        decision.get("decisionId"),
        "production_p2p_nat_v1_controlled_network_spike_decision_v1",
        "decision.decisionId",
    )
    recursive_exact(
        decision.get("sourceReviewId"),
        "production_p2p_nat_v1_controlled_network_spike_review_v1",
        "decision.sourceReviewId",
    )
    recursive_exact(
        decision.get("decisionScope"),
        "bounded_phase_a_evidence_authorization",
        "decision.decisionScope",
    )
    recursive_exact(decision.get("authorization"), DECISION_AUTHORIZATION, "decision.authorization")
    approvals = decision.get("approvals")
    if not isinstance(approvals, list):
        fail("decision.approvals: expected list")
    networking = [
        item for item in approvals
        if isinstance(item, dict) and item.get("decisionId") == "networking_library_selection"
    ]
    if len(networking) != 1:
        fail("decision.approvals: expected exactly one networking library approval")
    recursive_exact(
        networking[0],
        {
            "decisionId": "networking_library_selection",
            "status": "approved_for_bounded_phase_a_evidence",
            "recommendedOptionId": "libjuice-1.7.2-static-c-abi",
            "resolution": "libjuice-1.7.2-static-c-abi",
            "approvalSource": "explicit_user_instruction",
        },
        "decision.networkingApproval",
    )

    handoff = load_json(SOURCE_HANDOFF_PATH)
    recursive_exact(
        handoff.get("handoffId"), "production_p2p_nat_v1_handoff_v4", "handoff.handoffId"
    )
    recursive_exact(handoff.get("authorization"), HANDOFF_AUTHORIZATION, "handoff.authorization")
    packages = handoff.get("packages")
    if not isinstance(packages, list):
        fail("handoff.packages: expected list")
    controlled = [
        item for item in packages
        if isinstance(item, dict) and item.get("packageId") == "controlled-network-spike"
    ]
    if len(controlled) != 1:
        fail("handoff.packages: expected exactly one controlled-network-spike package")
    phase_a = controlled[0].get("phaseA")
    if not isinstance(phase_a, dict):
        fail("handoff.controlled.phaseA: expected object")
    for key, expected in {
        "sourceMaterialMode": "offline_user_provided_or_preexisting_workspace_only",
        "offlineSourceInspectionAuthorized": True,
        "sourceAcquisitionNetworkIOAllowed": False,
        "compileOnlyIntegrationAuthorized": True,
        "sourceExecutionAllowed": False,
        "socketCreationAllowed": False,
        "runtimeNetworkIOAllowed": False,
        "harnessNetworkIOAllowed": False,
    }.items():
        recursive_exact(phase_a.get(key), expected, f"handoff.controlled.phaseA.{key}")

    intake = load_json(OFFLINE_INTAKE_PATH)
    for key, expected in {
        "documentType": "aetherlink.p2p-nat-phase-a-offline-source-intake",
        "schemaVersion": "1.0",
        "artifactId": "production_p2p_nat_v1_phase_a_libjuice_offline_source_intake_v1",
        "profileId": "production_p2p_nat_v1_recommended",
        "artifactStatus": "blocked_missing_offline_source",
        "sourcePresence": "absent",
        "auditStatus": "not_started",
        "compileStatus": "not_started",
    }.items():
        recursive_exact(intake.get(key), expected, f"offlineSourceIntake.{key}")
    intake_authorization = intake.get("authorization")
    if not isinstance(intake_authorization, dict):
        fail("offlineSourceIntake.authorization: expected object")
    for key, expected in {
        "sourceAcquisitionNetworkIOAllowed": False,
        "urlFetchAllowed": False,
        "redirectFollowingAllowed": False,
        "packageManagerAcquisitionAllowed": False,
        "sourceExecutionAllowed": False,
        "buildExecutionAllowedBeforeReviewedManifest": False,
        "compileExecutionAllowedBeforeReviewedManifest": False,
        "processLaunchAllowed": False,
        "socketCreationAllowed": False,
        "runtimeNetworkIOAllowed": False,
        "dynamicImportAllowed": False,
    }.items():
        recursive_exact(
            intake_authorization.get(key), expected, f"offlineSourceIntake.authorization.{key}"
        )


def canonical_document() -> Any:
    return load_json(ARTIFACT_JSON_PATH)


def validate_document(document: Any) -> None:
    root = exact_keys(document, TOP_LEVEL_KEYS, "artifact")
    recursive_exact(root, canonical_document(), "artifact.canonical")
    recursive_exact(
        root["documentType"],
        "aetherlink.p2p-nat-libjuice-compile-only-contract",
        "artifact.documentType",
    )
    recursive_exact(root["schemaVersion"], "1.0", "artifact.schemaVersion")
    recursive_exact(
        root["contractId"],
        "production_p2p_nat_v1_libjuice_compile_only_contract_v1",
        "artifact.contractId",
    )
    recursive_exact(root["profileId"], "production_p2p_nat_v1_recommended", "artifact.profileId")
    recursive_exact(root["sourceReview"], {
        "path": "../review-v1.json",
        "reviewId": "production_p2p_nat_v1_controlled_network_spike_review_v1",
        "sha256": SOURCE_SHA256[SOURCE_REVIEW_PATH],
    }, "artifact.sourceReview")
    recursive_exact(root["sourceDecision"], {
        "path": "../decision-v1.json",
        "decisionId": "production_p2p_nat_v1_controlled_network_spike_decision_v1",
        "sha256": SOURCE_SHA256[SOURCE_DECISION_PATH],
    }, "artifact.sourceDecision")
    recursive_exact(root["sourceHandoff"], {
        "path": "../../implementation/handoff-v4.json",
        "handoffId": "production_p2p_nat_v1_handoff_v4",
        "sha256": SOURCE_SHA256[SOURCE_HANDOFF_PATH],
    }, "artifact.sourceHandoff")
    recursive_exact(root["offlineSourceIntake"], {
        "path": "offline-source-intake-v1.json",
        "artifactId": "production_p2p_nat_v1_phase_a_libjuice_offline_source_intake_v1",
        "sha256": SOURCE_SHA256[OFFLINE_INTAKE_PATH],
        "requiredBeforeReviewedManifest": True,
        "currentDeclaredStatus": "blocked_missing_offline_source",
        "sourcePresence": "absent",
        "auditStatus": "not_started",
        "compileStatus": "not_started",
        "linkedArtifactPresent": True,
        "linkageRule": (
            "this_hash_pins_only_the_canonical_blocked_intake_supersede_with_a_new_version_that_pins_"
            "the_completed_reviewed_intake_before_any_compile_invocation"
        ),
    }, "artifact.offlineSourceIntake")
    recursive_exact(root["currentStatus"], EXPECTED_CURRENT_STATUS, "artifact.currentStatus")
    recursive_exact(root["authorization"], EXPECTED_AUTHORIZATION, "artifact.authorization")
    recursive_exact(
        root["reviewedSourceManifestPrerequisite"],
        EXPECTED_SOURCE_PREREQUISITE,
        "artifact.reviewedSourceManifestPrerequisite",
    )
    recursive_exact(
        root["futureCompilationContract"],
        EXPECTED_FUTURE_COMPILATION,
        "artifact.futureCompilationContract",
    )
    exact_keys(root["platformMatrix"], {"android", "macos", "crossPlatformRule"}, "artifact.platformMatrix")
    recursive_exact(root["platformMatrix"]["android"], EXPECTED_ANDROID, "artifact.platformMatrix.android")
    recursive_exact(root["platformMatrix"]["macos"], EXPECTED_MACOS, "artifact.platformMatrix.macos")
    recursive_exact(
        root["platformMatrix"]["crossPlatformRule"],
        "one_identical_versioned_c_abi_and_export_allowlist_for_all_four_targets",
        "artifact.platformMatrix.crossPlatformRule",
    )
    recursive_exact(root["abiBoundary"], EXPECTED_ABI, "artifact.abiBoundary")
    recursive_exact(root["outputPolicy"], EXPECTED_OUTPUT_POLICY, "artifact.outputPolicy")
    recursive_exact(
        root["prohibitedRepositoryArtifacts"],
        EXPECTED_PROHIBITED_ARTIFACTS,
        "artifact.prohibitedRepositoryArtifacts",
    )
    recursive_exact(root["transitionPolicy"], EXPECTED_TRANSITION, "artifact.transitionPolicy")
    recursive_exact(root["immutability"], {
        "recordState": "closed",
        "artifactHashAuthority": "script/check_p2p_nat_libjuice_compile_only.py",
        "hashAlgorithm": "sha256",
        "coveredArtifacts": [
            "libjuice-compile-only-contract-v1.json",
            "libjuice-compile-only-contract-v1.md",
        ],
        "amendmentPolicy": "supersede_with_new_versioned_contract_after_reviewed_source_manifest",
    }, "artifact.immutability")


def qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def validate_ast_source(raw: str, label: str) -> None:
    try:
        tree = ast.parse(raw, filename=label)
    except SyntaxError as error:
        fail(f"{label}: invalid Python syntax: {error}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    fail(f"{label}:{node.lineno}: import outside static allowlist {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            allowed_names = ALLOWED_FROM_IMPORTS.get(module, set())
            if not allowed_names or any(
                alias.name == "*" or alias.name not in allowed_names for alias in node.names
            ):
                fail(f"{label}:{node.lineno}: import outside static allowlist {module}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in FORBIDDEN_DYNAMIC_NAMES:
                fail(f"{label}:{node.lineno}: forbidden capability reference {node.id}")
        elif isinstance(node, ast.Attribute):
            name = qualified_name(node)
            bare = name.rsplit(".", 1)[-1] if name else ""
            if bare in FORBIDDEN_BARE_CALL_NAMES or any(
                name == forbidden or name.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_QUALIFIED_REFERENCES
            ):
                fail(f"{label}:{node.lineno}: forbidden capability reference {name}")
        elif isinstance(node, ast.Call):
            name = qualified_name(node.func)
            bare = name.rsplit(".", 1)[-1] if name else ""
            if bare in FORBIDDEN_BARE_CALL_NAMES:
                fail(f"{label}:{node.lineno}: forbidden capability call {name}")


def validate_owned_python_ast() -> None:
    for path in (CHECKER_PATH, TEST_PATH):
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            fail(f"{path.relative_to(ROOT)}: {error}")
        validate_ast_source(raw, str(path.relative_to(ROOT)))


def validate_artifact_hashes() -> None:
    for path, digest in ARTIFACT_SHA256.items():
        validate_file_hash(path, digest)


def main() -> int:
    try:
        validate_source_documents()
        validate_document(load_json(ARTIFACT_JSON_PATH))
        validate_owned_python_ast()
        validate_artifact_hashes()
    except LibjuiceCompileOnlyValidationError as error:
        print(f"P2P/NAT libjuice compile-only contract validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "P2P/NAT libjuice compile-only contract validation passed "
        "(blocked missing reviewed source; not executed; evidence absent)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
