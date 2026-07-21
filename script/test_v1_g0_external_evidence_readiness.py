#!/usr/bin/env python3
"""Mutation tests for the remaining eight dormant G0 evidence profiles."""

from __future__ import annotations

import ast
import builtins
from contextlib import ExitStack
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from script import check_v1_g0_external_evidence_readiness as external
from script import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROFILE_RAW_SHA256_LITERAL = (
    "8670a9c5a948b5c0e89ffd3fcd6561f4dcb51776a6d5c174f6a12c5a587c9848"
)
EXPECTED_PLAN_BYTE_LENGTH_LITERAL = 5_179
EXPECTED_PLAN_RAW_SHA256_LITERAL = (
    "4764c79d1497c231f4edb920b13bb6b3343addbdccc5d6e8ac0499185022e4fd"
)
EXPECTED_BINDINGS = (
    (
        "owned_application_ids",
        "production_application_namespaces",
        ("production_namespaces_distribution_and_key_custody",),
        ("product_and_distribution_owner",),
    ),
    (
        "distribution_accounts",
        "distribution_account_and_key_owners",
        ("production_namespaces_distribution_and_key_custody",),
        ("release_owner",),
    ),
    (
        "key_custody_runbook",
        "distribution_account_and_key_owners",
        ("production_namespaces_distribution_and_key_custody",),
        ("release_owner",),
    ),
    (
        "approved_minimum_current_previous_matrix",
        "provider_compatibility_baseline",
        ("provider_compatibility_baseline",),
        ("runtime_provider_compatibility_owner",),
    ),
    (
        "domain_dns_webpki_owners",
        "service_domain_dns_and_webpki_owners",
        ("service_identity_and_signer_custody",),
        ("service_identity_owner",),
    ),
    (
        "root_signer_rotation_and_revocation_owners",
        "service_root_and_online_signer_owners",
        ("service_identity_and_signer_custody",),
        ("service_security_owner",),
    ),
    (
        "privacy_incident_and_retention_owner_approval",
        "privacy_incident_and_retention_owners",
        ("privacy_incident_quality_and_operations_ownership",),
        ("privacy_and_incident_owner",),
    ),
    (
        "approved_region_peak_capacity_and_cost_ceiling",
        "relay_region_capacity_and_cost_budget",
        ("relay_region_capacity_and_cost",),
        ("service_operations_owner",),
    ),
)
EXPECTED_KEY_PURPOSES = (
    "android_play_app_signing",
    "android_upload",
    "macos_developer_id_application",
    "macos_notarization",
)
EXPECTED_CUSTODY_CLASSES = (
    "platform_managed_non_exportable",
    "offline_hardware_or_cold",
    "non_exportable_hsm_or_kms",
    "operating_system_keychain",
)
EXPECTED_SERVICE_ROLES = ("allocation_api", "signaling", "turn", "sealed_relay")
EXPECTED_CUSTODY_RESPONSIBILITIES = (
    "offline_root_custody",
    "online_signer_custody",
    "emergency_revocation",
)
EXPECTED_SYNTHETIC_BUDGET_CURRENCY_CODES = frozenset(("KRW",))


