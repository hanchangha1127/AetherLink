#!/usr/bin/env python3
"""Validate dormant profiles for the eight externally rooted G0 evidence kinds.

The pure entry points consume supplied bytes only.  They define and validate
closed candidate payloads, but they do not acquire external values, authenticate
an owner, verify evidence, create a catalog record, or change G0/G1a authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

try:
    from script import check_v1_g0_baseline_evidence_readiness as baseline
    from script import check_v1_g0_checkpoint as checkpoint
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_receipt_bundle as receipt
except ModuleNotFoundError:
    import check_v1_g0_baseline_evidence_readiness as baseline
    import check_v1_g0_checkpoint as checkpoint
    import check_v1_g0_decision as decision
    import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = "docs/v1/g0/external-evidence-candidate-profile-v1.json"
BASELINE_PROFILE_PATH = baseline.PROFILE_PATH
SUPPORTING_PROFILE_PATH = receipt.EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_PATH
OWNER_CATALOG_INPUT_PATH = receipt.OWNER_CATALOG_INPUT_PATH
DECISION_PATH = "docs/v1/g0/decision-v1.json"
EXPECTED_DECISION_RAW_SHA256 = (
    "44dd88a0de7e02fdb2b7c22e597496ffe4f00f9a67a54af6e9ace8afdcf9308a"
)
EXPECTED_PROFILE_RAW_SHA256 = (
    "e5233e7b52369299aa50f07adb726ec57c0ea5e4ffe138e0b2725b8d5f87b371"
)
EXPECTED_PLAN_RAW_SHA256 = (
    "a40914504f5ffde47a84d0745d4ffe1976fecf0e47a57bd876b390de6081183b"
)
EXPECTED_PLAN_BYTE_LENGTH = 5_179

MAX_PROFILE_BYTES = 262_144
MAX_DECISION_BYTES = 65_536
MAX_CANDIDATE_BYTES = 131_072
MAX_JSON_DEPTH = 16
MAX_JSON_ITEMS = 128
MAX_STRING_BYTES = 512

DORMANT_MESSAGE = (
    "G0 external evidence candidate is candidate_unverified_non_authorizing; "
    "supplied-byte validation cannot authenticate owners, verify external facts, "
    "create catalog records or receipts, close G0, or authorize G1a"
)

EXPECTED_REMAINING_EVIDENCE_COUNT = 8

PROFILE_FIELDS = (
    "documentType",
    "schemaVersion",
    "profileId",
    "status",
    "contractBinding",
    "coverageDerivation",
    "artifactPaths",
    "evidenceProfiles",
    "commonEnvelopeProfile",
    "readinessPlanProfile",
    "resourceBounds",
    "sensitiveDataPolicy",
    "authorizationBoundary",
    "supersessionPolicy",
)
CONTRACT_FIELDS = (
    "repositoryRef",
    "publicationCommitObjectId",
    "publicationCheckpointPath",
    "publicationCheckpointRawSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
    "decisionId",
    "decisionCanonicalSha256",
    "coveredBlockerIds",
    "requiredCheckIds",
    "requiredOwnerRoles",
    "requiredEvidenceKinds",
    "existingTypedEvidenceKinds",
    "totalNonDerivedEvidenceKindCount",
)
COVERAGE_FIELDS = (
    "decisionRef",
    "baselineProfileRef",
    "supportingProfileRef",
    "ownerCatalogInputRef",
    "effectiveV3NonDerivedKindsCanonicalSha256",
    "existingTypedKindsCanonicalSha256",
    "remainingKindsCanonicalSha256",
    "subtractionPolicy",
    "ownerCatalogSelectionPolicy",
)
DECISION_REF_FIELDS = ("path", "rawSha256", "canonicalSha256")
COVERAGE_REF_FIELDS = ("path", "rawSha256", "coveredEvidenceKinds")
OWNER_CATALOG_REF_FIELDS = ("path", "rawSha256")
ARTIFACT_PATH_FIELDS = ("evidenceKind", "candidateVersion", "path")
EVIDENCE_PROFILE_FIELDS = (
    "evidenceKind",
    "blockerId",
    "requiredCheckIds",
    "requiredOwnerRoles",
    "artifactId",
    "candidatePath",
    "exactPayloadFields",
    "nestedFieldProfiles",
    "validationPolicy",
    "requiredIndependentInputsAbsent",
)
NESTED_FIELD_PROFILE_FIELDS = (
    "field",
    "entryExactFields",
    "cardinalityPolicy",
    "valuePolicy",
)
COMMON_PROFILE_FIELDS = (
    "exactFields",
    "fixedValues",
    "profileRefExactFields",
    "contractBindingExactFields",
    "intakeBindingExactFields",
    "intakeBindingFixedValues",
    "trustBoundaryExactFields",
    "trustBoundaryFixedValues",
    "stateExactFields",
    "stateFixedValues",
    "canonicalEncoding",
)
READINESS_PLAN_PROFILE_FIELDS = (
    "documentType",
    "schemaVersion",
    "planId",
    "status",
    "reservationExactFields",
    "artifactInstancePolicy",
    "authorizationEffect",
)
RESOURCE_FIELDS = (
    "profileMaximumBytes",
    "candidateMaximumBytes",
    "jsonMaximumDepth",
    "arrayMaximumItems",
    "stringMaximumUtf8Bytes",
    "integerMaximumDigits",
    "parsePolicy",
    "integerPolicy",
    "pathPolicy",
    "canonicalEncoding",
)
SENSITIVE_POLICY_FIELDS = (
    "allowedVariableInputs",
    "forbiddenMaterial",
    "arbitraryFreeFormFieldsAllowed",
    "referencePolicy",
    "publicValueReviewPolicy",
)
AUTHORIZATION_FIELDS = (
    "catalogRecordReservedFields",
    "candidateForbiddenFields",
    "derivedEvidenceKindsForbidden",
    "candidateValidationMayReadFiles",
    "candidateValidationMayUseNetwork",
    "candidateValidationMayAuthenticateOwner",
    "candidateValidationMayVerifyEvidence",
    "candidateValidationMayCreateCatalogRecords",
    "candidateValidationMayCreateApprovalReceipts",
    "candidateValidationMayCloseBlocker",
    "candidateValidationMayActivateReceipts",
    "candidateValidationMayCompleteG0",
    "candidateValidationMayAuthorizeG1a",
    "artifactInstancePolicy",
)
SUPERSESSION_FIELDS = (
    "mutateInPlaceAllowed",
    "verifiedStateMutationAllowed",
    "candidateToCatalogRecordMutationAllowed",
    "replacementPolicy",
    "nextProfilePathPattern",
)

CANDIDATE_FIELDS = (
    "documentType",
    "schemaVersion",
    "artifactId",
    "evidenceKind",
    "status",
    "profileRef",
    "contractBinding",
    "intakeBinding",
    "payload",
    "trustBoundary",
    "state",
)
PROFILE_REF_FIELDS = ("path", "profileId", "rawSha256")
CANDIDATE_CONTRACT_FIELDS = (
    "repositoryRef",
    "publicationCommitObjectId",
    "publicationCheckpointPath",
    "publicationCheckpointRawSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
    "decisionId",
    "decisionCanonicalSha256",
    "blockerId",
    "requiredCheckIds",
    "requiredOwnerRoles",
    "evidenceKind",
)
INTAKE_BINDING_FIELDS = (
    "candidateVersion",
    "reservedArtifactPath",
    "selectorState",
    "ownerBindingRefCandidate",
    "evidenceInputRefCandidate",
    "supportingArtifactPresent",
    "supportingArtifactRefCandidate",
)
TRUST_BOUNDARY_FIELDS = (
    "observationClass",
    "independentInputsPresent",
    "requiredIndependentInputsAbsent",
    "ownerIdentityAuthenticated",
    "externalFactsVerified",
    "catalogRecordDerivable",
    "approvalReceiptDerivable",
    "authorityDerivable",
)
STATE_FIELDS = (
    "ownerIdentityAuthenticated",
    "evidenceVerified",
    "approvalReceiptAccepted",
    "blockerClosureDerived",
    "receiptActivationAllowed",
    "g0ExitComplete",
    "g1aMayStartNow",
)
REQUIRED_INDEPENDENT_INPUTS_ABSENT = (
    "authenticated_owner_binding_and_approval_receipt",
    "independent_external_source_provenance",
    "independent_exact_artifact_verification",
    "trusted_validation_time",
)

PLAN_FIELDS = (
    "documentType",
    "schemaVersion",
    "planId",
    "status",
    "profileRef",
    "contractBinding",
    "candidateArtifactReservations",
    "state",
)
PLAN_RESERVATION_FIELDS = (
    "evidenceKind",
    "blockerId",
    "requiredOwnerRoles",
    "path",
    "artifactPresent",
    "externalValuesSelected",
    "acquisitionAuthorized",
)

APPLICATION_ID_PAYLOAD_FIELDS = (
    "applicationIds",
    "versionPolicyRefCandidate",
    "migrationPolicyRefCandidate",
)
APPLICATION_ID_ENTRY_FIELDS = (
    "platform",
    "identifier",
    "distributionChannel",
    "ownershipRecordRefCandidate",
)
DISTRIBUTION_ACCOUNT_PAYLOAD_FIELDS = (
    "accounts",
    "accessControlRunbookRefCandidate",
    "recoveryRunbookRefCandidate",
)
DISTRIBUTION_ACCOUNT_ENTRY_FIELDS = (
    "platform",
    "distributionChannel",
    "accountOrganizationRefCandidate",
    "accountControlEvidenceRefCandidate",
)
KEY_CUSTODY_PAYLOAD_FIELDS = (
    "keyClasses",
    "custodyRunbookRefCandidate",
    "separationOfDutiesPolicyRefCandidate",
)
KEY_CLASS_ENTRY_FIELDS = (
    "keyPurpose",
    "custodyClass",
    "custodyProviderRefCandidate",
    "accessPolicyRefCandidate",
    "rotationPolicyRefCandidate",
    "recoveryPolicyRefCandidate",
    "emergencyRevocationRefCandidate",
)
PROVIDER_MATRIX_PAYLOAD_FIELDS = (
    "matrixRevisionRefCandidate",
    "providers",
    "testPolicyRefCandidate",
)
PROVIDER_ENTRY_FIELDS = (
    "providerId",
    "minimumCandidateVersion",
    "currentCandidateVersion",
    "previousCandidateVersion",
    "compatibilityProfileRefCandidate",
    "evidenceRefCandidates",
)
SERVICE_DOMAIN_PAYLOAD_FIELDS = ("services", "lifecycleRunbookRefCandidate")
SERVICE_DOMAIN_ENTRY_FIELDS = (
    "serviceRole",
    "domainName",
    "domainOwnershipRecordRefCandidate",
    "dnsControlEvidenceRefCandidate",
    "webpkiLifecycleRefCandidate",
    "renewalMonitoringRefCandidate",
)
ROOT_SIGNER_PAYLOAD_FIELDS = (
    "custodyAssignments",
    "rotationOverlapSeconds",
    "rotationPolicyRefCandidate",
    "keyCeremonyRunbookRefCandidate",
    "separationOfDutiesPolicyRefCandidate",
)
CUSTODY_ASSIGNMENT_ENTRY_FIELDS = (
    "responsibility",
    "assignmentRecordRefCandidate",
    "custodyProfileRefCandidate",
)
PRIVACY_PAYLOAD_FIELDS = (
    "privacyPolicyRefCandidate",
    "retentionSchedule",
    "dataDeletionRunbookRefCandidate",
    "incidentResponseRunbookRefCandidate",
    "notificationPolicyRefCandidate",
    "policyReviewRecordRefCandidate",
)
RETENTION_SCHEDULE_FIELDS = (
    "aggregateOperationalMetricsDays",
    "sourceFreeSecurityEventsDays",
    "sanitizedIncidentEvidenceDays",
    "contentFreeReleaseRecordsDays",
)
RELAY_BUDGET_PAYLOAD_FIELDS = (
    "regions",
    "projectedPeakConcurrentSessions",
    "requiredCapacityMultiplierBasisPoints",
    "monthlyCostCeilingMinorUnits",
    "currency",
    "capacityForecastRefCandidate",
    "loadModelRefCandidate",
    "budgetReviewRecordRefCandidate",
)
REGION_ENTRY_FIELDS = ("regionCode", "providerRegionRefCandidate")

PAYLOAD_FIELDS_BY_KIND = {
    "owned_application_ids": APPLICATION_ID_PAYLOAD_FIELDS,
    "distribution_accounts": DISTRIBUTION_ACCOUNT_PAYLOAD_FIELDS,
    "key_custody_runbook": KEY_CUSTODY_PAYLOAD_FIELDS,
    "approved_minimum_current_previous_matrix": PROVIDER_MATRIX_PAYLOAD_FIELDS,
    "domain_dns_webpki_owners": SERVICE_DOMAIN_PAYLOAD_FIELDS,
    "root_signer_rotation_and_revocation_owners": ROOT_SIGNER_PAYLOAD_FIELDS,
    "privacy_incident_and_retention_owner_approval": PRIVACY_PAYLOAD_FIELDS,
    "approved_region_peak_capacity_and_cost_ceiling": RELAY_BUDGET_PAYLOAD_FIELDS,
}

SUPPORTED_PAYLOAD_KINDS = tuple(PAYLOAD_FIELDS_BY_KIND)
ARTIFACT_PATHS = {
    kind: f"docs/evidence/g0-{kind.replace('_', '-')}-candidate-v1.json"
    for kind in SUPPORTED_PAYLOAD_KINDS
}

REFERENCE_CLASSES = (
    "public-record",
    "policy",
    "runbook",
    "ownership-record",
    "account-organization",
    "account-control-evidence",
    "custody-provider",
    "compatibility-profile",
    "evidence-record",
    "domain-ownership",
    "dns-control",
    "webpki-lifecycle",
    "renewal-monitoring",
    "assignment-record",
    "custody-profile",
    "capacity-forecast",
    "load-model",
    "review-record",
    "provider-region",
    "matrix",
)
REFERENCE_PATTERN = re.compile(
    r"^(?:"
    + "|".join(re.escape(value) for value in REFERENCE_CLASSES)
    + r"):sha256:[0-9a-f]{64}:v[1-9][0-9]{0,8}$"
)
APPLICATION_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]{0,62}(?:\.[a-z][a-z0-9_]{0,62}){2,7}$"
)
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$")
DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
REGION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

KEY_PURPOSES = (
    "android_play_app_signing",
    "android_upload",
    "macos_developer_id_application",
    "macos_notarization",
)
CUSTODY_CLASSES = (
    "platform_managed_non_exportable",
    "offline_hardware_or_cold",
    "non_exportable_hsm_or_kms",
    "operating_system_keychain",
)
SERVICE_ROLES = ("allocation_api", "signaling", "turn", "sealed_relay")
CUSTODY_RESPONSIBILITIES = (
    "offline_root_custody",
    "online_signer_custody",
    "emergency_revocation",
)
def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _require_exact(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not decision.exactly_equal(actual, expected):
        failures.append(f"{label} is not exact")


def _require_reference(value: object, label: str, failures: list[str]) -> None:
    if not isinstance(value, str) or REFERENCE_PATTERN.fullmatch(value) is None:
        failures.append(f"{label} must be a bounded versioned nonsecret reference")


def _require_pattern(
    value: object,
    pattern: re.Pattern[str],
    label: str,
    failures: list[str],
) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        failures.append(f"{label} is invalid")


def _require_int(
    value: object,
    minimum: int,
    maximum: int,
    label: str,
    failures: list[str],
) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        failures.append(f"{label} must be an exact integer in [{minimum}, {maximum}]")


def _expected_nested_profiles(kind: str) -> list[dict[str, object]]:
    definitions: dict[str, tuple[str, tuple[str, ...], str, str]] = {
        "owned_application_ids": (
            "applicationIds",
            APPLICATION_ID_ENTRY_FIELDS,
            "exactly_android_then_macos",
            "valid_production_identifier_exact_selected_channel_and_versioned_ownership_record_ref",
        ),
        "distribution_accounts": (
            "accounts",
            DISTRIBUTION_ACCOUNT_ENTRY_FIELDS,
            "exactly_android_then_macos",
            "exact_selected_channel_and_versioned_nonpersonal_organization_and_control_refs",
        ),
        "key_custody_runbook": (
            "keyClasses",
            KEY_CLASS_ENTRY_FIELDS,
            "exactly_four_required_key_purposes_in_canonical_order",
            "closed_custody_class_and_versioned_policy_refs_no_key_bytes_or_signatures",
        ),
        "approved_minimum_current_previous_matrix": (
            "providers",
            PROVIDER_ENTRY_FIELDS,
            "exactly_ollama_then_lm_studio",
            "three_bounded_versions_per_provider_and_at_least_two_versioned_evidence_refs",
        ),
        "domain_dns_webpki_owners": (
            "services",
            SERVICE_DOMAIN_ENTRY_FIELDS,
            "exactly_allocation_api_signaling_turn_sealed_relay_in_order",
            "lowercase_dns_name_and_versioned_ownership_dns_webpki_monitoring_refs",
        ),
        "root_signer_rotation_and_revocation_owners": (
            "custodyAssignments",
            CUSTODY_ASSIGNMENT_ENTRY_FIELDS,
            "exactly_offline_root_online_signer_emergency_revocation_in_order",
            "versioned_assignment_and_custody_refs_without_owner_identity_or_key_material",
        ),
        "privacy_incident_and_retention_owner_approval": (
            "retentionSchedule",
            RETENTION_SCHEDULE_FIELDS,
            "one_exact_object",
            "exact_decision_v1_retention_days",
        ),
        "approved_region_peak_capacity_and_cost_ceiling": (
            "regions",
            REGION_ENTRY_FIELDS,
            "exactly_one_initial_region",
            "bounded_region_code_and_versioned_provider_region_ref",
        ),
    }
    field, fields, cardinality, policy = definitions[kind]
    return [
        {
            "field": field,
            "entryExactFields": list(fields),
            "cardinalityPolicy": cardinality,
            "valuePolicy": policy,
        }
    ]


def _expected_validation_policy(kind: str) -> str:
    policies = {
        "owned_application_ids": "production_ids_must_differ_from_current_debug_ids_and_bind_selected_channels",
        "distribution_accounts": "opaque_nonpersonal_account_refs_only_no_tokens_emails_or_account_credentials",
        "key_custody_runbook": "all_distribution_key_purposes_require_custody_access_rotation_recovery_and_revocation_refs",
        "approved_minimum_current_previous_matrix": "both_runtime_host_providers_require_minimum_current_previous_versions_and_evidence",
        "domain_dns_webpki_owners": "all_production_service_roles_require_domain_dns_webpki_and_renewal_lifecycle_refs",
        "root_signer_rotation_and_revocation_owners": "offline_root_online_signer_and_emergency_revocation_assignments_remain_reference_only",
        "privacy_incident_and_retention_owner_approval": "decision_v1_retention_values_and_all_policy_runbook_review_refs_are_required",
        "approved_region_peak_capacity_and_cost_ceiling": "one_initial_region_positive_peak_two_x_capacity_basis_and_positive_iso4217_cost_ceiling_required",
    }
    return policies[kind]


def _derive_contract(
    effective_v3: dict[str, object],
    baseline_profile: dict[str, object],
    supporting_profile: dict[str, object],
    owner_catalog_input: dict[str, object],
    failures: list[str],
) -> tuple[
    dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    closure = effective_v3.get("g0ClosureContract")
    if not isinstance(closure, dict):
        failures.append("effective V3 g0ClosureContract is unavailable")
        return {}, (), (), ()
    _, evidence_kinds, _, _, _ = receipt._derive_contract_sets(effective_v3, failures)
    non_derived = tuple(evidence_kinds)

    def covered_kinds(profile: dict[str, object], label: str) -> tuple[str, ...]:
        contract = profile.get("contractBinding")
        kinds = contract.get("requiredEvidenceKinds") if isinstance(contract, dict) else None
        if not isinstance(kinds, list) or not all(isinstance(kind, str) for kind in kinds):
            failures.append(f"{label} coverage is unavailable")
            return ()
        if len(kinds) != len(set(kinds)):
            failures.append(f"{label} coverage contains duplicates")
        return tuple(kinds)

    baseline_kinds = covered_kinds(baseline_profile, "baseline profile")
    supporting_kinds = covered_kinds(supporting_profile, "supporting profile")
    overlap = set(baseline_kinds).intersection(supporting_kinds)
    if overlap:
        failures.append("existing typed evidence profile coverage overlaps")
    existing_set = set(baseline_kinds).union(supporting_kinds)
    unknown_existing = existing_set.difference(non_derived)
    if unknown_existing:
        failures.append("existing typed evidence coverage contains a non-V3 kind")
    existing = tuple(kind for kind in non_derived if kind in existing_set)
    _require_exact(
        existing,
        baseline_kinds + supporting_kinds,
        "existing typed evidence canonical order",
        failures,
    )
    remaining = tuple(kind for kind in non_derived if kind not in existing_set)
    if len(remaining) != EXPECTED_REMAINING_EVIDENCE_COUNT:
        failures.append("effective V3 subtraction must produce exactly eight remaining kinds")
    if set(remaining) != set(SUPPORTED_PAYLOAD_KINDS):
        failures.append("remaining V3 evidence kinds do not match the closed payload schemas")

    selected_catalog_kinds: list[str] = []
    responses = owner_catalog_input.get("responses")
    if not isinstance(responses, list):
        failures.append("owner/catalog input responses are unavailable")
    else:
        for response in responses:
            if not isinstance(response, dict):
                continue
            candidates = response.get("evidenceCandidates")
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                if isinstance(candidate, dict) and isinstance(candidate.get("evidenceKind"), str):
                    selected_catalog_kinds.append(candidate["evidenceKind"])
    if set(selected_catalog_kinds).intersection(remaining):
        failures.append("a remaining external evidence kind already has an intake selector")

    unordered_mapping: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {}
    blockers = closure.get("blockerRequirements")
    if not isinstance(blockers, list):
        failures.append("effective V3 blocker requirements are unavailable")
        return {}, non_derived, existing, remaining
    for blocker in blockers:
        if not isinstance(blocker, dict):
            failures.append("effective V3 blocker requirement is not an object")
            continue
        blocker_id = blocker.get("blockerId")
        checks = blocker.get("requiredCheckIds")
        roles = blocker.get("requiredOwnerRoles")
        kinds = blocker.get("requiredEvidenceKinds")
        if (
            not isinstance(blocker_id, str)
            or not isinstance(checks, list)
            or not isinstance(roles, list)
            or not isinstance(kinds, list)
        ):
            failures.append("effective V3 blocker projection is malformed")
            continue
        for kind in kinds:
            if kind in remaining:
                if kind in unordered_mapping:
                    failures.append(f"external evidence kind {kind!r} maps to multiple blockers")
                unordered_mapping[kind] = (blocker_id, tuple(checks), tuple(roles))
    mapping = {
        kind: unordered_mapping[kind]
        for kind in remaining
        if kind in unordered_mapping
    }
    _require_exact(tuple(mapping), remaining, "external evidence order", failures)
    covered_checks = tuple(
        dict.fromkeys(check for _, checks, _ in mapping.values() for check in checks)
    )
    non_executable_checks = closure.get("nonExecutableCheckIds")
    if not isinstance(non_executable_checks, list):
        failures.append("effective V3 non-executable check order is unavailable")
    elif (
        len(covered_checks) != 5
        or any(check not in non_executable_checks for check in covered_checks)
        or tuple(check for check in non_executable_checks if check in covered_checks)
        != covered_checks
    ):
        failures.append(
            "remaining external evidence must map to five canonical non-executable checks"
        )
    return mapping, non_derived, existing, remaining


def _expected_contract(
    mapping: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]],
    non_derived: tuple[str, ...],
    existing: tuple[str, ...],
) -> dict[str, object]:
    blockers = tuple(dict.fromkeys(blocker for blocker, _, _ in mapping.values()))
    checks = tuple(dict.fromkeys(check for _, values, _ in mapping.values() for check in values))
    roles = tuple(dict.fromkeys(role for _, _, values in mapping.values() for role in values))
    return {
        "repositoryRef": receipt.EXPECTED_RECORDED_REPOSITORY_REF,
        "publicationCommitObjectId": receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
        "publicationCheckpointPath": receipt.V3_CHECKPOINT_PATH,
        "publicationCheckpointRawSha256": receipt.LINEAGE_RAW_SHA256[-1],
        "effectiveAssuranceCanonicalSha256": receipt.EXPECTED_EFFECTIVE_V3_SHA256,
        "effectiveClosureCanonicalSha256": receipt.EXPECTED_CLOSURE_V3_SHA256,
        "decisionId": "aetherlink_v1_g0_decision_v1",
        "decisionCanonicalSha256": decision.EXPECTED_DECISION_CANONICAL_SHA256,
        "coveredBlockerIds": list(blockers),
        "requiredCheckIds": list(checks),
        "requiredOwnerRoles": list(roles),
        "requiredEvidenceKinds": list(mapping),
        "existingTypedEvidenceKinds": list(existing),
        "totalNonDerivedEvidenceKindCount": len(non_derived),
    }


def _expected_coverage_derivation(
    non_derived: tuple[str, ...],
    existing: tuple[str, ...],
    remaining: tuple[str, ...],
) -> dict[str, object]:
    return {
        "decisionRef": {
            "path": DECISION_PATH,
            "rawSha256": EXPECTED_DECISION_RAW_SHA256,
            "canonicalSha256": decision.EXPECTED_DECISION_CANONICAL_SHA256,
        },
        "baselineProfileRef": {
            "path": BASELINE_PROFILE_PATH,
            "rawSha256": baseline.EXPECTED_PROFILE_RAW_SHA256,
            "coveredEvidenceKinds": list(existing[:5]),
        },
        "supportingProfileRef": {
            "path": SUPPORTING_PROFILE_PATH,
            "rawSha256": receipt.EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256,
            "coveredEvidenceKinds": list(existing[5:]),
        },
        "ownerCatalogInputRef": {
            "path": OWNER_CATALOG_INPUT_PATH,
            "rawSha256": receipt.EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        },
        "effectiveV3NonDerivedKindsCanonicalSha256": _sha256(_canonical_bytes(list(non_derived))),
        "existingTypedKindsCanonicalSha256": _sha256(_canonical_bytes(list(existing))),
        "remainingKindsCanonicalSha256": _sha256(_canonical_bytes(list(remaining))),
        "subtractionPolicy": "effective_v3_non_derived_order_minus_content_addressed_baseline_five_and_supporting_two_profiles_exactly_once",
        "ownerCatalogSelectionPolicy": "all_eight_remaining_kinds_have_no_v1_intake_selector_and_require_a_new_versioned_profile_after_selection",
    }


def _expected_evidence_profiles(
    mapping: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]],
) -> list[dict[str, object]]:
    return [
        {
            "evidenceKind": kind,
            "blockerId": mapping[kind][0],
            "requiredCheckIds": list(mapping[kind][1]),
            "requiredOwnerRoles": list(mapping[kind][2]),
            "artifactId": f"g0-{kind.replace('_', '-')}-candidate-v1",
            "candidatePath": ARTIFACT_PATHS[kind],
            "exactPayloadFields": list(PAYLOAD_FIELDS_BY_KIND[kind]),
            "nestedFieldProfiles": _expected_nested_profiles(kind),
            "validationPolicy": _expected_validation_policy(kind),
            "requiredIndependentInputsAbsent": list(REQUIRED_INDEPENDENT_INPUTS_ABSENT),
        }
        for kind in mapping
    ]


def _expected_common_profile() -> dict[str, object]:
    return {
        "exactFields": list(CANDIDATE_FIELDS),
        "fixedValues": {
            "documentType": "aetherlink.v1-g0-external-evidence-candidate",
            "schemaVersion": 1,
            "status": "synthetic_fixture_unverified_non_authorizing",
        },
        "profileRefExactFields": list(PROFILE_REF_FIELDS),
        "contractBindingExactFields": list(CANDIDATE_CONTRACT_FIELDS),
        "intakeBindingExactFields": list(INTAKE_BINDING_FIELDS),
        "intakeBindingFixedValues": {
            "candidateVersion": 1,
            "selectorState": "not_selected",
            "ownerBindingRefCandidate": None,
            "evidenceInputRefCandidate": None,
            "supportingArtifactPresent": False,
            "supportingArtifactRefCandidate": None,
        },
        "trustBoundaryExactFields": list(TRUST_BOUNDARY_FIELDS),
        "trustBoundaryFixedValues": {
            "observationClass": "synthetic_fixture_unverified",
            "independentInputsPresent": [],
            "requiredIndependentInputsAbsent": list(REQUIRED_INDEPENDENT_INPUTS_ABSENT),
            "ownerIdentityAuthenticated": False,
            "externalFactsVerified": False,
            "catalogRecordDerivable": False,
            "approvalReceiptDerivable": False,
            "authorityDerivable": False,
        },
        "stateExactFields": list(STATE_FIELDS),
        "stateFixedValues": {field: False for field in STATE_FIELDS},
        "canonicalEncoding": "compact_utf8_json_no_trailing_newline_preserve_declared_field_order",
    }


def _expected_readiness_plan_profile() -> dict[str, object]:
    return {
        "documentType": "aetherlink.v1-g0-external-evidence-readiness-plan",
        "schemaVersion": 1,
        "planId": "aetherlink_v1_g0_external_evidence_readiness_plan_v1",
        "status": "prepared_unselected_unverified_non_authorizing",
        "reservationExactFields": list(PLAN_RESERVATION_FIELDS),
        "artifactInstancePolicy": "all_eight_reserved_candidate_paths_must_remain_absent_until_public_values_are_separately_selected_and_reviewed",
        "authorizationEffect": "none",
    }


def _expected_resource_bounds() -> dict[str, object]:
    return {
        "profileMaximumBytes": MAX_PROFILE_BYTES,
        "candidateMaximumBytes": MAX_CANDIDATE_BYTES,
        "jsonMaximumDepth": MAX_JSON_DEPTH,
        "arrayMaximumItems": MAX_JSON_ITEMS,
        "stringMaximumUtf8Bytes": MAX_STRING_BYTES,
        "integerMaximumDigits": 12,
        "parsePolicy": "strict_utf8_json_reject_duplicate_keys_nonfinite_numbers_unknown_or_reordered_fields",
        "integerPolicy": "exact_json_integers_only_no_boolean_aliases",
        "pathPolicy": "fixed_repository_relative_candidate_paths_no_symlink_or_existing_instance_in_default_check",
        "canonicalEncoding": "compact_utf8_json_no_trailing_newline_preserve_declared_field_order",
    }


def _expected_sensitive_policy() -> dict[str, object]:
    return {
        "allowedVariableInputs": [
            "public_production_application_identifiers",
            "opaque_versioned_public_record_and_policy_refs",
            "bounded_provider_versions",
            "public_service_dns_names",
            "bounded_public_region_capacity_and_cost_values",
        ],
        "forbiddenMaterial": [
            "private_keys",
            "raw_public_or_private_key_bytes",
            "certificate_bytes",
            "signatures",
            "credentials",
            "access_tokens",
            "account_tokens",
            "passwords",
            "recovery_codes",
            "private_account_data",
            "personal_contact_data",
            "personal_names_emails_phone_numbers_or_addresses",
            "http_headers",
            "dns_api_secrets",
            "unsanitized_logs",
            "arbitrary_logs",
            "artifact_bytes",
            "qr_pairing_or_route_secrets",
            "provider_urls_with_credentials",
        ],
        "arbitraryFreeFormFieldsAllowed": False,
        "referencePolicy": "all_refs_use_an_allowlisted_class_plus_literal_sha256_lowercase_digest_and_version_with_no_raw_identifier_or_secret_material",
        "publicValueReviewPolicy": "candidate_values_must_be_separately_reviewed_before_any_artifact_is_written_or_cataloged",
    }


def _expected_authorization_boundary() -> dict[str, object]:
    return {
        "catalogRecordReservedFields": list(receipt.EVIDENCE_RECORD_FIELDS),
        "candidateForbiddenFields": [
            "verifiedAt",
            "verifierIdentityRef",
            "provenanceRef",
            "ownerBinding",
            "approvalReceipt",
            "evidenceCatalogRecord",
            "authorityBinding",
            "runnerAttestation",
            "gateReceipt",
            "receiptActivation",
            "g0ExitAuthority",
            "g1aAuthority",
        ],
        "derivedEvidenceKindsForbidden": [
            "owner_acceptance",
            "quality_measurement_contract_owner_approvals",
        ],
        "candidateValidationMayReadFiles": False,
        "candidateValidationMayUseNetwork": False,
        "candidateValidationMayAuthenticateOwner": False,
        "candidateValidationMayVerifyEvidence": False,
        "candidateValidationMayCreateCatalogRecords": False,
        "candidateValidationMayCreateApprovalReceipts": False,
        "candidateValidationMayCloseBlocker": False,
        "candidateValidationMayActivateReceipts": False,
        "candidateValidationMayCompleteG0": False,
        "candidateValidationMayAuthorizeG1a": False,
        "artifactInstancePolicy": "profile_and_plan_only_no_candidate_instance_exists_now",
    }


def _expected_supersession_policy() -> dict[str, object]:
    return {
        "mutateInPlaceAllowed": False,
        "verifiedStateMutationAllowed": False,
        "candidateToCatalogRecordMutationAllowed": False,
        "replacementPolicy": "new_versioned_profile_and_candidate_required_for_any_schema_or_value_change",
        "nextProfilePathPattern": "^docs/v1/g0/external-evidence-candidate-profile-v[2-9][0-9]*\\.json$",
    }


def _validated_decision_constraints(
    decision_raw: bytes,
    failures: list[str],
) -> dict[str, object]:
    document = receipt._parse_object(decision_raw, "G0 decision source", failures)
    if document is None:
        return {}
    receipt._validate_json_resources(
        document,
        failures,
        root_label="G0 decision source",
        maximum_depth=32,
        maximum_items=512,
        maximum_string_bytes=4_096,
    )
    _require_exact(
        _sha256(decision_raw),
        EXPECTED_DECISION_RAW_SHA256,
        "G0 decision source raw SHA-256",
        failures,
    )
    _require_exact(
        decision.canonical_json_sha256(document),
        decision.EXPECTED_DECISION_CANONICAL_SHA256,
        "G0 decision source canonical SHA-256",
        failures,
    )
    for field, expected in (
        ("documentType", "aetherlink.v1-g0-decision"),
        ("schemaVersion", "1.0"),
        ("decisionId", "aetherlink_v1_g0_decision_v1"),
    ):
        _require_exact(document.get(field), expected, f"G0 decision source.{field}", failures)

    release = document.get("releasePolicy")
    product = document.get("productScope")
    operations = document.get("operationsAndPrivacy")
    quality = document.get("qualityGates")
    if not all(isinstance(value, dict) for value in (release, product, operations, quality)):
        failures.append("G0 decision source constraints are unavailable")
        return {}
    android = release.get("android")
    macos = release.get("macos")
    providers = product.get("providers")
    if not isinstance(android, dict) or not isinstance(macos, dict) or not isinstance(providers, list):
        failures.append("G0 decision source platform/provider constraints are unavailable")
        return {}
    provider_ids = tuple(
        entry.get("id") for entry in providers if isinstance(entry, dict)
    )
    if not provider_ids or not all(isinstance(value, str) for value in provider_ids):
        failures.append("G0 decision source provider order is unavailable")
    capacity_rule = quality.get("capacityRule")
    _require_exact(
        capacity_rule,
        "pass_at_two_times_the_approved_projected_peak_without_unbounded_growth_or_weaker_admission",
        "G0 decision source capacity rule",
        failures,
    )
    return {
        "platformChannels": (
            ("android", android.get("channel")),
            ("macos", macos.get("channel")),
        ),
        "currentApplicationIds": {
            "android": android.get("currentApplicationId"),
            "macos": macos.get("currentBundleId"),
        },
        "providerIds": provider_ids,
        "retentionSchedule": {
            "aggregateOperationalMetricsDays": operations.get(
                "aggregateOperationalMetricsRetentionDays"
            ),
            "sourceFreeSecurityEventsDays": operations.get(
                "sourceFreeSecurityEventRetentionDays"
            ),
            "sanitizedIncidentEvidenceDays": operations.get(
                "sanitizedIncidentEvidenceRetentionDays"
            ),
            "contentFreeReleaseRecordsDays": operations.get(
                "contentFreeReleaseRecordRetentionDays"
            ),
        },
        "initialRegionCount": operations.get("initialRegionCount"),
        "capacityMultiplierBasisPoints": 20_000,
    }


def collect_external_evidence_profile_failures(
    profile_bytes: object,
    *,
    lineage_blobs: object,
    decision_bytes: object,
    baseline_profile_bytes: object,
    supporting_profile_bytes: object,
    owner_catalog_input_bytes: object,
) -> tuple[str, ...]:
    """Validate the supplied profile and effective V3 mapping without I/O."""

    failures: list[str] = []
    profile_raw = receipt._bounded_snapshot(
        profile_bytes,
        "G0 external evidence profile",
        MAX_PROFILE_BYTES,
        failures,
    )
    decision_raw = receipt._bounded_snapshot(
        decision_bytes,
        "G0 decision source",
        MAX_DECISION_BYTES,
        failures,
    )
    baseline_raw = receipt._bounded_snapshot(
        baseline_profile_bytes,
        "G0 baseline evidence readiness profile",
        baseline.MAX_PROFILE_BYTES,
        failures,
    )
    supporting_raw = receipt._bounded_snapshot(
        supporting_profile_bytes,
        "G0 supporting evidence profile",
        receipt.MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
        failures,
    )
    owner_catalog_raw = receipt._bounded_snapshot(
        owner_catalog_input_bytes,
        "G0 owner/catalog input",
        receipt.MAX_OWNER_CATALOG_INPUT_BYTES,
        failures,
    )
    immutable_lineage = receipt._snapshot_validated_v3_lineage(
        lineage_blobs,
        label="G0 external evidence profile lineage",
        failures=failures,
    )
    profile = (
        receipt._parse_object(profile_raw, "G0 external evidence profile", failures)
        if profile_raw is not None
        else None
    )
    baseline_profile = (
        receipt._parse_object(baseline_raw, "G0 baseline evidence readiness profile", failures)
        if baseline_raw is not None
        else None
    )
    supporting_profile = (
        receipt._parse_object(supporting_raw, "G0 supporting evidence profile", failures)
        if supporting_raw is not None
        else None
    )
    owner_catalog = (
        receipt._parse_object(owner_catalog_raw, "G0 owner/catalog input", failures)
        if owner_catalog_raw is not None
        else None
    )
    if (
        profile is None
        or decision_raw is None
        or baseline_profile is None
        or supporting_profile is None
        or owner_catalog is None
        or immutable_lineage is None
    ):
        return tuple(failures)

    _validated_decision_constraints(decision_raw, failures)

    failures.extend(
        baseline.collect_baseline_evidence_readiness_profile_failures(
            baseline_raw,
            lineage_blobs=immutable_lineage,
        )
    )
    failures.extend(
        receipt._collect_evidence_supporting_artifact_profile_failures(
            supporting_raw,
            owner_catalog_input_bytes=owner_catalog_raw,
        )
    )
    owner_catalog_failures = receipt._collect_owner_catalog_input_candidate_failures(
        owner_catalog_raw,
        lineage_blobs=immutable_lineage,
    )
    if owner_catalog_failures != (receipt.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,):
        failures.extend(
            failure
            for failure in owner_catalog_failures
            if failure != receipt.OWNER_CATALOG_INPUT_DORMANT_MESSAGE
        )
        if not any(
            failure != receipt.OWNER_CATALOG_INPUT_DORMANT_MESSAGE
            for failure in owner_catalog_failures
        ):
            failures.append("owner/catalog input did not retain the exact dormant result")
    receipt._validate_json_resources(
        profile,
        failures,
        root_label="G0 external evidence profile",
        maximum_depth=MAX_JSON_DEPTH,
        maximum_items=MAX_JSON_ITEMS,
        maximum_string_bytes=MAX_STRING_BYTES,
    )
    root = receipt._exact_ordered_object(
        profile,
        PROFILE_FIELDS,
        "G0 external evidence profile",
        failures,
    )
    for field, expected in (
        ("documentType", "aetherlink.v1-g0-external-evidence-candidate-profile"),
        ("schemaVersion", 1),
        ("profileId", "aetherlink_v1_g0_external_evidence_candidate_profile_v1"),
        ("status", "draft_prepared_unselected_unverified_non_authorizing"),
    ):
        _require_exact(root.get(field), expected, f"profile.{field}", failures)

    effective_v3 = receipt._materialize_effective_v3(immutable_lineage, failures)
    if not isinstance(effective_v3, dict):
        failures.append("effective V3 assurance is unavailable")
        return tuple(failures)
    mapping, non_derived, existing, remaining = _derive_contract(
        effective_v3,
        baseline_profile,
        supporting_profile,
        owner_catalog,
        failures,
    )
    expected_contract = _expected_contract(mapping, non_derived, existing)
    contract = receipt._exact_ordered_object(
        root.get("contractBinding"), CONTRACT_FIELDS, "profile.contractBinding", failures
    )
    _require_exact(contract, expected_contract, "profile.contractBinding", failures)
    coverage = receipt._exact_ordered_object(
        root.get("coverageDerivation"),
        COVERAGE_FIELDS,
        "profile.coverageDerivation",
        failures,
    )
    decision_ref = receipt._exact_ordered_object(
        coverage.get("decisionRef"),
        DECISION_REF_FIELDS,
        "profile.coverageDerivation.decisionRef",
        failures,
    )
    baseline_ref = receipt._exact_ordered_object(
        coverage.get("baselineProfileRef"),
        COVERAGE_REF_FIELDS,
        "profile.coverageDerivation.baselineProfileRef",
        failures,
    )
    supporting_ref = receipt._exact_ordered_object(
        coverage.get("supportingProfileRef"),
        COVERAGE_REF_FIELDS,
        "profile.coverageDerivation.supportingProfileRef",
        failures,
    )
    owner_ref = receipt._exact_ordered_object(
        coverage.get("ownerCatalogInputRef"),
        OWNER_CATALOG_REF_FIELDS,
        "profile.coverageDerivation.ownerCatalogInputRef",
        failures,
    )
    _ = (decision_ref, baseline_ref, supporting_ref, owner_ref)
    _require_exact(
        coverage,
        _expected_coverage_derivation(non_derived, existing, remaining),
        "profile.coverageDerivation",
        failures,
    )

    artifact_paths = root.get("artifactPaths")
    expected_paths = [
        {"evidenceKind": kind, "candidateVersion": 1, "path": ARTIFACT_PATHS[kind]}
        for kind in remaining
    ]
    if not isinstance(artifact_paths, list):
        failures.append("profile.artifactPaths must be a list")
    else:
        for index, item in enumerate(artifact_paths):
            receipt._exact_ordered_object(
                item, ARTIFACT_PATH_FIELDS, f"profile.artifactPaths[{index}]", failures
            )
        _require_exact(artifact_paths, expected_paths, "profile.artifactPaths", failures)

    evidence_profiles = root.get("evidenceProfiles")
    expected_profiles = _expected_evidence_profiles(mapping)
    if not isinstance(evidence_profiles, list):
        failures.append("profile.evidenceProfiles must be a list")
    else:
        for index, item in enumerate(evidence_profiles):
            profile_item = receipt._exact_ordered_object(
                item,
                EVIDENCE_PROFILE_FIELDS,
                f"profile.evidenceProfiles[{index}]",
                failures,
            )
            nested = profile_item.get("nestedFieldProfiles")
            if not isinstance(nested, list):
                failures.append(
                    f"profile.evidenceProfiles[{index}].nestedFieldProfiles must be a list"
                )
            else:
                for nested_index, nested_item in enumerate(nested):
                    receipt._exact_ordered_object(
                        nested_item,
                        NESTED_FIELD_PROFILE_FIELDS,
                        f"profile.evidenceProfiles[{index}].nestedFieldProfiles[{nested_index}]",
                        failures,
                    )
        _require_exact(evidence_profiles, expected_profiles, "profile.evidenceProfiles", failures)

    common = receipt._exact_ordered_object(
        root.get("commonEnvelopeProfile"),
        COMMON_PROFILE_FIELDS,
        "profile.commonEnvelopeProfile",
        failures,
    )
    _require_exact(common, _expected_common_profile(), "profile.commonEnvelopeProfile", failures)
    readiness = receipt._exact_ordered_object(
        root.get("readinessPlanProfile"),
        READINESS_PLAN_PROFILE_FIELDS,
        "profile.readinessPlanProfile",
        failures,
    )
    _require_exact(readiness, _expected_readiness_plan_profile(), "profile.readinessPlanProfile", failures)
    resources = receipt._exact_ordered_object(
        root.get("resourceBounds"), RESOURCE_FIELDS, "profile.resourceBounds", failures
    )
    _require_exact(resources, _expected_resource_bounds(), "profile.resourceBounds", failures)
    sensitive = receipt._exact_ordered_object(
        root.get("sensitiveDataPolicy"),
        SENSITIVE_POLICY_FIELDS,
        "profile.sensitiveDataPolicy",
        failures,
    )
    _require_exact(sensitive, _expected_sensitive_policy(), "profile.sensitiveDataPolicy", failures)
    boundary = receipt._exact_ordered_object(
        root.get("authorizationBoundary"),
        AUTHORIZATION_FIELDS,
        "profile.authorizationBoundary",
        failures,
    )
    _require_exact(boundary, _expected_authorization_boundary(), "profile.authorizationBoundary", failures)
    supersession = receipt._exact_ordered_object(
        root.get("supersessionPolicy"),
        SUPERSESSION_FIELDS,
        "profile.supersessionPolicy",
        failures,
    )
    _require_exact(supersession, _expected_supersession_policy(), "profile.supersessionPolicy", failures)

    if profile_raw is not None:
        _require_exact(
            _sha256(profile_raw),
            EXPECTED_PROFILE_RAW_SHA256,
            "recorded external evidence profile raw SHA-256",
            failures,
        )
    return tuple(failures)


def compile_dormant_external_evidence_readiness_plan(
    profile_bytes: object,
    *,
    lineage_blobs: object,
    decision_bytes: object,
    baseline_profile_bytes: object,
    supporting_profile_bytes: object,
    owner_catalog_input_bytes: object,
) -> tuple[bytes, str]:
    """Compile an in-memory absence plan; never create an evidence artifact."""

    profile_snapshot_failures: list[str] = []
    profile_raw = receipt._bounded_snapshot(
        profile_bytes,
        "G0 external evidence readiness profile",
        MAX_PROFILE_BYTES,
        profile_snapshot_failures,
    )
    decision_raw = receipt._bounded_snapshot(
        decision_bytes,
        "G0 decision source",
        MAX_DECISION_BYTES,
        profile_snapshot_failures,
    )
    baseline_raw = receipt._bounded_snapshot(
        baseline_profile_bytes,
        "G0 baseline evidence readiness profile",
        baseline.MAX_PROFILE_BYTES,
        profile_snapshot_failures,
    )
    supporting_raw = receipt._bounded_snapshot(
        supporting_profile_bytes,
        "G0 supporting evidence profile",
        receipt.MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
        profile_snapshot_failures,
    )
    owner_catalog_raw = receipt._bounded_snapshot(
        owner_catalog_input_bytes,
        "G0 owner/catalog input",
        receipt.MAX_OWNER_CATALOG_INPUT_BYTES,
        profile_snapshot_failures,
    )
    lineage_snapshots = receipt._snapshot_validated_v3_lineage(
        lineage_blobs,
        label="G0 external evidence readiness lineage",
        failures=profile_snapshot_failures,
    )
    if (
        profile_raw is None
        or decision_raw is None
        or baseline_raw is None
        or supporting_raw is None
        or owner_catalog_raw is None
        or lineage_snapshots is None
        or profile_snapshot_failures
    ):
        raise ValueError(
            "external evidence readiness inputs are invalid: "
            + "; ".join(profile_snapshot_failures)
        )
    profile_failures = collect_external_evidence_profile_failures(
        profile_raw,
        lineage_blobs=lineage_snapshots,
        decision_bytes=decision_raw,
        baseline_profile_bytes=baseline_raw,
        supporting_profile_bytes=supporting_raw,
        owner_catalog_input_bytes=owner_catalog_raw,
    )
    if profile_failures:
        raise ValueError("external evidence profile is invalid: " + "; ".join(profile_failures))
    profile = json.loads(profile_raw)
    plan = {
        "documentType": "aetherlink.v1-g0-external-evidence-readiness-plan",
        "schemaVersion": 1,
        "planId": "aetherlink_v1_g0_external_evidence_readiness_plan_v1",
        "status": "prepared_unselected_unverified_non_authorizing",
        "profileRef": {
            "path": PROFILE_PATH,
            "profileId": profile["profileId"],
            "rawSha256": EXPECTED_PROFILE_RAW_SHA256,
        },
        "contractBinding": profile["contractBinding"],
        "candidateArtifactReservations": [
            {
                "evidenceKind": item["evidenceKind"],
                "blockerId": evidence_profile["blockerId"],
                "requiredOwnerRoles": evidence_profile["requiredOwnerRoles"],
                "path": item["path"],
                "artifactPresent": False,
                "externalValuesSelected": False,
                "acquisitionAuthorized": False,
            }
            for item, evidence_profile in zip(
                profile["artifactPaths"], profile["evidenceProfiles"]
            )
        ],
        "state": {field: False for field in STATE_FIELDS},
    }
    raw = _canonical_bytes(plan)
    if len(raw) > MAX_CANDIDATE_BYTES:
        raise ValueError("external evidence readiness plan exceeds the candidate byte bound")
    return raw, _sha256(raw)


def _validate_reference_list(
    value: object,
    label: str,
    failures: list[str],
    *,
    minimum: int = 1,
    maximum: int = 8,
) -> None:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        failures.append(f"{label} must contain {minimum}..{maximum} references")
        return
    if len(value) != len(set(item for item in value if isinstance(item, str))):
        failures.append(f"{label} references must be unique")
    for index, item in enumerate(value):
        _require_reference(item, f"{label}[{index}]", failures)


def _validate_application_ids(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    platform_channels = constraints.get("platformChannels")
    if not isinstance(platform_channels, tuple):
        failures.append("decision-derived platform channels are unavailable")
        platform_channels = ()
    entries = payload.get("applicationIds")
    if not isinstance(entries, list) or len(entries) != len(platform_channels):
        failures.append("owned application IDs must contain exactly Android then macOS")
        entries = []
    current_ids = constraints.get("currentApplicationIds")
    if not isinstance(current_ids, dict):
        failures.append("decision-derived current application IDs are unavailable")
        current_ids = {}
    for index, (platform, channel) in enumerate(platform_channels):
        entry = receipt._exact_ordered_object(
            entries[index] if index < len(entries) else None,
            APPLICATION_ID_ENTRY_FIELDS,
            f"application ID entry {index}",
            failures,
        )
        _require_exact(entry.get("platform"), platform, f"application ID entry {index}.platform", failures)
        _require_exact(entry.get("distributionChannel"), channel, f"application ID entry {index}.distributionChannel", failures)
        _require_pattern(entry.get("identifier"), APPLICATION_ID_PATTERN, f"application ID entry {index}.identifier", failures)
        if entry.get("identifier") == current_ids[platform]:
            failures.append(f"application ID entry {index}.identifier must be a distinct production identifier")
        _require_reference(entry.get("ownershipRecordRefCandidate"), f"application ID entry {index}.ownershipRecordRefCandidate", failures)
    _require_reference(payload.get("versionPolicyRefCandidate"), "owned application IDs versionPolicyRefCandidate", failures)
    _require_reference(payload.get("migrationPolicyRefCandidate"), "owned application IDs migrationPolicyRefCandidate", failures)


def _validate_distribution_accounts(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    platform_channels = constraints.get("platformChannels")
    if not isinstance(platform_channels, tuple):
        failures.append("decision-derived platform channels are unavailable")
        platform_channels = ()
    entries = payload.get("accounts")
    if not isinstance(entries, list) or len(entries) != len(platform_channels):
        failures.append("distribution accounts must contain exactly Android then macOS")
        entries = []
    for index, (platform, channel) in enumerate(platform_channels):
        entry = receipt._exact_ordered_object(
            entries[index] if index < len(entries) else None,
            DISTRIBUTION_ACCOUNT_ENTRY_FIELDS,
            f"distribution account entry {index}",
            failures,
        )
        _require_exact(entry.get("platform"), platform, f"distribution account entry {index}.platform", failures)
        _require_exact(entry.get("distributionChannel"), channel, f"distribution account entry {index}.distributionChannel", failures)
        _require_reference(entry.get("accountOrganizationRefCandidate"), f"distribution account entry {index}.accountOrganizationRefCandidate", failures)
        _require_reference(entry.get("accountControlEvidenceRefCandidate"), f"distribution account entry {index}.accountControlEvidenceRefCandidate", failures)
    _require_reference(payload.get("accessControlRunbookRefCandidate"), "distribution accounts accessControlRunbookRefCandidate", failures)
    _require_reference(payload.get("recoveryRunbookRefCandidate"), "distribution accounts recoveryRunbookRefCandidate", failures)


def _validate_key_custody(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    _ = constraints
    entries = payload.get("keyClasses")
    if not isinstance(entries, list) or len(entries) != len(KEY_PURPOSES):
        failures.append("key custody must contain exactly four required key purposes")
        entries = []
    for index, purpose in enumerate(KEY_PURPOSES):
        entry = receipt._exact_ordered_object(
            entries[index] if index < len(entries) else None,
            KEY_CLASS_ENTRY_FIELDS,
            f"key class entry {index}",
            failures,
        )
        _require_exact(entry.get("keyPurpose"), purpose, f"key class entry {index}.keyPurpose", failures)
        if entry.get("custodyClass") not in CUSTODY_CLASSES:
            failures.append(f"key class entry {index}.custodyClass is not in the closed set")
        for field in KEY_CLASS_ENTRY_FIELDS[2:]:
            _require_reference(entry.get(field), f"key class entry {index}.{field}", failures)
    _require_reference(payload.get("custodyRunbookRefCandidate"), "key custody custodyRunbookRefCandidate", failures)
    _require_reference(payload.get("separationOfDutiesPolicyRefCandidate"), "key custody separationOfDutiesPolicyRefCandidate", failures)


def _validate_provider_matrix(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    _require_reference(payload.get("matrixRevisionRefCandidate"), "provider matrix matrixRevisionRefCandidate", failures)
    provider_ids = constraints.get("providerIds")
    if not isinstance(provider_ids, tuple):
        failures.append("decision-derived provider order is unavailable")
        provider_ids = ()
    entries = payload.get("providers")
    if not isinstance(entries, list) or len(entries) != len(provider_ids):
        failures.append("provider matrix must contain exactly Ollama then LM Studio")
        entries = []
    for index, provider in enumerate(provider_ids):
        entry = receipt._exact_ordered_object(
            entries[index] if index < len(entries) else None,
            PROVIDER_ENTRY_FIELDS,
            f"provider matrix entry {index}",
            failures,
        )
        _require_exact(entry.get("providerId"), provider, f"provider matrix entry {index}.providerId", failures)
        versions = []
        for field in ("minimumCandidateVersion", "currentCandidateVersion", "previousCandidateVersion"):
            value = entry.get(field)
            _require_pattern(value, VERSION_PATTERN, f"provider matrix entry {index}.{field}", failures)
            if isinstance(value, str):
                versions.append(value)
        if len(versions) == 3 and len(set(versions)) != 3:
            failures.append(f"provider matrix entry {index} versions must be distinct")
        _require_reference(entry.get("compatibilityProfileRefCandidate"), f"provider matrix entry {index}.compatibilityProfileRefCandidate", failures)
        _validate_reference_list(entry.get("evidenceRefCandidates"), f"provider matrix entry {index}.evidenceRefCandidates", failures, minimum=2)
    _require_reference(payload.get("testPolicyRefCandidate"), "provider matrix testPolicyRefCandidate", failures)


def _validate_service_domains(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    _ = constraints
    entries = payload.get("services")
    if not isinstance(entries, list) or len(entries) != len(SERVICE_ROLES):
        failures.append("service domains must contain all four production service roles")
        entries = []
    for index, service_role in enumerate(SERVICE_ROLES):
        entry = receipt._exact_ordered_object(
            entries[index] if index < len(entries) else None,
            SERVICE_DOMAIN_ENTRY_FIELDS,
            f"service domain entry {index}",
            failures,
        )
        _require_exact(entry.get("serviceRole"), service_role, f"service domain entry {index}.serviceRole", failures)
        _require_pattern(entry.get("domainName"), DOMAIN_PATTERN, f"service domain entry {index}.domainName", failures)
        for field in SERVICE_DOMAIN_ENTRY_FIELDS[2:]:
            _require_reference(entry.get(field), f"service domain entry {index}.{field}", failures)
    _require_reference(payload.get("lifecycleRunbookRefCandidate"), "service domains lifecycleRunbookRefCandidate", failures)


def _validate_root_signer(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    _ = constraints
    entries = payload.get("custodyAssignments")
    if not isinstance(entries, list) or len(entries) != len(CUSTODY_RESPONSIBILITIES):
        failures.append("root signer evidence must contain three custody responsibilities")
        entries = []
    for index, responsibility in enumerate(CUSTODY_RESPONSIBILITIES):
        entry = receipt._exact_ordered_object(
            entries[index] if index < len(entries) else None,
            CUSTODY_ASSIGNMENT_ENTRY_FIELDS,
            f"custody assignment entry {index}",
            failures,
        )
        _require_exact(entry.get("responsibility"), responsibility, f"custody assignment entry {index}.responsibility", failures)
        _require_reference(entry.get("assignmentRecordRefCandidate"), f"custody assignment entry {index}.assignmentRecordRefCandidate", failures)
        _require_reference(entry.get("custodyProfileRefCandidate"), f"custody assignment entry {index}.custodyProfileRefCandidate", failures)
    _require_int(payload.get("rotationOverlapSeconds"), 1, 31_536_000, "root signer rotationOverlapSeconds", failures)
    for field in ROOT_SIGNER_PAYLOAD_FIELDS[2:]:
        _require_reference(payload.get(field), f"root signer {field}", failures)


def _validate_privacy(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    _require_reference(payload.get("privacyPolicyRefCandidate"), "privacy privacyPolicyRefCandidate", failures)
    retention = receipt._exact_ordered_object(
        payload.get("retentionSchedule"),
        RETENTION_SCHEDULE_FIELDS,
        "privacy retentionSchedule",
        failures,
    )
    _require_exact(
        retention,
        constraints.get("retentionSchedule"),
        "privacy retentionSchedule",
        failures,
    )
    for field in PRIVACY_PAYLOAD_FIELDS[2:]:
        _require_reference(payload.get(field), f"privacy {field}", failures)


def _validate_relay_budget(
    payload: dict[str, object],
    constraints: dict[str, object],
    failures: list[str],
) -> None:
    regions = payload.get("regions")
    initial_region_count = constraints.get("initialRegionCount")
    if type(initial_region_count) is not int or not 1 <= initial_region_count <= 8:
        failures.append("decision-derived initial region count is unavailable")
        initial_region_count = 0
    if not isinstance(regions, list) or len(regions) != initial_region_count:
        failures.append("relay budget must contain exactly one initial region")
        regions = []
    entry = receipt._exact_ordered_object(
        regions[0] if regions else None,
        REGION_ENTRY_FIELDS,
        "relay region entry 0",
        failures,
    )
    _require_pattern(entry.get("regionCode"), REGION_PATTERN, "relay region entry 0.regionCode", failures)
    _require_reference(entry.get("providerRegionRefCandidate"), "relay region entry 0.providerRegionRefCandidate", failures)
    _require_int(payload.get("projectedPeakConcurrentSessions"), 1, 1_000_000_000, "relay projectedPeakConcurrentSessions", failures)
    _require_exact(
        payload.get("requiredCapacityMultiplierBasisPoints"),
        constraints.get("capacityMultiplierBasisPoints"),
        "relay requiredCapacityMultiplierBasisPoints",
        failures,
    )
    _require_int(payload.get("monthlyCostCeilingMinorUnits"), 1, 999_999_999_999, "relay monthlyCostCeilingMinorUnits", failures)
    _require_pattern(payload.get("currency"), CURRENCY_PATTERN, "relay currency", failures)
    for field in RELAY_BUDGET_PAYLOAD_FIELDS[5:]:
        _require_reference(payload.get(field), f"relay {field}", failures)


PAYLOAD_VALIDATORS = {
    "owned_application_ids": _validate_application_ids,
    "distribution_accounts": _validate_distribution_accounts,
    "key_custody_runbook": _validate_key_custody,
    "approved_minimum_current_previous_matrix": _validate_provider_matrix,
    "domain_dns_webpki_owners": _validate_service_domains,
    "root_signer_rotation_and_revocation_owners": _validate_root_signer,
    "privacy_incident_and_retention_owner_approval": _validate_privacy,
    "approved_region_peak_capacity_and_cost_ceiling": _validate_relay_budget,
}


def collect_external_evidence_candidate_failures(
    candidate_bytes: object,
    *,
    profile_bytes: object,
    lineage_blobs: object,
    decision_bytes: object,
    baseline_profile_bytes: object,
    supporting_profile_bytes: object,
    owner_catalog_input_bytes: object,
) -> tuple[str, ...]:
    """Validate one supplied candidate while always retaining dormant status."""

    failures: list[str] = []
    candidate_raw = receipt._bounded_snapshot(
        candidate_bytes,
        "G0 external evidence candidate",
        MAX_CANDIDATE_BYTES,
        failures,
    )
    profile_raw = receipt._bounded_snapshot(
        profile_bytes,
        "G0 external evidence profile",
        MAX_PROFILE_BYTES,
        failures,
    )
    decision_raw = receipt._bounded_snapshot(
        decision_bytes,
        "G0 decision source",
        MAX_DECISION_BYTES,
        failures,
    )
    baseline_raw = receipt._bounded_snapshot(
        baseline_profile_bytes,
        "G0 baseline evidence readiness profile",
        baseline.MAX_PROFILE_BYTES,
        failures,
    )
    supporting_raw = receipt._bounded_snapshot(
        supporting_profile_bytes,
        "G0 supporting evidence profile",
        receipt.MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
        failures,
    )
    owner_catalog_raw = receipt._bounded_snapshot(
        owner_catalog_input_bytes,
        "G0 owner/catalog input",
        receipt.MAX_OWNER_CATALOG_INPUT_BYTES,
        failures,
    )
    lineage_snapshots = receipt._snapshot_validated_v3_lineage(
        lineage_blobs,
        label="G0 external evidence candidate lineage",
        failures=failures,
    )
    if (
        candidate_raw is None
        or profile_raw is None
        or decision_raw is None
        or baseline_raw is None
        or supporting_raw is None
        or owner_catalog_raw is None
        or lineage_snapshots is None
    ):
        if DORMANT_MESSAGE not in failures:
            failures.append(DORMANT_MESSAGE)
        return tuple(failures)
    profile_failures = collect_external_evidence_profile_failures(
        profile_raw,
        lineage_blobs=lineage_snapshots,
        decision_bytes=decision_raw,
        baseline_profile_bytes=baseline_raw,
        supporting_profile_bytes=supporting_raw,
        owner_catalog_input_bytes=owner_catalog_raw,
    )
    if profile_failures:
        failures.extend(profile_failures)
        if DORMANT_MESSAGE not in failures:
            failures.append(DORMANT_MESSAGE)
        return tuple(failures)
    profile = json.loads(profile_raw)
    decision_constraints_failures: list[str] = []
    decision_constraints = _validated_decision_constraints(
        decision_raw,
        decision_constraints_failures,
    )
    failures.extend(decision_constraints_failures)
    candidate = receipt._parse_object(candidate_raw, "G0 external evidence candidate", failures)
    if candidate is None:
        if DORMANT_MESSAGE not in failures:
            failures.append(DORMANT_MESSAGE)
        return tuple(failures)
    receipt._validate_json_resources(
        candidate,
        failures,
        root_label="G0 external evidence candidate",
        maximum_depth=MAX_JSON_DEPTH,
        maximum_items=MAX_JSON_ITEMS,
        maximum_string_bytes=MAX_STRING_BYTES,
    )
    try:
        canonical = _canonical_bytes(candidate)
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        failures.append(f"external evidence candidate cannot be canonicalized: {error}")
        canonical = b""
    if candidate_raw != canonical:
        failures.append("external evidence candidate bytes are not exact compact UTF-8 JSON")

    root = receipt._exact_ordered_object(
        candidate,
        CANDIDATE_FIELDS,
        "G0 external evidence candidate",
        failures,
    )
    for field, expected in profile["commonEnvelopeProfile"]["fixedValues"].items():
        _require_exact(root.get(field), expected, f"candidate.{field}", failures)
    kind = root.get("evidenceKind")
    profile_by_kind = {item["evidenceKind"]: item for item in profile["evidenceProfiles"]}
    kind_profile = profile_by_kind.get(kind)
    if not isinstance(kind, str) or kind_profile is None:
        failures.append("candidate.evidenceKind is unsupported")
        kind_profile = {}
    _require_exact(root.get("artifactId"), kind_profile.get("artifactId"), "candidate.artifactId", failures)

    profile_ref = receipt._exact_ordered_object(
        root.get("profileRef"), PROFILE_REF_FIELDS, "candidate.profileRef", failures
    )
    _require_exact(
        profile_ref,
        {"path": PROFILE_PATH, "profileId": profile["profileId"], "rawSha256": EXPECTED_PROFILE_RAW_SHA256},
        "candidate.profileRef",
        failures,
    )
    contract = receipt._exact_ordered_object(
        root.get("contractBinding"),
        CANDIDATE_CONTRACT_FIELDS,
        "candidate.contractBinding",
        failures,
    )
    expected_contract = {
        "repositoryRef": profile["contractBinding"]["repositoryRef"],
        "publicationCommitObjectId": profile["contractBinding"]["publicationCommitObjectId"],
        "publicationCheckpointPath": profile["contractBinding"]["publicationCheckpointPath"],
        "publicationCheckpointRawSha256": profile["contractBinding"]["publicationCheckpointRawSha256"],
        "effectiveAssuranceCanonicalSha256": profile["contractBinding"]["effectiveAssuranceCanonicalSha256"],
        "effectiveClosureCanonicalSha256": profile["contractBinding"]["effectiveClosureCanonicalSha256"],
        "decisionId": profile["contractBinding"]["decisionId"],
        "decisionCanonicalSha256": profile["contractBinding"]["decisionCanonicalSha256"],
        "blockerId": kind_profile.get("blockerId"),
        "requiredCheckIds": kind_profile.get("requiredCheckIds"),
        "requiredOwnerRoles": kind_profile.get("requiredOwnerRoles"),
        "evidenceKind": kind,
    }
    _require_exact(contract, expected_contract, "candidate.contractBinding", failures)

    intake = receipt._exact_ordered_object(
        root.get("intakeBinding"),
        INTAKE_BINDING_FIELDS,
        "candidate.intakeBinding",
        failures,
    )
    expected_intake = {
        "candidateVersion": 1,
        "reservedArtifactPath": kind_profile.get("candidatePath"),
        "selectorState": "not_selected",
        "ownerBindingRefCandidate": None,
        "evidenceInputRefCandidate": None,
        "supportingArtifactPresent": False,
        "supportingArtifactRefCandidate": None,
    }
    _require_exact(intake, expected_intake, "candidate.intakeBinding", failures)

    payload_fields = tuple(kind_profile.get("exactPayloadFields", ()))
    payload = receipt._exact_ordered_object(
        root.get("payload"), payload_fields, "candidate.payload", failures
    )
    validator = PAYLOAD_VALIDATORS.get(kind)
    if validator is not None:
        validator(payload, decision_constraints, failures)

    trust = receipt._exact_ordered_object(
        root.get("trustBoundary"), TRUST_BOUNDARY_FIELDS, "candidate.trustBoundary", failures
    )
    _require_exact(
        trust,
        profile["commonEnvelopeProfile"]["trustBoundaryFixedValues"],
        "candidate.trustBoundary",
        failures,
    )
    state = receipt._exact_ordered_object(
        root.get("state"), STATE_FIELDS, "candidate.state", failures
    )
    _require_exact(
        state,
        profile["commonEnvelopeProfile"]["stateFixedValues"],
        "candidate.state",
        failures,
    )
    if DORMANT_MESSAGE not in failures:
        failures.append(DORMANT_MESSAGE)
    return tuple(failures)


def _collect_absent_candidate_failures(root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    for kind in SUPPORTED_PAYLOAD_KINDS:
        path = root / ARTIFACT_PATHS[kind]
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            failures.append(f"cannot inspect reserved {kind} candidate path: {error}")
        else:
            failures.append(
                f"reserved {kind} candidate artifact must remain absent until external values are selected and reviewed"
            )
    return tuple(failures)


def _collect_worktree_failures(root: Path = ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    lineage: list[bytes] = []
    identities: list[tuple[int, int, int, int, int, int]] = []
    for role, path, maximum in zip(
        receipt.LINEAGE_ROLES, receipt.LINEAGE_PATHS, receipt.LINEAGE_MAXIMUM_BYTES
    ):
        try:
            raw, identity = decision.read_g0_content_addressed_snapshot(
                root, path, f"G0 external evidence lineage {role}", maximum
            )
        except checkpoint.CheckpointValidationError as error:
            failures.append(str(error))
            continue
        lineage.append(raw)
        identities.append(identity)
    try:
        profile_raw, profile_identity = decision.read_g0_content_addressed_snapshot(
            root, PROFILE_PATH, "G0 external evidence profile", MAX_PROFILE_BYTES
        )
    except checkpoint.CheckpointValidationError as error:
        failures.append(str(error))
        return tuple(failures)
    try:
        decision_raw, decision_identity = decision.read_g0_content_addressed_snapshot(
            root,
            DECISION_PATH,
            "G0 decision source",
            MAX_DECISION_BYTES,
        )
    except checkpoint.CheckpointValidationError as error:
        failures.append(str(error))
        return tuple(failures)
    supporting_inputs: list[tuple[str, str, int, str, bytes, tuple[int, int, int, int, int, int]]] = []
    for path, label, maximum, expected_sha in (
        (
            BASELINE_PROFILE_PATH,
            "G0 baseline evidence readiness profile",
            baseline.MAX_PROFILE_BYTES,
            baseline.EXPECTED_PROFILE_RAW_SHA256,
        ),
        (
            SUPPORTING_PROFILE_PATH,
            "G0 supporting evidence profile",
            receipt.MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES,
            receipt.EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256,
        ),
        (
            OWNER_CATALOG_INPUT_PATH,
            "G0 owner/catalog input",
            receipt.MAX_OWNER_CATALOG_INPUT_BYTES,
            receipt.EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        ),
    ):
        try:
            raw, identity = decision.read_g0_content_addressed_snapshot(
                root, path, label, maximum
            )
        except checkpoint.CheckpointValidationError as error:
            failures.append(str(error))
            continue
        supporting_inputs.append((path, label, maximum, expected_sha, raw, identity))
    if failures:
        return tuple(failures)
    baseline_raw = supporting_inputs[0][4]
    supporting_raw = supporting_inputs[1][4]
    owner_catalog_raw = supporting_inputs[2][4]

    profile_failures = collect_external_evidence_profile_failures(
        profile_raw,
        lineage_blobs=tuple(lineage),
        decision_bytes=decision_raw,
        baseline_profile_bytes=baseline_raw,
        supporting_profile_bytes=supporting_raw,
        owner_catalog_input_bytes=owner_catalog_raw,
    )
    failures.extend(profile_failures)
    if not profile_failures:
        try:
            plan_raw, plan_sha256 = compile_dormant_external_evidence_readiness_plan(
                profile_raw,
                lineage_blobs=tuple(lineage),
                decision_bytes=decision_raw,
                baseline_profile_bytes=baseline_raw,
                supporting_profile_bytes=supporting_raw,
                owner_catalog_input_bytes=owner_catalog_raw,
            )
        except ValueError as error:
            failures.append(str(error))
        else:
            _require_exact(len(plan_raw), EXPECTED_PLAN_BYTE_LENGTH, "readiness plan byte length", failures)
            _require_exact(plan_sha256, EXPECTED_PLAN_RAW_SHA256, "readiness plan raw SHA-256", failures)

    failures.extend(_collect_absent_candidate_failures(root))
    for role, path, maximum, identity, expected_sha in zip(
        receipt.LINEAGE_ROLES,
        receipt.LINEAGE_PATHS,
        receipt.LINEAGE_MAXIMUM_BYTES,
        identities,
        receipt.LINEAGE_RAW_SHA256,
    ):
        failures.extend(
            decision.collect_g0_final_snapshot_failures(
                root,
                path,
                f"G0 external evidence lineage {role}",
                maximum,
                identity,
                expected_sha,
            )
        )
    failures.extend(
        decision.collect_g0_final_snapshot_failures(
            root,
            PROFILE_PATH,
            "G0 external evidence profile",
            MAX_PROFILE_BYTES,
            profile_identity,
            EXPECTED_PROFILE_RAW_SHA256,
        )
    )
    failures.extend(
        decision.collect_g0_final_snapshot_failures(
            root,
            DECISION_PATH,
            "G0 decision source",
            MAX_DECISION_BYTES,
            decision_identity,
            EXPECTED_DECISION_RAW_SHA256,
        )
    )
    for path, label, maximum, expected_sha, _, identity in supporting_inputs:
        failures.extend(
            decision.collect_g0_final_snapshot_failures(
                root,
                path,
                label,
                maximum,
                identity,
                expected_sha,
            )
        )
    failures.extend(_collect_absent_candidate_failures(root))
    return tuple(failures)


def main() -> int:
    failures = _collect_worktree_failures()
    if failures:
        for failure in failures:
            print(f"V1 G0 external evidence readiness validation failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 external evidence profile exactly derives the remaining eight "
        "non-derived kinds from effective V3, completing typed readiness for "
        "15/15 kinds. All eight candidate artifacts remain absent; no external "
        "value, owner authentication, verification, receipt, G0 exit, or G1a "
        "authority was created."
    )
    return 0


__all__ = (
    "DORMANT_MESSAGE",
    "EXPECTED_REMAINING_EVIDENCE_COUNT",
    "PROFILE_PATH",
    "collect_external_evidence_candidate_failures",
    "collect_external_evidence_profile_failures",
    "compile_dormant_external_evidence_readiness_plan",
)


if __name__ == "__main__":
    raise SystemExit(main())
