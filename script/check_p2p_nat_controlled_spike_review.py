#!/usr/bin/env python3
"""Validate the controlled-spike proposal, approval, and bounded phase-A handoff."""

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
DECISION_PATH = REVIEW_ROOT / "decision-v1.json"
DECISION_MARKDOWN_PATH = REVIEW_ROOT / "decision-v1.md"
CURRENT_HANDOFF_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v4.json"
CURRENT_HANDOFF_MARKDOWN_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/implementation/handoff-v4.md"
PHASE_A_PROGRESS_PATH = REVIEW_ROOT / "phase-a/progress-v1.json"
HANDOFF_SHA256 = "07a45cd49f6c42fe9c4ad722d78a0bf7595b0d38a0d88287d2e0ceeb94e4513c"
GENERATED_ARTIFACT_SHA256 = {
    REVIEW_PATH: "744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62",
    MARKDOWN_PATH: "9fd1d76b94fc834d72cd0c714113fab1e0e4c6e8ec3cee55e213a1a9cb6c781f",
    DECISION_PATH: "1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228",
    DECISION_MARKDOWN_PATH: "95ecd696a1617989e5f354e76fb58f8cc59aa40b69ed110c7af9a883bee4b7d9",
    CURRENT_HANDOFF_PATH: "b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd",
    CURRENT_HANDOFF_MARKDOWN_PATH: "9d185df0d11b49bcdbd1fe0e623d17f28ca6b41272830a72f9ae2e104e108187",
    PHASE_A_PROGRESS_PATH: "3e0d98c2c03e97f7f16e63cca9c545553234ab05ff7d233bae607e09f13738a3",
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
PHASE_A_EVIDENCE = [
    "libjuice_supply_chain_and_source_audit",
    "android_macos_compile_only_integration",
    "cross_platform_session_crypto_vectors",
    "static_harness_and_egress_policy",
    "phase_a_security_review",
]
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
    key: value
    for key, value in DECISION_AUTHORIZATION.items()
    if key != "handoffV4CreationAuthorized"
}
HANDOFF_AUTHORIZATION["implementationAuthorized"] = True
PHASE_A_CONTRACT = {
    "sourceMaterialMode": "offline_user_provided_or_preexisting_workspace_only",
    "offlineSourceInspectionAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "compileOnlyIntegrationAuthorized": True,
    "sessionCryptoVectorImplementationAuthorized": True,
    "staticHarnessImplementationAuthorized": True,
    "sourceExecutionAllowed": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIOAllowed": False,
    "harnessNetworkIOAllowed": False,
    "outputs": [
        "pinned_source_and_supply_chain_manifest",
        "line_referenced_source_audit",
        "android_macos_compile_only_logs",
        "cross_platform_session_crypto_vectors",
        "static_harness_and_egress_policy_evidence",
    ],
}
PHASE_B_CONTRACT = {
    "status": "blocked_on_phase_a_evidence_and_separate_versioned_decision",
    "executionAuthorized": False,
    "networkIOAllowed": False,
    "socketExecutionAuthorized": False,
    "externalEgressAllowed": False,
}
EXPECTED_PROPOSED_CONTRACTS = {
    "networking_library_selection": {
        "candidateOptionId": "libjuice-1.7.2-static-c-abi",
        "integrationShape": "static_library_through_versioned_c_abi_adapter",
        "targetPlatforms": ["android_min_sdk_26", "macos"],
        "requiredProtocolClaimsToAudit": ["rfc8445", "rfc8489", "rfc8656", "rfc7675"],
        "requiredIceBehavior": "full_ice_regular_nomination_single_component_udp",
        "requiredConsentBehavior": "authenticated_consent_freshness_with_fail_closed_traffic_stop",
        "sourceAcquisition": "prohibited_by_this_review_separate_bounded_compile_only_source_audit_authorization_required",
        "sourcePinAfterSelection": "exact_release_tag_and_commit_sha_required_before_compile_only_work",
        "networkExecutionDuringSelection": False,
        "fallbackRule": "reject_libjuice_and_open_a_new_versioned_review_for_libnice_0_1_23_if_compile_only_or_source_audit_fails",
    },
    "session_cryptography_library_selection": {
        "candidateOptionId": "platform-native-p256-hkdf-sha256-aes256gcm",
        "transcript": "existing_canonical_ALP1_transport_neutral_identity_session_transcript",
        "keyAgreement": "ephemeral_p256_ecdh",
        "keyDerivation": "hkdf_sha256_rfc5869_with_role_and_transcript_bound_info",
        "trafficProtection": "aes_256_gcm_with_unique_96_bit_nonce_and_authenticated_ALP1_context",
        "keyConfirmation": "bidirectional_transcript_bound_hmac_sha256_before_application_readiness",
        "macosImplementation": "CryptoKit_P256_HKDF_SHA256_AES_GCM",
        "androidImplementation": "provider_neutral_JCA_EC_secp256r1_KeyAgreement_ECDH_Mac_HmacSHA256_Cipher_AES_GCM_NoPadding",
        "androidMinimumSdk": 26,
        "androidEphemeralKeyRule": "in_memory_provider_neutral_keypair_generation_no_dependency_on_AndroidKeyStore_API_31_ephemeral_ECDH",
        "downgradeRule": "no_alternate_curve_hash_kdf_cipher_dtls_or_plaintext_fallback",
        "networkExecutionDuringSelection": False,
    },
    "isolated_harness_design": {
        "candidateOptionId": "linux-netns-twin-agent-local-services",
        "phaseA": {
            "name": "android_macos_compile_only",
            "socketCreationAllowed": False,
            "networkIOAllowed": False,
            "sourceDownloadAllowed": False,
            "outputs": ["compiler_diagnostics", "linker_symbol_manifest", "abi_manifest", "static_policy_results"],
        },
        "phaseB": {
            "name": "later_approved_linux_namespace_execution",
            "status": "blocked_on_separate_versioned_decision",
            "agentProcessCount": 2,
            "serviceScope": "local_stun_and_turn_only",
            "externalEgressPolicy": "deny_all",
            "namespaceRule": "one_network_namespace_per_agent_plus_local_service_namespace",
            "hostNetworkAccess": False,
            "internetAccess": False,
            "wallClockTimeoutSeconds": 600,
            "setupTimeoutSeconds": 120,
            "sessionEstablishmentTimeoutSeconds": 60,
            "consentObservationSeconds": 45,
            "maximumLocalServiceProcessCount": 2,
            "maximumCpuCoresPerProcess": 1,
            "maximumResidentMemoryMiBPerProcess": 256,
            "maximumFileDescriptorsPerProcess": 64,
            "maximumSocketsPerProcess": 16,
            "maximumCapturedPacketsPerRun": 10_000,
            "maximumCapturedBytesPerRun": 16_777_216,
        },
        "failureRule": "kill_all_processes_and_discard_measurement_on_timeout_ceiling_breach_route_drift_policy_drift_or_witness_failure",
    },
    "socket_destination_and_egress_controls": {
        "candidateOptionId": "numeric-endpoint-allowlist-plus-os-egress-witness",
        "authorizationOrder": [
            "parse_numeric_endpoint_without_resolution",
            "apply_candidate_policy_before_library_call",
            "match_immutable_per_run_protocol_address_port_allowlist",
            "verify_os_deny_all_witness_is_armed",
            "permit_single_bounded_socket_operation",
            "assert_packet_capture_against_same_allowlist",
        ],
        "allowlistMutability": "immutable_after_run_manifest_signature",
        "endpointSyntax": "numeric_ipv4_or_bracketed_numeric_ipv6_plus_explicit_protocol_and_port",
        "prohibitedResolutionAndRouting": [
            "dns", "mdns", "doh", "dot", "http_proxy", "socks_proxy", "pac",
            "environment_proxy", "redirect", "url_fetch", "default_external_route",
        ],
        "osWitness": "deny_all_then_allow_exact_local_numeric_tuples_with_counter_and_kill_switch",
        "packetCaptureAssertion": "every_packet_must_match_manifest_direction_protocol_numeric_address_and_port",
        "secretHandling": "redact_tokens_credentials_keys_nonces_candidate_values_packet_payloads_and_application_content",
        "policyDriftRule": "kill_all_processes_invalidate_run_and_preserve_content_free_reason_code_only",
        "networkExecutionDuringSelection": False,
    },
}
EXPECTED_SECURITY_FLOORS = [
    {
        "floorId": "route_token_separation",
        "contract": "routeToken is never candidate, ICE, STUN, TURN, endpoint, transcript, capability, traffic-key, allowlist, or application authority.",
    },
    {
        "floorId": "endpoint_identity_before_application_readiness",
        "contract": "Both paired endpoint identities and the ALP1 transcript are authenticated before any path becomes application-ready.",
    },
    {
        "floorId": "no_plaintext_or_unauthenticated_downgrade",
        "contract": "Failure of identity, key confirmation, authenticated encryption, consent, or service trust closes the path without plaintext, anonymous, legacy, or lower-suite fallback.",
    },
    {
        "floorId": "default_deny_destination",
        "contract": "Candidate policy and an immutable per-run numeric endpoint allowlist must both authorize the exact protocol, address, and port before socket creation.",
    },
    {
        "floorId": "no_dns_or_proxy",
        "contract": "Hostnames, DNS resolution, DNS rebinding, HTTP proxies, SOCKS proxies, environment proxies, PAC, URL fetches, and redirects are prohibited.",
    },
    {
        "floorId": "no_application_payload_before_identity_and_key_confirmation",
        "contract": "No application payload byte is admitted before path validation, endpoint identity verification, ALP1 transcript binding, and bidirectional key confirmation complete.",
    },
    {
        "floorId": "exact_resource_and_time_ceilings",
        "contract": {
            "agentProcessCount": 2,
            "maximumLocalServiceProcessCount": 2,
            "maximumRunSeconds": 600,
            "maximumSetupSeconds": 120,
            "maximumSessionEstablishmentSeconds": 60,
            "maximumConsentObservationSeconds": 45,
            "maximumCpuCoresPerProcess": 1,
            "maximumResidentMemoryMiBPerProcess": 256,
            "maximumFileDescriptorsPerProcess": 64,
            "maximumSocketsPerProcess": 16,
            "maximumCapturedPacketsPerRun": 10_000,
            "maximumCapturedBytesPerRun": 16_777_216,
        },
    },
    {
        "floorId": "content_free_logs",
        "contract": "Logs contain only bounded reason codes, counters, durations, numeric test endpoint labels, and redacted digests; no secrets, keys, tokens, credentials, candidates, packet payloads, or application content.",
    },
    {
        "floorId": "kill_on_policy_drift",
        "contract": "Any allowlist mutation, unexpected route, DNS or proxy attempt, witness failure, ceiling breach, or packet outside the approved tuple set kills all harness processes and marks the run invalid.",
    },
]
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
EXPECTED_OFFICIAL_SOURCES = [
    {"sourceId": "libjuice_repository", "url": "https://github.com/paullouisageneau/libjuice"},
    {"sourceId": "libjuice_v1_7_2_header", "url": "https://github.com/paullouisageneau/libjuice/blob/v1.7.2/include/juice/juice.h"},
    {"sourceId": "libjuice_v1_7_2_release", "url": "https://github.com/paullouisageneau/libjuice/releases/tag/v1.7.2"},
    {"sourceId": "libnice_site_and_0_1_23_release_index", "url": "https://libnice.freedesktop.org/"},
    {"sourceId": "libnice_nice_agent_reference", "url": "https://libnice.freedesktop.org/libnice/NiceAgent.html"},
    {"sourceId": "libdatachannel_repository", "url": "https://github.com/paullouisageneau/libdatachannel"},
    {"sourceId": "libdatachannel_v0_24_3_release", "url": "https://github.com/paullouisageneau/libdatachannel/releases/tag/v0.24.3"},
    {"sourceId": "libdatachannel_native_c_api_note", "url": "https://github.com/paullouisageneau/libdatachannel/blob/v0.24.3/DOC.md"},
    {"sourceId": "android_cryptography", "url": "https://developer.android.com/privacy-and-security/cryptography"},
    {"sourceId": "android_key_agreement", "url": "https://developer.android.com/reference/javax/crypto/KeyAgreement"},
    {"sourceId": "android_key_gen_parameter_spec", "url": "https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec"},
    {"sourceId": "apple_cryptokit_p256", "url": "https://developer.apple.com/documentation/cryptokit/p256"},
    {"sourceId": "apple_cryptokit_hkdf", "url": "https://developer.apple.com/documentation/cryptokit/hkdf"},
    {"sourceId": "apple_cryptokit_aes_gcm", "url": "https://developer.apple.com/documentation/cryptokit/aes/gcm"},
    {"sourceId": "rfc8445", "url": "https://www.rfc-editor.org/rfc/rfc8445.html"},
    {"sourceId": "rfc8489", "url": "https://www.rfc-editor.org/rfc/rfc8489.html"},
    {"sourceId": "rfc8656", "url": "https://www.rfc-editor.org/rfc/rfc8656.html"},
    {"sourceId": "rfc7675", "url": "https://www.rfc-editor.org/rfc/rfc7675.html"},
    {"sourceId": "rfc5869", "url": "https://www.rfc-editor.org/rfc/rfc5869.html"},
]


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


