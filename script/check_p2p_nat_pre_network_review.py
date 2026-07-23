#!/usr/bin/env python3
"""Validate the immutable P2P/NAT proposal, approval, and bounded handoff."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/pre-network/review-v1.json"
MARKDOWN_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/pre-network/review-v1.md"
DECISION_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/selection-decision.json"
HANDOFF_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v2.json"
APPROVAL_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/pre-network/decision-v1.json"
APPROVAL_MARKDOWN_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/pre-network/decision-v1.md"
HANDOFF_V3_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v3.json"
HANDOFF_V3_MARKDOWN_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v3.md"
ANDROID_CANONICAL_CODEC_PATH = (
    ROOT
    / "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatCanonicalCodec.kt"
)
ANDROID_P256_COMPAT_CURRENT = b"val left = y.modPow(BigInteger.valueOf(2L), P256_FIELD)"
ANDROID_P256_COMPAT_HISTORICAL = b"val left = y.modPow(BigInteger.TWO, P256_FIELD)"
HANDOFF_V3_EVIDENCE_ADDITIONS = {
    "canonical-contracts": [
        "../../../../apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatContract.kt",
    ],
    "no-network-conformance": [],
}
IMMUTABLE_SOURCE_SHA256 = {
    PACKET_PATH: "d3d7a39774610452babedc964ef57aa08d872c7fa9c8a0b5aaf35ca2b0f99802",
    MARKDOWN_PATH: "0aaad017d4bfa7189cc2864d8afe93b0216f32b999b554905106b7235748e16e",
    DECISION_PATH: "c87551296ca12d4ca8db68e13b45ad7b059ebd8354f8834a512ee218abd75b72",
    HANDOFF_PATH: "88c84d55e02bea251a8bce4b186fae51c0e85b5de89342c92be22fd8ed37e8e6",
    ROOT / "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v2.md":
        "fee98c2006198939504fac81393291bcb08340b844852c56be3855c3fd30549f",
}
GENERATED_ARTIFACT_SHA256 = {
    APPROVAL_PATH: "2962c6f752ebbdfd4432364544b5fa436974701cf54471ed121521f40296108a",
    APPROVAL_MARKDOWN_PATH: "e53e91ccf5686a962c10d7dacc2e7af6368f754bf42bb7a614999d6ed895c5d7",
    HANDOFF_V3_PATH: "07a45cd49f6c42fe9c4ad722d78a0bf7595b0d38a0d88287d2e0ceeb94e4513c",
    HANDOFF_V3_MARKDOWN_PATH: "bcdf4d15e48901a49c1d02024fabfe48020b6bafb17ad26632e312cb365bd55a",
}

DECISION_ORDER = (
    "service-ownership-and-trust",
    "pair-authorization-and-retention",
    "candidate-privacy-and-scope",
    "ice-and-consent-policy",
    "turn-credential-and-abuse-policy",
    "session-transition-semantics",
    "release-budgets",
)
SECURITY_FLOORS = (
    "route_token_separation",
    "end_to_end_identity_before_application_readiness",
    "no_unauthenticated_or_plaintext_downgrade",
    "default_deny_candidate_destinations",
    "bounded_replay_and_resource_state",
    "control_plane_application_data_exclusion",
)
RECOMMENDATIONS = {
    "service-ownership-and-trust": "first-party-tls13-signed-service-config",
    "pair-authorization-and-retention": "opaque-generation-scoped-capabilities",
    "candidate-privacy-and-scope": "e2e-limited-direct",
    "ice-and-consent-policy": "full-ice-regular-nomination-runtime-initiator",
    "turn-credential-and-abuse-policy": "short-lived-pair-scoped-turn",
    "session-transition-semantics": "between-request-cutover-fail-inflight",
    "release-budgets": "measured-matrix-with-hard-stop-budgets",
}
DECISION_SHA256 = {
    "service-ownership-and-trust": "941ab52e7dc14be308a75f83569003a00d88cd990b81e19d6e6572ab2736773e",
    "pair-authorization-and-retention": "8bc2d313e2785c9ae3748385532738ae12cefdd1562a2f259218d68d23ce49c1",
    "candidate-privacy-and-scope": "9e320ce2f4fefed5fc5d923d02fece019f11701d0e55a192f704c15e7ad36f2a",
    "ice-and-consent-policy": "dd9ea14b714f504c9594c7531bb91d07afc557770e2439f92593a69ddfde8bae",
    "turn-credential-and-abuse-policy": "cd2b1630ad7f1c509c8ec911907866c4a440946fe133e7e873e11e6d62b77690",
    "session-transition-semantics": "285e8bfd26b847674c451a63114abbf51a5a040d7cf158afa413dfb17f3b8240",
    "release-budgets": "d3c57b646d69473a8edfa4ed2d85560db1871afea5d51d7ff00510c284ead442",
}
REQUIRED_ACTION = (
    "Explicitly approve this complete recommendation set, approve specified modifications, "
    "or reject it before a new versioned handoff can be created."
)
OPTION_IDS = {
    "service-ownership-and-trust": (
        "first-party-tls13-signed-service-config",
        "contracted-provider-tls13-signed-service-config",
        "enterprise-self-hosted-signed-service-config",
    ),
    "pair-authorization-and-retention": (
        "opaque-generation-scoped-capabilities",
        "stable-pair-service-account",
        "per-request-capabilities",
    ),
    "candidate-privacy-and-scope": (
        "e2e-limited-direct",
        "relay-only-candidate-disclosure",
        "all-host-candidates",
    ),
    "ice-and-consent-policy": (
        "full-ice-regular-nomination-runtime-initiator",
        "ice-lite-runtime",
        "aggressive-nomination",
    ),
    "turn-credential-and-abuse-policy": (
        "short-lived-pair-scoped-turn",
        "long-lived-user-turn-credentials",
        "unscoped-anonymous-turn",
    ),
    "session-transition-semantics": (
        "between-request-cutover-fail-inflight",
        "duplicate-safe-cutover-barrier",
        "transparent-replay",
    ),
    "release-budgets": (
        "measured-matrix-with-hard-stop-budgets",
        "best-effort-observation",
        "single-network-success-gate",
    ),
}
CONTRACT_KEYS = {
    "service-ownership-and-trust": {
        "operatorClass", "serviceClasses", "transportTrust", "configurationTrust",
        "rotationRule", "outageRule", "incidentRule",
    },
    "pair-authorization-and-retention": {
        "capabilityKinds", "bindingFields", "maximumLifetimeSeconds", "maximumClockSkewSeconds",
        "rotationRule", "revocationRule", "retentionRule", "identifierRule",
    },
    "candidate-privacy-and-scope": {
        "candidateEnvelope", "gatheredAndSignaledCandidateKinds",
        "connectivityCheckDiscoveredCandidateKinds", "hostCandidatePolicy", "addressFamilies",
        "nat64Policy", "alwaysProhibited", "maximumCandidatesPerEndpoint", "serviceVisibility",
    },
    "ice-and-consent-policy": {
        "iceMode", "initiatorRole", "nomination", "maximumCandidatesPerEndpoint",
        "maximumTrickleBatchCandidates", "trickleRule", "restartRule", "pacingRule",
        "consentIntervalSeconds", "consentIntervalJitter", "consentExpirySeconds",
        "consentFailureRule", "mobilityRule",
    },
    "turn-credential-and-abuse-policy": {
        "credentialIssuance", "credentialLifetimeSeconds", "allocationLifetimeSeconds",
        "maximumActiveAllocationsPerPair", "permissionRule", "transportRule", "initialRegionCount",
        "quotaRule", "outageRule", "abuseTelemetry",
    },
    "session-transition-semantics": {
        "cutoverPoint", "newRequestAdmission", "inFlightRule", "idempotentRetryRule",
        "nonIdempotentRetryRule", "oldPathRule", "fallbackRule",
    },
    "release-budgets": {
        "minimumCompletedSessions", "requiredMatrix", "authenticatedTraversalSuccessMinimum",
        "directAndRelaySuccessReportedSeparately", "setupLatencyMilliseconds", "incrementalMemoryMiB",
        "androidBatteryPercentPerHourMaximum", "revocationClosureMillisecondsP99",
        "falseAbuseRejectionMaximum", "prohibitedDestinationAttemptsAllowed",
        "plaintextDowngradesAllowed", "duplicateNonIdempotentRequestsAllowed",
        "rollbackSuccessMinimum", "releaseRule",
    },
}


class ReviewValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise ReviewValidationError(message)


def historical_evidence_bytes_for_digest(path: Path, source: bytes) -> bytes:
    """Reconstruct one pinned historical digest without permitting a live API regression."""
    if path != ANDROID_CANONICAL_CODEC_PATH:
        return source
    if (
        source.count(ANDROID_P256_COMPAT_CURRENT) != 1
        or ANDROID_P256_COMPAT_HISTORICAL in source
    ):
        fail(
            "P2pNatCanonicalCodec.kt must retain the exact API 26-safe P-256 "
            "compatibility amendment"
        )
    return source.replace(
        ANDROID_P256_COMPAT_CURRENT,
        ANDROID_P256_COMPAT_HISTORICAL,
        1,
    )


def exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path}: expected object")
    actual = set(value)
    if actual != expected:
        fail(f"{path}: keys differ; missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")
    return value


def string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        fail(f"{path}: expected nonblank canonical string")
    return value


def string_list(value: Any, path: str, minimum: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum:
        fail(f"{path}: expected at least {minimum} strings")
    result = [string(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if len(set(result)) != len(result):
        fail(f"{path}: duplicate value")
    return result


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object contains duplicate name {key!r}")
        result[key] = value
    return result


def parse_json(raw: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=reject_duplicate_names)
    except json.JSONDecodeError as error:
        fail(f"invalid JSON: {error}")


def load_json(path: Path) -> Any:
    try:
        return parse_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        fail(f"{path.relative_to(ROOT)}: {error}")


def validate_file_hash(path: Path, expected: str) -> None:
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        fail(f"{path.relative_to(ROOT)}: {error}")
    if actual != expected:
        fail(f"{path.relative_to(ROOT)}: immutable content drifted")


def validate_markdown(raw: bytes) -> None:
    if hashlib.sha256(raw).hexdigest() != IMMUTABLE_SOURCE_SHA256[MARKDOWN_PATH]:
        fail("pre-network/review-v1.md: canonical human review content drifted")


def validate_references() -> None:
    for path, expected in IMMUTABLE_SOURCE_SHA256.items():
        validate_file_hash(path, expected)
    decision = exact_keys(load_json(DECISION_PATH), {
        "documentType", "schemaVersion", "decisionId", "profileId", "status", "decision",
        "approvalSource", "selectedOptions", "mandatoryFallback", "productionDesignStatus",
        "activeProtocolNamespace", "authorization", "handoffPath", "openPreNetworkDecisionIds",
        "immutability",
    }, "selection-decision")
    if decision["decision"] != "approved_for_bounded_handoff":
        fail("selection-decision: bounded profile approval is not closed")
    if decision["openPreNetworkDecisionIds"] != list(DECISION_ORDER):
        fail("selection-decision: open pre-network decisions drifted")

    handoff = exact_keys(load_json(HANDOFF_PATH), {
        "documentType", "schemaVersion", "handoffId", "supersedesPath", "profileId",
        "selectionDecisionPath", "status", "productionDesignStatus", "activeProtocolNamespace",
        "authorization", "packages", "preNetworkDecisions", "immutability",
    }, "handoff-v2")
    if handoff["handoffId"] != "production_p2p_nat_v1_handoff_v2" or handoff["status"] != "closed":
        fail("handoff-v2: expected closed source handoff")
    authorization = handoff["authorization"]
    if authorization.get("networkIOAllowed") is not False:
        fail("handoff-v2: network gate must remain closed")
    if [item.get("decisionId") for item in handoff["preNetworkDecisions"]] != list(DECISION_ORDER):
        fail("handoff-v2: pre-network decision order drifted")
    if any(item.get("status") != "open" for item in handoff["preNetworkDecisions"]):
        fail("handoff-v2: pre-network decisions must remain open")


def validate_approval_document(raw: Any) -> None:
    root = exact_keys(raw, {
        "documentType", "schemaVersion", "decisionId", "profileId", "sourceReviewId",
        "sourceReviewPath", "sourceHandoffId", "sourceHandoffPath", "status",
        "approvalSource", "measurementStatus", "decisionOrder", "resolutions",
        "authorization", "nextStep", "immutability",
    }, "approval")
    expected = {
        "documentType": "aetherlink.p2p-nat-pre-network-approval-decision",
        "schemaVersion": "1.0",
        "decisionId": "production_p2p_nat_v1_pre_network_decision_v1",
        "profileId": "production_p2p_nat_v1_recommended",
        "sourceReviewId": "production_p2p_nat_v1_pre_network_review_v1",
        "sourceReviewPath": "review-v1.json",
        "sourceHandoffId": "production_p2p_nat_v1_handoff_v2",
        "sourceHandoffPath": "../implementation/handoff-v2.json",
        "status": "closed",
        "approvalSource": "explicit_user_instruction",
        "measurementStatus": "unmeasured_proposal",
        "nextStep": "separate_networking_library_and_isolated_harness_review",
    }
    for key, value in expected.items():
        if root[key] != value:
            fail(f"approval.{key}: expected {value!r}")
    if root["decisionOrder"] != list(DECISION_ORDER):
        fail("approval.decisionOrder: canonical order drifted")
    resolutions = root["resolutions"]
    if not isinstance(resolutions, list) or len(resolutions) != len(DECISION_ORDER):
        fail("approval.resolutions: expected exactly seven resolutions")
    for index, raw_resolution in enumerate(resolutions):
        path = f"approval.resolutions[{index}]"
        resolution = exact_keys(raw_resolution, {
            "decisionId", "status", "recommendedOptionId", "resolution", "approvalSource",
        }, path)
        decision_id = DECISION_ORDER[index]
        if resolution["decisionId"] != decision_id:
            fail(f"{path}.decisionId: missing, duplicate, unknown, or out of order")
        recommended = RECOMMENDATIONS[decision_id]
        if resolution["status"] != "resolved":
            fail(f"{path}.status: expected resolved")
        if resolution["recommendedOptionId"] != recommended:
            fail(f"{path}.recommendedOptionId: recommendation mismatch")
        if resolution["resolution"] != recommended:
            fail(f"{path}.resolution: must exactly match recommendedOptionId")
        if resolution["approvalSource"] != "explicit_user_instruction":
            fail(f"{path}.approvalSource: explicit user instruction required")
    authorization = exact_keys(root["authorization"], {
        "handoffV3CreationAuthorized", "networkIOAllowed", "librarySelectionAuthorized",
        "productionDeploymentAuthorized", "controlledNetworkSpikeSocketExecutionAuthorized",
    }, "approval.authorization")
    if authorization["handoffV3CreationAuthorized"] is not True:
        fail("approval.authorization: handoff-v3 creation must be explicitly authorized")
    if any(authorization[key] is not False for key in (
        "networkIOAllowed", "librarySelectionAuthorized", "productionDeploymentAuthorized",
        "controlledNetworkSpikeSocketExecutionAuthorized",
    )):
        fail("approval.authorization: network, library, socket, and deployment gates must remain closed")
    if root["immutability"] != {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_decision",
    }:
        fail("approval.immutability: closed record contract drifted")


def validate_handoff_v3(raw: Any) -> None:
    root = exact_keys(raw, {
        "documentType", "schemaVersion", "handoffId", "supersedesPath", "profileId",
        "selectionDecisionPath", "preNetworkReviewPath", "approvalDecisionPath", "status",
        "productionDesignStatus", "measurementStatus", "activeProtocolNamespace",
        "authorization", "packages", "preNetworkDecisions", "nextReview", "immutability",
    }, "handoff-v3")
    expected = {
        "documentType": "aetherlink.p2p-nat-bounded-handoff",
        "schemaVersion": "1.0",
        "handoffId": "production_p2p_nat_v1_handoff_v3",
        "supersedesPath": "handoff-v2.json",
        "profileId": "production_p2p_nat_v1_recommended",
        "selectionDecisionPath": "../selection-decision.json",
        "preNetworkReviewPath": "../pre-network/review-v1.json",
        "approvalDecisionPath": "../pre-network/decision-v1.json",
        "status": "closed",
        "productionDesignStatus": "not_implemented",
        "measurementStatus": "unmeasured_proposal",
        "activeProtocolNamespace": ["route.refresh"],
    }
    for key, value in expected.items():
        if root[key] != value:
            fail(f"handoff-v3.{key}: expected {value!r}")
    authorization = exact_keys(root["authorization"], {
        "implementationAuthorized", "networkIOAllowed", "librarySelectionAuthorized",
        "productionDeploymentAuthorized", "controlledNetworkSpikeSocketExecutionAuthorized",
    }, "handoff-v3.authorization")
    if authorization["implementationAuthorized"] is not True:
        fail("handoff-v3.authorization: bounded implementation authorization drifted")
    if any(authorization[key] is not False for key in (
        "networkIOAllowed", "librarySelectionAuthorized", "productionDeploymentAuthorized",
        "controlledNetworkSpikeSocketExecutionAuthorized",
    )):
        fail("handoff-v3.authorization: network, library, socket, and deployment gates must remain closed")

    packages = root["packages"]
    if not isinstance(packages, list) or len(packages) != 3:
        fail("handoff-v3.packages: expected exactly three packages")
    source_packages = load_json(HANDOFF_PATH)["packages"]
    for index in range(2):
        package = exact_keys(packages[index], {
            "packageId", "authorizationStatus", "executionStatus", "executionAuthorized",
            "networkIOAllowed", "evidencePaths", "evidenceSha256",
        }, f"handoff-v3.packages[{index}]")
        source_package = source_packages[index]
        source_metadata = {
            key: value for key, value in source_package.items() if key != "evidencePaths"
        }
        if {
            key: package[key] for key in source_metadata
        } != source_metadata:
            fail("handoff-v3.packages: completed no-network evidence drifted from handoff-v2")
        evidence_paths = package["evidencePaths"]
        expected_evidence_paths = source_package["evidencePaths"] + HANDOFF_V3_EVIDENCE_ADDITIONS[
            package["packageId"]
        ]
        if evidence_paths != expected_evidence_paths:
            fail("handoff-v3.packages: completed evidence path set or order drifted")
        evidence_sha256 = exact_keys(
            package["evidenceSha256"],
            set(evidence_paths),
            f"handoff-v3.packages[{index}].evidenceSha256",
        )
        for relative_path in evidence_paths:
            expected_digest = evidence_sha256[relative_path]
            if not isinstance(expected_digest, str) or len(expected_digest) != 64:
                fail(f"handoff-v3.packages[{index}]: invalid evidence SHA-256")
            evidence_path = (HANDOFF_V3_PATH.parent / relative_path).resolve()
            if not evidence_path.is_relative_to(ROOT) or not evidence_path.is_file():
                fail(f"handoff-v3.packages[{index}]: evidence path is missing or escapes repository")
            historical_bytes = historical_evidence_bytes_for_digest(
                evidence_path,
                evidence_path.read_bytes(),
            )
            if hashlib.sha256(historical_bytes).hexdigest() != expected_digest:
                fail(f"handoff-v3.packages[{index}]: evidence SHA-256 drifted for {relative_path}")
    spike = exact_keys(packages[2], {
        "packageId", "authorizationStatus", "executionStatus", "executionAuthorized",
        "networkIOAllowed", "socketExecutionAuthorized", "blockedOnReviews",
    }, "handoff-v3.packages[2]")
    if spike != {
        "packageId": "controlled-network-spike",
        "authorizationStatus": "blocked_on_separate_review",
        "executionStatus": "not_started",
        "executionAuthorized": False,
        "networkIOAllowed": False,
        "socketExecutionAuthorized": False,
        "blockedOnReviews": [
            "networking_library_selection",
            "session_cryptography_library_selection",
            "isolated_harness_design",
            "socket_destination_and_egress_controls",
        ],
    }:
        fail("handoff-v3.packages[2]: controlled network spike boundary drifted")

    decisions = root["preNetworkDecisions"]
    if not isinstance(decisions, list) or len(decisions) != len(DECISION_ORDER):
        fail("handoff-v3.preNetworkDecisions: expected exactly seven decisions")
    for index, raw_decision in enumerate(decisions):
        path = f"handoff-v3.preNetworkDecisions[{index}]"
        decision = exact_keys(raw_decision, {
            "decisionId", "status", "resolution", "approvalSource",
        }, path)
        decision_id = DECISION_ORDER[index]
        if decision != {
            "decisionId": decision_id,
            "status": "resolved",
            "resolution": RECOMMENDATIONS[decision_id],
            "approvalSource": "explicit_user_instruction",
        }:
            fail(f"{path}: resolution, order, or approval source drifted")
    next_review = exact_keys(root["nextReview"], {
        "status", "scope", "networkIOAllowedDuringReview",
    }, "handoff-v3.nextReview")
    if next_review != {
        "status": "required_before_socket_execution",
        "scope": [
            "networking_library_selection", "session_cryptography_library_selection",
            "isolated_harness_design", "socket_destination_and_egress_controls",
        ],
        "networkIOAllowedDuringReview": False,
    }:
        fail("handoff-v3.nextReview: required separate review boundary drifted")
    if root["immutability"] != {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_handoff",
    }:
        fail("handoff-v3.immutability: closed record contract drifted")


def validate_contract(decision_id: str, contract: Any) -> None:
    contract = exact_keys(contract, CONTRACT_KEYS[decision_id], f"{decision_id}.proposedContract")
    if decision_id == "pair-authorization-and-retention":
        if contract["maximumLifetimeSeconds"] != 600 or contract["maximumClockSkewSeconds"] != 30:
            fail(f"{decision_id}: capability lifetime or skew floor weakened")
    elif decision_id == "candidate-privacy-and-scope":
        if contract["candidateEnvelope"] != "end_to_end_authenticated_encryption_required":
            fail(f"{decision_id}: end-to-end candidate protection is mandatory")
        if contract["maximumCandidatesPerEndpoint"] != 32:
            fail(f"{decision_id}: candidate cap drifted")
    elif decision_id == "ice-and-consent-policy":
        expected = (32, 8, 5, "0.8_to_1.2", 30)
        actual = (
            contract["maximumCandidatesPerEndpoint"], contract["maximumTrickleBatchCandidates"],
            contract["consentIntervalSeconds"], contract["consentIntervalJitter"],
            contract["consentExpirySeconds"],
        )
        if actual != expected:
            fail(f"{decision_id}: ICE/consent floors drifted")
    elif decision_id == "turn-credential-and-abuse-policy":
        if (contract["credentialLifetimeSeconds"], contract["allocationLifetimeSeconds"],
                contract["maximumActiveAllocationsPerPair"]) != (600, 600, 2):
            fail(f"{decision_id}: TURN lifetime or allocation cap drifted")
    elif decision_id == "session-transition-semantics":
        if contract["cutoverPoint"] != "between_application_requests_only":
            fail(f"{decision_id}: transition delivery floor weakened")
        if contract["inFlightRule"] != "fail_with_retryable_transport_error_without_automatic_replay":
            fail(f"{decision_id}: transparent replay is not authorized")
    elif decision_id == "release-budgets":
        if contract["minimumCompletedSessions"] != 1000:
            fail(f"{decision_id}: sample floor drifted")
        if contract["authenticatedTraversalSuccessMinimum"] != 0.99:
            fail(f"{decision_id}: traversal floor drifted")
        hard_stops = (
            contract["prohibitedDestinationAttemptsAllowed"], contract["plaintextDowngradesAllowed"],
            contract["duplicateNonIdempotentRequestsAllowed"], contract["rollbackSuccessMinimum"],
        )
        if hard_stops != (0, 0, 0, 1.0):
            fail(f"{decision_id}: security hard stop weakened")


def validate_document(raw: Any) -> None:
    root = exact_keys(raw, {
        "documentType", "schemaVersion", "reviewId", "profileId", "sourceHandoffId",
        "selectionDecisionPath", "sourceHandoffPath", "status", "approvalRequired",
        "measurementStatus", "authorization", "securityFloors", "decisionOrder", "decisions",
        "reviewOutcome",
    }, "review")
    expected_scalars = {
        "documentType": "aetherlink.p2p-nat-pre-network-review",
        "schemaVersion": "1.0",
        "reviewId": "production_p2p_nat_v1_pre_network_review_v1",
        "profileId": "production_p2p_nat_v1_recommended",
        "sourceHandoffId": "production_p2p_nat_v1_handoff_v2",
        "selectionDecisionPath": "../selection-decision.json",
        "sourceHandoffPath": "../implementation/handoff-v2.json",
        "status": "proposed_not_selected",
        "measurementStatus": "unmeasured_proposal",
    }
    for key, expected in expected_scalars.items():
        if root[key] != expected:
            fail(f"review.{key}: expected {expected!r}")
    if root["approvalRequired"] is not True:
        fail("review.approvalRequired: explicit approval must remain required")
    authorization = exact_keys(root["authorization"], {
        "networkIOAllowed", "librarySelectionAuthorized", "productionDeploymentAuthorized",
        "nextHandoffAuthorized",
    }, "review.authorization")
    if any(value is not False for value in authorization.values()):
        fail("review.authorization: every authorization must remain false")
    if root["securityFloors"] != list(SECURITY_FLOORS):
        fail("review.securityFloors: security floors drifted")
    if root["decisionOrder"] != list(DECISION_ORDER):
        fail("review.decisionOrder: canonical order drifted")

    decisions = root["decisions"]
    if not isinstance(decisions, list) or len(decisions) != len(DECISION_ORDER):
        fail("review.decisions: expected exactly seven decisions")
    seen: set[str] = set()
    for index, raw_decision in enumerate(decisions):
        path = f"review.decisions[{index}]"
        decision = exact_keys(raw_decision, {
            "decisionId", "status", "resolution", "approvalSource", "unresolvedApprovalInputs",
            "question", "recommendedOptionId", "options", "proposedContract",
            "rejectionConditions", "requiredEvidence",
        }, path)
        decision_id = string(decision["decisionId"], f"{path}.decisionId")
        if decision_id != DECISION_ORDER[index] or decision_id in seen:
            fail(f"{path}.decisionId: missing, duplicate, unknown, or out of order")
        seen.add(decision_id)
        if decision["status"] != "proposed_not_selected":
            fail(f"{path}.status: decision is not approved")
        if decision["resolution"] is not None or decision["approvalSource"] is not None:
            fail(f"{path}: resolution and approvalSource must remain null")
        string_list(decision["unresolvedApprovalInputs"], f"{path}.unresolvedApprovalInputs", 3)
        string(decision["question"], f"{path}.question")
        if decision["recommendedOptionId"] != RECOMMENDATIONS[decision_id]:
            fail(f"{path}.recommendedOptionId: recommendation drifted")
        options = decision["options"]
        if not isinstance(options, list) or len(options) != 3:
            fail(f"{path}.options: expected exactly three options")
        option_ids: list[str] = []
        recommended_count = 0
        for option_index, raw_option in enumerate(options):
            option = exact_keys(raw_option, {"optionId", "disposition", "tradeoff"}, f"{path}.options[{option_index}]")
            option_id = string(option["optionId"], f"{path}.options[{option_index}].optionId")
            option_ids.append(option_id)
            disposition = string(option["disposition"], f"{path}.options[{option_index}].disposition")
            if disposition == "recommended":
                recommended_count += 1
                if option_id != decision["recommendedOptionId"]:
                    fail(f"{path}.options: recommended disposition mismatch")
            string(option["tradeoff"], f"{path}.options[{option_index}].tradeoff")
        if tuple(option_ids) != OPTION_IDS[decision_id] or recommended_count != 1:
            fail(f"{path}.options: option set or recommendation count drifted")
        validate_contract(decision_id, decision["proposedContract"])
        string_list(decision["rejectionConditions"], f"{path}.rejectionConditions", 3)
        string_list(decision["requiredEvidence"], f"{path}.requiredEvidence", 3)
        canonical = json.dumps(
            decision,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        actual_digest = hashlib.sha256(canonical).hexdigest()
        if actual_digest != DECISION_SHA256[decision_id]:
            fail(f"{path}: canonical decision content drifted")

    outcome = exact_keys(root["reviewOutcome"], {
        "allDecisionsSelected", "networkSpikeAuthorized", "nextHandoffCreated", "requiredAction",
    }, "review.reviewOutcome")
    if any(outcome[key] is not False for key in ("allDecisionsSelected", "networkSpikeAuthorized", "nextHandoffCreated")):
        fail("review.reviewOutcome: selection, network spike, and next handoff must remain false")
    if outcome["requiredAction"] != REQUIRED_ACTION:
        fail("review.reviewOutcome.requiredAction: canonical approval instruction drifted")


def main() -> int:
    try:
        path = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else PACKET_PATH
        if len(sys.argv) > 2:
            fail("usage: check_p2p_nat_pre_network_review.py [packet.json]")
        validate_references()
        validate_document(load_json(path))
        validate_markdown(MARKDOWN_PATH.read_bytes())
        validate_approval_document(load_json(APPROVAL_PATH))
        validate_handoff_v3(load_json(HANDOFF_V3_PATH))
        for artifact_path, expected in GENERATED_ARTIFACT_SHA256.items():
            validate_file_hash(artifact_path, expected)
    except ReviewValidationError as error:
        print(f"P2P/NAT pre-network review check failed: {error}", file=sys.stderr)
        return 1
    print("P2P/NAT pre-network review passed (7 recommendations approved; handoff-v3 closed; network gate closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
