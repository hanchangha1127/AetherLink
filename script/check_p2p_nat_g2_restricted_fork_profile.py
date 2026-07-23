#!/usr/bin/env python3
"""Validate the non-executable G2 Pion restricted-fork design portfolio."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = ROOT / "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
PROFILE_PATH = DESIGN_ROOT / "restricted-fork-profile.json"
PROFILE_MARKDOWN_PATH = DESIGN_ROOT / "restricted-fork-profile.md"
EVIDENCE_MANIFEST_PATH = DESIGN_ROOT / "evidence-manifest-v1.json"
HARDENING_PATH = DESIGN_ROOT / "hardening.json"
HARDENING_MARKDOWN_PATH = DESIGN_ROOT / "hardening.md"
CONTEXT_PATH = DESIGN_ROOT / "context.md"
PROPOSAL_PATH = DESIGN_ROOT / "proposals/pion-ice-policy-owned-restriction.md"
SOURCE_REVIEW_PATH = ROOT / "docs/security-hardening/production-p2p-nat-v1/g2-requirements-review-v1.md"

DIAGRAM_PATHS = (
    DESIGN_ROOT / "diagrams/pion-ice-policy-owned-restriction-before.mmd",
    DESIGN_ROOT / "diagrams/pion-ice-policy-owned-restriction-upstream-as-is-after.mmd",
    DESIGN_ROOT / "diagrams/pion-ice-policy-owned-restriction-wrapper-only-gateway-after.mmd",
    DESIGN_ROOT / "diagrams/pion-ice-policy-owned-restriction-restricted-fork-policy-owned-after.mmd",
)

# Byte hashes deliberately remain separate from semantic validation. After an
# intentional portfolio refresh, run this script with --print-hashes and review
# every changed semantic section before replacing these constants.
SOURCE_REVIEW_SHA256 = "1874e43121997023b64b9f370c1782f46f8409630b6096ec8175009b300c246b"
ARTIFACT_SHA256 = {
    CONTEXT_PATH: "70176b985c3118cef40dc769a6371d4085a4a21097cc233f8cb8da1b4aa4dfdd",
    HARDENING_PATH: "10a0295236dded28b29e466414bce1868156db28279ae6f4ee55188ec334c669",
    HARDENING_MARKDOWN_PATH: "dd8f071e22b907334856b1f8314327e8de5ba01fc9b907dcdf5cdd16e284f495",
    PROFILE_PATH: "10e9436ae9b8f24c4447d12f8087b4f121810841ae33526e08fcc3d862d60a0f",
    PROFILE_MARKDOWN_PATH: "86ef115abad55f51f21ec2ed66dba56ba64ce5fc385778a2edf2373210fb7da9",
    EVIDENCE_MANIFEST_PATH: "98e0e53955e21a833fe19852ce00f64df2dc808506bdb222c9b8a20bc8006d00",
    PROPOSAL_PATH: "536bc85ec6d1e02255e8e265438dc04ecd2c28ae231be1aa37da46955e540f98",
    DIAGRAM_PATHS[0]: "5112244e6afe758252461b7bc245c78172997ac189df439c2c3fdb5887f0ac3a",
    DIAGRAM_PATHS[1]: "0cc409cf69d6a38bad4d27b49c2ed7eb94557efccb9792d70ccda1928be62489",
    DIAGRAM_PATHS[2]: "4285eeb9ec649db0d67d239275da86f613e770ea4f1eeabd2a40993cbd840d8c",
    DIAGRAM_PATHS[3]: "b16243c1e09c97b289db8c13d985b25a937c7b68859e23e56bc7be6b1a369337",
}

PROFILE_TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "profileId", "recordedDate", "status",
    "implementationStatus", "verificationStatus", "sourceReview", "upstreamBaseline",
    "forkGovernance", "featureProfile", "networkPolicyBoundary", "turnTlsServiceIdentity",
    "secureSessionPromotion", "resourceLimits", "loggingPolicy", "shutdownPolicy",
    "buildAndSupplyChain", "maintenancePolicy", "verificationMatrix", "technicalDecision",
    "disposition",
}
HARDENING_TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "analysisId", "implementationStatus",
    "runtimeVerificationStatus", "sourceEvidence", "governanceBoundary", "assessment",
    "constraints", "opportunities", "openQuestions", "technicalBoundary",
}
EVIDENCE_MANIFEST_TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "profileId", "recordedDate", "orderingRule",
    "collectionDigestAlgorithm", "artifactCount", "artifacts", "collectionSha256",
    "externalIdentityProofRequired", "userActionRequired",
}
EVIDENCE_MANIFEST_ARTIFACT_KEYS = {"evidenceId", "path", "sha256", "role"}
EVIDENCE_MANIFEST_ARTIFACTS = (
    (
        "G2E001",
        "docs/security-hardening/production-p2p-nat-v1/g2-requirements-review-v1.md",
        "exact_pion_v4_3_0_as_is_rejection_and_pre_acquisition_boundary",
    ),
    (
        "G2E002",
        "docs/v1/g0/decision-v1.md",
        "v1_platform_matrix_and_local_first_product_boundary",
    ),
    (
        "G2E003",
        "docs/roadmap.md",
        "current_sequential_g2_scope_and_progressive_gate_boundary",
    ),
    (
        "G2E004",
        "docs/handoff.md",
        "current_personal_project_boundary_and_handoff_state",
    ),
)

# Semantic SHA-256 uses sorted-key, whitespace-free UTF-8 JSON. These independent
# section pins keep require_canonical=False meaningful and make nested schemas
# closed without duplicating hundreds of literal field assertions.
PROFILE_DOCUMENT_SEMANTIC_SHA256 = "9c929d186eedb10cc890d5540597724d6df1d719f174ed1965c79e4d50324be6"
PROFILE_SECTION_SHA256 = {
    "sourceReview": "4471b5c366e89dcf96fc636920a62f614c722b2b287aa1e4803befd9ae2dde56",
    "upstreamBaseline": "2ce9a33b61008d954b73a00bbcaa4613cf2d986fc52b2a30bf0c742de89ef17f",
    "forkGovernance": "5ae0c39b9aa5af880dfd54235f080450b28e86adf754e66a290a7254320590af",
    "featureProfile": "25721030c1f109ac4e6133929f2bec6c5b23362e1a7f94b8440aa35ef2341cff",
    "networkPolicyBoundary": "bfcf63eeacf0e5af18a19775fb600442b1b9c765b857380e5632c4e3840cde3e",
    "turnTlsServiceIdentity": "cccfeb98cc6d82d1c4d6a28cce0a0e21209a1581555a1d7ea1d168016507dc8b",
    "secureSessionPromotion": "841a531864019afe03c9685807605dd24e4b6e3da3f43612ac894d96ea0ddf0e",
    "resourceLimits": "dc9c6ea29150503cf6a53139b5273f6be5d1e9ce7429e54c8f1463df5c038879",
    "loggingPolicy": "5ac0b3330b985079d6d39b137c94387a0adc74fa1dd1f52399906ae6cbab630e",
    "shutdownPolicy": "27da80c3ff7d79d97bb4dd8602bae37343906d9e57c71e66a393df09b08b2867",
    "buildAndSupplyChain": "3b6ab086ee4516e0f94ce0efe20cfb46c8594b89bb1a4282cc75d105f5183499",
    "maintenancePolicy": "06622aa538431a5a2de4b95b7db33a231d288c269e0694f20e35023d99c1c84b",
    "verificationMatrix": "6a701c3edff5d040fd2cf25ab39aa8a6d4f7fcf87edc2030ad8e8a8f9f057988",
    "technicalDecision": "528ebd61702dbadde2773db79b3d1fafe3028d16cfd869d4a5feb2b6f67b7afb",
    "disposition": "c7b88840de4a55d5048e825f77858ab4220b45476fabacfe82b686f03a2fd93b",
}
HARDENING_DOCUMENT_SEMANTIC_SHA256 = "a67b78777e99b0b7ba4820c15f92840f000eba5bd7cc701164124dec4c3987d0"
HARDENING_SECTION_SHA256 = {
    "sourceEvidence": "714a1321392dde7be5c998efee8cd756ec23127b5dcf8ba98a0c6c822d3965a2",
    "governanceBoundary": "57c1e74129d5bb6cdc9694a32d9df781cdc6235b37c6a4af2378736a01fba6e6",
    "assessment": "a6c4301dc05431d9b93e5932b2020f2f5e5cf99e61ddc4bd219a986265381fde",
    "constraints": "9bff2f56700400d61af48a0356d7694ae4b20611f8dc35603010e4d66c851d31",
    "opportunities": "952213447235b23e0c557e2cd7cb7f56ce426e8652fb0686fcfc41ae5012d920",
    "openQuestions": "4ee9ac447d2408ed3ddb16ce1526e33b1b54ff0493322d63161ce3360ba9dc5d",
    "technicalBoundary": "033aad15e8f483a02fa28781b63fb48088520ddca4ad571e5bd17a9716b6c2f1",
}

PROFILE_IDENTITY = {
    "documentType": "aetherlink.g2-pion-restricted-fork-profile",
    "schemaVersion": "1.1",
    "profileId": "pion_ice_v4_3_0_aetherlink_restricted_fork_v1",
    "recordedDate": "2026-07-23",
    "status": "rung1_profile_complete_candidate_not_selected",
    "implementationStatus": "not_implemented",
    "verificationStatus": "design_validator_passed_runtime_not_executed",
}
HARDENING_IDENTITY = {
    "documentType": "codex-security.hardening-analysis",
    "schemaVersion": "1.1",
    "analysisId": "g2_pion_restricted_fork_v1",
    "implementationStatus": "not_implemented",
    "runtimeVerificationStatus": "not_executed",
}

EXPECTED_REVOCATION_EVENTS = [
    "consent_loss", "path_change", "candidate_restart", "capability_expiry",
    "verification_failure", "session_close",
]

PROFILE_CRITICAL_ASSERTIONS = {
    ("sourceReview", "sha256"): SOURCE_REVIEW_SHA256,
    ("sourceReview", "sourceAcquired"): False,
    ("sourceReview", "sourceCompiled"): False,
    ("sourceReview", "sourceExecuted"): False,
    ("upstreamBaseline", "version"): "v4.3.0",
    ("upstreamBaseline", "commit"): "1e8716372f2bb52e45bf2a7172e4fb1004251c46",
    ("networkPolicyBoundary", "model"): "egress_capability_before_io_and_ingress_admission_before_state_mutation",
    ("networkPolicyBoundary", "egressCapability", "capabilityReuseAllowed"): False,
    ("networkPolicyBoundary", "egressCapability", "wildcardBindAllowed"): False,
    ("networkPolicyBoundary", "egressCapability", "redirectCountMaximum"): 0,
    ("networkPolicyBoundary", "egressCapability", "policyUnavailableRule"): "deny_before_io",
    ("networkPolicyBoundary", "ingressAdmission", "unknownOrInvalidInputRule"): "drop_before_state_mutation_increment_only_saturating_reason_counter",
    ("networkPolicyBoundary", "ingressAdmission", "consumerDeliveryRule"): "deliver_only_after_ingress_admission_and_exact_capability_check",
    ("turnTlsServiceIdentity", "implementationStatus"): "not_implemented",
    ("turnTlsServiceIdentity", "verificationStatus"): "not_executed",
    ("turnTlsServiceIdentity", "tlsMinimumVersion"): "1.3",
    ("turnTlsServiceIdentity", "requiredAlpn"): "stun.turn",
    ("turnTlsServiceIdentity", "insecureSkipVerifyAllowed"): False,
    ("turnTlsServiceIdentity", "ambientProxyAllowed"): False,
    ("turnTlsServiceIdentity", "ambientTrustStoreWithoutSignedTrustDigestAllowed"): False,
    ("secureSessionPromotion", "implementationStatus"): "not_implemented",
    ("secureSessionPromotion", "verificationStatus"): "not_executed",
    ("secureSessionPromotion", "preAuthCapability", "applicationRecordAllowed"): False,
    ("secureSessionPromotion", "postAuthCapability", "plaintextOrLegacyFallbackAllowed"): False,
    ("secureSessionPromotion", "revocationEvents"): EXPECTED_REVOCATION_EVENTS,
    ("secureSessionPromotion", "revocationRule"): "atomically_revoke_pre_auth_and_application_capabilities_before_any_further_io_state_mutation_event_or_payload_delivery",
    ("secureSessionPromotion", "carrierBoundary", "reliableCarrierSelected"): False,
    ("secureSessionPromotion", "carrierBoundary", "recordFragmentationFormatDefined"): False,
    ("secureSessionPromotion", "pionOrIceMayAuthenticateEndpoint"): False,
    ("resourceLimits", "scopeRule"): "per_session_limits_include_current_and_draining_and_closing_generations",
    ("resourceLimits", "processAggregateRule"): "process_totals_include_all_active_draining_and_closing_sessions_and_must_not_exceed_the_exact_process_ceilings",
    ("resourceLimits", "stickyTerminalLatchSlotsPerSession"): 1,
    ("resourceLimits", "eventOverflowRule"): "atomically_set_separate_sticky_terminal_latch_drop_nonterminal_queue_contents_and_close_generation",
    ("loggingPolicy", "implementationStatus"): "not_implemented",
    ("loggingPolicy", "verificationStatus"): "not_executed",
    ("shutdownPolicy", "implementationStatus"): "not_implemented",
    ("shutdownPolicy", "verificationStatus"): "not_executed",
    ("shutdownPolicy", "totalCloseDeadlineMilliseconds"): 2500,
    ("shutdownPolicy", "finalizerRelianceAllowed"): False,
    ("technicalDecision", "currentRung"): 1,
    ("technicalDecision", "currentResult"): "rung1_profile_complete_candidate_not_selected",
    ("technicalDecision", "recommendedNextAction"): "prepare_versioned_rung2_source_identity_and_acquisition_decision",
    ("technicalDecision", "profileDesignRecorded"): True,
    ("technicalDecision", "rung2DecisionRecorded"): False,
    ("technicalDecision", "externalIdentityProofRequired"): False,
    ("technicalDecision", "userActionRequired"): False,
    ("disposition", "result"): "pion_restricted_fork_profile_ready_for_rung2_decision_only",
    ("disposition", "candidateSelected"): False,
    ("disposition", "nextAction"): "prepare_versioned_rung2_source_identity_and_acquisition_decision",
}
EXECUTION_FALSE_FIELDS = (
    "candidateSelected", "librarySelected", "sourceAcquisitionAllowed",
    "dependencyInstallationAllowed", "compilerInvocationAllowed", "codeLoadingAllowed",
    "socketCreationAllowed", "networkIoAllowed", "deviceExecutionAllowed",
    "productionDeploymentAllowed", "gitOperationAllowed",
)
HARDENING_ALLOWED_ENUMS = {
    "claimType": frozenset({"observed", "inferred"}),
    "sourceKind": frozenset({
        "finding", "disclosure", "document", "source", "coverage", "threat_model",
        "poc", "experiment",
    }),
    "kind": frozenset({"baseline", "incremental", "structural"}),
    "effect": frozenset({"unaffected", "mitigates", "addresses"}),
    "direction": frozenset({"improves", "neutral", "regresses", "unknown"}),
    "confidence": frozenset({"low", "medium", "high"}),
    "basis": frozenset({"measured", "source-derived", "analogous", "hypothetical"}),
}

OPTION_DIAGRAM_PATHS = {
    "upstream-as-is": "diagrams/pion-ice-policy-owned-restriction-upstream-as-is-after.mmd",
    "wrapper-only-gateway": "diagrams/pion-ice-policy-owned-restriction-wrapper-only-gateway-after.mmd",
    "restricted-fork-policy-owned": "diagrams/pion-ice-policy-owned-restriction-restricted-fork-policy-owned-after.mmd",
}
BEFORE_DIAGRAM_PATH = "diagrams/pion-ice-policy-owned-restriction-before.mmd"

FABRICATED_STATE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bready\s+for\s+production\b",
        r"\bproduction\s+ready\b",
        r"\bauthorization\s+(?:was\s+)?granted\b",
        r"\ball(?:\s+\w+){0,3}\s+(?:checks|tests)\s+(?:have\s+)?(?:passed|succeeded)\b",
        r"\bcandidate\s+(?:is\s+|was\s+)?selected\b",
        r"\bsource\s+(?:is\s+|was\s+)?acquired\b",
        r"\bcompiled\s+successfully\b",
        r"\bcompilation\s+(?:has\s+)?succeeded\b",
        r"\bnetwork(?:ing)?\s+(?:tests?\s+)?(?:has\s+|was\s+)?(?:passed|succeeded|fully\s+verified)\b",
        r"\bproduction\s+validation\s+(?:has\s+)?passed\b",
        r"\b(?:production\s+)?release\s+(?:was\s+)?approved\b",
        r"\bapproved\s+for\s+acquisition\b",
        r"\bdeployment\s+(?:was\s+)?completed\b",
    )
)


class RestrictedForkValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise RestrictedForkValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object contains duplicate name {key!r}")
        result[key] = value
    return result


def reject_non_finite_constant(value: str) -> None:
    fail(f"JSON contains non-finite constant {value!r}")


def parse_json(raw: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=reject_duplicate_names,
            parse_constant=reject_non_finite_constant,
        )
    except json.JSONDecodeError as error:
        fail(f"invalid JSON: {error}")


def load_json(path: Path) -> Any:
    try:
        return parse_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        fail(f"{path.relative_to(ROOT)}: {error}")


def file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        fail(f"{path.relative_to(ROOT)}: {error}")


def semantic_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        fail(f"value is not canonical finite JSON: {error}")
    return hashlib.sha256(encoded).hexdigest()


def exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path}: expected object")
    actual = set(value)
    if actual != expected:
        fail(f"{path}: keys differ; missing={sorted(expected - actual)} unknown={sorted(actual - expected)}")
    return value


def get_path(root: Any, path: tuple[str, ...]) -> Any:
    value = root
    traversed = "$"
    for key in path:
        traversed += f".{key}"
        if not isinstance(value, dict) or key not in value:
            fail(f"{traversed}: required path missing")
        value = value[key]
    return value


def require_exact(value: Any, expected: Any, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        fail(f"{path}: expected {expected!r}, got {value!r}")


def validate_section_pins(root: dict[str, Any], pins: dict[str, str], path: str) -> None:
    for section, expected in pins.items():
        actual = semantic_sha256(root[section])
        if actual != expected:
            fail(f"{path}.{section}: semantic digest differs; expected {expected}, got {actual}")


def iter_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield from iter_strings(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from iter_strings(nested, f"{path}[{index}]")


def reject_fabricated_state_claims(value: Any, path: str = "$") -> None:
    for value_path, text in iter_strings(value, path):
        for pattern in FABRICATED_STATE_PATTERNS:
            if pattern.search(text):
                fail(f"{value_path}: fabricated state phrase matches {pattern.pattern!r}")


def require_enum(row: dict[str, Any], field: str, path: str) -> None:
    value = row.get(field)
    allowed = HARDENING_ALLOWED_ENUMS[field]
    if not isinstance(value, str) or value not in allowed:
        fail(f"{path}.{field}: expected one of {sorted(allowed)}, got {value!r}")


def require_object_rows(value: Any, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        fail(f"{path}: expected array")
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            fail(f"{path}[{index}]: expected object")
    return value


def validate_hardening_enums(root: dict[str, Any]) -> None:
    opportunities = require_object_rows(root.get("opportunities"), "$hardening.opportunities")
    for opportunity_index, opportunity in enumerate(opportunities):
        opportunity_path = f"$hardening.opportunities[{opportunity_index}]"
        evidence = require_object_rows(opportunity.get("evidence"), f"{opportunity_path}.evidence")
        for evidence_index, row in enumerate(evidence):
            row_path = f"{opportunity_path}.evidence[{evidence_index}]"
            require_enum(row, "claimType", row_path)
            require_enum(row, "sourceKind", row_path)
        options = require_object_rows(opportunity.get("options"), f"{opportunity_path}.options")
        for option_index, option in enumerate(options):
            option_path = f"{opportunity_path}.options[{option_index}]"
            require_enum(option, "kind", option_path)
            coverage = require_object_rows(option.get("evidenceCoverage"), f"{option_path}.evidenceCoverage")
            for coverage_index, row in enumerate(coverage):
                require_enum(row, "effect", f"{option_path}.evidenceCoverage[{coverage_index}]")
            tradeoffs = require_object_rows(option.get("tradeoffs"), f"{option_path}.tradeoffs")
            for tradeoff_index, row in enumerate(tradeoffs):
                row_path = f"{option_path}.tradeoffs[{tradeoff_index}]"
                for field in ("direction", "confidence", "basis"):
                    require_enum(row, field, row_path)


def validate_artifact_hashes() -> None:
    if file_sha256(SOURCE_REVIEW_PATH) != SOURCE_REVIEW_SHA256:
        fail("G2 source review bytes drifted")
    for path, expected in ARTIFACT_SHA256.items():
        if file_sha256(path) != expected:
            fail(f"{path.relative_to(ROOT)}: artifact bytes drifted")


def evidence_collection_sha256(rows: Iterable[tuple[str, str, str]]) -> str:
    payload = "".join(
        f"{evidence_id}\t{digest}\t{relative_path}\n"
        for evidence_id, digest, relative_path in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def current_evidence_rows() -> list[tuple[str, str, str]]:
    return [
        (evidence_id, file_sha256(ROOT / relative_path), relative_path)
        for evidence_id, relative_path, _role in EVIDENCE_MANIFEST_ARTIFACTS
    ]


def validate_evidence_manifest(document: Any, *, require_complete: bool = True) -> None:
    root = exact_keys(document, EVIDENCE_MANIFEST_TOP_LEVEL_KEYS, "$evidenceManifest")
    identity = {
        "documentType": "aetherlink.g2-pion-restricted-fork-evidence-manifest",
        "schemaVersion": "1.0",
        "profileId": PROFILE_IDENTITY["profileId"],
        "recordedDate": PROFILE_IDENTITY["recordedDate"],
        "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_path_newline",
        "artifactCount": len(EVIDENCE_MANIFEST_ARTIFACTS),
        "externalIdentityProofRequired": False,
        "userActionRequired": False,
    }
    for field, expected in identity.items():
        require_exact(root[field], expected, f"$evidenceManifest.{field}")
    artifacts = root["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != len(EVIDENCE_MANIFEST_ARTIFACTS):
        fail("$evidenceManifest.artifacts: exact artifact count differs")
    declared_rows: list[tuple[str, str, str]] = []
    for index, (artifact, expected) in enumerate(zip(artifacts, EVIDENCE_MANIFEST_ARTIFACTS)):
        row = exact_keys(artifact, EVIDENCE_MANIFEST_ARTIFACT_KEYS, f"$evidenceManifest.artifacts[{index}]")
        evidence_id, relative_path, role = expected
        require_exact(row["evidenceId"], evidence_id, f"$evidenceManifest.artifacts[{index}].evidenceId")
        require_exact(row["path"], relative_path, f"$evidenceManifest.artifacts[{index}].path")
        require_exact(row["role"], role, f"$evidenceManifest.artifacts[{index}].role")
        digest = row["sha256"]
        if not isinstance(digest, str):
            fail(f"$evidenceManifest.artifacts[{index}].sha256: expected string")
        if require_complete:
            if digest.startswith("__"):
                fail(f"$evidenceManifest.artifacts[{index}].sha256: placeholder remains")
            require_exact(digest, file_sha256(ROOT / relative_path), f"$evidenceManifest.artifacts[{index}].sha256")
        declared_rows.append((evidence_id, digest, relative_path))
    collection = root["collectionSha256"]
    if not isinstance(collection, str):
        fail("$evidenceManifest.collectionSha256: expected string")
    if require_complete:
        if collection.startswith("__"):
            fail("$evidenceManifest.collectionSha256: placeholder remains")
        require_exact(collection, evidence_collection_sha256(declared_rows), "$evidenceManifest.collectionSha256")


def validate_profile_manifest_link(profile: dict[str, Any], manifest: dict[str, Any]) -> None:
    source = get_path(profile, ("sourceReview",))
    require_exact(source.get("evidenceManifestPath"), "evidence-manifest-v1.json", "$profile.sourceReview.evidenceManifestPath")
    require_exact(source.get("evidenceManifestSha256"), file_sha256(EVIDENCE_MANIFEST_PATH), "$profile.sourceReview.evidenceManifestSha256")
    require_exact(source.get("evidenceCollectionSha256"), manifest.get("collectionSha256"), "$profile.sourceReview.evidenceCollectionSha256")


def validate_hardening_manifest_link(hardening: dict[str, Any], manifest: dict[str, Any]) -> None:
    source = get_path(hardening, ("sourceEvidence",))
    require_exact(source.get("manifestPath"), "evidence-manifest-v1.json", "$hardening.sourceEvidence.manifestPath")
    require_exact(source.get("manifestSha256"), file_sha256(EVIDENCE_MANIFEST_PATH), "$hardening.sourceEvidence.manifestSha256")
    require_exact(source.get("collectionSha256"), manifest.get("collectionSha256"), "$hardening.sourceEvidence.collectionSha256")
    require_exact(source.get("artifactCount"), manifest.get("artifactCount"), "$hardening.sourceEvidence.artifactCount")
    require_exact(
        source.get("orderedEvidenceIds"),
        [row["evidenceId"] for row in manifest["artifacts"]],
        "$hardening.sourceEvidence.orderedEvidenceIds",
    )
    hardening_rows = source.get("artifacts")
    if not isinstance(hardening_rows, list) or len(hardening_rows) != len(manifest["artifacts"]):
        fail("$hardening.sourceEvidence.artifacts: exact manifest row count differs")
    for index, (hardening_row, manifest_row) in enumerate(zip(hardening_rows, manifest["artifacts"])):
        for field in ("evidenceId", "path", "sha256", "role"):
            require_exact(
                hardening_row.get(field),
                manifest_row[field],
                f"$hardening.sourceEvidence.artifacts[{index}].{field}",
            )


def validate_profile_document(document: Any, *, require_canonical: bool = True) -> None:
    root = exact_keys(document, PROFILE_TOP_LEVEL_KEYS, "$profile")
    for field, expected in PROFILE_IDENTITY.items():
        require_exact(root[field], expected, f"$profile.{field}")
    reject_fabricated_state_claims(root, "$profile")
    validate_section_pins(root, PROFILE_SECTION_SHA256, "$profile")
    for path, expected in PROFILE_CRITICAL_ASSERTIONS.items():
        require_exact(get_path(root, path), expected, "$profile." + ".".join(path))
    decision = get_path(root, ("technicalDecision",))
    for field in EXECUTION_FALSE_FIELDS:
        require_exact(decision.get(field), False, f"$profile.technicalDecision.{field}")
    if require_canonical:
        actual = semantic_sha256(root)
        if actual != PROFILE_DOCUMENT_SEMANTIC_SHA256:
            fail(f"$profile: canonical semantic digest differs; got {actual}")


def validate_hardening_document(document: Any, *, require_canonical: bool = True) -> None:
    root = exact_keys(document, HARDENING_TOP_LEVEL_KEYS, "$hardening")
    for field, expected in HARDENING_IDENTITY.items():
        require_exact(root[field], expected, f"$hardening.{field}")
    reject_fabricated_state_claims(root, "$hardening")
    validate_hardening_enums(root)
    validate_section_pins(root, HARDENING_SECTION_SHA256, "$hardening")
    source = get_path(root, ("sourceEvidence",))
    for field in ("sourceAcquired", "sourceCompiled", "sourceLoaded", "sourceExecuted"):
        require_exact(source.get(field), False, f"$hardening.sourceEvidence.{field}")
    governance = get_path(root, ("governanceBoundary",))
    for field in ("externalIdentityProofRequired", "userActionRequired", "repositoryOwnerAuthenticationRequired"):
        require_exact(governance.get(field), False, f"$hardening.governanceBoundary.{field}")
    require_exact(governance.get("productEndpointAuthenticationRequired"), True, "$hardening.governanceBoundary.productEndpointAuthenticationRequired")
    boundary = get_path(root, ("technicalBoundary",))
    for field, expected in {
        "status": "rung1_profile_complete_candidate_not_selected",
        "result": "pion_restricted_fork_profile_ready_for_rung2_decision_only",
        "nextAction": "prepare_versioned_rung2_source_identity_and_acquisition_decision",
    }.items():
        require_exact(boundary.get(field), expected, f"$hardening.technicalBoundary.{field}")
    for field in EXECUTION_FALSE_FIELDS + ("externalIdentityProofRequired", "userActionRequired"):
        require_exact(boundary.get(field), False, f"$hardening.technicalBoundary.{field}")

    options = get_path(root, ("opportunities",))
    if not isinstance(options, list) or len(options) != 1 or not isinstance(options[0], dict):
        fail("$hardening.opportunities: expected one opportunity object")
    option_rows = options[0].get("options")
    if not isinstance(option_rows, list) or len(option_rows) != len(OPTION_DIAGRAM_PATHS):
        fail("$hardening.opportunities[0].options: exact option count differs")
    for index, (option, (option_id, after_path)) in enumerate(zip(option_rows, OPTION_DIAGRAM_PATHS.items())):
        if not isinstance(option, dict):
            fail(f"$hardening.opportunities[0].options[{index}]: expected object")
        require_exact(option.get("optionId"), option_id, f"$hardening.opportunities[0].options[{index}].optionId")
        diagrams = exact_keys(
            option.get("diagramPaths"),
            {"before", "after"},
            f"$hardening.opportunities[0].options[{index}].diagramPaths",
        )
        require_exact(diagrams["before"], BEFORE_DIAGRAM_PATH, f"$hardening.opportunities[0].options[{index}].diagramPaths.before")
        require_exact(diagrams["after"], after_path, f"$hardening.opportunities[0].options[{index}].diagramPaths.after")
    if require_canonical:
        actual = semantic_sha256(root)
        if actual != HARDENING_DOCUMENT_SEMANTIC_SHA256:
            fail(f"$hardening: canonical semantic digest differs; got {actual}")


def validate_profile_markdown(raw: str) -> None:
    normalized = " ".join(raw.split())
    required = (
        "# G2 Pion Restricted-Fork Profile v1",
        "Unmodified Pion ICE v4.3.0 remains rejected.",
        "2,500 ms total deadline",
        "pion_restricted_fork_profile_ready_for_rung2_decision_only",
        "No external identity proof or user action is required.",
    )
    for text in required:
        if normalized.count(text) != 1:
            fail(f"restricted-fork-profile.md: expected one {text!r}")
    reject_fabricated_state_claims(normalized, "$profileMarkdown")


def require_ordered_headings(raw: str, headings: tuple[str, ...], label: str) -> None:
    lines = raw.splitlines()
    positions: list[int] = []
    for heading in headings:
        if lines.count(heading) != 1:
            fail(f"{label}: expected one heading {heading!r}")
        positions.append(raw.index(heading))
    if positions != sorted(positions):
        fail(f"{label}: required headings are out of order")


def validate_portfolio_markdown(raw: str) -> None:
    require_ordered_headings(
        raw,
        (
            "# Security Hardening Review: G2 Pion Restricted-Fork Candidate",
            "## Evidence Basis", "## Constraints", "## Opportunity Portfolio",
            "## Recommendation Summary", "## Next Decisions",
        ),
        "hardening.md",
    )


def validate_proposal_markdown(raw: str) -> None:
    require_ordered_headings(
        raw,
        (
            "# Security Hardening Proposal: Make Pion Policy And Lifetime Ownership Structural",
            "## Decision", "## Executive Recommendation", "## Evidence",
            "## Current Design And Failure Mode", "## Desired Invariants",
            "## Constraints And Non-Goals", "## Before Architecture", "## Options",
            "### Option 1: Retain Unmodified Pion ICE v4.3.0",
            "### Option 2: Add A Wrapper-Only Gateway",
            "### Option 3: Maintain A Minimal Policy-Owned Restricted Fork",
            "## Comparison", "## Recommendation", "## Evidence Coverage And Residual Risk",
            "## Migration And Rollout", "## Validation Plan", "## Implementation Work Packages",
            "## Open Questions",
        ),
        "proposal",
    )
    if raw.count("G2E001") < 4:
        fail("proposal: evidence identifier lacks local definitions and coverage")


def validate_diagrams() -> None:
    for path in DIAGRAM_PATHS:
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("flowchart LR\n"):
            fail(f"{path.relative_to(ROOT)}: expected Mermaid flowchart LR")
        if "Network sockets and I/O" not in raw and "Capability-owned deadline-bound sockets" not in raw:
            fail(f"{path.relative_to(ROOT)}: missing exact network sink")


def refresh_hash_values() -> dict[str, Any]:
    profile = load_json(PROFILE_PATH)
    hardening = load_json(HARDENING_PATH)
    current_rows = current_evidence_rows()
    return {
        "SOURCE_REVIEW_SHA256": file_sha256(SOURCE_REVIEW_PATH),
        "ARTIFACT_SHA256": {
            str(path.relative_to(ROOT)): file_sha256(path) for path in ARTIFACT_SHA256
        },
        "PROFILE_DOCUMENT_SEMANTIC_SHA256": semantic_sha256(profile),
        "PROFILE_SECTION_SHA256": {
            section: semantic_sha256(profile[section]) for section in PROFILE_SECTION_SHA256
        },
        "HARDENING_DOCUMENT_SEMANTIC_SHA256": semantic_sha256(hardening),
        "HARDENING_SECTION_SHA256": {
            section: semantic_sha256(hardening[section]) for section in HARDENING_SECTION_SHA256
        },
        "EVIDENCE_ARTIFACT_SHA256": {
            evidence_id: digest for evidence_id, digest, _path in current_rows
        },
        "EVIDENCE_COLLECTION_SHA256": evidence_collection_sha256(current_rows),
    }


def validate_all() -> None:
    profile = load_json(PROFILE_PATH)
    manifest = load_json(EVIDENCE_MANIFEST_PATH)
    validate_profile_document(profile)
    validate_evidence_manifest(manifest)
    validate_profile_manifest_link(profile, manifest)
    hardening = load_json(HARDENING_PATH)
    validate_hardening_document(hardening)
    validate_hardening_manifest_link(hardening, manifest)
    validate_profile_markdown(PROFILE_MARKDOWN_PATH.read_text(encoding="utf-8"))
    validate_portfolio_markdown(HARDENING_MARKDOWN_PATH.read_text(encoding="utf-8"))
    validate_proposal_markdown(PROPOSAL_PATH.read_text(encoding="utf-8"))
    validate_diagrams()
    validate_artifact_hashes()


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["--print-hashes"]:
        print(json.dumps(refresh_hash_values(), indent=2, sort_keys=True))
        return 0
    if arguments:
        print("usage: check_p2p_nat_g2_restricted_fork_profile.py [--print-hashes]", file=sys.stderr)
        return 2
    try:
        validate_all()
    except (RestrictedForkValidationError, OSError, UnicodeError) as error:
        print(f"G2 restricted-fork profile validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "G2 restricted-fork profile validation passed: Pion v4.3.0 remains "
        "unselected; only rung-two decision preparation is open."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