def type_exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            type_exact_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            type_exact_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected)
        )
    return actual == expected


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
        if not type_exact_equal(
            decision["proposedContract"],
            EXPECTED_PROPOSED_CONTRACTS[decision_id],
        ):
            fail(f"review-v1.decisions[{index}].proposedContract: canonical contract drifted")
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

    if not type_exact_equal(root["securityFloors"], EXPECTED_SECURITY_FLOORS):
        fail("review-v1.securityFloors: canonical floor order, contract, or ceiling drifted")

    source_root = exact_keys(root["officialSources"], {"verifiedAt", "sources"}, "officialSources")
    if source_root["verifiedAt"] != "2026-07-12":
        fail("review-v1.officialSources.verifiedAt: expected 2026-07-12")
    sources = source_root["sources"]
    if not type_exact_equal(sources, EXPECTED_OFFICIAL_SOURCES):
        fail("review-v1.officialSources: canonical source id, URL, or order drifted")

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
    if not type_exact_equal(root["reviewOutcome"], {
        "selectedDecisionCount": 0,
        "recommendationCount": 4,
        "controlledNetworkSpikeStatus": "blocked_on_explicit_selection",
        "artifactCreated": False,
        "handoffCreated": False,
    }):
        fail("review-v1.reviewOutcome: unselected outcome drifted")
    if not type_exact_equal(root["approvalRequired"], {
        "decisionIds": list(DECISION_ORDER),
        "approvalBoundary": "separate_versioned_decision_before_socket_execution",
    }):
        fail("review-v1.approvalRequired: explicit approval dependency drifted")
    if not type_exact_equal(root["immutability"], {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_review",
    }):
        fail("review-v1.immutability: closed proposal contract drifted")


