#!/usr/bin/env python3
"""Validate the unselected, non-authorizing G0 owner trust bootstrap profile.

The pure entry point consumes supplied bytes only. It does not choose a trust
provider, read a credential, generate or verify a signature, create an adapter
result, change a selector, or derive G0/G1a authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

try:
    from script import check_v1_g0_checkpoint as checkpoint
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_independent_validation_context as independent
    from script import check_v1_g0_receipt_bundle as receipt
except ModuleNotFoundError:
    import check_v1_g0_checkpoint as checkpoint
    import check_v1_g0_decision as decision
    import check_v1_g0_independent_validation_context as independent
    import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = "docs/v1/g0/owner-trust-bootstrap-profile-v1.json"
MAX_PROFILE_BYTES = 65_536
EXPECTED_PROFILE_RAW_SHA256 = (
    "229120fcaf7a03b0920b67466ef281a6e739146da72ffab34c10a1f6ed49542b"
)

__all__ = (
    "DORMANT_MESSAGE",
    "EXPECTED_PROFILE_RAW_SHA256",
    "MAX_PROFILE_BYTES",
    "PROFILE_PATH",
    "collect_dormant_owner_trust_bootstrap_profile_failures",
    "main",
)

DORMANT_MESSAGE = (
    "G0 owner trust bootstrap profile records the user-declared sole-human "
    "ownership model and requires fourteen future role-scoped identity references "
    "but remains unverified, unselected, and non-authorizing; it cannot authenticate "
    "an owner or selector decision, create an adapter result, accept an approval "
    "receipt, close G0, or authorize G1a"
)

PROFILE_FIELDS = (
    "documentType",
    "schemaVersion",
    "profileId",
    "status",
    "contractBinding",
    "v3Reuse",
    "ownershipModel",
    "selection",
    "conditionalPolicies",
    "adapterProjection",
    "state",
)
CONTRACT_FIELDS = (
    "repositoryRef",
    "publicationCommitObjectId",
    "publicationCheckpointPath",
    "publicationCheckpointRawSha256",
    "effectiveAssuranceCanonicalSha256",
    "effectiveClosureCanonicalSha256",
)
V3_REUSE_FIELDS = (
    "ownerRole",
    "blockerId",
    "requiredEvidenceKinds",
    "ownerBindingProfilePointer",
    "approvalReceiptProfilePointer",
    "independentTrustInput",
)
OWNERSHIP_MODEL_FIELDS = (
    "model",
    "declarationStatus",
    "humanPrincipalCount",
    "canonicalRoleCount",
    "canonicalRoleOrderSha256",
    "ownerBindingRefPolicy",
    "ownerIdentityRefPolicy",
    "credentialPolicy",
    "approvalReceiptPolicy",
    "v3CompatibilityPolicy",
    "authorizationEffect",
)
SELECTION_FIELDS = (
    "providerProfileRef",
    "identityRegistryRef",
    "trustAnchorRef",
    "credentialMechanismRef",
    "proofOfControlProfileRef",
    "receiptAuthenticationProfileRef",
    "registrySnapshotProfileRef",
    "revocationSnapshotProfileRef",
    "trustedTimeProfileRef",
    "detachedEnvelopeProfileRef",
)
CONDITIONAL_POLICY_FIELDS = (
    "selectionChangePolicy",
    "successorTrustAdapterPolicy",
    "signatureMechanismPolicy",
    "detachedEnvelopePolicy",
    "replayPolicy",
    "sensitiveMaterialPolicy",
    "releaseEvidenceSeparationPolicy",
    "selectorTransitionPolicy",
)
ADAPTER_PROJECTION_FIELDS = (
    "independentTrustInput",
    "verifiedSubjectFields",
    "integrationStatus",
    "genericCandidateFactoryMaySubstitute",
    "mayCreateAdapterResult",
)
STATE_FIELDS = (
    "providerSelected",
    "trustAnchorSelected",
    "credentialMechanismSelected",
    "ownerIdentityAuthenticated",
    "selectorDecisionAuthenticated",
    "reviewedAdapterResultAvailable",
    "evidenceSelectorsMayChange",
    "approvalReceiptAccepted",
    "receiptActivationAllowed",
    "g0ExitComplete",
    "g1aMayStartNow",
)

EXPECTED_CONTRACT_BINDING = {
    "repositoryRef": receipt.EXPECTED_RECORDED_REPOSITORY_REF,
    "publicationCommitObjectId": receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
    "publicationCheckpointPath": receipt.V3_CHECKPOINT_PATH,
    "publicationCheckpointRawSha256": receipt.LINEAGE_RAW_SHA256[-1],
    "effectiveAssuranceCanonicalSha256": receipt.EXPECTED_EFFECTIVE_V3_SHA256,
    "effectiveClosureCanonicalSha256": receipt.EXPECTED_CLOSURE_V3_SHA256,
}
EXPECTED_V3_REUSE = {
    "ownerRole": "repository_owner",
    "blockerId": "roadmap_and_g0_checkpoint_publication",
    "requiredEvidenceKinds": ["reviewed_commit_scope", "published_checkpoint"],
    "ownerBindingProfilePointer": "/g0ClosureContract/ownerBindingProfile",
    "approvalReceiptProfilePointer": "/g0ClosureContract/approvalReceiptProfile",
    "independentTrustInput": (
        "trusted_owner_identity_registry_and_revocation_snapshot"
    ),
}
EXPECTED_OWNERSHIP_MODEL = {
    "model": "single_human_principal_with_role_scoped_identity_refs",
    "declarationStatus": "user_declared_unverified_non_authorizing",
    "humanPrincipalCount": 1,
    "canonicalRoleCount": 14,
    "canonicalRoleOrderSha256": (
        "51db62b86bfa80ebb7640808b6996f9fc79b27571d50f178a564842ceedd3861"
    ),
    "ownerBindingRefPolicy": (
        "fourteen_unique_role_specific_binding_refs_in_canonical_v3_role_order"
    ),
    "ownerIdentityRefPolicy": (
        "fourteen_unique_nonsecret_role_scoped_opaque_refs_independently_mapped_by_"
        "one_registry_revision_to_the_same_authenticated_human_principal"
    ),
    "credentialPolicy": (
        "same_or_role_specific_credential_refs_allowed_only_when_each_exact_binding_"
        "is_independently_authenticated_valid_and_nonrevoked"
    ),
    "approvalReceiptPolicy": (
        "fourteen_distinct_exact_eight_field_role_receipts_each_authenticated_"
        "against_its_corresponding_role_binding"
    ),
    "v3CompatibilityPolicy": (
        "preserves_v3_raw_owner_identity_ref_uniqueness_without_requiring_distinct_"
        "human_principals"
    ),
    "authorizationEffect": "none",
}
EXPECTED_CONDITIONAL_POLICIES = {
    "selectionChangePolicy": (
        "new_versioned_profile_required_before_any_selection_reference_is_non_null"
    ),
    "successorTrustAdapterPolicy": (
        "successor_profile_must_pin_one_human_principal_fourteen_unique_role_scoped_"
        "owner_identity_refs_owner_identity_credential_registry_revision_"
        "proof_of_control_authenticated_registry_and_revocation_snapshot_acquisition_"
        "provenance_freshness_rollback_accepted_at_validity_revocation_evaluation_"
        "trusted_time_clock_skew_and_exact_bounded_module_owned_adapter_result_"
        "context_handoff"
    ),
    "signatureMechanismPolicy": (
        "if_selected_mechanism_is_signature_based_the_successor_profile_must_pin_"
        "algorithm_encoding_key_usage_key_or_certificate_digest_and_fail_closed_verification"
    ),
    "detachedEnvelopePolicy": (
        "any_challenge_or_nonce_belongs_only_to_a_separately_versioned_detached_"
        "bootstrap_envelope_and_must_not_change_the_exact_eight_field_approval_receipt"
    ),
    "replayPolicy": (
        "successor_profile_must_define_challenge_consumption_and_external_consumed_"
        "bundle_ledger_relationship_before_stateful_activation"
    ),
    "sensitiveMaterialPolicy": (
        "private_keys_tokens_raw_credentials_and_signature_bytes_are_forbidden_in_this_profile"
    ),
    "releaseEvidenceSeparationPolicy": (
        "release_evidence_ed25519_keys_registry_and_envelope_contracts_must_not_be_reused_implicitly"
    ),
    "selectorTransitionPolicy": (
        "authenticated_owner_authenticated_selector_decision_and_a_reviewed_successor_"
        "profile_are_required_before_any_selector_or_authority_state_can_change"
    ),
}


def _require_exact(
    actual: object,
    expected: object,
    label: str,
    failures: list[str],
) -> None:
    if not decision.exactly_equal(actual, expected):
        failures.append(f"{label} is not exact")


def _effective_v3_assurance(
    lineage_blobs: tuple[bytes, ...],
    failures: list[str],
) -> dict[str, object]:
    effective_v3 = receipt._materialize_effective_v3(lineage_blobs, failures)
    if not isinstance(effective_v3, dict):
        failures.append("effective V3 assurance is unavailable")
        return {}
    return effective_v3


def _validate_v3_reuse(
    reuse: dict[str, object],
    closure: dict[str, object],
    failures: list[str],
) -> None:
    blockers = closure.get("blockerRequirements")
    matching = (
        [
            blocker
            for blocker in blockers
            if isinstance(blocker, dict)
            and blocker.get("blockerId") == reuse.get("blockerId")
        ]
        if isinstance(blockers, list)
        else []
    )
    if len(matching) != 1:
        failures.append("effective V3 blocker reuse target is not unique")
    else:
        blocker = matching[0]
        _require_exact(
            blocker.get("requiredOwnerRoles"),
            [reuse.get("ownerRole")],
            "effective V3 owner role projection",
            failures,
        )
        _require_exact(
            blocker.get("requiredEvidenceKinds"),
            reuse.get("requiredEvidenceKinds"),
            "effective V3 required evidence projection",
            failures,
        )

    owner_profile = closure.get("ownerBindingProfile")
    approval_profile = closure.get("approvalReceiptProfile")
    if not isinstance(owner_profile, dict):
        failures.append("effective V3 owner binding profile is unavailable")
    else:
        _require_exact(
            owner_profile.get("exactFields"),
            list(receipt.OWNER_BINDING_FIELDS),
            "effective V3 owner binding fields",
            failures,
        )
    if not isinstance(approval_profile, dict):
        failures.append("effective V3 approval receipt profile is unavailable")
    else:
        _require_exact(
            approval_profile.get("exactFields"),
            list(receipt.APPROVAL_RECEIPT_FIELDS),
            "effective V3 approval receipt fields",
            failures,
        )

    activation = closure.get("receiptActivationPolicy")
    inputs = activation.get("independentTrustInputs") if isinstance(activation, dict) else None
    if (
        not isinstance(inputs, list)
        or inputs.count(reuse.get("independentTrustInput")) != 1
    ):
        failures.append("effective V3 owner trust input reuse is not exact")


def _validate_ownership_model(
    model: dict[str, object],
    effective_v3: dict[str, object],
    closure: dict[str, object],
    failures: list[str],
) -> None:
    role_order, _, _, _, _ = receipt._derive_contract_sets(effective_v3, failures)

    canonical_role_bytes = json.dumps(
        list(role_order),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    _require_exact(
        model.get("canonicalRoleCount"),
        len(role_order),
        "ownership model canonical role count",
        failures,
    )
    _require_exact(
        model.get("canonicalRoleOrderSha256"),
        hashlib.sha256(canonical_role_bytes).hexdigest(),
        "ownership model canonical role order SHA-256",
        failures,
    )

    owner_profile = closure.get("ownerBindingProfile")
    if not isinstance(owner_profile, dict):
        failures.append("effective V3 owner binding profile is unavailable")
    else:
        _require_exact(
            owner_profile.get("rolePolicy"),
            "one_exact_binding_per_role_in_canonical_approval_role_order",
            "effective V3 role-specific owner binding policy",
            failures,
        )
        _require_exact(
            owner_profile.get("identityPolicy"),
            "all_fourteen_owner_identity_refs_nonempty_unique_opaque_nonsecret_and_no_key_or_credential_bytes_in_bundle",
            "effective V3 raw owner identity reference policy",
            failures,
        )

    approval_profile = closure.get("approvalReceiptProfile")
    if not isinstance(approval_profile, dict):
        failures.append("effective V3 approval receipt profile is unavailable")
    else:
        _require_exact(
            approval_profile.get("rolePolicy"),
            "one_exact_receipt_per_role_in_canonical_approval_role_order",
            "effective V3 role-specific approval receipt policy",
            failures,
        )
        _require_exact(
            approval_profile.get("ownerBindingPolicy"),
            "role_and_owner_identity_ref_exactly_equal_the_unique_corresponding_owner_binding",
            "effective V3 approval-to-owner binding policy",
            failures,
        )


def collect_dormant_owner_trust_bootstrap_profile_failures(
    profile_bytes: object,
    *,
    lineage_blobs: object,
) -> tuple[str, ...]:
    """Validate supplied bytes and always retain the dormant authority boundary."""

    failures: list[str] = []
    profile_raw = receipt._bounded_snapshot(
        profile_bytes,
        "G0 owner trust bootstrap profile",
        MAX_PROFILE_BYTES,
        failures,
    )

    lineage_snapshots: list[bytes] = []
    if not isinstance(lineage_blobs, tuple) or len(lineage_blobs) != len(receipt.LINEAGE_PATHS):
        failures.append("G0 owner trust bootstrap lineage must contain exactly six blobs")
    else:
        for role, raw, maximum_bytes in zip(
            receipt.LINEAGE_ROLES,
            lineage_blobs,
            receipt.LINEAGE_MAXIMUM_BYTES,
        ):
            snapshot = receipt._bounded_snapshot(
                raw,
                f"G0 owner trust bootstrap lineage {role}",
                maximum_bytes,
                failures,
            )
            if snapshot is not None:
                lineage_snapshots.append(snapshot)

    if len(lineage_snapshots) == len(receipt.LINEAGE_PATHS):
        failures.extend(receipt._collect_v3_lineage_failures(*lineage_snapshots))

    profile = (
        receipt._parse_object(profile_raw, "G0 owner trust bootstrap profile", failures)
        if profile_raw is not None
        else None
    )
    if profile is not None:
        receipt._validate_json_resources(
            profile,
            failures,
            root_label="G0 owner trust bootstrap profile",
            maximum_depth=8,
            maximum_items=32,
            maximum_string_bytes=4_096,
        )
        root = receipt._exact_ordered_object(
            profile, PROFILE_FIELDS, "G0 owner trust bootstrap profile", failures
        )
        for field, expected in (
            ("documentType", "aetherlink.v1-g0-owner-trust-bootstrap-profile"),
            ("schemaVersion", 1),
            ("profileId", "aetherlink_v1_g0_owner_trust_bootstrap_profile_v1"),
            (
                "status",
                "draft_solo_owner_declared_unselected_non_authorizing",
            ),
        ):
            _require_exact(root.get(field), expected, f"profile.{field}", failures)

        binding = receipt._exact_ordered_object(
            root.get("contractBinding"), CONTRACT_FIELDS, "profile.contractBinding", failures
        )
        _require_exact(binding, EXPECTED_CONTRACT_BINDING, "profile.contractBinding", failures)

        reuse = receipt._exact_ordered_object(
            root.get("v3Reuse"), V3_REUSE_FIELDS, "profile.v3Reuse", failures
        )
        _require_exact(reuse, EXPECTED_V3_REUSE, "profile.v3Reuse", failures)

        ownership_model = receipt._exact_ordered_object(
            root.get("ownershipModel"),
            OWNERSHIP_MODEL_FIELDS,
            "profile.ownershipModel",
            failures,
        )
        _require_exact(
            ownership_model,
            EXPECTED_OWNERSHIP_MODEL,
            "profile.ownershipModel",
            failures,
        )

        selection = receipt._exact_ordered_object(
            root.get("selection"), SELECTION_FIELDS, "profile.selection", failures
        )
        _require_exact(
            selection,
            {field: None for field in SELECTION_FIELDS},
            "profile.selection",
            failures,
        )

        policies = receipt._exact_ordered_object(
            root.get("conditionalPolicies"),
            CONDITIONAL_POLICY_FIELDS,
            "profile.conditionalPolicies",
            failures,
        )
        _require_exact(
            policies,
            EXPECTED_CONDITIONAL_POLICIES,
            "profile.conditionalPolicies",
            failures,
        )

        adapter = receipt._exact_ordered_object(
            root.get("adapterProjection"),
            ADAPTER_PROJECTION_FIELDS,
            "profile.adapterProjection",
            failures,
        )
        projection = independent._projection_payloads(
            {"ownerBindings": [], "approvalReceipts": []},
            target_binding=tuple(EXPECTED_CONTRACT_BINDING.values()),
            trusted_validation_time="1970-01-01T00:00:00Z",
        )[EXPECTED_V3_REUSE["independentTrustInput"]]
        expected_adapter = {
            "independentTrustInput": EXPECTED_V3_REUSE["independentTrustInput"],
            "verifiedSubjectFields": list(projection),
            "integrationStatus": "not_implemented",
            "genericCandidateFactoryMaySubstitute": False,
            "mayCreateAdapterResult": False,
        }
        _require_exact(adapter, expected_adapter, "profile.adapterProjection", failures)

        state = receipt._exact_ordered_object(
            root.get("state"), STATE_FIELDS, "profile.state", failures
        )
        _require_exact(
            state,
            {field: False for field in STATE_FIELDS},
            "profile.state",
            failures,
        )

        if len(lineage_snapshots) == len(receipt.LINEAGE_PATHS):
            effective_v3 = _effective_v3_assurance(tuple(lineage_snapshots), failures)
            closure = effective_v3.get("g0ClosureContract")
            if not isinstance(closure, dict):
                failures.append("effective V3 g0ClosureContract is unavailable")
            else:
                _validate_v3_reuse(reuse, closure, failures)
                _validate_ownership_model(
                    ownership_model,
                    effective_v3,
                    closure,
                    failures,
                )

    if profile_raw is not None:
        _require_exact(
            hashlib.sha256(profile_raw).hexdigest(),
            EXPECTED_PROFILE_RAW_SHA256,
            "recorded owner trust bootstrap profile raw SHA-256",
            failures,
        )
    if DORMANT_MESSAGE not in failures:
        failures.append(DORMANT_MESSAGE)
    return tuple(failures)


def _collect_worktree_failures(root: Path = ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    lineage: list[bytes] = []
    identities: list[tuple[int, int, int, int, int, int]] = []
    for role, path, maximum_bytes in zip(
        receipt.LINEAGE_ROLES,
        receipt.LINEAGE_PATHS,
        receipt.LINEAGE_MAXIMUM_BYTES,
    ):
        try:
            raw, identity = decision.read_g0_content_addressed_snapshot(
                root, path, f"G0 owner trust bootstrap lineage {role}", maximum_bytes
            )
        except checkpoint.CheckpointValidationError as error:
            failures.append(str(error))
            continue
        lineage.append(raw)
        identities.append(identity)
    try:
        profile_raw, profile_identity = decision.read_g0_content_addressed_snapshot(
            root, PROFILE_PATH, "G0 owner trust bootstrap profile", MAX_PROFILE_BYTES
        )
    except checkpoint.CheckpointValidationError as error:
        failures.append(str(error))
        return tuple(failures)
    if failures:
        return tuple(failures)

    result = collect_dormant_owner_trust_bootstrap_profile_failures(
        profile_raw,
        lineage_blobs=tuple(lineage),
    )
    if result != (DORMANT_MESSAGE,):
        non_dormant = tuple(item for item in result if item != DORMANT_MESSAGE)
        failures.extend(non_dormant or ("profile did not retain the exact dormant result",))

    for role, path, maximum_bytes, identity, expected_sha256 in zip(
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
                f"G0 owner trust bootstrap lineage {role}",
                maximum_bytes,
                identity,
                expected_sha256,
            )
        )
    failures.extend(
        decision.collect_g0_final_snapshot_failures(
            root,
            PROFILE_PATH,
            "G0 owner trust bootstrap profile",
            MAX_PROFILE_BYTES,
            profile_identity,
            EXPECTED_PROFILE_RAW_SHA256,
        )
    )
    return tuple(failures)


def main() -> int:
    failures = _collect_worktree_failures()
    if failures:
        for failure in failures:
            print(f"V1 G0 owner trust bootstrap validation failed: {failure}", file=sys.stderr)
        return 1
    print(
        "V1 G0 owner trust bootstrap profile is exact, provider-neutral, records the "
        "user-declared sole-human ownership model, and requires fourteen future "
        "unique role-scoped identity references while remaining unverified, "
        "unselected, and non-authorizing. Existing V3 owner-binding and approval-"
        "receipt schemas are reused; no owner, selector, adapter result, receipt, "
        "G0, or G1a state changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
