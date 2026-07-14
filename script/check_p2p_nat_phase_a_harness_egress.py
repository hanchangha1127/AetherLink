#!/usr/bin/env python3
"""Validate the immutable Phase A static-only harness and egress design."""

from __future__ import annotations

import ast
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_JSON_PATH = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/"
    "phase-a/static-harness-egress-policy-v1.json"
)
ARTIFACT_MARKDOWN_PATH = ARTIFACT_JSON_PATH.with_suffix(".md")
SOURCE_REVIEW_PATH = ARTIFACT_JSON_PATH.parents[1] / "review-v1.json"
SOURCE_DECISION_PATH = ARTIFACT_JSON_PATH.parents[1] / "decision-v1.json"
SOURCE_HANDOFF_PATH = ARTIFACT_JSON_PATH.parents[2] / "implementation/handoff-v4.json"
CHECKER_PATH = ROOT / "script/check_p2p_nat_phase_a_harness_egress.py"
TEST_PATH = ROOT / "script/test_p2p_nat_phase_a_harness_egress.py"

SOURCE_SHA256 = {
    SOURCE_REVIEW_PATH: "744099ec8b0fdd8edf214283661332b0b5deffed7c79211556b98d9ddf544c62",
    SOURCE_DECISION_PATH: "1fd24be7252e25381552d1732c5282f141ef0e9b02118f8c65b246b81a055228",
    SOURCE_HANDOFF_PATH: "b4ecfb30491320383e7ac19cd96fdd7601b91b897bb0fa2019eba187d30509dd",
}
ARTIFACT_SHA256 = {
    ARTIFACT_JSON_PATH: "6934995f310449fa675348c0314ea5bac2991693f1e1d080aa469d7d856ec9f5",
    ARTIFACT_MARKDOWN_PATH: "0578c5f6b89bc3db5cb1ce6ed24f62bad32898b923411759dbf55f946d2fb61b",
}

TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "artifactId", "profileId", "sourceReview",
    "sourceDecision", "sourceHandoff", "artifactStatus", "executionStatus",
    "measurementStatus", "scope", "authorization", "topology", "tuplePolicy",
    "denyAllWitness", "resourceCeilings", "evidencePolicy", "driftPolicy", "phaseB",
    "immutability",
}

EXPECTED_AUTHORIZATION = {
    "staticHarnessImplementationAuthorized": True,
    "sourceAcquisitionNetworkIOAllowed": False,
    "sourceExecutionAllowed": False,
    "socketCreationAllowed": False,
    "runtimeNetworkIOAllowed": False,
    "harnessNetworkIOAllowed": False,
    "controlledSpikeNetworkIOAllowed": False,
    "controlledSpikeSocketExecutionAuthorized": False,
    "phaseBExecutionAuthorized": False,
    "phaseBNetworkIOAllowed": False,
    "phaseBSocketExecutionAuthorized": False,
    "phaseBExternalEgressAllowed": False,
    "productionNetworkIOAllowed": False,
    "productionDeploymentAuthorized": False,
}

EXPECTED_TOPOLOGY = {
    "model": "non_executable_three_namespace_design",
    "namespaceCount": 3,
    "hostNetworkAttached": False,
    "defaultRoutePresent": False,
    "internetReachable": False,
    "namespaces": [
        {
            "namespaceId": "agent-a",
            "role": "agent",
            "processCeiling": 1,
            "processIds": ["agent_a"],
            "interfaces": [{
                "linkId": "agent-a-services",
                "ipv4Interface": "192.0.2.2/30",
                "ipv6Interface": "2001:db8:1::2/126",
                "peerNamespaceId": "local-services",
            }],
        },
        {
            "namespaceId": "agent-b",
            "role": "agent",
            "processCeiling": 1,
            "processIds": ["agent_b"],
            "interfaces": [{
                "linkId": "agent-b-services",
                "ipv4Interface": "198.51.100.2/30",
                "ipv6Interface": "2001:db8:2::2/126",
                "peerNamespaceId": "local-services",
            }],
        },
        {
            "namespaceId": "local-services",
            "role": "local_stun_turn_fixture",
            "processCeiling": 2,
            "processIds": ["stun_service", "turn_service"],
            "interfaces": [
                {
                    "linkId": "agent-a-services",
                    "ipv4Interface": "192.0.2.1/30",
                    "ipv6Interface": "2001:db8:1::1/126",
                    "peerNamespaceId": "agent-a",
                },
                {
                    "linkId": "agent-b-services",
                    "ipv4Interface": "198.51.100.1/30",
                    "ipv6Interface": "2001:db8:2::1/126",
                    "peerNamespaceId": "agent-b",
                },
            ],
        },
    ],
    "addressRule": "rfc5737_ipv4_and_rfc3849_ipv6_documentation_ranges_only",
    "connectivityRule": (
        "agents_reach_only_their_direct_local_services_link_and_never_each_other_or_the_host"
    ),
}


