#!/usr/bin/env python3
"""Validate the bounded libnice 0.1.23 source-acquisition authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DESIGN_ROOT = ROOT / "docs/security-hardening/production-p2p-nat-v1"
SPIKE_ROOT = DESIGN_ROOT / "controlled-network-spike"
DECISION_PATH = SPIKE_ROOT / "decision-v4.json"
DECISION_MARKDOWN_PATH = SPIKE_ROOT / "decision-v4.md"
HANDOFF_PATH = DESIGN_ROOT / "implementation/handoff-v7.json"
HANDOFF_MARKDOWN_PATH = DESIGN_ROOT / "implementation/handoff-v7.md"
PROGRESS_PATH = SPIKE_ROOT / "phase-a/progress-v4.json"

PROFILE_ID = "production_p2p_nat_v1_recommended"
DECISION_ID = "production_p2p_nat_v1_controlled_network_spike_decision_v4"
HANDOFF_ID = "production_p2p_nat_v1_handoff_v7"
SOURCE_URL = "https://libnice.freedesktop.org/releases/libnice-0.1.23.tar.gz"
SIGNATURE_URL = SOURCE_URL + ".asc"
SOURCE_PATH = "build/offline-source/libnice-0.1.23/original/libnice-0.1.23.tar.gz"
SIGNATURE_PATH = SOURCE_PATH + ".asc"

HASHES = {
    SPIKE_ROOT / "decision-v3.json": "ae129fc214ac96abb3e1393b895cf03ddf284004ce9a1d3ac2005b4cb5d2022d",
    SPIKE_ROOT / "review-v2.json": "d20c9ddcf572edbfeb8df3bf899cb32f0f61c684974ea074f7ed841332c4122b",
    DESIGN_ROOT / "implementation/handoff-v6.json": "87af07548bfeb17b54642bb16c00fab2652006ba9401a05ccce8d134bba894e5",
    SPIKE_ROOT / "phase-a/progress-v3.json": "22a285b0de28f593f39f6b2a3f43e2966f97e711dd97c6bfc240325c88827db8",
    DECISION_PATH: "a8a60ad80f9d83ebf29aae3d030b2d129bc98e7a88b4b05691327f6d08731809",
    HANDOFF_PATH: "22306a0f057cf9eaf720c865ea7e46ed703a37fba93493eb937f592abefa5a58",
}

FORBIDDEN_AUTHORITY = (
    "compilerInvocationAuthorized",
    "staticLibraryArchiverInvocationAuthorized",
    "buildSystemExecutionAllowed",
    "configureExecutionAllowed",
    "sourceExecutionAllowed",
    "testExecutionAllowed",
    "sourceForkAuthorized",
    "socketCreationAllowed",
    "runtimeNetworkIOAllowed",
    "harnessNetworkIOAllowed",
    "controlledSpikeNetworkIOAllowed",
    "controlledSpikeSocketExecutionAuthorized",
    "phaseBExecutionAuthorized",
    "phaseBNetworkIOAllowed",
    "productionNetworkIOAllowed",
    "productionDeploymentAuthorized",
)


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


def require_exact(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        fail(f"{label}: canonical value drifted")


def require_false_map(value: Any, keys: tuple[str, ...], label: str) -> None:
    if not isinstance(value, dict):
        fail(f"{label}: expected object")
    for key in keys:
        if key not in value:
            fail(f"{label}.{key}: missing")
        require_exact(value[key], False, f"{label}.{key}")


def validate_file_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        fail(f"{path.relative_to(ROOT)}: SHA-256 drifted; expected {expected}, got {actual}")


def validate_locked_url(url: Any, expected: str, label: str) -> None:
    require_exact(url, expected, label)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "libnice.freedesktop.org":
        fail(f"{label}: must use the exact HTTPS official host")
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        fail(f"{label}: userinfo, port, query, and fragment are forbidden")


def validate_decision(document: Any) -> None:
    if not isinstance(document, dict):
        fail("decision-v4: expected object")
    require_exact(document.get("decisionId"), DECISION_ID, "decision-v4.decisionId")
    require_exact(document.get("profileId"), PROFILE_ID, "decision-v4.profileId")
    require_exact(document.get("status"), "closed_libnice_source_acquisition_authorized_dependency_lock_pending", "decision-v4.status")
    require_exact(document.get("approvalSource"), "explicit_user_instruction", "decision-v4.approvalSource")
    require_exact(document.get("supersedes"), {
        "path": "decision-v3.json",
        "decisionId": "production_p2p_nat_v1_controlled_network_spike_decision_v3",
        "sha256": HASHES[SPIKE_ROOT / "decision-v3.json"],
    }, "decision-v4.supersedes")
    candidate = document.get("candidateEvaluation")
    require_exact(candidate.get("selectionStatus"), "not_selected", "decision-v4 candidate selection")
    require_exact(candidate.get("evaluationStatus"), "approved_for_bounded_phase_a_read_only_source_audit", "decision-v4 evaluation")
    require_exact(candidate.get("implicitProductionSelectionAllowed"), False, "decision-v4 implicit selection")

    acquisition = document.get("acquisitionAuthorization")
    require_exact(acquisition.get("networkIOAllowed"), True, "decision-v4 acquisition network")
    require_exact(acquisition.get("oneShotAuthority"), True, "decision-v4 one-shot")
    require_exact(acquisition.get("exactRequestCount"), 2, "decision-v4 request count")
    require_exact(acquisition.get("allowedHosts"), ["libnice.freedesktop.org"], "decision-v4 allowed hosts")
    for key in ("redirectFollowingAllowed", "environmentProxyAllowed", "packageManagerAcquisitionAllowed"):
        require_exact(acquisition.get(key), False, f"decision-v4 acquisition {key}")
    artifacts = acquisition.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        fail("decision-v4 artifacts: expected exactly two")
    validate_locked_url(artifacts[0].get("url"), SOURCE_URL, "decision-v4 source URL")
    validate_locked_url(artifacts[1].get("url"), SIGNATURE_URL, "decision-v4 signature URL")
    require_exact(artifacts[0].get("relativePath"), SOURCE_PATH, "decision-v4 source path")
    require_exact(artifacts[1].get("relativePath"), SIGNATURE_PATH, "decision-v4 signature path")
    require_exact(artifacts[0].get("maximumBytes"), 33_554_432, "decision-v4 source size")
    require_exact(artifacts[1].get("maximumBytes"), 65_536, "decision-v4 signature size")

    dependency = document.get("dependencyAcquisition")
    require_exact(dependency.get("userApprovalRecorded"), True, "decision-v4 dependency approval")
    require_exact(dependency.get("effectiveAuthority"), False, "decision-v4 dependency gate")
    require_exact(dependency.get("scopeExpansionApprovalRequired"), True, "decision-v4 scope expansion")
    authority = document.get("executionAuthority")
    require_exact(authority.get("offlineSourceInspectionAuthorized"), True, "decision-v4 inspection")
    require_exact(authority.get("sourceAcquisitionNetworkIOAllowed"), True, "decision-v4 source acquisition")
    require_exact(authority.get("dependencyAcquisitionNetworkIOAllowed"), False, "decision-v4 dependency acquisition")
    require_false_map(authority, FORBIDDEN_AUTHORITY, "decision-v4.executionAuthority")


def validate_handoff(document: Any) -> None:
    if not isinstance(document, dict):
        fail("handoff-v7: expected object")
    require_exact(document.get("handoffId"), HANDOFF_ID, "handoff-v7.handoffId")
    require_exact(document.get("profileId"), PROFILE_ID, "handoff-v7.profileId")
    require_exact(document.get("sourceDecision"), {
        "path": "../controlled-network-spike/decision-v4.json",
        "decisionId": DECISION_ID,
        "sha256": HASHES[DECISION_PATH],
    }, "handoff-v7.sourceDecision")
    requests = document.get("authorizedAcquisition", {}).get("requests")
    if not isinstance(requests, list) or len(requests) != 2:
        fail("handoff-v7 requests: expected exactly two")
    validate_locked_url(requests[0].get("url"), SOURCE_URL, "handoff-v7 source URL")
    validate_locked_url(requests[1].get("url"), SIGNATURE_URL, "handoff-v7 signature URL")
    authority = document.get("authorization")
    require_exact(authority.get("libniceSourceAcquisitionAuthorized"), True, "handoff-v7 source acquisition")
    require_exact(authority.get("libniceDependencyAcquisitionAuthorized"), False, "handoff-v7 dependency acquisition")
    require_exact(authority.get("sourceAcquisitionNetworkIOAllowed"), True, "handoff-v7 source network")
    require_exact(authority.get("dependencyAcquisitionNetworkIOAllowed"), False, "handoff-v7 dependency network")
    require_false_map(authority, FORBIDDEN_AUTHORITY, "handoff-v7.authorization")


def validate_progress(document: Any) -> None:
    if not isinstance(document, dict):
        fail("progress-v4: expected object")
    require_exact(document.get("artifactId"), "production_p2p_nat_v1_controlled_spike_phase_a_progress_v4", "progress-v4.artifactId")
    require_exact(document.get("status"), "libnice_source_acquisition_authorized_not_started", "progress-v4.status")
    current = document.get("currentAuthority")
    require_exact(current.get("decision", {}).get("sha256"), HASHES[DECISION_PATH], "progress-v4 decision hash")
    require_exact(current.get("handoff", {}).get("sha256"), HASHES[HANDOFF_PATH], "progress-v4 handoff hash")
    state = document.get("acquisitionState")
    require_exact(state.get("authorityStatus"), "authorized_not_consumed", "progress-v4 authority state")
    require_exact(state.get("authorizedRequestCount"), 2, "progress-v4 request count")
    require_exact(state.get("completedRequestCount"), 0, "progress-v4 completed requests")
    for key in ("sourceArchivePresent", "detachedSignaturePresent", "sourceExtracted", "sourceManifestRecorded", "dependencyClosureRecorded", "dependencyAcquisitionAuthorized", "dependencyArtifactsAcquired"):
        require_exact(state.get(key), False, f"progress-v4 acquisition {key}")
    authority = document.get("executionAuthority")
    require_exact(authority.get("libniceSourceAcquisitionNetworkIOAllowed"), True, "progress-v4 source network")
    require_exact(authority.get("dependencyAcquisitionNetworkIOAllowed"), False, "progress-v4 dependency network")
    require_false_map(authority, FORBIDDEN_AUTHORITY, "progress-v4.executionAuthority")


def validate_markdown(path: Path, required: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in required:
        if marker not in text:
            fail(f"{path.relative_to(ROOT)}: missing {marker!r}")


def main() -> int:
    try:
        for path, expected in HASHES.items():
            validate_file_hash(path, expected)
        decision = parse_json(DECISION_PATH.read_text(encoding="utf-8"), "decision-v4")
        handoff = parse_json(HANDOFF_PATH.read_text(encoding="utf-8"), "handoff-v7")
        progress = parse_json(PROGRESS_PATH.read_text(encoding="utf-8"), "progress-v4")
        validate_decision(decision)
        validate_handoff(handoff)
        validate_progress(progress)
        validate_markdown(DECISION_MARKDOWN_PATH, (SOURCE_URL, SIGNATURE_URL, "Compiler", "Phase B"))
        validate_markdown(HANDOFF_MARKDOWN_PATH, ("libnice 0.1.23", "Dependency acquisition remains disabled", "Compiler"))
    except (AuthorityValidationError, OSError) as error:
        print(f"libnice acquisition authority check failed: {error}", file=sys.stderr)
        return 1
    print("libnice acquisition authority check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
