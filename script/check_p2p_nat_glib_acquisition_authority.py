#!/usr/bin/env python3
"""Validate the exact GLib 2.64.2 source-acquisition authority."""

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
PHASE_ROOT = SPIKE_ROOT / "phase-a"
DECISION_PATH = SPIKE_ROOT / "decision-v5.json"
HANDOFF_PATH = DESIGN_ROOT / "implementation/handoff-v8.json"
PROGRESS_PATH = PHASE_ROOT / "progress-v6.json"
DECISION_ID = "production_p2p_nat_v1_controlled_network_spike_decision_v5"
HANDOFF_ID = "production_p2p_nat_v1_handoff_v8"
CHECKSUM_URL = "https://download.gnome.org/sources/glib/2.64/glib-2.64.2.sha256sum"
ARCHIVE_URL = "https://download.gnome.org/sources/glib/2.64/glib-2.64.2.tar.xz"
ARCHIVE_SHA256 = "9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277"
HASHES = {
    SPIKE_ROOT / "decision-v4.json": "a8a60ad80f9d83ebf29aae3d030b2d129bc98e7a88b4b05691327f6d08731809",
    PHASE_ROOT / "offline-source-intake-v3.json": "7a8d36474b6704a2e7312fb9697b4b77b555d98945207b421d138834e1b7d4c5",
    PHASE_ROOT / "libnice-dependency-closure-v1.json": "83604bfc0cbcce3a43cdcc62990ba8698576b219eed51d66c0c077118a0afab4",
    DESIGN_ROOT / "implementation/handoff-v7.json": "22306a0f057cf9eaf720c865ea7e46ed703a37fba93493eb937f592abefa5a58",
    PHASE_ROOT / "progress-v5.json": "f7680cffe2402545ec3b3ede970bb7aa2795910f0f42240e0d27b0256daebc1f",
    DECISION_PATH: "d1c31cce719aae8f3fbb5f5ab6fd564091d7ef72966e7f25a6e54ca8adb69d95",
    HANDOFF_PATH: "e51b970f5bc18800d462bcfea0f252c297648a8f07d54a19072416b405623613",
}
FORBIDDEN = (
    "compilerInvocationAuthorized", "staticLibraryArchiverInvocationAuthorized",
    "buildSystemExecutionAllowed", "sourceForkAuthorized", "socketCreationAllowed",
    "runtimeNetworkIOAllowed", "harnessNetworkIOAllowed", "controlledSpikeNetworkIOAllowed",
    "controlledSpikeSocketExecutionAuthorized", "phaseBExecutionAuthorized",
    "phaseBNetworkIOAllowed", "productionNetworkIOAllowed", "productionDeploymentAuthorized",
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


def parse_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_names)
    except json.JSONDecodeError as error:
        fail(f"{path.name}: invalid JSON: {error}")
    if not isinstance(value, dict):
        fail(f"{path.name}: expected object")
    return value