def flow(
    flow_id: str,
    agent: str,
    service: str,
    protocol: str,
    source_address: str,
    source_port: int,
    destination_address: str,
    destination_port: int,
) -> dict[str, object]:
    return {
        "flowId": flow_id,
        "agentNamespaceId": agent,
        "service": service,
        "protocol": protocol,
        "sourceAddress": source_address,
        "sourcePort": source_port,
        "destinationAddress": destination_address,
        "destinationPort": destination_port,
    }


EXPECTED_FLOWS = [
    flow("agent-a-ipv4-stun-udp", "agent-a", "stun", "udp", "192.0.2.2", 41000, "192.0.2.1", 3478),
    flow("agent-a-ipv4-turn-udp", "agent-a", "turn", "udp", "192.0.2.2", 41001, "192.0.2.1", 3478),
    flow("agent-a-ipv6-stun-udp", "agent-a", "stun", "udp", "2001:db8:1::2", 41100, "2001:db8:1::1", 3478),
    flow("agent-a-ipv6-turn-udp", "agent-a", "turn", "udp", "2001:db8:1::2", 41101, "2001:db8:1::1", 3478),
    flow("agent-b-ipv4-stun-udp", "agent-b", "stun", "udp", "198.51.100.2", 42000, "198.51.100.1", 3478),
    flow("agent-b-ipv4-turn-udp", "agent-b", "turn", "udp", "198.51.100.2", 42001, "198.51.100.1", 3478),
    flow("agent-b-ipv6-stun-udp", "agent-b", "stun", "udp", "2001:db8:2::2", 42100, "2001:db8:2::1", 3478),
    flow("agent-b-ipv6-turn-udp", "agent-b", "turn", "udp", "2001:db8:2::2", 42101, "2001:db8:2::1", 3478),
]

EXPECTED_TUPLE_POLICY = {
    "mode": "immutable_exact_bidirectional_five_tuple_flows",
    "allowlistMutability": "immutable_after_static_manifest_hash",
    "implicitTuplesAllowed": False,
    "dnsResolutionAllowed": False,
    "proxyUseAllowed": False,
    "redirectFollowingAllowed": False,
    "requiredIceBehavior": "full_ice_regular_nomination_single_component_udp",
    "flows": EXPECTED_FLOWS,
    "responseRule": "only_the_exact_reverse_of_a_listed_flow_is_allowed",
    "packetAssertion": "every_observed_packet_must_match_one_listed_flow_or_its_exact_reverse",
    "futurePhaseBRunManifest": {
        "requiredBeforeExecution": True,
        "manifestPresent": False,
        "manifest": None,
        "signatureRequiredBeforeExecution": True,
        "signaturePresent": False,
        "signature": None,
        "executionAuthorized": False,
        "networkIOAllowed": False,
        "socketExecutionAuthorized": False,
    },
}


def intent_vector(vector_id: str, attempt_class: str, value: str, reason: str) -> dict[str, str]:
    return {
        "vectorId": vector_id,
        "attemptClass": attempt_class,
        "input": value,
        "expectedReasonCode": reason,
    }


