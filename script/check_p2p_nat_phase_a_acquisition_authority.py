#!/usr/bin/env python3
"""Validate the versioned Phase A artifact-acquisition authority chain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = ROOT / "docs/security-hardening/production-p2p-nat-v1"
SPIKE_ROOT = DESIGN_ROOT / "controlled-network-spike"
DECISION_PATH = SPIKE_ROOT / "decision-v2.json"
DECISION_MARKDOWN_PATH = SPIKE_ROOT / "decision-v2.md"
HANDOFF_PATH = DESIGN_ROOT / "implementation/handoff-v5.json"
HANDOFF_MARKDOWN_PATH = DESIGN_ROOT / "implementation/handoff-v5.md"
PROGRESS_PATH = SPIKE_ROOT / "phase-a/progress-v2.json"
PREDECESSOR_HASHES = {
    SPIKE_ROOT / "decision-v1.json": "1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228",
    DESIGN_ROOT / "implementation/handoff-v4.json": "b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd",
    SPIKE_ROOT / "phase-a/progress-v1.json": "3e0d98c2c03e97f7f16e63cca9c545553234ab05ff7d233bae607e09f13738a3",
}
CURRENT_HASHES = {
    DECISION_PATH: "a23f4020a8d450248e4fb26a2697f9294626166d3166dc1f13971361094d074c",
    DECISION_MARKDOWN_PATH: "5ed3de5859f4529864403b2287754ef8bdcb8eb689eae6928820cc14fcb90bf0",
    HANDOFF_PATH: "af3fbf3f7ee3018a7dfcff6713471247db454bc5740a7893558ec57769e8f249",
    HANDOFF_MARKDOWN_PATH: "e2f0e7620ba85669014c94924a6ac0d38b021f9e82b6e2c4b6b3a25d84043644",
    PROGRESS_PATH: "af626c5dfe3c4b8d9263fe5464c1a0ee5fa98c78ea8be75ddf9356120207795b",
}

PROFILE_ID = "production_p2p_nat_v1_recommended"
DECISION_ID = "production_p2p_nat_v1_controlled_network_spike_decision_v2"
HANDOFF_ID = "production_p2p_nat_v1_handoff_v5"
APPROVALS = [
    {
        "decisionId": "networking_library_selection",
        "status": "approved_for_bounded_phase_a_evidence",
        "resolution": "libjuice-1.7.2-static-c-abi",
    },
    {
        "decisionId": "session_cryptography_library_selection",
        "status": "approved_for_bounded_phase_a_evidence",
        "resolution": "platform-native-p256-hkdf-sha256-aes256gcm",
    },
    {
        "decisionId": "isolated_harness_design",
        "status": "approved_for_bounded_phase_a_evidence",
        "resolution": "linux-netns-twin-agent-local-services",
    },
    {
        "decisionId": "socket_destination_and_egress_controls",
        "status": "approved_for_bounded_phase_a_evidence",
        "resolution": "numeric-endpoint-allowlist-plus-os-egress-witness",
    },
]
REQUIRED_BEFORE_COMPILATION = [
    "completed_versioned_source_intake",
    "exact_source_and_supply_chain_manifest",
    "independent_source_security_review",
    "exact_android_ndk_archive_package_and_tool_digests",
    "exact_macos_sdk_and_tool_digests",
    "new_versioned_compile_only_contract",
]
ACQUISITION_AUTHORIZATION = {
    "networkPurpose": "bounded_phase_a_artifact_acquisition_only",
    "networkIOAllowed": True,
    "sourceAcquisitionNetworkIOAllowed": True,
    "androidNdkAcquisitionNetworkIOAllowed": True,
    "httpsOnly": True,
    "redirectFollowingAllowed": False,
    "environmentProxyAllowed": False,
    "allowedHosts": ["github.com", "codeload.github.com", "dl.google.com"],
    "dnsAllowedOnlyForExactHosts": True,
    "packageManagerAcquisitionAllowed": False,
    "archiveExtractionAllowed": True,
    "manifestGenerationAllowed": True,
    "libjuice": {
        "candidateId": "libjuice-1.7.2-static-c-abi",
        "releaseTag": "v1.7.2",
        "repositoryMetadataUrl": "https://github.com/paullouisageneau/libjuice.git",
        "archiveUrl": "https://codeload.github.com/paullouisageneau/libjuice/tar.gz/refs/tags/v1.7.2",
        "archiveRelativePath": "build/offline-source/libjuice-1.7.2/original/libjuice-1.7.2.tar.gz",
        "extractedSourceRelativePath": "build/offline-source/libjuice-1.7.2/source",
        "maximumArchiveBytes": 16_777_216,
        "maximumExtractedBytes": 67_108_864,
    },
    "androidNdk": {
        "release": "r28c",
        "version": "28.2.13676358",
        "packageId": "ndk;28.2.13676358",
        "selectionReason": "agp_9_2_1_embedded_default_version",
        "agpJarRelativePath": ".gradle/caches/modules-2/files-2.1/com.android.tools.build/gradle/9.2.1/db4cfe640e5a8f1de9d71ec67b5a90ac541fafc5/gradle-9.2.1.jar",
        "agpJarSha256": "582e85078b60eb80669223b34b58200ba034654b2edb1cf9621e62fde7dfc0a3",
        "officialDocumentationUrl": "https://developer.android.com/studio/projects/configure-agp-ndk",
        "archiveUrl": "https://dl.google.com/android/repository/android-ndk-r28c-darwin.zip",
        "archiveRelativePath": "build/toolchain-intake/android-ndk-r28c-darwin.zip",
        "installRelativeToHome": "Library/Android/sdk/ndk/28.2.13676358",
        "maximumArchiveBytes": 1_258_291_200,
        "maximumInstalledBytes": 5_368_709_120,
    },
}
EXECUTION_AUTHORITY = {
    "offlineSourceInspectionAuthorized": True,
    "toolchainInspectionAuthorized": True,
    "sourceExecutionAllowed": False,
    "compilerInvocationAuthorizedBeforeReviewedManifest": False,
    "archiveInvocationAuthorizedBeforeReviewedManifest": False,
    "configureExecutionAllowed": False,
    "testExecutableBuildAllowed": False,
    "testExecutionAllowed": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIOAllowed": False,
    "harnessNetworkIOAllowed": False,
    "controlledSpikeNetworkIOAllowed": False,
    "controlledSpikeSocketExecutionAuthorized": False,
    "phaseBExecutionAuthorized": False,
    "phaseBNetworkIOAllowed": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
    "handoffV5CreationAuthorized": True,
}


class AuthorityValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise AuthorityValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON name {key!r}")
        result[key] = value
    return result


def parse_json(raw: str, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=reject_duplicate_names)
    except json.JSONDecodeError as error:
        fail(f"{label}: invalid JSON: {error}")


def type_exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            type_exact_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            type_exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        fail(f"{label}: expected exact keys {sorted(expected)}, got {actual}")
    return value


def require_exact(actual: Any, expected: Any, label: str) -> None:
    if not type_exact_equal(actual, expected):
        fail(f"{label}: canonical value drifted")


def validate_file_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        fail(f"{path.relative_to(ROOT)}: SHA-256 drifted; expected {expected}, got {actual}")


def validate_decision(document: Any) -> None:
    root = exact_keys(document, {
        "documentType", "schemaVersion", "decisionId", "profileId", "supersedes",
        "sourceReview", "sourceHandoff", "status", "approvalSource", "recordedAt",
        "decisionScope", "retainedApprovals", "acquisitionAuthorization",
        "executionAuthority", "requiredBeforeCompilation", "failurePolicy", "nextStep",
        "immutability",
    }, "decision-v2")
    require_exact(root["documentType"], "aetherlink.p2p-nat-controlled-network-spike-acquisition-decision", "decision-v2.documentType")
    require_exact(root["schemaVersion"], "1.0", "decision-v2.schemaVersion")
    require_exact(root["decisionId"], DECISION_ID, "decision-v2.decisionId")
    require_exact(root["profileId"], PROFILE_ID, "decision-v2.profileId")
    require_exact(root["supersedes"], {
        "path": "decision-v1.json",
        "decisionId": "production_p2p_nat_v1_controlled_network_spike_decision_v1",
        "sha256": PREDECESSOR_HASHES[SPIKE_ROOT / "decision-v1.json"],
    }, "decision-v2.supersedes")
    require_exact(root["sourceReview"], {
        "path": "review-v1.json",
        "reviewId": "production_p2p_nat_v1_controlled_network_spike_review_v1",
        "sha256": "744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62",
    }, "decision-v2.sourceReview")
    require_exact(root["sourceHandoff"], {
        "path": "../implementation/handoff-v4.json",
        "handoffId": "production_p2p_nat_v1_handoff_v4",
        "sha256": PREDECESSOR_HASHES[DESIGN_ROOT / "implementation/handoff-v4.json"],
    }, "decision-v2.sourceHandoff")
    require_exact(root["status"], "closed", "decision-v2.status")
    require_exact(root["approvalSource"], "explicit_user_instruction", "decision-v2.approvalSource")
    require_exact(root["recordedAt"], "2026-07-17", "decision-v2.recordedAt")
    require_exact(root["decisionScope"], "bounded_phase_a_official_source_and_android_ndk_acquisition", "decision-v2.decisionScope")
    require_exact(root["retainedApprovals"], APPROVALS, "decision-v2.retainedApprovals")
    require_exact(root["acquisitionAuthorization"], ACQUISITION_AUTHORIZATION, "decision-v2.acquisitionAuthorization")
    require_exact(root["executionAuthority"], EXECUTION_AUTHORITY, "decision-v2.executionAuthority")
    require_exact(root["requiredBeforeCompilation"], REQUIRED_BEFORE_COMPILATION, "decision-v2.requiredBeforeCompilation")
    require_exact(root["failurePolicy"], "fail_closed_without_fallback_download_execution_socket_or_phase_b_authority", "decision-v2.failurePolicy")
    require_exact(root["nextStep"], "create_handoff_v5_then_acquire_exact_artifacts_and_publish_reviewed_manifests_before_compilation", "decision-v2.nextStep")
    require_exact(root["immutability"], {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_decision",
    }, "decision-v2.immutability")


def validate_handoff(document: Any, decision: dict[str, Any]) -> None:
    root = exact_keys(document, {
        "documentType", "schemaVersion", "handoffId", "supersedesPath", "profileId",
        "selectionDecisionPath", "preNetworkApprovalDecisionPath", "controlledSpikeReviewPath",
        "controlledSpikeDecisionPath", "status", "productionDesignStatus", "measurementStatus",
        "activeProtocolNamespace", "authorization", "packages", "preNetworkDecisions",
        "controlledSpikeApprovals", "nextDecision", "immutability", "supersededHandoffSha256",
        "controlledSpikeDecisionSha256",
    }, "handoff-v5")
    require_exact(root["documentType"], "aetherlink.p2p-nat-bounded-handoff", "handoff-v5.documentType")
    require_exact(root["schemaVersion"], "1.0", "handoff-v5.schemaVersion")
    require_exact(root["handoffId"], HANDOFF_ID, "handoff-v5.handoffId")
    require_exact(root["supersedesPath"], "handoff-v4.json", "handoff-v5.supersedesPath")
    require_exact(root["supersededHandoffSha256"], PREDECESSOR_HASHES[DESIGN_ROOT / "implementation/handoff-v4.json"], "handoff-v5.supersededHandoffSha256")
    require_exact(root["controlledSpikeDecisionPath"], "../controlled-network-spike/decision-v2.json", "handoff-v5.controlledSpikeDecisionPath")
    require_exact(root["controlledSpikeDecisionSha256"], CURRENT_HASHES[DECISION_PATH], "handoff-v5.controlledSpikeDecisionSha256")
    require_exact(root["profileId"], PROFILE_ID, "handoff-v5.profileId")
    require_exact(root["status"], "closed", "handoff-v5.status")
    require_exact(root["productionDesignStatus"], "not_implemented", "handoff-v5.productionDesignStatus")
    require_exact(root["measurementStatus"], "not_started", "handoff-v5.measurementStatus")
    require_exact(root["activeProtocolNamespace"], ["route.refresh"], "handoff-v5.activeProtocolNamespace")

    predecessor = parse_json((DESIGN_ROOT / "implementation/handoff-v4.json").read_text(encoding="utf-8"), "handoff-v4")
    require_exact(root["packages"][:2], predecessor["packages"][:2], "handoff-v5 preserved packages")
    require_exact(root["preNetworkDecisions"], predecessor["preNetworkDecisions"], "handoff-v5 pre-network decisions")
    require_exact(root["controlledSpikeApprovals"], predecessor["controlledSpikeApprovals"], "handoff-v5 approvals")
    if len(root["packages"]) != 3:
        fail("handoff-v5.packages: expected exactly three packages")
    spike = root["packages"][2]
    require_exact(spike["packageId"], "controlled-network-spike", "handoff-v5 spike package")
    require_exact(spike["authorizationStatus"], "authorized_phase_a_acquisition_and_evidence_only", "handoff-v5 spike status")
    require_exact(spike["executionStatus"], "acquisition_authorized_not_started", "handoff-v5 execution status")
    require_exact(spike["phaseA"]["acquisitionPolicy"], decision["acquisitionAuthorization"], "handoff-v5 acquisition policy")
    require_exact(spike["phaseA"]["sourceAcquisitionNetworkIOAllowed"], True, "handoff-v5 source acquisition")
    require_exact(spike["phaseA"]["androidNdkAcquisitionNetworkIOAllowed"], True, "handoff-v5 NDK acquisition")
    for key in ("sourceExecutionAllowed", "socketCreationAllowed", "runtimeNetworkIOAllowed", "harnessNetworkIOAllowed"):
        require_exact(spike["phaseA"][key], False, f"handoff-v5 phaseA.{key}")
    require_exact(spike["phaseB"], predecessor["packages"][2]["phaseB"], "handoff-v5 phase B")
    for key in (
        "compilerInvocationAuthorized", "archiveInvocationAuthorized", "sourceExecutionAllowed",
        "socketCreationAllowed", "runtimeNetworkIOAllowed", "harnessNetworkIOAllowed",
        "controlledSpikeNetworkIOAllowed", "controlledSpikeSocketExecutionAuthorized",
        "phaseBExecutionAuthorized", "productionNetworkIOAllowed", "productionDeploymentAuthorized",
    ):
        require_exact(root["authorization"][key], False, f"handoff-v5.authorization.{key}")
    for key in (
        "officialLibjuiceSourceAcquisitionAuthorized", "sourceAcquisitionNetworkIOAllowed",
        "androidNdkInstallationAuthorized", "androidNdkPackageAcquisitionNetworkIOAllowed",
    ):
        require_exact(root["authorization"][key], True, f"handoff-v5.authorization.{key}")
    require_exact(root["nextDecision"], {
        "status": "reviewed_acquisition_required_before_compilation_and_complete_phase_a_required_before_socket_execution",
        "requiredBeforeCompilation": REQUIRED_BEFORE_COMPILATION,
        "sourceAcquisitionNetworkIOAllowedBeforeReviewedIntake": True,
        "androidNdkAcquisitionNetworkIOAllowedBeforeReviewedToolchain": True,
        "compilerInvocationAuthorizedBeforeReviewedManifest": False,
        "archiveInvocationAuthorizedBeforeReviewedManifest": False,
        "controlledSpikeNetworkIOAllowedBeforeSeparateDecision": False,
        "socketExecutionAuthorizedBeforeSeparateDecision": False,
    }, "handoff-v5.nextDecision")


def validate_progress(document: Any, decision: dict[str, Any]) -> None:
    root = exact_keys(document, {
        "documentType", "schemaVersion", "artifactId", "profileId", "recordedAt",
        "sourceDecision", "sourceHandoff", "approvalSnapshot", "overallStatus", "statusSummary",
        "evidenceStatus", "boundedPhaseAAuthority", "executionAuthority", "phaseBDecisionEligible",
        "measurementStatus", "nextStep", "immutability", "acquisitionState", "supersedes",
    }, "progress-v2")
    require_exact(root["artifactId"], "production_p2p_nat_v1_controlled_spike_phase_a_progress_v2", "progress-v2.artifactId")
    require_exact(root["profileId"], PROFILE_ID, "progress-v2.profileId")
    require_exact(root["supersedes"], {
        "path": "progress-v1.json",
        "artifactId": "production_p2p_nat_v1_controlled_spike_phase_a_progress_v1",
        "sha256": PREDECESSOR_HASHES[SPIKE_ROOT / "phase-a/progress-v1.json"],
    }, "progress-v2.supersedes")
    require_exact(root["sourceDecision"], {
        "path": "../decision-v2.json", "decisionId": DECISION_ID,
        "sha256": CURRENT_HASHES[DECISION_PATH],
    }, "progress-v2.sourceDecision")
    require_exact(root["sourceHandoff"], {
        "path": "../../implementation/handoff-v5.json", "handoffId": HANDOFF_ID,
        "sha256": CURRENT_HASHES[HANDOFF_PATH],
    }, "progress-v2.sourceHandoff")
    require_exact(root["overallStatus"], "acquisition_authorized_incomplete_phase_a", "progress-v2.overallStatus")
    require_exact(root["evidenceStatus"]["libjuice_supply_chain_and_source_audit"]["status"], "authorized_pending_official_source_acquisition", "progress-v2 source status")
    require_exact(root["evidenceStatus"]["android_macos_compile_only_integration"]["status"], "blocked_pending_reviewed_source_and_toolchain", "progress-v2 compile status")
    predecessor = parse_json((SPIKE_ROOT / "phase-a/progress-v1.json").read_text(encoding="utf-8"), "progress-v1")
    for key in ("cross_platform_session_crypto_vectors", "static_harness_and_egress_policy", "phase_a_security_review"):
        require_exact(root["evidenceStatus"][key], predecessor["evidenceStatus"][key], f"progress-v2 evidence {key}")
    require_exact(root["acquisitionState"], {
        "status": "authorized_not_started",
        "libjuiceArchivePresent": False,
        "libjuiceSourcePresent": False,
        "androidNdkArchivePresent": False,
        "androidNdkInstalled": False,
        "policy": decision["acquisitionAuthorization"],
    }, "progress-v2.acquisitionState")
    for key in ("sourceAcquisitionNetworkIOAllowed", "androidNdkPackageAcquisitionNetworkIOAllowed"):
        require_exact(root["executionAuthority"][key], True, f"progress-v2.executionAuthority.{key}")
    for key in (
        "sourceExecutionAllowed", "compilerInvocationAuthorized", "archiveInvocationAuthorized",
        "socketCreationAllowed", "runtimeNetworkIOAllowed", "harnessNetworkIOAllowed",
        "controlledSpikeNetworkIOAllowed", "controlledSpikeSocketExecutionAuthorized",
        "phaseBExecutionAuthorized", "phaseBNetworkIOAllowed", "phaseBSocketExecutionAuthorized",
        "externalEgressAllowed", "productionNetworkIOAllowed", "productionDeploymentAuthorized",
    ):
        require_exact(root["executionAuthority"][key], False, f"progress-v2.executionAuthority.{key}")
    require_exact(root["phaseBDecisionEligible"], False, "progress-v2.phaseBDecisionEligible")
    require_exact(root["measurementStatus"], "not_started", "progress-v2.measurementStatus")


def validate_markdown(path: Path, headings: list[str], required: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    actual_headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    if actual_headings != headings:
        fail(f"{path.name}: heading order drifted; got {actual_headings}")
    for snippet in required:
        if snippet.lower() not in text.lower():
            fail(f"{path.name}: missing {snippet!r}")
    for forbidden in (
        "controlledSpikeNetworkIOAllowed=true", "controlledSpikeSocketExecutionAuthorized=true",
        "phaseBExecutionAuthorized=true", "productionNetworkIOAllowed=true",
        "productionDeploymentAuthorized=true", "production ready", "ICE is implemented",
    ):
        if forbidden.lower() in text.lower():
            fail(f"{path.name}: forbidden claim {forbidden!r}")


def main() -> int:
    try:
        for path, expected in PREDECESSOR_HASHES.items():
            validate_file_hash(path, expected)
        decision = parse_json(DECISION_PATH.read_text(encoding="utf-8"), "decision-v2.json")
        handoff = parse_json(HANDOFF_PATH.read_text(encoding="utf-8"), "handoff-v5.json")
        progress = parse_json(PROGRESS_PATH.read_text(encoding="utf-8"), "progress-v2.json")
        validate_decision(decision)
        validate_handoff(handoff, decision)
        validate_progress(progress, decision)
        validate_markdown(
            DECISION_MARKDOWN_PATH,
            ["Closed Decision", "Exact Acquisition", "Pre-Compile Gate", "Closed Execution Gates", "Next Gate"],
            ("explicit user instruction", "v1.7.2", "28.2.13676358", "three allowed hosts", "compiler and archive invocation remain false", "sourceExecutionAllowed=false", "controlledSpikeNetworkIOAllowed=false", "separate from controlled-spike traffic"),
        )
        validate_markdown(
            HANDOFF_MARKDOWN_PATH,
            ["Closed Status", "Preserved Evidence", "Authorized Acquisition", "Pre-Compile Boundary", "Closed Network Boundary", "Next Decision"],
            ("supersedes `handoff-v4`", "decision-v2", "v1.7.2", "28.2.13676358", "compilerInvocationAuthorized=false", "controlledSpikeNetworkIOAllowed=false", "separate explicit versioned decision"),
        )
        for path, expected in CURRENT_HASHES.items():
            validate_file_hash(path, expected)
    except (OSError, UnicodeError, AuthorityValidationError) as error:
        print(f"P2P/NAT Phase A acquisition authority validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "P2P/NAT Phase A acquisition authority passed "
        "(exact libjuice v1.7.2 and NDK 28.2.13676358 acquisition allowed; "
        "compile/socket/runtime-network/Phase-B/production gates closed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