def validate_approval_rows(value: Any, label: str, include_recommendation: bool) -> None:
    if not isinstance(value, list) or len(value) != len(DECISION_ORDER):
        fail(f"{label}: expected exactly four approvals")
    for index, decision_id in enumerate(DECISION_ORDER):
        expected_keys = {"decisionId", "status", "resolution", "approvalSource"}
        if include_recommendation:
            expected_keys.add("recommendedOptionId")
        approval = exact_keys(value[index], expected_keys, f"{label}[{index}]")
        expected = {
            "decisionId": decision_id,
            "status": "approved_for_bounded_phase_a_evidence",
            "resolution": RECOMMENDATIONS[decision_id],
            "approvalSource": "explicit_user_instruction",
        }
        if include_recommendation:
            expected["recommendedOptionId"] = RECOMMENDATIONS[decision_id]
        if not type_exact_equal(approval, expected):
            fail(f"{label}[{index}]: approval order or resolution drifted")


def validate_decision(document: Any) -> None:
    root = exact_keys(
        document,
        {
            "documentType", "schemaVersion", "decisionId", "profileId", "sourceReviewId",
            "sourceReviewPath", "sourceHandoffId", "sourceHandoffPath", "status",
            "approvalSource", "decisionScope", "measurementStatus", "decisionOrder",
            "approvals", "authorization", "requiredPhaseAEvidence", "failurePolicy",
            "nextStep", "immutability",
        },
        "decision-v1",
    )
    expected_root = {
        "documentType": "aetherlink.p2p-nat-controlled-network-spike-approval-decision",
        "schemaVersion": "1.0",
        "decisionId": "production_p2p_nat_v1_controlled_network_spike_decision_v1",
        "profileId": "production_p2p_nat_v1_recommended",
        "sourceReviewId": "production_p2p_nat_v1_controlled_network_spike_review_v1",
        "sourceReviewPath": "review-v1.json",
        "sourceHandoffId": "production_p2p_nat_v1_handoff_v3",
        "sourceHandoffPath": "../implementation/handoff-v3.json",
        "status": "closed",
        "approvalSource": "explicit_user_instruction",
        "decisionScope": "bounded_phase_a_evidence_authorization",
        "measurementStatus": "not_started",
        "decisionOrder": list(DECISION_ORDER),
        "authorization": DECISION_AUTHORIZATION,
        "requiredPhaseAEvidence": PHASE_A_EVIDENCE,
        "failurePolicy": "reject_failed_option_and_require_a_new_versioned_decision_without_socket_or_network_execution",
        "nextStep": "collect_bounded_phase_a_evidence_before_a_separate_socket_execution_decision",
        "immutability": {
            "recordState": "closed",
            "amendmentPolicy": "supersede_with_new_versioned_decision",
        },
    }
    for field, expected in expected_root.items():
        if not type_exact_equal(root[field], expected):
            fail(f"decision-v1.{field}: canonical approval boundary drifted")
    validate_approval_rows(root["approvals"], "decision-v1.approvals", include_recommendation=True)