def require(actual: Any, expected: Any, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        fail(f"{label}: canonical value drifted")


def validate_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        fail(f"{path.relative_to(ROOT)}: SHA-256 drifted")


def validate_url(actual: Any, expected: str, label: str) -> None:
    require(actual, expected, label)
    parsed = urlsplit(actual)
    if parsed.scheme != "https" or parsed.hostname != "download.gnome.org":
        fail(f"{label}: wrong scheme or host")
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        fail(f"{label}: URL decoration forbidden")


def validate_forbidden(authority: Any, label: str) -> None:
    if not isinstance(authority, dict):
        fail(f"{label}: expected object")
    for key in FORBIDDEN:
        require(authority.get(key), False, f"{label}.{key}")


def validate_decision(value: dict[str, Any]) -> None:
    require(value.get("decisionId"), DECISION_ID, "decision id")
    require(value.get("status"), "closed_glib_2_64_2_source_acquisition_authorized", "decision status")
    acquisition = value.get("acquisitionAuthorization", {})
    require(acquisition.get("networkIOAllowed"), True, "decision network")
    require(acquisition.get("oneShotAuthority"), True, "decision one-shot")
    require(acquisition.get("exactRequestCount"), 2, "decision request count")
    require(acquisition.get("allowedHosts"), ["download.gnome.org"], "decision hosts")
    for key in ("redirectFollowingAllowed", "environmentProxyAllowed", "packageManagerAcquisitionAllowed"):
        require(acquisition.get(key), False, f"decision {key}")
    artifacts = acquisition.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        fail("decision artifacts: expected exactly two")
    validate_url(artifacts[0].get("url"), CHECKSUM_URL, "checksum URL")
    validate_url(artifacts[1].get("url"), ARCHIVE_URL, "archive URL")
    require(artifacts[0].get("maximumBytes"), 4096, "checksum limit")
    require(artifacts[1].get("maximumBytes"), 67_108_864, "archive limit")
    require(artifacts[1].get("expectedSha256"), ARCHIVE_SHA256, "archive hash")
    further = value.get("furtherDependencyAcquisition", {})
    require(further.get("effectiveAuthority"), False, "further dependency gate")
    require(further.get("opensslAcquisitionAuthorized"), False, "OpenSSL gate")
    authority = value.get("executionAuthority")
    require(authority.get("glibSourceAcquisitionNetworkIOAllowed"), True, "GLib network")
    require(authority.get("otherDependencyAcquisitionNetworkIOAllowed"), False, "other dependency network")
    require(authority.get("sourceOrGeneratorExecutionAllowed"), False, "source execution")
    validate_forbidden(authority, "decision authority")


def validate_handoff(value: dict[str, Any]) -> None:
    require(value.get("handoffId"), HANDOFF_ID, "handoff id")
    require(value.get("sourceDecision", {}).get("sha256"), HASHES[DECISION_PATH], "handoff decision hash")
    requests = value.get("authorizedAcquisition", {}).get("requests")
    if not isinstance(requests, list) or len(requests) != 2:
        fail("handoff requests: expected exactly two")
    validate_url(requests[0].get("url"), CHECKSUM_URL, "handoff checksum URL")
    validate_url(requests[1].get("url"), ARCHIVE_URL, "handoff archive URL")
    authority = value.get("authorization")
    require(authority.get("glibSourceAcquisitionAuthorized"), True, "handoff GLib acquisition")
    require(authority.get("otherDependencyAcquisitionAuthorized"), False, "handoff other dependency")
    require(authority.get("opensslAcquisitionAuthorized"), False, "handoff OpenSSL")
    require(authority.get("sourceOrGeneratorExecutionAllowed"), False, "handoff source execution")
    validate_forbidden(authority, "handoff authority")


def validate_progress(value: dict[str, Any]) -> None:
    require(value.get("artifactId"), "production_p2p_nat_v1_controlled_spike_phase_a_progress_v6", "progress id")
    require(value.get("status"), "glib_2_64_2_source_acquisition_authorized_not_started", "progress status")
    require(value.get("currentAuthority", {}).get("decision", {}).get("sha256"), HASHES[DECISION_PATH], "progress decision hash")
    require(value.get("currentAuthority", {}).get("handoff", {}).get("sha256"), HASHES[HANDOFF_PATH], "progress handoff hash")
    state = value.get("acquisitionState")
    require(state.get("authorizedRequestCount"), 2, "progress request count")
    require(state.get("completedRequestCount"), 0, "progress completed count")
    for key in ("officialChecksumPresent", "sourceArchivePresent", "sourceExtracted", "sourceManifestRecorded", "transitiveDependencyClosureRecorded", "otherDependencyAcquisitionAuthorized"):
        require(state.get(key), False, f"progress {key}")
    authority = value.get("authorization")
    require(authority.get("glibSourceAcquisitionNetworkIOAllowed"), True, "progress GLib network")
    require(authority.get("otherDependencyAcquisitionNetworkIOAllowed"), False, "progress other dependency")
    require(authority.get("opensslAcquisitionNetworkIOAllowed"), False, "progress OpenSSL")
    require(authority.get("sourceOrGeneratorExecutionAllowed"), False, "progress source execution")
    validate_forbidden(authority, "progress authority")


def main() -> int:
    try:
        for path, expected in HASHES.items():
            validate_hash(path, expected)
        validate_decision(parse_json(DECISION_PATH))
        validate_handoff(parse_json(HANDOFF_PATH))
        validate_progress(parse_json(PROGRESS_PATH))
    except (AuthorityValidationError, OSError) as error:
        print(f"GLib acquisition authority check failed: {error}", file=sys.stderr)
        return 1
    print("GLib acquisition authority check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
