#!/usr/bin/env python3
"""Validate the selection-gated production P2P NAT security design."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = ROOT / "docs/security-hardening/production-p2p-nat-v1"
EVIDENCE_COLLECTION_SHA256 = "3e778069ab57755e350b287355993d9bd27fe836f450d477354c8d34201a117c"
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
        "selection-gated",
        "not implemented",
        "no physical device",
        "route.refresh",
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


def validate_tradeoffs(option: dict[str, object], label: str) -> None:
    tradeoffs = option.get("tradeoffs")
    if not isinstance(tradeoffs, list) or len(tradeoffs) != 6:
        fail(f"{label} must define exactly six tradeoffs")
    dimensions: set[str] = set()
    for tradeoff in tradeoffs:
        if not isinstance(tradeoff, dict):
            fail(f"{label} contains a non-object tradeoff")
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
    if not isinstance(readiness, dict):
        fail(f"{label} implementationReadiness must be an object")
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
    document = json.loads((DESIGN_ROOT / "hardening.json").read_text(encoding="utf-8"))
    expected_top = {
        "documentType": "codex-security.hardening-analysis",
        "schemaVersion": "1.0",
        "analysisId": "production_p2p_nat_v1_20260711",
    }
    for field, expected in expected_top.items():
        if document.get(field) != expected:
            fail(f"hardening.json {field} must be {expected!r}")

    source_evidence = document.get("sourceEvidence")
    if not isinstance(source_evidence, dict):
        fail("hardening.json sourceEvidence must be an object")
    for field, expected in (
        ("collectionSha256", EVIDENCE_COLLECTION_SHA256),
        ("artifactCount", artifact_count),
        ("sourceDrift", "present"),
    ):
        if source_evidence.get(field) != expected:
            fail(f"hardening.json sourceEvidence.{field} must be {expected!r}")

    boundary = document.get("implementationBoundary")
    if not isinstance(boundary, dict):
        fail("hardening.json implementationBoundary must be an object")
    if boundary.get("selectionGatedProductionDesign") != "not_implemented":
        fail("production P2P NAT design must remain selection-gated and not implemented")
    if boundary.get("activeProtocolNamespace") != ["route.refresh"]:
        fail("hardening.json activeProtocolNamespace must be exactly route.refresh")

    catalog = document.get("evidenceCatalog")
    if not isinstance(catalog, list) or len(catalog) != len(EVIDENCE_IDS):
        fail("hardening.json evidenceCatalog must contain exactly 13 mappings")
    actual_catalog: dict[str, str] = {}
    for item in catalog:
        if not isinstance(item, dict):
            fail("hardening.json evidenceCatalog contains a non-object item")
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
            if not isinstance(item, dict):
                fail(f"{opportunity_id} contains non-object evidence")
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
            if not isinstance(option, dict):
                fail(f"{opportunity_id} contains a non-object option")
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
                if not isinstance(item, dict):
                    fail(f"{label} has non-object evidenceCoverage")
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
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
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


def main() -> int:
    try:
        artifact_count = validate_evidence_manifest()
        diagram_paths = validate_json(artifact_count)
        validate_documents()
        validate_diagrams(diagram_paths)
        validate_no_absolute_paths_outside_context()
        validate_active_protocol_namespace()
        if (DESIGN_ROOT / "implementation").exists():
            fail("design-local implementation/ handoff must not exist before an option is selected")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"Production P2P NAT security design check failed: {error}", file=sys.stderr)
        return 1

    print(
        "Production P2P NAT security design OK: "
        "13 evidence artifacts, 2 opportunities, 6 options, "
        "8 structurally distinct diagrams; selection pending, no production "
        "implementation status inferred."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