EXPECTED_INTENT_VECTORS = [
    intent_vector("hostname-dns", "dns", "stun.invalid:3478", "INTENT_DNS_PROHIBITED"),
    intent_vector("mdns-name", "mdns", "fixture.local:3478", "INTENT_MDNS_PROHIBITED"),
    intent_vector("doh-endpoint", "doh", "https://203.0.113.53/dns-query", "INTENT_DOH_PROHIBITED"),
    intent_vector("dot-endpoint", "dot", "203.0.113.53:853", "INTENT_DOT_PROHIBITED"),
    intent_vector("https-url", "url_fetch", "https://192.0.2.1/fixture", "INTENT_URL_PROHIBITED"),
    intent_vector("http-proxy", "http_proxy", "http://192.0.2.9:8080", "INTENT_PROXY_PROHIBITED"),
    intent_vector("socks-proxy", "socks_proxy", "socks5://[2001:db8:1::9]:1080", "INTENT_PROXY_PROHIBITED"),
    intent_vector("pac-config", "pac", "PROXY 192.0.2.9:8080", "INTENT_PAC_PROHIBITED"),
    intent_vector("environment-proxy", "environment_proxy", "HTTPS_PROXY=http://192.0.2.9:8080", "INTENT_ENVIRONMENT_PROXY_PROHIBITED"),
    intent_vector("redirect-target", "redirect", "203.0.113.254:443", "INTENT_REDIRECT_PROHIBITED"),
    intent_vector("wildcard-address", "wildcard", "0.0.0.0:3478", "INTENT_WILDCARD_PROHIBITED"),
    intent_vector("port-range", "port_range", "192.0.2.1:3478-5349", "INTENT_PORT_RANGE_PROHIBITED"),
    intent_vector("malformed-numeric", "malformed_numeric", "192.0.2.999:3478", "INTENT_MALFORMED_NUMERIC_PROHIBITED"),
    intent_vector("default-route-injection", "route_mutation", "0.0.0.0/0", "INTENT_ROUTE_DRIFT"),
    intent_vector("allowlist-mutation", "allowlist_mutation", "append tcp 203.0.113.254:443", "INTENT_ALLOWLIST_DRIFT"),
]


def packet_vector(
    vector_id: str,
    namespace_id: str,
    protocol: str,
    source_address: str,
    source_port: int,
    destination_address: str,
    destination_port: int,
    reason: str,
) -> dict[str, object]:
    return {
        "vectorId": vector_id,
        "namespaceId": namespace_id,
        "protocol": protocol,
        "sourceAddress": source_address,
        "sourcePort": source_port,
        "destinationAddress": destination_address,
        "destinationPort": destination_port,
        "expectedReasonCode": reason,
    }


EXPECTED_PACKET_VECTORS = [
    packet_vector("external-ipv4", "agent-a", "tcp", "192.0.2.2", 41900, "203.0.113.254", 443, "PACKET_TUPLE_DENIED"),
    packet_vector("external-ipv6", "agent-a", "tcp", "2001:db8:1::2", 41901, "2001:db8:ffff::254", 443, "PACKET_TUPLE_DENIED"),
    packet_vector("external-udp-ipv4", "agent-a", "udp", "192.0.2.2", 41910, "203.0.113.254", 3478, "PACKET_TUPLE_DENIED"),
    packet_vector("external-udp-ipv6", "agent-a", "udp", "2001:db8:1::2", 41911, "2001:db8:ffff::254", 3478, "PACKET_TUPLE_DENIED"),
    packet_vector("metadata-ipv4", "agent-b", "tcp", "198.51.100.2", 42900, "169.254.169.254", 80, "PACKET_METADATA_DENIED"),
    packet_vector("dns-ipv4", "agent-b", "udp", "198.51.100.2", 42901, "203.0.113.53", 53, "PACKET_DNS_DENIED"),
    packet_vector("agent-to-agent", "agent-a", "udp", "192.0.2.2", 41902, "198.51.100.2", 42000, "PACKET_CROSS_AGENT_DENIED"),
    packet_vector("service-wrong-port", "agent-a", "udp", "192.0.2.2", 41903, "192.0.2.1", 3479, "PACKET_TUPLE_DENIED"),
    packet_vector("ipv4-multicast", "agent-b", "udp", "198.51.100.2", 42902, "224.0.0.251", 5353, "PACKET_MULTICAST_DENIED"),
    packet_vector("ipv6-multicast", "agent-b", "udp", "2001:db8:2::2", 42903, "ff02::fb", 5353, "PACKET_MULTICAST_DENIED"),
    packet_vector("ipv4-mapped-ipv6", "agent-a", "tcp", "2001:db8:1::2", 41904, "::ffff:203.0.113.254", 443, "PACKET_MAPPED_ADDRESS_DENIED"),
    packet_vector("loopback-ipv4", "agent-a", "udp", "192.0.2.2", 41905, "127.0.0.1", 3478, "PACKET_LOOPBACK_DENIED"),
    packet_vector("loopback-ipv6", "agent-a", "udp", "2001:db8:1::2", 41906, "::1", 3478, "PACKET_LOOPBACK_DENIED"),
    packet_vector("link-local-ipv4", "agent-b", "udp", "198.51.100.2", 42904, "169.254.10.10", 3478, "PACKET_LINK_LOCAL_DENIED"),
    packet_vector("link-local-ipv6", "agent-b", "udp", "2001:db8:2::2", 42905, "fe80::1", 3478, "PACKET_LINK_LOCAL_DENIED"),
    packet_vector("broadcast-ipv4", "agent-a", "udp", "192.0.2.2", 41907, "255.255.255.255", 3478, "PACKET_BROADCAST_DENIED"),
    packet_vector("unlisted-private-ipv4", "agent-b", "udp", "198.51.100.2", 42906, "10.0.0.1", 3478, "PACKET_UNLISTED_PRIVATE_DENIED"),
    packet_vector("unspecified-ipv4", "agent-a", "udp", "192.0.2.2", 41908, "0.0.0.0", 3478, "PACKET_UNSPECIFIED_DENIED"),
    packet_vector("unspecified-ipv6", "agent-a", "udp", "2001:db8:1::2", 41909, "::", 3478, "PACKET_UNSPECIFIED_DENIED"),
]