def validate_handoff_v4(document: Any) -> None:
    root = exact_keys(
        document,
        {
            "documentType", "schemaVersion", "handoffId", "supersedesPath", "profileId",
            "selectionDecisionPath", "preNetworkApprovalDecisionPath", "controlledSpikeReviewPath",
            "controlledSpikeDecisionPath", "status", "productionDesignStatus", "measurementStatus",
            "activeProtocolNamespace", "authorization", "packages", "preNetworkDecisions",
            "controlledSpikeApprovals", "nextDecision", "immutability",
        },
        "handoff-v4",
    )
    expected_root = {
        "documentType": "aetherlink.p2p-nat-bounded-handoff",
        "schemaVersion": "1.0",
        "handoffId": "production_p2p_nat_v1_handoff_v4",
        "supersedesPath": "handoff-v3.json",
        "profileId": "production_p2p_nat_v1_recommended",
        "selectionDecisionPath": "../selection-decision.json",
        "preNetworkApprovalDecisionPath": "../pre-network/decision-v1.json",
        "controlledSpikeReviewPath": "../controlled-network-spike/review-v1.json",
        "controlledSpikeDecisionPath": "../controlled-network-spike/decision-v1.json",
        "status": "closed",
        "productionDesignStatus": "not_implemented",
        "measurementStatus": "not_started",
        "activeProtocolNamespace": ["route.refresh"],
        "authorization": HANDOFF_AUTHORIZATION,
        "nextDecision": {
            "status": "required_after_phase_a_evidence_before_socket_execution",
            "requiredEvidence": PHASE_A_EVIDENCE,
            "networkIOAllowedBeforeDecision": False,
            "socketExecutionAuthorizedBeforeDecision": False,
        },
        "immutability": {
            "recordState": "closed",
            "amendmentPolicy": "supersede_with_new_versioned_handoff",
        },
    }
    for field, expected in expected_root.items():
        if not type_exact_equal(root[field], expected):
            fail(f"handoff-v4.{field}: canonical bounded handoff drifted")

    source_handoff = parse_json(HANDOFF_PATH.read_text(encoding="utf-8"), "handoff-v3")
    packages = root["packages"]
    if not isinstance(packages, list) or len(packages) != 3:
        fail("handoff-v4.packages: expected exactly three packages")
    if not type_exact_equal(packages[:2], source_handoff["packages"][:2]):
        fail("handoff-v4.packages: completed handoff-v3 evidence drifted")
    spike = exact_keys(
        packages[2],
        {
            "packageId", "authorizationStatus", "executionStatus", "executionAuthorized",
            "selectedOptions", "phaseA", "phaseB",
        },
        "handoff-v4 controlled-network-spike",
    )
    expected_spike = {
        "packageId": "controlled-network-spike",
        "authorizationStatus": "authorized_phase_a_evidence_only",
        "executionStatus": "not_started",
        "executionAuthorized": True,
        "selectedOptions": RECOMMENDATIONS,
        "phaseA": PHASE_A_CONTRACT,
        "phaseB": PHASE_B_CONTRACT,
    }
    if not type_exact_equal(spike, expected_spike):
        fail("handoff-v4 controlled-network-spike phase boundary drifted")
    if not type_exact_equal(root["preNetworkDecisions"], source_handoff["preNetworkDecisions"]):
        fail("handoff-v4 pre-network decisions drifted from handoff-v3")
    validate_approval_rows(
        root["controlledSpikeApprovals"],
        "handoff-v4.controlledSpikeApprovals",
        include_recommendation=False,
    )


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


