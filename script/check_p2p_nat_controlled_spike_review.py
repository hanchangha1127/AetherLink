#!/usr/bin/env python3
"""Validate the closed, unselected P2P/NAT controlled-spike review packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = ROOT / "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike"
REVIEW_PATH = REVIEW_ROOT / "review-v1.json"
MARKDOWN_PATH = REVIEW_ROOT / "review-v1.md"
HANDOFF_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v3.json"
HANDOFF_SHA256 = "07a45cd49f6c42fe9c4ad722d78a0bf7595b0d38a0d88287d2e0ceeb94e4513c"
GENERATED_ARTIFACT_SHA256 = {
    REVIEW_PATH: "744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62",
    MARKDOWN_PATH: "9fd1d76b94fc834d72cd0c714113fab1e0e4c6e8ec3cee55e213a1a9cb6c781f",
}

DECISION_ORDER = (
    "networking_library_selection",
    "session_cryptography_library_selection",
    "isolated_harness_design",
    "socket_destination_and_egress_controls",
)
RECOMMENDATIONS = {
    "networking_library_selection": "libjuice-1.7.2-static-c-abi",
    "session_cryptography_library_selection": "platform-native-p256-hkdf-sha256-aes256gcm",
    "isolated_harness_design": "linux-netns-twin-agent-local-services",
    "socket_destination_and_egress_controls": "numeric-endpoint-allowlist-plus-os-egress-witness",
}
EXPECTED_OPTIONS = {
    "networking_library_selection": {
        "libjuice-1.7.2-static-c-abi",
        "libnice-0.1.23-glib-c-abi",
        "libdatachannel-0.24.3-datachannel-stack",
    },
    "session_cryptography_library_selection": {
        "platform-native-p256-hkdf-sha256-aes256gcm",
        "pinned-boringssl-native",
        "libdatachannel-dtls-session",
    },
    "isolated_harness_design": {
        "linux-netns-twin-agent-local-services",
        "macos-pf-host-harness",
        "android-emulator-first-harness",
    },
    "socket_destination_and_egress_controls": {
        "numeric-endpoint-allowlist-plus-os-egress-witness",
        "library-config-only",
        "firewall-only",
    },
}
REQUIRED_CONTRACT_SNIPPETS = {
    "networking_library_selection": (
        "libjuice-1.7.2-static-c-abi", "static_library_through_versioned_c_abi_adapter",
        "android_min_sdk_26", "macos", "full_ice_regular_nomination",
        "authenticated_consent_freshness", "sourceacquisition",
        "exact_release_tag_and_commit_sha", "networkexecutionduringselection", "libnice_0_1_23",
    ),
    "session_cryptography_library_selection": (
        "cryptokit", "provider_neutral_jca", "ephemeral_p256_ecdh", "hkdf_sha256_rfc5869",
        "aes_256_gcm", "androidminimumsdk", "androidkeystore_api_31", "ephemeral",
        "transport_neutral", "networkexecutionduringselection",
    ),
    "isolated_harness_design": (
        "compile_only", "socketcreationallowed", "networkioallowed", "sourcedownloadallowed",
        "linux", "network_namespace", "local_stun_and_turn_only", "deny_all",
        "agentprocesscount", "wallclocktimeoutseconds", "maximumsocketsperprocess",
    ),
    "socket_destination_and_egress_controls": (
        "numeric-endpoint-allowlist-plus-os-egress-witness", "candidate_policy_before_library_call",
        "immutable_per_run", "dns", "proxy", "redirect", "deny_all", "packetcaptureassertion",
        "redact", "policydriftrule", "networkexecutionduringselection",
    ),
}
REQUIRED_SECURITY_FLOORS = {
    "route_token_separation",
    "endpoint_identity_before_application_readiness",
    "no_plaintext_or_unauthenticated_downgrade",
    "default_deny_destination",
    "no_dns_or_proxy",
    "no_application_payload_before_identity_and_key_confirmation",
    "exact_resource_and_time_ceilings",
    "content_free_logs",
    "kill_on_policy_drift",
}
REQUIRED_SOURCE_URLS = {
    "https://github.com/paullouisageneau/libjuice",
    "https://github.com/paullouisageneau/libjuice/blob/v1.7.2/include/juice/juice.h",
    "https://github.com/paullouisageneau/libjuice/releases/tag/v1.7.2",
    "https://libnice.freedesktop.org/",
    "https://libnice.freedesktop.org/libnice/NiceAgent.html",
    "https://github.com/paullouisageneau/libdatachannel",
    "https://github.com/paullouisageneau/libdatachannel/releases/tag/v0.24.3",
    "https://github.com/paullouisageneau/libdatachannel/blob/v0.24.3/DOC.md",
    "https://developer.android.com/privacy-and-security/cryptography",
    "https://developer.android.com/reference/javax/crypto/KeyAgreement",
    "https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec",
    "https://developer.apple.com/documentation/cryptokit/p256",
    "https://developer.apple.com/documentation/cryptokit/hkdf",
    "https://developer.apple.com/documentation/cryptokit/aes/gcm",
    "https://www.rfc-editor.org/rfc/rfc8445.html",
    "https://www.rfc-editor.org/rfc/rfc8489.html",
    "https://www.rfc-editor.org/rfc/rfc8656.html",
    "https://www.rfc-editor.org/rfc/rfc7675.html",
    "https://www.rfc-editor.org/rfc/rfc5869.html",
}


class ReviewValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise ReviewValidationError(message)


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


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        fail(f"{label}: expected exact keys {sorted(expected)}, got {actual}")
    return value


def nonempty_strings(value: Any, label: str, minimum: int = 1) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or not all(isinstance(item, str) and item.strip() == item and item for item in value)
        or len(set(value)) != len(value)
    ):
        fail(f"{label}: expected at least {minimum} unique canonical strings")
    return value


def validate_file_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        fail(f"{path.relative_to(ROOT)}: SHA-256 drifted; expected {expected}, got {actual}")


def validate_source_handoff() -> None:
    validate_file_hash(HANDOFF_PATH, HANDOFF_SHA256)
    handoff = exact_keys(
        parse_json(HANDOFF_PATH.read_text(encoding="utf-8"), "handoff-v3"),
        {
            "documentType", "schemaVersion", "handoffId", "supersedesPath", "profileId",
            "selectionDecisionPath", "preNetworkReviewPath", "approvalDecisionPath", "status",
            "productionDesignStatus", "measurementStatus", "activeProtocolNamespace",
            "authorization", "packages", "preNetworkDecisions", "nextReview", "immutability",
        },
        "handoff-v3",
    )
    if handoff["handoffId"] != "production_p2p_nat_v1_handoff_v3":
        fail("handoff-v3: unexpected source handoff id")
    authorization = handoff["authorization"]
    if not isinstance(authorization, dict) or any(
        authorization.get(field) is not False
        for field in (
            "networkIOAllowed", "librarySelectionAuthorized", "productionDeploymentAuthorized",
            "controlledNetworkSpikeSocketExecutionAuthorized",
        )
    ):
        fail("handoff-v3: library, network, socket, and deployment gates must remain closed")
    if handoff["nextReview"] != {
        "status": "required_before_socket_execution",
        "scope": list(DECISION_ORDER),
        "networkIOAllowedDuringReview": False,
    }:
        fail("handoff-v3: controlled-spike review dependency drifted")


def validate_document(document: Any) -> None:
    root = exact_keys(
        document,
        {
            "documentType", "schemaVersion", "reviewId", "profileId", "sourceHandoffId",
            "sourceHandoffPath", "status", "measurementStatus", "decisionOrder", "decisions",
            "securityFloors", "officialSources", "authorization", "reviewOutcome",
            "approvalRequired", "immutability",
        },
        "review-v1",
    )
    expected_root = {
        "documentType": "aetherlink.p2p-nat-controlled-network-spike-review",
        "schemaVersion": "1.0",
        "reviewId": "production_p2p_nat_v1_controlled_network_spike_review_v1",
        "profileId": "production_p2p_nat_v1_recommended",
        "sourceHandoffId": "production_p2p_nat_v1_handoff_v3",
        "sourceHandoffPath": "../implementation/handoff-v3.json",
        "status": "proposed_not_selected",
        "measurementStatus": "not_started",
        "decisionOrder": list(DECISION_ORDER),
    }
    for field, expected in expected_root.items():
        if root[field] != expected:
            fail(f"review-v1.{field}: expected {expected!r}")

    decisions = root["decisions"]
    if not isinstance(decisions, list) or len(decisions) != len(DECISION_ORDER):
        fail("review-v1.decisions: expected exactly four decisions")
    for index, decision_id in enumerate(DECISION_ORDER):
        decision = exact_keys(
            decisions[index],
            {
                "decisionId", "status", "resolution", "approvalSource", "unresolvedApprovalInputs",
                "question", "recommendedOptionId", "options", "proposedContract",
                "rejectionConditions", "requiredEvidence",
            },
            f"review-v1.decisions[{index}]",
        )
        if decision["decisionId"] != decision_id:
            fail(f"review-v1.decisions[{index}]: decision order drifted")
        if (
            decision["status"] != "proposed_not_selected"
            or decision["resolution"] is not None
            or decision["approvalSource"] is not None
        ):
            fail(f"review-v1.decisions[{index}]: implicit selection is forbidden")
        if not isinstance(decision["question"], str) or not decision["question"].strip():
            fail(f"review-v1.decisions[{index}].question: expected non-empty text")
        nonempty_strings(
            decision["unresolvedApprovalInputs"],
            f"review-v1.decisions[{index}].unresolvedApprovalInputs",
            3,
        )
        if decision["recommendedOptionId"] != RECOMMENDATIONS[decision_id]:
            fail(f"review-v1.decisions[{index}]: recommendation drifted")
        options = decision["options"]
        if not isinstance(options, list) or len(options) != 3:
            fail(f"review-v1.decisions[{index}].options: expected exactly three options")
        option_ids: set[str] = set()
        recommendation_count = 0
        for option_index, raw_option in enumerate(options):
            option = exact_keys(
                raw_option,
                {"optionId", "disposition", "tradeoff"},
                f"review-v1.decisions[{index}].options[{option_index}]",
            )
            if not all(isinstance(option[field], str) and option[field] for field in option):
                fail(f"review-v1.decisions[{index}].options[{option_index}]: invalid option text")
            option_ids.add(option["optionId"])
            recommendation_count += option["disposition"] == "recommended"
        if option_ids != EXPECTED_OPTIONS[decision_id] or recommendation_count != 1:
            fail(f"review-v1.decisions[{index}].options: option set or disposition drifted")
        recommended = next(option for option in options if option["disposition"] == "recommended")
        if recommended["optionId"] != decision["recommendedOptionId"]:
            fail(f"review-v1.decisions[{index}]: recommended disposition mismatch")
        if not isinstance(decision["proposedContract"], dict) or not decision["proposedContract"]:
            fail(f"review-v1.decisions[{index}].proposedContract: expected a non-empty object")
        contract_text = json.dumps(decision["proposedContract"], sort_keys=True).lower()
        for snippet in REQUIRED_CONTRACT_SNIPPETS[decision_id]:
            if snippet.lower() not in contract_text:
                fail(f"review-v1.decisions[{index}].proposedContract: missing {snippet!r}")
        nonempty_strings(
            decision["rejectionConditions"],
            f"review-v1.decisions[{index}].rejectionConditions",
            3,
        )
        nonempty_strings(
            decision["requiredEvidence"],
            f"review-v1.decisions[{index}].requiredEvidence",
            3,
        )

    floors = root["securityFloors"]
    if not isinstance(floors, list) or len(floors) != len(REQUIRED_SECURITY_FLOORS):
        fail("review-v1.securityFloors: expected exactly nine floors")
    floor_ids: set[str] = set()
    for index, raw_floor in enumerate(floors):
        floor = exact_keys(raw_floor, {"floorId", "contract"}, f"securityFloors[{index}]")
        if not isinstance(floor["floorId"], str) or not floor["floorId"]:
            fail(f"securityFloors[{index}].floorId: invalid")
        if not isinstance(floor["contract"], (str, dict)) or not floor["contract"]:
            fail(f"securityFloors[{index}].contract: invalid")
        floor_ids.add(floor["floorId"])
    if floor_ids != REQUIRED_SECURITY_FLOORS:
        fail("review-v1.securityFloors: canonical security floor set drifted")

    source_root = exact_keys(root["officialSources"], {"verifiedAt", "sources"}, "officialSources")
    if source_root["verifiedAt"] != "2026-07-12":
        fail("review-v1.officialSources.verifiedAt: expected 2026-07-12")
    sources = source_root["sources"]
    if not isinstance(sources, list) or len(sources) != len(REQUIRED_SOURCE_URLS):
        fail("review-v1.officialSources: expected the exact official source set")
    urls: set[str] = set()
    for index, raw_source in enumerate(sources):
        source = exact_keys(raw_source, {"sourceId", "url"}, f"officialSources[{index}]")
        if not isinstance(source["sourceId"], str) or not source["sourceId"]:
            fail(f"officialSources[{index}].sourceId: invalid")
        if not isinstance(source["url"], str):
            fail(f"officialSources[{index}].url: invalid")
        urls.add(source["url"])
    if urls != REQUIRED_SOURCE_URLS:
        fail("review-v1.officialSources: source URL set drifted")

    authorization = exact_keys(
        root["authorization"],
        {
            "librarySelectionAuthorized", "harnessImplementationAuthorized", "networkIOAllowed",
            "socketExecutionAuthorized", "productionDeploymentAuthorized", "nextHandoffAuthorized",
        },
        "review-v1.authorization",
    )
    if any(value is not False for value in authorization.values()):
        fail("review-v1.authorization: all approval gates must remain false")
    if root["reviewOutcome"] != {
        "selectedDecisionCount": 0,
        "recommendationCount": 4,
        "controlledNetworkSpikeStatus": "blocked_on_explicit_selection",
        "artifactCreated": False,
        "handoffCreated": False,
    }:
        fail("review-v1.reviewOutcome: unselected outcome drifted")
    if root["approvalRequired"] != {
        "decisionIds": list(DECISION_ORDER),
        "approvalBoundary": "separate_versioned_decision_before_socket_execution",
    }:
        fail("review-v1.approvalRequired: explicit approval dependency drifted")
    if root["immutability"] != {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_review",
    }:
        fail("review-v1.immutability: closed proposal contract drifted")


def validate_markdown(raw: bytes) -> None:
    text = raw.decode("utf-8")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    expected_headings = [
        "Status",
        "Decision Summary",
        "Official Evidence",
        "Recommended Set",
        "Security Floors",
        "Required Evidence Before Selection",
        "Authorization Boundary",
        "Evidence Boundary",
    ]
    if headings != expected_headings:
        fail(f"review-v1.md: heading order drifted; got {headings}")
    required = (
        "proposed_not_selected", "libjuice-1.7.2", "libnice-0.1.23", "libdatachannel-0.24.3",
        "CryptoKit", "provider-neutral JCA", "Linux network namespaces", "numeric", "egress",
        "librarySelectionAuthorized=false", "networkIOAllowed=false", "socketExecutionAuthorized=false",
        "physical-device", "no execution artifact",
    )
    for snippet in required:
        if snippet.lower() not in text.lower():
            fail(f"review-v1.md: missing {snippet!r}")
    forbidden = (
        "networkIOAllowed=true", "socketExecutionAuthorized=true", "librarySelectionAuthorized=true",
        "ICE is implemented", "NAT traversal is implemented", "production ready",
    )
    for snippet in forbidden:
        if snippet.lower() in text.lower():
            fail(f"review-v1.md: forbidden claim {snippet!r}")


def main() -> int:
    try:
        validate_source_handoff()
        document = parse_json(REVIEW_PATH.read_text(encoding="utf-8"), "review-v1.json")
        validate_document(document)
        validate_markdown(MARKDOWN_PATH.read_bytes())
        for path, expected in GENERATED_ARTIFACT_SHA256.items():
            validate_file_hash(path, expected)
    except (OSError, UnicodeError, ReviewValidationError) as error:
        print(f"P2P/NAT controlled-spike review check failed: {error}", file=sys.stderr)
        return 1
    print("P2P/NAT controlled-spike review passed (4 recommendations proposed; 0 selected; socket gate closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
