#!/usr/bin/env python3
"""Validate the selection-gated production P2P NAT security design."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = ROOT / "docs/security-hardening/production-p2p-nat-v1"
PRE_NETWORK_HANDOFF_PATH = DESIGN_ROOT / "implementation/handoff-v3.json"
CURRENT_HANDOFF_PATH = DESIGN_ROOT / "implementation/handoff-v4.json"
SESSION_CRYPTO_VALIDATOR_PATH = ROOT / "script/check_p2p_nat_session_crypto_vectors.py"
HARNESS_EGRESS_VALIDATOR_PATH = ROOT / "script/check_p2p_nat_phase_a_harness_egress.py"
OFFLINE_SOURCE_VALIDATOR_PATH = ROOT / "script/check_p2p_nat_libjuice_offline_source.py"
COMPILE_ONLY_VALIDATOR_PATH = ROOT / "script/check_p2p_nat_libjuice_compile_only.py"
PHASE_A_STATIC_PYTHON_PATHS = (
    SESSION_CRYPTO_VALIDATOR_PATH,
    ROOT / "script/test_p2p_nat_session_crypto_vectors.py",
    HARNESS_EGRESS_VALIDATOR_PATH,
    ROOT / "script/test_p2p_nat_phase_a_harness_egress.py",
    OFFLINE_SOURCE_VALIDATOR_PATH,
    ROOT / "script/test_p2p_nat_libjuice_offline_source.py",
    COMPILE_ONLY_VALIDATOR_PATH,
    ROOT / "script/test_p2p_nat_libjuice_compile_only.py",
)
PHASE_A_STATIC_EVIDENCE_SHA256 = {
    ROOT / "apps/macos/P2PNATContracts/Sources/P2PNATSessionCrypto.swift": "8933edff1e9ed11ac510f4c5c394fa924f5764057e187d127b485661cdc135bb",
    ROOT / "apps/macos/P2PNATContracts/Tests/P2PNATSessionCryptoVectorTests.swift": "c39c4e37a3f022698d9994804972a0bafd14000d010baa99bc6928066ef87acd",
    ROOT / "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCrypto.kt": "a7222474e0b38e061a1d04ba5993af844f8f1cebaed36496403ae3bf47bd5b93",
    ROOT / "apps/android/core/protocol/src/test/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCryptoVectorTest.kt": "3a28cef4d942dac397bd443ec3b7e0f9c96e2a0c9ccda836ec3c49f178367bf4",
    ROOT / "shared/protocol/fixtures/production-p2p-nat-v1-session-crypto-vectors.json": "4693f71330b5f40f9b99b4445c24fba8fa0939c4ae76f8b9bf3c9644b08f29c9",
    SESSION_CRYPTO_VALIDATOR_PATH: "c8f51de5a77599617eb24df3f767569e778e3ac327a8eae7e3fdad6fcad949ee",
    ROOT / "script/test_p2p_nat_session_crypto_vectors.py": "37ba5844a7822d65bca27b312718c7a43c30febc2c0ca83976b91a246e09b526",
    DESIGN_ROOT / "controlled-network-spike/phase-a/static-harness-egress-policy-v1.json": "6934995f310449fa675348c0314ea5bac2991693f1e1d080aa469d7d856ec9f5",
    DESIGN_ROOT / "controlled-network-spike/phase-a/static-harness-egress-policy-v1.md": "0578c5f6b89bc3db5cb1ce6ed24f62bad32898b923411759dbf55f946d2fb61b",
    HARNESS_EGRESS_VALIDATOR_PATH: "052b4e3358cd7803e640a491e55bd1cab28a0a6ef5f4cc8cbbdd1f960f00bdf1",
    ROOT / "script/test_p2p_nat_phase_a_harness_egress.py": "597888e9600c2b7aabd459959ad05f91b0d0f51e696a6a233bc95ac99c95f608",
    DESIGN_ROOT / "controlled-network-spike/phase-a/offline-source-intake-v1.json": "3359624f1fa1474b2bfd2acd4e3591fd1e0a8cd5840cda4372327f25dfc68850",
    DESIGN_ROOT / "controlled-network-spike/phase-a/offline-source-intake-v1.md": "c186c4bed45a6edd9d270062ac9927839ab1f5c8f5c66eab966dfc9a61c0d2ee",
    OFFLINE_SOURCE_VALIDATOR_PATH: "229d703b6d1ac789bbd34d7ce64fed6adbd52153ebb7358ae55ba71b5486eda1",
    ROOT / "script/test_p2p_nat_libjuice_offline_source.py": "93b7572d795114f92d6dae4e3b8de51a30fe2bdfc2a3d08f8c72b8f521204045",
    DESIGN_ROOT / "controlled-network-spike/phase-a/libjuice-compile-only-contract-v1.json": "2664736c7b783d650eabcd8bc4ad5391babd456d3b7df596dff2171eba7d84b4",
    DESIGN_ROOT / "controlled-network-spike/phase-a/libjuice-compile-only-contract-v1.md": "6e181de962f961ccf1b35f020e83e2cceb3829e13bf824c7fa68f17677d09420",
    COMPILE_ONLY_VALIDATOR_PATH: "2fd88bf6aa418920cb13f244215ce91a97f135a94c6a9c79d3658b62e3d570eb",
    ROOT / "script/test_p2p_nat_libjuice_compile_only.py": "df9dfd78cd2b35274d5fe5d08c4114d091fd27db75f5856794e3cf215b134c13",
}
EVIDENCE_COLLECTION_SHA256 = "8741927642b8697e517dccee7dc639d279037f530b442f9ddf9873cbd2294a92"
EXPECTED_EVIDENCE_PATHS = (
    "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt",
    "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt",
    "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt",
    "apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeConnectionManager.kt",
    "apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimePeerToPeerRoutePreparation.kt",
    "apps/macos/CompanionCore/Sources/CompanionAppModel.swift",
    "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift",
    "apps/macos/CompanionCore/Sources/MacRuntimeConnectionManager.swift",
    "apps/macos/Pairing/Sources/PairingCoordinator.swift",
    "apps/macos/Transport/Sources/RuntimeTransport.swift",
    "packages/protocol-schema/pairing-qr.schema.json",
    "packages/protocol-schema/protocol.schema.json",
    "shared/protocol/fixtures/macos-compact-p2p-rendezvous-pairing-uri.txt",
)
EVIDENCE_IDS = {
    f"E{index:03d}": path
    for index, path in enumerate(EXPECTED_EVIDENCE_PATHS, start=1)
}
REQUIRED_TRADEOFFS = {
    "security",
    "performance",
    "memory",
    "reliability",
    "operability",
    "migration",
}
EXPECTED_OPTIONS = {
    "authenticated-rendezvous-and-candidate-protection": (
        "relay-only-sealed-signaling",
        "authenticated-encrypted-ice-turn",
        "decentralized-rendezvous",
    ),
    "identity-bound-traversal-and-relay-fallback": (
        "transport-neutral-identity-session",
        "ice-quic-identity-session",
        "relay-first-direct-promotion",
    ),
}
EXPECTED_OPTION_KINDS = {
    "relay-only-sealed-signaling": "baseline",
    "authenticated-encrypted-ice-turn": "structural",
    "decentralized-rendezvous": "isolation",
    "transport-neutral-identity-session": "baseline",
    "ice-quic-identity-session": "contingent",
    "relay-first-direct-promotion": "alternative",
}
RECOMMENDED_OPTIONS = {
    "authenticated-rendezvous-and-candidate-protection": "authenticated-encrypted-ice-turn",
    "identity-bound-traversal-and-relay-fallback": "transport-neutral-identity-session",
}
SELECTION_PROFILE_ID = "production_p2p_nat_v1_recommended"
APPROVED_PROFILE_STATUS = "approved_for_bounded_handoff"
SELECTION_DECISION_ID = "production_p2p_nat_v1_approval_20260712"
HANDOFF_ID = "production_p2p_nat_v1_handoff_v1"
COMPLETION_HANDOFF_ID = "production_p2p_nat_v1_handoff_v2"
EXPECTED_DEFERRED_OPTIONS = {
    "decentralized-rendezvous",
    "ice-quic-identity-session",
    "relay-first-direct-promotion",
}
EXPECTED_HANDOFF_PACKAGES = (
    "canonical-contracts",
    "no-network-conformance",
    "controlled-network-spike",
)
EXPECTED_PRE_NETWORK_DECISIONS = {
    "service-ownership-and-trust",
    "pair-authorization-and-retention",
    "candidate-privacy-and-scope",
    "ice-and-consent-policy",
    "turn-credential-and-abuse-policy",
    "session-transition-semantics",
    "release-budgets",
}
EXPECTED_PRE_NETWORK_DECISION_RESOLUTIONS = {
    "service-ownership-and-trust": "first-party-tls13-signed-service-config",
    "pair-authorization-and-retention": "opaque-generation-scoped-capabilities",
    "candidate-privacy-and-scope": "e2e-limited-direct",
    "ice-and-consent-policy": "full-ice-regular-nomination-runtime-initiator",
    "turn-credential-and-abuse-policy": "short-lived-pair-scoped-turn",
    "session-transition-semantics": "between-request-cutover-fail-inflight",
    "release-budgets": "measured-matrix-with-hard-stop-budgets",
}
EXPECTED_SPIKE_REVIEWS = [
    "networking_library_selection",
    "session_cryptography_library_selection",
    "isolated_harness_design",
    "socket_destination_and_egress_controls",
]
EXPECTED_SPIKE_RESOLUTIONS = {
    "networking_library_selection": "libjuice-1.7.2-static-c-abi",
    "session_cryptography_library_selection": "platform-native-p256-hkdf-sha256-aes256gcm",
    "isolated_harness_design": "linux-netns-twin-agent-local-services",
    "socket_destination_and_egress_controls": "numeric-endpoint-allowlist-plus-os-egress-witness",
}
EXPECTED_PHASE_A_EVIDENCE = [
    "libjuice_supply_chain_and_source_audit",
    "android_macos_compile_only_integration",
    "cross_platform_session_crypto_vectors",
    "static_harness_and_egress_policy",
    "phase_a_security_review",
]
EXPECTED_SELECTION_PROFILE_KEYS = {
    "documentType",
    "schemaVersion",
    "profileId",
    "status",
    "implementationAuthorized",
    "selectedOptions",
    "mandatoryFallback",
    "deferredOptions",
    "activeProtocolNamespaceBeforeSelection",
    "selectionEffect",
    "rolloutFloors",
    "initialHandoffPackages",
    "requiredPreNetworkDecisions",
    "explicitSelectionRequired",
    "selectionInstruction",
}
EXPECTED_SELECTION_DECISION_KEYS = {
    "documentType",
    "schemaVersion",
    "decisionId",
    "profileId",
    "status",
    "decision",
    "approvalSource",
    "selectedOptions",
    "mandatoryFallback",
    "productionDesignStatus",
    "activeProtocolNamespace",
    "authorization",
    "handoffPath",
    "openPreNetworkDecisionIds",
    "immutability",
}
EXPECTED_HANDOFF_KEYS = {
    "documentType",
    "schemaVersion",
    "handoffId",
    "profileId",
    "selectionDecisionPath",
    "status",
    "productionDesignStatus",
    "activeProtocolNamespace",
    "authorization",
    "packages",
    "preNetworkDecisions",
    "immutability",
}
EXPECTED_IMPLEMENTATION_FILES = {
    "handoff-v1.json",
    "handoff-v1.md",
    "handoff-v2.json",
    "handoff-v2.md",
    "handoff-v3.json",
    "handoff-v3.md",
    "handoff-v4.json",
    "handoff-v4.md",
}
EXPECTED_PACKAGE_STATES = {
    "canonical-contracts": ("authorized", "not_started", True),
    "no-network-conformance": ("blocked_on_dependency", "not_started", False),
    "controlled-network-spike": (
        "blocked_on_separate_review",
        "not_started",
        False,
    ),
}
EXPECTED_SELECTION_AUTHORIZES = [
    "a versioned implementation handoff for canonical sealed records and the transport-neutral identity transcript",
    "cross-language fixed vectors and a no-network transport conformance harness",
    "parse-only candidate policy work that performs no candidate network I/O",
]
EXPECTED_SELECTION_DENIES = [
    "production deployment or production readiness claims",
    "public rendezvous, STUN, TURN, candidate exchange, hole punching, or direct payload traffic",
    "a concrete networking or cryptography library",
    "QUIC, decentralized rendezvous, relay-first promotion, or plaintext downgrade",
    "physical Android, optical QR, live-network, performance, battery, or interoperability claims",
]
EXPECTED_PROPOSALS = {
    "authenticated-rendezvous-and-candidate-protection": (
        "proposals/authenticated-rendezvous-and-candidate-protection.md"
    ),
    "identity-bound-traversal-and-relay-fallback": (
        "proposals/identity-bound-traversal-and-relay-fallback.md"
    ),
}
EXPECTED_DIAGRAMS = {
    "authenticated-rendezvous-and-candidate-protection": {
        "relay-only-sealed-signaling": (
            "diagrams/authenticated-rendezvous-and-candidate-protection-before.mmd",
            "diagrams/authenticated-rendezvous-and-candidate-protection-relay-only-after.mmd",
        ),
        "authenticated-encrypted-ice-turn": (
            "diagrams/authenticated-rendezvous-and-candidate-protection-before.mmd",
            "diagrams/authenticated-rendezvous-and-candidate-protection-authenticated-ice-turn-after.mmd",
        ),
        "decentralized-rendezvous": (
            "diagrams/authenticated-rendezvous-and-candidate-protection-before.mmd",
            "diagrams/authenticated-rendezvous-and-candidate-protection-decentralized-after.mmd",
        ),
    },
    "identity-bound-traversal-and-relay-fallback": {
        "ice-quic-identity-session": (
            "diagrams/identity-bound-traversal-and-relay-fallback-before.mmd",
            "diagrams/identity-bound-traversal-and-relay-fallback-quic-after.mmd",
        ),
        "transport-neutral-identity-session": (
            "diagrams/identity-bound-traversal-and-relay-fallback-before.mmd",
            "diagrams/identity-bound-traversal-and-relay-fallback-transport-neutral-after.mmd",
        ),
        "relay-first-direct-promotion": (
            "diagrams/identity-bound-traversal-and-relay-fallback-before.mmd",
            "diagrams/identity-bound-traversal-and-relay-fallback-relay-promotion-after.mmd",
        ),
    },
}
PROPOSAL_HEADINGS = [
    "Decision",
    "Executive Recommendation",
    "Evidence",
    "Current Design And Failure Mode",
    "Desired Invariants",
    "Constraints And Non-Goals",
    "Before Architecture",
    "Options",
    "Comparison",
    "Recommendation",
    "Evidence Coverage And Residual Risk",
    "Migration And Rollout",
    "Validation Plan",
    "Implementation Work Packages",
    "Open Questions",
]
REQUIRED_DOCUMENT_SNIPPETS = {
    "context.md": (
        EVIDENCE_COLLECTION_SHA256,
        "13",
        "route.refresh",
        "opaque",
        "no physical device",
        "not implemented",
        "selection-decision.json",
        "implementation/handoff-v1.json",
        "all seven pre-network recommendations are selected",
    ),
    "threat-model.md": (
        "trust boundaries",
        "rendezvous/signaling service",
        "stun",
        "turn",
        "candidate",
        "endpoint identity",
        "replay",
        "downgrade",
        "metadata",
        "denial-of-service",
        "`t016`",
        "destination policy",
        "private destinations",
    ),
    "standards.md": (
        "rfc 8445",
        "rfc 8489",
        "rfc 8656",
        "rfc 7675",
        "authenticated encrypted",
        "tls 1.3",
        "short-lived",
        "consent freshness",
        "rfc 9221",
    ),
    "hardening.md": (
        "authenticated-rendezvous-and-candidate-protection",
        "authenticated-encrypted-ice-turn",
        "identity-bound-traversal-and-relay-fallback",
        "transport-neutral-identity-session",
        "approved_for_bounded_handoff",
        "not implemented",
        "no physical device",
        "route.refresh",
        "selection-decision.json",
        "implementation/handoff-v1.json",
        "no networking library, network i/o, or deployment is authorized",
    ),
    "selection-profile.md": (
        "explicitly approved for a bounded handoff",
        SELECTION_PROFILE_ID,
        APPROVED_PROFILE_STATUS,
        "implementationAuthorized",
        "explicitSelectionRequired",
        "authenticated-encrypted-ice-turn",
        "transport-neutral-identity-session",
        "relay-only-sealed-signaling",
        "route.refresh",
        "no-network conformance harness",
        "open decisions before network i/o",
        "does not add production p2p code",
    ),
    "implementation/handoff-v1.md": (
        "closed",
        SELECTION_PROFILE_ID,
        "not_implemented",
        "route.refresh",
        "canonical-contracts",
        "blocked_on_dependency",
        "blocked_on_separate_review",
        "network i/o",
        "all seven decisions remain `open`",
        "does not authorize public rendezvous",
    ),
}
REQUIRED_PROPOSAL_SECTION_SNIPPETS = {
    "authenticated-rendezvous-and-candidate-protection.md": {
        "Executive Recommendation": (
            "authenticated-encrypted-ice-turn",
            "authenticated encrypted ice+turn",
            "turn",
        ),
        "Evidence": ("`E001`", "`E002`", "`E008`", "`E011`", "`E013`"),
        "Desired Invariants": (
            "end to end",
            "untrusted rendezvous",
            "connectivity checks",
            "short-lived",
            "authenticated encryption",
        ),
        "Options": (
            "relay-only-sealed-signaling",
            "authenticated-encrypted-ice-turn",
            "decentralized-rendezvous",
        ),
        "Recommendation": ("authenticated-encrypted-ice-turn",),
        "Migration And Rollout": ("no automatic downgrade",),
        "Validation Plan": ("nat", "turn", "replay", "plaintext"),
    },
    "identity-bound-traversal-and-relay-fallback.md": {
        "Executive Recommendation": (
            "transport-neutral-identity-session",
            "direct",
            "relay",
        ),
        "Evidence": ("`E001`", "`E003`", "`E008`", "`E010`", "`E011`"),
        "Desired Invariants": (
            "paired",
            "canonical transcript",
            "path-specific",
            "fallback",
            "route tokens",
        ),
        "Options": (
            "ice-quic-identity-session",
            "transport-neutral-identity-session",
            "relay-first-direct-promotion",
        ),
        "Recommendation": ("transport-neutral-identity-session",),
        "Migration And Rollout": ("protocol floor",),
        "Validation Plan": ("identity substitution", "cross-path replay", "race"),
    },
}
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9:])/(?:Users|home|tmp|var|private|Volumes|opt)/"
    r"|\bfile://|\b[A-Za-z]:\\",
    re.IGNORECASE,
)
EDGE_PATTERN = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_-]*)\b.*?"
    r"(-->|-.->|==>|---|~~~)\s*(?:\|[^|]*\|\s*)?"
    r"([A-Za-z][A-Za-z0-9_-]*)\b"
)
TRAVERSAL_MESSAGE_COMPONENT = re.compile(
    r"(?:^|[._-])(p2p|peer|ice|stun|turn|nat|traversal|rendezvous|candidate)(?:[._-]|$)"
)


def fail(message: str) -> None:
    raise ValueError(message)


def reject_duplicate_names(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object contains duplicate name {key!r}")
        result[key] = value
    return result


def parse_json(raw: str, label: str) -> object:
    try:
        return json.loads(raw, object_pairs_hook=reject_duplicate_names)
    except json.JSONDecodeError as error:
        fail(f"{label}: invalid JSON: {error}")


def load_json(path: Path, label: str) -> object:
    return parse_json(path.read_text(encoding="utf-8"), label)


def normalized(text: str) -> str:
    return " ".join(text.split()).lower()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_relative_file(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        fail(f"unsafe design artifact path: {relative_path}")
    resolved = DESIGN_ROOT / path
    if not resolved.is_file():
        fail(f"missing design artifact: {relative_path}")
    return resolved


def validate_evidence_manifest() -> int:
    manifest_path = DESIGN_ROOT / "evidence.sha256"
    manifest_bytes = manifest_path.read_bytes()
    actual_collection_hash = sha256_bytes(manifest_bytes)
    if actual_collection_hash != EVIDENCE_COLLECTION_SHA256:
        fail(
            "evidence manifest collection hash changed: "
            f"expected {EVIDENCE_COLLECTION_SHA256}, got {actual_collection_hash}"
        )

    expected_paths = set(EXPECTED_EVIDENCE_PATHS)
    lines = manifest_bytes.decode("utf-8").splitlines()
    if len(lines) != len(expected_paths):
        fail(f"evidence manifest must contain exactly 13 artifacts, got {len(lines)}")

    seen_paths: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if match is None:
            fail(f"invalid evidence manifest line {line_number}")
        expected_hash, relative_path = match.groups()
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            fail(f"unsafe evidence path on line {line_number}: {relative_path}")
        if relative_path in seen_paths:
            fail(f"duplicate evidence path: {relative_path}")
        seen_paths.add(relative_path)
        source_path = ROOT / path
        if not source_path.is_file():
            fail(f"missing evidence artifact: {relative_path}")
        actual_hash = sha256_bytes(source_path.read_bytes())
        if actual_hash != expected_hash:
            fail(
                f"evidence artifact drifted: {relative_path}; "
                f"expected {expected_hash}, got {actual_hash}"
            )

    if seen_paths != expected_paths:
        missing = sorted(expected_paths - seen_paths)
        extra = sorted(seen_paths - expected_paths)
        fail(f"evidence path set mismatch; missing={missing}, extra={extra}")
    return len(lines)


def require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        fail(f"{label} must contain non-empty strings")
    return value


def require_exact_keys(value: object, expected: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        fail(f"{label} must use the exact closed key set; actual={actual}")
    return value


def type_exact_equal(actual: object, expected: object) -> bool:
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


def validate_tradeoffs(option: dict[str, object], label: str) -> None:
    tradeoffs = option.get("tradeoffs")
    if not isinstance(tradeoffs, list) or len(tradeoffs) != 6:
        fail(f"{label} must define exactly six tradeoffs")
    dimensions: set[str] = set()
    for tradeoff in tradeoffs:
        require_exact_keys(
            tradeoff,
            {"dimension", "direction", "confidence", "basis", "assessment", "validationPlan"},
            f"{label} tradeoff",
        )
        for field in (
            "dimension",
            "direction",
            "confidence",
            "basis",
            "assessment",
            "validationPlan",
        ):
            if not isinstance(tradeoff.get(field), str) or not tradeoff[field]:
                fail(f"{label} tradeoff.{field} must be a non-empty string")
        dimension = tradeoff["dimension"]
        if dimension in dimensions:
            fail(f"{label} repeats tradeoff dimension {dimension}")
        dimensions.add(dimension)
    if dimensions != REQUIRED_TRADEOFFS:
        fail(
            f"{label} tradeoff dimensions mismatch; "
            f"missing={sorted(REQUIRED_TRADEOFFS - dimensions)}, "
            f"extra={sorted(dimensions - REQUIRED_TRADEOFFS)}"
        )


def validate_readiness(option: dict[str, object], label: str) -> None:
    readiness = option.get("implementationReadiness")
    require_exact_keys(
        readiness,
        {"affectedComponents", "workPackages", "acceptanceCriteria", "migrationNotes", "rollback"},
        f"{label} implementationReadiness",
    )
    for field in (
        "affectedComponents",
        "workPackages",
        "acceptanceCriteria",
        "migrationNotes",
    ):
        require_string_list(readiness.get(field), f"{label} readiness.{field}")
    if not isinstance(readiness.get("rollback"), str) or not readiness["rollback"]:
        fail(f"{label} readiness.rollback must be a non-empty string")


def validate_json(artifact_count: int) -> set[str]:
    document = load_json(DESIGN_ROOT / "hardening.json", "hardening.json")
    require_exact_keys(
        document,
        {
            "documentType", "schemaVersion", "analysisId", "sourceEvidence",
            "implementationBoundary", "assessment", "constraints", "evidenceCatalog",
            "opportunities",
        },
        "hardening.json",
    )
    expected_top = {
        "documentType": "codex-security.hardening-analysis",
        "schemaVersion": "1.0",
        "analysisId": "production_p2p_nat_v1_20260711",
    }
    for field, expected in expected_top.items():
        if document.get(field) != expected:
            fail(f"hardening.json {field} must be {expected!r}")

    source_evidence = document.get("sourceEvidence")
    require_exact_keys(
        source_evidence,
        {"kind", "label", "collectionSha256", "artifactCount", "sourceDrift"},
        "hardening.json sourceEvidence",
    )
    for field, expected in (
        ("collectionSha256", EVIDENCE_COLLECTION_SHA256),
        ("artifactCount", artifact_count),
        ("sourceDrift", "present"),
    ):
        if source_evidence.get(field) != expected:
            fail(f"hardening.json sourceEvidence.{field} must be {expected!r}")

    boundary = document.get("implementationBoundary")
    require_exact_keys(
        boundary,
        {
            "selectionGatedProductionDesign", "activeProtocolNamespace",
            "selectionProfilePath", "selectionProfileStatus", "selectionDecisionPath",
            "handoffPath", "implementationAuthorized", "networkIOAllowed",
            "librarySelectionAuthorized", "productionDeploymentAuthorized",
            "conditionalLibrarySelectionAuthorized", "controlledSpikePhaseAAuthorized",
            "offlineSourceInspectionAuthorized", "sourceAcquisitionNetworkIOAllowed",
            "controlledNetworkSpikeSocketExecutionAuthorized", "notImplemented",
        },
        "hardening.json implementationBoundary",
    )
    if boundary.get("selectionGatedProductionDesign") != "not_implemented":
        fail("production P2P NAT design must remain selection-gated and not implemented")
    if boundary.get("activeProtocolNamespace") != ["route.refresh"]:
        fail("hardening.json activeProtocolNamespace must be exactly route.refresh")
    if boundary.get("selectionProfilePath") != "selection-profile.json":
        fail("hardening.json selectionProfilePath must identify the proposed profile")
    if boundary.get("selectionProfileStatus") not in {
        "proposed_not_selected",
        APPROVED_PROFILE_STATUS,
    }:
        fail("hardening.json selectionProfileStatus is not a recognized lifecycle state")
    if boundary.get("implementationAuthorized") is not True:
        fail("hardening.json bounded implementation authorization must remain true")
    if boundary.get("conditionalLibrarySelectionAuthorized") is not True:
        fail("hardening.json must authorize only the conditional phase-A library selection")
    if boundary.get("controlledSpikePhaseAAuthorized") is not True:
        fail("hardening.json must authorize the bounded controlled-spike phase A")
    if boundary.get("offlineSourceInspectionAuthorized") is not True:
        fail("hardening.json must authorize only offline source inspection")
    for field in (
        "networkIOAllowed", "librarySelectionAuthorized",
        "productionDeploymentAuthorized", "sourceAcquisitionNetworkIOAllowed",
        "controlledNetworkSpikeSocketExecutionAuthorized",
    ):
        if boundary.get(field) is not False:
            fail(f"hardening.json implementationBoundary.{field} must remain false")

    require_exact_keys(
        document.get("assessment"),
        {"outcome", "summary"},
        "hardening.json assessment",
    )
    require_exact_keys(
        document.get("constraints"),
        {"profile", "nonNegotiables", "assumptions", "changeHorizons"},
        "hardening.json constraints",
    )

    catalog = document.get("evidenceCatalog")
    if not isinstance(catalog, list) or len(catalog) != len(EVIDENCE_IDS):
        fail("hardening.json evidenceCatalog must contain exactly 13 mappings")
    actual_catalog: dict[str, str] = {}
    for item in catalog:
        require_exact_keys(item, {"evidenceId", "path"}, "hardening.json evidenceCatalog entry")
        evidence_id = item.get("evidenceId")
        path = item.get("path")
        if not isinstance(evidence_id, str) or not isinstance(path, str):
            fail("hardening.json evidenceCatalog entries require evidenceId and path")
        if evidence_id in actual_catalog:
            fail(f"duplicate evidence catalog id: {evidence_id}")
        actual_catalog[evidence_id] = path
    if actual_catalog != EVIDENCE_IDS:
        fail("hardening.json evidenceCatalog ID-to-path mapping is not canonical")

    opportunities = document.get("opportunities")
    if not isinstance(opportunities, list) or len(opportunities) != 2:
        fail("hardening.json must contain exactly two opportunities")
    by_id = {
        item.get("opportunityId"): item
        for item in opportunities
        if isinstance(item, dict) and isinstance(item.get("opportunityId"), str)
    }
    if set(by_id) != set(EXPECTED_OPTIONS):
        fail("hardening.json opportunity IDs are not canonical")

    referenced_diagrams: set[str] = set()
    for opportunity_id, expected_option_ids in EXPECTED_OPTIONS.items():
        opportunity = by_id[opportunity_id]
        require_exact_keys(
            opportunity,
            {
                "opportunityId", "title", "summary", "diagnosis", "desiredInvariants",
                "evidence", "options", "recommendedOptionId", "recommendation", "proposalPath",
            },
            f"hardening.json opportunity {opportunity_id}",
        )
        if opportunity.get("proposalPath") != EXPECTED_PROPOSALS[opportunity_id]:
            fail(f"{opportunity_id} proposalPath is not canonical")
        require_relative_file(EXPECTED_PROPOSALS[opportunity_id])
        if opportunity.get("recommendedOptionId") != RECOMMENDED_OPTIONS[opportunity_id]:
            fail(f"{opportunity_id} recommendation is not canonical")
        if RECOMMENDED_OPTIONS[opportunity_id] not in normalized(
            str(opportunity.get("recommendation", ""))
        ):
            fail(f"{opportunity_id} recommendation text must name the recommended option")
        require_string_list(
            opportunity.get("desiredInvariants"),
            f"{opportunity_id} desiredInvariants",
        )

        evidence = opportunity.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            fail(f"{opportunity_id} evidence must be a non-empty list")
        opportunity_evidence_ids: set[str] = set()
        for item in evidence:
            require_exact_keys(
                item,
                {"claimType", "sourceKind", "evidenceId", "path", "claim"},
                f"{opportunity_id} evidence",
            )
            evidence_id = item.get("evidenceId")
            path = item.get("path")
            if evidence_id not in EVIDENCE_IDS or path != EVIDENCE_IDS[evidence_id]:
                fail(f"{opportunity_id} has a non-canonical evidence ID/path mapping")
            if evidence_id in opportunity_evidence_ids:
                fail(f"{opportunity_id} repeats evidence {evidence_id}")
            opportunity_evidence_ids.add(evidence_id)
            for field in ("claimType", "sourceKind", "claim"):
                if not isinstance(item.get(field), str) or not item[field]:
                    fail(f"{opportunity_id}/{evidence_id} evidence.{field} is empty")

        options = opportunity.get("options")
        if not isinstance(options, list) or len(options) != 3:
            fail(f"{opportunity_id} must contain exactly three options")
        option_ids = tuple(
            option.get("optionId") if isinstance(option, dict) else None
            for option in options
        )
        if option_ids != expected_option_ids:
            fail(f"{opportunity_id} option IDs or order are not canonical")

        for option in options:
            require_exact_keys(
                option,
                {
                    "optionId", "title", "kind", "summary", "evidenceCoverage",
                    "diagramPaths", "tradeoffs", "residualRisks", "implementationReadiness",
                },
                f"{opportunity_id} option",
            )
            option_id = option["optionId"]
            label = f"{opportunity_id}/{option_id}"
            if option.get("kind") != EXPECTED_OPTION_KINDS[option_id]:
                fail(
                    f"{label} kind must be "
                    f"{EXPECTED_OPTION_KINDS[option_id]!r}"
                )
            coverage = option.get("evidenceCoverage")
            if not isinstance(coverage, list) or not coverage:
                fail(f"{label} evidenceCoverage must be a non-empty list")
            coverage_ids: set[str] = set()
            for item in coverage:
                require_exact_keys(
                    item,
                    {"evidenceId", "effect", "tacticalFixRequired", "rationale"},
                    f"{label} evidenceCoverage",
                )
                evidence_id = item.get("evidenceId")
                if evidence_id not in opportunity_evidence_ids:
                    fail(f"{label} covers evidence absent from its opportunity: {evidence_id}")
                if evidence_id in coverage_ids:
                    fail(f"{label} repeats evidenceCoverage {evidence_id}")
                coverage_ids.add(evidence_id)
                if item.get("effect") not in {"addresses", "mitigates", "unaffected"}:
                    fail(f"{label}/{evidence_id} has invalid coverage effect")
                if not isinstance(item.get("tacticalFixRequired"), bool):
                    fail(f"{label}/{evidence_id} tacticalFixRequired must be boolean")
                if not isinstance(item.get("rationale"), str) or not item["rationale"]:
                    fail(f"{label}/{evidence_id} rationale is empty")

            expected_before, expected_after = EXPECTED_DIAGRAMS[opportunity_id][option_id]
            diagram_paths = option.get("diagramPaths")
            if diagram_paths != {"before": expected_before, "after": expected_after}:
                fail(f"{label} diagram references are not canonical")
            require_relative_file(expected_before)
            require_relative_file(expected_after)
            referenced_diagrams.update((expected_before, expected_after))

            validate_tradeoffs(option, label)
            require_string_list(option.get("residualRisks"), f"{label} residualRisks")
            validate_readiness(option, label)

    if len(referenced_diagrams) != 8:
        fail(f"hardening.json must reference exactly eight diagrams, got {len(referenced_diagrams)}")
    return referenced_diagrams


def validate_selection_profile() -> None:
    path = require_relative_file("selection-profile.json")
    profile = load_json(path, "selection-profile.json")
    require_exact_keys(profile, EXPECTED_SELECTION_PROFILE_KEYS, "selection-profile.json")
    expected_top = {
        "documentType": "aetherlink.p2p-nat-selection-profile",
        "schemaVersion": "1.0",
        "profileId": SELECTION_PROFILE_ID,
        "mandatoryFallback": "relay-only-sealed-signaling",
        "activeProtocolNamespaceBeforeSelection": ["route.refresh"],
    }
    for field, expected in expected_top.items():
        if profile.get(field) != expected:
            fail(f"selection-profile.json {field} must be {expected!r}")

    if profile.get("selectedOptions") != RECOMMENDED_OPTIONS:
        fail("selection-profile.json selectedOptions must match both recommended options")
    deferred = require_string_list(
        profile.get("deferredOptions"),
        "selection-profile.json deferredOptions",
    )
    if len(deferred) != len(set(deferred)) or set(deferred) != EXPECTED_DEFERRED_OPTIONS:
        fail("selection-profile.json deferredOptions are not canonical")

    selection_effect = require_exact_keys(
        profile.get("selectionEffect"),
        {"authorizes", "doesNotAuthorize"},
        "selection-profile.json selectionEffect",
    )
    if selection_effect.get("authorizes") != EXPECTED_SELECTION_AUTHORIZES:
        fail("selection-profile.json selectionEffect.authorizes is not canonical")
    if selection_effect.get("doesNotAuthorize") != EXPECTED_SELECTION_DENIES:
        fail("selection-profile.json selectionEffect.doesNotAuthorize is not canonical")

    floors = require_string_list(
        profile.get("rolloutFloors"),
        "selection-profile.json rolloutFloors",
    )
    if len(floors) < 5:
        fail("selection-profile.json rolloutFloors must contain at least five invariants")
    floor_text = normalized(" ".join(floors))
    for snippet in ("routeToken", "same paired-identity", "application-ready", "rollback"):
        if normalized(snippet) not in floor_text:
            fail(f"selection-profile.json rolloutFloors must pin {snippet!r}")

    packages = profile.get("initialHandoffPackages")
    if not isinstance(packages, list) or len(packages) != len(EXPECTED_HANDOFF_PACKAGES):
        fail("selection-profile.json must define exactly three initial handoff packages")
    actual_package_ids: list[str] = []
    for package in packages:
        require_exact_keys(
            package,
            {"packageId", "scope", "networkIOAllowed", "exitCriteria"},
            "selection-profile.json handoff package",
        )
        package_id = package.get("packageId")
        if not isinstance(package_id, str):
            fail("selection-profile.json handoff package id must be a string")
        actual_package_ids.append(package_id)
        if not isinstance(package.get("scope"), str) or not package["scope"]:
            fail(f"selection-profile.json package {package_id} scope must be non-empty")
        if package.get("networkIOAllowed") is not False:
            fail(f"selection-profile.json package {package_id} must keep networkIOAllowed false")
        criteria = require_string_list(
            package.get("exitCriteria"),
            f"selection-profile.json package {package_id} exitCriteria",
        )
        if len(criteria) < 3:
            fail(f"selection-profile.json package {package_id} needs at least three exit criteria")
    if tuple(actual_package_ids) != EXPECTED_HANDOFF_PACKAGES:
        fail("selection-profile.json handoff package order is not canonical")

    decisions = profile.get("requiredPreNetworkDecisions")
    if not isinstance(decisions, list) or len(decisions) != len(EXPECTED_PRE_NETWORK_DECISIONS):
        fail("selection-profile.json must define exactly seven pre-network decisions")
    actual_decisions: set[str] = set()
    for decision in decisions:
        require_exact_keys(
            decision,
            {"decisionId", "question"},
            "selection-profile.json pre-network decision",
        )
        decision_id = decision.get("decisionId")
        question = decision.get("question")
        if not isinstance(decision_id, str) or decision_id in actual_decisions:
            fail("selection-profile.json pre-network decision ids must be unique strings")
        if not isinstance(question, str) or not question.endswith("?"):
            fail(f"selection-profile.json decision {decision_id} must contain a question")
        actual_decisions.add(decision_id)
    if actual_decisions != EXPECTED_PRE_NETWORK_DECISIONS:
        fail("selection-profile.json pre-network decision ids are not canonical")

    instruction = profile.get("selectionInstruction")
    if not isinstance(instruction, str) or SELECTION_PROFILE_ID not in instruction:
        fail("selection-profile.json selectionInstruction must name the profile")

    status = profile.get("status")
    decision_path = DESIGN_ROOT / "selection-decision.json"
    implementation_root = DESIGN_ROOT / "implementation"
    if status == "proposed_not_selected":
        if profile.get("implementationAuthorized") is not False:
            fail("pending profile cannot authorize implementation")
        if profile.get("explicitSelectionRequired") is not True:
            fail("pending profile must require explicit selection")
        if decision_path.exists() or implementation_root.exists():
            fail("pending profile cannot contain a decision or implementation handoff")
        expected_headings = [
            "Status",
            "Proposed Choice",
            "Selection Effect",
            "Security Floors",
            "Spike Exit Criteria",
            "Decisions Still Required Before Network I/O",
            "Evidence Boundary",
        ]
    elif status == APPROVED_PROFILE_STATUS:
        if profile.get("implementationAuthorized") is not True:
            fail("approved profile must authorize its bounded implementation handoff")
        if profile.get("explicitSelectionRequired") is not False:
            fail("approved profile cannot continue requiring explicit selection")
        validate_approved_handoff(profile, actual_decisions)
        expected_headings = [
            "Status",
            "Approved Choice",
            "Selection Effect",
            "Security Floors",
            "Spike Exit Criteria",
            "Open Decisions Before Network I/O",
            "Evidence Boundary",
        ]
    else:
        fail(f"selection-profile.json has unsupported lifecycle status {status!r}")

    markdown_path = require_relative_file("selection-profile.md")
    if markdown_headings(markdown_path) != expected_headings:
        fail("selection-profile.md headings are missing or out of order")

    hardening = load_json(DESIGN_ROOT / "hardening.json", "hardening.json")
    boundary = hardening["implementationBoundary"]
    expected_boundary = {
        "selectionProfileStatus": status,
        "implementationAuthorized": profile["implementationAuthorized"],
        "selectionDecisionPath": "selection-decision.json",
        "handoffPath": "implementation/handoff-v4.json",
    }
    for field, expected in expected_boundary.items():
        if boundary.get(field) != expected:
            fail(f"hardening.json implementationBoundary.{field} must be {expected!r}")


def validate_approved_handoff(profile: dict[str, object], decision_ids: set[str]) -> None:
    decision = load_json(require_relative_file("selection-decision.json"), "selection-decision.json")
    require_exact_keys(decision, EXPECTED_SELECTION_DECISION_KEYS, "selection-decision.json")
    expected_decision = {
        "documentType": "aetherlink.p2p-nat-selection-decision",
        "schemaVersion": "1.0",
        "decisionId": SELECTION_DECISION_ID,
        "profileId": SELECTION_PROFILE_ID,
        "status": "closed",
        "decision": APPROVED_PROFILE_STATUS,
        "approvalSource": "explicit_user_instruction",
        "selectedOptions": profile["selectedOptions"],
        "mandatoryFallback": profile["mandatoryFallback"],
        "productionDesignStatus": "not_implemented",
        "activeProtocolNamespace": ["route.refresh"],
        "handoffPath": "implementation/handoff-v1.json",
    }
    for field, expected in expected_decision.items():
        if decision.get(field) != expected:
            fail(f"selection-decision.json {field} must be {expected!r}")
    expected_authorization = {
        "implementationAuthorized": True,
        "explicitSelectionRequired": False,
        "networkIOAllowed": False,
        "librarySelectionAuthorized": False,
        "productionDeploymentAuthorized": False,
    }
    if require_exact_keys(
        decision.get("authorization"),
        set(expected_authorization),
        "selection-decision.json authorization",
    ) != expected_authorization:
        fail("selection-decision.json authorization boundary is not canonical")
    if set(require_string_list(
        decision.get("openPreNetworkDecisionIds"),
        "selection-decision.json openPreNetworkDecisionIds",
    )) != decision_ids:
        fail("selection-decision.json must keep all seven pre-network decisions open")
    if require_exact_keys(
        decision.get("immutability"),
        {"recordState", "amendmentPolicy"},
        "selection-decision.json immutability",
    ) != {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_decision",
    }:
        fail("selection-decision.json must be a closed immutable record")

    implementation_root = DESIGN_ROOT / "implementation"
    if not implementation_root.is_dir():
        fail("approved profile requires the bounded implementation handoff directory")
    actual_files = {
        str(path.relative_to(implementation_root))
        for path in implementation_root.rglob("*")
        if path.is_file()
    }
    actual_dirs = [path for path in implementation_root.rglob("*") if path.is_dir()]
    if actual_files != EXPECTED_IMPLEMENTATION_FILES or actual_dirs:
        fail(
            "implementation/ must contain only the four closed versioned handoff pairs; "
            f"actual={sorted(actual_files)}"
        )

    handoff = load_json(require_relative_file("implementation/handoff-v1.json"), "implementation/handoff-v1.json")
    require_exact_keys(handoff, EXPECTED_HANDOFF_KEYS, "implementation/handoff-v1.json")
    expected_handoff = {
        "documentType": "aetherlink.p2p-nat-bounded-handoff",
        "schemaVersion": "1.0",
        "handoffId": HANDOFF_ID,
        "profileId": SELECTION_PROFILE_ID,
        "selectionDecisionPath": "../selection-decision.json",
        "status": "closed",
        "productionDesignStatus": "not_implemented",
        "activeProtocolNamespace": ["route.refresh"],
    }
    for field, expected in expected_handoff.items():
        if handoff.get(field) != expected:
            fail(f"implementation/handoff-v1.json {field} must be {expected!r}")
    handoff_authorization = {
        "implementationAuthorized": True,
        "networkIOAllowed": False,
        "librarySelectionAuthorized": False,
        "productionDeploymentAuthorized": False,
    }
    if require_exact_keys(
        handoff.get("authorization"),
        set(handoff_authorization),
        "implementation/handoff-v1.json authorization",
    ) != handoff_authorization:
        fail("implementation/handoff-v1.json authorization boundary is not canonical")

    packages = handoff.get("packages")
    if not isinstance(packages, list) or len(packages) != 3:
        fail("implementation/handoff-v1.json must contain exactly three packages")
    package_ids: list[str] = []
    for package in packages:
        if not isinstance(package, dict):
            fail("implementation/handoff-v1.json package must be an object")
        package_id = package.get("packageId")
        package_ids.append(str(package_id))
        base_keys = {
            "packageId", "authorizationStatus", "executionStatus",
            "executionAuthorized", "networkIOAllowed",
        }
        if package_id == "canonical-contracts":
            expected_keys = base_keys
        elif package_id == "no-network-conformance":
            expected_keys = base_keys | {"blockedOnPackageIds"}
            if package.get("blockedOnPackageIds") != ["canonical-contracts"]:
                fail("no-network-conformance must be blocked on canonical-contracts")
        elif package_id == "controlled-network-spike":
            expected_keys = base_keys | {"blockedOnDecisionIds"}
            if set(package.get("blockedOnDecisionIds", [])) != decision_ids:
                fail("controlled-network-spike must be blocked on all seven open decisions")
        else:
            fail(f"unexpected handoff package {package_id!r}")
        require_exact_keys(package, expected_keys, f"handoff package {package_id}")
        expected_state = EXPECTED_PACKAGE_STATES[package_id]
        actual_state = (
            package.get("authorizationStatus"),
            package.get("executionStatus"),
            package.get("executionAuthorized"),
        )
        if actual_state != expected_state or package.get("networkIOAllowed") is not False:
            fail(f"handoff package {package_id} state or network gate is not canonical")
    if tuple(package_ids) != EXPECTED_HANDOFF_PACKAGES:
        fail("implementation/handoff-v1.json package order is not canonical")

    open_decisions = handoff.get("preNetworkDecisions")
    if not isinstance(open_decisions, list) or len(open_decisions) != 7:
        fail("implementation/handoff-v1.json must contain all seven pre-network decisions")
    handoff_decision_ids: set[str] = set()
    for item in open_decisions:
        require_exact_keys(item, {"decisionId", "status"}, "handoff pre-network decision")
        if item.get("status") != "open" or not isinstance(item.get("decisionId"), str):
            fail("every handoff pre-network decision must remain open")
        handoff_decision_ids.add(item["decisionId"])
    if handoff_decision_ids != decision_ids:
        fail("handoff pre-network decision set is not canonical")
    if require_exact_keys(
        handoff.get("immutability"),
        {"recordState", "amendmentPolicy"},
        "implementation/handoff-v1.json immutability",
    ) != {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_handoff",
    }:
        fail("implementation/handoff-v1.json must be a closed immutable record")

    validate_completion_handoff(decision_ids, handoff_authorization)


def validate_completion_handoff(
    decision_ids: set[str],
    handoff_authorization: dict[str, bool],
) -> None:
    path = "implementation/handoff-v2.json"
    handoff = load_json(require_relative_file(path), path)
    expected_keys = EXPECTED_HANDOFF_KEYS | {"supersedesPath"}
    require_exact_keys(handoff, expected_keys, path)
    expected = {
        "documentType": "aetherlink.p2p-nat-bounded-handoff",
        "schemaVersion": "1.0",
        "handoffId": COMPLETION_HANDOFF_ID,
        "supersedesPath": "handoff-v1.json",
        "profileId": SELECTION_PROFILE_ID,
        "selectionDecisionPath": "../selection-decision.json",
        "status": "closed",
        "productionDesignStatus": "not_implemented",
        "activeProtocolNamespace": ["route.refresh"],
    }
    for field, value in expected.items():
        if handoff.get(field) != value:
            fail(f"{path} {field} must be {value!r}")
    if require_exact_keys(
        handoff.get("authorization"),
        set(handoff_authorization),
        f"{path} authorization",
    ) != handoff_authorization:
        fail(f"{path} authorization boundary is not canonical")

    expected_evidence = {
        "canonical-contracts": [
            "../../../../shared/protocol/fixtures/production-p2p-nat-v1-vectors.json",
            "../../../../script/check_p2p_nat_contract_vectors.py",
            "../../../../apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatCanonicalCodec.kt",
            "../../../../apps/android/core/protocol/src/test/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSharedVectorTest.kt",
            "../../../../apps/macos/P2PNATContracts/Sources/P2PNATContracts.swift",
            "../../../../apps/macos/P2PNATContracts/Tests/P2PNATSharedVectorTests.swift",
        ],
        "no-network-conformance": [
            "../../../../apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/p2pnat/CandidatePolicy.kt",
            "../../../../apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/p2pnat/ReplayWindow.kt",
            "../../../../apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/p2pnat/ReadinessStateMachine.kt",
            "../../../../apps/macos/P2PNATConformance/Sources/P2PNATConformance.swift",
            "../../../../apps/android/core/transport/src/test/java/com/localagentbridge/android/core/transport/p2pnat/CandidatePolicyTest.kt",
            "../../../../apps/android/core/transport/src/test/java/com/localagentbridge/android/core/transport/p2pnat/ReplayWindowTest.kt",
            "../../../../apps/android/core/transport/src/test/java/com/localagentbridge/android/core/transport/p2pnat/ReadinessStateMachineTest.kt",
            "../../../../apps/macos/P2PNATConformance/Tests/P2PNATConformanceTests.swift",
        ],
    }
    packages = handoff.get("packages")
    if not isinstance(packages, list) or len(packages) != 3:
        fail(f"{path} must contain exactly three packages")
    package_ids: list[str] = []
    for package in packages:
        if not isinstance(package, dict):
            fail(f"{path} package must be an object")
        package_id = package.get("packageId")
        package_ids.append(str(package_id))
        base_keys = {
            "packageId", "authorizationStatus", "executionStatus",
            "executionAuthorized", "networkIOAllowed",
        }
        if package_id in expected_evidence:
            require_exact_keys(package, base_keys | {"evidencePaths"}, f"{path} package {package_id}")
            if (
                package.get("authorizationStatus") != "authorized"
                or package.get("executionStatus") != "completed"
                or package.get("executionAuthorized") is not False
                or package.get("networkIOAllowed") is not False
                or package.get("evidencePaths") != expected_evidence[package_id]
            ):
                fail(f"{path} completed package {package_id} is not canonical")
            for relative in expected_evidence[package_id]:
                evidence_path = (DESIGN_ROOT / "implementation" / relative).resolve()
                if not evidence_path.is_relative_to(ROOT) or not evidence_path.is_file():
                    fail(f"{path} evidence path is missing or escapes the repository: {relative}")
        elif package_id == "controlled-network-spike":
            require_exact_keys(package, base_keys | {"blockedOnDecisionIds"}, f"{path} controlled package")
            if (
                package.get("authorizationStatus") != "blocked_on_separate_review"
                or package.get("executionStatus") != "not_started"
                or package.get("executionAuthorized") is not False
                or package.get("networkIOAllowed") is not False
                or set(package.get("blockedOnDecisionIds", [])) != decision_ids
            ):
                fail(f"{path} controlled network spike gate is not canonical")
        else:
            fail(f"{path} has unexpected package {package_id!r}")
    if tuple(package_ids) != EXPECTED_HANDOFF_PACKAGES:
        fail(f"{path} package order is not canonical")

    open_decisions = handoff.get("preNetworkDecisions")
    if not isinstance(open_decisions, list) or {
        item.get("decisionId")
        for item in open_decisions
        if isinstance(item, dict) and item.get("status") == "open"
    } != decision_ids:
        fail(f"{path} must keep all seven pre-network decisions open")
    if require_exact_keys(
        handoff.get("immutability"),
        {"recordState", "amendmentPolicy"},
        f"{path} immutability",
    ) != {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_handoff",
    }:
        fail(f"{path} must be a closed immutable record")


def markdown_headings(path: Path) -> list[str]:
    return [
        line.removeprefix("## ").strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]


def markdown_sections(path: Path) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line.removeprefix("## ").strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {heading: "\n".join(lines) for heading, lines in sections.items()}


def require_snippets(text: str, snippets: tuple[str, ...], label: str) -> None:
    haystack = normalized(text)
    for snippet in snippets:
        if normalized(snippet) not in haystack:
            fail(f"{label} is missing required snippet {snippet!r}")


def validate_documents() -> None:
    for name, snippets in REQUIRED_DOCUMENT_SNIPPETS.items():
        path = require_relative_file(name)
        require_snippets(path.read_text(encoding="utf-8"), snippets, name)

    hardening_text = require_relative_file("hardening.md").read_text(encoding="utf-8")
    if "**not selected**" in hardening_text:
        fail("hardening.md retains a stale not-selected marker after bounded approval")
    hardening_json_text = require_relative_file("hardening.json").read_text(encoding="utf-8")
    if "future explicit selection" in hardening_json_text:
        fail("hardening.json retains a stale future-selection recommendation after approval")

    for proposal_name, section_snippets in REQUIRED_PROPOSAL_SECTION_SNIPPETS.items():
        proposal_path = require_relative_file(f"proposals/{proposal_name}")
        if markdown_headings(proposal_path) != PROPOSAL_HEADINGS:
            fail(f"proposal headings are missing or out of order: {proposal_name}")
        sections = markdown_sections(proposal_path)
        for heading, snippets in section_snippets.items():
            if heading not in sections:
                fail(f"{proposal_name} is missing section {heading!r}")
            require_snippets(
                sections[heading],
                snippets,
                f"{proposal_name} section {heading!r}",
            )


def diagram_fingerprint(text: str, name: str) -> tuple[int, tuple[tuple[int, str, int], ...]]:
    identifiers: dict[str, int] = {}
    edges: list[tuple[int, str, int]] = []

    def identifier(value: str) -> int:
        if value not in identifiers:
            identifiers[value] = len(identifiers)
        return identifiers[value]

    for line in text.splitlines():
        stripped = line.split("%%", 1)[0]
        match = EDGE_PATTERN.match(stripped)
        if match is None:
            continue
        source, operator, target = match.groups()
        edges.append((identifier(source), operator, identifier(target)))
    if len(identifiers) < 4 or len(edges) < 4:
        fail(f"Mermaid diagram lacks a reviewable flow structure: {name}")
    subgraphs = sum(
        1 for line in text.splitlines() if line.lstrip().lower().startswith("subgraph ")
    )
    if subgraphs < 1:
        fail(f"Mermaid diagram must show at least one trust boundary: {name}")
    return subgraphs, tuple(edges)


def validate_diagrams(diagram_paths: set[str]) -> None:
    fingerprints: dict[tuple[int, tuple[tuple[int, str, int], ...]], str] = {}
    for relative_path in sorted(diagram_paths):
        path = require_relative_file(relative_path)
        text = path.read_text(encoding="utf-8")
        if not text.lstrip().startswith("flowchart"):
            fail(f"Mermaid diagram must start with flowchart: {path.name}")
        require_snippets(
            text,
            ("trust boundary", "untrusted", "auth", "encrypt", "fallback"),
            path.name,
        )
        fingerprint = diagram_fingerprint(text, path.name)
        duplicate = fingerprints.get(fingerprint)
        if duplicate is not None:
            fail(f"Mermaid diagrams are not structurally distinct: {duplicate}, {path.name}")
        fingerprints[fingerprint] = path.name

        if path.name == "identity-bound-traversal-and-relay-fallback-relay-promotion-after.mmd":
            subgraph_stack: list[str] = []
            promotion_boundary: tuple[str, ...] | None = None
            for line in text.splitlines():
                stripped = line.strip()
                subgraph_match = re.match(r"subgraph\s+([A-Za-z][A-Za-z0-9_-]*)", stripped)
                if subgraph_match is not None:
                    subgraph_stack.append(subgraph_match.group(1))
                    continue
                if stripped == "end":
                    if subgraph_stack:
                        subgraph_stack.pop()
                    continue
                if re.match(r"Promote\s*\[", stripped):
                    promotion_boundary = tuple(subgraph_stack)
            if promotion_boundary is None or "EndpointTrust" not in promotion_boundary:
                fail("direct promotion authority must remain inside EndpointTrust")
    if len(fingerprints) != 8:
        fail(f"expected eight structurally distinct Mermaid flowcharts, got {len(fingerprints)}")


def validate_no_absolute_paths_outside_context() -> None:
    checked_suffixes = {".md", ".mmd", ".json"}
    for path in DESIGN_ROOT.rglob("*"):
        if not path.is_file() or path.name == "context.md" or path.suffix not in checked_suffixes:
            continue
        if ABSOLUTE_PATH_PATTERN.search(path.read_text(encoding="utf-8")):
            fail(f"absolute local path leaked outside context.md: {path.relative_to(DESIGN_ROOT)}")


def validate_active_protocol_namespace() -> None:
    schema_path = ROOT / "packages/protocol-schema/protocol.schema.json"
    schema = load_json(schema_path, "packages/protocol-schema/protocol.schema.json")
    message_types = schema.get("properties", {}).get("type", {}).get("enum")
    if not isinstance(message_types, list) or not all(
        isinstance(message_type, str) for message_type in message_types
    ):
        fail("protocol.schema.json message type enum is missing")
    active_traversal_namespace = {
        message_type
        for message_type in message_types
        if message_type.startswith("route.")
        or TRAVERSAL_MESSAGE_COMPONENT.search(message_type) is not None
    }
    if active_traversal_namespace != {"route.refresh"}:
        fail(
            "active traversal protocol namespace changed; "
            f"expected ['route.refresh'], got {sorted(active_traversal_namespace)}"
        )


def validate_current_pre_network_handoff(handoff: object | None = None) -> None:
    if handoff is None:
        handoff = load_json(PRE_NETWORK_HANDOFF_PATH, "implementation/handoff-v3.json")
    root = require_exact_keys(
        handoff,
        {
            "documentType", "schemaVersion", "handoffId", "supersedesPath", "profileId",
            "selectionDecisionPath", "preNetworkReviewPath", "approvalDecisionPath", "status",
            "productionDesignStatus", "measurementStatus", "activeProtocolNamespace",
            "authorization", "packages", "preNetworkDecisions", "nextReview", "immutability",
        },
        "implementation/handoff-v3.json",
    )
    expected_root = {
        "documentType": "aetherlink.p2p-nat-bounded-handoff",
        "schemaVersion": "1.0",
        "handoffId": "production_p2p_nat_v1_handoff_v3",
        "supersedesPath": "handoff-v2.json",
        "profileId": SELECTION_PROFILE_ID,
        "selectionDecisionPath": "../selection-decision.json",
        "preNetworkReviewPath": "../pre-network/review-v1.json",
        "approvalDecisionPath": "../pre-network/decision-v1.json",
        "status": "closed",
        "productionDesignStatus": "not_implemented",
        "measurementStatus": "unmeasured_proposal",
        "activeProtocolNamespace": ["route.refresh"],
    }
    for field, expected in expected_root.items():
        if root[field] != expected:
            fail(f"handoff-v3 {field} must remain {expected!r}")
    authorization = require_exact_keys(
        root["authorization"],
        {
            "implementationAuthorized", "networkIOAllowed", "librarySelectionAuthorized",
            "productionDeploymentAuthorized", "controlledNetworkSpikeSocketExecutionAuthorized",
        },
        "handoff-v3 authorization",
    )
    if authorization["implementationAuthorized"] is not True or any(
        authorization[field] is not False
        for field in (
            "networkIOAllowed", "librarySelectionAuthorized", "productionDeploymentAuthorized",
            "controlledNetworkSpikeSocketExecutionAuthorized",
        )
    ):
        fail("handoff-v3 network, library, socket, and deployment gates must remain closed")
    packages = root["packages"]
    if not isinstance(packages, list) or len(packages) != 3:
        fail("handoff-v3 must contain exactly three packages")
    for index, package_id in enumerate(("canonical-contracts", "no-network-conformance")):
        package = require_exact_keys(
            packages[index],
            {
                "packageId", "authorizationStatus", "executionStatus", "executionAuthorized",
                "networkIOAllowed", "evidencePaths", "evidenceSha256",
            },
            f"handoff-v3 package {index}",
        )
        if any((
            package["packageId"] != package_id,
            package["authorizationStatus"] != "authorized",
            package["executionStatus"] != "completed",
            package["executionAuthorized"] is not False,
            package["networkIOAllowed"] is not False,
        )):
            fail(f"handoff-v3 completed package {package_id} boundary drifted")
    spike = require_exact_keys(
        packages[2],
        {
            "packageId", "authorizationStatus", "executionStatus", "executionAuthorized",
            "networkIOAllowed", "socketExecutionAuthorized", "blockedOnReviews",
        },
        "handoff-v3 controlled network spike",
    )
    if spike != {
        "packageId": "controlled-network-spike",
        "authorizationStatus": "blocked_on_separate_review",
        "executionStatus": "not_started",
        "executionAuthorized": False,
        "networkIOAllowed": False,
        "socketExecutionAuthorized": False,
        "blockedOnReviews": EXPECTED_SPIKE_REVIEWS,
    }:
        fail("handoff-v3 controlled network spike gate must remain closed")
    decisions = root["preNetworkDecisions"]
    if not isinstance(decisions, list) or len(decisions) != len(EXPECTED_PRE_NETWORK_DECISION_RESOLUTIONS):
        fail("handoff-v3 must retain all seven resolved decisions")
    for decision, (decision_id, resolution) in zip(
        decisions,
        EXPECTED_PRE_NETWORK_DECISION_RESOLUTIONS.items(),
    ):
        closed_decision = require_exact_keys(
            decision,
            {"decisionId", "status", "resolution", "approvalSource"},
            f"handoff-v3 decision {decision_id}",
        )
        if closed_decision != {
            "decisionId": decision_id,
            "status": "resolved",
            "resolution": resolution,
            "approvalSource": "explicit_user_instruction",
        }:
            fail(f"handoff-v3 decision {decision_id} closure drifted")
    next_review = require_exact_keys(
        root["nextReview"],
        {"status", "scope", "networkIOAllowedDuringReview"},
        "handoff-v3 next review",
    )
    if next_review != {
        "status": "required_before_socket_execution",
        "scope": EXPECTED_SPIKE_REVIEWS,
        "networkIOAllowedDuringReview": False,
    }:
        fail("handoff-v3 next review boundary drifted")
    immutability = require_exact_keys(
        root["immutability"],
        {"recordState", "amendmentPolicy"},
        "handoff-v3 immutability",
    )
    if immutability != {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_handoff",
    }:
        fail("handoff-v3 immutability boundary drifted")


def validate_current_controlled_spike_handoff(handoff: object | None = None) -> None:
    if handoff is None:
        handoff = load_json(CURRENT_HANDOFF_PATH, "implementation/handoff-v4.json")
    root = require_exact_keys(
        handoff,
        {
            "documentType", "schemaVersion", "handoffId", "supersedesPath", "profileId",
            "selectionDecisionPath", "preNetworkApprovalDecisionPath", "controlledSpikeReviewPath",
            "controlledSpikeDecisionPath", "status", "productionDesignStatus", "measurementStatus",
            "activeProtocolNamespace", "authorization", "packages", "preNetworkDecisions",
            "controlledSpikeApprovals", "nextDecision", "immutability",
        },
        "implementation/handoff-v4.json",
    )
    expected_root = {
        "documentType": "aetherlink.p2p-nat-bounded-handoff",
        "schemaVersion": "1.0",
        "handoffId": "production_p2p_nat_v1_handoff_v4",
        "supersedesPath": "handoff-v3.json",
        "profileId": SELECTION_PROFILE_ID,
        "selectionDecisionPath": "../selection-decision.json",
        "preNetworkApprovalDecisionPath": "../pre-network/decision-v1.json",
        "controlledSpikeReviewPath": "../controlled-network-spike/review-v1.json",
        "controlledSpikeDecisionPath": "../controlled-network-spike/decision-v1.json",
        "status": "closed",
        "productionDesignStatus": "not_implemented",
        "measurementStatus": "not_started",
        "activeProtocolNamespace": ["route.refresh"],
    }
    for field, expected in expected_root.items():
        if root[field] != expected:
            fail(f"handoff-v4 {field} must remain {expected!r}")

    expected_authorization = {
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
    if not type_exact_equal(
        require_exact_keys(
            root["authorization"], set(expected_authorization), "handoff-v4 authorization"
        ),
        expected_authorization,
    ):
        fail("handoff-v4 phase-A and production authorization boundary drifted")

    previous = load_json(PRE_NETWORK_HANDOFF_PATH, "implementation/handoff-v3.json")
    packages = root["packages"]
    if not isinstance(packages, list) or len(packages) != 3:
        fail("handoff-v4 must contain exactly three packages")
    if not type_exact_equal(packages[:2], previous["packages"][:2]):
        fail("handoff-v4 must preserve completed handoff-v3 package evidence exactly")
    spike = require_exact_keys(
        packages[2],
        {
            "packageId", "authorizationStatus", "executionStatus", "executionAuthorized",
            "selectedOptions", "phaseA", "phaseB",
        },
        "handoff-v4 controlled network spike",
    )
    if any((
        spike["packageId"] != "controlled-network-spike",
        spike["authorizationStatus"] != "authorized_phase_a_evidence_only",
        spike["executionStatus"] != "not_started",
        spike["executionAuthorized"] is not True,
        not type_exact_equal(spike["selectedOptions"], EXPECTED_SPIKE_RESOLUTIONS),
    )):
        fail("handoff-v4 controlled network spike selection drifted")
    expected_phase_a = {
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
    if not type_exact_equal(
        require_exact_keys(
            spike["phaseA"], set(expected_phase_a), "handoff-v4 phase A"
        ),
        expected_phase_a,
    ):
        fail("handoff-v4 phase A scope drifted")
    expected_phase_b = {
        "status": "blocked_on_phase_a_evidence_and_separate_versioned_decision",
        "executionAuthorized": False,
        "networkIOAllowed": False,
        "socketExecutionAuthorized": False,
        "externalEgressAllowed": False,
    }
    if not type_exact_equal(
        require_exact_keys(
            spike["phaseB"], set(expected_phase_b), "handoff-v4 phase B"
        ),
        expected_phase_b,
    ):
        fail("handoff-v4 phase B socket gate drifted")
    if not type_exact_equal(root["preNetworkDecisions"], previous["preNetworkDecisions"]):
        fail("handoff-v4 pre-network decision history drifted")

    approvals = root["controlledSpikeApprovals"]
    if not isinstance(approvals, list) or len(approvals) != len(EXPECTED_SPIKE_REVIEWS):
        fail("handoff-v4 must retain all four phase-A approvals")
    for approval, decision_id in zip(approvals, EXPECTED_SPIKE_REVIEWS):
        expected = {
            "decisionId": decision_id,
            "status": "approved_for_bounded_phase_a_evidence",
            "resolution": EXPECTED_SPIKE_RESOLUTIONS[decision_id],
            "approvalSource": "explicit_user_instruction",
        }
        if not type_exact_equal(
            require_exact_keys(
                approval, set(expected), f"handoff-v4 approval {decision_id}"
            ),
            expected,
        ):
            fail(f"handoff-v4 approval {decision_id} drifted")
    expected_next = {
        "status": "required_after_phase_a_evidence_before_socket_execution",
        "requiredEvidence": EXPECTED_PHASE_A_EVIDENCE,
        "networkIOAllowedBeforeDecision": False,
        "socketExecutionAuthorizedBeforeDecision": False,
    }
    if not type_exact_equal(
        require_exact_keys(
            root["nextDecision"], set(expected_next), "handoff-v4 next decision"
        ),
        expected_next,
    ):
        fail("handoff-v4 next socket decision boundary drifted")
    expected_immutability = {
        "recordState": "closed",
        "amendmentPolicy": "supersede_with_new_versioned_handoff",
    }
    if require_exact_keys(
        root["immutability"], set(expected_immutability), "handoff-v4 immutability"
    ) != expected_immutability:
        fail("handoff-v4 immutability boundary drifted")


def qualified_ast_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = qualified_ast_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def validate_phase_a_static_python_ast(raw: str, label: str) -> None:
    allowed_imports = {
        "ast", "copy", "hashlib", "hmac", "ipaddress", "json", "re", "stat",
        "struct", "sys", "unittest",
    }
    allowed_from_imports = {
        "__future__": {"annotations"},
        "pathlib": {"Path", "PurePosixPath"},
        "typing": {"Any"},
        "script": {
            "check_p2p_nat_libjuice_compile_only",
            "check_p2p_nat_libjuice_offline_source",
            "check_p2p_nat_phase_a_harness_egress",
            "check_p2p_nat_security_design",
            "check_p2p_nat_session_crypto_vectors",
        },
    }
    forbidden_names = {
        "__builtins__", "__import__", "compile", "delattr", "eval", "exec", "getattr",
        "globals", "locals", "open", "setattr", "vars",
    }
    forbidden_method_names = {
        "CDLL", "PyDLL", "accept", "bind", "call", "check_call", "check_output",
        "chmod", "connect", "connect_ex", "create_connection", "create_subprocess_exec",
        "create_subprocess_shell", "extract", "extractall", "fork", "fork_exec", "forkpty",
        "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
        "glob", "hardlink_to", "iglob", "import_module", "link_to", "listen", "make_archive",
        "mkdir", "open", "popen", "posix_spawn", "posix_spawnp", "recv", "recvfrom",
        "rename", "replace", "request", "rglob", "rmdir", "rmtree", "run", "send",
        "sendall", "sendto",
        "socket", "spawn", "symlink_to", "system", "touch", "unlink", "unpack_archive",
        "urlopen", "urlretrieve", "write_bytes", "write_text",
    }
    forbidden_qualified_prefixes = ("sys.modules",)
    try:
        tree = ast.parse(raw, filename=label)
    except SyntaxError as error:
        fail(f"{label} has invalid Python syntax: {error}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_imports:
                    fail(f"{label} imports module outside static allowlist {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            allowed_names = allowed_from_imports.get(module, set())
            if not allowed_names or any(
                alias.name == "*" or alias.name not in allowed_names for alias in node.names
            ):
                fail(f"{label} imports from module outside static allowlist {module}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in forbidden_names:
                fail(f"{label} contains forbidden dynamic/capability reference {node.id}")
        elif isinstance(node, ast.Attribute):
            name = qualified_ast_name(node)
            final_name = name.rsplit(".", 1)[-1] if name else ""
            if final_name in forbidden_method_names or any(
                name == prefix or name.startswith(f"{prefix}.")
                for prefix in forbidden_qualified_prefixes
            ):
                fail(f"{label} contains forbidden network/process/file capability {name}")
        elif isinstance(node, ast.Call):
            name = qualified_ast_name(node.func)
            final_name = name.rsplit(".", 1)[-1] if name else ""
            if name in forbidden_names or final_name in forbidden_method_names:
                fail(f"{label} contains forbidden dynamic/network/process/file call {name}")


def validate_phase_a_static_evidence_preflight() -> None:
    for path, expected_digest in PHASE_A_STATIC_EVIDENCE_SHA256.items():
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            fail(
                f"Phase A static evidence hash drifted for {path.relative_to(ROOT)}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
    for path in PHASE_A_STATIC_PYTHON_PATHS:
        raw = path.read_text(encoding="utf-8")
        validate_phase_a_static_python_ast(raw, str(path.relative_to(ROOT)))


def main() -> int:
    try:
        artifact_count = validate_evidence_manifest()
        diagram_paths = validate_json(artifact_count)
        validate_selection_profile()
        validate_documents()
        validate_diagrams(diagram_paths)
        validate_no_absolute_paths_outside_context()
        validate_active_protocol_namespace()
        validate_current_pre_network_handoff()
        validate_current_controlled_spike_handoff()
        validate_phase_a_static_evidence_preflight()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"Production P2P NAT security design check failed: {error}", file=sys.stderr)
        return 1

    print(
        "Production P2P NAT security design OK: "
        "13 evidence artifacts, 2 opportunities, 6 options, "
        "8 structurally distinct diagrams; bounded phase-A handoff approved; "
        "offline source/compile blocked state, session crypto, and static harness policy verified; "
        "socket gate closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