EXPECTED_DENY_ALL_WITNESS = {
    "defaultPolicy": "deny_all",
    "requiredOutcome": "reject_before_io_or_witness_drop_then_kill_and_invalidate",
    "intentVectors": EXPECTED_INTENT_VECTORS,
    "packetVectors": EXPECTED_PACKET_VECTORS,
    "witnessIndependenceRule": (
        "intent_policy_and_packet_observation_must_fail_independently_and_either_failure_kills_the_run"
    ),
}

EXPECTED_RESOURCE_CEILINGS = {
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
    "maximumCapturedPacketsPerRun": 10000,
    "maximumCapturedBytesPerRun": 16777216,
}

EXPECTED_EVIDENCE_POLICY = {
    "mode": "content_free_bounded_records_only",
    "allowedRecordKeys": [
        "reasonCode", "counterName", "count", "durationMillis", "numericEndpointLabel",
        "redactedDigest",
    ],
    "prohibitedContentClasses": [
        "secret", "key", "token", "credential", "nonce", "raw_candidate", "packet_payload",
        "application_content", "hostname", "url", "command_line", "environment_value",
    ],
    "packetPayloadRetentionBytes": 0,
    "applicationPayloadAdmissionBytes": 0,
    "rawPacketRetentionAllowed": False,
    "rawCandidateRetentionAllowed": False,
    "secretRetentionAllowed": False,
    "reasonCodeRegex": "^[A-Z][A-Z0-9_]{0,63}$",
    "counterNameRegex": "^[a-z][a-z0-9_]{0,63}$",
    "numericEndpointLabelRegex": "^endpoint_[0-9]{1,4}$",
    "redactedDigestRegex": "^[0-9a-f]{64}$",
    "maximumDurationMillis": 600000,
    "maximumCounterValue": 16777216,
    "retainedRuntimeEvents": [],
    "digestRule": "sha256_lowercase_hex_over_redacted_structural_record_only",
    "failureRetentionRule": (
        "retain_only_bounded_reason_code_counter_duration_numeric_label_and_redacted_digest"
    ),
}

EXPECTED_DRIFT_POLICY = {
    "terminationProcessIds": ["agent_a", "agent_b", "stun_service", "turn_service"],
    "actions": [
        "terminate_all_listed_processes",
        "invalidate_run",
        "discard_all_measurements",
        "retain_content_free_drift_record_only",
    ],
    "measurementDisposition": "discard_all_measurements",
    "triggers": [
        "allowlist_mutation", "unexpected_route", "dns_attempt", "proxy_attempt",
        "redirect_attempt", "witness_failure", "resource_ceiling_breach",
        "time_ceiling_breach", "packet_outside_exact_tuple_set", "payload_observed",
        "evidence_content_violation", "namespace_topology_drift",
    ],
    "continuationAllowedAfterDrift": False,
    "validMeasurementAllowedAfterDrift": False,
}

