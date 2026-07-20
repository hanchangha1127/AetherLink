#!/usr/bin/env python3
"""Validate the dormant V3 G0 complete-receipt-bundle contract lineage."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
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

MAX_V3_AMENDMENT_BYTES = 262_144
MAX_V3_CHECKPOINT_BYTES = 131_072

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


def _bounded_snapshot(
    value: object,
    label: str,
    maximum_bytes: int,
    failures: list[str],
) -> bytes | None:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        failures.append(f"{label} must be bytes")
        return None
    try:
        observed_size = value.nbytes if isinstance(value, memoryview) else len(value)
    except (BufferError, TypeError, ValueError):
        failures.append(f"{label} is not a readable byte buffer")
        return None
    if observed_size == 0:
        failures.append(f"{label} must not be empty")
        return None
    if observed_size > maximum_bytes:
        failures.append(f"{label} exceeds {maximum_bytes} bytes")
        return None
    try:
        return bytes(value)
    except (BufferError, TypeError, ValueError):
        failures.append(f"{label} is not a readable byte buffer")
        return None


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
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        failures.append(f"{label} must be a real canonical UTC timestamp")
        return None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        failures.append(f"{label} is not canonical UTC")
        return None
    return parsed


def _validate_json_resources(value: object, failures: list[str]) -> None:
    stack: list[tuple[object, int, str]] = [(value, 1, "complete receipt bundle")]
    while stack:
        current, depth, label = stack.pop()
        if depth > MAX_COMPLETE_BUNDLE_DEPTH:
            failures.append(
                f"{label} exceeds maximum JSON depth {MAX_COMPLETE_BUNDLE_DEPTH}"
            )
            continue
        if isinstance(current, str):
            try:
                encoded = current.encode("utf-8")
            except UnicodeEncodeError:
                failures.append(f"{label} contains a non-UTF-8 Unicode scalar")
                continue
            if len(encoded) > MAX_COMPLETE_BUNDLE_STRING_BYTES:
                failures.append(
                    f"{label} exceeds {MAX_COMPLETE_BUNDLE_STRING_BYTES} UTF-8 bytes"
                )
        elif isinstance(current, list):
            if len(current) > MAX_COMPLETE_BUNDLE_ARRAY_ITEMS:
                failures.append(
                    f"{label} exceeds {MAX_COMPLETE_BUNDLE_ARRAY_ITEMS} array items"
                )
                continue
            for index, child in enumerate(reversed(current)):
                actual_index = len(current) - index - 1
                stack.append((child, depth + 1, f"{label}[{actual_index}]"))
        elif isinstance(current, dict):
            if len(current) > MAX_COMPLETE_BUNDLE_ARRAY_ITEMS:
                failures.append(
                    f"{label} exceeds {MAX_COMPLETE_BUNDLE_ARRAY_ITEMS} object fields"
                )
                continue
            for key, child in reversed(tuple(current.items())):
                try:
                    encoded_key = key.encode("utf-8")
                except UnicodeEncodeError:
                    failures.append(f"{label} key contains a non-UTF-8 Unicode scalar")
                    continue
                if len(encoded_key) > MAX_COMPLETE_BUNDLE_STRING_BYTES:
                    failures.append(
                        f"{label} key exceeds {MAX_COMPLETE_BUNDLE_STRING_BYTES} UTF-8 bytes"
                    )
                stack.append((child, depth + 1, f"{label}.{key}"))


def _safe_artifact_path(value: object) -> bool:
    try:
        checkpoint.canonical_relative_path(value, "receipt evidence artifact path")
    except checkpoint.CheckpointValidationError:
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


def _finish_candidate_failures(failures: list[str]) -> tuple[str, ...]:
    if COMPLETE_BUNDLE_DORMANT_MESSAGE not in failures:
        failures.append(COMPLETE_BUNDLE_DORMANT_MESSAGE)
    return tuple(failures)


def _collect_complete_bundle_candidate_failures(
    bundle_bytes: object,
    *,
    lineage_blobs: tuple[object, ...],
) -> tuple[str, ...]:
    """Compile caller-supplied candidate bytes while always remaining dormant."""

    failures: list[str] = []
    if not isinstance(lineage_blobs, tuple) or len(lineage_blobs) != len(LINEAGE_PATHS):
        failures.append("V3 bundle lineage must be an exact six-blob tuple")
        return _finish_candidate_failures(failures)
    lineage_snapshots: list[bytes] = []
    for role, value, maximum_bytes in zip(
        LINEAGE_ROLES,
        lineage_blobs,
        LINEAGE_MAXIMUM_BYTES,
    ):
        snapshot = _bounded_snapshot(
            value,
            f"G0 V3 bundle lineage {role}",
            maximum_bytes,
            failures,
        )
        if snapshot is not None:
            lineage_snapshots.append(snapshot)
    if failures or len(lineage_snapshots) != len(LINEAGE_PATHS):
        return _finish_candidate_failures(failures)
    immutable_lineage = tuple(lineage_snapshots)
    failures.extend(_collect_v3_lineage_failures(*immutable_lineage))
    if failures:
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
    _validate_json_resources(bundle, failures)
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

    publication_receipt = _exact_ordered_object(
        root.get("publicationReceipt"),
        PUBLICATION_RECEIPT_FIELDS,
        "publication receipt",
        failures,
    )
    repository_ref = publication_receipt.get("repositoryRef")
    commit_object_id = publication_receipt.get("commitObjectId")
    if not _valid_opaque_text(repository_ref):
        failures.append("publication receipt repositoryRef is invalid")
    if not isinstance(commit_object_id, str) or _GIT_OBJECT_ID_PATTERN.fullmatch(commit_object_id) is None:
        failures.append("publication receipt commitObjectId is invalid")
    artifact_bindings = publication_receipt.get("artifactBindings")
    if not isinstance(artifact_bindings, list) or len(artifact_bindings) != 6:
        failures.append("publication receipt artifactBindings must contain exactly six entries")
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
    failures.extend(_collect_v3_lineage_failures(*snapshots))
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
    return tuple(failures)


def main() -> int:
    failures = _collect_worktree_failures()
    if failures:
        for failure in failures:
            print(f"V1 G0 V3 receipt-bundle contract validation failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 effective V3 complete-receipt-bundle contract reconstructed from six "
        "content-addressed local candidate blobs; publication, independent trust inputs, "
        "receipt activation, command execution, G0 exit, and G1a remain closed."
    )
    return 0


__all__: list[str] = []


if __name__ == "__main__":
    raise SystemExit(main())
