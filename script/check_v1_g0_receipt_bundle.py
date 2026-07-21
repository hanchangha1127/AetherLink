#!/usr/bin/env python3
"""Validate the dormant V3 G0 complete-receipt-bundle contract lineage."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

try:
    from script import check_v1_g0_checkpoint as checkpoint
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_publication_receipt as publication
except ModuleNotFoundError:
    import check_v1_g0_checkpoint as checkpoint
    import check_v1_g0_decision as decision
    import check_v1_g0_publication_receipt as publication


ROOT = Path(__file__).resolve().parents[1]

V3_AMENDMENT_PATH = "docs/v1/g0/assurance-closure-amendment-v3.json"
V3_CHECKPOINT_PATH = (
    "docs/v1/g0/assurance-closure-amendment-checkpoint-v3.json"
)
RECORDED_PUBLICATION_RECEIPT_PATH = (
    "docs/v1/g0/assurance-closure-publication-receipt-candidate-v3.json"
)
OWNER_CATALOG_INPUT_PATH = "docs/v1/g0/owner-catalog-input-candidate-v1.json"
EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_PATH = (
    "docs/v1/g0/evidence-supporting-artifact-candidate-profile-v1.json"
)
EVIDENCE_SUPPORTING_ARTIFACT_CANDIDATE_PATHS = (
    "docs/evidence/g0-reviewed-commit-scope-candidate-v1.json",
    "docs/evidence/g0-published-checkpoint-candidate-v1.json",
)

MAX_V3_AMENDMENT_BYTES = 262_144
MAX_V3_CHECKPOINT_BYTES = 131_072
MAX_RECORDED_PUBLICATION_RECEIPT_BYTES = 65_536
MAX_OWNER_CATALOG_INPUT_BYTES = 262_144
MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES = 131_072
MAX_EVIDENCE_SUPPORTING_ARTIFACT_DEPTH = 8
MAX_EVIDENCE_SUPPORTING_ARTIFACT_ARRAY_ITEMS = 32
MAX_EVIDENCE_SUPPORTING_ARTIFACT_STRING_BYTES = 4_096

EXPECTED_RECORDED_PUBLICATION_RECEIPT_RAW_SHA256 = (
    "d9d6c43713a4550f88080306a0150a6a7325f7575e369b2d80cd18902b272856"
)
EXPECTED_RECORDED_REPOSITORY_REF = "github:hanchangha1127/AetherLink"
EXPECTED_RECORDED_COMMIT_OBJECT_ID = (
    "12c381547935b96d383ac39976261ea6c3ce6a5b"
)
EXPECTED_RECORDED_REMOTE_READBACK_AT = "2026-07-20T12:05:44Z"
EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256 = (
    "0221d2d49e4bcccfd34fb6905102117fbf5632e27d3d2f2e23d53e29f47752bc"
)
EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256 = (
    "f8ad6742fcb569f408b5f4087b20f11f32cb497a8f9eec2fc3f255d8b22c226f"
)

LINEAGE_PATHS = (
    publication.PARENT_ASSURANCE_PATH,
    publication.PARENT_CHECKPOINT_PATH,
    publication.AMENDMENT_PATH,
    publication.AMENDMENT_CHECKPOINT_PATH,
    V3_AMENDMENT_PATH,
    V3_CHECKPOINT_PATH,
)
LINEAGE_ROLES = (
    "v1_parent_assurance",
    "v1_parent_checkpoint",
    "v2_parent_amendment",
    "v2_parent_checkpoint",
    "v3_amendment",
    "v3_checkpoint",
)
LINEAGE_MAXIMUM_BYTES = (
    checkpoint.MAX_ASSURANCE_BYTES,
    checkpoint.MAX_CHECKPOINT_BYTES,
    publication.MAX_AMENDMENT_BYTES,
    publication.MAX_AMENDMENT_CHECKPOINT_BYTES,
    MAX_V3_AMENDMENT_BYTES,
    MAX_V3_CHECKPOINT_BYTES,
)
LINEAGE_RAW_SHA256 = (
    decision.EXPECTED_ASSURANCE_BYTE_SHA256,
    decision.EXPECTED_ASSURANCE_CHECKPOINT_BYTE_SHA256,
    decision.EXPECTED_ASSURANCE_AMENDMENT_BYTE_SHA256,
    decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256,
    "f8314bcb37f98d0877e8d2a5279b2702fa6a5883f7efb4fcd91af5508eb126bc",
    "37462cd8303ce61742bc480d0f7d37e0ccb380ec12375cc8c8d10169aebf4dc5",
)
LINEAGE_CANONICAL_SHA256 = (
    decision.EXPECTED_ASSURANCE_CANONICAL_SHA256,
    decision.EXPECTED_ASSURANCE_CHECKPOINT_CANONICAL_SHA256,
    decision.EXPECTED_ASSURANCE_AMENDMENT_CANONICAL_SHA256,
    decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_CANONICAL_SHA256,
    "1bc500f2798da19bf74a1513f15d8822b5c41fa73c28795e1501696c1b4dad97",
    "a9ceca766845f0e2d23987425eeee5498f9bf5b114a3f9c4d272867cfe70d7f3",
)

EXPECTED_EFFECTIVE_V2_SHA256 = (
    decision.EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256
)
EXPECTED_CLOSURE_V2_SHA256 = (
    "d8dcc755ba58b2e5eb72f5df7ce09ff9586504105eddb75290b9c11f5478a20d"
)
EXPECTED_EFFECTIVE_V3_SHA256 = (
    "e8f661094a678a2ac0966d8b35de46824316883a845eb9ae8c6e9f76df18ad4b"
)
EXPECTED_CLOSURE_V3_SHA256 = (
    "79b0d7275bcf371e8b9ab5a6b123969474bfbc86b1d7e78fcb28ed7256e3a93c"
)

EXPECTED_V3_OPERATIONS = (
    ("replace", "/schemaVersion"),
    ("replace", "/assuranceId"),
    ("replace", "/g0ClosureContract/schemaVersion"),
    ("add", "/g0ClosureContract/sourceBindings/receiptBundleProfile"),
    ("add", "/g0ClosureContract/receiptBundleProfile"),
    ("add", "/g0ClosureContract/ownerBindingProfile"),
    ("replace", "/g0ClosureContract/evidenceCatalogRecordProfile"),
    ("add", "/g0ClosureContract/authorityBindingProfile"),
    ("add", "/g0ClosureContract/runnerAttestationProfile"),
    ("replace", "/g0ClosureContract/gateReceiptProfile"),
    ("replace", "/g0ClosureContract/approvalReceiptProfile"),
    ("replace", "/g0ClosureContract/publicationReceiptProfile"),
    ("replace", "/g0ClosureContract/receiptActivationPolicy"),
)

COMPLETE_BUNDLE_DORMANT_MESSAGE = (
    "G0 V3 complete receipt bundle candidate is dormant_non_authorizing; "
    "it cannot establish trust, activate receipts, close G0, or authorize G1a"
)
RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE = (
    "G0 V3 recorded publication receipt candidate is dormant_non_authorizing; "
    "it cannot establish independent trust, activate receipts, close G0, or authorize G1a"
)
OWNER_CATALOG_INPUT_DORMANT_MESSAGE = (
    "G0 V3 owner/catalog input candidate is draft_unverified_non_authorizing; "
    "it cannot authenticate owners, verify evidence, accept receipts, close G0, or authorize G1a"
)
EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE = (
    "G0 evidence supporting artifact candidate is "
    "session_observation_unverified_non_authorizing; it cannot verify evidence, "
    "establish provenance, accept receipts, close G0, or authorize G1a"
)
COMPLETE_BUNDLE_FIELDS = (
    "documentType",
    "schemaVersion",
    "effectiveAssuranceCanonicalSha256",
    "publicationReceipt",
    "ownerBindings",
    "evidenceCatalog",
    "authorityBindings",
    "runnerAttestations",
    "gateReceipts",
    "approvalReceipts",
)
PUBLICATION_RECEIPT_FIELDS = (
    "repositoryRef",
    "commitObjectId",
    "artifactBindings",
    "parentEffectiveAssuranceCanonicalSha256",
    "parentClosureSchemaVersion",
    "parentClosureCanonicalSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureSchemaVersion",
    "effectiveClosureCanonicalSha256",
    "remoteCheckpointPath",
    "remoteCheckpointRawSha256",
    "remoteReadbackAt",
    "remoteReadbackSha256",
)
ARTIFACT_BINDING_FIELDS = ("role", "path", "rawSha256", "canonicalSha256")
OWNER_CATALOG_INPUT_FIELDS = (
    "documentType",
    "schemaVersion",
    "status",
    "contractBinding",
    "responses",
    "state",
)
OWNER_CATALOG_CONTRACT_BINDING_FIELDS = (
    "repositoryRef",
    "publicationCommitObjectId",
    "publicationCheckpointSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
)
OWNER_CATALOG_RESPONSE_FIELDS = (
    "blockerId",
    "requirementDisposition",
    "ownerCandidates",
    "evidenceCandidates",
    "changeRequestRefCandidate",
    "inputSourceRefCandidate",
)
OWNER_CANDIDATE_FIELDS = ("role", "ownerBindingRefCandidate")
EVIDENCE_CANDIDATE_FIELDS = (
    "evidenceKind",
    "evidenceInputRefCandidate",
    "supportingArtifactRefCandidate",
)
OWNER_CATALOG_STATE_FIELDS = (
    "ownerIdentityAuthenticated",
    "evidenceCatalogVerified",
    "approvalReceiptsAccepted",
    "blockerClosureDerived",
    "receiptActivationAllowed",
    "g0ExitComplete",
    "g1aMayStartNow",
)
OWNER_CATALOG_REQUIREMENT_DISPOSITIONS = (
    "proposed_as_written",
    "proposed_with_changes",
    "not_available",
)
OWNER_CATALOG_PREVIEW_REQUEST_FIELDS = (
    "documentType",
    "schemaVersion",
    "proposals",
)
OWNER_CATALOG_PREVIEW_PROPOSAL_FIELDS = (
    "blockerId",
    "requirementDisposition",
    "ownerCandidates",
    "evidenceCandidates",
    "changeRequestCandidateVersion",
    "inputSessionDate",
    "inputSessionItem",
)
OWNER_CATALOG_PREVIEW_OWNER_FIELDS = ("role", "candidateVersion")
OWNER_CATALOG_PREVIEW_EVIDENCE_FIELDS = (
    "evidenceKind",
    "candidateVersion",
    "supportingArtifactPresent",
)
EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_FIELDS = (
    "documentType",
    "schemaVersion",
    "profileId",
    "status",
    "contractBinding",
    "artifactPaths",
    "selectorSnapshotBinding",
    "commonEnvelopeProfile",
    "reviewedCommitScopePayloadProfile",
    "publishedCheckpointPayloadProfile",
    "resourceBounds",
    "sensitiveDataPolicy",
    "authorizationBoundary",
    "supersessionPolicy",
)
EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_CONTRACT_FIELDS = (
    "repositoryRef",
    "blockerId",
    "publicationCommitObjectId",
    "publicationCheckpointPath",
    "publicationCheckpointRawSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
    "requiredEvidenceKinds",
)
EVIDENCE_SUPPORTING_ARTIFACT_PATH_FIELDS = (
    "evidenceKind",
    "candidateVersion",
    "path",
)
EVIDENCE_SELECTOR_SNAPSHOT_FIELDS = (
    "ownerCatalogInputCandidatePath",
    "ownerCatalogInputCandidateRawSha256",
    "responseIndex",
    "blockerId",
    "inputSourceRefCandidate",
    "ownerBindingRefCandidate",
    "evidenceSelectors",
    "artifactInstancePolicy",
)
EVIDENCE_SELECTOR_SNAPSHOT_ENTRY_FIELDS = (
    "evidenceKind",
    "evidenceSelectorIndex",
    "candidateVersion",
    "evidenceInputRefCandidate",
    "supportingArtifactPresent",
    "supportingArtifactRefCandidate",
    "reservedArtifactPath",
)
EVIDENCE_SUPPORTING_ARTIFACT_FIELDS = (
    "documentType",
    "schemaVersion",
    "artifactId",
    "evidenceKind",
    "status",
    "profileRef",
    "contractBinding",
    "selectorBinding",
    "payload",
    "trustBoundary",
    "state",
)
EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_REF_FIELDS = (
    "path",
    "profileId",
    "rawSha256",
)
EVIDENCE_SUPPORTING_ARTIFACT_CONTRACT_FIELDS = (
    "repositoryRef",
    "blockerId",
    "publicationCommitObjectId",
    "publicationCheckpointPath",
    "publicationCheckpointRawSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
)
EVIDENCE_SUPPORTING_ARTIFACT_SELECTOR_BINDING_FIELDS = (
    "ownerCatalogInputCandidatePath",
    "ownerCatalogInputCandidateRawSha256",
    "responseIndex",
    "blockerId",
    "inputSourceRefCandidate",
    "ownerBindingRefCandidate",
    "evidenceSelectorIndex",
    "candidateVersion",
    "evidenceInputRefCandidate",
    "supportingArtifactPresent",
    "supportingArtifactRefCandidate",
    "reservedArtifactPath",
)
EVIDENCE_SUPPORTING_ARTIFACT_TRUST_FIELDS = (
    "observationClass",
    "independentInputsPresent",
    "requiredIndependentInputsAbsent",
    "catalogRecordDerivable",
    "authorityDerivable",
)
REVIEWED_COMMIT_SCOPE_PAYLOAD_FIELDS = (
    "baseCommitObjectId",
    "baseTreeObjectId",
    "publicationTreeObjectId",
    "scopeEntryCount",
    "scopeEntries",
    "scopeEntriesCanonicalSha256",
    "reviewClaim",
)
REVIEWED_COMMIT_SCOPE_ENTRY_FIELDS = (
    "path",
    "changeType",
    "fileMode",
    "blobObjectId",
    "byteLength",
    "rawSha256",
)
REVIEWED_COMMIT_SCOPE_CLAIM_FIELDS = (
    "disposition",
    "ownerBindingRefCandidate",
    "inputSourceRefCandidate",
    "claimedReviewRecordedAt",
)
PUBLISHED_CHECKPOINT_PAYLOAD_FIELDS = (
    "remoteRef",
    "checkpointPath",
    "checkpointBlobObjectId",
    "checkpointByteLength",
    "commitCheckpointRawSha256",
    "observedRemoteCheckpointRawSha256",
    "observationMethod",
    "observationStartedAt",
    "observationCompletedAt",
    "publicationReceiptCandidatePath",
    "publicationReceiptCandidateRawSha256",
    "standaloneAcquisitionTranscriptRef",
)
OWNER_BINDING_FIELDS = (
    "ownerBindingRef",
    "role",
    "ownerIdentityRef",
    "credentialRef",
    "identityRegistryRef",
    "identityRegistryRevision",
    "validFrom",
    "validUntil",
    "revocationRef",
    "provenanceRef",
)
EVIDENCE_RECORD_FIELDS = (
    "evidenceId",
    "evidenceKind",
    "evidenceClass",
    "subjectImplementationRevision",
    "subjectCheckpointSha256",
    "artifactPath",
    "artifactByteLength",
    "artifactSha256",
    "verificationMethod",
    "verifierIdentityRef",
    "verifiedAt",
    "provenanceRef",
)
AUTHORITY_BINDING_FIELDS = (
    "authorizationRef",
    "authorityIssuerRef",
    "checkId",
    "sourcePublicationCommit",
    "commandProfileId",
    "commandProfileSha256",
    "commandArgvSha256",
    "workingDirectorySha256",
    "environmentSha256",
    "allowedSideEffectsSha256",
    "notBefore",
    "notAfter",
    "revocationRef",
    "provenanceRef",
)
RUNNER_ATTESTATION_FIELDS = (
    "runnerAttestationRef",
    "runnerIdentityRef",
    "authorizationRef",
    "checkId",
    "sourcePublicationCommit",
    "commandProfileId",
    "commandProfileSha256",
    "commandArgvSha256",
    "workingDirectorySha256",
    "environmentSha256",
    "allowedSideEffectsSha256",
    "toolchainManifestSha256",
    "dependencyManifestSha256",
    "observationManifestSha256",
    "orderedStepResults",
    "startedAt",
    "completedAt",
    "exitCode",
    "sanitizedLogSha256",
    "evidenceRefs",
    "provenanceRef",
)
STEP_RESULT_FIELDS = ("stepId", "argvSha256", "startedAt", "completedAt", "exitCode")
GATE_RECEIPT_FIELDS = (
    "checkId",
    "authorizationRef",
    "runnerAttestationRef",
    "sourcePublicationCommit",
    "commandProfileId",
    "commandProfileSha256",
    "startedAt",
    "completedAt",
    "exitCode",
    "sanitizedLogSha256",
    "evidenceRefs",
)
APPROVAL_RECEIPT_FIELDS = (
    "role",
    "ownerIdentityRef",
    "status",
    "acceptedRevision",
    "acceptedPublicationCommit",
    "acceptedBlockerIds",
    "acceptedAt",
    "acceptanceEvidenceRefs",
)

MAX_COMPLETE_BUNDLE_BYTES = 4_194_304
MAX_COMPLETE_BUNDLE_DEPTH = 32
MAX_COMPLETE_BUNDLE_ARRAY_ITEMS = 256
MAX_COMPLETE_BUNDLE_STRING_BYTES = 4_096
MAX_REFERENCED_ARTIFACT_BYTES = 4_194_304

_GIT_OBJECT_ID_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_ID_PATTERN = re.compile(r"^g0-evidence-[a-z0-9_-]{1,96}$")
_OWNER_BINDING_REF_PATTERN = re.compile(
    r"^g0-owner-binding-[a-z0-9][a-z0-9_-]{0,95}-v[1-9][0-9]*$"
)
_AUTHORIZATION_REF_PATTERN = re.compile(
    r"^g0-authority-[a-z0-9][a-z0-9_-]{0,95}-v[1-9][0-9]*$"
)
_RUNNER_ATTESTATION_REF_PATTERN = re.compile(
    r"^g0-runner-attestation-[a-z0-9][a-z0-9_-]{0,95}-v[1-9][0-9]*$"
)
_CANONICAL_UTC_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_OWNER_BINDING_REF_CANDIDATE_PATTERN = re.compile(
    r"^owner-candidate:([a-z][a-z0-9-]{0,95}):v([1-9][0-9]{0,8})$"
)
_EVIDENCE_INPUT_REF_CANDIDATE_PATTERN = re.compile(
    r"^evidence-input-candidate:([a-z][a-z0-9-]{0,127}):v([1-9][0-9]{0,8})$"
)
_CHANGE_REQUEST_REF_CANDIDATE_PATTERN = re.compile(
    r"^change-request-candidate:([a-z][a-z0-9-]{0,127}):v([1-9][0-9]{0,8})$"
)
_INPUT_SOURCE_REF_CANDIDATE_PATTERN = re.compile(
    r"^user-input:session-([0-9]{8}):item-([1-9][0-9]{0,2})$"
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_equal(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not decision.exactly_equal(actual, expected):
        failures.append(f"{label} does not match the canonical V3 candidate")


def _require_exact(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not decision.exactly_equal(actual, expected):
        failures.append(f"{label} is not exact")


def _bounded_snapshot(
    value: object,
    label: str,
    maximum_bytes: int,
    failures: list[str],
) -> bytes | None:
    if type(value) not in (bytes, bytearray, memoryview):
        failures.append(f"{label} must be bytes")
        return None
    if type(value) is bytes:
        snapshot = value
    else:
        try:
            pinned = memoryview(value)
        except (BufferError, TypeError, ValueError):
            failures.append(f"{label} is not a readable byte buffer")
            return None
        try:
            observed_size = pinned.nbytes
            if observed_size == 0:
                failures.append(f"{label} must not be empty")
                return None
            if observed_size > maximum_bytes:
                failures.append(f"{label} exceeds {maximum_bytes} bytes")
                return None
            snapshot = pinned.tobytes()
        except (BufferError, MemoryError, TypeError, ValueError):
            failures.append(f"{label} is not a readable byte buffer")
            return None
        finally:
            pinned.release()
        if len(snapshot) != observed_size:
            failures.append(f"{label} changed size while being snapshotted")
            return None
    if len(snapshot) == 0:
        failures.append(f"{label} must not be empty")
        return None
    if len(snapshot) > maximum_bytes:
        failures.append(f"{label} exceeds {maximum_bytes} bytes")
        return None
    return snapshot


def _parse_object(
    raw: bytes,
    label: str,
    failures: list[str],
) -> dict[str, object] | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        failures.append(f"{label} is not UTF-8: {error}")
        return None
    try:
        parsed, parse_failures = decision.parse_g0_json_object(text, label)
    except RecursionError:
        failures.append(f"{label} exceeds the supported JSON nesting depth")
        return None
    failures.extend(parse_failures)
    return None if parse_failures else parsed


def _exact_ordered_object(
    value: object,
    expected_fields: tuple[str, ...],
    label: str,
    failures: list[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        failures.append(f"{label} must be an object")
        return {}
    if tuple(value) != expected_fields:
        failures.append(f"{label} fields or field order are not exact")
    return value


def _valid_opaque_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return (
        0 < len(encoded) <= MAX_COMPLETE_BUNDLE_STRING_BYTES
        and value == value.strip()
        and not any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    )


def _parse_canonical_utc(
    value: object,
    label: str,
    failures: list[str],
) -> datetime | None:
    if not isinstance(value, str) or _CANONICAL_UTC_PATTERN.fullmatch(value) is None:
        failures.append(f"{label} must be canonical RFC3339 UTC")
        return None
    try:
        parsed = datetime(
            int(value[0:4]),
            int(value[5:7]),
            int(value[8:10]),
            int(value[11:13]),
            int(value[14:16]),
            int(value[17:19]),
            tzinfo=timezone.utc,
        )
    except ValueError:
        failures.append(f"{label} must be a real canonical UTC timestamp")
        return None
    return parsed


def _validate_json_resources(
    value: object,
    failures: list[str],
    *,
    root_label: str,
    maximum_depth: int = MAX_COMPLETE_BUNDLE_DEPTH,
    maximum_items: int = MAX_COMPLETE_BUNDLE_ARRAY_ITEMS,
    maximum_string_bytes: int = MAX_COMPLETE_BUNDLE_STRING_BYTES,
) -> None:
    stack: list[tuple[object, int, str]] = [(value, 1, root_label)]
    while stack:
        current, depth, label = stack.pop()
        if depth > maximum_depth:
            failures.append(
                f"{label} exceeds maximum JSON depth {maximum_depth}"
            )
            continue
        if isinstance(current, str):
            try:
                encoded = current.encode("utf-8")
            except UnicodeEncodeError:
                failures.append(f"{label} contains a non-UTF-8 Unicode scalar")
                continue
            if len(encoded) > maximum_string_bytes:
                failures.append(
                    f"{label} exceeds {maximum_string_bytes} UTF-8 bytes"
                )
        elif isinstance(current, list):
            if len(current) > maximum_items:
                failures.append(
                    f"{label} exceeds {maximum_items} array items"
                )
                continue
            for index, child in enumerate(reversed(current)):
                actual_index = len(current) - index - 1
                stack.append((child, depth + 1, f"{label}[{actual_index}]"))
        elif isinstance(current, dict):
            if len(current) > maximum_items:
                failures.append(
                    f"{label} exceeds {maximum_items} object fields"
                )
                continue
            for key, child in reversed(tuple(current.items())):
                try:
                    encoded_key = key.encode("utf-8")
                except UnicodeEncodeError:
                    failures.append(f"{label} key contains a non-UTF-8 Unicode scalar")
                    continue
                if len(encoded_key) > maximum_string_bytes:
                    failures.append(
                        f"{label} key exceeds {maximum_string_bytes} UTF-8 bytes"
                    )
                stack.append((child, depth + 1, f"{label}.{key}"))


def _safe_artifact_path(value: object) -> bool:
    try:
        checkpoint.canonical_relative_path(value, "receipt evidence artifact path")
    except checkpoint.CheckpointValidationError:
        return False
    return True


def _canonical_candidate_version(
    value: object,
    pattern: re.Pattern[str],
    canonical_identifier: object,
) -> int | None:
    if not isinstance(value, str) or not isinstance(canonical_identifier, str):
        return None
    match = pattern.fullmatch(value)
    if match is None or match.group(1) != canonical_identifier.replace("_", "-"):
        return None
    return int(match.group(2))


def _safe_supporting_artifact_candidate(
    value: object,
    evidence_kind: object,
    candidate_version: int | None,
) -> bool:
    if value is None:
        return True
    if (
        not isinstance(value, str)
        or not isinstance(evidence_kind, str)
        or candidate_version is None
    ):
        return False
    expected = (
        "docs/evidence/g0-"
        f"{evidence_kind.replace('_', '-')}-candidate-v{candidate_version}.json"
    )
    return value == expected and _safe_artifact_path(value)


def _valid_input_source_ref_candidate(value: object) -> bool:
    if not isinstance(value, str):
        return False
    match = _INPUT_SOURCE_REF_CANDIDATE_PATTERN.fullmatch(value)
    if match is None:
        return False
    session_date = match.group(1)
    try:
        datetime(
            int(session_date[0:4]),
            int(session_date[4:6]),
            int(session_date[6:8]),
        )
    except ValueError:
        return False
    return True


def _exact_zero(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _materialize_effective_v3(
    raw_blobs: tuple[bytes, ...],
    failures: list[str],
) -> dict[str, object] | None:
    assurance = _parse_object(raw_blobs[0], "G0 V3 parent assurance", failures)
    amendment_v2 = _parse_object(raw_blobs[2], "G0 V3 V2 amendment", failures)
    amendment_v3 = _parse_object(raw_blobs[4], "G0 V3 amendment", failures)
    if assurance is None or amendment_v2 is None or amendment_v3 is None:
        return None
    effective_v2 = decision.apply_assurance_amendment_operations(
        assurance,
        amendment_v2.get("operations"),
        failures,
    )
    return _apply_v3_operations(
        effective_v2,
        amendment_v3.get("operations"),
        failures,
    )


def _unique_string_sequence(
    value: object,
    label: str,
    failures: list[str],
) -> tuple[str, ...]:
    if not isinstance(value, list):
        failures.append(f"{label} must be a list")
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not _valid_opaque_text(item):
            failures.append(f"{label}[{index}] must be a nonempty bounded string")
            continue
        if item in seen:
            failures.append(f"{label}[{index}] duplicates {item!r}")
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def _derive_contract_sets(
    effective_v3: dict[str, object],
    failures: list[str],
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    dict[str, tuple[str, ...]],
    dict[str, dict[str, object]],
    tuple[str, ...],
]:
    """Derive the complete-bundle graph only from the effective V3 record."""

    closure = effective_v3.get("g0ClosureContract")
    if not isinstance(closure, dict):
        failures.append("effective V3 g0ClosureContract must be an object")
        return (), (), {}, {}, ()

    approvals = effective_v3.get("approvals")
    roles: list[str] = []
    if not isinstance(approvals, list):
        failures.append("effective V3 approvals must be a list")
    else:
        seen_roles: set[str] = set()
        for index, raw_approval in enumerate(approvals):
            role = raw_approval.get("role") if isinstance(raw_approval, dict) else None
            if not _valid_opaque_text(role):
                failures.append(f"effective V3 approvals[{index}].role is invalid")
            elif role in seen_roles:
                failures.append(f"effective V3 approvals[{index}].role is duplicated")
            else:
                seen_roles.add(role)
                roles.append(role)
    role_order = tuple(roles)

    release_checklist = effective_v3.get("releaseChecklist")
    g0_exit = (
        release_checklist.get("g0Exit")
        if isinstance(release_checklist, dict)
        else None
    )
    check_ids: list[str] = []
    check_evidence_kinds: list[str] = []
    if not isinstance(g0_exit, list):
        failures.append("effective V3 releaseChecklist.g0Exit must be a list")
    else:
        seen_checks: set[str] = set()
        for index, raw_check in enumerate(g0_exit):
            check_id = raw_check.get("checkId") if isinstance(raw_check, dict) else None
            if not _valid_opaque_text(check_id):
                failures.append(
                    f"effective V3 releaseChecklist.g0Exit[{index}].checkId is invalid"
                )
            elif check_id in seen_checks:
                failures.append(
                    f"effective V3 releaseChecklist.g0Exit[{index}].checkId is duplicated"
                )
            else:
                seen_checks.add(check_id)
                check_ids.append(check_id)
            required_evidence = _unique_string_sequence(
                raw_check.get("requiredEvidence")
                if isinstance(raw_check, dict)
                else None,
                f"effective V3 releaseChecklist.g0Exit[{index}].requiredEvidence",
                failures,
            )
            if not required_evidence:
                failures.append(
                    f"effective V3 releaseChecklist.g0Exit[{index}] requires no evidence"
                )
            for kind in required_evidence:
                if kind not in check_evidence_kinds:
                    check_evidence_kinds.append(kind)
    check_order = tuple(check_ids)

    blockers = closure.get("blockerRequirements")
    if not isinstance(blockers, list):
        failures.append("effective V3 blockerRequirements must be a list")
        blockers = []
    derived = closure.get("derivedEvidenceKinds")
    if not isinstance(derived, dict):
        failures.append("effective V3 derivedEvidenceKinds must be an object")
        derived_order: tuple[str, ...] = ()
    else:
        derived_order = tuple(derived)
        if any(not _valid_opaque_text(kind) for kind in derived_order):
            failures.append("effective V3 derivedEvidenceKinds keys are invalid")
    derived_kinds = set(derived_order)
    if len(derived_order) != 2:
        failures.append("effective V3 must define exactly two derived evidence kinds")

    evidence_kinds: list[str] = []
    role_blockers: dict[str, list[str]] = {role: [] for role in role_order}
    blocker_ids: list[str] = []
    seen_blockers: set[str] = set()
    covered_checks: set[str] = set()
    covered_roles: set[str] = set()
    referenced_derived_kinds: set[str] = set()
    role_blocker_pairs: set[tuple[str, str]] = set()
    blocker_evidence_kinds: list[str] = []
    for index, raw_blocker in enumerate(blockers):
        if not isinstance(raw_blocker, dict):
            failures.append(f"effective V3 blockerRequirements[{index}] must be an object")
            continue
        blocker_id = raw_blocker.get("blockerId")
        if not _valid_opaque_text(blocker_id):
            failures.append(f"effective V3 blockerRequirements[{index}].blockerId is invalid")
            continue
        if blocker_id in seen_blockers:
            failures.append(
                f"effective V3 blockerRequirements[{index}].blockerId is duplicated"
            )
        else:
            seen_blockers.add(blocker_id)
            blocker_ids.append(blocker_id)

        required_checks = _unique_string_sequence(
            raw_blocker.get("requiredCheckIds"),
            f"effective V3 blockerRequirements[{index}].requiredCheckIds",
            failures,
        )
        required_roles = _unique_string_sequence(
            raw_blocker.get("requiredOwnerRoles"),
            f"effective V3 blockerRequirements[{index}].requiredOwnerRoles",
            failures,
        )
        required_evidence = _unique_string_sequence(
            raw_blocker.get("requiredEvidenceKinds"),
            f"effective V3 blockerRequirements[{index}].requiredEvidenceKinds",
            failures,
        )
        unknown_checks = tuple(check for check in required_checks if check not in check_order)
        if unknown_checks:
            failures.append(
                f"effective V3 blockerRequirements[{index}] references unknown G0 checks"
            )
        if tuple(check for check in check_order if check in required_checks) != required_checks:
            failures.append(
                f"effective V3 blockerRequirements[{index}].requiredCheckIds order is not canonical"
            )
        covered_checks.update(required_checks)
        for role in required_roles:
            if role not in role_blockers:
                failures.append(f"effective V3 blocker has unknown role {role!r}")
                continue
            covered_roles.add(role)
            pair = (role, blocker_id)
            if pair in role_blocker_pairs:
                failures.append(f"effective V3 repeats role-blocker pair {pair!r}")
                continue
            role_blocker_pairs.add(pair)
            role_blockers[role].append(blocker_id)
        for kind in required_evidence:
            if kind not in blocker_evidence_kinds:
                blocker_evidence_kinds.append(kind)
            if kind in derived_kinds:
                referenced_derived_kinds.add(kind)
            elif kind not in evidence_kinds:
                evidence_kinds.append(kind)

    if set(check_order) != covered_checks:
        failures.append(
            "effective V3 blocker requiredCheckIds do not cover releaseChecklist.g0Exit exactly"
        )
    if set(role_order) != covered_roles:
        failures.append(
            "effective V3 blocker requiredOwnerRoles do not cover approvals exactly"
        )
    if referenced_derived_kinds != derived_kinds:
        failures.append("effective V3 blockers do not reference both derived evidence kinds")
    if tuple(blocker_evidence_kinds) != tuple(check_evidence_kinds):
        failures.append(
            "effective V3 blocker evidence does not exactly match the ordered "
            "releaseChecklist.g0Exit evidence union"
        )

    executable_checks = _unique_string_sequence(
        closure.get("executableCheckIds"),
        "effective V3 executableCheckIds",
        failures,
    )
    non_executable_checks = _unique_string_sequence(
        closure.get("nonExecutableCheckIds"),
        "effective V3 nonExecutableCheckIds",
        failures,
    )
    executable_set = set(executable_checks)
    non_executable_set = set(non_executable_checks)
    if executable_set & non_executable_set:
        failures.append("effective V3 executable and non-executable checks overlap")
    if executable_set | non_executable_set != set(check_order):
        failures.append(
            "effective V3 executable and non-executable checks do not partition G0 checks"
        )
    if tuple(check for check in check_order if check in executable_set) != executable_checks:
        failures.append("effective V3 executableCheckIds order is not canonical")
    if (
        tuple(check for check in check_order if check in non_executable_set)
        != non_executable_checks
    ):
        failures.append("effective V3 nonExecutableCheckIds order is not canonical")

    evidence_profile = closure.get("evidenceCatalogRecordProfile")
    forbidden_derived = (
        evidence_profile.get("derivedEvidenceKindsForbidden")
        if isinstance(evidence_profile, dict)
        else None
    )
    if not isinstance(forbidden_derived, list) or tuple(forbidden_derived) != derived_order:
        failures.append(
            "effective V3 evidence profile derived-kind exclusion is not exact"
        )

    profiles = closure.get("commandProfiles")
    profile_by_check: dict[str, dict[str, object]] = {}
    if not isinstance(profiles, list):
        failures.append("effective V3 commandProfiles must be a list")
    else:
        for index, raw_profile in enumerate(profiles):
            if not isinstance(raw_profile, dict):
                failures.append(f"effective V3 commandProfiles[{index}] must be an object")
                continue
            body = raw_profile.get("profileBody")
            check_id = body.get("checkId") if isinstance(body, dict) else None
            if not isinstance(check_id, str) or check_id in profile_by_check:
                failures.append(f"effective V3 commandProfiles[{index}] checkId is invalid")
                continue
            profile_by_check[check_id] = raw_profile
    if tuple(profile_by_check) != executable_checks:
        failures.append(
            "effective V3 command profiles do not exactly cover executable checks in order"
        )

    cardinalities = (
        len(blockers),
        len(check_order),
        len(role_order),
        len(role_blocker_pairs),
        len(evidence_kinds),
        len(executable_checks),
    )
    if cardinalities != (10, 9, 14, 15, 15, 2):
        failures.append(
            "effective V3 graph cardinalities are not 10 blockers, 9 checks, "
            "14 roles, 15 role-blocker pairs, 15 non-derived evidence kinds, "
            "and 2 executable checks"
        )
    return (
        role_order,
        tuple(evidence_kinds),
        {role: tuple(values) for role, values in role_blockers.items()},
        profile_by_check,
        executable_checks,
    )


def _derive_owner_catalog_graph(
    effective_v3: dict[str, object],
    failures: list[str],
) -> tuple[
    tuple[str, ...],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
]:
    """Derive the reference-only intake graph from the effective V3 record."""

    _derive_contract_sets(effective_v3, failures)
    closure = effective_v3.get("g0ClosureContract")
    if failures or not isinstance(closure, dict):
        return (), {}, {}
    derived = closure.get("derivedEvidenceKinds")
    blockers = closure.get("blockerRequirements")
    if not isinstance(derived, dict) or not isinstance(blockers, list):
        return (), {}, {}

    canonical_blockers = tuple(blocker for blocker in blockers if isinstance(blocker, dict))
    derived_kinds = set(derived)
    blocker_order = tuple(blocker["blockerId"] for blocker in canonical_blockers)
    blocker_roles = {
        blocker["blockerId"]: tuple(blocker["requiredOwnerRoles"])
        for blocker in canonical_blockers
    }
    blocker_evidence = {
        blocker["blockerId"]: tuple(
            kind
            for kind in blocker["requiredEvidenceKinds"]
            if kind not in derived_kinds
        )
        for blocker in canonical_blockers
    }
    return blocker_order, blocker_roles, blocker_evidence


def _apply_v3_operations(
    parent: dict[str, object],
    operations: object,
    failures: list[str],
) -> dict[str, object]:
    if not isinstance(operations, list):
        failures.append("V3 assurance amendment operations must be a list")
        return copy.deepcopy(parent)
    effective = copy.deepcopy(parent)
    observed: list[tuple[object, object]] = []
    for index, raw_operation in enumerate(operations):
        operation = decision.exact_keys(
            raw_operation,
            {"op", "path", "value"},
            f"V3 assurance amendment operations[{index}]",
            failures,
        )
        operation_kind = operation.get("op")
        path = operation.get("path")
        observed.append((operation_kind, path))
        if operation_kind not in {"add", "replace"}:
            failures.append(f"V3 assurance amendment operations[{index}].op is invalid")
            continue
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or path == "/"
            or "~" in path
        ):
            failures.append(
                f"V3 assurance amendment operations[{index}].path is invalid"
            )
            continue
        parts = path[1:].split("/")
        if any(not part or part.isdigit() for part in parts):
            failures.append(
                f"V3 assurance amendment operations[{index}] cannot address arrays or blank keys"
            )
            continue
        target: object = effective
        valid_target = True
        for part in parts[:-1]:
            if not isinstance(target, dict) or part not in target:
                failures.append(
                    f"V3 assurance amendment operations[{index}] parent path is absent"
                )
                valid_target = False
                break
            target = target[part]
        if not valid_target or not isinstance(target, dict):
            continue
        key = parts[-1]
        if operation_kind == "add" and key in target:
            failures.append(
                f"V3 assurance amendment operations[{index}] add target already exists"
            )
            continue
        if operation_kind == "replace" and key not in target:
            failures.append(
                f"V3 assurance amendment operations[{index}] replace target is absent"
            )
            continue
        target[key] = copy.deepcopy(operation.get("value"))
    _require_equal(
        tuple(observed),
        EXPECTED_V3_OPERATIONS,
        "V3 assurance amendment operation order",
        failures,
    )
    return effective


def _collect_v3_lineage_failures(
    parent_assurance: object,
    parent_checkpoint: object,
    amendment_v2: object,
    amendment_checkpoint_v2: object,
    amendment_v3: object,
    amendment_checkpoint_v3: object,
) -> tuple[str, ...]:
    """Compile the exact six supplied blobs without I/O or authority changes."""

    failures: list[str] = []
    supplied = (
        parent_assurance,
        parent_checkpoint,
        amendment_v2,
        amendment_checkpoint_v2,
        amendment_v3,
        amendment_checkpoint_v3,
    )
    snapshots: list[bytes | None] = []
    for role, value, maximum_bytes in zip(
        LINEAGE_ROLES,
        supplied,
        LINEAGE_MAXIMUM_BYTES,
    ):
        snapshots.append(
            _bounded_snapshot(value, f"G0 V3 lineage {role}", maximum_bytes, failures)
        )
    if any(raw is None for raw in snapshots):
        return tuple(failures)
    raw_blobs = tuple(raw for raw in snapshots if raw is not None)
    for role, raw, expected_sha256 in zip(
        LINEAGE_ROLES,
        raw_blobs,
        LINEAGE_RAW_SHA256,
    ):
        _require_equal(
            _sha256(raw),
            expected_sha256,
            f"G0 V3 lineage {role} raw SHA-256",
            failures,
        )
    if failures:
        return tuple(failures)

    failures.extend(publication.collect_amendment_bundle_failures(*raw_blobs[:4]))
    documents: list[dict[str, object] | None] = []
    for role, raw in zip(LINEAGE_ROLES, raw_blobs):
        documents.append(_parse_object(raw, f"G0 V3 lineage {role}", failures))
    if any(document is None for document in documents):
        return tuple(failures)
    parsed = tuple(document for document in documents if document is not None)
    for role, document, expected_sha256 in zip(
        LINEAGE_ROLES,
        parsed,
        LINEAGE_CANONICAL_SHA256,
    ):
        _require_equal(
            decision.canonical_json_sha256(document),
            expected_sha256,
            f"G0 V3 lineage {role} canonical SHA-256",
            failures,
        )

    assurance, _, v2, _, v3, v3_checkpoint = parsed
    effective_v2 = decision.apply_assurance_amendment_operations(
        assurance,
        v2.get("operations"),
        failures,
    )
    _require_equal(
        decision.canonical_json_sha256(effective_v2),
        EXPECTED_EFFECTIVE_V2_SHA256,
        "effective V2 assurance canonical SHA-256",
        failures,
    )
    closure_v2 = effective_v2.get("g0ClosureContract")
    if not isinstance(closure_v2, dict):
        failures.append("effective V2 g0ClosureContract must be an object")
    else:
        _require_equal(
            decision.canonical_json_sha256(closure_v2),
            EXPECTED_CLOSURE_V2_SHA256,
            "effective V2 closure canonical SHA-256",
            failures,
        )

    effective_v3 = _apply_v3_operations(
        effective_v2,
        v3.get("operations"),
        failures,
    )
    effective_v3_sha256 = decision.canonical_json_sha256(effective_v3)
    _require_equal(
        effective_v3_sha256,
        EXPECTED_EFFECTIVE_V3_SHA256,
        "effective V3 assurance canonical SHA-256",
        failures,
    )
    _require_equal(
        effective_v3.get("assuranceId"),
        "aetherlink_v1_g0_assurance_v3",
        "effective V3 assurance identity",
        failures,
    )
    _require_equal(
        effective_v3.get("schemaVersion"),
        "3.0",
        "effective V3 assurance schemaVersion",
        failures,
    )
    closure_v3 = effective_v3.get("g0ClosureContract")
    if not isinstance(closure_v3, dict):
        failures.append("effective V3 g0ClosureContract must be an object")
    else:
        _require_equal(
            closure_v3.get("schemaVersion"),
            3,
            "effective V3 closure schemaVersion",
            failures,
        )
        _require_equal(
            decision.canonical_json_sha256(closure_v3),
            EXPECTED_CLOSURE_V3_SHA256,
            "effective V3 closure canonical SHA-256",
            failures,
        )
        activation = closure_v3.get("receiptActivationPolicy")
        if not isinstance(activation, dict):
            failures.append("effective V3 receiptActivationPolicy must be an object")
        else:
            for field in (
                "receiptDerivedTrustAnchorsAllowed",
                "bundleSuppliedResultOrActivationFieldsAllowed",
                "partialBundleAcceptanceAllowed",
                "candidateValidationMayAuthorize",
                "receiptActivationAllowed",
                "g1aAuthorityDerivationAllowed",
            ):
                _require_equal(
                    activation.get(field),
                    False,
                    f"effective V3 receiptActivationPolicy.{field}",
                    failures,
                )

    expected_effective = v3.get("effectiveAssurance")
    if not isinstance(expected_effective, dict):
        failures.append("V3 amendment effectiveAssurance must be an object")
    else:
        for field, expected in (
            ("assuranceId", "aetherlink_v1_g0_assurance_v3"),
            ("schemaVersion", "3.0"),
            ("canonicalSha256", effective_v3_sha256),
            ("closureSchemaVersion", 3),
            ("closureCanonicalSha256", EXPECTED_CLOSURE_V3_SHA256),
            ("status", "blocked_before_g1a"),
        ):
            _require_equal(
                expected_effective.get(field),
                expected,
                f"V3 amendment effectiveAssurance.{field}",
                failures,
            )

    effective_readback = v3_checkpoint.get("effectiveAssuranceReadback")
    if not isinstance(effective_readback, dict):
        failures.append("V3 checkpoint effectiveAssuranceReadback must be an object")
    else:
        for field, expected in (
            ("assuranceId", "aetherlink_v1_g0_assurance_v3"),
            ("schemaVersion", "3.0"),
            ("canonicalSha256", effective_v3_sha256),
            ("closureSchemaVersion", 3),
            ("closureCanonicalSha256", EXPECTED_CLOSURE_V3_SHA256),
            ("result", "match"),
        ):
            _require_equal(
                effective_readback.get(field),
                expected,
                f"V3 checkpoint effectiveAssuranceReadback.{field}",
                failures,
            )
    _require_equal(
        v3.get("status"),
        "candidate_not_published_not_authorized",
        "V3 amendment status",
        failures,
    )
    _require_equal(
        v3_checkpoint.get("status"),
        "candidate_observed_not_immutable",
        "V3 checkpoint status",
        failures,
    )
    return tuple(failures)


def _validate_publication_receipt(
    value: object,
    failures: list[str],
    *,
    expected_repository_ref: str | None = None,
    expected_commit_object_id: str | None = None,
    expected_remote_readback_at: str | None = None,
) -> tuple[dict[str, object], datetime | None]:
    """Validate the exact V3 receipt shape without deriving trust or authority."""

    publication_receipt = _exact_ordered_object(
        value,
        PUBLICATION_RECEIPT_FIELDS,
        "publication receipt",
        failures,
    )
    repository_ref = publication_receipt.get("repositoryRef")
    commit_object_id = publication_receipt.get("commitObjectId")
    if not _valid_opaque_text(repository_ref):
        failures.append("publication receipt repositoryRef is invalid")
    if (
        not isinstance(commit_object_id, str)
        or _GIT_OBJECT_ID_PATTERN.fullmatch(commit_object_id) is None
    ):
        failures.append("publication receipt commitObjectId is invalid")
    if expected_repository_ref is not None:
        _require_equal(
            repository_ref,
            expected_repository_ref,
            "publication receipt reviewed repositoryRef",
            failures,
        )
    if expected_commit_object_id is not None:
        _require_equal(
            commit_object_id,
            expected_commit_object_id,
            "publication receipt reviewed commitObjectId",
            failures,
        )

    artifact_bindings = publication_receipt.get("artifactBindings")
    if not isinstance(artifact_bindings, list) or len(artifact_bindings) != 6:
        failures.append(
            "publication receipt artifactBindings must contain exactly six entries"
        )
        artifact_bindings = []
    for index, (role, path, raw_sha256, canonical_sha256) in enumerate(
        zip(
            LINEAGE_ROLES,
            LINEAGE_PATHS,
            LINEAGE_RAW_SHA256,
            LINEAGE_CANONICAL_SHA256,
        )
    ):
        binding = _exact_ordered_object(
            artifact_bindings[index] if index < len(artifact_bindings) else None,
            ARTIFACT_BINDING_FIELDS,
            f"publication artifact binding {index}",
            failures,
        )
        for field, expected in (
            ("role", role),
            ("path", path),
            ("rawSha256", raw_sha256),
            ("canonicalSha256", canonical_sha256),
        ):
            _require_equal(
                binding.get(field),
                expected,
                f"publication artifact binding {index}.{field}",
                failures,
            )
    for field, expected in (
        ("parentEffectiveAssuranceCanonicalSha256", EXPECTED_EFFECTIVE_V2_SHA256),
        ("parentClosureSchemaVersion", 2),
        ("parentClosureCanonicalSha256", EXPECTED_CLOSURE_V2_SHA256),
        ("effectiveAssuranceCanonicalSha256", EXPECTED_EFFECTIVE_V3_SHA256),
        ("effectiveClosureSchemaVersion", 3),
        ("effectiveClosureCanonicalSha256", EXPECTED_CLOSURE_V3_SHA256),
        ("remoteCheckpointPath", V3_CHECKPOINT_PATH),
        ("remoteCheckpointRawSha256", LINEAGE_RAW_SHA256[-1]),
        ("remoteReadbackSha256", LINEAGE_RAW_SHA256[-1]),
    ):
        _require_equal(
            publication_receipt.get(field),
            expected,
            f"publication receipt {field}",
            failures,
        )
    remote_readback_at = _parse_canonical_utc(
        publication_receipt.get("remoteReadbackAt"),
        "publication receipt remoteReadbackAt",
        failures,
    )
    if expected_remote_readback_at is not None:
        _require_equal(
            publication_receipt.get("remoteReadbackAt"),
            expected_remote_readback_at,
            "publication receipt observed remoteReadbackAt",
            failures,
        )
    return publication_receipt, remote_readback_at


def _snapshot_validated_v3_lineage(
    lineage_blobs: object,
    *,
    label: str,
    failures: list[str],
) -> tuple[bytes, ...] | None:
    if not isinstance(lineage_blobs, tuple) or len(lineage_blobs) != len(LINEAGE_PATHS):
        failures.append(f"{label} must be an exact six-blob tuple")
        return None
    snapshots: list[bytes] = []
    for role, value, maximum_bytes in zip(
        LINEAGE_ROLES,
        lineage_blobs,
        LINEAGE_MAXIMUM_BYTES,
    ):
        snapshot = _bounded_snapshot(
            value,
            f"{label} {role}",
            maximum_bytes,
            failures,
        )
        if snapshot is not None:
            snapshots.append(snapshot)
    if failures or len(snapshots) != len(LINEAGE_PATHS):
        return None
    immutable_lineage = tuple(snapshots)
    failures.extend(_collect_v3_lineage_failures(*immutable_lineage))
    return None if failures else immutable_lineage


def _finish_candidate_failures(failures: list[str]) -> tuple[str, ...]:
    if COMPLETE_BUNDLE_DORMANT_MESSAGE not in failures:
        failures.append(COMPLETE_BUNDLE_DORMANT_MESSAGE)
    return tuple(failures)


def _finish_recorded_publication_receipt_failures(
    failures: list[str],
) -> tuple[str, ...]:
    if RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE not in failures:
        failures.append(RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE)
    return tuple(failures)


def _finish_owner_catalog_input_failures(failures: list[str]) -> tuple[str, ...]:
    if OWNER_CATALOG_INPUT_DORMANT_MESSAGE not in failures:
        failures.append(OWNER_CATALOG_INPUT_DORMANT_MESSAGE)
    return tuple(failures)


def _finish_evidence_supporting_artifact_failures(
    failures: list[str],
) -> tuple[str, ...]:
    if EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE not in failures:
        failures.append(EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE)
    return tuple(failures)


def compile_dormant_owner_catalog_input_preview(
    request_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
) -> tuple[bytes, str]:
    """Compile a bounded selector request without authenticating or activating it."""

    failures: list[str] = []
    request_raw = _bounded_snapshot(
        request_bytes,
        "G0 owner/catalog preview request",
        MAX_OWNER_CATALOG_INPUT_BYTES,
        failures,
    )
    request = (
        _parse_object(request_raw, "G0 owner/catalog preview request", failures)
        if request_raw is not None
        else None
    )
    if request is not None:
        _validate_json_resources(
            request,
            failures,
            root_label="G0 owner/catalog preview request",
        )
        request = _exact_ordered_object(
            request,
            OWNER_CATALOG_PREVIEW_REQUEST_FIELDS,
            "owner/catalog preview request",
            failures,
        )
        _require_equal(
            request.get("documentType"),
            "aetherlink.v1-g0-owner-catalog-preview-request",
            "owner/catalog preview request documentType",
            failures,
        )
        _require_equal(
            request.get("schemaVersion"),
            1,
            "owner/catalog preview request schemaVersion",
            failures,
        )
    if failures or request is None:
        raise ValueError("owner/catalog preview request is invalid: " + "; ".join(failures))
    proposal_snapshot = request.get("proposals")
    if not isinstance(proposal_snapshot, list):
        raise ValueError("owner/catalog preview request proposals must be a list")

    immutable_lineage = _snapshot_validated_v3_lineage(
        lineage_blobs,
        label="G0 owner/catalog preview lineage",
        failures=failures,
    )
    if immutable_lineage is None:
        raise ValueError("owner/catalog preview lineage is invalid: " + "; ".join(failures))

    effective_v3 = _materialize_effective_v3(immutable_lineage, failures)
    if effective_v3 is None:
        raise ValueError("owner/catalog preview lineage is invalid: " + "; ".join(failures))
    (
        blocker_order,
        blocker_roles,
        blocker_evidence,
    ) = _derive_owner_catalog_graph(effective_v3, failures)
    if failures:
        raise ValueError("owner/catalog preview graph is invalid: " + "; ".join(failures))

    if len(proposal_snapshot) > len(blocker_order):
        raise ValueError("owner/catalog preview proposals must be a list of at most ten items")

    def exact_object(value: object, fields: tuple[str, ...], label: str) -> dict[str, object]:
        if not isinstance(value, dict) or set(value) != set(fields):
            raise ValueError(f"{label} fields are not exact")
        return value

    def candidate_ref(
        identifier: str,
        value: object,
        prefix: str,
        pattern: re.Pattern[str],
        label: str,
    ) -> tuple[str, int]:
        if type(value) is not int or not 1 <= value <= 999_999_999:
            raise ValueError(f"{label} is invalid")
        reference = f"{prefix}:{identifier.replace('_', '-')}:v{value}"
        version = _canonical_candidate_version(reference, pattern, identifier)
        if version is None or version != value:
            raise ValueError(f"{label} is invalid")
        return reference, version

    def compile_selections(
        value: object,
        fields: tuple[str, ...],
        identifier_field: str,
        allowed: tuple[str, ...],
        prefix: str,
        pattern: re.Pattern[str],
        label: str,
        seen: set[str],
    ) -> list[tuple[str, str, int, dict[str, object]]]:
        if not isinstance(value, list):
            raise ValueError(f"{label} must be a list")
        compiled: list[tuple[str, str, int, dict[str, object]]] = []
        for index, raw_entry in enumerate(value):
            entry_label = f"{label}[{index}]"
            entry = exact_object(raw_entry, fields, entry_label)
            identifier = entry[identifier_field]
            if not isinstance(identifier, str) or identifier not in allowed:
                raise ValueError(f"{entry_label}.{identifier_field} is unknown or forbidden")
            if identifier in seen:
                raise ValueError(f"{entry_label}.{identifier_field} is duplicated")
            seen.add(identifier)
            reference, version = candidate_ref(
                identifier,
                entry["candidateVersion"],
                prefix,
                pattern,
                f"{entry_label}.candidateVersion",
            )
            compiled.append((identifier, reference, version, entry))
        return sorted(compiled, key=lambda entry: allowed.index(entry[0]))

    compiled_responses: list[dict[str, object]] = []
    seen_blockers: set[str] = set()
    seen_evidence_kinds: set[str] = set()
    for proposal_index, raw_proposal in enumerate(proposal_snapshot):
        label = f"owner/catalog preview proposal {proposal_index}"
        proposal = exact_object(raw_proposal, OWNER_CATALOG_PREVIEW_PROPOSAL_FIELDS, label)
        blocker_id = proposal["blockerId"]
        if not isinstance(blocker_id, str) or blocker_id not in blocker_roles:
            raise ValueError(f"{label}.blockerId is unknown")
        if blocker_id in seen_blockers:
            raise ValueError(f"{label}.blockerId is duplicated")
        seen_blockers.add(blocker_id)

        owner_selections = compile_selections(
            proposal["ownerCandidates"],
            OWNER_CATALOG_PREVIEW_OWNER_FIELDS,
            "role",
            blocker_roles[blocker_id],
            "owner-candidate",
            _OWNER_BINDING_REF_CANDIDATE_PATTERN,
            f"{label}.ownerCandidates",
            set(),
        )
        compiled_owners = [
            {"role": role, "ownerBindingRefCandidate": reference}
            for role, reference, _, _ in owner_selections
        ]

        evidence_selections = compile_selections(
            proposal["evidenceCandidates"],
            OWNER_CATALOG_PREVIEW_EVIDENCE_FIELDS,
            "evidenceKind",
            blocker_evidence[blocker_id],
            "evidence-input-candidate",
            _EVIDENCE_INPUT_REF_CANDIDATE_PATTERN,
            f"{label}.evidenceCandidates",
            seen_evidence_kinds,
        )
        compiled_evidence: list[dict[str, object]] = []
        for evidence_kind, evidence_ref, version, evidence in evidence_selections:
            artifact_present = evidence["supportingArtifactPresent"]
            if not isinstance(artifact_present, bool):
                raise ValueError(
                    f"{label} evidence {evidence_kind!r} artifact flag must be boolean"
                )
            slug = evidence_kind.replace("_", "-")
            compiled_evidence.append(
                {
                    "evidenceKind": evidence_kind,
                    "evidenceInputRefCandidate": evidence_ref,
                    "supportingArtifactRefCandidate": (
                        f"docs/evidence/g0-{slug}-candidate-v{version}.json"
                        if artifact_present
                        else None
                    ),
                }
            )

        change_version = proposal["changeRequestCandidateVersion"]
        change_request_ref = None
        if change_version is not None:
            change_request_ref, _ = candidate_ref(
                blocker_id,
                change_version,
                "change-request-candidate",
                _CHANGE_REQUEST_REF_CANDIDATE_PATTERN,
                f"{label}.changeRequestCandidateVersion",
            )
        session_date = proposal["inputSessionDate"]
        session_item = proposal["inputSessionItem"]
        if (
            not isinstance(session_date, str)
            or not isinstance(session_item, int)
            or isinstance(session_item, bool)
        ):
            raise ValueError(f"{label} input session selector types are invalid")
        source_ref = (
            f"user-input:session-{session_date}:item-{session_item}"
        )
        if not _valid_input_source_ref_candidate(source_ref):
            raise ValueError(f"{label} input session must be a real YYYYMMDD date and item 1..999")
        compiled_responses.append(
            {
                "blockerId": blocker_id,
                "requirementDisposition": proposal["requirementDisposition"],
                "ownerCandidates": compiled_owners,
                "evidenceCandidates": compiled_evidence,
                "changeRequestRefCandidate": change_request_ref,
                "inputSourceRefCandidate": source_ref,
            }
        )
    compiled_responses.sort(
        key=lambda response: blocker_order.index(response["blockerId"])
    )

    candidate = {
        "documentType": "aetherlink.v1-g0-owner-catalog-input-candidate",
        "schemaVersion": 1,
        "status": "draft_unverified_non_authorizing",
        "contractBinding": {
            "repositoryRef": EXPECTED_RECORDED_REPOSITORY_REF,
            "publicationCommitObjectId": EXPECTED_RECORDED_COMMIT_OBJECT_ID,
            "publicationCheckpointSha256": LINEAGE_RAW_SHA256[-1],
            "effectiveAssuranceCanonicalSha256": EXPECTED_EFFECTIVE_V3_SHA256,
            "effectiveClosureCanonicalSha256": EXPECTED_CLOSURE_V3_SHA256,
        },
        "responses": compiled_responses,
        "state": {field: False for field in OWNER_CATALOG_STATE_FIELDS},
    }
    canonical_bytes = json.dumps(
        candidate,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    round_trip_failures = _collect_owner_catalog_input_candidate_failures(
        canonical_bytes,
        lineage_blobs=immutable_lineage,
    )
    if round_trip_failures != (OWNER_CATALOG_INPUT_DORMANT_MESSAGE,):
        raise ValueError(
            "compiled owner/catalog preview failed dormant round-trip validation: "
            + "; ".join(round_trip_failures)
        )
    return canonical_bytes, _sha256(canonical_bytes)


def _expected_evidence_selector_snapshot_binding() -> dict[str, object]:
    evidence_kinds = ("reviewed_commit_scope", "published_checkpoint")
    evidence_refs = (
        "evidence-input-candidate:reviewed-commit-scope:v1",
        "evidence-input-candidate:published-checkpoint:v1",
    )
    return {
        "ownerCatalogInputCandidatePath": OWNER_CATALOG_INPUT_PATH,
        "ownerCatalogInputCandidateRawSha256": (
            EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256
        ),
        "responseIndex": 0,
        "blockerId": "roadmap_and_g0_checkpoint_publication",
        "inputSourceRefCandidate": "user-input:session-20260721:item-2",
        "ownerBindingRefCandidate": "owner-candidate:repository-owner:v1",
        "evidenceSelectors": [
            {
                "evidenceKind": evidence_kind,
                "evidenceSelectorIndex": index,
                "candidateVersion": 1,
                "evidenceInputRefCandidate": evidence_ref,
                "supportingArtifactPresent": False,
                "supportingArtifactRefCandidate": None,
                "reservedArtifactPath": artifact_path,
            }
            for index, (evidence_kind, evidence_ref, artifact_path) in enumerate(
                zip(
                    evidence_kinds,
                    evidence_refs,
                    EVIDENCE_SUPPORTING_ARTIFACT_CANDIDATE_PATHS,
                )
            )
        ],
        "artifactInstancePolicy": (
            "forbidden_in_repository_while_selector_supporting_artifact_reference_"
            "is_null_new_profile_required_after_any_selector_change"
        ),
    }


def _collect_evidence_supporting_artifact_profile_failures(
    profile_bytes: object,
    *,
    owner_catalog_input_bytes: object,
) -> tuple[str, ...]:
    """Validate the versioned non-authorizing artifact profile from supplied bytes."""

    failures: list[str] = []
    raw = _bounded_snapshot(
        profile_bytes,
        "G0 evidence supporting artifact profile",
        MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
        failures,
    )
    owner_input_raw = _bounded_snapshot(
        owner_catalog_input_bytes,
        "G0 owner/catalog selector snapshot",
        MAX_OWNER_CATALOG_INPUT_BYTES,
        failures,
    )
    if raw is None or owner_input_raw is None:
        return tuple(failures)
    _require_exact(
        _sha256(raw),
        EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256,
        "evidence supporting artifact profile raw SHA-256",
        failures,
    )
    _require_exact(
        _sha256(owner_input_raw),
        EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        "owner/catalog selector snapshot raw SHA-256",
        failures,
    )
    document = _parse_object(raw, "G0 evidence supporting artifact profile", failures)
    owner_input = _parse_object(
        owner_input_raw,
        "G0 owner/catalog selector snapshot",
        failures,
    )
    if document is None or owner_input is None:
        return tuple(failures)
    _validate_json_resources(
        document,
        failures,
        root_label="G0 evidence supporting artifact profile",
        maximum_depth=MAX_EVIDENCE_SUPPORTING_ARTIFACT_DEPTH,
        maximum_items=MAX_EVIDENCE_SUPPORTING_ARTIFACT_ARRAY_ITEMS,
        maximum_string_bytes=MAX_EVIDENCE_SUPPORTING_ARTIFACT_STRING_BYTES,
    )
    _validate_json_resources(
        owner_input,
        failures,
        root_label="G0 owner/catalog selector snapshot",
    )
    root = _exact_ordered_object(
        document,
        EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_FIELDS,
        "evidence supporting artifact profile",
        failures,
    )
    for field, expected in (
        (
            "documentType",
            "aetherlink.v1-g0-evidence-supporting-artifact-candidate-profile",
        ),
        ("schemaVersion", 1),
        (
            "profileId",
            "aetherlink_v1_g0_evidence_supporting_artifact_candidate_profile_v1",
        ),
        ("status", "draft_unverified_non_authorizing"),
    ):
        _require_exact(root.get(field), expected, f"artifact profile {field}", failures)

    expected_contract = {
        "repositoryRef": EXPECTED_RECORDED_REPOSITORY_REF,
        "blockerId": "roadmap_and_g0_checkpoint_publication",
        "publicationCommitObjectId": EXPECTED_RECORDED_COMMIT_OBJECT_ID,
        "publicationCheckpointPath": V3_CHECKPOINT_PATH,
        "publicationCheckpointRawSha256": LINEAGE_RAW_SHA256[-1],
        "effectiveAssuranceCanonicalSha256": EXPECTED_EFFECTIVE_V3_SHA256,
        "effectiveClosureCanonicalSha256": EXPECTED_CLOSURE_V3_SHA256,
        "requiredEvidenceKinds": ["reviewed_commit_scope", "published_checkpoint"],
    }
    contract = _exact_ordered_object(
        root.get("contractBinding"),
        EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_CONTRACT_FIELDS,
        "artifact profile contractBinding",
        failures,
    )
    _require_exact(
        contract,
        expected_contract,
        "artifact profile contractBinding",
        failures,
    )

    expected_paths = [
        {
            "evidenceKind": kind,
            "candidateVersion": 1,
            "path": path,
        }
        for kind, path in zip(
            expected_contract["requiredEvidenceKinds"],
            EVIDENCE_SUPPORTING_ARTIFACT_CANDIDATE_PATHS,
        )
    ]
    artifact_paths = root.get("artifactPaths")
    if not isinstance(artifact_paths, list):
        failures.append("artifact profile artifactPaths must be a list")
    else:
        for index, entry in enumerate(artifact_paths):
            _exact_ordered_object(
                entry,
                EVIDENCE_SUPPORTING_ARTIFACT_PATH_FIELDS,
                f"artifact profile artifactPaths[{index}]",
                failures,
            )
        _require_exact(
            artifact_paths,
            expected_paths,
            "artifact profile artifactPaths",
            failures,
        )

    expected_selector_snapshot = _expected_evidence_selector_snapshot_binding()
    selector_snapshot = _exact_ordered_object(
        root.get("selectorSnapshotBinding"),
        EVIDENCE_SELECTOR_SNAPSHOT_FIELDS,
        "artifact profile selectorSnapshotBinding",
        failures,
    )
    selector_entries = selector_snapshot.get("evidenceSelectors")
    if not isinstance(selector_entries, list):
        failures.append("artifact profile evidenceSelectors must be a list")
    else:
        for index, entry in enumerate(selector_entries):
            _exact_ordered_object(
                entry,
                EVIDENCE_SELECTOR_SNAPSHOT_ENTRY_FIELDS,
                f"artifact profile evidenceSelectors[{index}]",
                failures,
            )
    _require_exact(
        selector_snapshot,
        expected_selector_snapshot,
        "artifact profile selectorSnapshotBinding",
        failures,
    )

    owner_root = _exact_ordered_object(
        owner_input,
        OWNER_CATALOG_INPUT_FIELDS,
        "owner/catalog selector snapshot",
        failures,
    )
    owner_responses = owner_root.get("responses")
    if not isinstance(owner_responses, list) or len(owner_responses) != 1:
        failures.append("owner/catalog selector snapshot must contain exactly one response")
    else:
        owner_response = _exact_ordered_object(
            owner_responses[0],
            OWNER_CATALOG_RESPONSE_FIELDS,
            "owner/catalog selector snapshot response 0",
            failures,
        )
        expected_selector_response = {
            "blockerId": expected_selector_snapshot["blockerId"],
            "requirementDisposition": "proposed_as_written",
            "ownerCandidates": [
                {
                    "role": "repository_owner",
                    "ownerBindingRefCandidate": expected_selector_snapshot[
                        "ownerBindingRefCandidate"
                    ],
                }
            ],
            "evidenceCandidates": [
                {
                    "evidenceKind": entry["evidenceKind"],
                    "evidenceInputRefCandidate": entry[
                        "evidenceInputRefCandidate"
                    ],
                    "supportingArtifactRefCandidate": entry[
                        "supportingArtifactRefCandidate"
                    ],
                }
                for entry in expected_selector_snapshot["evidenceSelectors"]
            ],
            "changeRequestRefCandidate": None,
            "inputSourceRefCandidate": expected_selector_snapshot[
                "inputSourceRefCandidate"
            ],
        }
        _require_exact(
            owner_response,
            expected_selector_response,
            "owner/catalog selector snapshot response 0",
            failures,
        )
    owner_state = _exact_ordered_object(
        owner_root.get("state"),
        OWNER_CATALOG_STATE_FIELDS,
        "owner/catalog selector snapshot state",
        failures,
    )
    _require_exact(
        owner_state,
        {field: False for field in OWNER_CATALOG_STATE_FIELDS},
        "owner/catalog selector snapshot state",
        failures,
    )

    common = _exact_ordered_object(
        root.get("commonEnvelopeProfile"),
        (
            "exactFields",
            "fixedValues",
            "profileRefExactFields",
            "profileRefPolicy",
            "contractBindingExactFields",
            "contractBindingPolicy",
            "selectorBindingExactFields",
            "selectorBindingPolicy",
            "trustBoundaryExactFields",
            "trustBoundaryFixedValues",
            "stateExactFields",
            "stateFixedValues",
            "canonicalEncoding",
        ),
        "artifact profile commonEnvelopeProfile",
        failures,
    )
    _require_exact(
        common.get("exactFields"),
        list(EVIDENCE_SUPPORTING_ARTIFACT_FIELDS),
        "artifact profile common exactFields",
        failures,
    )
    _require_exact(
        common.get("fixedValues"),
        {
            "documentType": "aetherlink.v1-g0-evidence-supporting-artifact-candidate",
            "schemaVersion": 1,
            "status": "session_observation_unverified_non_authorizing",
        },
        "artifact profile common fixedValues",
        failures,
    )
    for field, expected in (
        ("profileRefExactFields", list(EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_REF_FIELDS)),
        (
            "contractBindingExactFields",
            list(EVIDENCE_SUPPORTING_ARTIFACT_CONTRACT_FIELDS),
        ),
        (
            "selectorBindingExactFields",
            list(EVIDENCE_SUPPORTING_ARTIFACT_SELECTOR_BINDING_FIELDS),
        ),
        ("trustBoundaryExactFields", list(EVIDENCE_SUPPORTING_ARTIFACT_TRUST_FIELDS)),
        ("stateExactFields", list(OWNER_CATALOG_STATE_FIELDS)),
        (
            "stateFixedValues",
            {field: False for field in OWNER_CATALOG_STATE_FIELDS},
        ),
        (
            "canonicalEncoding",
            "utf8_compact_json_exact_field_order_no_bom_no_trailing_newline",
        ),
    ):
        _require_exact(
            common.get(field),
            expected,
            f"artifact profile common {field}",
            failures,
        )
    for field, expected in (
        (
            "profileRefPolicy",
            "exact_profile_path_id_and_validator_pinned_raw_sha256",
        ),
        (
            "contractBindingPolicy",
            "equals_profile_contract_binding_without_requiredEvidenceKinds",
        ),
        (
            "selectorBindingPolicy",
            "exact_per_kind_projection_of_profile_selector_snapshot_with_false_"
            "null_artifact_state",
        ),
    ):
        _require_exact(
            common.get(field),
            expected,
            f"artifact profile common {field}",
            failures,
        )
    _require_exact(
        common.get("trustBoundaryFixedValues"),
        {
            "observationClass": "session_observation_only",
            "independentInputsPresent": [],
            "catalogRecordDerivable": False,
            "authorityDerivable": False,
        },
        "artifact profile common trustBoundaryFixedValues",
        failures,
    )

    reviewed = _exact_ordered_object(
        root.get("reviewedCommitScopePayloadProfile"),
        (
            "evidenceKind",
            "artifactId",
            "exactPayloadFields",
            "fixedSubject",
            "scopeEntryExactFields",
            "expectedScopeEntries",
            "scopeEntriesCanonicalization",
            "expectedScopeEntriesCanonicalSha256",
            "reviewClaimExactFields",
            "reviewClaimDisposition",
            "ownerBindingRefCandidatePattern",
            "inputSourceRefCandidatePattern",
            "claimedReviewRecordedAtPolicy",
            "requiredIndependentInputsAbsent",
        ),
        "artifact profile reviewedCommitScopePayloadProfile",
        failures,
    )
    for field, expected in (
        ("evidenceKind", "reviewed_commit_scope"),
        ("artifactId", "g0-reviewed-commit-scope-candidate-v1"),
        ("exactPayloadFields", list(REVIEWED_COMMIT_SCOPE_PAYLOAD_FIELDS)),
        ("scopeEntryExactFields", list(REVIEWED_COMMIT_SCOPE_ENTRY_FIELDS)),
        ("reviewClaimExactFields", list(REVIEWED_COMMIT_SCOPE_CLAIM_FIELDS)),
        (
            "reviewClaimDisposition",
            "explicit_exact_scope_review_claim_unverified",
        ),
    ):
        _require_exact(
            reviewed.get(field),
            expected,
            f"reviewed-commit profile {field}",
            failures,
        )
    _require_exact(
        reviewed.get("fixedSubject"),
        {
            "baseCommitObjectId": "929fda5f2c01cd7d53325a036071b6a684ecaa1f",
            "baseTreeObjectId": "63bb7d2644321b5bfd006a7ebd82ddee1765e89d",
            "publicationTreeObjectId": "fcdf392d47ab5591e6c1085dcc4e71935f115704",
            "scopeEntryCount": 18,
        },
        "reviewed-commit profile fixedSubject",
        failures,
    )
    scope_entries = reviewed.get("expectedScopeEntries")
    if not isinstance(scope_entries, list) or len(scope_entries) != 18:
        failures.append("reviewed-commit profile must contain exactly eighteen scope entries")
        scope_entries = []
    previous_path = ""
    for index, raw_entry in enumerate(scope_entries):
        entry = _exact_ordered_object(
            raw_entry,
            REVIEWED_COMMIT_SCOPE_ENTRY_FIELDS,
            f"reviewed-commit profile scope entry {index}",
            failures,
        )
        path = entry.get("path")
        if not _safe_artifact_path(path):
            failures.append(f"reviewed-commit profile scope entry {index}.path is invalid")
        elif isinstance(path, str):
            if path <= previous_path:
                failures.append("reviewed-commit profile scope paths are not canonical")
            previous_path = path
        change_type = entry.get("changeType")
        if not isinstance(change_type, str) or change_type not in (
            "added",
            "modified",
        ):
            failures.append(
                f"reviewed-commit profile scope entry {index}.changeType is invalid"
            )
        file_mode = entry.get("fileMode")
        if not isinstance(file_mode, str) or file_mode not in ("100644", "100755"):
            failures.append(
                f"reviewed-commit profile scope entry {index}.fileMode is invalid"
            )
        if (
            not isinstance(entry.get("blobObjectId"), str)
            or re.fullmatch(r"[0-9a-f]{40}", entry["blobObjectId"]) is None
        ):
            failures.append(
                f"reviewed-commit profile scope entry {index}.blobObjectId is invalid"
            )
        byte_length = entry.get("byteLength")
        if (
            type(byte_length) is not int
            or not 0 < byte_length <= MAX_REFERENCED_ARTIFACT_BYTES
        ):
            failures.append(
                f"reviewed-commit profile scope entry {index}.byteLength is invalid"
            )
        if (
            not isinstance(entry.get("rawSha256"), str)
            or _SHA256_PATTERN.fullmatch(entry["rawSha256"]) is None
        ):
            failures.append(
                f"reviewed-commit profile scope entry {index}.rawSha256 is invalid"
            )
    scope_entries_sha256 = _sha256(
        json.dumps(
            scope_entries,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )
    for field, expected in (
        (
            "scopeEntriesCanonicalization",
            "utf8_compact_json_scope_entry_field_order_v1",
        ),
        (
            "expectedScopeEntriesCanonicalSha256",
            "8e04479d4ab4941976061e066ff4a43e25b09111111c8ed96643a5ec3ee53138",
        ),
    ):
        _require_exact(
            reviewed.get(field),
            expected,
            f"reviewed-commit profile {field}",
            failures,
        )
    _require_exact(
        scope_entries_sha256,
        reviewed.get("expectedScopeEntriesCanonicalSha256"),
        "reviewed-commit profile scope entries digest",
        failures,
    )

    published = _exact_ordered_object(
        root.get("publishedCheckpointPayloadProfile"),
        (
            "evidenceKind",
            "artifactId",
            "exactPayloadFields",
            "fixedValues",
            "requiredIndependentInputsAbsent",
        ),
        "artifact profile publishedCheckpointPayloadProfile",
        failures,
    )
    _require_exact(
        published.get("evidenceKind"),
        "published_checkpoint",
        "published-checkpoint profile evidenceKind",
        failures,
    )
    _require_exact(
        published.get("artifactId"),
        "g0-published-checkpoint-candidate-v1",
        "published-checkpoint profile artifactId",
        failures,
    )
    _require_exact(
        published.get("exactPayloadFields"),
        list(PUBLISHED_CHECKPOINT_PAYLOAD_FIELDS),
        "published-checkpoint profile exactPayloadFields",
        failures,
    )
    fixed_published = _exact_ordered_object(
        published.get("fixedValues"),
        PUBLISHED_CHECKPOINT_PAYLOAD_FIELDS,
        "published-checkpoint profile fixedValues",
        failures,
    )
    expected_published = {
        "remoteRef": "refs/heads/main",
        "checkpointPath": V3_CHECKPOINT_PATH,
        "checkpointBlobObjectId": "c91cd84cfe2ba5fa69221b5643b5810a36ec7316",
        "checkpointByteLength": 4692,
        "commitCheckpointRawSha256": LINEAGE_RAW_SHA256[-1],
        "observedRemoteCheckpointRawSha256": LINEAGE_RAW_SHA256[-1],
        "observationMethod": "fresh_https_no_object_alternates_exact_byte_readback",
        "observationStartedAt": "2026-07-20T12:05:21Z",
        "observationCompletedAt": EXPECTED_RECORDED_REMOTE_READBACK_AT,
        "publicationReceiptCandidatePath": RECORDED_PUBLICATION_RECEIPT_PATH,
        "publicationReceiptCandidateRawSha256": (
            EXPECTED_RECORDED_PUBLICATION_RECEIPT_RAW_SHA256
        ),
        "standaloneAcquisitionTranscriptRef": None,
    }
    _require_exact(
        fixed_published,
        expected_published,
        "published-checkpoint profile fixedValues",
        failures,
    )
    started_at = _parse_canonical_utc(
        fixed_published.get("observationStartedAt"),
        "published-checkpoint profile observationStartedAt",
        failures,
    )
    completed_at = _parse_canonical_utc(
        fixed_published.get("observationCompletedAt"),
        "published-checkpoint profile observationCompletedAt",
        failures,
    )
    if started_at is not None and completed_at is not None and started_at >= completed_at:
        failures.append("published-checkpoint profile observation interval is invalid")

    bounds = _exact_ordered_object(
        root.get("resourceBounds"),
        (
            "artifactMaximumBytes",
            "jsonMaximumDepth",
            "arrayMaximumItems",
            "stringMaximumUtf8Bytes",
            "integerMaximumDigits",
            "scopeEntryCount",
            "referencedSourceMaximumBytes",
            "parsePolicy",
            "integerPolicy",
            "pathPolicy",
            "canonicalEncoding",
        ),
        "artifact profile resourceBounds",
        failures,
    )
    for field, expected in (
        ("artifactMaximumBytes", MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES),
        ("jsonMaximumDepth", MAX_EVIDENCE_SUPPORTING_ARTIFACT_DEPTH),
        ("arrayMaximumItems", MAX_EVIDENCE_SUPPORTING_ARTIFACT_ARRAY_ITEMS),
        ("stringMaximumUtf8Bytes", MAX_EVIDENCE_SUPPORTING_ARTIFACT_STRING_BYTES),
        ("integerMaximumDigits", 128),
        ("scopeEntryCount", 18),
        ("referencedSourceMaximumBytes", MAX_REFERENCED_ARTIFACT_BYTES),
    ):
        _require_exact(
            bounds.get(field),
            expected,
            f"artifact profile resourceBounds.{field}",
            failures,
        )

    sensitive = _exact_ordered_object(
        root.get("sensitiveDataPolicy"),
        (
            "allowedVariableInputs",
            "forbiddenMaterial",
            "arbitraryFreeFormFieldsAllowed",
            "standaloneAcquisitionTranscriptPolicy",
        ),
        "artifact profile sensitiveDataPolicy",
        failures,
    )
    _require_exact(
        sensitive.get("arbitraryFreeFormFieldsAllowed"),
        False,
        "artifact profile arbitraryFreeFormFieldsAllowed",
        failures,
    )
    forbidden_material = sensitive.get("forbiddenMaterial")
    required_forbidden_material = {
        "credentials",
        "private_keys",
        "access_tokens",
        "pairing_secrets",
        "private_account_data",
        "personal_contact_data",
    }
    if (
        not isinstance(forbidden_material, list)
        or not all(isinstance(value, str) for value in forbidden_material)
        or not required_forbidden_material.issubset(set(forbidden_material))
    ):
        failures.append("artifact profile sensitive material exclusions are incomplete")

    authority = _exact_ordered_object(
        root.get("authorizationBoundary"),
        (
            "catalogRecordReservedFields",
            "artifactForbiddenFields",
            "catalogRecordPolicy",
            "ownerAuthenticationDerivable",
            "evidenceVerificationDerivable",
            "receiptAcceptanceDerivable",
            "blockerClosureDerivable",
            "receiptActivationDerivable",
            "selectorTransitionDerivable",
            "g0ExitDerivable",
            "g1aAuthorityDerivable",
        ),
        "artifact profile authorizationBoundary",
        failures,
    )
    _require_exact(
        authority.get("catalogRecordReservedFields"),
        list(EVIDENCE_RECORD_FIELDS),
        "artifact profile catalogRecordReservedFields",
        failures,
    )
    for field in (
        "ownerAuthenticationDerivable",
        "evidenceVerificationDerivable",
        "receiptAcceptanceDerivable",
        "blockerClosureDerivable",
        "receiptActivationDerivable",
        "selectorTransitionDerivable",
        "g0ExitDerivable",
        "g1aAuthorityDerivable",
    ):
        _require_exact(
            authority.get(field),
            False,
            f"artifact profile authorizationBoundary.{field}",
            failures,
        )

    supersession = _exact_ordered_object(
        root.get("supersessionPolicy"),
        (
            "mutateInPlaceAllowed",
            "verifiedStateMutationAllowed",
            "candidateToCatalogRecordMutationAllowed",
            "replacementPolicy",
            "nextProfilePathPattern",
        ),
        "artifact profile supersessionPolicy",
        failures,
    )
    for field in (
        "mutateInPlaceAllowed",
        "verifiedStateMutationAllowed",
        "candidateToCatalogRecordMutationAllowed",
    ):
        _require_exact(
            supersession.get(field),
            False,
            f"artifact profile supersessionPolicy.{field}",
            failures,
        )
    return tuple(failures)


def _collect_evidence_supporting_artifact_candidate_failures(
    artifact_bytes: object,
    *,
    profile_bytes: object,
    owner_catalog_input_bytes: object,
) -> tuple[str, ...]:
    """Inspect a future artifact from supplied bytes without verifying or authorizing it."""

    failures: list[str] = []
    raw = _bounded_snapshot(
        artifact_bytes,
        "G0 evidence supporting artifact candidate",
        MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
        failures,
    )
    profile_raw = _bounded_snapshot(
        profile_bytes,
        "G0 evidence supporting artifact profile",
        MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
        failures,
    )
    if raw is None or profile_raw is None:
        return _finish_evidence_supporting_artifact_failures(failures)
    profile_failures = _collect_evidence_supporting_artifact_profile_failures(
        profile_raw,
        owner_catalog_input_bytes=owner_catalog_input_bytes,
    )
    if profile_failures:
        failures.extend(profile_failures)
        return _finish_evidence_supporting_artifact_failures(failures)
    profile = _parse_object(
        profile_raw,
        "G0 evidence supporting artifact profile",
        failures,
    )
    document = _parse_object(
        raw,
        "G0 evidence supporting artifact candidate",
        failures,
    )
    if profile is None or document is None:
        return _finish_evidence_supporting_artifact_failures(failures)
    _validate_json_resources(
        document,
        failures,
        root_label="G0 evidence supporting artifact candidate",
        maximum_depth=MAX_EVIDENCE_SUPPORTING_ARTIFACT_DEPTH,
        maximum_items=MAX_EVIDENCE_SUPPORTING_ARTIFACT_ARRAY_ITEMS,
        maximum_string_bytes=MAX_EVIDENCE_SUPPORTING_ARTIFACT_STRING_BYTES,
    )
    try:
        canonical_raw = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        failures.append(f"artifact candidate cannot be canonicalized: {error}")
        canonical_raw = b""
    if raw != canonical_raw:
        failures.append(
            "artifact candidate bytes are not exact compact UTF-8 JSON without a trailing newline"
        )

    common = profile["commonEnvelopeProfile"]
    root = _exact_ordered_object(
        document,
        EVIDENCE_SUPPORTING_ARTIFACT_FIELDS,
        "evidence supporting artifact candidate",
        failures,
    )
    for field, expected in common["fixedValues"].items():
        _require_exact(
            root.get(field),
            expected,
            f"artifact candidate {field}",
            failures,
        )
    evidence_kind = root.get("evidenceKind")
    if evidence_kind not in profile["contractBinding"]["requiredEvidenceKinds"]:
        failures.append("artifact candidate evidenceKind is unsupported")
        kind_profile: dict[str, object] = {}
    elif evidence_kind == "reviewed_commit_scope":
        kind_profile = profile["reviewedCommitScopePayloadProfile"]
    else:
        kind_profile = profile["publishedCheckpointPayloadProfile"]
    _require_exact(
        root.get("artifactId"),
        kind_profile.get("artifactId"),
        "artifact candidate artifactId",
        failures,
    )

    profile_ref = _exact_ordered_object(
        root.get("profileRef"),
        EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_REF_FIELDS,
        "artifact candidate profileRef",
        failures,
    )
    _require_exact(
        profile_ref,
        {
            "path": EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_PATH,
            "profileId": profile["profileId"],
            "rawSha256": EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256,
        },
        "artifact candidate profileRef",
        failures,
    )
    contract = _exact_ordered_object(
        root.get("contractBinding"),
        EVIDENCE_SUPPORTING_ARTIFACT_CONTRACT_FIELDS,
        "artifact candidate contractBinding",
        failures,
    )
    expected_artifact_contract = {
        field: profile["contractBinding"][field]
        for field in EVIDENCE_SUPPORTING_ARTIFACT_CONTRACT_FIELDS
    }
    _require_exact(
        contract,
        expected_artifact_contract,
        "artifact candidate contractBinding",
        failures,
    )

    selector_snapshot = profile["selectorSnapshotBinding"]
    selector_entry: dict[str, object] = {}
    for entry in selector_snapshot["evidenceSelectors"]:
        if entry["evidenceKind"] == evidence_kind:
            selector_entry = entry
            break
    selector_binding = _exact_ordered_object(
        root.get("selectorBinding"),
        EVIDENCE_SUPPORTING_ARTIFACT_SELECTOR_BINDING_FIELDS,
        "artifact candidate selectorBinding",
        failures,
    )
    expected_selector_binding = {
        "ownerCatalogInputCandidatePath": selector_snapshot[
            "ownerCatalogInputCandidatePath"
        ],
        "ownerCatalogInputCandidateRawSha256": selector_snapshot[
            "ownerCatalogInputCandidateRawSha256"
        ],
        "responseIndex": selector_snapshot["responseIndex"],
        "blockerId": selector_snapshot["blockerId"],
        "inputSourceRefCandidate": selector_snapshot["inputSourceRefCandidate"],
        "ownerBindingRefCandidate": selector_snapshot[
            "ownerBindingRefCandidate"
        ],
        "evidenceSelectorIndex": selector_entry.get("evidenceSelectorIndex"),
        "candidateVersion": selector_entry.get("candidateVersion"),
        "evidenceInputRefCandidate": selector_entry.get(
            "evidenceInputRefCandidate"
        ),
        "supportingArtifactPresent": selector_entry.get(
            "supportingArtifactPresent"
        ),
        "supportingArtifactRefCandidate": selector_entry.get(
            "supportingArtifactRefCandidate"
        ),
        "reservedArtifactPath": selector_entry.get("reservedArtifactPath"),
    }
    _require_exact(
        selector_binding,
        expected_selector_binding,
        "artifact candidate selectorBinding",
        failures,
    )

    payload = root.get("payload")
    if evidence_kind == "reviewed_commit_scope":
        payload_object = _exact_ordered_object(
            payload,
            REVIEWED_COMMIT_SCOPE_PAYLOAD_FIELDS,
            "reviewed-commit artifact payload",
            failures,
        )
        fixed_subject = kind_profile.get("fixedSubject", {})
        for field in (
            "baseCommitObjectId",
            "baseTreeObjectId",
            "publicationTreeObjectId",
            "scopeEntryCount",
        ):
            _require_exact(
                payload_object.get(field),
                fixed_subject.get(field),
                f"reviewed-commit artifact payload.{field}",
                failures,
            )
        expected_entries = kind_profile.get("expectedScopeEntries")
        observed_entries = payload_object.get("scopeEntries")
        _require_exact(
            observed_entries,
            expected_entries,
            "reviewed-commit artifact scopeEntries",
            failures,
        )
        if isinstance(observed_entries, list):
            entries_sha256 = _sha256(
                json.dumps(
                    observed_entries,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
        else:
            entries_sha256 = ""
        _require_exact(
            payload_object.get("scopeEntriesCanonicalSha256"),
            kind_profile.get("expectedScopeEntriesCanonicalSha256"),
            "reviewed-commit artifact scopeEntriesCanonicalSha256",
            failures,
        )
        _require_exact(
            entries_sha256,
            kind_profile.get("expectedScopeEntriesCanonicalSha256"),
            "reviewed-commit artifact calculated scope digest",
            failures,
        )
        claim = _exact_ordered_object(
            payload_object.get("reviewClaim"),
            REVIEWED_COMMIT_SCOPE_CLAIM_FIELDS,
            "reviewed-commit artifact reviewClaim",
            failures,
        )
        _require_exact(
            claim.get("disposition"),
            kind_profile.get("reviewClaimDisposition"),
            "reviewed-commit artifact reviewClaim.disposition",
            failures,
        )
        if (
            _canonical_candidate_version(
                claim.get("ownerBindingRefCandidate"),
                _OWNER_BINDING_REF_CANDIDATE_PATTERN,
                "repository_owner",
            )
            != 1
        ):
            failures.append(
                "reviewed-commit artifact reviewClaim owner candidate is invalid"
            )
        if not _valid_input_source_ref_candidate(claim.get("inputSourceRefCandidate")):
            failures.append(
                "reviewed-commit artifact reviewClaim input source is invalid"
            )
        _require_exact(
            claim.get("ownerBindingRefCandidate"),
            selector_binding.get("ownerBindingRefCandidate"),
            "reviewed-commit artifact reviewClaim owner selector binding",
            failures,
        )
        _require_exact(
            claim.get("inputSourceRefCandidate"),
            selector_binding.get("inputSourceRefCandidate"),
            "reviewed-commit artifact reviewClaim source selector binding",
            failures,
        )
        _parse_canonical_utc(
            claim.get("claimedReviewRecordedAt"),
            "reviewed-commit artifact reviewClaim.claimedReviewRecordedAt",
            failures,
        )
    elif evidence_kind == "published_checkpoint":
        payload_object = _exact_ordered_object(
            payload,
            PUBLISHED_CHECKPOINT_PAYLOAD_FIELDS,
            "published-checkpoint artifact payload",
            failures,
        )
        _require_exact(
            payload_object,
            kind_profile.get("fixedValues"),
            "published-checkpoint artifact payload",
            failures,
        )
        started_at = _parse_canonical_utc(
            payload_object.get("observationStartedAt"),
            "published-checkpoint artifact observationStartedAt",
            failures,
        )
        completed_at = _parse_canonical_utc(
            payload_object.get("observationCompletedAt"),
            "published-checkpoint artifact observationCompletedAt",
            failures,
        )
        if started_at is not None and completed_at is not None and started_at >= completed_at:
            failures.append("published-checkpoint artifact observation interval is invalid")

    trust_boundary = _exact_ordered_object(
        root.get("trustBoundary"),
        EVIDENCE_SUPPORTING_ARTIFACT_TRUST_FIELDS,
        "artifact candidate trustBoundary",
        failures,
    )
    _require_exact(
        trust_boundary,
        {
            "observationClass": "session_observation_only",
            "independentInputsPresent": [],
            "requiredIndependentInputsAbsent": kind_profile.get(
                "requiredIndependentInputsAbsent"
            ),
            "catalogRecordDerivable": False,
            "authorityDerivable": False,
        },
        "artifact candidate trustBoundary",
        failures,
    )
    state = _exact_ordered_object(
        root.get("state"),
        OWNER_CATALOG_STATE_FIELDS,
        "artifact candidate state",
        failures,
    )
    _require_exact(
        state,
        common.get("stateFixedValues"),
        "artifact candidate state",
        failures,
    )

    forbidden_fields = set(profile["authorizationBoundary"]["artifactForbiddenFields"])
    stack: list[object] = [document]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key in forbidden_fields:
                    failures.append(f"artifact candidate forbidden field {key!r} is present")
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return _finish_evidence_supporting_artifact_failures(failures)


def _collect_recorded_publication_receipt_candidate_failures(
    receipt_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
) -> tuple[str, ...]:
    """Validate the recorded observation while always remaining dormant."""

    failures: list[str] = []
    immutable_lineage = _snapshot_validated_v3_lineage(
        lineage_blobs,
        label="recorded publication receipt lineage",
        failures=failures,
    )
    if immutable_lineage is None:
        return _finish_recorded_publication_receipt_failures(failures)

    raw = _bounded_snapshot(
        receipt_bytes,
        "recorded G0 V3 publication receipt candidate",
        MAX_RECORDED_PUBLICATION_RECEIPT_BYTES,
        failures,
    )
    if raw is None:
        return _finish_recorded_publication_receipt_failures(failures)
    _require_equal(
        _sha256(raw),
        EXPECTED_RECORDED_PUBLICATION_RECEIPT_RAW_SHA256,
        "recorded publication receipt raw SHA-256",
        failures,
    )
    receipt = _parse_object(
        raw,
        "recorded G0 V3 publication receipt candidate",
        failures,
    )
    if receipt is None:
        return _finish_recorded_publication_receipt_failures(failures)
    _validate_json_resources(
        receipt,
        failures,
        root_label="recorded G0 V3 publication receipt candidate",
    )
    _validate_publication_receipt(
        receipt,
        failures,
        expected_repository_ref=EXPECTED_RECORDED_REPOSITORY_REF,
        expected_commit_object_id=EXPECTED_RECORDED_COMMIT_OBJECT_ID,
        expected_remote_readback_at=EXPECTED_RECORDED_REMOTE_READBACK_AT,
    )
    return _finish_recorded_publication_receipt_failures(failures)


def _collect_owner_catalog_input_candidate_failures(
    input_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
) -> tuple[str, ...]:
    """Validate sparse external input without accepting or authenticating it."""

    failures: list[str] = []
    immutable_lineage = _snapshot_validated_v3_lineage(
        lineage_blobs,
        label="G0 owner/catalog input lineage",
        failures=failures,
    )
    if immutable_lineage is None:
        return _finish_owner_catalog_input_failures(failures)

    raw = _bounded_snapshot(
        input_bytes,
        "G0 owner/catalog input candidate",
        MAX_OWNER_CATALOG_INPUT_BYTES,
        failures,
    )
    if raw is None:
        return _finish_owner_catalog_input_failures(failures)
    document = _parse_object(raw, "G0 owner/catalog input candidate", failures)
    if document is None:
        return _finish_owner_catalog_input_failures(failures)
    _validate_json_resources(
        document,
        failures,
        root_label="G0 owner/catalog input candidate",
    )
    root = _exact_ordered_object(
        document,
        OWNER_CATALOG_INPUT_FIELDS,
        "owner/catalog input candidate",
        failures,
    )
    for field, expected in (
        ("documentType", "aetherlink.v1-g0-owner-catalog-input-candidate"),
        ("schemaVersion", 1),
        ("status", "draft_unverified_non_authorizing"),
    ):
        _require_equal(
            root.get(field),
            expected,
            f"owner/catalog input candidate {field}",
            failures,
        )

    contract_binding = _exact_ordered_object(
        root.get("contractBinding"),
        OWNER_CATALOG_CONTRACT_BINDING_FIELDS,
        "owner/catalog input contractBinding",
        failures,
    )
    for field, expected in (
        ("repositoryRef", EXPECTED_RECORDED_REPOSITORY_REF),
        ("publicationCommitObjectId", EXPECTED_RECORDED_COMMIT_OBJECT_ID),
        ("publicationCheckpointSha256", LINEAGE_RAW_SHA256[-1]),
        ("effectiveAssuranceCanonicalSha256", EXPECTED_EFFECTIVE_V3_SHA256),
        ("effectiveClosureCanonicalSha256", EXPECTED_CLOSURE_V3_SHA256),
    ):
        _require_equal(
            contract_binding.get(field),
            expected,
            f"owner/catalog input contractBinding.{field}",
            failures,
        )

    effective_v3 = _materialize_effective_v3(immutable_lineage, failures)
    if effective_v3 is None:
        return _finish_owner_catalog_input_failures(failures)
    (
        blocker_order,
        blocker_roles,
        blocker_evidence,
    ) = _derive_owner_catalog_graph(effective_v3, failures)

    responses = root.get("responses")
    if not isinstance(responses, list) or len(responses) > len(blocker_order):
        failures.append("owner/catalog responses must be a sparse list of at most ten items")
        responses = []
    seen_blockers: set[str] = set()
    previous_blocker_index = -1
    owner_version_by_role: dict[str, int] = {}
    seen_evidence_kinds: set[str] = set()
    for response_index, raw_response in enumerate(responses):
        response = _exact_ordered_object(
            raw_response,
            OWNER_CATALOG_RESPONSE_FIELDS,
            f"owner/catalog response {response_index}",
            failures,
        )
        blocker_id = response.get("blockerId")
        if not isinstance(blocker_id, str) or blocker_id not in blocker_roles:
            failures.append(f"owner/catalog response {response_index}.blockerId is invalid")
            required_roles = ()
            allowed_evidence = ()
        else:
            blocker_position = blocker_order.index(blocker_id)
            if blocker_id in seen_blockers:
                failures.append(
                    f"owner/catalog response {response_index}.blockerId is duplicated"
                )
            elif blocker_position <= previous_blocker_index:
                failures.append("owner/catalog responses are not in canonical blocker order")
            else:
                seen_blockers.add(blocker_id)
                previous_blocker_index = blocker_position
            required_roles = blocker_roles[blocker_id]
            allowed_evidence = blocker_evidence[blocker_id]

        disposition = response.get("requirementDisposition")
        if disposition not in OWNER_CATALOG_REQUIREMENT_DISPOSITIONS:
            failures.append(
                f"owner/catalog response {response_index}.requirementDisposition is invalid"
            )

        owner_candidates = response.get("ownerCandidates")
        if not isinstance(owner_candidates, list) or len(owner_candidates) > len(
            required_roles
        ):
            failures.append(
                f"owner/catalog response {response_index}.ownerCandidates is invalid"
            )
            owner_candidates = []
        observed_roles: list[str] = []
        for owner_index, raw_owner in enumerate(owner_candidates):
            owner = _exact_ordered_object(
                raw_owner,
                OWNER_CANDIDATE_FIELDS,
                f"owner/catalog response {response_index} owner {owner_index}",
                failures,
            )
            role = owner.get("role")
            owner_ref = owner.get("ownerBindingRefCandidate")
            if not isinstance(role, str) or role not in required_roles:
                failures.append(
                    f"owner/catalog response {response_index} owner {owner_index}.role is invalid"
                )
            else:
                observed_roles.append(role)
            owner_version = _canonical_candidate_version(
                owner_ref,
                _OWNER_BINDING_REF_CANDIDATE_PATTERN,
                role,
            )
            if owner_version is None:
                failures.append(
                    f"owner/catalog response {response_index} owner {owner_index} "
                    "binding reference is invalid"
                )
                continue
            if isinstance(role, str):
                existing_version = owner_version_by_role.get(role)
                if existing_version is not None and existing_version != owner_version:
                    failures.append(
                        f"owner binding candidate for role {role!r} is inconsistent"
                    )
                owner_version_by_role[role] = owner_version
        if tuple(observed_roles) != tuple(
            role for role in required_roles if role in observed_roles
        ) or len(observed_roles) != len(set(observed_roles)):
            failures.append(
                f"owner/catalog response {response_index} owner role order is not canonical"
            )

        evidence_candidates = response.get("evidenceCandidates")
        if not isinstance(evidence_candidates, list) or len(evidence_candidates) > len(
            allowed_evidence
        ):
            failures.append(
                f"owner/catalog response {response_index}.evidenceCandidates is invalid"
            )
            evidence_candidates = []
        observed_evidence: list[str] = []
        for evidence_index, raw_evidence in enumerate(evidence_candidates):
            evidence = _exact_ordered_object(
                raw_evidence,
                EVIDENCE_CANDIDATE_FIELDS,
                f"owner/catalog response {response_index} evidence {evidence_index}",
                failures,
            )
            evidence_kind = evidence.get("evidenceKind")
            if (
                not isinstance(evidence_kind, str)
                or evidence_kind not in allowed_evidence
            ):
                failures.append(
                    f"owner/catalog response {response_index} evidence "
                    f"{evidence_index}.kind is invalid"
                )
            else:
                observed_evidence.append(evidence_kind)
                if evidence_kind in seen_evidence_kinds:
                    failures.append(
                        f"owner catalog evidence kind {evidence_kind!r} is duplicated"
                    )
                else:
                    seen_evidence_kinds.add(evidence_kind)
            evidence_input_ref = evidence.get("evidenceInputRefCandidate")
            evidence_candidate_version = _canonical_candidate_version(
                evidence_input_ref,
                _EVIDENCE_INPUT_REF_CANDIDATE_PATTERN,
                evidence_kind,
            )
            if evidence_candidate_version is None:
                failures.append(
                    f"owner/catalog response {response_index} evidence {evidence_index} "
                    "input reference is invalid"
                )
            if not _safe_supporting_artifact_candidate(
                evidence.get("supportingArtifactRefCandidate"),
                evidence_kind,
                evidence_candidate_version,
            ):
                failures.append(
                    f"owner/catalog response {response_index} evidence {evidence_index} "
                    "supporting artifact candidate is invalid"
                )
        if tuple(observed_evidence) != tuple(
            kind for kind in allowed_evidence if kind in observed_evidence
        ) or len(observed_evidence) != len(set(observed_evidence)):
            failures.append(
                f"owner/catalog response {response_index} evidence order is not canonical"
            )

        change_request_ref = response.get("changeRequestRefCandidate")
        if disposition == "proposed_as_written":
            if change_request_ref is not None:
                failures.append(
                    f"owner/catalog response {response_index} as-written proposal "
                    "must not include a change request"
                )
            if not owner_candidates and not evidence_candidates:
                failures.append(
                    f"owner/catalog response {response_index} proposal contains no input"
                )
        elif disposition == "proposed_with_changes":
            if _canonical_candidate_version(
                change_request_ref,
                _CHANGE_REQUEST_REF_CANDIDATE_PATTERN,
                blocker_id,
            ) is None:
                failures.append(
                    f"owner/catalog response {response_index} change request "
                    "reference is invalid"
                )
        elif disposition == "not_available":
            if owner_candidates or evidence_candidates or change_request_ref is not None:
                failures.append(
                    f"owner/catalog response {response_index} not-available response "
                    "must not include owner, evidence, or change candidates"
                )
        input_source_ref = response.get("inputSourceRefCandidate")
        if not _valid_input_source_ref_candidate(input_source_ref):
            failures.append(
                f"owner/catalog response {response_index}.inputSourceRefCandidate is invalid"
            )

    state = _exact_ordered_object(
        root.get("state"),
        OWNER_CATALOG_STATE_FIELDS,
        "owner/catalog input state",
        failures,
    )
    for field in OWNER_CATALOG_STATE_FIELDS:
        _require_equal(
            state.get(field),
            False,
            f"owner/catalog input state.{field}",
            failures,
        )
    return _finish_owner_catalog_input_failures(failures)


def _collect_complete_bundle_candidate_failures(
    bundle_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
) -> tuple[str, ...]:
    """Compile caller-supplied candidate bytes while always remaining dormant."""

    failures: list[str] = []
    immutable_lineage = _snapshot_validated_v3_lineage(
        lineage_blobs,
        label="G0 V3 bundle lineage",
        failures=failures,
    )
    if immutable_lineage is None:
        return _finish_candidate_failures(failures)

    raw = _bounded_snapshot(
        bundle_bytes,
        "G0 V3 complete receipt bundle candidate",
        MAX_COMPLETE_BUNDLE_BYTES,
        failures,
    )
    if raw is None:
        return _finish_candidate_failures(failures)
    bundle = _parse_object(raw, "G0 V3 complete receipt bundle candidate", failures)
    if bundle is None:
        return _finish_candidate_failures(failures)
    _validate_json_resources(
        bundle,
        failures,
        root_label="complete receipt bundle",
    )
    root = _exact_ordered_object(
        bundle,
        COMPLETE_BUNDLE_FIELDS,
        "complete receipt bundle",
        failures,
    )
    _require_equal(
        root.get("documentType"),
        "aetherlink.v1-g0-complete-receipt-bundle-candidate",
        "complete receipt bundle documentType",
        failures,
    )
    _require_equal(
        root.get("schemaVersion"),
        1,
        "complete receipt bundle schemaVersion",
        failures,
    )
    _require_equal(
        root.get("effectiveAssuranceCanonicalSha256"),
        EXPECTED_EFFECTIVE_V3_SHA256,
        "complete receipt bundle effective assurance binding",
        failures,
    )

    effective_v3 = _materialize_effective_v3(immutable_lineage, failures)
    if effective_v3 is None:
        return _finish_candidate_failures(failures)
    closure = effective_v3.get("g0ClosureContract")
    if not isinstance(closure, dict):
        failures.append("effective V3 g0ClosureContract must be an object")
        return _finish_candidate_failures(failures)
    (
        roles,
        evidence_kinds,
        role_blockers,
        profile_by_check,
        executable_checks,
    ) = _derive_contract_sets(effective_v3, failures)

    publication_receipt, remote_readback_at = _validate_publication_receipt(
        root.get("publicationReceipt"),
        failures,
    )
    commit_object_id = publication_receipt.get("commitObjectId")

    owner_bindings = root.get("ownerBindings")
    if not isinstance(owner_bindings, list) or len(owner_bindings) != len(roles):
        failures.append("ownerBindings must contain exactly fourteen records")
        owner_bindings = []
    owner_by_role: dict[str, tuple[dict[str, object], datetime | None, datetime | None]] = {}
    seen_owner_refs: set[str] = set()
    seen_owner_identities: set[str] = set()
    for index, role in enumerate(roles):
        owner = _exact_ordered_object(
            owner_bindings[index] if index < len(owner_bindings) else None,
            OWNER_BINDING_FIELDS,
            f"owner binding {index}",
            failures,
        )
        _require_equal(owner.get("role"), role, f"owner binding {index}.role", failures)
        owner_ref = owner.get("ownerBindingRef")
        owner_identity = owner.get("ownerIdentityRef")
        if not isinstance(owner_ref, str) or _OWNER_BINDING_REF_PATTERN.fullmatch(owner_ref) is None:
            failures.append(f"owner binding {index}.ownerBindingRef is invalid")
        elif owner_ref in seen_owner_refs:
            failures.append(f"owner binding {index}.ownerBindingRef is duplicated")
        else:
            seen_owner_refs.add(owner_ref)
        if not _valid_opaque_text(owner_identity):
            failures.append(f"owner binding {index}.ownerIdentityRef is invalid")
        elif owner_identity in seen_owner_identities:
            failures.append(f"owner binding {index}.ownerIdentityRef is duplicated")
        else:
            seen_owner_identities.add(owner_identity)
        for field in (
            "credentialRef",
            "identityRegistryRef",
            "identityRegistryRevision",
            "revocationRef",
            "provenanceRef",
        ):
            if not _valid_opaque_text(owner.get(field)):
                failures.append(f"owner binding {index}.{field} is invalid")
        valid_from = _parse_canonical_utc(
            owner.get("validFrom"), f"owner binding {index}.validFrom", failures
        )
        valid_until = _parse_canonical_utc(
            owner.get("validUntil"), f"owner binding {index}.validUntil", failures
        )
        if valid_from is not None and valid_until is not None and valid_from >= valid_until:
            failures.append(f"owner binding {index} validity interval is empty or reversed")
        owner_by_role[role] = (owner, valid_from, valid_until)

    evidence_catalog = root.get("evidenceCatalog")
    if not isinstance(evidence_catalog, list) or len(evidence_catalog) != len(evidence_kinds):
        failures.append("evidenceCatalog must contain exactly fifteen records")
        evidence_catalog = []
    evidence_by_id: dict[str, tuple[dict[str, object], datetime | None]] = {}
    evidence_id_by_kind: dict[str, str] = {}
    total_artifact_bytes = 0
    for index, kind in enumerate(evidence_kinds):
        evidence = _exact_ordered_object(
            evidence_catalog[index] if index < len(evidence_catalog) else None,
            EVIDENCE_RECORD_FIELDS,
            f"evidence record {index}",
            failures,
        )
        _require_equal(
            evidence.get("evidenceKind"),
            kind,
            f"evidence record {index}.evidenceKind",
            failures,
        )
        evidence_id = evidence.get("evidenceId")
        if not isinstance(evidence_id, str) or _EVIDENCE_ID_PATTERN.fullmatch(evidence_id) is None:
            failures.append(f"evidence record {index}.evidenceId is invalid")
        elif evidence_id in evidence_by_id:
            failures.append(f"evidence record {index}.evidenceId is duplicated")
        if not _valid_opaque_text(evidence.get("evidenceClass")):
            failures.append(f"evidence record {index}.evidenceClass is invalid")
        _require_equal(
            evidence.get("subjectImplementationRevision"),
            commit_object_id,
            f"evidence record {index}.subjectImplementationRevision",
            failures,
        )
        _require_equal(
            evidence.get("subjectCheckpointSha256"),
            LINEAGE_RAW_SHA256[-1],
            f"evidence record {index}.subjectCheckpointSha256",
            failures,
        )
        if not _safe_artifact_path(evidence.get("artifactPath")):
            failures.append(f"evidence record {index}.artifactPath is invalid")
        artifact_length = evidence.get("artifactByteLength")
        if (
            not isinstance(artifact_length, int)
            or isinstance(artifact_length, bool)
            or not 0 < artifact_length <= MAX_REFERENCED_ARTIFACT_BYTES
        ):
            failures.append(f"evidence record {index}.artifactByteLength is invalid")
        else:
            total_artifact_bytes += artifact_length
        artifact_sha256 = evidence.get("artifactSha256")
        if not isinstance(artifact_sha256, str) or _SHA256_PATTERN.fullmatch(artifact_sha256) is None:
            failures.append(f"evidence record {index}.artifactSha256 is invalid")
        for field in (
            "verificationMethod",
            "verifierIdentityRef",
            "provenanceRef",
        ):
            if not _valid_opaque_text(evidence.get(field)):
                failures.append(f"evidence record {index}.{field} is invalid")
        verified_at = _parse_canonical_utc(
            evidence.get("verifiedAt"), f"evidence record {index}.verifiedAt", failures
        )
        if (
            remote_readback_at is not None
            and verified_at is not None
            and verified_at < remote_readback_at
        ):
            failures.append(f"evidence record {index} predates publication readback")
        if isinstance(evidence_id, str):
            evidence_by_id[evidence_id] = (evidence, verified_at)
            evidence_id_by_kind[kind] = evidence_id
    if total_artifact_bytes > 62_914_560:
        failures.append("evidence artifact byte total exceeds the V3 contract bound")

    authority_bindings = root.get("authorityBindings")
    if not isinstance(authority_bindings, list) or len(authority_bindings) != 2:
        failures.append("authorityBindings must contain exactly two records")
        authority_bindings = []
    authority_by_check: dict[str, tuple[dict[str, object], datetime | None, datetime | None]] = {}
    seen_authorization_refs: set[str] = set()
    profile_expectations: dict[str, dict[str, object]] = {}
    for index, check_id in enumerate(executable_checks):
        authority = _exact_ordered_object(
            authority_bindings[index] if index < len(authority_bindings) else None,
            AUTHORITY_BINDING_FIELDS,
            f"authority binding {index}",
            failures,
        )
        profile = profile_by_check.get(check_id, {})
        profile_body = profile.get("profileBody") if isinstance(profile, dict) else None
        if not isinstance(profile_body, dict):
            failures.append(f"command profile for {check_id} is absent")
            profile_body = {}
        ordered_steps = profile_body.get("orderedSteps")
        allowed_side_effects = profile_body.get("allowedSideEffects")
        expected_profile_id = profile.get("commandProfileId") if isinstance(profile, dict) else None
        expected_profile_sha256 = profile.get("canonicalProfileSha256") if isinstance(profile, dict) else None
        expected_command_sha256 = decision.canonical_json_sha256(ordered_steps)
        expected_side_effects_sha256 = decision.canonical_json_sha256(allowed_side_effects)
        required_kinds = profile_body.get("requiredEvidenceKinds")
        profile_expectations[check_id] = {
            "profileId": expected_profile_id,
            "profileSha256": expected_profile_sha256,
            "commandSha256": expected_command_sha256,
            "sideEffectsSha256": expected_side_effects_sha256,
            "orderedSteps": ordered_steps,
            "requiredEvidenceKinds": required_kinds,
        }
        for field, expected in (
            ("checkId", check_id),
            ("sourcePublicationCommit", commit_object_id),
            ("commandProfileId", expected_profile_id),
            ("commandProfileSha256", expected_profile_sha256),
            ("commandArgvSha256", expected_command_sha256),
            ("allowedSideEffectsSha256", expected_side_effects_sha256),
        ):
            _require_equal(
                authority.get(field),
                expected,
                f"authority binding {index}.{field}",
                failures,
            )
        authorization_ref = authority.get("authorizationRef")
        if (
            not isinstance(authorization_ref, str)
            or _AUTHORIZATION_REF_PATTERN.fullmatch(authorization_ref) is None
        ):
            failures.append(f"authority binding {index}.authorizationRef is invalid")
        elif authorization_ref in seen_authorization_refs:
            failures.append(f"authority binding {index}.authorizationRef is duplicated")
        else:
            seen_authorization_refs.add(authorization_ref)
        for field in ("authorityIssuerRef", "revocationRef", "provenanceRef"):
            if not _valid_opaque_text(authority.get(field)):
                failures.append(f"authority binding {index}.{field} is invalid")
        for field in ("workingDirectorySha256", "environmentSha256"):
            value = authority.get(field)
            if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
                failures.append(f"authority binding {index}.{field} is invalid")
        not_before = _parse_canonical_utc(
            authority.get("notBefore"), f"authority binding {index}.notBefore", failures
        )
        not_after = _parse_canonical_utc(
            authority.get("notAfter"), f"authority binding {index}.notAfter", failures
        )
        if not_before is not None and not_after is not None and not_before >= not_after:
            failures.append(f"authority binding {index} validity interval is empty or reversed")
        if (
            remote_readback_at is not None
            and not_before is not None
            and not_before < remote_readback_at
        ):
            failures.append(f"authority binding {index} predates publication readback")
        authority_by_check[check_id] = (authority, not_before, not_after)

    runner_attestations = root.get("runnerAttestations")
    if not isinstance(runner_attestations, list) or len(runner_attestations) != 2:
        failures.append("runnerAttestations must contain exactly two records")
        runner_attestations = []
    runner_by_check: dict[str, tuple[dict[str, object], datetime | None, datetime | None]] = {}
    seen_runner_refs: set[str] = set()
    for index, check_id in enumerate(executable_checks):
        runner = _exact_ordered_object(
            runner_attestations[index] if index < len(runner_attestations) else None,
            RUNNER_ATTESTATION_FIELDS,
            f"runner attestation {index}",
            failures,
        )
        authority, not_before, not_after = authority_by_check.get(check_id, ({}, None, None))
        expectation = profile_expectations.get(check_id, {})
        for field, expected in (
            ("authorizationRef", authority.get("authorizationRef")),
            ("checkId", check_id),
            ("sourcePublicationCommit", commit_object_id),
            ("commandProfileId", expectation.get("profileId")),
            ("commandProfileSha256", expectation.get("profileSha256")),
            ("commandArgvSha256", expectation.get("commandSha256")),
            ("workingDirectorySha256", authority.get("workingDirectorySha256")),
            ("environmentSha256", authority.get("environmentSha256")),
            ("allowedSideEffectsSha256", expectation.get("sideEffectsSha256")),
        ):
            _require_equal(
                runner.get(field),
                expected,
                f"runner attestation {index}.{field}",
                failures,
            )
        runner_ref = runner.get("runnerAttestationRef")
        if (
            not isinstance(runner_ref, str)
            or _RUNNER_ATTESTATION_REF_PATTERN.fullmatch(runner_ref) is None
        ):
            failures.append(f"runner attestation {index}.runnerAttestationRef is invalid")
        elif runner_ref in seen_runner_refs:
            failures.append(f"runner attestation {index}.runnerAttestationRef is duplicated")
        else:
            seen_runner_refs.add(runner_ref)
        for field in ("runnerIdentityRef", "provenanceRef"):
            if not _valid_opaque_text(runner.get(field)):
                failures.append(f"runner attestation {index}.{field} is invalid")
        if runner.get("runnerIdentityRef") == authority.get("authorityIssuerRef"):
            failures.append(f"runner attestation {index} cannot share the authority issuer identity")
        for field in (
            "toolchainManifestSha256",
            "dependencyManifestSha256",
            "observationManifestSha256",
            "sanitizedLogSha256",
        ):
            value = runner.get(field)
            if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
                failures.append(f"runner attestation {index}.{field} is invalid")
        started_at = _parse_canonical_utc(
            runner.get("startedAt"), f"runner attestation {index}.startedAt", failures
        )
        completed_at = _parse_canonical_utc(
            runner.get("completedAt"), f"runner attestation {index}.completedAt", failures
        )
        if started_at is not None and completed_at is not None and started_at > completed_at:
            failures.append(f"runner attestation {index} interval is reversed")
        if not_before is not None and started_at is not None and started_at < not_before:
            failures.append(f"runner attestation {index} starts before authority validity")
        if not_after is not None and completed_at is not None and completed_at > not_after:
            failures.append(f"runner attestation {index} ends after authority validity")
        if not _exact_zero(runner.get("exitCode")):
            failures.append(f"runner attestation {index}.exitCode must be exact integer zero")

        expected_steps = expectation.get("orderedSteps")
        step_results = runner.get("orderedStepResults")
        if not isinstance(expected_steps, list):
            expected_steps = []
        if not isinstance(step_results, list) or len(step_results) != len(expected_steps):
            failures.append(f"runner attestation {index} step result count is not exact")
            step_results = []
        previous_step_completed: datetime | None = None
        for step_index, expected_step in enumerate(expected_steps):
            step = _exact_ordered_object(
                step_results[step_index] if step_index < len(step_results) else None,
                STEP_RESULT_FIELDS,
                f"runner attestation {index} step {step_index}",
                failures,
            )
            expected_step_id = expected_step.get("stepId") if isinstance(expected_step, dict) else None
            expected_argv = expected_step.get("argv") if isinstance(expected_step, dict) else None
            _require_equal(
                step.get("stepId"),
                expected_step_id,
                f"runner attestation {index} step {step_index}.stepId",
                failures,
            )
            _require_equal(
                step.get("argvSha256"),
                decision.canonical_json_sha256(expected_argv),
                f"runner attestation {index} step {step_index}.argvSha256",
                failures,
            )
            step_started = _parse_canonical_utc(
                step.get("startedAt"),
                f"runner attestation {index} step {step_index}.startedAt",
                failures,
            )
            step_completed = _parse_canonical_utc(
                step.get("completedAt"),
                f"runner attestation {index} step {step_index}.completedAt",
                failures,
            )
            if step_started is not None and step_completed is not None and step_started > step_completed:
                failures.append(f"runner attestation {index} step {step_index} interval is reversed")
            if previous_step_completed is not None and step_started is not None and step_started < previous_step_completed:
                failures.append(f"runner attestation {index} steps overlap or reorder")
            if started_at is not None and step_started is not None and step_started < started_at:
                failures.append(f"runner attestation {index} step starts outside runner interval")
            if completed_at is not None and step_completed is not None and step_completed > completed_at:
                failures.append(f"runner attestation {index} step ends outside runner interval")
            if not _exact_zero(step.get("exitCode")):
                failures.append(f"runner attestation {index} step {step_index}.exitCode must be zero")
            previous_step_completed = step_completed

        required_kinds = expectation.get("requiredEvidenceKinds")
        if not isinstance(required_kinds, list):
            required_kinds = []
        expected_evidence_refs = [
            evidence_id_by_kind[kind]
            for kind in required_kinds
            if kind in evidence_id_by_kind
        ]
        _require_equal(
            runner.get("evidenceRefs"),
            expected_evidence_refs,
            f"runner attestation {index}.evidenceRefs",
            failures,
        )
        runner_by_check[check_id] = (runner, started_at, completed_at)

    gate_receipts = root.get("gateReceipts")
    if not isinstance(gate_receipts, list) or len(gate_receipts) != 2:
        failures.append("gateReceipts must contain exactly two records")
        gate_receipts = []
    referenced_evidence_ids: set[str] = set()
    for index, check_id in enumerate(executable_checks):
        gate = _exact_ordered_object(
            gate_receipts[index] if index < len(gate_receipts) else None,
            GATE_RECEIPT_FIELDS,
            f"gate receipt {index}",
            failures,
        )
        authority, _, _ = authority_by_check.get(check_id, ({}, None, None))
        runner, started_at, completed_at = runner_by_check.get(check_id, ({}, None, None))
        expectation = profile_expectations.get(check_id, {})
        for field, expected in (
            ("checkId", check_id),
            ("authorizationRef", authority.get("authorizationRef")),
            ("runnerAttestationRef", runner.get("runnerAttestationRef")),
            ("sourcePublicationCommit", commit_object_id),
            ("commandProfileId", expectation.get("profileId")),
            ("commandProfileSha256", expectation.get("profileSha256")),
            ("startedAt", runner.get("startedAt")),
            ("completedAt", runner.get("completedAt")),
            ("exitCode", 0),
            ("sanitizedLogSha256", runner.get("sanitizedLogSha256")),
            ("evidenceRefs", runner.get("evidenceRefs")),
        ):
            _require_equal(gate.get(field), expected, f"gate receipt {index}.{field}", failures)
        if not _exact_zero(gate.get("exitCode")):
            failures.append(f"gate receipt {index}.exitCode must be exact integer zero")
        gate_refs = gate.get("evidenceRefs")
        if isinstance(gate_refs, list):
            for evidence_ref in gate_refs:
                if isinstance(evidence_ref, str):
                    referenced_evidence_ids.add(evidence_ref)
                    evidence_entry = evidence_by_id.get(evidence_ref)
                    if (
                        evidence_entry is not None
                        and completed_at is not None
                        and evidence_entry[1] is not None
                        and evidence_entry[1] < completed_at
                    ):
                        failures.append(
                            f"gate receipt {index} evidence {evidence_ref!r} predates gate completion"
                        )
        if (
            remote_readback_at is not None
            and started_at is not None
            and started_at < remote_readback_at
        ):
            failures.append(f"gate receipt {index} predates publication readback")

    blocker_requirements = closure.get("blockerRequirements")
    blocker_evidence: dict[str, tuple[str, ...]] = {}
    if isinstance(blocker_requirements, list):
        for blocker in blocker_requirements:
            if not isinstance(blocker, dict):
                continue
            blocker_id = blocker.get("blockerId")
            required = blocker.get("requiredEvidenceKinds")
            if isinstance(blocker_id, str) and isinstance(required, list):
                blocker_evidence[blocker_id] = tuple(
                    kind
                    for kind in required
                    if isinstance(kind, str) and kind in evidence_id_by_kind
                )

    approval_receipts = root.get("approvalReceipts")
    if not isinstance(approval_receipts, list) or len(approval_receipts) != len(roles):
        failures.append("approvalReceipts must contain exactly fourteen records")
        approval_receipts = []
    for index, role in enumerate(roles):
        approval = _exact_ordered_object(
            approval_receipts[index] if index < len(approval_receipts) else None,
            APPROVAL_RECEIPT_FIELDS,
            f"approval receipt {index}",
            failures,
        )
        owner, valid_from, valid_until = owner_by_role.get(role, ({}, None, None))
        for field, expected in (
            ("role", role),
            ("ownerIdentityRef", owner.get("ownerIdentityRef")),
            ("status", "accepted"),
            ("acceptedRevision", LINEAGE_RAW_SHA256[-1]),
            ("acceptedPublicationCommit", commit_object_id),
            ("acceptedBlockerIds", list(role_blockers.get(role, ()))),
        ):
            _require_equal(
                approval.get(field),
                expected,
                f"approval receipt {index}.{field}",
                failures,
            )
        accepted_at = _parse_canonical_utc(
            approval.get("acceptedAt"), f"approval receipt {index}.acceptedAt", failures
        )
        if valid_from is not None and accepted_at is not None and accepted_at < valid_from:
            failures.append(f"approval receipt {index} predates owner validity")
        if valid_until is not None and accepted_at is not None and accepted_at > valid_until:
            failures.append(f"approval receipt {index} exceeds owner validity")
        if (
            remote_readback_at is not None
            and accepted_at is not None
            and accepted_at < remote_readback_at
        ):
            failures.append(f"approval receipt {index} predates publication readback")
        relevant_kinds: set[str] = {"published_checkpoint"}
        for blocker_id in role_blockers.get(role, ()):
            relevant_kinds.update(blocker_evidence.get(blocker_id, ()))
        expected_refs = [
            evidence_id_by_kind[kind]
            for kind in evidence_kinds
            if kind in relevant_kinds and kind in evidence_id_by_kind
        ]
        _require_equal(
            approval.get("acceptanceEvidenceRefs"),
            expected_refs,
            f"approval receipt {index}.acceptanceEvidenceRefs",
            failures,
        )
        for evidence_ref in expected_refs:
            referenced_evidence_ids.add(evidence_ref)
            entry = evidence_by_id.get(evidence_ref)
            if (
                entry is not None
                and entry[1] is not None
                and accepted_at is not None
                and entry[1] > accepted_at
            ):
                failures.append(
                    f"approval receipt {index} predates referenced evidence {evidence_ref!r}"
                )

    if referenced_evidence_ids != set(evidence_by_id):
        failures.append("evidence catalog contains missing, dangling, or orphan references")
    return _finish_candidate_failures(failures)


def _consume_exact_dormant_result(
    candidate_failures: tuple[str, ...],
    *,
    expected_message: str,
    label: str,
    failures: list[str],
) -> None:
    if candidate_failures == (expected_message,):
        return
    non_dormant_failures = tuple(
        failure for failure in candidate_failures if failure != expected_message
    )
    if non_dormant_failures:
        failures.extend(non_dormant_failures)
    else:
        failures.append(
            f"{label} validator did not return the exact dormant non-authorizing result"
        )


def _collect_absent_evidence_artifact_failures(root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    for path in EVIDENCE_SUPPORTING_ARTIFACT_CANDIDATE_PATHS:
        try:
            (root / path).lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            failures.append(f"could not confirm absent evidence artifact {path}: {error}")
        else:
            failures.append(
                f"evidence artifact {path} must be absent while its selector reference is null"
            )
    return tuple(failures)


def _collect_worktree_failures(root: Path = ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    snapshots: list[bytes] = []
    identities: list[tuple[int, int, int, int, int, int]] = []
    for role, path, maximum_bytes in zip(
        LINEAGE_ROLES,
        LINEAGE_PATHS,
        LINEAGE_MAXIMUM_BYTES,
    ):
        try:
            raw, identity = decision.read_g0_content_addressed_snapshot(
                root,
                path,
                f"G0 V3 lineage {role}",
                maximum_bytes,
            )
        except checkpoint.CheckpointValidationError as error:
            failures.append(str(error))
            continue
        snapshots.append(raw)
        identities.append(identity)
    if failures:
        return tuple(failures)
    try:
        receipt_raw, receipt_identity = decision.read_g0_content_addressed_snapshot(
            root,
            RECORDED_PUBLICATION_RECEIPT_PATH,
            "recorded G0 V3 publication receipt candidate",
            MAX_RECORDED_PUBLICATION_RECEIPT_BYTES,
        )
    except checkpoint.CheckpointValidationError as error:
        return (str(error),)
    try:
        profile_raw, profile_identity = decision.read_g0_content_addressed_snapshot(
            root,
            EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_PATH,
            "G0 evidence supporting artifact profile",
            MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
        )
    except checkpoint.CheckpointValidationError as error:
        return (str(error),)
    try:
        input_raw, input_identity = decision.read_g0_content_addressed_snapshot(
            root,
            OWNER_CATALOG_INPUT_PATH,
            "G0 owner/catalog input candidate",
            MAX_OWNER_CATALOG_INPUT_BYTES,
        )
    except checkpoint.CheckpointValidationError as error:
        return (str(error),)
    receipt_failures = _collect_recorded_publication_receipt_candidate_failures(
        receipt_raw,
        lineage_blobs=tuple(snapshots),
    )
    _consume_exact_dormant_result(
        receipt_failures,
        expected_message=RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE,
        label="recorded publication receipt",
        failures=failures,
    )
    failures.extend(
        _collect_evidence_supporting_artifact_profile_failures(
            profile_raw,
            owner_catalog_input_bytes=input_raw,
        )
    )
    failures.extend(_collect_absent_evidence_artifact_failures(root))
    _require_equal(
        _sha256(input_raw),
        EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        "recorded owner/catalog input raw SHA-256",
        failures,
    )
    input_failures = _collect_owner_catalog_input_candidate_failures(
        input_raw,
        lineage_blobs=tuple(snapshots),
    )
    _consume_exact_dormant_result(
        input_failures,
        expected_message=OWNER_CATALOG_INPUT_DORMANT_MESSAGE,
        label="owner/catalog input",
        failures=failures,
    )
    for role, path, maximum_bytes, identity, expected_sha256 in zip(
        LINEAGE_ROLES,
        LINEAGE_PATHS,
        LINEAGE_MAXIMUM_BYTES,
        identities,
        LINEAGE_RAW_SHA256,
    ):
        failures.extend(
            decision.collect_g0_final_snapshot_failures(
                root,
                path,
                f"G0 V3 lineage {role}",
                maximum_bytes,
                identity,
                expected_sha256,
            )
        )
    failures.extend(
        decision.collect_g0_final_snapshot_failures(
            root,
            RECORDED_PUBLICATION_RECEIPT_PATH,
            "recorded G0 V3 publication receipt candidate",
            MAX_RECORDED_PUBLICATION_RECEIPT_BYTES,
            receipt_identity,
            EXPECTED_RECORDED_PUBLICATION_RECEIPT_RAW_SHA256,
        )
    )
    failures.extend(
        decision.collect_g0_final_snapshot_failures(
            root,
            OWNER_CATALOG_INPUT_PATH,
            "G0 owner/catalog input candidate",
            MAX_OWNER_CATALOG_INPUT_BYTES,
            input_identity,
            EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        )
    )
    failures.extend(
        decision.collect_g0_final_snapshot_failures(
            root,
            EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_PATH,
            "G0 evidence supporting artifact profile",
            MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
            profile_identity,
            EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256,
        )
    )
    failures.extend(_collect_absent_evidence_artifact_failures(root))
    return tuple(failures)


def main() -> int:
    failures = _collect_worktree_failures()
    if failures:
        for failure in failures:
            print(f"V1 G0 V3 receipt-bundle contract validation failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 effective V3 contract, published-target receipt candidate, one explicit "
        "owner/catalog proposal with two null artifact references, and the exact "
        "selector-snapshot-bound non-authorizing supporting-artifact profile were "
        "reconstructed; no supporting artifact instance exists, and owner "
        "authentication, evidence verification, activation, command execution, G0 "
        "exit, and G1a remain closed."
    )
    return 0


__all__ = ["compile_dormant_owner_catalog_input_preview"]


if __name__ == "__main__":
    raise SystemExit(main())