def validate_decision_markdown(raw: bytes) -> None:
    text = raw.decode("utf-8")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    if headings != [
        "Closed Decision",
        "Phase A Authorization",
        "Closed Execution Gates",
        "Required Evidence",
        "Next Gate",
    ]:
        fail(f"decision-v1.md: heading order drifted; got {headings}")
    required = (
        "explicit user instruction", "all four", "bounded phase A evidence",
        "libjuice-1.7.2-static-c-abi", "platform-native-p256-hkdf-sha256-aes256gcm",
        "linux-netns-twin-agent-local-services", "numeric-endpoint-allowlist-plus-os-egress-witness",
        "offline source inspection", "sourceAcquisitionNetworkIOAllowed=false",
        "controlledSpikeNetworkIOAllowed=false", "controlledSpikeSocketExecutionAuthorized=false",
        "phaseBExecutionAuthorized=false", "productionDeploymentAuthorized=false",
        "separate versioned decision",
    )
    for snippet in required:
        if snippet.lower() not in text.lower():
            fail(f"decision-v1.md: missing {snippet!r}")
    for snippet in (
        "controlledSpikeNetworkIOAllowed=true", "controlledSpikeSocketExecutionAuthorized=true",
        "phaseBExecutionAuthorized=true", "productionDeploymentAuthorized=true", "production ready",
    ):
        if snippet.lower() in text.lower():
            fail(f"decision-v1.md: forbidden claim {snippet!r}")


