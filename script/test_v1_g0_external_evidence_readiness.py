#!/usr/bin/env python3
"""Mutation tests for the remaining eight dormant G0 evidence profiles."""

from __future__ import annotations

import builtins
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from script import check_v1_g0_external_evidence_readiness as external
from script import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]


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
                    for purpose in external.KEY_PURPOSES
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
                    for role in external.SERVICE_ROLES
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
                    for responsibility in external.CUSTODY_RESPONSIBILITIES
                ],
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
                "rawSha256": external.EXPECTED_PROFILE_RAW_SHA256,
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
            external.EXPECTED_PROFILE_RAW_SHA256,
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
        self.assertEqual(tuple(self.profile_by_kind), tuple(external.SUPPORTED_PAYLOAD_KINDS))

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
        self.assertEqual(len(raw), external.EXPECTED_PLAN_BYTE_LENGTH)
        self.assertEqual(digest, external.EXPECTED_PLAN_RAW_SHA256)
        self.assertEqual(raw, self.encoded(plan))
        self.assertEqual(len(plan["candidateArtifactReservations"]), 8)
        for reservation in plan["candidateArtifactReservations"]:
            self.assertFalse(reservation["artifactPresent"])
            self.assertFalse(reservation["externalValuesSelected"])
            self.assertFalse(reservation["acquisitionAuthorized"])
        self.assertTrue(all(value is False for value in plan["state"].values()))

    def test_all_eight_synthetic_candidates_are_exactly_dormant(self) -> None:
        for kind in self.profile_by_kind:
            with self.subTest(kind=kind):
                self.assertEqual(
                    self.candidate_failures(self.make_candidate(kind)),
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
        for index, (candidate, needle) in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assert_candidate_rejected(candidate, needle)

    def test_digest_only_reference_allowlist_rejects_secret_pii_and_actual_record_fields(self) -> None:
        forbidden = (
            "person:alice-smith:v1",
            "account:123456789:v1",
            "password:syntheticsecret:v1",
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

        candidate = self.make_candidate("distribution_accounts")
        candidate["payload"]["accounts"].reverse()
        cases.append(("distribution_accounts", candidate, ".platform"))

        candidate = self.make_candidate("key_custody_runbook")
        candidate["payload"]["keyClasses"][0]["custodyClass"] = "raw_private_key"
        cases.append(("key_custody_runbook", candidate, "closed set"))

        candidate = self.make_candidate("approved_minimum_current_previous_matrix")
        candidate["payload"]["providers"][0]["previousCandidateVersion"] = "2.0.0"
        cases.append(("approved_minimum_current_previous_matrix", candidate, "versions must be distinct"))

        candidate = self.make_candidate("domain_dns_webpki_owners")
        candidate["payload"]["services"][0]["domainName"] = "localhost"
        cases.append(("domain_dns_webpki_owners", candidate, "domainName is invalid"))

        candidate = self.make_candidate("root_signer_rotation_and_revocation_owners")
        candidate["payload"]["rotationOverlapSeconds"] = False
        cases.append(("root_signer_rotation_and_revocation_owners", candidate, "exact integer"))

        candidate = self.make_candidate("privacy_incident_and_retention_owner_approval")
        candidate["payload"]["retentionSchedule"]["aggregateOperationalMetricsDays"] = 31
        cases.append(("privacy_incident_and_retention_owner_approval", candidate, "retentionSchedule"))

        candidate = self.make_candidate("approved_region_peak_capacity_and_cost_ceiling")
        candidate["payload"]["requiredCapacityMultiplierBasisPoints"] = 10_000
        cases.append(("approved_region_peak_capacity_and_cost_ceiling", candidate, "requiredCapacityMultiplierBasisPoints"))

        for kind, mutated, needle in cases:
            with self.subTest(kind=kind):
                self.assert_candidate_rejected(mutated, needle)

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
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("file I/O")),
            mock.patch.object(os, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network")),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess")),
            mock.patch.object(time, "time", side_effect=AssertionError("clock")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("clock")),
            mock.patch.object(os, "urandom", side_effect=AssertionError("entropy")),
            mock.patch.object(secrets, "token_bytes", side_effect=AssertionError("entropy")),
        ):
            self.assertEqual(self.candidate_failures(candidate_raw), (external.DORMANT_MESSAGE,))

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
        kind = next(iter(self.profile_by_kind))
        reserved = external.ARTIFACT_PATHS[kind]
        for mode in ("file", "directory", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
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
            inserted = False

            def insert_after_first_readback(*args: object, **kwargs: object) -> tuple[str, ...]:
                nonlocal inserted
                result = real_final(*args, **kwargs)
                if not inserted:
                    target = root / reserved
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"synthetic-race")
                    inserted = True
                return result

            with mock.patch.object(
                external.decision,
                "collect_g0_final_snapshot_failures",
                side_effect=insert_after_first_readback,
            ):
                failures = external._collect_worktree_failures(root)
            self.assertTrue(any("must remain absent" in item for item in failures), failures)

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
