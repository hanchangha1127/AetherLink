#!/usr/bin/env python3
"""Validate the production relay security-design portfolio and its evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = ROOT / "docs/security-hardening/production-relay-v1"
EVIDENCE_COLLECTION_SHA256 = (
    "4a6ab46a0ba36feacd1f8f23402223dd33194c3449ac0a41d118a1453cdca092"
)
EXPECTED_EVIDENCE_PATHS = {
    "apps/macos/CompanionCore/Sources/RemoteRelayAllocationClient.swift",
    "apps/macos/Protocol/Sources/RelaySessionCrypto.swift",
    "apps/macos/Protocol/Sources/RelayIdentityAuthorization.swift",
    "apps/macos/Protocol/Sources/PairedRelayAllocationAuthorization.swift",
    "apps/macos/Pairing/Sources/InitialPairingProof.swift",
    "apps/macos/RelayServerCore/Sources/RelayServer.swift",
    "apps/macos/RelayServerCore/Sources/RelayMatcher.swift",
    "apps/macos/RelayServerCore/Sources/RelaySourceRateLimiter.swift",
    "apps/macos/RelayServerCore/Sources/RelaySourceQuotaLimiter.swift",
    "apps/macos/RelayServerCore/Sources/RelayWaitingPeerPolicy.swift",
    "apps/macos/RelayServerCore/Sources/RelayAllocation.swift",
    "apps/macos/Transport/Sources/RelayPeerClient.swift",
    "apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RuntimeRelayTcpClient.kt",
    "apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/RelaySessionCrypto.kt",
    "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairingStore.kt",
    "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/PairedRelayAllocationAuthorization.kt",
    "packages/protocol-schema/protocol.schema.json",
}
REQUIRED_TRADEOFFS = {
    "security",
    "performance",
    "memory",
    "reliability",
    "operability",
    "migration",
}
PORTFOLIO_HEADINGS = [
    "Evidence Basis",
    "Constraints",
    "Opportunity Portfolio",
    "Recommendation Summary",
    "Next Decisions",
]
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
RECOMMENDED_OPTIONS = {
    "authenticated-allocation-control-plane": "tls-signed-leases",
    "pair-epoch-recovery": "pair-epoch-state-machine",
}
REQUIRED_INVARIANT_SNIPPETS = {
    "authenticated-allocation-control-plane": (
        "authenticates the intended service",
        "every accepted lease is signed",
        "service key id",
        "directly verify each other's signatures",
        "both ephemeral shares",
        "signed lease digest",
        "never receives endpoint traffic secrets",
        "cannot roll back",
    ),
    "pair-epoch-recovery": (
        "monotonic pair epoch and revocation counter",
        "normal renewal is dual-signed",
        "may revoke access but may not authorize a replacement key alone",
        "fresh qr authority",
        "close active and waiting rooms",
        "current signed state receipt",
        "idempotent by transition id",
        "canonical request digest",
        "same id with different content fails",
        "read-only authenticated status operation",
        "signed winning state",
    ),
}
PORTFOLIO_SECTION_SNIPPETS = {
    "Evidence Basis": (
        "allocation uses plain TCP",
        "no pair recovery epoch",
        "source buckets",
        "source peer quotas",
        "bounded waiting",
        "authenticated identity",
        "readiness probes",
        "matcher lock",
        "post-publication",
        "do not authenticate the allocation service",
        "exact strict preflight classification",
        "full-refill-before-idle validation",
    ),
    "Recommendation Summary": (
        "TLS 1.3",
        "endpoint-verifiable",
        "canonical request digest",
        "read-only signed",
    ),
    "Next Decisions": (
        "Select or refine the recommended options before protocol implementation.",
    ),
}
PROPOSAL_SECTION_SNIPPETS = {
    "authenticated-allocation-control-plane.md": {
        "Evidence": (
            "`E006`",
            "`E010`",
            "`E011`",
            "`E012`",
            "not directly peer-verifiable",
            "exact strict preflight classification",
            "registration/readiness decisions",
            "post-publication room lookup",
        ),
        "Current Design And Failure Mode": ("service has no authenticated voice",),
        "Desired Invariants": (
            "authenticates the intended service",
            "every accepted lease is verifiable offline",
            "both long-term identities",
            "both ephemeral shares",
            "signed lease digest",
            "cannot terminate or replace this proof",
            "never receives the endpoint traffic secret",
            "cannot silently roll back",
            "development plain TCP",
        ),
        "Options": (
            "TLS 1.3 Plus Signed Lease Capabilities",
            "relay is not the trust terminator",
            "initial bootstrap is deliberately asymmetric",
        ),
        "Migration And Rollout": (
            "identity-authenticated KEX state machine",
            "never negotiate down",
            "source buckets",
            "production TLS and service authentication",
        ),
        "Validation Plan": (
            "Endpoint KEX integration",
            "Bootstrap integration",
        ),
        "Implementation Work Packages": ("peer-verifiable identity KEX",),
    },
    "pair-epoch-recovery.md": {
        "Evidence": (
            "`E010`",
            "`E011`",
            "`E012`",
            "allocation-mutation source bucket",
            "cannot reset before full refill",
            "registration/readiness decisions",
            "post-publication room lookup",
        ),
        "Current Design And Failure Mode": (
            "commits paired allocation state before returning the final",
            "authority at N+1 and both endpoints at N",
        ),
        "Desired Invariants": (
            "monotonic positive `pair_epoch`",
            "normal lease renewal requires both current device keys",
            "deny-only emergency revocation",
            "cannot authorize a new key",
            "fresh QR ceremony",
            "closes waiting and active rooms",
            "current signed state receipt",
            "same id and digest returns the original signed receipt",
            "same id with different content fails",
            "read-only authenticated status operation",
        ),
        "Options": (
            "Monotonic Pair Epoch State Machine",
            "one-sided deny-only",
            "Planned two-phase in-band key rollover remains distinct",
            "already consume the allocation-mutation source bucket",
        ),
        "Migration And Rollout": ("`pair.status`",),
        "Validation Plan": (
            "drop the final response",
            "`pair.status` convergence",
        ),
        "Implementation Work Packages": ("read-only status",),
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    raise ValueError(message)


def validate_evidence_manifest() -> int:
    manifest_path = DESIGN_ROOT / "evidence.sha256"
    manifest_bytes = manifest_path.read_bytes()
    actual_collection_hash = sha256_bytes(manifest_bytes)
    if actual_collection_hash != EVIDENCE_COLLECTION_SHA256:
        fail(
            "evidence manifest collection hash changed: "
            f"expected {EVIDENCE_COLLECTION_SHA256}, got {actual_collection_hash}"
        )

    lines = manifest_bytes.decode("utf-8").splitlines()
    if len(lines) != len(EXPECTED_EVIDENCE_PATHS):
        fail(
            "evidence manifest must contain "
            f"{len(EXPECTED_EVIDENCE_PATHS)} artifacts, got {len(lines)}"
        )

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
    if seen_paths != EXPECTED_EVIDENCE_PATHS:
        missing = sorted(EXPECTED_EVIDENCE_PATHS - seen_paths)
        extra = sorted(seen_paths - EXPECTED_EVIDENCE_PATHS)
        fail(f"evidence path set mismatch; missing={missing}, extra={extra}")
    return len(lines)


def require_relative_design_file(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        fail(f"unsafe design artifact path: {relative_path}")
    artifact_path = DESIGN_ROOT / path
    if not artifact_path.is_file():
        fail(f"missing design artifact: {relative_path}")
    return artifact_path


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


def require_section_snippets(
    path: Path,
    expected: dict[str, tuple[str, ...]],
) -> None:
    sections = markdown_sections(path)
    for heading, snippets in expected.items():
        section = sections.get(heading)
        if section is None:
            fail(f"{path.name} is missing section {heading!r}")
        normalized_section = " ".join(section.split()).lower()
        for snippet in snippets:
            if " ".join(snippet.split()).lower() not in normalized_section:
                fail(f"{path.name} section {heading!r} is missing {snippet!r}")


def validate_json(artifact_count: int) -> tuple[dict[str, object], list[Path]]:
    json_path = DESIGN_ROOT / "hardening.json"
    document = json.loads(json_path.read_text(encoding="utf-8"))
    if document.get("documentType") != "codex-security.hardening-analysis":
        fail("hardening.json documentType is not canonical")
    if document.get("schemaVersion") != "1.0":
        fail("hardening.json schemaVersion must be 1.0")
    if document.get("analysisId") != "production_relay_v1_20260710":
        fail("hardening.json analysisId is not canonical")

    source_evidence = document.get("sourceEvidence")
    if not isinstance(source_evidence, dict):
        fail("hardening.json sourceEvidence must be an object")
    expected_source_fields = {
        "collectionSha256": EVIDENCE_COLLECTION_SHA256,
        "artifactCount": artifact_count,
        "sourceDrift": "present",
    }
    for field, expected in expected_source_fields.items():
        if source_evidence.get(field) != expected:
            fail(f"hardening.json sourceEvidence.{field} must be {expected!r}")
    if "development-relay" not in str(source_evidence.get("label", "")):
        fail("hardening.json sourceEvidence.label must identify the development-relay snapshot")

    implementation_boundary = document.get("implementationBoundary")
    expected_boundary = {
        "selectionGatedProductionDesign": "not_implemented",
        "implementedTacticalControls": {
            "scope": "development_relay_only",
            "evidenceIds": ["E010", "E011", "E012"],
        },
        "notImplemented": [
            "production TLS and service authentication",
            "service-signed lease capabilities",
            "peer-verifiable endpoint identity KEX",
            "pair-epoch recovery and immediate revocation",
        ],
    }
    if implementation_boundary != expected_boundary:
        fail("hardening.json implementationBoundary is not canonical")

    assessment = document.get("assessment")
    if not isinstance(assessment, dict):
        fail("hardening.json assessment must be an object")
    assessment_summary = " ".join(str(assessment.get("summary", "")).split()).lower()
    for snippet in (
        "tactical source-aware",
        "bounded waiting",
        "authenticated identity fairness",
        "selection-gated production",
    ):
        if snippet not in assessment_summary:
            fail(f"hardening.json assessment.summary is missing {snippet!r}")

    opportunities = document.get("opportunities")
    if not isinstance(opportunities, list):
        fail("hardening.json opportunities must be a list")
    if len(opportunities) != len(RECOMMENDED_OPTIONS):
        fail("hardening.json must contain exactly the two reviewed opportunities")
    by_id = {
        item.get("opportunityId"): item
        for item in opportunities
        if isinstance(item, dict) and isinstance(item.get("opportunityId"), str)
    }
    if set(by_id) != set(RECOMMENDED_OPTIONS):
        fail("hardening.json must contain exactly the two reviewed opportunities")

    referenced_paths: list[Path] = []
    for opportunity_id, recommended_option_id in RECOMMENDED_OPTIONS.items():
        opportunity = by_id[opportunity_id]
        if opportunity.get("recommendedOptionId") != recommended_option_id:
            fail(
                f"{opportunity_id} must recommend {recommended_option_id}"
            )
        desired_invariants = opportunity.get("desiredInvariants")
        if not isinstance(desired_invariants, list) or not all(
            isinstance(item, str) and item for item in desired_invariants
        ):
            fail(f"{opportunity_id} desiredInvariants must be non-empty strings")
        invariant_text = " ".join("\n".join(desired_invariants).split()).lower()
        for snippet in REQUIRED_INVARIANT_SNIPPETS[opportunity_id]:
            if " ".join(snippet.split()).lower() not in invariant_text:
                fail(f"{opportunity_id} desiredInvariants is missing {snippet!r}")
        evidence = opportunity.get("evidence")
        if not isinstance(evidence, list):
            fail(f"{opportunity_id} evidence must be a list")
        e010 = [
            item
            for item in evidence
            if isinstance(item, dict) and item.get("evidenceId") == "E010"
        ]
        if len(e010) != 1:
            fail(f"{opportunity_id} must contain exactly one E010 evidence item")
        if e010[0].get("claimType") != "observed" or e010[0].get("path") != (
            "apps/macos/RelayServerCore/Sources/RelaySourceRateLimiter.swift"
        ):
            fail(f"{opportunity_id} E010 evidence mapping is not canonical")
        e012 = [
            item
            for item in evidence
            if isinstance(item, dict) and item.get("evidenceId") == "E012"
        ]
        if len(e012) != 1:
            fail(f"{opportunity_id} must contain exactly one E012 evidence item")
        if e012[0].get("claimType") != "observed" or e012[0].get("path") != (
            "apps/macos/RelayServerCore/Sources/RelayWaitingPeerPolicy.swift"
        ):
            fail(f"{opportunity_id} E012 evidence mapping is not canonical")
        e012_claim = " ".join(str(e012[0].get("claim", "")).split()).lower()
        for snippet in (
            "atomically expire late rooms",
            "post-publication room lookup",
            "does not",
        ):
            if snippet not in e012_claim:
                fail(f"{opportunity_id} E012 claim is missing {snippet!r}")
        proposal_path = opportunity.get("proposalPath")
        if not isinstance(proposal_path, str):
            fail(f"{opportunity_id} proposalPath is missing")
        referenced_paths.append(require_relative_design_file(proposal_path))

        options = opportunity.get("options")
        if not isinstance(options, list) or len(options) < 2:
            fail(f"{opportunity_id} must compare at least two options")
        option_ids = {
            option.get("optionId")
            for option in options
            if isinstance(option, dict)
        }
        if len(option_ids) != len(options) or not all(
            isinstance(option_id, str) and option_id for option_id in option_ids
        ):
            fail(f"{opportunity_id} option ids must be unique non-empty strings")
        if recommended_option_id not in option_ids:
            fail(f"{opportunity_id} recommended option is absent from options")

        for option in options:
            if not isinstance(option, dict):
                fail(f"{opportunity_id} has a non-object option")
            option_id = option.get("optionId", "<missing>")
            evidence_coverage = option.get("evidenceCoverage")
            if not isinstance(evidence_coverage, list):
                fail(f"{opportunity_id}/{option_id} evidenceCoverage must be a list")
            e010_coverage = [
                item
                for item in evidence_coverage
                if isinstance(item, dict) and item.get("evidenceId") == "E010"
            ]
            if len(e010_coverage) != 1:
                fail(f"{opportunity_id}/{option_id} must map E010 exactly once")
            coverage = e010_coverage[0]
            if coverage.get("effect") != "unaffected" or coverage.get(
                "tacticalFixRequired"
            ) is not True:
                fail(f"{opportunity_id}/{option_id} E010 coverage is not canonical")
            rationale = " ".join(str(coverage.get("rationale", "")).split()).lower()
            if "defense in depth" not in rationale or "does not" not in rationale:
                fail(
                    f"{opportunity_id}/{option_id} E010 rationale must preserve the "
                    "tactical-versus-production boundary"
                )
            e012_coverage = [
                item
                for item in evidence_coverage
                if isinstance(item, dict) and item.get("evidenceId") == "E012"
            ]
            if len(e012_coverage) != 1:
                fail(f"{opportunity_id}/{option_id} must map E012 exactly once")
            waiting_coverage = e012_coverage[0]
            if waiting_coverage.get("effect") != "unaffected" or waiting_coverage.get(
                "tacticalFixRequired"
            ) is not True:
                fail(f"{opportunity_id}/{option_id} E012 coverage is not canonical")
            waiting_rationale = " ".join(
                str(waiting_coverage.get("rationale", "")).split()
            ).lower()
            if "defense in depth" not in waiting_rationale or "does not" not in waiting_rationale:
                fail(
                    f"{opportunity_id}/{option_id} E012 rationale must preserve the "
                    "tactical-versus-production boundary"
                )
            tradeoffs = option.get("tradeoffs")
            if not isinstance(tradeoffs, list):
                fail(f"{opportunity_id}/{option_id} tradeoffs must be a list")
            if len(tradeoffs) != len(REQUIRED_TRADEOFFS):
                fail(f"{opportunity_id}/{option_id} must define six tradeoffs")
            dimensions: set[str] = set()
            for tradeoff in tradeoffs:
                if not isinstance(tradeoff, dict):
                    fail(f"{opportunity_id}/{option_id} has a non-object tradeoff")
                for field in (
                    "dimension",
                    "direction",
                    "confidence",
                    "basis",
                    "assessment",
                    "validationPlan",
                ):
                    if not isinstance(tradeoff.get(field), str) or not tradeoff[field]:
                        fail(
                            f"{opportunity_id}/{option_id} tradeoff.{field} "
                            "must be a non-empty string"
                        )
                dimensions.add(tradeoff["dimension"])
            if dimensions != REQUIRED_TRADEOFFS:
                missing = sorted(REQUIRED_TRADEOFFS - dimensions)
                extra = sorted(dimensions - REQUIRED_TRADEOFFS)
                fail(
                    f"{opportunity_id}/{option_id} tradeoffs mismatch; "
                    f"missing={missing}, extra={extra}"
                )
            diagram_paths = option.get("diagramPaths")
            if not isinstance(diagram_paths, dict):
                fail(f"{opportunity_id}/{option_id} diagramPaths must be an object")
            for variant in ("before", "after"):
                relative_path = diagram_paths.get(variant)
                if not isinstance(relative_path, str):
                    fail(f"{opportunity_id}/{option_id} missing {variant} diagram")
                referenced_paths.append(require_relative_design_file(relative_path))

            readiness = option.get("implementationReadiness")
            if not isinstance(readiness, dict):
                fail(f"{opportunity_id}/{option_id} implementationReadiness is missing")
            for field in (
                "affectedComponents",
                "workPackages",
                "acceptanceCriteria",
                "migrationNotes",
            ):
                value = readiness.get(field)
                if not isinstance(value, list) or not value or not all(
                    isinstance(item, str) and item for item in value
                ):
                    fail(
                        f"{opportunity_id}/{option_id} readiness.{field} "
                        "must contain non-empty strings"
                    )
            if not isinstance(readiness.get("rollback"), str) or not readiness["rollback"]:
                fail(f"{opportunity_id}/{option_id} readiness.rollback is empty")

    return document, referenced_paths


def validate_documents(referenced_paths: list[Path]) -> None:
    context_path = DESIGN_ROOT / "context.md"
    expected_context_headings = [
        "Source Identity",
        "Evidence Inventory",
        "Evidence Limits",
        "Tactical Baseline Update",
    ]
    if markdown_headings(context_path) != expected_context_headings:
        fail("context.md headings are missing or out of order")
    require_section_snippets(
        context_path,
        {
            "Source Identity": (
                EVIDENCE_COLLECTION_SHA256,
                "17 source/schema files",
                "phone is disconnected",
            ),
            "Evidence Inventory": (
                "`E010`",
                "RelaySourceRateLimiter.swift",
                "RelaySourceQuotaLimiter.swift",
                "RelayWaitingPeerPolicy.swift",
                "RelayServer.swift",
            ),
            "Evidence Limits": (
                "in-process, restart-local",
                "exact strict preflight envelope",
                "fully refill before idle deletion",
                "carrier-NAT or VPN fairness",
                "coordinated multi-instance policy",
                "production capacity",
                "first-insertion",
                "bootstrap clients",
                "sybil path",
                "delayed timer delivery",
                "post-publication room lookup",
            ),
            "Tactical Baseline Update": (
                "allocation- and renewal-prefixed attempts",
                "before full parsing",
                "bounded overflow",
                "do not add allocation TLS",
                "peer-verifiable identity KEX",
                "pair epoch recovery",
                "post-proof",
                "active bridges",
            ),
        },
    )

    portfolio_path = DESIGN_ROOT / "hardening.md"
    if markdown_headings(portfolio_path) != PORTFOLIO_HEADINGS:
        fail("hardening.md headings are missing or out of order")
    require_section_snippets(portfolio_path, PORTFOLIO_SECTION_SNIPPETS)

    proposal_paths = sorted({path for path in referenced_paths if path.suffix == ".md"})
    if len(proposal_paths) != 2:
        fail(f"expected two proposal files, got {len(proposal_paths)}")
    for proposal_path in proposal_paths:
        if markdown_headings(proposal_path) != PROPOSAL_HEADINGS:
            fail(f"proposal headings are missing or out of order: {proposal_path.name}")
        require_section_snippets(
            proposal_path,
            PROPOSAL_SECTION_SNIPPETS[proposal_path.name],
        )
        normalized = " ".join(proposal_path.read_text(encoding="utf-8").split()).lower()
        for stale_phrase in (
            "does not add source-aware rate limiting",
            "migration still requires source-aware rate limits",
            "would still require source-aware rate limits",
        ):
            if stale_phrase in normalized:
                fail(f"{proposal_path.name} contains stale phrase {stale_phrase!r}")
    recovery_sections = markdown_sections(
        DESIGN_ROOT / "proposals/pair-epoch-recovery.md"
    )
    recovery_invariants = " ".join(
        recovery_sections["Desired Invariants"].split()
    ).lower()
    if "reused transition id" in recovery_invariants:
        fail(
            "pair-epoch-recovery.md must not reject every reused transition id; "
            "exact id plus request-digest retries are idempotent"
        )

    diagram_paths = sorted({path for path in referenced_paths if path.suffix == ".mmd"})
    if len(diagram_paths) != 8:
        fail(f"expected eight Mermaid diagrams, got {len(diagram_paths)}")
    for diagram_path in diagram_paths:
        if not diagram_path.read_text(encoding="utf-8").lstrip().startswith("flowchart"):
            fail(f"Mermaid diagram must start with flowchart: {diagram_path.name}")

    distributable_paths = [portfolio_path, DESIGN_ROOT / "hardening.json"]
    distributable_paths.extend(proposal_paths)
    distributable_paths.extend(diagram_paths)
    for path in distributable_paths:
        text = path.read_text(encoding="utf-8")
        if "/Users/" in text:
            fail(f"absolute local path leaked into distributable artifact: {path.name}")

    if (DESIGN_ROOT / "implementation").exists():
        fail("implementation/ must not exist before the user selects an option")


def main() -> int:
    try:
        artifact_count = validate_evidence_manifest()
        _, referenced_paths = validate_json(artifact_count)
        validate_documents(referenced_paths)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"Production relay security design check failed: {error}", file=sys.stderr)
        return 1

    print(
        "Production relay security design OK: "
        f"{artifact_count} evidence artifacts, "
        f"{len(RECOMMENDED_OPTIONS)} opportunities, 8 diagrams; "
        "selection-gated production TLS/KEX/pair-epoch implementation not started."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