class V1G0ExternalEvidenceReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_raw = (ROOT / external.PROFILE_PATH).read_bytes()
        cls.profile = json.loads(cls.profile_raw)
        cls.decision_raw = (ROOT / external.DECISION_PATH).read_bytes()
        cls.baseline_raw = (ROOT / external.BASELINE_PROFILE_PATH).read_bytes()
        cls.supporting_raw = (ROOT / external.SUPPORTING_PROFILE_PATH).read_bytes()
        cls.owner_catalog_raw = (ROOT / external.OWNER_CATALOG_INPUT_PATH).read_bytes()
        cls.lineage = tuple((ROOT / path).read_bytes() for path in receipt.LINEAGE_PATHS)
        cls.profile_by_kind = {
            item["evidenceKind"]: item for item in cls.profile["evidenceProfiles"]
        }

    @staticmethod
    def encoded(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
    def ref(reference_class: str, seed: str, version: int = 1) -> str:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"{reference_class}:sha256:{digest}:v{version}"

    def profile_failures(self, **overrides: object) -> tuple[str, ...]:
        return external.collect_external_evidence_profile_failures(
            overrides.get("profile_bytes", self.profile_raw),
            lineage_blobs=overrides.get("lineage_blobs", self.lineage),
            decision_bytes=overrides.get("decision_bytes", self.decision_raw),
            baseline_profile_bytes=overrides.get("baseline_profile_bytes", self.baseline_raw),
            supporting_profile_bytes=overrides.get("supporting_profile_bytes", self.supporting_raw),
            owner_catalog_input_bytes=overrides.get("owner_catalog_input_bytes", self.owner_catalog_raw),
        )

    def candidate_failures(self, candidate: object, **overrides: object) -> tuple[str, ...]:
        raw = candidate if isinstance(candidate, (bytes, bytearray, memoryview)) else self.encoded(candidate)
        return external.collect_external_evidence_candidate_failures(
            raw,
            profile_bytes=overrides.get("profile_bytes", self.profile_raw),
            lineage_blobs=overrides.get("lineage_blobs", self.lineage),
            decision_bytes=overrides.get("decision_bytes", self.decision_raw),
            baseline_profile_bytes=overrides.get("baseline_profile_bytes", self.baseline_raw),
            supporting_profile_bytes=overrides.get("supporting_profile_bytes", self.supporting_raw),
            owner_catalog_input_bytes=overrides.get("owner_catalog_input_bytes", self.owner_catalog_raw),
        )

    def make_payload(self, kind: str) -> dict[str, object]:
        ref = self.ref
        if kind == "owned_application_ids":
            return {
                "applicationIds": [
                    {
                        "platform": "android",
                        "identifier": "dev.aetherlink.android",
                        "distributionChannel": "google_play_closed_testing_then_staged_production",
                        "ownershipRecordRefCandidate": ref("ownership-record", "android-id"),
                    },
                    {
                        "platform": "macos",
                        "identifier": "dev.aetherlink.runtime",
                        "distributionChannel": "direct_distribution",
                        "ownershipRecordRefCandidate": ref("ownership-record", "macos-id"),
                    },
                ],
                "versionPolicyRefCandidate": ref("policy", "version"),
                "migrationPolicyRefCandidate": ref("policy", "migration"),
            }
        if kind == "distribution_accounts":
            return {
                "accounts": [
                    {
                        "platform": "android",
                        "distributionChannel": "google_play_closed_testing_then_staged_production",
                        "accountOrganizationRefCandidate": ref("account-organization", "android-org"),
                        "accountControlEvidenceRefCandidate": ref("account-control-evidence", "android-control"),
                    },
                    {
                        "platform": "macos",
                        "distributionChannel": "direct_distribution",
                        "accountOrganizationRefCandidate": ref("account-organization", "macos-org"),
                        "accountControlEvidenceRefCandidate": ref("account-control-evidence", "macos-control"),
                    },
                ],
                "accessControlRunbookRefCandidate": ref("runbook", "account-access"),
                "recoveryRunbookRefCandidate": ref("runbook", "account-recovery"),
            }
        if kind == "key_custody_runbook":
            return {
                "keyClasses": [
                    {
                        "keyPurpose": purpose,
                        "custodyClass": "platform_managed_non_exportable",
                        "custodyProviderRefCandidate": ref("custody-provider", f"{purpose}-provider"),
                        "accessPolicyRefCandidate": ref("policy", f"{purpose}-access"),
                        "rotationPolicyRefCandidate": ref("policy", f"{purpose}-rotation"),
                        "recoveryPolicyRefCandidate": ref("policy", f"{purpose}-recovery"),
                        "emergencyRevocationRefCandidate": ref("runbook", f"{purpose}-revoke"),
                    }
                    for purpose in EXPECTED_KEY_PURPOSES
                ],
                "custodyRunbookRefCandidate": ref("runbook", "key-custody"),
                "separationOfDutiesPolicyRefCandidate": ref("policy", "key-separation"),
            }
        if kind == "approved_minimum_current_previous_matrix":
            return {
                "matrixRevisionRefCandidate": ref("matrix", "provider-matrix"),
                "providers": [
                    {
                        "providerId": provider,
                        "minimumCandidateVersion": "1.0.0",
                        "currentCandidateVersion": "2.0.0",
                        "previousCandidateVersion": "1.9.0",
                        "compatibilityProfileRefCandidate": ref("compatibility-profile", provider),
                        "evidenceRefCandidates": [
                            ref("evidence-record", f"{provider}-current"),
                            ref("evidence-record", f"{provider}-previous"),
                        ],
                    }
                    for provider in ("ollama", "lm_studio")
                ],
                "testPolicyRefCandidate": ref("policy", "provider-test"),
            }
        if kind == "domain_dns_webpki_owners":
            return {
                "services": [
                    {
                        "serviceRole": role,
                        "domainName": f"{role.replace('_', '-')}.aetherlink.invalid",
                        "domainOwnershipRecordRefCandidate": ref("domain-ownership", role),
                        "dnsControlEvidenceRefCandidate": ref("dns-control", role),
                        "webpkiLifecycleRefCandidate": ref("webpki-lifecycle", role),
                        "renewalMonitoringRefCandidate": ref("renewal-monitoring", role),
                    }
                    for role in EXPECTED_SERVICE_ROLES
                ],
                "lifecycleRunbookRefCandidate": ref("runbook", "domain-lifecycle"),
            }
        if kind == "root_signer_rotation_and_revocation_owners":
            return {
                "custodyAssignments": [
                    {
                        "responsibility": responsibility,
                        "assignmentRecordRefCandidate": ref("assignment-record", responsibility),
                        "custodyProfileRefCandidate": ref("custody-profile", responsibility),
                    }
                    for responsibility in EXPECTED_CUSTODY_RESPONSIBILITIES
                ],
                "offlineRootCustodyPolicy": "offline_hsm_or_cold_custody_with_two_person_approval",
                "onlineSignerCustodyPolicy": "non_exportable_kms_or_hsm_with_overlap_rotation",
                "emergencyRevocationSeparatedFromReleaseSigning": True,
                "releaseSigningAssignmentRefCandidate": ref("assignment-record", "release-signing"),
                "rotationOverlapSeconds": 86_400,
                "rotationPolicyRefCandidate": ref("policy", "service-rotation"),
                "keyCeremonyRunbookRefCandidate": ref("runbook", "key-ceremony"),
                "separationOfDutiesPolicyRefCandidate": ref("policy", "service-separation"),
            }
        if kind == "privacy_incident_and_retention_owner_approval":
            return {
                "privacyPolicyRefCandidate": ref("policy", "privacy"),
                "retentionSchedule": {
                    "aggregateOperationalMetricsDays": 30,
                    "sourceFreeSecurityEventsDays": 7,
                    "sanitizedIncidentEvidenceDays": 90,
                    "contentFreeReleaseRecordsDays": 365,
                    "expiredAuthorizationStateDeletionSeconds": 30,
                },
                "dataDeletionRunbookRefCandidate": ref("runbook", "deletion"),
                "incidentResponseRunbookRefCandidate": ref("runbook", "incident"),
                "notificationPolicyRefCandidate": ref("policy", "notification"),
                "policyReviewRecordRefCandidate": ref("review-record", "privacy-review"),
            }
        if kind == "approved_region_peak_capacity_and_cost_ceiling":
            return {
                "regions": [
                    {
                        "regionCode": "kr-central",
                        "providerRegionRefCandidate": ref("provider-region", "kr-central"),
                    }
                ],
                "projectedPeakConcurrentSessions": 1_000,
                "requiredCapacityMultiplierBasisPoints": 20_000,
                "monthlyCostCeilingMinorUnits": 1_000_000,
                "currency": "KRW",
                "capacityForecastRefCandidate": ref("capacity-forecast", "relay-forecast"),
                "loadModelRefCandidate": ref("load-model", "relay-load"),
                "budgetReviewRecordRefCandidate": ref("review-record", "relay-budget"),
            }
        raise AssertionError(kind)

    def make_candidate(self, kind: str) -> dict[str, object]:
        profile = self.profile_by_kind[kind]
        contract = self.profile["contractBinding"]
        common = self.profile["commonEnvelopeProfile"]
        return {
            "documentType": "aetherlink.v1-g0-external-evidence-candidate",
            "schemaVersion": 1,
            "artifactId": profile["artifactId"],
            "evidenceKind": kind,
            "status": "synthetic_fixture_unverified_non_authorizing",
            "profileRef": {
                "path": external.PROFILE_PATH,
                "profileId": self.profile["profileId"],
                "rawSha256": EXPECTED_PROFILE_RAW_SHA256_LITERAL,
            },
            "contractBinding": {
                "repositoryRef": contract["repositoryRef"],
                "publicationCommitObjectId": contract["publicationCommitObjectId"],
                "publicationCheckpointPath": contract["publicationCheckpointPath"],
                "publicationCheckpointRawSha256": contract["publicationCheckpointRawSha256"],
                "effectiveAssuranceCanonicalSha256": contract["effectiveAssuranceCanonicalSha256"],
                "effectiveClosureCanonicalSha256": contract["effectiveClosureCanonicalSha256"],
                "decisionId": contract["decisionId"],
                "decisionCanonicalSha256": contract["decisionCanonicalSha256"],
                "blockerId": profile["blockerId"],
                "requiredCheckIds": profile["requiredCheckIds"],
                "requiredOwnerRoles": profile["requiredOwnerRoles"],
                "evidenceKind": kind,
            },
            "intakeBinding": {
                "candidateVersion": 1,
                "reservedArtifactPath": profile["candidatePath"],
                "selectorState": "not_selected",
                "ownerBindingRefCandidate": None,
                "evidenceInputRefCandidate": None,
                "supportingArtifactPresent": False,
                "supportingArtifactRefCandidate": None,
            },
            "payload": self.make_payload(kind),
            "trustBoundary": copy.deepcopy(common["trustBoundaryFixedValues"]),
            "state": copy.deepcopy(common["stateFixedValues"]),
        }

    def assert_candidate_rejected(self, candidate: dict[str, object], needle: str) -> None:
        failures = self.candidate_failures(candidate)
        self.assertEqual(failures[-1], external.DORMANT_MESSAGE)
        self.assertTrue(any(needle in failure for failure in failures[:-1]), failures)

    def test_exact_profile_derives_eight_after_content_addressed_five_plus_two(self) -> None:
        self.assertEqual(self.profile_failures(), ())
        self.assertEqual(
            hashlib.sha256(self.profile_raw).hexdigest(),
            EXPECTED_PROFILE_RAW_SHA256_LITERAL,
        )
        self.assertEqual(
            external.EXPECTED_PROFILE_RAW_SHA256,
            EXPECTED_PROFILE_RAW_SHA256_LITERAL,
        )
        contract = self.profile["contractBinding"]
        coverage = self.profile["coverageDerivation"]
        self.assertEqual(contract["totalNonDerivedEvidenceKindCount"], 15)
        self.assertEqual(len(contract["existingTypedEvidenceKinds"]), 7)
        self.assertEqual(len(contract["requiredEvidenceKinds"]), 8)
        self.assertEqual(len(contract["coveredBlockerIds"]), 7)
        self.assertEqual(len(contract["requiredCheckIds"]), 5)
        self.assertEqual(len(contract["requiredOwnerRoles"]), 7)
        self.assertEqual(
            coverage["effectiveV3NonDerivedKindsCanonicalSha256"],
            "f94b99d98af42052e37b73074b2d67be8155cdb3da3a8ba37d04f69923fa4ee4",
        )
        self.assertEqual(
            coverage["existingTypedKindsCanonicalSha256"],
            "65e119092dee2e27baba3f4dd37a3bf39cb3618d6dcefaafd97147bbe8846a7f",
        )
        self.assertEqual(
            coverage["remainingKindsCanonicalSha256"],
            "cafe2e1a02a2beac873dfc93933a8a7187d8e3a30b99cc12f244666dadde48c9",
        )
        self.assertEqual(tuple(self.profile_by_kind), tuple(item[0] for item in EXPECTED_BINDINGS))
        self.assertEqual(external.KEY_PURPOSES, EXPECTED_KEY_PURPOSES)
        self.assertEqual(external.CUSTODY_CLASSES, EXPECTED_CUSTODY_CLASSES)
        self.assertEqual(external.SERVICE_ROLES, EXPECTED_SERVICE_ROLES)
        self.assertEqual(
            external.CUSTODY_RESPONSIBILITIES,
            EXPECTED_CUSTODY_RESPONSIBILITIES,
        )
        self.assertEqual(
            external.PROFILE_V1_SYNTHETIC_BUDGET_CURRENCY_CODES,
            EXPECTED_SYNTHETIC_BUDGET_CURRENCY_CODES,
        )

    def test_plan_is_deterministic_dormant_and_pins_all_absent_reservations(self) -> None:
        raw, digest = external.compile_dormant_external_evidence_readiness_plan(
            self.profile_raw,
            lineage_blobs=self.lineage,
            decision_bytes=self.decision_raw,
            baseline_profile_bytes=self.baseline_raw,
            supporting_profile_bytes=self.supporting_raw,
            owner_catalog_input_bytes=self.owner_catalog_raw,
        )
        plan = json.loads(raw)
        self.assertEqual(len(raw), EXPECTED_PLAN_BYTE_LENGTH_LITERAL)
        self.assertEqual(digest, EXPECTED_PLAN_RAW_SHA256_LITERAL)
        self.assertEqual(external.EXPECTED_PLAN_BYTE_LENGTH, EXPECTED_PLAN_BYTE_LENGTH_LITERAL)
        self.assertEqual(external.EXPECTED_PLAN_RAW_SHA256, EXPECTED_PLAN_RAW_SHA256_LITERAL)
        self.assertEqual(raw, self.encoded(plan))
        self.assertEqual(len(plan["candidateArtifactReservations"]), 8)
        for reservation in plan["candidateArtifactReservations"]:
            self.assertFalse(reservation["artifactPresent"])
            self.assertFalse(reservation["externalValuesSelected"])
            self.assertFalse(reservation["acquisitionAuthorized"])
        self.assertTrue(all(value is False for value in plan["state"].values()))

    def test_all_eight_synthetic_candidates_are_exactly_dormant(self) -> None:
        expected_state = {
            "ownerIdentityAuthenticated": False,
            "evidenceVerified": False,
            "approvalReceiptAccepted": False,
            "blockerClosureDerived": False,
            "receiptActivationAllowed": False,
            "g0ExitComplete": False,
            "g1aMayStartNow": False,
        }
        expected_trust = {
            "observationClass": "synthetic_fixture_unverified",
            "independentInputsPresent": [],
            "requiredIndependentInputsAbsent": [
                "authenticated_owner_binding_and_approval_receipt",
                "independent_external_source_provenance",
                "independent_exact_artifact_verification",
                "trusted_validation_time",
            ],
            "ownerIdentityAuthenticated": False,
            "externalFactsVerified": False,
            "catalogRecordDerivable": False,
            "approvalReceiptDerivable": False,
            "authorityDerivable": False,
        }
        for kind, blocker, checks, roles in EXPECTED_BINDINGS:
            with self.subTest(kind=kind):
                candidate = self.make_candidate(kind)
                self.assertEqual(candidate["documentType"], "aetherlink.v1-g0-external-evidence-candidate")
                self.assertEqual(candidate["schemaVersion"], 1)
                self.assertEqual(candidate["artifactId"], f"g0-{kind.replace('_', '-')}-candidate-v1")
                self.assertEqual(candidate["status"], "synthetic_fixture_unverified_non_authorizing")
                self.assertEqual(candidate["contractBinding"]["blockerId"], blocker)
                self.assertEqual(candidate["contractBinding"]["requiredCheckIds"], list(checks))
                self.assertEqual(candidate["contractBinding"]["requiredOwnerRoles"], list(roles))
                self.assertEqual(
                    candidate["intakeBinding"],
                    {
                        "candidateVersion": 1,
                        "reservedArtifactPath": f"docs/evidence/g0-{kind.replace('_', '-')}-candidate-v1.json",
                        "selectorState": "not_selected",
                        "ownerBindingRefCandidate": None,
                        "evidenceInputRefCandidate": None,
                        "supportingArtifactPresent": False,
                        "supportingArtifactRefCandidate": None,
                    },
                )
                self.assertEqual(candidate["trustBoundary"], expected_trust)
                self.assertEqual(candidate["state"], expected_state)
                self.assertEqual(
                    self.candidate_failures(candidate),
                    (external.DORMANT_MESSAGE,),
                )

    def test_cross_kind_unknown_reordered_and_promoted_candidates_fail_closed(self) -> None:
        base = self.make_candidate("owned_application_ids")
        mutations = []
        changed = copy.deepcopy(base)
        changed["payload"] = self.make_payload("distribution_accounts")
        mutations.append((changed, "candidate.payload"))
        changed = dict(reversed(tuple(base.items())))
        mutations.append((changed, "fields or field order"))
        changed = copy.deepcopy(base)
        changed["evidenceKind"] = "owner_acceptance"
        mutations.append((changed, "unsupported"))
        changed = copy.deepcopy(base)
        changed["status"] = "verified"
        mutations.append((changed, "candidate.status"))
        changed = copy.deepcopy(base)
        changed["state"]["g0ExitComplete"] = True
        mutations.append((changed, "candidate.state"))
        changed = copy.deepcopy(base)
        changed["trustBoundary"]["externalFactsVerified"] = True
        mutations.append((changed, "candidate.trustBoundary"))
        changed = copy.deepcopy(base)
        changed["intakeBinding"]["selectorState"] = "selected"
        mutations.append((changed, "candidate.intakeBinding"))
        changed = copy.deepcopy(base)
        changed["intakeBinding"]["supportingArtifactPresent"] = True
        mutations.append((changed, "candidate.intakeBinding"))
        for field in (
            "ownerBindingRefCandidate",
            "evidenceInputRefCandidate",
            "supportingArtifactRefCandidate",
        ):
            changed = copy.deepcopy(base)
            changed["intakeBinding"][field] = self.ref("assignment-record", field)
            mutations.append((changed, "candidate.intakeBinding"))
        for field in (
            "ownerIdentityAuthenticated",
            "externalFactsVerified",
            "catalogRecordDerivable",
            "approvalReceiptDerivable",
            "authorityDerivable",
        ):
            changed = copy.deepcopy(base)
            changed["trustBoundary"][field] = True
            mutations.append((changed, "candidate.trustBoundary"))
        changed = copy.deepcopy(base)
        changed["trustBoundary"]["independentInputsPresent"] = ["self_asserted"]
        mutations.append((changed, "candidate.trustBoundary"))
        changed = copy.deepcopy(base)
        changed["trustBoundary"]["requiredIndependentInputsAbsent"] = []
        mutations.append((changed, "candidate.trustBoundary"))
        for field in base["state"]:
            changed = copy.deepcopy(base)
            changed["state"][field] = True
            mutations.append((changed, "candidate.state"))
        for index, (candidate, needle) in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assert_candidate_rejected(candidate, needle)

    def test_digest_only_reference_allowlist_rejects_secret_pii_and_actual_record_fields(self) -> None:
        forbidden = (
            "person:alice-smith:v1",
            "account:123456789:v1",
            "password:sha256:" + "a" * 64 + ":v1",
            "token:bearer-token-material:v1",
            "private-key:syntheticpem:v1",
            "alice@example.invalid",
            "+82-10-1234-5678",
            "Bearer synthetic-token",
            "-----BEGIN PRIVATE KEY-----",
            "Authorization: secret",
            "unsanitized log body",
            "artifactBytes:AAAA",
        )
        for value in forbidden:
            candidate = self.make_candidate("owned_application_ids")
            candidate["payload"]["versionPolicyRefCandidate"] = value
            with self.subTest(value=value):
                self.assert_candidate_rejected(candidate, "versioned nonsecret reference")

        reference_fields: tuple[tuple[str, tuple[object, ...], str], ...] = (
            ("owned_application_ids", ("applicationIds", 0, "ownershipRecordRefCandidate"), "ownership-record"),
            ("owned_application_ids", ("versionPolicyRefCandidate",), "policy"),
            ("owned_application_ids", ("migrationPolicyRefCandidate",), "policy"),
            ("distribution_accounts", ("accounts", 0, "accountOrganizationRefCandidate"), "account-organization"),
            ("distribution_accounts", ("accounts", 0, "accountControlEvidenceRefCandidate"), "account-control-evidence"),
            ("distribution_accounts", ("accessControlRunbookRefCandidate",), "runbook"),
            ("distribution_accounts", ("recoveryRunbookRefCandidate",), "runbook"),
            ("key_custody_runbook", ("keyClasses", 0, "custodyProviderRefCandidate"), "custody-provider"),
            ("key_custody_runbook", ("keyClasses", 0, "accessPolicyRefCandidate"), "policy"),
            ("key_custody_runbook", ("keyClasses", 0, "rotationPolicyRefCandidate"), "policy"),
            ("key_custody_runbook", ("keyClasses", 0, "recoveryPolicyRefCandidate"), "policy"),
            ("key_custody_runbook", ("keyClasses", 0, "emergencyRevocationRefCandidate"), "runbook"),
            ("key_custody_runbook", ("custodyRunbookRefCandidate",), "runbook"),
            ("key_custody_runbook", ("separationOfDutiesPolicyRefCandidate",), "policy"),
            ("approved_minimum_current_previous_matrix", ("matrixRevisionRefCandidate",), "matrix"),
            ("approved_minimum_current_previous_matrix", ("providers", 0, "compatibilityProfileRefCandidate"), "compatibility-profile"),
            ("approved_minimum_current_previous_matrix", ("providers", 0, "evidenceRefCandidates", 0), "evidence-record"),
            ("approved_minimum_current_previous_matrix", ("testPolicyRefCandidate",), "policy"),
            ("domain_dns_webpki_owners", ("services", 0, "domainOwnershipRecordRefCandidate"), "domain-ownership"),
            ("domain_dns_webpki_owners", ("services", 0, "dnsControlEvidenceRefCandidate"), "dns-control"),
            ("domain_dns_webpki_owners", ("services", 0, "webpkiLifecycleRefCandidate"), "webpki-lifecycle"),
            ("domain_dns_webpki_owners", ("services", 0, "renewalMonitoringRefCandidate"), "renewal-monitoring"),
            ("domain_dns_webpki_owners", ("lifecycleRunbookRefCandidate",), "runbook"),
            ("root_signer_rotation_and_revocation_owners", ("custodyAssignments", 0, "assignmentRecordRefCandidate"), "assignment-record"),
            ("root_signer_rotation_and_revocation_owners", ("custodyAssignments", 0, "custodyProfileRefCandidate"), "custody-profile"),
            ("root_signer_rotation_and_revocation_owners", ("releaseSigningAssignmentRefCandidate",), "assignment-record"),
            ("root_signer_rotation_and_revocation_owners", ("rotationPolicyRefCandidate",), "policy"),
            ("root_signer_rotation_and_revocation_owners", ("keyCeremonyRunbookRefCandidate",), "runbook"),
            ("root_signer_rotation_and_revocation_owners", ("separationOfDutiesPolicyRefCandidate",), "policy"),
            ("privacy_incident_and_retention_owner_approval", ("privacyPolicyRefCandidate",), "policy"),
            ("privacy_incident_and_retention_owner_approval", ("dataDeletionRunbookRefCandidate",), "runbook"),
            ("privacy_incident_and_retention_owner_approval", ("incidentResponseRunbookRefCandidate",), "runbook"),
            ("privacy_incident_and_retention_owner_approval", ("notificationPolicyRefCandidate",), "policy"),
            ("privacy_incident_and_retention_owner_approval", ("policyReviewRecordRefCandidate",), "review-record"),
            ("approved_region_peak_capacity_and_cost_ceiling", ("regions", 0, "providerRegionRefCandidate"), "provider-region"),
            ("approved_region_peak_capacity_and_cost_ceiling", ("capacityForecastRefCandidate",), "capacity-forecast"),
            ("approved_region_peak_capacity_and_cost_ceiling", ("loadModelRefCandidate",), "load-model"),
            ("approved_region_peak_capacity_and_cost_ceiling", ("budgetReviewRecordRefCandidate",), "review-record"),
        )
        for kind, field_path, expected_class in reference_fields:
            candidate = self.make_candidate(kind)
            container: object = candidate["payload"]
            for part in field_path[:-1]:
                container = container[part]  # type: ignore[index]
            wrong_class = "runbook" if expected_class != "runbook" else "policy"
            container[field_path[-1]] = self.ref(wrong_class, f"wrong-{kind}-{field_path}")  # type: ignore[index]
            with self.subTest(kind=kind, field_path=field_path):
                self.assert_candidate_rejected(candidate, f"exact {expected_class} class")

        for field in receipt.EVIDENCE_RECORD_FIELDS:
            candidate = self.make_candidate("owned_application_ids")
            candidate["payload"][field] = "forbidden"
            with self.subTest(catalog_field=field):
                self.assert_candidate_rejected(candidate, "fields or field order")

    def test_each_payload_contract_rejects_representative_semantic_drift(self) -> None:
        cases: list[tuple[str, object, str]] = []

        candidate = self.make_candidate("owned_application_ids")
        candidate["payload"]["applicationIds"][0]["identifier"] = "com.localagentbridge.android"
        cases.append(("owned_application_ids", candidate, "distinct production"))

        candidate = self.make_candidate("owned_application_ids")
        candidate["payload"]["applicationIds"][0]["distributionChannel"] = "synthetic_channel"
        cases.append(("owned_application_ids", candidate, "distributionChannel"))

        candidate = self.make_candidate("distribution_accounts")
        candidate["payload"]["accounts"].reverse()
        cases.append(("distribution_accounts", candidate, ".platform"))

        candidate = self.make_candidate("distribution_accounts")
        candidate["payload"]["accounts"][0]["distributionChannel"] = "synthetic_channel"
        cases.append(("distribution_accounts", candidate, ".distributionChannel"))

        candidate = self.make_candidate("key_custody_runbook")
        candidate["payload"]["keyClasses"][0]["custodyClass"] = "raw_private_key"
        cases.append(("key_custody_runbook", candidate, "closed set"))

        candidate = self.make_candidate("approved_minimum_current_previous_matrix")
        candidate["payload"]["providers"][0]["previousCandidateVersion"] = "2.0.0"
        cases.append(("approved_minimum_current_previous_matrix", candidate, "current and previous versions must be distinct"))

        candidate = self.make_candidate("approved_minimum_current_previous_matrix")
        candidate["payload"]["providers"][0]["providerId"] = "synthetic_provider"
        cases.append(("approved_minimum_current_previous_matrix", candidate, ".providerId"))

        candidate = self.make_candidate("domain_dns_webpki_owners")
        candidate["payload"]["services"][0]["domainName"] = "localhost"
        cases.append(("domain_dns_webpki_owners", candidate, "domainName is invalid"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        candidate["payload"]["rotationOverlapSeconds"] = False
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "exact integer"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        shared = candidate["payload"]["custodyAssignments"][0]["assignmentRecordRefCandidate"]
        for assignment in candidate["payload"]["custodyAssignments"]:
            assignment["assignmentRecordRefCandidate"] = shared
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "assignment references must be unique"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        candidate["payload"]["custodyAssignments"][1]["custodyProfileRefCandidate"] = candidate["payload"]["custodyAssignments"][0]["custodyProfileRefCandidate"]
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "custody profiles must be unique"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        candidate["payload"]["offlineRootCustodyPolicy"] = "weaker"
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "offlineRootCustodyPolicy"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        candidate["payload"]["onlineSignerCustodyPolicy"] = "weaker"
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "onlineSignerCustodyPolicy"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        candidate["payload"]["emergencyRevocationSeparatedFromReleaseSigning"] = False
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "emergencyRevocationSeparatedFromReleaseSigning"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        candidate["payload"]["releaseSigningAssignmentRefCandidate"] = candidate["payload"]["custodyAssignments"][2]["assignmentRecordRefCandidate"]
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "release-signing assignment must be distinct"))

        candidate = self.make_candidate("privacy_incident_and_retention_owner_approval")
        candidate["payload"]["retentionSchedule"]["aggregateOperationalMetricsDays"] = 31
        cases.append(("privacy_incident_and_retention_owner_approval", candidate, "retentionSchedule"))

        candidate = self.make_candidate("privacy_incident_and_retention_owner_approval")
        candidate["payload"]["retentionSchedule"]["expiredAuthorizationStateDeletionSeconds"] = 31
        cases.append(("privacy_incident_and_retention_owner_approval", candidate, "retentionSchedule"))

        candidate = self.make_candidate("approved_region_peak_capacity_and_cost_ceiling")
        candidate["payload"]["requiredCapacityMultiplierBasisPoints"] = 10_000
        cases.append(("approved_region_peak_capacity_and_cost_ceiling", candidate, "requiredCapacityMultiplierBasisPoints"))

        candidate = self.make_candidate("approved_region_peak_capacity_and_cost_ceiling")
        candidate["payload"]["regions"].append(copy.deepcopy(candidate["payload"]["regions"][0]))
        cases.append(("approved_region_peak_capacity_and_cost_ceiling", candidate, "exactly one initial region"))

        for currency in ("ZZZ", "VED", "HRK", "VEF", "SLL", "CUC", "EUR", "USD"):
            candidate = self.make_candidate("approved_region_peak_capacity_and_cost_ceiling")
            candidate["payload"]["currency"] = currency
            cases.append(("approved_region_peak_capacity_and_cost_ceiling", candidate, "synthetic profile-v1 KRW"))

        for kind, mutated, needle in cases:
            with self.subTest(kind=kind):
                self.assert_candidate_rejected(mutated, needle)

        minimum_equals_previous = self.make_candidate("approved_minimum_current_previous_matrix")
        for provider in minimum_equals_previous["payload"]["providers"]:
            provider["minimumCandidateVersion"] = provider["previousCandidateVersion"]
        self.assertEqual(
            self.candidate_failures(minimum_equals_previous),
            (external.DORMANT_MESSAGE,),
        )

    def test_decision_prior_profiles_lineage_and_owner_catalog_drift_fail_closed(self) -> None:
        drift_cases = (
            {"decision_bytes": self.decision_raw + b" "},
            {"baseline_profile_bytes": self.baseline_raw + b" "},
            {"supporting_profile_bytes": self.supporting_raw + b" "},
            {"owner_catalog_input_bytes": self.owner_catalog_raw + b" "},
            {"lineage_blobs": (self.lineage[0] + b" ", *self.lineage[1:])},
        )
        for overrides in drift_cases:
            with self.subTest(input=next(iter(overrides))):
                self.assertTrue(self.profile_failures(**overrides))

        decision_document = json.loads(self.decision_raw)
        decision_failures: list[str] = []
        constraints = external._validated_decision_constraints(
            self.decision_raw,
            decision_failures,
        )
        self.assertEqual(decision_failures, [])
        release = decision_document["releasePolicy"]
        product = decision_document["productScope"]
        operations = decision_document["operationsAndPrivacy"]
        self.assertEqual(
            constraints["platformChannels"],
            (
                ("android", release["android"]["channel"]),
                ("macos", release["macos"]["channel"]),
            ),
        )
        self.assertEqual(
            constraints["providerIds"],
            tuple(provider["id"] for provider in product["providers"]),
        )
        self.assertEqual(constraints["initialRegionCount"], operations["initialRegionCount"])
        self.assertEqual(constraints["offlineRootCustodyPolicy"], operations["offlineRootCustody"])
        self.assertEqual(constraints["onlineSignerCustodyPolicy"], operations["onlineSignerCustody"])
        self.assertEqual(
            constraints["emergencyRevocationSeparatedFromReleaseSigning"],
            operations["emergencyRevocationSeparatedFromReleaseSigning"],
        )
        self.assertEqual(
            constraints["retentionSchedule"]["expiredAuthorizationStateDeletionSeconds"],
            operations["expiredAuthorizationStateDeletionSeconds"],
        )

        def constraints_for(document: dict[str, object]) -> tuple[dict[str, object], list[str]]:
            raw = self.encoded(document)
            with (
                mock.patch.object(external, "EXPECTED_DECISION_RAW_SHA256", hashlib.sha256(raw).hexdigest()),
                mock.patch.object(
                    external.decision,
                    "EXPECTED_DECISION_CANONICAL_SHA256",
                    external.decision.canonical_json_sha256(document),
                ),
            ):
                local_failures: list[str] = []
                result = external._validated_decision_constraints(raw, local_failures)
            return result, local_failures

        decision_mutations = (
            (("releasePolicy", "android", "channel"), "synthetic_android_channel", "platformChannels"),
            (("operationsAndPrivacy", "initialRegionCount"), 2, "initialRegionCount"),
            (("operationsAndPrivacy", "offlineRootCustody"), "synthetic_offline_policy", "offlineRootCustodyPolicy"),
            (("operationsAndPrivacy", "onlineSignerCustody"), "synthetic_online_policy", "onlineSignerCustodyPolicy"),
            (("operationsAndPrivacy", "emergencyRevocationSeparatedFromReleaseSigning"), False, "emergencyRevocationSeparatedFromReleaseSigning"),
            (("operationsAndPrivacy", "expiredAuthorizationStateDeletionSeconds"), 31, "expiredAuthorizationStateDeletionSeconds"),
        )
        for key_path, replacement, result_key in decision_mutations:
            mutated = copy.deepcopy(decision_document)
            target: object = mutated
            for key in key_path[:-1]:
                target = target[key]  # type: ignore[index]
            target[key_path[-1]] = replacement  # type: ignore[index]
            result, failures = constraints_for(mutated)
            with self.subTest(decision_key=key_path):
                self.assertEqual(failures, [])
                if result_key == "expiredAuthorizationStateDeletionSeconds":
                    self.assertEqual(result["retentionSchedule"][result_key], replacement)
                elif result_key == "platformChannels":
                    self.assertEqual(result[result_key][0][1], replacement)
                else:
                    self.assertEqual(result[result_key], replacement)

        provider_mutation = copy.deepcopy(decision_document)
        provider_mutation["productScope"]["providers"].reverse()
        provider_constraints, provider_failures = constraints_for(provider_mutation)
        self.assertEqual(provider_failures, [])
        self.assertEqual(
            provider_constraints["providerIds"],
            tuple(provider["id"] for provider in provider_mutation["productScope"]["providers"]),
        )

        materialization_failures: list[str] = []
        effective = receipt._materialize_effective_v3(self.lineage, materialization_failures)
        self.assertEqual(materialization_failures, [])
        baseline_profile = json.loads(self.baseline_raw)
        supporting_profile = json.loads(self.supporting_raw)
        owner_catalog = json.loads(self.owner_catalog_raw)
        owner_catalog["responses"][0]["evidenceCandidates"].append(
            {
                "evidenceKind": "owned_application_ids",
                "evidenceInputRefCandidate": "synthetic",
                "supportingArtifactRefCandidate": None,
            }
        )
        failures: list[str] = []
        external._derive_contract(
            effective,
            baseline_profile,
            supporting_profile,
            owner_catalog,
            failures,
        )
        self.assertTrue(any("already has an intake selector" in item for item in failures))

        def derive_failures(
            *,
            effective_override: dict[str, object] | None = None,
            baseline_override: dict[str, object] | None = None,
            supporting_override: dict[str, object] | None = None,
        ) -> list[str]:
            local_failures: list[str] = []
            external._derive_contract(
                effective_override or copy.deepcopy(effective),
                baseline_override or copy.deepcopy(baseline_profile),
                supporting_override or copy.deepcopy(supporting_profile),
                json.loads(self.owner_catalog_raw),
                local_failures,
            )
            return local_failures

        mutated_baseline = copy.deepcopy(baseline_profile)
        mutated_baseline["contractBinding"]["requiredEvidenceKinds"].append(
            mutated_baseline["contractBinding"]["requiredEvidenceKinds"][0]
        )
        self.assertTrue(any("coverage contains duplicates" in item for item in derive_failures(baseline_override=mutated_baseline)))

        split_baseline = copy.deepcopy(baseline_profile)
        split_supporting = copy.deepcopy(supporting_profile)
        moved_kind = split_baseline["contractBinding"]["requiredEvidenceKinds"].pop()
        split_supporting["contractBinding"]["requiredEvidenceKinds"].insert(0, moved_kind)
        split_failures = derive_failures(
            baseline_override=split_baseline,
            supporting_override=split_supporting,
        )
        self.assertTrue(any("exactly five" in item for item in split_failures))
        self.assertTrue(any("exactly two" in item for item in split_failures))

        overlapping = copy.deepcopy(supporting_profile)
        overlapping["contractBinding"]["requiredEvidenceKinds"][0] = baseline_profile["contractBinding"]["requiredEvidenceKinds"][0]
        self.assertTrue(any("coverage overlaps" in item for item in derive_failures(supporting_override=overlapping)))

        unknown = copy.deepcopy(baseline_profile)
        unknown["contractBinding"]["requiredEvidenceKinds"][0] = "owner_acceptance"
        self.assertTrue(any("non-V3 kind" in item for item in derive_failures(baseline_override=unknown)))

        reordered = copy.deepcopy(baseline_profile)
        reordered_kinds = reordered["contractBinding"]["requiredEvidenceKinds"]
        reordered_kinds[0], reordered_kinds[1] = reordered_kinds[1], reordered_kinds[0]
        self.assertTrue(any("canonical order" in item for item in derive_failures(baseline_override=reordered)))

        remaining_kind = EXPECTED_BINDINGS[0][0]
        missing_mapping = copy.deepcopy(effective)
        for blocker in missing_mapping["g0ClosureContract"]["blockerRequirements"]:
            if remaining_kind in blocker["requiredEvidenceKinds"]:
                blocker["requiredEvidenceKinds"].remove(remaining_kind)
        self.assertTrue(
            any(
                "graph cardinalities" in item or "remaining V3 evidence kinds" in item
                for item in derive_failures(effective_override=missing_mapping)
            )
        )

        ambiguous_mapping = copy.deepcopy(effective)
        for blocker in ambiguous_mapping["g0ClosureContract"]["blockerRequirements"]:
            if remaining_kind not in blocker["requiredEvidenceKinds"]:
                blocker["requiredEvidenceKinds"].append(remaining_kind)
                break
        self.assertTrue(any("maps to multiple blockers" in item for item in derive_failures(effective_override=ambiguous_mapping)))

        non_executable_drift = copy.deepcopy(effective)
        covered_check = EXPECTED_BINDINGS[0][2][0]
        non_executable_drift["g0ClosureContract"]["nonExecutableCheckIds"].remove(covered_check)
        self.assertTrue(any("five canonical non-executable checks" in item for item in derive_failures(effective_override=non_executable_drift)))

        non_executable_reordered = copy.deepcopy(effective)
        non_executable_checks = non_executable_reordered["g0ClosureContract"]["nonExecutableCheckIds"]
        first_index = non_executable_checks.index(EXPECTED_BINDINGS[0][2][0])
        second_index = non_executable_checks.index(EXPECTED_BINDINGS[3][2][0])
        non_executable_checks[first_index], non_executable_checks[second_index] = (
            non_executable_checks[second_index],
            non_executable_checks[first_index],
        )
        self.assertTrue(
            any(
                "five canonical non-executable checks" in item
                for item in derive_failures(effective_override=non_executable_reordered)
            )
        )

    def test_duplicate_nonfinite_encoding_and_resource_drift_fail_closed(self) -> None:
        exact = self.encoded(self.make_candidate("owned_application_ids"))
        duplicate = exact.replace(b'"schemaVersion":1,', b'"schemaVersion":1,"schemaVersion":1,', 1)
        nonfinite = exact.replace(b'"schemaVersion":1', b'"schemaVersion":NaN', 1)
        newline = exact + b"\n"
        invalid_utf8 = b"\xff"
        oversized = b"{" + b" " * external.MAX_CANDIDATE_BYTES + b"}"
        for raw in (duplicate, nonfinite, newline, invalid_utf8, oversized):
            with self.subTest(size=len(raw)):
                failures = self.candidate_failures(raw)
                self.assertGreater(len(failures), 1)
                self.assertEqual(failures[-1], external.DORMANT_MESSAGE)

        candidate = self.make_candidate("owned_application_ids")
        candidate["payload"]["versionPolicyRefCandidate"] = "policy:sha256:" + "a" * 513 + ":v1"
        self.assert_candidate_rejected(candidate, "UTF-8 bytes")

    def test_mutable_inputs_are_snapshotted_and_pure_validator_uses_no_io(self) -> None:
        candidate = bytearray(self.encoded(self.make_candidate("owned_application_ids")))
        profile = bytearray(self.profile_raw)
        decision_raw = bytearray(self.decision_raw)
        baseline_raw = bytearray(self.baseline_raw)
        supporting_raw = bytearray(self.supporting_raw)
        owner_raw = bytearray(self.owner_catalog_raw)
        lineage = tuple(bytearray(raw) for raw in self.lineage)
        mutable = (candidate, profile, decision_raw, baseline_raw, supporting_raw, owner_raw, *lineage)
        target_ids = {id(value) for value in mutable}
        mutated: set[int] = set()
        real_snapshot = receipt._bounded_snapshot

        def snapshot_then_mutate(value: object, label: str, maximum: int, failures: list[str]) -> bytes | None:
            snapshot = real_snapshot(value, label, maximum, failures)
            if id(value) in target_ids and id(value) not in mutated:
                assert isinstance(value, bytearray)
                value[0] ^= 1
                mutated.add(id(value))
            return snapshot

        with mock.patch.object(receipt, "_bounded_snapshot", side_effect=snapshot_then_mutate):
            result = external.collect_external_evidence_candidate_failures(
                candidate,
                profile_bytes=profile,
                lineage_blobs=lineage,
                decision_bytes=decision_raw,
                baseline_profile_bytes=baseline_raw,
                supporting_profile_bytes=supporting_raw,
                owner_catalog_input_bytes=owner_raw,
            )
        self.assertEqual(result, (external.DORMANT_MESSAGE,))
        self.assertEqual(mutated, target_ids)

        candidate_raw = self.encoded(self.make_candidate("owned_application_ids"))
        production_sources = (
            Path(external.__file__),
            Path(receipt.__file__),
        )
        forbidden_nondeterministic_import_roots = frozenset(
            ("random", "secrets", "time", "uuid")
        )
        forbidden_nondeterministic_attributes = frozenset(
            (
                "now",
                "utcnow",
                "today",
                "time",
                "time_ns",
                "monotonic",
                "monotonic_ns",
                "perf_counter",
                "perf_counter_ns",
                "process_time",
                "process_time_ns",
                "thread_time",
                "thread_time_ns",
                "sleep",
                "random",
                "randrange",
                "randint",
                "choice",
                "choices",
                "shuffle",
                "sample",
                "token_bytes",
                "token_hex",
                "token_urlsafe",
                "randbelow",
                "randbits",
                "urandom",
                "uuid4",
            )
        )
        static_violations: list[str] = []
        for source_path in production_sources:
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".", 1)[0] in forbidden_nondeterministic_import_roots:
                            static_violations.append(
                                f"{source_path.name}:{node.lineno}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    root = (node.module or "").split(".", 1)[0]
                    if root in forbidden_nondeterministic_import_roots:
                        static_violations.append(
                            f"{source_path.name}:{node.lineno}: from {node.module} import"
                        )
                elif (
                    isinstance(node, ast.Attribute)
                    and node.attr in forbidden_nondeterministic_attributes
                ):
                    static_violations.append(
                        f"{source_path.name}:{node.lineno}: attribute {node.attr}"
                    )
        self.assertEqual(static_violations, [])

        audit_script = r'''
import datetime
import random
import secrets
import sys
import time
from pathlib import Path
from script import check_v1_g0_external_evidence_readiness as external
from script import check_v1_g0_receipt_bundle as receipt

root = Path.cwd()
candidate_raw = sys.stdin.buffer.read()
profile_raw = (root / external.PROFILE_PATH).read_bytes()
decision_raw = (root / external.DECISION_PATH).read_bytes()
baseline_raw = (root / external.BASELINE_PROFILE_PATH).read_bytes()
supporting_raw = (root / external.SUPPORTING_PROFILE_PATH).read_bytes()
owner_raw = (root / external.OWNER_CATALOG_INPUT_PATH).read_bytes()
lineage = tuple((root / path).read_bytes() for path in receipt.LINEAGE_PATHS)

def reject_io(event, args):
    if (
        event == "open"
        or event.startswith("os.")
        or event.startswith("socket.")
        or event.startswith("subprocess.")
        or event.startswith("pty.")
        or event == "ctypes.dlopen"
    ):
        raise AssertionError(f"pure API emitted audit event {event}")

def callable_module(value):
    module = getattr(value, "__module__", None)
    owner = getattr(value, "__self__", None)
    if not module and owner is not None:
        owner_type = owner if isinstance(owner, type) else type(owner)
        module = getattr(owner_type, "__module__", None)
    return module or ""

def reject_nondeterminism(frame, event, value):
    if event == "call":
        module = frame.f_globals.get("__name__", "")
        if module in {"random", "secrets"}:
            raise AssertionError(f"pure API called nondeterministic module {module}")
    elif event == "c_call":
        module = callable_module(value)
        name = getattr(value, "__name__", "")
        if module in {"time", "random", "secrets", "_random"}:
            raise AssertionError(f"pure API called nondeterministic callable {module}.{name}")
        if module == "datetime" and name in {"now", "utcnow", "today"}:
            raise AssertionError(f"pure API called clock callable {module}.{name}")

sys.addaudithook(reject_io)
kwargs = {
    "lineage_blobs": lineage,
    "decision_bytes": decision_raw,
    "baseline_profile_bytes": baseline_raw,
    "supporting_profile_bytes": supporting_raw,
    "owner_catalog_input_bytes": owner_raw,
}
sys.setprofile(reject_nondeterminism)
try:
    assert external.collect_external_evidence_profile_failures(profile_raw, **kwargs) == ()
    assert external.collect_external_evidence_candidate_failures(
        candidate_raw,
        profile_bytes=profile_raw,
        **kwargs,
    ) == (external.DORMANT_MESSAGE,)
    plan_raw, plan_digest = external.compile_dormant_external_evidence_readiness_plan(
        profile_raw,
        **kwargs,
    )
    assert len(plan_raw) == external.EXPECTED_PLAN_BYTE_LENGTH
    assert plan_digest == external.EXPECTED_PLAN_RAW_SHA256
finally:
    sys.setprofile(None)

def expect_profile_blocked(operation):
    sys.setprofile(reject_nondeterminism)
    try:
        operation()
    except AssertionError:
        return
    finally:
        sys.setprofile(None)
    raise AssertionError("profile guard did not reject a nondeterministic operation")

for operation in (
    time.time_ns,
    random.random,
    lambda: random.SystemRandom().randrange(10),
    datetime.datetime.now,
    datetime.datetime.utcnow,
    lambda: secrets.SystemRandom().randrange(10),
):
    expect_profile_blocked(operation)
'''
        audit_result = subprocess.run(
            [sys.executable, "-c", audit_script],
            cwd=ROOT,
            input=candidate_raw,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            audit_result.returncode,
            0,
            audit_result.stderr.decode("utf-8", errors="replace"),
        )
        blocked_operations = (
            mock.patch.object(builtins, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "stat", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "exists", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "lstat", side_effect=AssertionError("file I/O")),
            mock.patch.object(os, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(os, "listdir", side_effect=AssertionError("file I/O")),
            mock.patch.object(os, "scandir", side_effect=AssertionError("file I/O")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network")),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")),
            mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError("network")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess")),
            mock.patch.object(time, "time", side_effect=AssertionError("clock")),
            mock.patch.object(time, "time_ns", side_effect=AssertionError("clock")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("clock")),
            mock.patch.object(time, "monotonic_ns", side_effect=AssertionError("clock")),
            mock.patch.object(time, "perf_counter", side_effect=AssertionError("clock")),
            mock.patch.object(time, "perf_counter_ns", side_effect=AssertionError("clock")),
            mock.patch.object(time, "process_time", side_effect=AssertionError("clock")),
            mock.patch.object(time, "process_time_ns", side_effect=AssertionError("clock")),
            mock.patch.object(time, "thread_time", side_effect=AssertionError("clock")),
            mock.patch.object(time, "thread_time_ns", side_effect=AssertionError("clock")),
            mock.patch.object(time, "sleep", side_effect=AssertionError("clock")),
            mock.patch.object(random, "random", side_effect=AssertionError("entropy")),
            mock.patch.object(random, "randrange", side_effect=AssertionError("entropy")),
            mock.patch.object(random, "randint", side_effect=AssertionError("entropy")),
            mock.patch.object(random, "choice", side_effect=AssertionError("entropy")),
            mock.patch.object(random, "choices", side_effect=AssertionError("entropy")),
            mock.patch.object(random, "shuffle", side_effect=AssertionError("entropy")),
            mock.patch.object(random, "sample", side_effect=AssertionError("entropy")),
            mock.patch.object(random, "SystemRandom", side_effect=AssertionError("entropy")),
            mock.patch.object(os, "urandom", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "token_bytes", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "token_hex", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "token_urlsafe", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "randbelow", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "choice", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "randbits", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "SystemRandom", side_effect=AssertionError("entropy")),
        )
        with ExitStack() as stack:
            for blocked_operation in blocked_operations:
                stack.enter_context(blocked_operation)
            self.assertEqual(self.candidate_failures(candidate_raw), (external.DORMANT_MESSAGE,))
            self.assertEqual(self.profile_failures(), ())
            plan_raw, plan_digest = external.compile_dormant_external_evidence_readiness_plan(
                self.profile_raw,
                lineage_blobs=self.lineage,
                decision_bytes=self.decision_raw,
                baseline_profile_bytes=self.baseline_raw,
                supporting_profile_bytes=self.supporting_raw,
                owner_catalog_input_bytes=self.owner_catalog_raw,
            )
            self.assertEqual(len(plan_raw), EXPECTED_PLAN_BYTE_LENGTH_LITERAL)
            self.assertEqual(plan_digest, EXPECTED_PLAN_RAW_SHA256_LITERAL)

    def populate_worktree(self, root: Path) -> None:
        files = {
            external.PROFILE_PATH: self.profile_raw,
            external.DECISION_PATH: self.decision_raw,
            external.BASELINE_PROFILE_PATH: self.baseline_raw,
            external.SUPPORTING_PROFILE_PATH: self.supporting_raw,
            external.OWNER_CATALOG_INPUT_PATH: self.owner_catalog_raw,
            **dict(zip(receipt.LINEAGE_PATHS, self.lineage)),
        }
        for relative, raw in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def test_worktree_rejects_any_reserved_path_and_absent_to_present_race(self) -> None:
        reserved_paths = tuple(external.ARTIFACT_PATHS.values())
        for reserved in reserved_paths:
            for mode in ("file", "directory", "symlink"):
                with self.subTest(path=reserved, mode=mode), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    target = root / reserved
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if mode == "file":
                        target.write_bytes(b"synthetic")
                    elif mode == "directory":
                        target.mkdir()
                    else:
                        outside = root / "outside"
                        outside.write_bytes(b"synthetic")
                        target.symlink_to(outside)
                    self.assertTrue(external._collect_absent_candidate_failures(root))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.populate_worktree(root)
            real_final = external.decision.collect_g0_final_snapshot_failures
            real_absent = external._collect_absent_candidate_failures
            final_call_count = len(receipt.LINEAGE_PATHS) + 5
            observed_final_calls = 0
            events: list[str] = []

            def insert_after_last_readback(*args: object, **kwargs: object) -> tuple[str, ...]:
                nonlocal observed_final_calls
                observed_final_calls += 1
                events.append(f"final-{observed_final_calls}")
                result = real_final(*args, **kwargs)
                if observed_final_calls == final_call_count:
                    for index, reserved in enumerate(reserved_paths):
                        target = root / reserved
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(f"synthetic-race-{index}".encode("ascii"))
                    events.append("insert")
                return result

            def record_absence(check_root: Path) -> tuple[str, ...]:
                events.append("absence")
                return real_absent(check_root)

            with (
                mock.patch.object(
                    external.decision,
                    "collect_g0_final_snapshot_failures",
                    side_effect=insert_after_last_readback,
                ),
                mock.patch.object(
                    external,
                    "_collect_absent_candidate_failures",
                    side_effect=record_absence,
                ),
            ):
                failures = external._collect_worktree_failures(root)
            self.assertEqual(observed_final_calls, final_call_count)
            self.assertEqual(events[0], "absence")
            self.assertEqual(events[-2:], ["insert", "absence"])
            self.assertEqual(
                sum("must remain absent" in item for item in failures),
                len(reserved_paths),
                failures,
            )

    def test_public_api_exposes_no_factory_accept_verify_or_authority_constructor(self) -> None:
        self.assertEqual(
            external.__all__,
            (
                "DORMANT_MESSAGE",
                "EXPECTED_REMAINING_EVIDENCE_COUNT",
                "PROFILE_PATH",
                "collect_external_evidence_candidate_failures",
                "collect_external_evidence_profile_failures",
                "compile_dormant_external_evidence_readiness_plan",
            ),
        )
        forbidden = ("accept", "activate", "authorize", "verify_actual", "catalog", "receipt", "write", "acquire", "adapter", "factory")
        self.assertFalse(any(any(token in name for token in forbidden) for name in external.__all__))


if __name__ == "__main__":
    unittest.main()