EXPECTED_PHASE_B = {
    "status": "blocked_on_phase_a_evidence_and_separate_versioned_decision",
    "proofStatus": "unproven",
    "executionStatus": "not_executed",
    "measurementStatus": "not_started",
    "executionAuthorized": False,
    "networkIOAllowed": False,
    "socketExecutionAuthorized": False,
    "externalEgressAllowed": False,
    "requiredDecision": "separate_versioned_decision_after_phase_a_security_review",
}

EXPECTED_IMMUTABILITY = {
    "recordState": "closed",
    "artifactHashAuthority": "script/check_p2p_nat_phase_a_harness_egress.py",
    "hashAlgorithm": "sha256",
    "coveredArtifacts": [
        "static-harness-egress-policy-v1.json",
        "static-harness-egress-policy-v1.md",
    ],
    "amendmentPolicy": "supersede_with_new_versioned_static_design",
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

HANDOFF_PHASE_A = {
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

HANDOFF_PHASE_B = {
    "status": "blocked_on_phase_a_evidence_and_separate_versioned_decision",
    "executionAuthorized": False,
    "networkIOAllowed": False,
    "socketExecutionAuthorized": False,
    "externalEgressAllowed": False,
}

FORBIDDEN_IMPORT_ROOTS = {
    "socket", "socketserver", "ssl", "subprocess", "multiprocessing", "asyncio", "os",
    "posix", "pty", "ctypes", "fcntl", "requests", "httpx", "aiohttp", "urllib", "http",
    "ftplib", "telnetlib", "smtplib", "imaplib", "webbrowser", "importlib", "builtins",
}
FORBIDDEN_DYNAMIC_NAMES = {
    "__builtins__", "__import__", "eval", "exec", "compile", "getattr",
}
FORBIDDEN_CALLS = {
    "os.system", "os.popen", "os.fork", "os.forkpty", "os.posix_spawn", "os.posix_spawnp",
    "pty.spawn", "asyncio.create_subprocess_exec", "asyncio.create_subprocess_shell",
}
FORBIDDEN_CALL_PREFIXES = (
    "socket.", "subprocess.", "multiprocessing.", "requests.", "httpx.",
    "urllib.request.", "http.client.", "ftplib.", "telnetlib.", "os.exec", "os.spawn",
)
FORBIDDEN_QUALIFIED_REFERENCES = {"sys.modules"}


class HarnessEgressValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise HarnessEgressValidationError(message)


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
        fail(f"{label}: keys differ; missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")
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
    if review.get("reviewId") != "production_p2p_nat_v1_controlled_network_spike_review_v1":
        fail("review-v1.json: review id drifted")
    recursive_exact(review.get("authorization"), REVIEW_AUTHORIZATION, "review.authorization")
    floors = {item.get("floorId"): item.get("contract") for item in review.get("securityFloors", [])}
    recursive_exact(
        floors.get("exact_resource_and_time_ceilings"),
        EXPECTED_RESOURCE_CEILINGS,
        "review.securityFloors.exact_resource_and_time_ceilings",
    )

    decision = load_json(SOURCE_DECISION_PATH)
    if decision.get("decisionId") != "production_p2p_nat_v1_controlled_network_spike_decision_v1":
        fail("decision-v1.json: decision id drifted")
    if decision.get("sourceReviewId") != "production_p2p_nat_v1_controlled_network_spike_review_v1":
        fail("decision-v1.json: source review id drifted")
    if decision.get("decisionScope") != "bounded_phase_a_evidence_authorization":
        fail("decision-v1.json: Phase A decision scope drifted")
    recursive_exact(decision.get("authorization"), DECISION_AUTHORIZATION, "decision.authorization")

    handoff = load_json(SOURCE_HANDOFF_PATH)
    if handoff.get("handoffId") != "production_p2p_nat_v1_handoff_v4":
        fail("handoff-v4.json: handoff id drifted")
    recursive_exact(handoff.get("authorization"), HANDOFF_AUTHORIZATION, "handoff.authorization")
    packages = handoff.get("packages")
    if not isinstance(packages, list):
        fail("handoff.packages: expected list")
    controlled = [item for item in packages if isinstance(item, dict) and item.get("packageId") == "controlled-network-spike"]
    if len(controlled) != 1:
        fail("handoff.packages: expected exactly one controlled-network-spike package")
    recursive_exact(controlled[0].get("phaseA"), HANDOFF_PHASE_A, "handoff.controlled.phaseA")
    recursive_exact(controlled[0].get("phaseB"), HANDOFF_PHASE_B, "handoff.controlled.phaseB")
    recursive_exact(
        handoff.get("nextDecision"),
        {
            "status": "required_after_phase_a_evidence_before_socket_execution",
            "requiredEvidence": [
                "libjuice_supply_chain_and_source_audit",
                "android_macos_compile_only_integration",
                "cross_platform_session_crypto_vectors",
                "static_harness_and_egress_policy",
                "phase_a_security_review",
            ],
            "networkIOAllowedBeforeDecision": False,
            "socketExecutionAuthorizedBeforeDecision": False,
        },
        "handoff.nextDecision",
    )


def validate_ip_model(document: dict[str, Any]) -> None:
    expected_networks = {
        ipaddress.ip_network("192.0.2.0/30"),
        ipaddress.ip_network("198.51.100.0/30"),
        ipaddress.ip_network("2001:db8:1::/126"),
        ipaddress.ip_network("2001:db8:2::/126"),
    }
    observed_networks: set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()
    for namespace in document["topology"]["namespaces"]:
        for interface in namespace["interfaces"]:
            for family_key in ("ipv4Interface", "ipv6Interface"):
                try:
                    parsed = ipaddress.ip_interface(interface[family_key])
                except ValueError as error:
                    fail(f"topology {family_key}: invalid interface: {error}")
                observed_networks.add(parsed.network)
                if family_key == "ipv4Interface" and parsed.version != 4:
                    fail("topology.ipv4Interface: expected IPv4")
                if family_key == "ipv6Interface" and parsed.version != 6:
                    fail("topology.ipv6Interface: expected IPv6")
    if observed_networks != expected_networks:
        fail("topology: documentation network set drifted")

    for collection, label in (
        (document["tuplePolicy"]["flows"], "tuplePolicy.flows"),
        (document["denyAllWitness"]["packetVectors"], "denyAllWitness.packetVectors"),
    ):
        for index, item in enumerate(collection):
            try:
                source = ipaddress.ip_address(item["sourceAddress"])
                destination = ipaddress.ip_address(item["destinationAddress"])
            except ValueError as error:
                fail(f"{label}[{index}]: invalid numeric address: {error}")
            if source.version != destination.version:
                fail(f"{label}[{index}]: address families differ")
            for port_key in ("sourcePort", "destinationPort"):
                port = item[port_key]
                if type(port) is not int or not 1 <= port <= 65535:
                    fail(f"{label}[{index}].{port_key}: expected exact integer port")

    for index, item in enumerate(document["tuplePolicy"]["flows"]):
        destination = ipaddress.ip_address(item["destinationAddress"])
        source = ipaddress.ip_address(item["sourceAddress"])
        if item["protocol"] != "udp" or item["destinationPort"] != 3478:
            fail(f"tuplePolicy.flows[{index}]: only exact UDP port 3478 flows are allowed")
        if source.is_unspecified or source.is_multicast or destination.is_unspecified or destination.is_multicast:
            fail(f"tuplePolicy.flows[{index}]: wildcard or multicast address prohibited")
        if isinstance(source, ipaddress.IPv6Address) and source.ipv4_mapped is not None:
            fail(f"tuplePolicy.flows[{index}]: mapped source prohibited")
        if isinstance(destination, ipaddress.IPv6Address) and destination.ipv4_mapped is not None:
            fail(f"tuplePolicy.flows[{index}]: mapped destination prohibited")


def validate_evidence_bounds(document: dict[str, Any]) -> None:
    policy = document["evidencePolicy"]
    regex_cases = {
        "reasonCodeRegex": ("PACKET_TUPLE_DENIED", "packet-tuple-denied"),
        "counterNameRegex": ("captured_packets", "CAPTURED_PACKETS"),
        "numericEndpointLabelRegex": ("endpoint_42", "endpoint_10000"),
        "redactedDigestRegex": ("a" * 64, "a" * 63),
    }
    for key, (accepted, rejected) in regex_cases.items():
        try:
            pattern = re.compile(policy[key])
        except re.error as error:
            fail(f"evidencePolicy.{key}: invalid regex: {error}")
        if pattern.fullmatch(accepted) is None or pattern.fullmatch(rejected) is not None:
            fail(f"evidencePolicy.{key}: bounded matching behavior drifted")
    if policy["maximumDurationMillis"] != document["resourceCeilings"]["maximumRunSeconds"] * 1000:
        fail("evidencePolicy.maximumDurationMillis: must equal the exact run ceiling")
    if policy["maximumCounterValue"] != document["resourceCeilings"]["maximumCapturedBytesPerRun"]:
        fail("evidencePolicy.maximumCounterValue: must equal the largest retained numeric ceiling")
    if policy["retainedRuntimeEvents"] != []:
        fail("evidencePolicy.retainedRuntimeEvents: execution has not occurred")


def validate_document(document: Any) -> None:
    root = exact_keys(document, TOP_LEVEL_KEYS, "artifact")
    recursive_exact(root["documentType"], "aetherlink.p2p-nat-phase-a-static-harness-egress-policy", "artifact.documentType")
    recursive_exact(root["schemaVersion"], "1.0", "artifact.schemaVersion")
    recursive_exact(root["artifactId"], "production_p2p_nat_v1_phase_a_static_harness_egress_policy_v1", "artifact.artifactId")
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
    recursive_exact(root["artifactStatus"], "static_design_complete", "artifact.artifactStatus")
    recursive_exact(root["executionStatus"], "not_executed", "artifact.executionStatus")
    recursive_exact(root["measurementStatus"], "not_started", "artifact.measurementStatus")
    recursive_exact(root["scope"], "non_executable_phase_a_static_design_evidence_only", "artifact.scope")
    recursive_exact(root["authorization"], EXPECTED_AUTHORIZATION, "artifact.authorization")
    recursive_exact(root["topology"], EXPECTED_TOPOLOGY, "artifact.topology")
    recursive_exact(root["tuplePolicy"], EXPECTED_TUPLE_POLICY, "artifact.tuplePolicy")
    recursive_exact(root["denyAllWitness"], EXPECTED_DENY_ALL_WITNESS, "artifact.denyAllWitness")
    recursive_exact(root["resourceCeilings"], EXPECTED_RESOURCE_CEILINGS, "artifact.resourceCeilings")
    recursive_exact(root["evidencePolicy"], EXPECTED_EVIDENCE_POLICY, "artifact.evidencePolicy")
    recursive_exact(root["driftPolicy"], EXPECTED_DRIFT_POLICY, "artifact.driftPolicy")
    recursive_exact(root["phaseB"], EXPECTED_PHASE_B, "artifact.phaseB")
    recursive_exact(root["immutability"], EXPECTED_IMMUTABILITY, "artifact.immutability")
    validate_ip_model(root)
    validate_evidence_bounds(root)


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
                if alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                    fail(f"{label}:{node.lineno}: forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                fail(f"{label}:{node.lineno}: forbidden import from {module}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in FORBIDDEN_IMPORT_ROOTS or node.id in FORBIDDEN_DYNAMIC_NAMES:
                fail(f"{label}:{node.lineno}: forbidden dynamic or capability reference {node.id}")
        elif isinstance(node, ast.Attribute):
            name = qualified_name(node)
            root = name.split(".")[0] if name else ""
            if root in FORBIDDEN_IMPORT_ROOTS or any(
                name == forbidden or name.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_QUALIFIED_REFERENCES
            ):
                fail(f"{label}:{node.lineno}: forbidden dynamic or capability reference {name}")
        elif isinstance(node, ast.Call):
            name = qualified_name(node.func)
            if name and (name in FORBIDDEN_CALLS or name.startswith(FORBIDDEN_CALL_PREFIXES)):
                fail(f"{label}:{node.lineno}: forbidden network or process-launch call {name}")


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
    except HarnessEgressValidationError as error:
        print(f"P2P/NAT Phase A static harness/egress validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "P2P/NAT Phase A static harness/egress validation passed "
        "(static design complete; execution not executed; measurement not started; Phase B blocked)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
