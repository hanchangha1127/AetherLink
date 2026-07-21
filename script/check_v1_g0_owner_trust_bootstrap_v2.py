#!/usr/bin/env python3
"""Validate the non-authorizing G0 owner trust bootstrap v2 candidate.

The pure validator consumes supplied bytes only. It records a user-selected
GitHub principal and software SSHSIG mechanism, but it never creates, searches
for, loads, or verifies a private key; queries GitHub; chooses a trust anchor;
constructs an adapter result; or derives receipt, G0, or G1a authority.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime as _datetime, timezone as _timezone
import hashlib
import json
from pathlib import Path
import re
import sys

try:
    from script import check_v1_g0_checkpoint as checkpoint
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_owner_trust_bootstrap as bootstrap_v1
    from script import check_v1_g0_receipt_bundle as receipt
except ModuleNotFoundError:
    import check_v1_g0_checkpoint as checkpoint
    import check_v1_g0_decision as decision
    import check_v1_g0_owner_trust_bootstrap as bootstrap_v1
    import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = "docs/v1/g0/owner-trust-bootstrap-profile-v2.json"
MAX_PROFILE_BYTES = 131_072
EXPECTED_PROFILE_RAW_SHA256 = (
    "13a3b3a5097b443620f049ad69663c486810945436e1c484f3a79cc8635c53f3"
)

__all__ = (
    "DORMANT_MESSAGE",
    "PAYLOAD_DORMANT_MESSAGE",
    "EXPECTED_PROFILE_RAW_SHA256",
    "MAX_PROFILE_BYTES",
    "PROFILE_PATH",
    "collect_dormant_owner_trust_payload_failures",
    "collect_owner_trust_bootstrap_v2_failures",
    "main",
)

DORMANT_MESSAGE = (
    "G0 owner trust bootstrap v2 records the unverified user selection of "
    "github:hanchangha1127 as one human principal for fourteen role-scoped "
    "identity candidates and the software ssh-ed25519 SSHSIG candidate, but "
    "no credential, trust anchor, authenticated selector, adapter result, "
    "approval receipt, G0 exit, or G1a authority exists"
)
PAYLOAD_DORMANT_MESSAGE = (
    "G0 owner trust bootstrap v2 supplied registry, revocation, root-statement, "
    "role-envelope, manifest, and sidecar bytes are structurally bound, but no "
    "root or owner signature is verified and no authentication or authority exists"
)

PROFILE_FIELDS = (
    "documentType",
    "schemaVersion",
    "profileId",
    "status",
    "supersedes",
    "contractBinding",
    "sourceDecision",
    "principalCandidate",
    "roleIdentityCandidates",
    "signatureMechanismCandidate",
    "sshsigWireContract",
    "detachedEnvelopeContract",
    "bundleManifestContract",
    "registryAndRevocationContract",
    "trustedTimeContract",
    "replayContract",
    "successorTransitionPolicy",
    "selection",
    "adapterProjection",
    "state",
)
SUPERSEDES_FIELDS = ("profilePath", "profileId", "profileRawSha256")
SOURCE_DECISION_FIELDS = (
    "decisionSource",
    "principalSelectionStatus",
    "credentialPathSelectionStatus",
    "hardwareBackedCredentialAvailable",
    "authorizationEffect",
)
PRINCIPAL_FIELDS = (
    "principalRef",
    "provider",
    "login",
    "declaredPrincipal",
    "immutableUserId",
    "subjectType",
    "status",
    "identitySemantics",
    "humanPrincipalCount",
    "ownerIdentityRefDerivationDomain",
    "roleMappingPolicy",
)
ROLE_IDENTITY_FIELDS = (
    "role",
    "ownerBindingRefCandidate",
    "ownerIdentityRefCandidate",
    "principalRef",
    "receiptRefCandidate",
    "credentialRefCandidate",
)
SIGNATURE_MECHANISM_FIELDS = (
    "mechanismRef",
    "protocol",
    "keyAlgorithm",
    "hardwareBacked",
    "messageHashAlgorithm",
    "namespace",
    "signatureEncoding",
    "canonicalEnvelopeEncoding",
    "keyUsage",
    "softwareKeyProvisioningPolicy",
    "automaticCredentialFallbackAllowed",
    "privateKeyPathAccepted",
    "callerSuppliedPrivateKeyMaterialAllowed",
    "sshAgentEnumerationAllowed",
    "sshAgentUseAllowed",
    "environmentCredentialLookupAllowed",
    "keychainCredentialLookupAllowed",
    "projectDrivenSigningInvocationAllowed",
    "releaseEvidenceKeyReuseAllowed",
    "credentialRefCandidate",
    "publicKeyBlobSha256",
    "openSshPublicKeyFingerprint",
    "trustAnchorRef",
    "proofOfControlStatus",
)
SSHSIG_WIRE_FIELDS = (
    "magic",
    "version",
    "reservedFieldPolicy",
    "outerPublicKeyAlgorithm",
    "embeddedPublicKeyPolicy",
    "signatureAlgorithm",
    "signatureLengthBytes",
    "hashAlgorithm",
    "namespace",
    "sshCertificatesAllowed",
    "securityKeyAlgorithmsAllowed",
    "rsaOrEcdsaAlgorithmsAllowed",
    "armorPolicy",
    "armorLineLengthCharacters",
    "armorNewlinePolicy",
)
DETACHED_ENVELOPE_FIELDS = (
    "documentType",
    "schemaVersion",
    "domain",
    "exactFields",
    "receiptMutationAllowed",
    "receiptRawBytePolicy",
    "receiptCanonicalFieldCount",
    "receiptDigestAlgorithm",
    "perRoleEnvelopeRequired",
    "perRoleSignatureRequired",
    "requiredRoleCount",
    "nonceBytes",
    "challengeTtlSeconds",
    "maximumClockSkewSeconds",
    "exactFieldListPolicy",
    "canonicalSerializationPolicy",
    "credentialBindingPolicy",
    "challengeIssuerPolicy",
    "nonceEncodingPolicy",
    "timestampPolicy",
    "bundleManifestPolicy",
    "unknownFieldPolicy",
)
BUNDLE_MANIFEST_FIELDS = (
    "documentType",
    "schemaVersion",
    "domain",
    "exactFields",
    "roleEntryExactFields",
    "canonicalEncoding",
    "digestAlgorithm",
    "roleOrderPolicy",
    "roleCardinality",
    "duplicateOrPartialRoleEntryPolicy",
)
REGISTRY_FIELDS = (
    "registryRootStatus",
    "githubAccountSnapshotRole",
    "canonicalEncoding",
    "digestAlgorithm",
    "maximumSnapshotBytes",
    "maximumDepth",
    "maximumArrayItems",
    "maximumStringBytes",
    "canonicalUint64Pattern",
    "registrySnapshotContract",
    "revocationSnapshotContract",
    "offlineRootSignatureStatementContract",
    "offlineRootSelectors",
    "privateRootBoundary",
    "pairBindingPolicy",
    "digestEqualityPolicy",
    "revisionPolicy",
    "highWatermarkPolicy",
    "ownerMappingPolicy",
    "keySeparationPolicy",
    "revocationEvaluationPolicy",
    "unknownCompromiseTimePolicy",
    "availabilityPolicy",
    "normalDelegateRotationPolicy",
    "rootCompromisePolicy",
)
TRUSTED_TIME_FIELDS = (
    "standard",
    "providerSelectionStatus",
    "tsaProviderRef",
    "tsaTrustAnchorRef",
    "timeUse",
    "mayProveLatestRegistryRevision",
    "maySubstituteForReplayLedger",
    "manifestCoveragePolicy",
    "tokenValidationPolicy",
    "availabilityPolicy",
)
REPLAY_FIELDS = (
    "ledgerStatus",
    "ledgerNamespace",
    "coordinatorStatus",
    "externalConsumedBundleLedgerRequiredBeforeActivation",
    "atomicRoleCoverageCount",
    "consumeKeyFields",
    "partialConsumptionAllowed",
    "idempotentExactRetryMayReturnPriorResult",
    "rollbackDetectionRequired",
    "atomicCompareAndSetPolicy",
    "crashRecoveryPolicy",
    "backupRestorePolicy",
    "ledgerUnavailablePolicy",
)
SUCCESSOR_TRANSITION_FIELDS = (
    "currentCandidateMayAuthenticate",
    "currentCandidateMaySelectOperationalSelectors",
    "nonNullSelectorPrerequisites",
    "selfAssertedTrustAnchorAllowed",
    "githubPublishedKeyAsSoleTrustAnchorAllowed",
    "cachedRegistryOrLocalClockFallbackAllowed",
    "statefulActivationPrerequisite",
    "failurePolicy",
)
ADAPTER_FIELDS = (
    "independentTrustInput",
    "verifiedSubjectFields",
    "dormantSidecarDocumentType",
    "dormantSidecarSchemaVersion",
    "dormantSidecarExactFields",
    "dormantRoleResultExactFields",
    "dormantSidecarStatus",
    "mayCreateDormantSidecar",
    "integrationStatus",
    "genericCandidateFactoryMaySubstitute",
    "mayCreateAdapterResult",
)
REGISTRY_SNAPSHOT_FIELDS = (
    "documentType",
    "schemaVersion",
    "registrySnapshotRef",
    "registryId",
    "revision",
    "previousRegistrySnapshotSha256",
    "issuedAt",
    "expiresAt",
    "principalMappings",
    "credentialRecords",
)
PRINCIPAL_MAPPING_FIELDS = (
    "ownerBindingRef",
    "role",
    "ownerIdentityRef",
    "principalRef",
    "credentialRef",
    "identityRegistryRef",
    "identityRegistryRevision",
    "validFrom",
    "validUntil",
    "revocationRef",
    "provenanceRef",
)
CREDENTIAL_RECORD_FIELDS = (
    "credentialRef",
    "principalRef",
    "keyEpoch",
    "keyAlgorithmRef",
    "publicKeyEncodingRef",
    "publicKeyWireBlobBase64",
    "publicKeyBlobSha256",
    "openSshPublicKeyFingerprint",
    "keyUsage",
    "allowedRoles",
    "validFrom",
    "validUntil",
    "proofOfControlRef",
    "proofOfControlEnvelopeSha256",
    "proofOfControlVerifiedAt",
    "revocationRef",
    "provenanceRef",
)
REVOCATION_SNAPSHOT_FIELDS = (
    "documentType",
    "schemaVersion",
    "revocationSnapshotRef",
    "registryId",
    "registryRevision",
    "registrySnapshotSha256",
    "revision",
    "previousRevocationSnapshotSha256",
    "issuedAt",
    "expiresAt",
    "credentialStatuses",
)
CREDENTIAL_STATUS_FIELDS = (
    "statusRef",
    "credentialRef",
    "publicKeyBlobSha256",
    "keyEpoch",
    "status",
    "effectiveAt",
    "compromiseAt",
    "reason",
)
ROOT_STATEMENT_FIELDS = (
    "documentType",
    "schemaVersion",
    "domain",
    "snapshotKind",
    "snapshotRef",
    "snapshotSha256",
    "registryId",
    "revision",
    "rootTrustAnchorRef",
    "rootKeyRef",
    "rootAlgorithmRef",
    "rootPublicKeySha256",
    "signatureFormatRef",
)
ROOT_SELECTOR_FIELDS = (
    "rootTrustAnchorRef",
    "rootKeyRef",
    "rootAlgorithmRef",
    "rootPublicKeySha256",
    "signatureFormatRef",
)
PRIVATE_ROOT_BOUNDARY_FIELDS = (
    "privateRootKeyMaterialAccepted",
    "privateRootKeyPathAccepted",
    "rootAgentEnumerationAllowed",
    "rootAgentUseAllowed",
    "rootEnvironmentLookupAllowed",
    "rootKeychainLookupAllowed",
    "projectDrivenRootSigningInvocationAllowed",
    "ownerCredentialKeyReuseAllowed",
    "releaseEvidenceKeyReuseAllowed",
)
ROLE_ENVELOPE_PAYLOAD_FIELDS = (
    "documentType",
    "schemaVersion",
    "domain",
    "principalRef",
    "role",
    "ownerBindingRef",
    "ownerIdentityRef",
    "credentialRef",
    "publicKeyBlobSha256",
    "receiptRef",
    "receiptRawSha256",
    "receiptCanonicalSha256",
    "targetBindingSha256",
    "identityRegistryRevision",
    "registrySnapshotSha256",
    "revocationSnapshotSha256",
    "keyEpoch",
    "bundleId",
    "challengeIssuerRef",
    "challengeId",
    "nonceBase64Url",
    "audience",
    "issuedAt",
    "expiresAt",
)
MANIFEST_PAYLOAD_FIELDS = (
    "documentType",
    "schemaVersion",
    "domain",
    "bundleId",
    "principalRef",
    "targetBindingSha256",
    "identityRegistryRevision",
    "registrySnapshotSha256",
    "revocationSnapshotSha256",
    "challengeIssuerRef",
    "audience",
    "orderedRoleEntries",
)
MANIFEST_ROLE_ENTRY_FIELDS = (
    "role",
    "ownerBindingRef",
    "ownerIdentityRef",
    "credentialRef",
    "keyEpoch",
    "publicKeyBlobSha256",
    "receiptRef",
    "receiptRawSha256",
    "receiptCanonicalSha256",
    "challengeId",
    "nonceBase64Url",
    "envelopeSha256",
    "signatureSha256",
)
DORMANT_SIDECAR_FIELDS = (
    "documentType",
    "schemaVersion",
    "status",
    "registrySnapshotSha256",
    "registryRevision",
    "committedRevocationSnapshotSha256",
    "committedRevocationRevision",
    "evaluatedLatestRevocationSnapshotSha256",
    "evaluatedLatestRevocationRevision",
    "orderedRoleResults",
)
DORMANT_ROLE_RESULT_FIELDS = (
    "role",
    "ownerBindingRef",
    "ownerIdentityRef",
    "credentialRef",
    "keyEpoch",
    "receiptRef",
    "receiptRawSha256",
    "receiptCanonicalSha256",
    "envelopeSha256",
    "signatureSha256",
)
STATE_FIELDS = (
    "providerSelected",
    "trustAnchorSelected",
    "credentialMechanismSelected",
    "credentialProvisioned",
    "ownerIdentityAuthenticated",
    "selectorDecisionAuthenticated",
    "reviewedAdapterResultAvailable",
    "evidenceSelectorsMayChange",
    "approvalReceiptAccepted",
    "receiptActivationAllowed",
    "g0ExitComplete",
    "g1aMayStartNow",
)

EXPECTED_SUPERSEDES = {
    "profilePath": bootstrap_v1.PROFILE_PATH,
    "profileId": "aetherlink_v1_g0_owner_trust_bootstrap_profile_v1",
    "profileRawSha256": bootstrap_v1.EXPECTED_PROFILE_RAW_SHA256,
}
EXPECTED_SOURCE_DECISION = {
    "decisionSource": "direct_user_instruction",
    "principalSelectionStatus": "user_selected_unverified_non_authorizing",
    "credentialPathSelectionStatus": "user_selected_software_ssh_ed25519_candidate",
    "hardwareBackedCredentialAvailable": False,
    "authorizationEffect": "none",
}
EXPECTED_PRINCIPAL = {
    "principalRef": "github-user-243786110-v1",
    "provider": "github",
    "login": "hanchangha1127",
    "declaredPrincipal": "github:hanchangha1127",
    "immutableUserId": "243786110",
    "subjectType": "User",
    "status": "user_selected_unverified_non_authorizing",
    "identitySemantics": "control_of_exact_github_account_not_real_world_identity",
    "humanPrincipalCount": 1,
    "ownerIdentityRefDerivationDomain": "aetherlink-v1-g0-owner-identity-v1",
    "roleMappingPolicy": "fourteen_unique_role_scoped_refs_map_to_this_one_principal",
}
EXPECTED_SIGNATURE_MECHANISM = {
    "mechanismRef": "software-ssh-ed25519-sshsig-v1",
    "protocol": "openssh_sshsig",
    "keyAlgorithm": "ssh-ed25519",
    "hardwareBacked": False,
    "messageHashAlgorithm": "sha512",
    "namespace": "aetherlink-owner-bootstrap-v1",
    "signatureEncoding": "openssh_sshsig_armored_v1",
    "canonicalEnvelopeEncoding": "rfc8785_jcs_utf8",
    "keyUsage": "g0_owner_role_authentication_only",
    "softwareKeyProvisioningPolicy": (
        "external_user_custody_only_no_project_key_generation_discovery_storage_or_backup"
    ),
    "automaticCredentialFallbackAllowed": False,
    "privateKeyPathAccepted": False,
    "callerSuppliedPrivateKeyMaterialAllowed": False,
    "sshAgentEnumerationAllowed": False,
    "sshAgentUseAllowed": False,
    "environmentCredentialLookupAllowed": False,
    "keychainCredentialLookupAllowed": False,
    "projectDrivenSigningInvocationAllowed": False,
    "releaseEvidenceKeyReuseAllowed": False,
    "credentialRefCandidate": None,
    "publicKeyBlobSha256": None,
    "openSshPublicKeyFingerprint": None,
    "trustAnchorRef": None,
    "proofOfControlStatus": "pending_owner_secret_custody_ceremony",
}
EXPECTED_SSHSIG_WIRE = {
    "magic": "SSHSIG",
    "version": 1,
    "reservedFieldPolicy": "exactly_empty",
    "outerPublicKeyAlgorithm": "ssh-ed25519",
    "embeddedPublicKeyPolicy": "exact_role_credential_registry_wire_blob",
    "signatureAlgorithm": "ssh-ed25519",
    "signatureLengthBytes": 64,
    "hashAlgorithm": "sha512",
    "namespace": "aetherlink-owner-bootstrap-v1",
    "sshCertificatesAllowed": False,
    "securityKeyAlgorithmsAllowed": False,
    "rsaOrEcdsaAlgorithmsAllowed": False,
    "armorPolicy": "canonical_single_block_no_leading_or_trailing_bytes",
    "armorLineLengthCharacters": 70,
    "armorNewlinePolicy": "lf_only_final_newline_required",
}
EXPECTED_DETACHED_ENVELOPE = {
    "documentType": "aetherlink.v1-g0-owner-role-auth-envelope",
    "schemaVersion": 1,
    "domain": "aetherlink-owner-bootstrap-v1",
    "exactFields": [
        "documentType",
        "schemaVersion",
        "domain",
        "principalRef",
        "role",
        "ownerBindingRef",
        "ownerIdentityRef",
        "credentialRef",
        "publicKeyBlobSha256",
        "receiptRef",
        "receiptRawSha256",
        "receiptCanonicalSha256",
        "targetBindingSha256",
        "identityRegistryRevision",
        "registrySnapshotSha256",
        "revocationSnapshotSha256",
        "keyEpoch",
        "bundleId",
        "challengeIssuerRef",
        "challengeId",
        "nonceBase64Url",
        "audience",
        "issuedAt",
        "expiresAt",
    ],
    "receiptMutationAllowed": False,
    "receiptRawBytePolicy": (
        "sha256_of_exact_supplied_eight_field_receipt_bytes_is_signed_without_rewrite"
    ),
    "receiptCanonicalFieldCount": len(receipt.APPROVAL_RECEIPT_FIELDS),
    "receiptDigestAlgorithm": "sha256",
    "perRoleEnvelopeRequired": True,
    "perRoleSignatureRequired": True,
    "requiredRoleCount": 14,
    "nonceBytes": 32,
    "challengeTtlSeconds": 600,
    "maximumClockSkewSeconds": 120,
    "exactFieldListPolicy": "closed_logical_field_set_not_serialization_order",
    "canonicalSerializationPolicy": (
        "strict_parse_then_rfc8785_jcs_utf8_bytes_are_the_only_signing_input"
    ),
    "credentialBindingPolicy": (
        "credential_and_public_key_digest_equal_the_role_binding_and_sshsig_embedded_key"
    ),
    "challengeIssuerPolicy": (
        "independent_verifier_pending_record_exactly_matches_issuer_challenge_nonce_audience_and_target"
    ),
    "nonceEncodingPolicy": "unpadded_base64url_decodes_to_exactly_thirty_two_bytes",
    "timestampPolicy": (
        "canonical_rfc3339_utc_issued_at_strictly_before_expires_at_with_exact_ttl"
    ),
    "bundleManifestPolicy": (
        "exact_canonical_role_order_all_fourteen_envelope_and_signature_digests"
    ),
    "unknownFieldPolicy": "reject",
}
EXPECTED_BUNDLE_MANIFEST = {
    "documentType": "aetherlink.v1-g0-owner-role-auth-bundle-manifest",
    "schemaVersion": 1,
    "domain": "aetherlink-owner-bootstrap-v1",
    "exactFields": [
        "documentType",
        "schemaVersion",
        "domain",
        "bundleId",
        "principalRef",
        "targetBindingSha256",
        "identityRegistryRevision",
        "registrySnapshotSha256",
        "revocationSnapshotSha256",
        "challengeIssuerRef",
        "audience",
        "orderedRoleEntries",
    ],
    "roleEntryExactFields": [
        "role",
        "ownerBindingRef",
        "ownerIdentityRef",
        "credentialRef",
        "keyEpoch",
        "publicKeyBlobSha256",
        "receiptRef",
        "receiptRawSha256",
        "receiptCanonicalSha256",
        "challengeId",
        "nonceBase64Url",
        "envelopeSha256",
        "signatureSha256",
    ],
    "canonicalEncoding": "rfc8785_jcs_utf8",
    "digestAlgorithm": "sha256",
    "roleOrderPolicy": "exact_effective_v3_canonical_approval_role_order",
    "roleCardinality": 14,
    "duplicateOrPartialRoleEntryPolicy": "reject",
}
EXPECTED_REGISTRY = {
    "registryRootStatus": (
        "pending_independent_out_of_band_public_key_fingerprint_pin"
    ),
    "githubAccountSnapshotRole": "supplemental_provenance_only_not_trust_anchor",
    "canonicalEncoding": "rfc8785_jcs_utf8_exact_input_bytes",
    "digestAlgorithm": "sha256",
    "maximumSnapshotBytes": 4_194_304,
    "maximumDepth": 32,
    "maximumArrayItems": 256,
    "maximumStringBytes": 4_096,
    "canonicalUint64Pattern": r"^(0|[1-9][0-9]{0,19})$",
    "registrySnapshotContract": {
        "documentType": "aetherlink.v1-g0-owner-identity-registry-snapshot",
        "schemaVersion": 1,
        "exactFields": list(REGISTRY_SNAPSHOT_FIELDS),
        "principalMappingExactFields": list(PRINCIPAL_MAPPING_FIELDS),
        "credentialRecordExactFields": list(CREDENTIAL_RECORD_FIELDS),
        "principalMappingCount": 14,
        "credentialRecordCountPolicy": "one_to_fourteen_all_and_only_referenced_records",
        "credentialReusePolicy": (
            "same_principal_same_exact_key_digest_one_immutable_epoch_and_"
            "allowed_roles_exactly_equal_referencing_roles"
        ),
        "rotationPolicy": "new_key_epoch_requires_new_credential_ref",
        "roleOrderPolicy": "exact_effective_v3_canonical_approval_role_order",
        "ownerBindingProjectionPolicy": (
            "mapping_exactly_projects_v3_owner_binding_fields_with_header_registry_ref_and_revision"
        ),
        "validityPolicy": "mapping_interval_is_contained_by_credential_interval",
        "statusSourcePolicy": (
            "no_registry_status_field_revocation_snapshot_is_the_only_status_source"
        ),
        "revocationBackReferenceAllowed": False,
    },
    "revocationSnapshotContract": {
        "documentType": "aetherlink.v1-g0-owner-credential-status-snapshot",
        "schemaVersion": 1,
        "exactFields": list(REVOCATION_SNAPSHOT_FIELDS),
        "credentialStatusExactFields": list(CREDENTIAL_STATUS_FIELDS),
        "coveragePolicy": (
            "exactly_one_status_record_for_every_bound_registry_credential_and_no_orphans"
        ),
        "statusOrderPolicy": "exact_registry_credential_record_order",
        "referencePolicy": (
            "owner_binding_revocation_ref_equals_credential_record_revocation_ref_"
            "equals_status_record_status_ref"
        ),
        "activePolicy": "effective_at_compromise_at_and_reason_are_null",
        "revokedPolicy": (
            "effective_at_required_reason_closed_enum_compromise_at_canonical_utc_or_null"
        ),
        "registryBindingPolicy": (
            "registry_id_revision_and_exact_canonical_registry_sha256_must_match_"
            "supplied_registry_snapshot"
        ),
        "registryDigestBackReferenceAllowed": True,
    },
    "offlineRootSignatureStatementContract": {
        "documentType": "aetherlink.v1-g0-owner-registry-root-signature-statement",
        "schemaVersion": 1,
        "domain": "aetherlink-owner-registry-root-v1",
        "exactFields": list(ROOT_STATEMENT_FIELDS),
        "snapshotKinds": ["registry", "revocation"],
        "signedBytesPolicy": "exact_rfc8785_jcs_utf8_statement_bytes_only",
        "signaturePlacementPolicy": (
            "detached_signature_bytes_are_outside_statement_and_never_part_of_snapshot_digest"
        ),
        "verificationKeyPolicy": (
            "external_pinned_selector_only_never_snapshot_embedded_key"
        ),
        "currentSelectorPolicy": (
            "all_root_selector_fields_null_so_no_signature_can_be_verified_now"
        ),
    },
    "offlineRootSelectors": {field: None for field in ROOT_SELECTOR_FIELDS},
    "privateRootBoundary": {
        field: False for field in PRIVATE_ROOT_BOUNDARY_FIELDS
    },
    "pairBindingPolicy": (
        "revocation_snapshot_one_way_commits_registry_ref_revision_and_digest_"
        "registry_never_commits_revocation_id_or_digest"
    ),
    "digestEqualityPolicy": (
        "computed_registry_and_revocation_digests_exactly_equal_all_role_"
        "envelopes_manifest_root_statements_and_dormant_adapter_sidecar"
    ),
    "revisionPolicy": (
        "independent_strictly_monotonic_canonical_uint64_registry_and_revocation_"
        "chains_with_previous_snapshot_sha256"
    ),
    "highWatermarkPolicy": (
        "independent_ledger_atomically_rejects_lower_revision_same_revision_fork_"
        "broken_previous_digest_and_pair_rollback"
    ),
    "ownerMappingPolicy": (
        "one_principal_fourteen_unique_role_scoped_identity_refs_with_resolved_"
        "credentials_and_statuses"
    ),
    "keySeparationPolicy": (
        "owner_root_delegate_recovery_and_release_evidence_keys_are_distinct"
    ),
    "revocationEvaluationPolicy": (
        "latest_independently_observed_nonrollback_snapshot_at_trusted_validation_time"
    ),
    "unknownCompromiseTimePolicy": "reject_all_signatures_from_affected_key_epoch",
    "availabilityPolicy": (
        "fail_closed_when_latest_acceptable_registry_or_revocation_state_is_unavailable"
    ),
    "normalDelegateRotationPolicy": (
        "new_credential_ref_for_higher_epoch_in_root_signed_registry_successor_"
        "then_previous_status_revoked"
    ),
    "rootCompromisePolicy": (
        "freeze_without_cross_sign_and_require_pre_enrolled_offline_recovery_or_new_bootstrap"
    ),
}
EXPECTED_TRUSTED_TIME = {
    "standard": "rfc3161",
    "providerSelectionStatus": "unselected",
    "tsaProviderRef": None,
    "tsaTrustAnchorRef": None,
    "timeUse": "signature_existence_and_accepted_at_boundary_only",
    "mayProveLatestRegistryRevision": False,
    "maySubstituteForReplayLedger": False,
    "manifestCoveragePolicy": (
        "timestamped_manifest_commits_all_fourteen_signature_digests_with_inclusion_proofs"
    ),
    "tokenValidationPolicy": (
        "exact_der_message_imprint_nonce_policy_oid_tsa_eku_chain_certificate_status_and_generation_time"
    ),
    "availabilityPolicy": "validation_may_remain_dormant_but_activation_fails_closed",
}
EXPECTED_REPLAY = {
    "ledgerStatus": "not_implemented",
    "ledgerNamespace": "aetherlink-v1-g0-owner-role-auth",
    "coordinatorStatus": "unselected",
    "externalConsumedBundleLedgerRequiredBeforeActivation": True,
    "atomicRoleCoverageCount": 14,
    "consumeKeyFields": [
        "principalRef",
        "role",
        "ownerIdentityRef",
        "receiptRef",
        "receiptRawSha256",
        "receiptCanonicalSha256",
        "challengeId",
        "nonceBase64Url",
        "keyEpoch",
        "targetBindingSha256",
        "bundleManifestSha256",
    ],
    "partialConsumptionAllowed": False,
    "idempotentExactRetryMayReturnPriorResult": True,
    "rollbackDetectionRequired": True,
    "atomicCompareAndSetPolicy": (
        "consume_complete_bundle_and_advance_registry_and_revocation_pair_"
        "high_watermarks_in_one_transaction"
    ),
    "crashRecoveryPolicy": (
        "after_restart_exact_transaction_outcome_must_be_read_back_without_second_consumption"
    ),
    "backupRestorePolicy": (
        "restored_ledger_below_either_external_registry_or_revocation_high_"
        "watermark_or_at_an_unobserved_pair_is_rejected"
    ),
    "ledgerUnavailablePolicy": "dormant_validation_only_no_activation",
}
EXPECTED_SUCCESSOR_TRANSITION = {
    "currentCandidateMayAuthenticate": False,
    "currentCandidateMaySelectOperationalSelectors": False,
    "nonNullSelectorPrerequisites": [
        "independently_pinned_root_and_exact_public_key",
        "authenticated_owner_proof_of_control",
        "authenticated_exact_selector_decision",
        "reviewed_versioned_registry_revocation_time_envelope_and_adapter_contracts",
    ],
    "selfAssertedTrustAnchorAllowed": False,
    "githubPublishedKeyAsSoleTrustAnchorAllowed": False,
    "cachedRegistryOrLocalClockFallbackAllowed": False,
    "statefulActivationPrerequisite": (
        "reviewed_external_atomic_consumed_bundle_ledger"
    ),
    "failurePolicy": (
        "remain_dormant_with_all_selection_and_authority_state_unchanged"
    ),
}
EXPECTED_ADAPTER = {
    "independentTrustInput": "trusted_owner_identity_registry_and_revocation_snapshot",
    "verifiedSubjectFields": ["targetBinding", "ownerBindings", "approvalReceipts"],
    "dormantSidecarDocumentType": (
        "aetherlink.v1-g0-owner-trust-dormant-verification-sidecar"
    ),
    "dormantSidecarSchemaVersion": 1,
    "dormantSidecarExactFields": list(DORMANT_SIDECAR_FIELDS),
    "dormantRoleResultExactFields": list(DORMANT_ROLE_RESULT_FIELDS),
    "dormantSidecarStatus": (
        "dormant_structurally_valid_unverified_non_authorizing"
    ),
    "mayCreateDormantSidecar": False,
    "integrationStatus": "not_implemented",
    "genericCandidateFactoryMaySubstitute": False,
    "mayCreateAdapterResult": False,
}

_OWNER_BINDING_REF_PATTERN = re.compile(
    r"^g0-owner-binding-[a-z0-9][a-z0-9_-]{0,95}-v[1-9][0-9]*$"
)
_OWNER_IDENTITY_REF_PATTERN = re.compile(
    r"^g0-owner-identity-[0-9a-f]{64}-v[1-9][0-9]*$"
)
_RECEIPT_REF_PATTERN = re.compile(
    r"^g0-approval-receipt-[a-z0-9][a-z0-9_-]{0,95}-v[1-9][0-9]*$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_UINT64_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,19})$")
_ASCII_REF_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:@/-]{0,255}$")
_CREDENTIAL_REF_PATTERN = re.compile(
    r"^g0-owner-credential-[0-9a-f]{64}-e(?:0|[1-9][0-9]{0,19})-v1$"
)
_STATUS_REF_PATTERN = re.compile(
    r"^g0-owner-credential-status-[0-9a-f]{64}-v1$"
)
_CANONICAL_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_REVOCATION_REASONS = {
    "compromise",
    "superseded",
    "owner_request",
    "registry_policy",
}
_EXPECTED_ROLE_ORDER = (
    "repository_owner",
    "repository_quality_owner",
    "product_and_distribution_owner",
    "product_security_owner",
    "release_owner",
    "release_quality_owner",
    "release_network_qa_owner",
    "release_performance_qa_owner",
    "runtime_provider_compatibility_owner",
    "service_identity_owner",
    "service_security_owner",
    "service_operations_owner",
    "service_operations_and_abuse_owner",
    "privacy_and_incident_owner",
)
MAX_SNAPSHOT_BYTES = 4_194_304
MAX_PAYLOAD_DEPTH = 32
MAX_PAYLOAD_ARRAY_ITEMS = 256
MAX_PAYLOAD_STRING_BYTES = 4_096
MAX_SIGNATURE_BYTES = 16_384
_SSHSIG_ARMOR_BEGIN = b"-----BEGIN SSH SIGNATURE-----"
_SSHSIG_ARMOR_END = b"-----END SSH SIGNATURE-----"
_SSHSIG_ARMOR_LINE_BYTES = 70


def _require_exact(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not decision.exactly_equal(actual, expected):
        failures.append(f"{label} is not exact")


def _expected_identity_ref(role: str) -> str:
    raw = "\0".join(
        (
            EXPECTED_PRINCIPAL["ownerIdentityRefDerivationDomain"],
            EXPECTED_PRINCIPAL["provider"],
            EXPECTED_PRINCIPAL["immutableUserId"],
            role,
        )
    ).encode("utf-8")
    return f"g0-owner-identity-{hashlib.sha256(raw).hexdigest()}-v1"


def _expected_role_mapping(role: str) -> dict[str, object]:
    role_slug = role.replace("_", "-")
    return {
        "role": role,
        "ownerBindingRefCandidate": f"g0-owner-binding-{role_slug}-v1",
        "ownerIdentityRefCandidate": _expected_identity_ref(role),
        "principalRef": EXPECTED_PRINCIPAL["principalRef"],
        "receiptRefCandidate": f"g0-approval-receipt-{role_slug}-v1",
        "credentialRefCandidate": None,
    }


def _validate_role_candidates(
    value: object,
    expected_roles: tuple[str, ...],
    failures: list[str],
) -> None:
    if not isinstance(value, list):
        failures.append("profile.roleIdentityCandidates is not an array")
        return
    if len(value) != len(expected_roles):
        failures.append("profile.roleIdentityCandidates count is not exact")

    parsed: list[dict[str, object]] = []
    for index, item in enumerate(value):
        parsed.append(
            receipt._exact_ordered_object(
                item,
                ROLE_IDENTITY_FIELDS,
                f"profile.roleIdentityCandidates[{index}]",
                failures,
            )
        )

    actual_roles = tuple(item.get("role") for item in parsed)
    _require_exact(
        actual_roles,
        expected_roles,
        "profile.roleIdentityCandidates canonical role order",
        failures,
    )

    for index, role in enumerate(expected_roles):
        if index >= len(parsed):
            break
        candidate = parsed[index]
        _require_exact(
            candidate,
            _expected_role_mapping(role),
            f"profile.roleIdentityCandidates[{index}] mapping",
            failures,
        )

    binding_refs = [item.get("ownerBindingRefCandidate") for item in parsed]
    identity_refs = [item.get("ownerIdentityRefCandidate") for item in parsed]
    receipt_refs = [item.get("receiptRefCandidate") for item in parsed]
    binding_refs_are_strings = all(isinstance(ref, str) for ref in binding_refs)
    identity_refs_are_strings = all(isinstance(ref, str) for ref in identity_refs)
    receipt_refs_are_strings = all(isinstance(ref, str) for ref in receipt_refs)
    if binding_refs_are_strings and len(set(binding_refs)) != len(binding_refs):
        failures.append("role candidate owner binding references are not unique")
    if identity_refs_are_strings and len(set(identity_refs)) != len(identity_refs):
        failures.append("role candidate owner identity references are not unique")
    if receipt_refs_are_strings and len(set(receipt_refs)) != len(receipt_refs):
        failures.append("role candidate receipt references are not unique")
    for ref in binding_refs:
        if not isinstance(ref, str) or _OWNER_BINDING_REF_PATTERN.fullmatch(ref) is None:
            failures.append("role candidate owner binding reference is malformed")
    for ref in identity_refs:
        if not isinstance(ref, str) or _OWNER_IDENTITY_REF_PATTERN.fullmatch(ref) is None:
            failures.append("role candidate owner identity reference is malformed")
    for ref in receipt_refs:
        if not isinstance(ref, str) or _RECEIPT_REF_PATTERN.fullmatch(ref) is None:
            failures.append("role candidate receipt reference is malformed")


def _canonical_payload_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _parse_canonical_payload(
    value: object,
    label: str,
    maximum_bytes: int,
    failures: list[str],
) -> tuple[bytes | None, dict[str, object]]:
    raw = receipt._bounded_snapshot(value, label, maximum_bytes, failures)
    parsed = (
        receipt._parse_object(raw, label, failures)
        if raw is not None
        else None
    )
    if parsed is None:
        return raw, {}
    receipt._validate_json_resources(
        parsed,
        failures,
        root_label=label,
        maximum_depth=MAX_PAYLOAD_DEPTH,
        maximum_items=MAX_PAYLOAD_ARRAY_ITEMS,
        maximum_string_bytes=MAX_PAYLOAD_STRING_BYTES,
    )
    try:
        canonical = _canonical_payload_bytes(parsed)
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        failures.append(f"{label} cannot be canonically encoded: {error}")
    else:
        if raw != canonical:
            failures.append(f"{label} bytes are not exact restricted RFC 8785 JCS UTF-8")
    return raw, parsed


def _payload_object(
    value: object,
    fields: tuple[str, ...],
    label: str,
    failures: list[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        failures.append(f"{label} is not an object")
        return {}
    if set(value) != set(fields) or len(value) != len(fields):
        failures.append(f"{label} fields are not exact")
    return value


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_PATTERN.fullmatch(value) is not None


def _valid_ascii_ref(value: object) -> bool:
    return isinstance(value, str) and _ASCII_REF_PATTERN.fullmatch(value) is not None


def _parse_uint64(value: object, label: str, failures: list[str]) -> int | None:
    if not isinstance(value, str) or _CANONICAL_UINT64_PATTERN.fullmatch(value) is None:
        failures.append(f"{label} is not a canonical uint64 decimal string")
        return None
    parsed = int(value)
    if parsed > (1 << 64) - 1:
        failures.append(f"{label} exceeds uint64")
        return None
    return parsed


def _parse_payload_utc(
    value: object,
    label: str,
    failures: list[str],
) -> _datetime | None:
    if not isinstance(value, str) or _CANONICAL_UTC_PATTERN.fullmatch(value) is None:
        failures.append(f"{label} is not canonical RFC3339 UTC")
        return None
    try:
        return _datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_timezone.utc
        )
    except ValueError:
        failures.append(f"{label} is not a valid UTC timestamp")
        return None


def _validate_interval(
    start_value: object,
    end_value: object,
    label: str,
    failures: list[str],
) -> tuple[_datetime | None, _datetime | None]:
    start = _parse_payload_utc(start_value, f"{label}.start", failures)
    end = _parse_payload_utc(end_value, f"{label}.end", failures)
    if start is not None and end is not None and start >= end:
        failures.append(f"{label} interval is empty or reversed")
    return start, end


def _valid_previous_digest(value: object) -> bool:
    return value is None or _valid_sha256(value)


def _decode_ed25519_wire_blob(
    value: object,
    label: str,
    failures: list[str],
) -> bytes | None:
    if not isinstance(value, str) or not value:
        failures.append(f"{label} is not canonical base64")
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        failures.append(f"{label} is not canonical base64")
        return None
    if base64.b64encode(raw).decode("ascii") != value:
        failures.append(f"{label} base64 is not canonical")
        return None
    if (
        len(raw) != 51
        or raw[:4] != (11).to_bytes(4, "big")
        or raw[4:15] != b"ssh-ed25519"
        or raw[15:19] != (32).to_bytes(4, "big")
    ):
        failures.append(f"{label} is not the exact 51-byte ssh-ed25519 wire blob")
        return None
    return raw


def _canonical_sshsig_armor(payload: bytes) -> bytes:
    encoded = base64.b64encode(payload)
    lines = [
        encoded[offset : offset + _SSHSIG_ARMOR_LINE_BYTES]
        for offset in range(0, len(encoded), _SSHSIG_ARMOR_LINE_BYTES)
    ]
    return (
        _SSHSIG_ARMOR_BEGIN
        + b"\n"
        + b"\n".join(lines)
        + b"\n"
        + _SSHSIG_ARMOR_END
        + b"\n"
    )


def _read_ssh_string(
    payload: bytes,
    offset: int,
    label: str,
    failures: list[str],
) -> tuple[bytes | None, int]:
    if len(payload) - offset < 4:
        failures.append(f"{label} SSH string length is truncated")
        return None, len(payload)
    size = int.from_bytes(payload[offset : offset + 4], "big")
    start = offset + 4
    end = start + size
    if size > MAX_SIGNATURE_BYTES or end > len(payload):
        failures.append(f"{label} SSH string length exceeds supplied bytes")
        return None, len(payload)
    return payload[start:end], end


def _parse_ed25519_sshsig(
    value: object,
    expected_public_key_wire: object,
    label: str,
    failures: list[str],
) -> bytes | None:
    """Parse the public SSHSIG wire shape without verifying its signature."""

    armored = receipt._bounded_snapshot(value, label, MAX_SIGNATURE_BYTES, failures)
    if armored is None:
        return None
    prefix = _SSHSIG_ARMOR_BEGIN + b"\n"
    suffix = b"\n" + _SSHSIG_ARMOR_END + b"\n"
    if not armored.startswith(prefix) or not armored.endswith(suffix):
        failures.append(f"{label} armor is not one canonical OpenSSH SSHSIG block")
        return armored
    encoded_lines = armored[len(prefix) : -len(suffix)].split(b"\n")
    if not encoded_lines or any(not line for line in encoded_lines):
        failures.append(f"{label} armor body is empty or split by a blank line")
        return armored
    encoded = b"".join(encoded_lines)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        failures.append(f"{label} armor base64 is invalid")
        return armored
    if base64.b64encode(payload) != encoded or _canonical_sshsig_armor(payload) != armored:
        failures.append(f"{label} armor is not canonical")

    if len(payload) < 10:
        failures.append(f"{label} SSHSIG wire header is truncated")
        return armored
    if payload[:6] != b"SSHSIG":
        failures.append(f"{label} SSHSIG magic is not exact")
    if payload[6:10] != (1).to_bytes(4, "big"):
        failures.append(f"{label} SSHSIG version is not 1")

    offset = 10
    public_key, offset = _read_ssh_string(
        payload, offset, f"{label} embedded public key", failures
    )
    if public_key is None:
        return armored
    namespace, offset = _read_ssh_string(
        payload, offset, f"{label} namespace", failures
    )
    if namespace is None:
        return armored
    reserved, offset = _read_ssh_string(
        payload, offset, f"{label} reserved field", failures
    )
    if reserved is None:
        return armored
    hash_algorithm, offset = _read_ssh_string(
        payload, offset, f"{label} hash algorithm", failures
    )
    if hash_algorithm is None:
        return armored
    inner, offset = _read_ssh_string(
        payload, offset, f"{label} inner signature", failures
    )
    if inner is None:
        return armored
    if offset != len(payload):
        failures.append(f"{label} SSHSIG wire has trailing bytes")

    if (
        len(public_key) != 51
        or public_key[:4] != (11).to_bytes(4, "big")
        or public_key[4:15] != b"ssh-ed25519"
        or public_key[15:19] != (32).to_bytes(4, "big")
    ):
        failures.append(f"{label} embedded public key is not exact ssh-ed25519 wire")
    if not isinstance(expected_public_key_wire, bytes):
        failures.append(f"{label} role credential public key is unavailable")
    elif public_key != expected_public_key_wire:
        failures.append(f"{label} embedded public key does not equal the role credential")
    if namespace != b"aetherlink-owner-bootstrap-v1":
        failures.append(f"{label} namespace is not exact")
    if reserved != b"":
        failures.append(f"{label} reserved field is not empty")
    if hash_algorithm != b"sha512":
        failures.append(f"{label} hash algorithm is not sha512")

    inner_algorithm, inner_offset = _read_ssh_string(
        inner, 0, f"{label} inner signature algorithm", failures
    )
    if inner_algorithm is None:
        return armored
    signature, inner_offset = _read_ssh_string(
        inner, inner_offset, f"{label} inner signature bytes", failures
    )
    if signature is None:
        return armored
    if inner_offset != len(inner):
        failures.append(f"{label} inner signature has trailing bytes")
    if inner_algorithm != b"ssh-ed25519":
        failures.append(f"{label} inner signature algorithm is not ssh-ed25519")
    if len(signature) != 64:
        failures.append(f"{label} inner signature length is not 64 bytes")
    return armored


def _valid_nonce(value: object) -> bool:
    if not isinstance(value, str) or "=" in value:
        return False
    try:
        raw = base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))
    except (binascii.Error, ValueError):
        return False
    return (
        len(raw) == 32
        and base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") == value
    )


def collect_dormant_owner_trust_payload_failures(
    registry_snapshot_bytes: object,
    revocation_snapshot_bytes: object,
    registry_root_statement_bytes: object,
    revocation_root_statement_bytes: object,
    *,
    role_envelope_blobs: object,
    role_signature_blobs: object,
    manifest_bytes: object,
    adapter_sidecar_bytes: object,
) -> tuple[str, ...]:
    """Validate supplied public candidate bytes without verifying any signature."""

    failures: list[str] = []
    registry_raw, registry = _parse_canonical_payload(
        registry_snapshot_bytes,
        "owner registry snapshot",
        MAX_SNAPSHOT_BYTES,
        failures,
    )
    revocation_raw, revocation = _parse_canonical_payload(
        revocation_snapshot_bytes,
        "owner revocation snapshot",
        MAX_SNAPSHOT_BYTES,
        failures,
    )
    _, registry_statement = _parse_canonical_payload(
        registry_root_statement_bytes,
        "registry offline-root statement",
        MAX_PAYLOAD_STRING_BYTES * 8,
        failures,
    )
    _, revocation_statement = _parse_canonical_payload(
        revocation_root_statement_bytes,
        "revocation offline-root statement",
        MAX_PAYLOAD_STRING_BYTES * 8,
        failures,
    )
    _, manifest = _parse_canonical_payload(
        manifest_bytes,
        "owner role manifest",
        MAX_SNAPSHOT_BYTES,
        failures,
    )
    _, sidecar = _parse_canonical_payload(
        adapter_sidecar_bytes,
        "dormant adapter sidecar",
        MAX_SNAPSHOT_BYTES,
        failures,
    )

    registry = _payload_object(
        registry, REGISTRY_SNAPSHOT_FIELDS, "owner registry snapshot", failures
    )
    for field, expected in (
        ("documentType", "aetherlink.v1-g0-owner-identity-registry-snapshot"),
        ("schemaVersion", 1),
    ):
        _require_exact(registry.get(field), expected, f"registry.{field}", failures)
    for field in ("registrySnapshotRef", "registryId"):
        if not _valid_ascii_ref(registry.get(field)):
            failures.append(f"registry.{field} is invalid")
    _parse_uint64(registry.get("revision"), "registry.revision", failures)
    if not _valid_previous_digest(registry.get("previousRegistrySnapshotSha256")):
        failures.append("registry.previousRegistrySnapshotSha256 is invalid")
    _validate_interval(
        registry.get("issuedAt"), registry.get("expiresAt"), "registry validity", failures
    )
    registry_sha = hashlib.sha256(registry_raw or b"").hexdigest()

    mappings_value = registry.get("principalMappings")
    if not isinstance(mappings_value, list) or len(mappings_value) != 14:
        failures.append("registry principalMappings must contain exactly fourteen records")
        mappings_value = []
    mappings: dict[str, dict[str, object]] = {}
    mapping_intervals: dict[str, tuple[_datetime | None, _datetime | None]] = {}
    seen_binding_refs: set[str] = set()
    seen_identity_refs: set[str] = set()
    for index, role in enumerate(_EXPECTED_ROLE_ORDER):
        mapping = _payload_object(
            mappings_value[index] if index < len(mappings_value) else None,
            PRINCIPAL_MAPPING_FIELDS,
            f"principal mapping {index}",
            failures,
        )
        expected_candidate = _expected_role_mapping(role)
        for field, expected in (
            ("role", role),
            ("ownerBindingRef", expected_candidate["ownerBindingRefCandidate"]),
            ("ownerIdentityRef", expected_candidate["ownerIdentityRefCandidate"]),
            ("principalRef", EXPECTED_PRINCIPAL["principalRef"]),
            ("identityRegistryRef", registry.get("registryId")),
            ("identityRegistryRevision", registry.get("revision")),
        ):
            _require_exact(mapping.get(field), expected, f"mapping {role}.{field}", failures)
        for field in ("credentialRef", "revocationRef", "provenanceRef"):
            if not _valid_ascii_ref(mapping.get(field)):
                failures.append(f"mapping {role}.{field} is invalid")
        for field, seen in (
            ("ownerBindingRef", seen_binding_refs),
            ("ownerIdentityRef", seen_identity_refs),
        ):
            value = mapping.get(field)
            if isinstance(value, str):
                if value in seen:
                    failures.append(f"mapping {role}.{field} is duplicated")
                seen.add(value)
        mapping_intervals[role] = _validate_interval(
            mapping.get("validFrom"),
            mapping.get("validUntil"),
            f"mapping {role} validity",
            failures,
        )
        mappings[role] = mapping

    credentials_value = registry.get("credentialRecords")
    if (
        not isinstance(credentials_value, list)
        or not 1 <= len(credentials_value) <= 14
    ):
        failures.append("registry credentialRecords must contain one through fourteen records")
        credentials_value = []
    credentials: dict[str, dict[str, object]] = {}
    credential_wires: dict[str, bytes] = {}
    credential_intervals: dict[str, tuple[_datetime | None, _datetime | None]] = {}
    seen_key_digests: set[str] = set()
    for index, item in enumerate(credentials_value):
        credential = _payload_object(
            item,
            CREDENTIAL_RECORD_FIELDS,
            f"credential record {index}",
            failures,
        )
        credential_ref = credential.get("credentialRef")
        key_epoch = credential.get("keyEpoch")
        _parse_uint64(key_epoch, f"credential record {index}.keyEpoch", failures)
        if (
            not isinstance(credential_ref, str)
            or _CREDENTIAL_REF_PATTERN.fullmatch(credential_ref) is None
        ):
            failures.append(f"credential record {index}.credentialRef is invalid")
        elif credential_ref in credentials:
            failures.append(f"credential record {index}.credentialRef is duplicated")
        for field, expected in (
            ("principalRef", EXPECTED_PRINCIPAL["principalRef"]),
            ("keyAlgorithmRef", EXPECTED_SIGNATURE_MECHANISM["mechanismRef"]),
            ("publicKeyEncodingRef", "openssh_ssh_ed25519_wire_blob_v1"),
            ("keyUsage", EXPECTED_SIGNATURE_MECHANISM["keyUsage"]),
        ):
            _require_exact(
                credential.get(field), expected, f"credential record {index}.{field}", failures
            )
        wire = _decode_ed25519_wire_blob(
            credential.get("publicKeyWireBlobBase64"),
            f"credential record {index}.publicKeyWireBlobBase64",
            failures,
        )
        digest = hashlib.sha256(wire).hexdigest() if wire is not None else None
        if digest is not None:
            _require_exact(
                credential.get("publicKeyBlobSha256"),
                digest,
                f"credential record {index}.publicKeyBlobSha256",
                failures,
            )
            fingerprint = "SHA256:" + base64.b64encode(bytes.fromhex(digest)).decode(
                "ascii"
            ).rstrip("=")
            _require_exact(
                credential.get("openSshPublicKeyFingerprint"),
                fingerprint,
                f"credential record {index}.openSshPublicKeyFingerprint",
                failures,
            )
            expected_ref = f"g0-owner-credential-{digest}-e{key_epoch}-v1"
            _require_exact(
                credential_ref,
                expected_ref,
                f"credential record {index}.credentialRef",
                failures,
            )
            if digest in seen_key_digests:
                failures.append("credential public-key digest is reused by multiple records")
            seen_key_digests.add(digest)
        allowed_roles = credential.get("allowedRoles")
        if (
            not isinstance(allowed_roles, list)
            or not allowed_roles
            or any(role not in _EXPECTED_ROLE_ORDER for role in allowed_roles)
            or allowed_roles != sorted(
                set(allowed_roles), key=_EXPECTED_ROLE_ORDER.index
            )
        ):
            failures.append(f"credential record {index}.allowedRoles is invalid")
        for field in (
            "proofOfControlRef",
            "revocationRef",
            "provenanceRef",
        ):
            if not _valid_ascii_ref(credential.get(field)):
                failures.append(f"credential record {index}.{field} is invalid")
        if not _valid_sha256(credential.get("proofOfControlEnvelopeSha256")):
            failures.append(
                f"credential record {index}.proofOfControlEnvelopeSha256 is invalid"
            )
        _parse_payload_utc(
            credential.get("proofOfControlVerifiedAt"),
            f"credential record {index}.proofOfControlVerifiedAt",
            failures,
        )
        interval = _validate_interval(
            credential.get("validFrom"),
            credential.get("validUntil"),
            f"credential record {index} validity",
            failures,
        )
        if isinstance(credential_ref, str):
            credentials[credential_ref] = credential
            credential_intervals[credential_ref] = interval
            if wire is not None:
                credential_wires[credential_ref] = wire

    referenced_credentials = {
        value
        for mapping in mappings.values()
        if isinstance((value := mapping.get("credentialRef")), str)
    }
    if referenced_credentials != set(credentials):
        failures.append("registry credentials are dangling, orphaned, or incomplete")
    for credential_ref, credential in credentials.items():
        roles = [
            role
            for role in _EXPECTED_ROLE_ORDER
            if mappings.get(role, {}).get("credentialRef") == credential_ref
        ]
        _require_exact(
            credential.get("allowedRoles"),
            roles,
            f"credential {credential_ref}.allowedRoles",
            failures,
        )
        credential_start, credential_end = credential_intervals.get(
            credential_ref, (None, None)
        )
        for role in roles:
            mapping = mappings[role]
            _require_exact(
                mapping.get("revocationRef"),
                credential.get("revocationRef"),
                f"mapping {role}.revocationRef",
                failures,
            )
            mapping_start, mapping_end = mapping_intervals[role]
            if (
                None not in (credential_start, credential_end, mapping_start, mapping_end)
                and not (
                    credential_start <= mapping_start
                    and mapping_end <= credential_end
                )
            ):
                failures.append(f"mapping {role} validity escapes credential validity")

    revocation = _payload_object(
        revocation,
        REVOCATION_SNAPSHOT_FIELDS,
        "owner revocation snapshot",
        failures,
    )
    for field, expected in (
        ("documentType", "aetherlink.v1-g0-owner-credential-status-snapshot"),
        ("schemaVersion", 1),
        ("registryId", registry.get("registryId")),
        ("registryRevision", registry.get("revision")),
        ("registrySnapshotSha256", registry_sha),
    ):
        _require_exact(revocation.get(field), expected, f"revocation.{field}", failures)
    if not _valid_ascii_ref(revocation.get("revocationSnapshotRef")):
        failures.append("revocation.revocationSnapshotRef is invalid")
    _parse_uint64(revocation.get("revision"), "revocation.revision", failures)
    if not _valid_previous_digest(revocation.get("previousRevocationSnapshotSha256")):
        failures.append("revocation.previousRevocationSnapshotSha256 is invalid")
    _validate_interval(
        revocation.get("issuedAt"),
        revocation.get("expiresAt"),
        "revocation validity",
        failures,
    )
    revocation_sha = hashlib.sha256(revocation_raw or b"").hexdigest()

    statuses_value = revocation.get("credentialStatuses")
    if not isinstance(statuses_value, list) or len(statuses_value) != len(credentials):
        failures.append("revocation credentialStatuses must cover every credential exactly once")
        statuses_value = []
    statuses: dict[str, dict[str, object]] = {}
    for index, credential_ref in enumerate(credentials):
        status = _payload_object(
            statuses_value[index] if index < len(statuses_value) else None,
            CREDENTIAL_STATUS_FIELDS,
            f"credential status {index}",
            failures,
        )
        credential = credentials[credential_ref]
        for field, expected in (
            ("credentialRef", credential_ref),
            ("publicKeyBlobSha256", credential.get("publicKeyBlobSha256")),
            ("keyEpoch", credential.get("keyEpoch")),
            ("statusRef", credential.get("revocationRef")),
        ):
            _require_exact(status.get(field), expected, f"status {index}.{field}", failures)
        if (
            not isinstance(status.get("statusRef"), str)
            or _STATUS_REF_PATTERN.fullmatch(status["statusRef"]) is None
        ):
            failures.append(f"credential status {index}.statusRef is invalid")
        status_value = status.get("status")
        if status_value == "active":
            if any(status.get(field) is not None for field in ("effectiveAt", "compromiseAt", "reason")):
                failures.append(f"credential status {index} active fields must be null")
        elif status_value == "revoked":
            _parse_payload_utc(
                status.get("effectiveAt"), f"credential status {index}.effectiveAt", failures
            )
            if status.get("compromiseAt") is not None:
                _parse_payload_utc(
                    status.get("compromiseAt"),
                    f"credential status {index}.compromiseAt",
                    failures,
                )
            reason = status.get("reason")
            if not isinstance(reason, str) or reason not in _REVOCATION_REASONS:
                failures.append(f"credential status {index}.reason is invalid")
        else:
            failures.append(f"credential status {index}.status is invalid")
        if isinstance(status.get("statusRef"), str):
            if status["statusRef"] in statuses:
                failures.append("credential status reference is duplicated")
            statuses[status["statusRef"]] = status
    referenced_statuses = {
        value
        for mapping in mappings.values()
        if isinstance((value := mapping.get("revocationRef")), str)
    }
    if referenced_statuses != set(statuses):
        failures.append("owner binding revocation references do not exactly resolve statuses")

    for label, statement, kind, snapshot_ref, snapshot_sha, revision in (
        (
            "registry root statement",
            registry_statement,
            "registry",
            registry.get("registrySnapshotRef"),
            registry_sha,
            registry.get("revision"),
        ),
        (
            "revocation root statement",
            revocation_statement,
            "revocation",
            revocation.get("revocationSnapshotRef"),
            revocation_sha,
            revocation.get("revision"),
        ),
    ):
        statement = _payload_object(statement, ROOT_STATEMENT_FIELDS, label, failures)
        for field, expected in (
            ("documentType", "aetherlink.v1-g0-owner-registry-root-signature-statement"),
            ("schemaVersion", 1),
            ("domain", "aetherlink-owner-registry-root-v1"),
            ("snapshotKind", kind),
            ("snapshotRef", snapshot_ref),
            ("snapshotSha256", snapshot_sha),
            ("registryId", registry.get("registryId")),
            ("revision", revision),
        ):
            _require_exact(statement.get(field), expected, f"{label}.{field}", failures)
        for field in ROOT_SELECTOR_FIELDS:
            if statement.get(field) is not None:
                failures.append(f"{label}.{field} must remain null")

    if not isinstance(role_envelope_blobs, tuple) or len(role_envelope_blobs) != 14:
        failures.append("role envelopes must contain exactly fourteen supplied blobs")
        role_envelope_blobs = ()
    if not isinstance(role_signature_blobs, tuple) or len(role_signature_blobs) != 14:
        failures.append("role signatures must contain exactly fourteen supplied blobs")
        role_signature_blobs = ()
    role_records: list[dict[str, object]] = []
    shared: dict[str, object] = {}
    for index, role in enumerate(_EXPECTED_ROLE_ORDER):
        envelope_raw, envelope = _parse_canonical_payload(
            role_envelope_blobs[index] if index < len(role_envelope_blobs) else None,
            f"role envelope {index}",
            MAX_PAYLOAD_STRING_BYTES * 8,
            failures,
        )
        envelope = _payload_object(
            envelope, ROLE_ENVELOPE_PAYLOAD_FIELDS, f"role envelope {index}", failures
        )
        mapping = mappings.get(role, {})
        credential = credentials.get(str(mapping.get("credentialRef")), {})
        signature = _parse_ed25519_sshsig(
            role_signature_blobs[index] if index < len(role_signature_blobs) else None,
            credential_wires.get(str(mapping.get("credentialRef"))),
            f"role signature {index}",
            failures,
        )
        status = statuses.get(str(mapping.get("revocationRef")), {})
        expected_candidate = _expected_role_mapping(role)
        for field, expected in (
            ("documentType", "aetherlink.v1-g0-owner-role-auth-envelope"),
            ("schemaVersion", 1),
            ("domain", "aetherlink-owner-bootstrap-v1"),
            ("principalRef", EXPECTED_PRINCIPAL["principalRef"]),
            ("role", role),
            ("ownerBindingRef", mapping.get("ownerBindingRef")),
            ("ownerIdentityRef", mapping.get("ownerIdentityRef")),
            ("credentialRef", mapping.get("credentialRef")),
            ("publicKeyBlobSha256", credential.get("publicKeyBlobSha256")),
            ("receiptRef", expected_candidate["receiptRefCandidate"]),
            ("identityRegistryRevision", registry.get("revision")),
            ("registrySnapshotSha256", registry_sha),
            ("revocationSnapshotSha256", revocation_sha),
            ("keyEpoch", credential.get("keyEpoch")),
        ):
            _require_exact(envelope.get(field), expected, f"envelope {role}.{field}", failures)
        if status.get("status") != "active":
            failures.append(f"envelope {role} uses a non-active credential")
        for field in (
            "receiptRawSha256",
            "receiptCanonicalSha256",
            "targetBindingSha256",
        ):
            if not _valid_sha256(envelope.get(field)):
                failures.append(f"envelope {role}.{field} is invalid")
        if not _valid_nonce(envelope.get("nonceBase64Url")):
            failures.append(f"envelope {role}.nonceBase64Url is invalid")
        issued = _parse_payload_utc(
            envelope.get("issuedAt"), f"envelope {role}.issuedAt", failures
        )
        expires = _parse_payload_utc(
            envelope.get("expiresAt"), f"envelope {role}.expiresAt", failures
        )
        if issued is not None and expires is not None and (expires - issued).total_seconds() != 600:
            failures.append(f"envelope {role} TTL is not exactly 600 seconds")
        for field in ("bundleId", "challengeIssuerRef", "challengeId", "audience"):
            if not _valid_ascii_ref(envelope.get(field)):
                failures.append(f"envelope {role}.{field} is invalid")
        if index == 0:
            shared = {
                field: envelope.get(field)
                for field in (
                    "bundleId",
                    "targetBindingSha256",
                    "challengeIssuerRef",
                    "audience",
                )
            }
        else:
            for field, expected in shared.items():
                _require_exact(envelope.get(field), expected, f"envelope {role}.{field}", failures)
        role_records.append(
            {
                "role": role,
                "ownerBindingRef": envelope.get("ownerBindingRef"),
                "ownerIdentityRef": envelope.get("ownerIdentityRef"),
                "credentialRef": envelope.get("credentialRef"),
                "keyEpoch": envelope.get("keyEpoch"),
                "publicKeyBlobSha256": envelope.get("publicKeyBlobSha256"),
                "receiptRef": envelope.get("receiptRef"),
                "receiptRawSha256": envelope.get("receiptRawSha256"),
                "receiptCanonicalSha256": envelope.get("receiptCanonicalSha256"),
                "challengeId": envelope.get("challengeId"),
                "nonceBase64Url": envelope.get("nonceBase64Url"),
                "envelopeSha256": hashlib.sha256(envelope_raw or b"").hexdigest(),
                "signatureSha256": hashlib.sha256(signature or b"").hexdigest(),
            }
        )

    manifest = _payload_object(
        manifest, MANIFEST_PAYLOAD_FIELDS, "owner role manifest", failures
    )
    for field, expected in (
        ("documentType", "aetherlink.v1-g0-owner-role-auth-bundle-manifest"),
        ("schemaVersion", 1),
        ("domain", "aetherlink-owner-bootstrap-v1"),
        ("principalRef", EXPECTED_PRINCIPAL["principalRef"]),
        ("identityRegistryRevision", registry.get("revision")),
        ("registrySnapshotSha256", registry_sha),
        ("revocationSnapshotSha256", revocation_sha),
        *tuple(shared.items()),
    ):
        _require_exact(manifest.get(field), expected, f"manifest.{field}", failures)
    manifest_entries = manifest.get("orderedRoleEntries")
    if not isinstance(manifest_entries, list) or len(manifest_entries) != 14:
        failures.append("manifest orderedRoleEntries must contain exactly fourteen records")
        manifest_entries = []
    for index, expected in enumerate(role_records):
        entry = _payload_object(
            manifest_entries[index] if index < len(manifest_entries) else None,
            MANIFEST_ROLE_ENTRY_FIELDS,
            f"manifest role entry {index}",
            failures,
        )
        _require_exact(entry, expected, f"manifest role entry {index}", failures)

    sidecar = _payload_object(
        sidecar, DORMANT_SIDECAR_FIELDS, "dormant adapter sidecar", failures
    )
    for field, expected in (
        ("documentType", EXPECTED_ADAPTER["dormantSidecarDocumentType"]),
        ("schemaVersion", 1),
        ("status", EXPECTED_ADAPTER["dormantSidecarStatus"]),
        ("registrySnapshotSha256", registry_sha),
        ("registryRevision", registry.get("revision")),
        ("committedRevocationSnapshotSha256", revocation_sha),
        ("committedRevocationRevision", revocation.get("revision")),
        ("evaluatedLatestRevocationSnapshotSha256", revocation_sha),
        ("evaluatedLatestRevocationRevision", revocation.get("revision")),
    ):
        _require_exact(sidecar.get(field), expected, f"sidecar.{field}", failures)
    sidecar_entries = sidecar.get("orderedRoleResults")
    if not isinstance(sidecar_entries, list) or len(sidecar_entries) != 14:
        failures.append("sidecar orderedRoleResults must contain exactly fourteen records")
        sidecar_entries = []
    for index, record in enumerate(role_records):
        expected = {field: record[field] for field in DORMANT_ROLE_RESULT_FIELDS}
        entry = _payload_object(
            sidecar_entries[index] if index < len(sidecar_entries) else None,
            DORMANT_ROLE_RESULT_FIELDS,
            f"sidecar role result {index}",
            failures,
        )
        _require_exact(entry, expected, f"sidecar role result {index}", failures)

    if PAYLOAD_DORMANT_MESSAGE not in failures:
        failures.append(PAYLOAD_DORMANT_MESSAGE)
    return tuple(failures)


def collect_owner_trust_bootstrap_v2_failures(
    profile_bytes: object,
    *,
    predecessor_bytes: object,
    lineage_blobs: object,
) -> tuple[str, ...]:
    """Validate supplied bytes while always retaining the dormant boundary."""

    failures: list[str] = []
    profile_raw = receipt._bounded_snapshot(
        profile_bytes,
        "G0 owner trust bootstrap v2 profile",
        MAX_PROFILE_BYTES,
        failures,
    )
    predecessor_raw = receipt._bounded_snapshot(
        predecessor_bytes,
        "G0 owner trust bootstrap v1 predecessor",
        bootstrap_v1.MAX_PROFILE_BYTES,
        failures,
    )

    lineage_snapshots: list[bytes] = []
    if not isinstance(lineage_blobs, tuple) or len(lineage_blobs) != len(receipt.LINEAGE_PATHS):
        failures.append("G0 owner trust bootstrap v2 lineage must contain exactly six blobs")
    else:
        for role, raw, maximum_bytes in zip(
            receipt.LINEAGE_ROLES,
            lineage_blobs,
            receipt.LINEAGE_MAXIMUM_BYTES,
        ):
            snapshot = receipt._bounded_snapshot(
                raw,
                f"G0 owner trust bootstrap v2 lineage {role}",
                maximum_bytes,
                failures,
            )
            if snapshot is not None:
                lineage_snapshots.append(snapshot)

    if predecessor_raw is not None:
        predecessor_failures = bootstrap_v1.collect_dormant_owner_trust_bootstrap_profile_failures(
            predecessor_raw,
            lineage_blobs=tuple(lineage_snapshots),
        )
        if predecessor_failures != (bootstrap_v1.DORMANT_MESSAGE,):
            failures.append("G0 owner trust bootstrap v1 predecessor is not exact and dormant")

    effective_v3: dict[str, object] = {}
    expected_roles: tuple[str, ...] = ()
    if len(lineage_snapshots) == len(receipt.LINEAGE_PATHS):
        failures.extend(receipt._collect_v3_lineage_failures(*lineage_snapshots))
        materialization_failures: list[str] = []
        materialized = receipt._materialize_effective_v3(
            tuple(lineage_snapshots),
            materialization_failures,
        )
        failures.extend(materialization_failures)
        if isinstance(materialized, dict):
            effective_v3 = materialized
            expected_roles, _, _, _, _ = receipt._derive_contract_sets(
                effective_v3,
                failures,
            )
        else:
            failures.append("effective V3 assurance is unavailable")

    profile = (
        receipt._parse_object(
            profile_raw,
            "G0 owner trust bootstrap v2 profile",
            failures,
        )
        if profile_raw is not None
        else None
    )
    if profile is not None:
        receipt._validate_json_resources(
            profile,
            failures,
            root_label="G0 owner trust bootstrap v2 profile",
            maximum_depth=9,
            maximum_items=128,
            maximum_string_bytes=4_096,
        )
        root = receipt._exact_ordered_object(
            profile,
            PROFILE_FIELDS,
            "G0 owner trust bootstrap v2 profile",
            failures,
        )
        for field, expected in (
            ("documentType", "aetherlink.v1-g0-owner-trust-bootstrap-profile"),
            ("schemaVersion", 2),
            ("profileId", "aetherlink_v1_g0_owner_trust_bootstrap_profile_v2"),
            (
                "status",
                "draft_user_selected_principal_and_software_signature_candidate_non_authorizing",
            ),
        ):
            _require_exact(root.get(field), expected, f"profile.{field}", failures)

        supersedes = receipt._exact_ordered_object(
            root.get("supersedes"),
            SUPERSEDES_FIELDS,
            "profile.supersedes",
            failures,
        )
        _require_exact(supersedes, EXPECTED_SUPERSEDES, "profile.supersedes", failures)
        contract_binding = receipt._exact_ordered_object(
            root.get("contractBinding"),
            bootstrap_v1.CONTRACT_FIELDS,
            "profile.contractBinding",
            failures,
        )
        _require_exact(
            contract_binding,
            bootstrap_v1.EXPECTED_CONTRACT_BINDING,
            "profile.contractBinding",
            failures,
        )

        source = receipt._exact_ordered_object(
            root.get("sourceDecision"),
            SOURCE_DECISION_FIELDS,
            "profile.sourceDecision",
            failures,
        )
        _require_exact(source, EXPECTED_SOURCE_DECISION, "profile.sourceDecision", failures)
        principal = receipt._exact_ordered_object(
            root.get("principalCandidate"),
            PRINCIPAL_FIELDS,
            "profile.principalCandidate",
            failures,
        )
        _require_exact(principal, EXPECTED_PRINCIPAL, "profile.principalCandidate", failures)

        if expected_roles:
            _validate_role_candidates(
                root.get("roleIdentityCandidates"),
                expected_roles,
                failures,
            )

        mechanism = receipt._exact_ordered_object(
            root.get("signatureMechanismCandidate"),
            SIGNATURE_MECHANISM_FIELDS,
            "profile.signatureMechanismCandidate",
            failures,
        )
        _require_exact(
            mechanism,
            EXPECTED_SIGNATURE_MECHANISM,
            "profile.signatureMechanismCandidate",
            failures,
        )
        sshsig_wire = receipt._exact_ordered_object(
            root.get("sshsigWireContract"),
            SSHSIG_WIRE_FIELDS,
            "profile.sshsigWireContract",
            failures,
        )
        _require_exact(
            sshsig_wire,
            EXPECTED_SSHSIG_WIRE,
            "profile.sshsigWireContract",
            failures,
        )
        envelope = receipt._exact_ordered_object(
            root.get("detachedEnvelopeContract"),
            DETACHED_ENVELOPE_FIELDS,
            "profile.detachedEnvelopeContract",
            failures,
        )
        _require_exact(
            envelope,
            EXPECTED_DETACHED_ENVELOPE,
            "profile.detachedEnvelopeContract",
            failures,
        )
        manifest = receipt._exact_ordered_object(
            root.get("bundleManifestContract"),
            BUNDLE_MANIFEST_FIELDS,
            "profile.bundleManifestContract",
            failures,
        )
        _require_exact(
            manifest,
            EXPECTED_BUNDLE_MANIFEST,
            "profile.bundleManifestContract",
            failures,
        )
        registry = receipt._exact_ordered_object(
            root.get("registryAndRevocationContract"),
            REGISTRY_FIELDS,
            "profile.registryAndRevocationContract",
            failures,
        )
        _require_exact(
            registry,
            EXPECTED_REGISTRY,
            "profile.registryAndRevocationContract",
            failures,
        )
        trusted_time = receipt._exact_ordered_object(
            root.get("trustedTimeContract"),
            TRUSTED_TIME_FIELDS,
            "profile.trustedTimeContract",
            failures,
        )
        _require_exact(
            trusted_time,
            EXPECTED_TRUSTED_TIME,
            "profile.trustedTimeContract",
            failures,
        )
        replay = receipt._exact_ordered_object(
            root.get("replayContract"),
            REPLAY_FIELDS,
            "profile.replayContract",
            failures,
        )
        _require_exact(replay, EXPECTED_REPLAY, "profile.replayContract", failures)
        transition = receipt._exact_ordered_object(
            root.get("successorTransitionPolicy"),
            SUCCESSOR_TRANSITION_FIELDS,
            "profile.successorTransitionPolicy",
            failures,
        )
        _require_exact(
            transition,
            EXPECTED_SUCCESSOR_TRANSITION,
            "profile.successorTransitionPolicy",
            failures,
        )

        selection = receipt._exact_ordered_object(
            root.get("selection"),
            bootstrap_v1.SELECTION_FIELDS,
            "profile.selection",
            failures,
        )
        _require_exact(
            selection,
            {field: None for field in bootstrap_v1.SELECTION_FIELDS},
            "profile.selection",
            failures,
        )
        adapter = receipt._exact_ordered_object(
            root.get("adapterProjection"),
            ADAPTER_FIELDS,
            "profile.adapterProjection",
            failures,
        )
        _require_exact(adapter, EXPECTED_ADAPTER, "profile.adapterProjection", failures)
        state = receipt._exact_ordered_object(
            root.get("state"),
            STATE_FIELDS,
            "profile.state",
            failures,
        )
        _require_exact(
            state,
            {field: False for field in STATE_FIELDS},
            "profile.state",
            failures,
        )

        approvals = effective_v3.get("approvals")
        if expected_roles and isinstance(approvals, list):
            _require_exact(
                [item.get("role") for item in approvals if isinstance(item, dict)],
                list(expected_roles),
                "effective V3 approval role order",
                failures,
            )

    if profile_raw is not None:
        _require_exact(
            hashlib.sha256(profile_raw).hexdigest(),
            EXPECTED_PROFILE_RAW_SHA256,
            "recorded owner trust bootstrap v2 profile raw SHA-256",
            failures,
        )
    if DORMANT_MESSAGE not in failures:
        failures.append(DORMANT_MESSAGE)
    return tuple(failures)


def _collect_worktree_failures(root: Path = ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    inputs: list[tuple[str, str, int, str]] = [
        (
            bootstrap_v1.PROFILE_PATH,
            "G0 owner trust bootstrap v1 predecessor",
            bootstrap_v1.MAX_PROFILE_BYTES,
            bootstrap_v1.EXPECTED_PROFILE_RAW_SHA256,
        ),
        *[
            (path, f"G0 owner trust bootstrap v2 lineage {role}", maximum, expected)
            for path, role, maximum, expected in zip(
                receipt.LINEAGE_PATHS,
                receipt.LINEAGE_ROLES,
                receipt.LINEAGE_MAXIMUM_BYTES,
                receipt.LINEAGE_RAW_SHA256,
            )
        ],
        (
            PROFILE_PATH,
            "G0 owner trust bootstrap v2 profile",
            MAX_PROFILE_BYTES,
            EXPECTED_PROFILE_RAW_SHA256,
        ),
    ]
    snapshots: list[bytes] = []
    identities: list[tuple[int, int, int, int, int, int]] = []
    for path, label, maximum, _ in inputs:
        try:
            raw, identity = decision.read_g0_content_addressed_snapshot(
                root,
                path,
                label,
                maximum,
            )
        except checkpoint.CheckpointValidationError as error:
            failures.append(str(error))
            continue
        snapshots.append(raw)
        identities.append(identity)
    if failures:
        return tuple(failures)

    predecessor_raw = snapshots[0]
    lineage = tuple(snapshots[1:-1])
    profile_raw = snapshots[-1]
    result = collect_owner_trust_bootstrap_v2_failures(
        profile_raw,
        predecessor_bytes=predecessor_raw,
        lineage_blobs=lineage,
    )
    if result != (DORMANT_MESSAGE,):
        failures.extend(item for item in result if item != DORMANT_MESSAGE)

    for (path, label, maximum, expected), identity in zip(inputs, identities):
        failures.extend(
            decision.collect_g0_final_snapshot_failures(
                root,
                path,
                label,
                maximum,
                identity,
                expected,
            )
        )
    return tuple(failures)


def main() -> int:
    failures = _collect_worktree_failures()
    if failures:
        for failure in failures:
            print(
                f"V1 G0 owner trust bootstrap v2 validation failed: {failure}",
                file=sys.stderr,
            )
        return 1
    print(
        "V1 G0 owner trust bootstrap v2 exactly records github:hanchangha1127 "
        "(GitHub user ID 243786110) as the single unverified principal candidate "
        "for fourteen unique role-scoped identity candidates and records the "
        "software ssh-ed25519 SSHSIG candidate. Private-key handling, trust-anchor "
        "selection, signature verification, adapter construction, receipt acceptance, "
        "G0 exit, and G1a authority remain absent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