def validate_handoff_v4_markdown(raw: bytes) -> None:
    text = raw.decode("utf-8")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    if headings != [
        "Closed Status", "Preserved Evidence", "Authorized Phase A",
        "Closed Network Boundary", "Next Decision",
    ]:
        fail(f"handoff-v4.md: heading order drifted; got {headings}")
    required = (
        "supersedes `handoff-v3`", "not_implemented", "route.refresh",
        "inspect and hash-pin", "user out of band", "sourceAcquisitionNetworkIOAllowed=false",
        "without sockets", "may not execute",
        "controlledSpikeNetworkIOAllowed=false", "controlledSpikeSocketExecutionAuthorized=false",
        "phaseBExecutionAuthorized=false", "productionDeploymentAuthorized=false",
        "separate versioned decision",
    )
    for snippet in required:
        if snippet.lower() not in text.lower():
            fail(f"handoff-v4.md: missing {snippet!r}")
    for snippet in (
        "controlledSpikeNetworkIOAllowed=true", "controlledSpikeSocketExecutionAuthorized=true",
        "phaseBExecutionAuthorized=true", "productionDeploymentAuthorized=true", "production ready",
    ):
        if snippet.lower() in text.lower():
            fail(f"handoff-v4.md: forbidden claim {snippet!r}")


def main() -> int:
    try:
        validate_source_handoff()
        document = parse_json(REVIEW_PATH.read_text(encoding="utf-8"), "review-v1.json")
        validate_document(document)
        validate_markdown(MARKDOWN_PATH.read_bytes())
        validate_decision(parse_json(DECISION_PATH.read_text(encoding="utf-8"), "decision-v1.json"))
        validate_decision_markdown(DECISION_MARKDOWN_PATH.read_bytes())
        validate_handoff_v4(parse_json(CURRENT_HANDOFF_PATH.read_text(encoding="utf-8"), "handoff-v4.json"))
        validate_handoff_v4_markdown(CURRENT_HANDOFF_MARKDOWN_PATH.read_bytes())
        for path, expected in GENERATED_ARTIFACT_SHA256.items():
            validate_file_hash(path, expected)
    except (OSError, UnicodeError, ReviewValidationError) as error:
        print(f"P2P/NAT controlled-spike review check failed: {error}", file=sys.stderr)
        return 1
    print(
        "P2P/NAT controlled-spike approval passed "
        "(4 recommendations approved for phase A; handoff-v4 closed; "
        "progress-v1 blocked incomplete; socket gate closed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
