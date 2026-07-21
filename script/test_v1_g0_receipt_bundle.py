#!/usr/bin/env python3
"""Mutation tests for the dormant V3 G0 receipt-bundle contract lineage."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock

from script import check_v1_g0_decision as decision
from script import check_v1_g0_receipt_bundle as receipt_bundle


ROOT = Path(__file__).resolve().parents[1]


class V1G0ReceiptBundleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_blobs = tuple(
            (ROOT / path).read_bytes() for path in receipt_bundle.LINEAGE_PATHS
        )
        cls.recorded_receipt_raw = (
            ROOT / receipt_bundle.RECORDED_PUBLICATION_RECEIPT_PATH
        ).read_bytes()
        cls.recorded_receipt = json.loads(cls.recorded_receipt_raw)
        cls.owner_catalog_input_raw = (
            ROOT / receipt_bundle.OWNER_CATALOG_INPUT_PATH
        ).read_bytes()
        cls.owner_catalog_input = json.loads(cls.owner_catalog_input_raw)
        cls.evidence_artifact_profile_raw = (
            ROOT / receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_PATH
        ).read_bytes()
        cls.evidence_artifact_profile = json.loads(
            cls.evidence_artifact_profile_raw
        )
        cls.documents = tuple(json.loads(raw) for raw in cls.raw_blobs)
        cls.effective_v2 = decision.apply_assurance_amendment_operations(
            cls.documents[0],
            cls.documents[2]["operations"],
            [],
        )
        cls.effective_v3 = receipt_bundle._apply_v3_operations(
            cls.effective_v2,
            cls.documents[4]["operations"],
            [],
        )
        cls.closure = cls.effective_v3["g0ClosureContract"]
        (
            cls.roles,
            cls.evidence_kinds,
            cls.role_blockers,
            cls.profile_by_check,
            cls.executable_checks,
        ) = receipt_bundle._derive_contract_sets(cls.effective_v3, [])

    @staticmethod
    def encoded(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def make_owner_catalog_preview_proposals() -> list[dict[str, object]]:
        def proposal(
            blocker_id: str,
            disposition: str,
            owners: list[tuple[str, int]],
            evidence: list[tuple[str, int, bool]],
            change_version: int | None,
            item: int,
        ) -> dict[str, object]:
            return {
                "blockerId": blocker_id,
                "requirementDisposition": disposition,
                "ownerCandidates": [
                    {"role": role, "candidateVersion": version}
                    for role, version in owners
                ],
                "evidenceCandidates": [
                    {
                        "evidenceKind": kind,
                        "candidateVersion": version,
                        "supportingArtifactPresent": artifact_present,
                    }
                    for kind, version, artifact_present in evidence
                ],
                "changeRequestCandidateVersion": change_version,
                "inputSessionDate": "20260720",
                "inputSessionItem": item,
            }

        return [
            proposal(
                "g0_assurance_artifacts_and_baseline_gate",
                "proposed_as_written",
                [("repository_quality_owner", 1), ("release_quality_owner", 2)],
                [
                    ("canonical_assurance_hash", 1, False),
                    ("source_hash_readback", 2, True),
                ],
                None,
                1,
            ),
            proposal("roadmap_and_g0_checkpoint_publication", "not_available", [], [], None, 2),
            proposal(
                "quality_measurement_owners",
                "proposed_as_written",
                [("release_quality_owner", 2)],
                [],
                None,
                3,
            ),
            proposal(
                "relay_region_capacity_and_cost_budget",
                "proposed_with_changes",
                [("service_operations_owner", 4)],
                [("approved_region_peak_capacity_and_cost_ceiling", 3, True)],
                5,
                4,
            ),
        ]

    @classmethod
    def owner_catalog_preview_request_bytes(
        cls,
        proposals: list[dict[str, object]],
    ) -> bytes:
        return cls.encoded(
            {
                "documentType": "aetherlink.v1-g0-owner-catalog-preview-request",
                "schemaVersion": 1,
                "proposals": proposals,
            }
        )

    @classmethod
    def make_evidence_artifact_candidate(
        cls,
        evidence_kind: str,
    ) -> dict[str, object]:
        profile = cls.evidence_artifact_profile
        common = profile["commonEnvelopeProfile"]
        if evidence_kind == "reviewed_commit_scope":
            kind_profile = profile["reviewedCommitScopePayloadProfile"]
            payload = {
                **kind_profile["fixedSubject"],
                "scopeEntries": copy.deepcopy(kind_profile["expectedScopeEntries"]),
                "scopeEntriesCanonicalSha256": (
                    kind_profile["expectedScopeEntriesCanonicalSha256"]
                ),
                "reviewClaim": {
                    "disposition": kind_profile["reviewClaimDisposition"],
                    "ownerBindingRefCandidate": "owner-candidate:repository-owner:v1",
                    "inputSourceRefCandidate": "user-input:session-20260721:item-2",
                    "claimedReviewRecordedAt": "2026-07-21T02:00:00Z",
                },
            }
        elif evidence_kind == "published_checkpoint":
            kind_profile = profile["publishedCheckpointPayloadProfile"]
            payload = copy.deepcopy(kind_profile["fixedValues"])
        else:
            raise ValueError(f"unsupported fixture evidence kind: {evidence_kind}")
        selector_snapshot = profile["selectorSnapshotBinding"]
        selector_entry = next(
            entry
            for entry in selector_snapshot["evidenceSelectors"]
            if entry["evidenceKind"] == evidence_kind
        )
        return {
            "documentType": common["fixedValues"]["documentType"],
            "schemaVersion": common["fixedValues"]["schemaVersion"],
            "artifactId": kind_profile["artifactId"],
            "evidenceKind": evidence_kind,
            "status": common["fixedValues"]["status"],
            "profileRef": {
                "path": receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_PATH,
                "profileId": profile["profileId"],
                "rawSha256": (
                    receipt_bundle.EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256
                ),
            },
            "contractBinding": {
                field: profile["contractBinding"][field]
                for field in receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_CONTRACT_FIELDS
            },
            "selectorBinding": {
                "ownerCatalogInputCandidatePath": selector_snapshot[
                    "ownerCatalogInputCandidatePath"
                ],
                "ownerCatalogInputCandidateRawSha256": selector_snapshot[
                    "ownerCatalogInputCandidateRawSha256"
                ],
                "responseIndex": selector_snapshot["responseIndex"],
                "blockerId": selector_snapshot["blockerId"],
                "inputSourceRefCandidate": selector_snapshot[
                    "inputSourceRefCandidate"
                ],
                "ownerBindingRefCandidate": selector_snapshot[
                    "ownerBindingRefCandidate"
                ],
                "evidenceSelectorIndex": selector_entry["evidenceSelectorIndex"],
                "candidateVersion": selector_entry["candidateVersion"],
                "evidenceInputRefCandidate": selector_entry[
                    "evidenceInputRefCandidate"
                ],
                "supportingArtifactPresent": selector_entry[
                    "supportingArtifactPresent"
                ],
                "supportingArtifactRefCandidate": selector_entry[
                    "supportingArtifactRefCandidate"
                ],
                "reservedArtifactPath": selector_entry["reservedArtifactPath"],
            },
            "payload": payload,
            "trustBoundary": {
                "observationClass": "session_observation_only",
                "independentInputsPresent": [],
                "requiredIndependentInputsAbsent": copy.deepcopy(
                    kind_profile["requiredIndependentInputsAbsent"]
                ),
                "catalogRecordDerivable": False,
                "authorityDerivable": False,
            },
            "state": copy.deepcopy(common["stateFixedValues"]),
        }

    def make_complete_bundle(self) -> dict[str, object]:
        repository_ref = "repository:aetherlink-reviewed"
        commit_object_id = "a" * 40
        remote_readback_at = "2026-07-20T10:00:00Z"
        evidence_verified_at = "2026-07-20T10:10:00Z"
        approval_accepted_at = "2026-07-20T10:15:00Z"

        publication_receipt = {
            "repositoryRef": repository_ref,
            "commitObjectId": commit_object_id,
            "artifactBindings": [
                {
                    "role": role,
                    "path": path,
                    "rawSha256": raw_sha256,
                    "canonicalSha256": canonical_sha256,
                }
                for role, path, raw_sha256, canonical_sha256 in zip(
                    receipt_bundle.LINEAGE_ROLES,
                    receipt_bundle.LINEAGE_PATHS,
                    receipt_bundle.LINEAGE_RAW_SHA256,
                    receipt_bundle.LINEAGE_CANONICAL_SHA256,
                )
            ],
            "parentEffectiveAssuranceCanonicalSha256": (
                receipt_bundle.EXPECTED_EFFECTIVE_V2_SHA256
            ),
            "parentClosureSchemaVersion": 2,
            "parentClosureCanonicalSha256": receipt_bundle.EXPECTED_CLOSURE_V2_SHA256,
            "effectiveAssuranceCanonicalSha256": (
                receipt_bundle.EXPECTED_EFFECTIVE_V3_SHA256
            ),
            "effectiveClosureSchemaVersion": 3,
            "effectiveClosureCanonicalSha256": receipt_bundle.EXPECTED_CLOSURE_V3_SHA256,
            "remoteCheckpointPath": receipt_bundle.V3_CHECKPOINT_PATH,
            "remoteCheckpointRawSha256": receipt_bundle.LINEAGE_RAW_SHA256[-1],
            "remoteReadbackAt": remote_readback_at,
            "remoteReadbackSha256": receipt_bundle.LINEAGE_RAW_SHA256[-1],
        }

        owner_bindings = [
            {
                "ownerBindingRef": f"g0-owner-binding-{role}-v1",
                "role": role,
                "ownerIdentityRef": f"owner:{role}",
                "credentialRef": f"credential:{role}",
                "identityRegistryRef": "identity-registry:g0-v1",
                "identityRegistryRevision": "identity-registry-revision:1",
                "validFrom": "2026-07-20T10:00:00Z",
                "validUntil": "2026-07-20T12:00:00Z",
                "revocationRef": f"owner-revocation:{role}:1",
                "provenanceRef": f"owner-provenance:{role}:1",
            }
            for role in self.roles
        ]

        evidence_catalog = []
        evidence_id_by_kind: dict[str, str] = {}
        for index, kind in enumerate(self.evidence_kinds):
            evidence_id = f"g0-evidence-{index + 1:02d}-{kind}"
            evidence_id_by_kind[kind] = evidence_id
            evidence_catalog.append(
                {
                    "evidenceId": evidence_id,
                    "evidenceKind": kind,
                    "evidenceClass": "sanitized_g0_receipt",
                    "subjectImplementationRevision": commit_object_id,
                    "subjectCheckpointSha256": receipt_bundle.LINEAGE_RAW_SHA256[-1],
                    "artifactPath": f"build/qa/g0-evidence-{index + 1:02d}.json",
                    "artifactByteLength": 128 + index,
                    "artifactSha256": f"{index + 1:064x}",
                    "verificationMethod": "independent_exact_byte_verification",
                    "verifierIdentityRef": "verifier:g0-independent-v1",
                    "verifiedAt": evidence_verified_at,
                    "provenanceRef": f"evidence-provenance:{index + 1:02d}",
                }
            )

        authority_bindings = []
        runner_attestations = []
        gate_receipts = []
        gate_times = (
            ("2026-07-20T10:02:00Z", "2026-07-20T10:04:00Z"),
            ("2026-07-20T10:05:00Z", "2026-07-20T10:08:00Z"),
        )
        step_times = (
            (("2026-07-20T10:02:00Z", "2026-07-20T10:04:00Z"),),
            (
                ("2026-07-20T10:05:00Z", "2026-07-20T10:06:00Z"),
                ("2026-07-20T10:07:00Z", "2026-07-20T10:08:00Z"),
            ),
        )
        for index, check_id in enumerate(decision.EXPECTED_G0_EXECUTABLE_CHECK_IDS):
            profile = self.profile_by_check[check_id]
            body = profile["profileBody"]
            profile_id = profile["commandProfileId"]
            profile_sha256 = profile["canonicalProfileSha256"]
            command_sha256 = decision.canonical_json_sha256(body["orderedSteps"])
            side_effects_sha256 = decision.canonical_json_sha256(
                body["allowedSideEffects"]
            )
            cwd_sha256 = f"{100 + index:064x}"
            environment_sha256 = f"{110 + index:064x}"
            authorization_ref = f"g0-authority-{check_id}-v1"
            runner_ref = f"g0-runner-attestation-{check_id}-v1"
            required_refs = [
                evidence_id_by_kind[kind] for kind in body["requiredEvidenceKinds"]
            ]
            started_at, completed_at = gate_times[index]
            authority_bindings.append(
                {
                    "authorizationRef": authorization_ref,
                    "authorityIssuerRef": f"authority-issuer:{index + 1}",
                    "checkId": check_id,
                    "sourcePublicationCommit": commit_object_id,
                    "commandProfileId": profile_id,
                    "commandProfileSha256": profile_sha256,
                    "commandArgvSha256": command_sha256,
                    "workingDirectorySha256": cwd_sha256,
                    "environmentSha256": environment_sha256,
                    "allowedSideEffectsSha256": side_effects_sha256,
                    "notBefore": "2026-07-20T10:01:00Z",
                    "notAfter": "2026-07-20T10:20:00Z",
                    "revocationRef": f"authority-revocation:{index + 1}",
                    "provenanceRef": f"authority-provenance:{index + 1}",
                }
            )
            ordered_step_results = [
                {
                    "stepId": step["stepId"],
                    "argvSha256": decision.canonical_json_sha256(step["argv"]),
                    "startedAt": step_times[index][step_index][0],
                    "completedAt": step_times[index][step_index][1],
                    "exitCode": 0,
                }
                for step_index, step in enumerate(body["orderedSteps"])
            ]
            runner_attestations.append(
                {
                    "runnerAttestationRef": runner_ref,
                    "runnerIdentityRef": f"trusted-runner:{index + 1}",
                    "authorizationRef": authorization_ref,
                    "checkId": check_id,
                    "sourcePublicationCommit": commit_object_id,
                    "commandProfileId": profile_id,
                    "commandProfileSha256": profile_sha256,
                    "commandArgvSha256": command_sha256,
                    "workingDirectorySha256": cwd_sha256,
                    "environmentSha256": environment_sha256,
                    "allowedSideEffectsSha256": side_effects_sha256,
                    "toolchainManifestSha256": f"{120 + index:064x}",
                    "dependencyManifestSha256": f"{130 + index:064x}",
                    "observationManifestSha256": f"{140 + index:064x}",
                    "orderedStepResults": ordered_step_results,
                    "startedAt": started_at,
                    "completedAt": completed_at,
                    "exitCode": 0,
                    "sanitizedLogSha256": f"{150 + index:064x}",
                    "evidenceRefs": required_refs,
                    "provenanceRef": f"runner-provenance:{index + 1}",
                }
            )
            gate_receipts.append(
                {
                    "checkId": check_id,
                    "authorizationRef": authorization_ref,
                    "runnerAttestationRef": runner_ref,
                    "sourcePublicationCommit": commit_object_id,
                    "commandProfileId": profile_id,
                    "commandProfileSha256": profile_sha256,
                    "startedAt": started_at,
                    "completedAt": completed_at,
                    "exitCode": 0,
                    "sanitizedLogSha256": f"{150 + index:064x}",
                    "evidenceRefs": required_refs,
                }
            )

        blocker_evidence = {
            blocker["blockerId"]: tuple(
                kind
                for kind in blocker["requiredEvidenceKinds"]
                if kind in evidence_id_by_kind
            )
            for blocker in self.closure["blockerRequirements"]
        }
        approval_receipts = []
        for role in self.roles:
            relevant_kinds = {"published_checkpoint"}
            for blocker_id in self.role_blockers[role]:
                relevant_kinds.update(blocker_evidence[blocker_id])
            acceptance_refs = [
                evidence_id_by_kind[kind]
                for kind in self.evidence_kinds
                if kind in relevant_kinds
            ]
            approval_receipts.append(
                {
                    "role": role,
                    "ownerIdentityRef": f"owner:{role}",
                    "status": "accepted",
                    "acceptedRevision": receipt_bundle.LINEAGE_RAW_SHA256[-1],
                    "acceptedPublicationCommit": commit_object_id,
                    "acceptedBlockerIds": list(self.role_blockers[role]),
                    "acceptedAt": approval_accepted_at,
                    "acceptanceEvidenceRefs": acceptance_refs,
                }
            )

        return {
            "documentType": "aetherlink.v1-g0-complete-receipt-bundle-candidate",
            "schemaVersion": 1,
            "effectiveAssuranceCanonicalSha256": (
                receipt_bundle.EXPECTED_EFFECTIVE_V3_SHA256
            ),
            "publicationReceipt": publication_receipt,
            "ownerBindings": owner_bindings,
            "evidenceCatalog": evidence_catalog,
            "authorityBindings": authority_bindings,
            "runnerAttestations": runner_attestations,
            "gateReceipts": gate_receipts,
            "approvalReceipts": approval_receipts,
        }

    def test_exact_six_blob_lineage_reconstructs_without_io_or_authority(self) -> None:
        self.assertEqual(
            receipt_bundle._collect_v3_lineage_failures(*self.raw_blobs),
            (),
        )
        self.assertEqual(
            receipt_bundle.__all__,
            ["compile_dormant_owner_catalog_input_preview"],
        )
        self.assertEqual(
            self.documents[0]["assuranceId"],
            "aetherlink_v1_g0_assurance_v1",
        )
        self.assertEqual(
            self.documents[2]["amendmentId"],
            "aetherlink_v1_g0_assurance_closure_amendment_v2",
        )

    def test_every_lineage_blob_is_exact_and_inputs_are_resource_bounded(self) -> None:
        for index in range(len(self.raw_blobs)):
            mutated = list(self.raw_blobs)
            mutated[index] += b" "
            with self.subTest(blob=index):
                self.assertTrue(
                    receipt_bundle._collect_v3_lineage_failures(*mutated)
                )

        released = memoryview(self.raw_blobs[0])
        released.release()
        released_inputs = (released,) + self.raw_blobs[1:]
        self.assertTrue(
            receipt_bundle._collect_v3_lineage_failures(*released_inputs)
        )

        oversized = list(self.raw_blobs)
        oversized[4] = bytearray(receipt_bundle.MAX_V3_AMENDMENT_BYTES + 1)
        self.assertTrue(receipt_bundle._collect_v3_lineage_failures(*oversized))

        deeply_nested = (b'{"x":' * 1_500) + b"0" + (b"}" * 1_500)
        nested = list(self.raw_blobs)
        nested[4] = deeply_nested
        self.assertTrue(receipt_bundle._collect_v3_lineage_failures(*nested))

    def test_v3_overlay_is_exact_ordered_and_does_not_mutate_v2(self) -> None:
        v2_before = copy.deepcopy(self.effective_v2)
        failures: list[str] = []
        effective_v3 = receipt_bundle._apply_v3_operations(
            self.effective_v2,
            self.documents[4]["operations"],
            failures,
        )
        self.assertEqual(failures, [])
        self.assertEqual(self.effective_v2, v2_before)
        self.assertEqual(
            decision.canonical_json_sha256(effective_v3),
            receipt_bundle.EXPECTED_EFFECTIVE_V3_SHA256,
        )

        reordered = copy.deepcopy(self.documents[4]["operations"])
        reordered[4], reordered[5] = reordered[5], reordered[4]
        reordered_failures: list[str] = []
        receipt_bundle._apply_v3_operations(
            self.effective_v2,
            reordered,
            reordered_failures,
        )
        self.assertTrue(reordered_failures)
        self.assertEqual(self.effective_v2, v2_before)

        array_target = copy.deepcopy(self.documents[4]["operations"])
        array_target[4]["path"] = "/g0ClosureContract/commandProfiles/0"
        array_failures: list[str] = []
        receipt_bundle._apply_v3_operations(
            self.effective_v2,
            array_target,
            array_failures,
        )
        self.assertTrue(array_failures)
        self.assertEqual(self.effective_v2, v2_before)

    def test_effective_v3_profiles_forbid_self_asserted_outcomes(self) -> None:
        failures: list[str] = []
        effective_v3 = receipt_bundle._apply_v3_operations(
            self.effective_v2,
            self.documents[4]["operations"],
            failures,
        )
        self.assertEqual(failures, [])
        closure = effective_v3["g0ClosureContract"]
        self.assertEqual(closure["schemaVersion"], 3)

        bundle = closure["receiptBundleProfile"]
        self.assertEqual(
            bundle["exactFields"],
            [
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
            ],
        )
        self.assertIn("result", bundle["forbiddenInputFields"])
        self.assertIn("g0ExitComplete", bundle["forbiddenInputFields"])

        evidence = closure["evidenceCatalogRecordProfile"]
        self.assertNotIn("verificationResult", evidence["exactFields"])
        self.assertEqual(
            evidence["derivedEvidenceKindsForbidden"],
            [
                "owner_acceptance",
                "quality_measurement_contract_owner_approvals",
            ],
        )
        self.assertNotIn("result", closure["gateReceiptProfile"]["exactFields"])
        self.assertNotIn("result", closure["runnerAttestationProfile"]["exactFields"])
        self.assertNotIn("result", closure["publicationReceiptProfile"]["exactFields"])
        self.assertIn(
            "published_checkpoint",
            closure["approvalReceiptProfile"]["acceptanceEvidenceRefsPolicy"],
        )

        derivation_failures: list[str] = []
        (
            roles,
            evidence_kinds,
            role_blockers,
            profile_by_check,
            executable_checks,
        ) = receipt_bundle._derive_contract_sets(effective_v3, derivation_failures)
        self.assertEqual(derivation_failures, [])
        self.assertEqual(
            (
                len(closure["blockerRequirements"]),
                len(effective_v3["releaseChecklist"]["g0Exit"]),
                len(roles),
                sum(len(blockers) for blockers in role_blockers.values()),
                len(evidence_kinds),
                len(executable_checks),
            ),
            (10, 9, 14, 15, 15, 2),
        )
        self.assertEqual(tuple(profile_by_check), executable_checks)

        graph_mutations = []
        missing_blocker_check = copy.deepcopy(effective_v3)
        missing_blocker_check["g0ClosureContract"]["blockerRequirements"][0][
            "requiredCheckIds"
        ].pop()
        graph_mutations.append(missing_blocker_check)

        missing_role_pair = copy.deepcopy(effective_v3)
        missing_role_pair["g0ClosureContract"]["blockerRequirements"][0][
            "requiredOwnerRoles"
        ].pop()
        graph_mutations.append(missing_role_pair)

        missing_evidence = copy.deepcopy(effective_v3)
        missing_evidence["g0ClosureContract"]["blockerRequirements"][1][
            "requiredEvidenceKinds"
        ].pop()
        graph_mutations.append(missing_evidence)

        substituted_evidence = copy.deepcopy(effective_v3)
        substituted_evidence["g0ClosureContract"]["blockerRequirements"][1][
            "requiredEvidenceKinds"
        ][0] = "invented_evidence"
        graph_mutations.append(substituted_evidence)

        overlapping_partition = copy.deepcopy(effective_v3)
        overlapping_partition["g0ClosureContract"]["executableCheckIds"].append(
            overlapping_partition["g0ClosureContract"]["nonExecutableCheckIds"][0]
        )
        graph_mutations.append(overlapping_partition)

        extra_derived_kind = copy.deepcopy(effective_v3)
        extra_derived_kind["g0ClosureContract"]["derivedEvidenceKinds"][
            "invented_derived_evidence"
        ] = "forbidden"
        graph_mutations.append(extra_derived_kind)

        for index, mutation in enumerate(graph_mutations):
            with self.subTest(graph_mutation=index):
                mutation_failures: list[str] = []
                receipt_bundle._derive_contract_sets(mutation, mutation_failures)
                self.assertTrue(mutation_failures)

    def test_activation_and_execution_remain_closed_in_both_v3_records(self) -> None:
        amendment = self.documents[4]
        checkpoint = self.documents[5]
        self.assertEqual(amendment["publication"], None)
        self.assertFalse(amendment["acceptance"]["effectiveAssuranceActivated"])
        self.assertFalse(amendment["acceptance"]["g0ExitComplete"])
        self.assertFalse(amendment["acceptance"]["g1aMayStartNow"])
        for field, value in amendment["authority"].items():
            if field in {
                "g0DocumentationAndStaticValidationAllowed",
                "receiptBundleCandidateStaticValidationAllowed",
            }:
                self.assertTrue(value, field)
            else:
                self.assertFalse(value, field)

        self.assertEqual(
            checkpoint["immutability"]["recordState"],
            "content_addressed_local_candidate_not_publication",
        )
        self.assertEqual(checkpoint["immutability"]["publicationRoot"], "absent")
        self.assertFalse(
            checkpoint["contractControls"]["selfAssertedResultStatusOrActivationFieldsAllowed"]
        )
        self.assertFalse(checkpoint["contractControls"]["candidateValidationMayAuthorize"])

    def test_worktree_checker_passes_the_content_addressed_candidate(self) -> None:
        self.assertEqual(receipt_bundle._collect_worktree_failures(ROOT), ())
        self.assertEqual(
            hashlib.sha256(self.recorded_receipt_raw).hexdigest(),
            receipt_bundle.EXPECTED_RECORDED_PUBLICATION_RECEIPT_RAW_SHA256,
        )
        self.assertEqual(
            tuple(self.recorded_receipt),
            receipt_bundle.PUBLICATION_RECEIPT_FIELDS,
        )
        self.assertEqual(
            self.recorded_receipt["repositoryRef"],
            receipt_bundle.EXPECTED_RECORDED_REPOSITORY_REF,
        )
        self.assertEqual(
            self.recorded_receipt["commitObjectId"],
            receipt_bundle.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
        )
        self.assertEqual(
            receipt_bundle._collect_recorded_publication_receipt_candidate_failures(
                self.recorded_receipt_raw,
                lineage_blobs=self.raw_blobs,
            ),
            (receipt_bundle.RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE,),
        )

        mutations: list[tuple[str, object, str]] = []
        wrong_repository = copy.deepcopy(self.recorded_receipt)
        wrong_repository["repositoryRef"] = "github:someone-else/AetherLink"
        mutations.append(("repository", wrong_repository, "reviewed repositoryRef"))

        wrong_commit = copy.deepcopy(self.recorded_receipt)
        wrong_commit["commitObjectId"] = "a" * 40
        mutations.append(("commit", wrong_commit, "reviewed commitObjectId"))

        wrong_time = copy.deepcopy(self.recorded_receipt)
        wrong_time["remoteReadbackAt"] = "2026-07-20T12:05:43Z"
        mutations.append(("time", wrong_time, "observed remoteReadbackAt"))

        reordered_fields = {
            key: self.recorded_receipt[key]
            for key in reversed(tuple(self.recorded_receipt))
        }
        mutations.append(("field order", reordered_fields, "field order"))

        self_asserted = copy.deepcopy(self.recorded_receipt)
        self_asserted["status"] = "verified"
        mutations.append(("self asserted status", self_asserted, "field order"))

        reordered_bindings = copy.deepcopy(self.recorded_receipt)
        reordered_bindings["artifactBindings"][0], reordered_bindings[
            "artifactBindings"
        ][1] = (
            reordered_bindings["artifactBindings"][1],
            reordered_bindings["artifactBindings"][0],
        )
        mutations.append(("binding order", reordered_bindings, "binding 0.role"))

        missing_binding = copy.deepcopy(self.recorded_receipt)
        missing_binding["artifactBindings"].pop()
        mutations.append(("missing binding", missing_binding, "exactly six"))

        extra_binding = copy.deepcopy(self.recorded_receipt)
        extra_binding["artifactBindings"].append(
            copy.deepcopy(extra_binding["artifactBindings"][-1])
        )
        mutations.append(("extra binding", extra_binding, "exactly six"))

        binding_path = copy.deepcopy(self.recorded_receipt)
        binding_path["artifactBindings"][5]["path"] = "docs/v1/g0/other.json"
        mutations.append(("binding path", binding_path, "binding 5.path"))

        binding_raw_hash = copy.deepcopy(self.recorded_receipt)
        binding_raw_hash["artifactBindings"][5]["rawSha256"] = "0" * 64
        mutations.append(
            ("binding raw hash", binding_raw_hash, "binding 5.rawSha256")
        )

        binding_canonical_hash = copy.deepcopy(self.recorded_receipt)
        binding_canonical_hash["artifactBindings"][5]["canonicalSha256"] = (
            "0" * 64
        )
        mutations.append(
            (
                "binding canonical hash",
                binding_canonical_hash,
                "binding 5.canonicalSha256",
            )
        )

        binding_unknown_field = copy.deepcopy(self.recorded_receipt)
        binding_unknown_field["artifactBindings"][0]["verified"] = True
        mutations.append(
            ("binding unknown field", binding_unknown_field, "fields or field order")
        )

        effective_hash = copy.deepcopy(self.recorded_receipt)
        effective_hash["effectiveAssuranceCanonicalSha256"] = "0" * 64
        mutations.append(
            ("effective hash", effective_hash, "effectiveAssuranceCanonicalSha256")
        )

        checkpoint_path = copy.deepcopy(self.recorded_receipt)
        checkpoint_path["remoteCheckpointPath"] = "docs/v1/g0/other.json"
        mutations.append(
            ("remote checkpoint path", checkpoint_path, "remoteCheckpointPath")
        )

        checkpoint_hash = copy.deepcopy(self.recorded_receipt)
        checkpoint_hash["remoteReadbackSha256"] = "0" * 64
        mutations.append(
            ("remote readback hash", checkpoint_hash, "remoteReadbackSha256")
        )

        malformed_time = copy.deepcopy(self.recorded_receipt)
        malformed_time["remoteReadbackAt"] = "2026-07-20T21:05:44+09:00"
        mutations.append(("malformed time", malformed_time, "canonical RFC3339 UTC"))

        boolean_version = copy.deepcopy(self.recorded_receipt)
        boolean_version["parentClosureSchemaVersion"] = True
        mutations.append(
            ("boolean version", boolean_version, "parentClosureSchemaVersion")
        )

        for label, mutation, expected_failure in mutations:
            with self.subTest(mutation=label):
                failures = (
                    receipt_bundle._collect_recorded_publication_receipt_candidate_failures(
                        self.encoded(mutation),
                        lineage_blobs=self.raw_blobs,
                    )
                )
                self.assertGreater(len(failures), 1)
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    failures,
                )
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE,
                )

        duplicate_key = self.recorded_receipt_raw.replace(
            b'{\n  "repositoryRef": ',
            b'{\n  "repositoryRef": "github:duplicate/target",\n  "repositoryRef": ',
            1,
        )
        duplicate_failures = (
            receipt_bundle._collect_recorded_publication_receipt_candidate_failures(
                duplicate_key,
                lineage_blobs=self.raw_blobs,
            )
        )
        self.assertGreater(len(duplicate_failures), 1)
        self.assertTrue(
            any("duplicate" in failure for failure in duplicate_failures),
            duplicate_failures,
        )
        self.assertEqual(
            duplicate_failures[-1],
            receipt_bundle.RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE,
        )

        malformed_inputs = (
            b"",
            b"\xff",
            b'{"value":NaN}',
            (b'{"x":' * 1_500) + b"0" + (b"}" * 1_500),
            memoryview(
                bytearray(receipt_bundle.MAX_RECORDED_PUBLICATION_RECEIPT_BYTES + 1)
            ),
        )
        for raw in malformed_inputs:
            with self.subTest(malformed_size=len(raw)):
                failures = (
                    receipt_bundle._collect_recorded_publication_receipt_candidate_failures(
                        raw,
                        lineage_blobs=self.raw_blobs,
                    )
                )
                self.assertGreater(len(failures), 1)
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE,
                )

        released = memoryview(self.recorded_receipt_raw)
        released.release()
        released_failures = (
            receipt_bundle._collect_recorded_publication_receipt_candidate_failures(
                released,
                lineage_blobs=self.raw_blobs,
            )
        )
        self.assertGreater(len(released_failures), 1)
        self.assertEqual(
            released_failures[-1],
            receipt_bundle.RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE,
        )

        mutable_receipt = bytearray(self.recorded_receipt_raw)
        original_parser = receipt_bundle._parse_object

        def parse_then_mutate(
            raw: bytes,
            label: str,
            failures: list[str],
        ) -> dict[str, object] | None:
            if label == "recorded G0 V3 publication receipt candidate":
                self.assertIsInstance(raw, bytes)
                mutable_receipt.extend(b" ")
            return original_parser(raw, label, failures)

        with mock.patch.object(
            receipt_bundle,
            "_parse_object",
            side_effect=parse_then_mutate,
        ):
            self.assertEqual(
                receipt_bundle._collect_recorded_publication_receipt_candidate_failures(
                    mutable_receipt,
                    lineage_blobs=self.raw_blobs,
                ),
                (receipt_bundle.RECORDED_PUBLICATION_RECEIPT_DORMANT_MESSAGE,),
            )

        original_final_check = decision.collect_g0_final_snapshot_failures

        def report_sidecar_replacement(*args: object, **kwargs: object) -> tuple[str, ...]:
            if len(args) > 1 and args[1] == receipt_bundle.RECORDED_PUBLICATION_RECEIPT_PATH:
                return ("recorded receipt changed after validation",)
            return original_final_check(*args, **kwargs)

        with mock.patch.object(
            decision,
            "collect_g0_final_snapshot_failures",
            side_effect=report_sidecar_replacement,
        ):
            self.assertIn(
                "recorded receipt changed after validation",
                receipt_bundle._collect_worktree_failures(ROOT),
            )

        with mock.patch.object(
            receipt_bundle,
            "_collect_recorded_publication_receipt_candidate_failures",
            return_value=(),
        ):
            self.assertIn(
                "recorded publication receipt validator did not return the exact "
                "dormant non-authorizing result",
                receipt_bundle._collect_worktree_failures(ROOT),
            )

        original_reader = decision.read_g0_content_addressed_snapshot

        def reject_sidecar_read(*args: object, **kwargs: object) -> object:
            if len(args) > 1 and args[1] == receipt_bundle.RECORDED_PUBLICATION_RECEIPT_PATH:
                raise receipt_bundle.checkpoint.CheckpointValidationError(
                    "recorded receipt is not a regular no-follow snapshot"
                )
            return original_reader(*args, **kwargs)

        with mock.patch.object(
            decision,
            "read_g0_content_addressed_snapshot",
            side_effect=reject_sidecar_read,
        ):
            self.assertEqual(
                receipt_bundle._collect_worktree_failures(ROOT),
                ("recorded receipt is not a regular no-follow snapshot",),
            )

    def test_owner_catalog_input_is_reference_only_and_always_dormant(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.owner_catalog_input_raw).hexdigest(),
            receipt_bundle.EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        )
        self.assertEqual(
            self.owner_catalog_input["responses"],
            [
                {
                    "blockerId": "roadmap_and_g0_checkpoint_publication",
                    "requirementDisposition": "proposed_as_written",
                    "ownerCandidates": [
                        {
                            "role": "repository_owner",
                            "ownerBindingRefCandidate": (
                                "owner-candidate:repository-owner:v1"
                            ),
                        }
                    ],
                    "evidenceCandidates": [
                        {
                            "evidenceKind": "reviewed_commit_scope",
                            "evidenceInputRefCandidate": (
                                "evidence-input-candidate:reviewed-commit-scope:v1"
                            ),
                            "supportingArtifactRefCandidate": None,
                        },
                        {
                            "evidenceKind": "published_checkpoint",
                            "evidenceInputRefCandidate": (
                                "evidence-input-candidate:published-checkpoint:v1"
                            ),
                            "supportingArtifactRefCandidate": None,
                        },
                    ],
                    "changeRequestRefCandidate": None,
                    "inputSourceRefCandidate": (
                        "user-input:session-20260721:item-2"
                    ),
                }
            ],
        )
        self.assertTrue(
            all(value is False for value in self.owner_catalog_input["state"].values())
        )
        explicit_preview_request = self.owner_catalog_preview_request_bytes(
            [
                {
                    "blockerId": "roadmap_and_g0_checkpoint_publication",
                    "requirementDisposition": "proposed_as_written",
                    "ownerCandidates": [
                        {"role": "repository_owner", "candidateVersion": 1}
                    ],
                    "evidenceCandidates": [
                        {
                            "evidenceKind": "reviewed_commit_scope",
                            "candidateVersion": 1,
                            "supportingArtifactPresent": False,
                        },
                        {
                            "evidenceKind": "published_checkpoint",
                            "candidateVersion": 1,
                            "supportingArtifactPresent": False,
                        },
                    ],
                    "changeRequestCandidateVersion": None,
                    "inputSessionDate": "20260721",
                    "inputSessionItem": 2,
                }
            ]
        )
        preview_bytes, preview_sha256 = (
            receipt_bundle.compile_dormant_owner_catalog_input_preview(
                explicit_preview_request,
                lineage_blobs=self.raw_blobs,
            )
        )
        self.assertEqual(preview_bytes, self.owner_catalog_input_raw)
        self.assertEqual(
            preview_sha256,
            receipt_bundle.EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        )
        self.assertEqual(
            receipt_bundle._collect_owner_catalog_input_candidate_failures(
                self.owner_catalog_input_raw,
                lineage_blobs=self.raw_blobs,
            ),
            (receipt_bundle.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,),
        )

        candidate = copy.deepcopy(self.owner_catalog_input)
        candidate["responses"] = [
            {
                "blockerId": "g0_assurance_artifacts_and_baseline_gate",
                "requirementDisposition": "proposed_as_written",
                "ownerCandidates": [
                    {
                        "role": "repository_quality_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:repository-quality-owner:v1"
                        ),
                    },
                    {
                        "role": "release_quality_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:release-quality-owner:v1"
                        ),
                    },
                ],
                "evidenceCandidates": [],
                "changeRequestRefCandidate": None,
                "inputSourceRefCandidate": "user-input:session-20260720:item-1",
            },
            {
                "blockerId": "production_application_namespaces",
                "requirementDisposition": "proposed_as_written",
                "ownerCandidates": [
                    {
                        "role": "product_and_distribution_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:product-and-distribution-owner:v1"
                        ),
                    }
                ],
                "evidenceCandidates": [
                    {
                        "evidenceKind": "owned_application_ids",
                        "evidenceInputRefCandidate": (
                            "evidence-input-candidate:owned-application-ids:v1"
                        ),
                        "supportingArtifactRefCandidate": (
                            "docs/evidence/"
                            "g0-owned-application-ids-candidate-v1.json"
                        ),
                    }
                ],
                "changeRequestRefCandidate": None,
                "inputSourceRefCandidate": "user-input:session-20260720:item-2",
            },
            {
                "blockerId": "quality_measurement_owners",
                "requirementDisposition": "proposed_as_written",
                "ownerCandidates": [
                    {
                        "role": "release_quality_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:release-quality-owner:v1"
                        ),
                    },
                    {
                        "role": "release_network_qa_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:release-network-qa-owner:v1"
                        ),
                    },
                    {
                        "role": "release_performance_qa_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:release-performance-qa-owner:v1"
                        ),
                    },
                    {
                        "role": "service_operations_and_abuse_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:service-operations-and-abuse-owner:v1"
                        ),
                    },
                    {
                        "role": "product_security_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:product-security-owner:v1"
                        ),
                    },
                ],
                "evidenceCandidates": [],
                "changeRequestRefCandidate": None,
                "inputSourceRefCandidate": "user-input:session-20260720:item-3",
            },
            {
                "blockerId": "relay_region_capacity_and_cost_budget",
                "requirementDisposition": "proposed_with_changes",
                "ownerCandidates": [
                    {
                        "role": "service_operations_owner",
                        "ownerBindingRefCandidate": (
                            "owner-candidate:service-operations-owner:v1"
                        ),
                    }
                ],
                "evidenceCandidates": [
                    {
                        "evidenceKind": (
                            "approved_region_peak_capacity_and_cost_ceiling"
                        ),
                        "evidenceInputRefCandidate": (
                            "evidence-input-candidate:"
                            "approved-region-peak-capacity-and-cost-ceiling:v1"
                        ),
                        "supportingArtifactRefCandidate": (
                            "docs/evidence/g0-approved-region-peak-capacity-and-"
                            "cost-ceiling-candidate-v1.json"
                        ),
                    }
                ],
                "changeRequestRefCandidate": (
                    "change-request-candidate:"
                    "relay-region-capacity-and-cost-budget:v1"
                ),
                "inputSourceRefCandidate": "user-input:session-20260720:item-4",
            },
        ]
        self.assertEqual(
            receipt_bundle._collect_owner_catalog_input_candidate_failures(
                self.encoded(candidate),
                lineage_blobs=self.raw_blobs,
            ),
            (receipt_bundle.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,),
        )

        def assert_rejected(
            mutation: dict[str, object],
            expected_fragment: str,
        ) -> None:
            failures = receipt_bundle._collect_owner_catalog_input_candidate_failures(
                self.encoded(mutation),
                lineage_blobs=self.raw_blobs,
            )
            self.assertGreater(len(failures), 1)
            self.assertTrue(
                any(expected_fragment in failure for failure in failures),
                failures,
            )
            self.assertEqual(
                failures[-1],
                receipt_bundle.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,
            )

        status_claim = copy.deepcopy(candidate)
        status_claim["status"] = "accepted"
        assert_rejected(status_claim, "candidate status")

        target_drift = copy.deepcopy(candidate)
        target_drift["contractBinding"]["publicationCommitObjectId"] = "a" * 40
        assert_rejected(target_drift, "publicationCommitObjectId")

        reordered_responses = copy.deepcopy(candidate)
        reordered_responses["responses"].reverse()
        assert_rejected(reordered_responses, "canonical blocker order")

        duplicate_response = copy.deepcopy(candidate)
        duplicate_response["responses"].insert(
            1,
            copy.deepcopy(duplicate_response["responses"][0]),
        )
        assert_rejected(duplicate_response, "duplicated")

        unknown_blocker = copy.deepcopy(candidate)
        unknown_blocker["responses"][0]["blockerId"] = "invented_blocker"
        assert_rejected(unknown_blocker, "blockerId is invalid")

        accepted_disposition = copy.deepcopy(candidate)
        accepted_disposition["responses"][0]["requirementDisposition"] = "accepted"
        assert_rejected(accepted_disposition, "requirementDisposition")

        wrong_role = copy.deepcopy(candidate)
        wrong_role["responses"][1]["ownerCandidates"][0]["role"] = (
            "service_operations_owner"
        )
        assert_rejected(wrong_role, ".role is invalid")

        misbound_owner_ref = copy.deepcopy(candidate)
        misbound_owner_ref["responses"][1]["ownerCandidates"][0][
            "ownerBindingRefCandidate"
        ] = "owner-candidate:repository-quality-owner:v1"
        assert_rejected(misbound_owner_ref, "binding reference is invalid")

        inconsistent_role = copy.deepcopy(candidate)
        inconsistent_role["responses"][2]["ownerCandidates"][0][
            "ownerBindingRefCandidate"
        ] = "owner-candidate:release-quality-owner:v2"
        assert_rejected(inconsistent_role, "is inconsistent")

        personal_identity = copy.deepcopy(candidate)
        personal_identity["responses"][1]["ownerCandidates"][0][
            "ownerBindingRefCandidate"
        ] = "person@example.com"
        assert_rejected(personal_identity, "binding reference is invalid")

        derived_evidence = copy.deepcopy(candidate)
        derived_evidence["responses"][2]["evidenceCandidates"] = [
            {
                "evidenceKind": "quality_measurement_contract_owner_approvals",
                "evidenceInputRefCandidate": (
                    "evidence-input-candidate:self-asserted-approval:v1"
                ),
                "supportingArtifactRefCandidate": None,
            }
        ]
        assert_rejected(derived_evidence, "evidenceCandidates is invalid")

        freeform_input = copy.deepcopy(candidate)
        freeform_input["responses"][1]["evidenceCandidates"][0][
            "nonSecretInput"
        ] = "Authorization: Bearer header.payload.signature"
        assert_rejected(freeform_input, "fields or field order")

        invalid_evidence_ref = copy.deepcopy(candidate)
        invalid_evidence_ref["responses"][1]["evidenceCandidates"][0][
            "evidenceInputRefCandidate"
        ] = "evidence-input-candidate:relay-secret:v1"
        assert_rejected(invalid_evidence_ref, "input reference is invalid")

        token_owner_ref = copy.deepcopy(candidate)
        token_owner_ref["responses"][1]["ownerCandidates"][0][
            "ownerBindingRefCandidate"
        ] = "owner-candidate:ghp-example-token:v1"
        assert_rejected(token_owner_ref, "binding reference is invalid")

        unsafe_artifact = copy.deepcopy(candidate)
        unsafe_artifact["responses"][3]["evidenceCandidates"][0][
            "supportingArtifactRefCandidate"
        ] = "../private.json"
        assert_rejected(unsafe_artifact, "supporting artifact candidate is invalid")

        misbound_artifact = copy.deepcopy(candidate)
        misbound_artifact["responses"][1]["evidenceCandidates"][0][
            "supportingArtifactRefCandidate"
        ] = "docs/evidence/g0-published-checkpoint-candidate-v1.json"
        assert_rejected(misbound_artifact, "supporting artifact candidate is invalid")

        invalid_source = copy.deepcopy(candidate)
        invalid_source["responses"][0]["inputSourceRefCandidate"] = (
            "user-input:token:sk-proj-example"
        )
        assert_rejected(invalid_source, "inputSourceRefCandidate is invalid")

        valid_not_available = copy.deepcopy(candidate)
        valid_not_available["responses"][0]["requirementDisposition"] = (
            "not_available"
        )
        valid_not_available["responses"][0]["ownerCandidates"] = []
        self.assertEqual(
            receipt_bundle._collect_owner_catalog_input_candidate_failures(
                self.encoded(valid_not_available),
                lineage_blobs=self.raw_blobs,
            ),
            (receipt_bundle.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,),
        )

        not_available_with_input = copy.deepcopy(candidate)
        not_available_with_input["responses"][0]["requirementDisposition"] = (
            "not_available"
        )
        assert_rejected(not_available_with_input, "not-available response")

        missing_change_request = copy.deepcopy(candidate)
        missing_change_request["responses"][3]["changeRequestRefCandidate"] = None
        assert_rejected(missing_change_request, "change request reference is invalid")

        misbound_change_request = copy.deepcopy(candidate)
        misbound_change_request["responses"][3]["changeRequestRefCandidate"] = (
            "change-request-candidate:relay-budget:v1"
        )
        assert_rejected(misbound_change_request, "change request reference is invalid")

        unexpected_change_request = copy.deepcopy(candidate)
        unexpected_change_request["responses"][0]["changeRequestRefCandidate"] = (
            "change-request-candidate:unexpected:v1"
        )
        assert_rejected(unexpected_change_request, "must not include a change request")

        empty_proposal = copy.deepcopy(candidate)
        empty_proposal["responses"][0]["ownerCandidates"] = []
        assert_rejected(empty_proposal, "proposal contains no input")

        activated = copy.deepcopy(candidate)
        activated["state"]["receiptActivationAllowed"] = True
        assert_rejected(activated, "state.receiptActivationAllowed")

        extra_field = copy.deepcopy(candidate)
        extra_field["g0ExitComplete"] = True
        assert_rejected(extra_field, "fields or field order")

        reordered_root = {key: candidate[key] for key in reversed(tuple(candidate))}
        assert_rejected(reordered_root, "fields or field order")

        for raw in (
            b"",
            b"\xff",
            memoryview(bytearray(receipt_bundle.MAX_OWNER_CATALOG_INPUT_BYTES + 1)),
        ):
            with self.subTest(owner_catalog_input_size=len(raw)):
                failures = (
                    receipt_bundle._collect_owner_catalog_input_candidate_failures(
                        raw,
                        lineage_blobs=self.raw_blobs,
                    )
                )
                self.assertGreater(len(failures), 1)
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,
                )

        released = memoryview(self.owner_catalog_input_raw)
        released.release()
        released_failures = (
            receipt_bundle._collect_owner_catalog_input_candidate_failures(
                released,
                lineage_blobs=self.raw_blobs,
            )
        )
        self.assertGreater(len(released_failures), 1)
        self.assertEqual(
            released_failures[-1],
            receipt_bundle.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,
        )

        original_reader = decision.read_g0_content_addressed_snapshot

        def reject_input_read(*args: object, **kwargs: object) -> object:
            if len(args) > 1 and args[1] == receipt_bundle.OWNER_CATALOG_INPUT_PATH:
                raise receipt_bundle.checkpoint.CheckpointValidationError(
                    "owner/catalog input is not a regular no-follow snapshot"
                )
            return original_reader(*args, **kwargs)

        with mock.patch.object(
            decision,
            "read_g0_content_addressed_snapshot",
            side_effect=reject_input_read,
        ):
            self.assertEqual(
                receipt_bundle._collect_worktree_failures(ROOT),
                ("owner/catalog input is not a regular no-follow snapshot",),
            )

        original_final_check = decision.collect_g0_final_snapshot_failures

        def report_input_replacement(*args: object, **kwargs: object) -> tuple[str, ...]:
            if len(args) > 1 and args[1] == receipt_bundle.OWNER_CATALOG_INPUT_PATH:
                return ("owner/catalog input changed after validation",)
            return original_final_check(*args, **kwargs)

        with mock.patch.object(
            decision,
            "collect_g0_final_snapshot_failures",
            side_effect=report_input_replacement,
        ):
            self.assertIn(
                "owner/catalog input changed after validation",
                receipt_bundle._collect_worktree_failures(ROOT),
            )

        with mock.patch.object(
            receipt_bundle,
            "_collect_owner_catalog_input_candidate_failures",
            return_value=(),
        ):
            self.assertIn(
                "owner/catalog input validator did not return the exact dormant "
                "non-authorizing result",
                receipt_bundle._collect_worktree_failures(ROOT),
            )

    def test_owner_catalog_preview_compiles_canonical_dormant_bytes(self) -> None:
        proposals = self.make_owner_catalog_preview_proposals()
        request_buffer = bytearray(
            self.owner_catalog_preview_request_bytes(proposals)
        )
        mutable_lineage = tuple(bytearray(raw) for raw in self.raw_blobs)
        original_validator = (
            receipt_bundle._collect_owner_catalog_input_candidate_failures
        )

        def mutate_sources_then_validate(
            candidate_bytes: object,
            *,
            lineage_blobs: tuple[object, ...],
        ) -> tuple[str, ...]:
            self.assertTrue(all(isinstance(blob, bytes) for blob in lineage_blobs))
            request_buffer.extend(b" ")
            mutable_lineage[0].extend(b" ")
            return original_validator(candidate_bytes, lineage_blobs=lineage_blobs)

        with mock.patch.object(
            receipt_bundle,
            "_collect_owner_catalog_input_candidate_failures",
            side_effect=mutate_sources_then_validate,
        ):
            preview_bytes, preview_sha256 = (
                receipt_bundle.compile_dormant_owner_catalog_input_preview(
                    request_buffer,
                    lineage_blobs=mutable_lineage,
                )
            )

        preview = json.loads(preview_bytes)
        self.assertIn(
            "compile_dormant_owner_catalog_input_preview",
            receipt_bundle.__all__,
        )
        self.assertEqual(preview_bytes, self.encoded(preview))
        self.assertEqual(preview_sha256, hashlib.sha256(preview_bytes).hexdigest())
        self.assertTrue(all(value is False for value in preview["state"].values()))
        self.assertEqual(
            preview["responses"][0]["ownerCandidates"][1][
                "ownerBindingRefCandidate"
            ],
            "owner-candidate:release-quality-owner:v2",
        )
        self.assertEqual(
            preview["responses"][0]["evidenceCandidates"][1][
                "supportingArtifactRefCandidate"
            ],
            "docs/evidence/g0-source-hash-readback-candidate-v2.json",
        )
        self.assertEqual(
            preview["responses"][3]["changeRequestRefCandidate"],
            "change-request-candidate:relay-region-capacity-and-cost-budget:v5",
        )
        self.assertEqual(
            tuple(response["requirementDisposition"] for response in preview["responses"]),
            (
                "proposed_as_written",
                "not_available",
                "proposed_as_written",
                "proposed_with_changes",
            ),
        )
        self.assertEqual(
            original_validator(preview_bytes, lineage_blobs=self.raw_blobs),
            (receipt_bundle.OWNER_CATALOG_INPUT_DORMANT_MESSAGE,),
        )

        reordered = self.make_owner_catalog_preview_proposals()
        reordered.reverse()
        reordered[-1]["ownerCandidates"].reverse()
        reordered[-1]["evidenceCandidates"].reverse()
        reordered_bytes, reordered_sha256 = (
            receipt_bundle.compile_dormant_owner_catalog_input_preview(
                self.owner_catalog_preview_request_bytes(reordered),
                lineage_blobs=self.raw_blobs,
            )
        )
        self.assertEqual(reordered_bytes, preview_bytes)
        self.assertEqual(reordered_sha256, preview_sha256)

        mutated_preview = json.loads(preview_bytes)
        mutated_preview["state"]["g0ExitComplete"] = True
        self.assertFalse(json.loads(preview_bytes)["state"]["g0ExitComplete"])

    def test_owner_catalog_preview_rejects_noncanonical_or_unsafe_selectors(self) -> None:
        def assert_invalid(mutate: object) -> None:
            proposals = self.make_owner_catalog_preview_proposals()
            mutate(proposals)
            with self.assertRaises(ValueError):
                receipt_bundle.compile_dormant_owner_catalog_input_preview(
                    self.owner_catalog_preview_request_bytes(proposals),
                    lineage_blobs=self.raw_blobs,
                )

        mutations = (
            lambda values: values[0].__setitem__("blockerId", "unknown_blocker"),
            lambda values: values[0]["ownerCandidates"][0].__setitem__(
                "role", "unknown_owner"
            ),
            lambda values: values[0]["evidenceCandidates"][0].__setitem__(
                "evidenceKind", "unknown_evidence"
            ),
            lambda values: values[2]["evidenceCandidates"].append(
                {
                    "evidenceKind": "quality_measurement_contract_owner_approvals",
                    "candidateVersion": 1,
                    "supportingArtifactPresent": False,
                }
            ),
            lambda values: values[0].__setitem__("inputSessionDate", "20260230"),
            lambda values: values.insert(1, copy.deepcopy(values[0])),
            lambda values: values[0]["ownerCandidates"].append(
                copy.deepcopy(values[0]["ownerCandidates"][0])
            ),
            lambda values: values[0]["evidenceCandidates"].append(
                copy.deepcopy(values[0]["evidenceCandidates"][0])
            ),
            lambda values: values[2]["ownerCandidates"][0].__setitem__(
                "candidateVersion", 3
            ),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                assert_invalid(mutation)

        for invalid_version in (
            False,
            0,
            1_000_000_000,
            "1",
            1.0,
        ):
            with self.subTest(candidate_version=invalid_version):
                assert_invalid(
                    lambda values, version=invalid_version: values[0][
                        "ownerCandidates"
                    ][0].__setitem__("candidateVersion", version)
                )

        with self.assertRaises(ValueError):
            receipt_bundle.compile_dormant_owner_catalog_input_preview(
                b"x" * (receipt_bundle.MAX_OWNER_CATALOG_INPUT_BYTES + 1),
                lineage_blobs=self.raw_blobs,
            )

        duplicate_key_request = (
            b'{"documentType":"aetherlink.v1-g0-owner-catalog-preview-request",'
            b'"schemaVersion":1,"schemaVersion":1,"proposals":[]}'
        )
        with self.assertRaises(ValueError):
            receipt_bundle.compile_dormant_owner_catalog_input_preview(
                duplicate_key_request,
                lineage_blobs=self.raw_blobs,
            )

        valid_request = self.owner_catalog_preview_request_bytes(
            self.make_owner_catalog_preview_proposals()
        )

        class LyingBytes(bytes):
            def __len__(self) -> int:
                return 1

            def __bytes__(self) -> bytes:
                return (
                    valid_request
                    + b" " * receipt_bundle.MAX_OWNER_CATALOG_INPUT_BYTES
                )

        class LyingBytearray(bytearray):
            def __len__(self) -> int:
                return 1

            def __bytes__(self) -> bytes:
                return valid_request

        for hooked_buffer in (LyingBytes(b"x"), LyingBytearray(b"x")):
            with self.subTest(buffer_type=type(hooked_buffer).__name__):
                with self.assertRaises(ValueError):
                    receipt_bundle.compile_dormant_owner_catalog_input_preview(
                        hooked_buffer,
                        lineage_blobs=self.raw_blobs,
                    )

        self.assertTrue(
            receipt_bundle._valid_input_source_ref_candidate(
                "user-input:session-20240229:item-1"
            )
        )
        for invalid_source in (
            "user-input:session-20230229:item-1",
            "user-input:session-00000101:item-1",
        ):
            with self.subTest(input_source=invalid_source):
                self.assertFalse(
                    receipt_bundle._valid_input_source_ref_candidate(invalid_source)
                )

        impossible_date = copy.deepcopy(self.owner_catalog_input)
        impossible_date["responses"] = [
            {
                "blockerId": "roadmap_and_g0_checkpoint_publication",
                "requirementDisposition": "not_available",
                "ownerCandidates": [],
                "evidenceCandidates": [],
                "changeRequestRefCandidate": None,
                "inputSourceRefCandidate": "user-input:session-20260230:item-1",
            }
        ]
        self.assertTrue(
            any(
                "inputSourceRefCandidate is invalid" in failure
                for failure in receipt_bundle._collect_owner_catalog_input_candidate_failures(
                    self.encoded(impossible_date),
                    lineage_blobs=self.raw_blobs,
                )
            )
        )

    def test_exact_complete_bundle_fixture_is_structural_only_and_dormant(self) -> None:
        failures = receipt_bundle._collect_complete_bundle_candidate_failures(
            self.encoded(self.make_complete_bundle()),
            lineage_blobs=self.raw_blobs,
        )
        self.assertEqual(
            failures,
            (receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,),
        )
        self.assertFalse(self.documents[4]["acceptance"]["effectiveAssuranceActivated"])
        self.assertFalse(self.documents[4]["acceptance"]["g0ExitComplete"])

        mutable_lineage = tuple(bytearray(raw) for raw in self.raw_blobs)
        original_validator = receipt_bundle._collect_v3_lineage_failures

        def validate_then_mutate(*snapshots: object) -> tuple[str, ...]:
            self.assertTrue(all(isinstance(snapshot, bytes) for snapshot in snapshots))
            failures = original_validator(*snapshots)
            mutable_lineage[4].extend(b" ")
            return failures

        with mock.patch.object(
            receipt_bundle,
            "_collect_v3_lineage_failures",
            side_effect=validate_then_mutate,
        ):
            failures = receipt_bundle._collect_complete_bundle_candidate_failures(
                self.encoded(self.make_complete_bundle()),
                lineage_blobs=mutable_lineage,
            )

        self.assertEqual(
            failures,
            (receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,),
        )

    def test_complete_bundle_rejects_partial_duplicate_and_self_asserted_state(self) -> None:
        canonical = self.make_complete_bundle()
        mutations = []

        missing_field = copy.deepcopy(canonical)
        missing_field.pop("ownerBindings")
        mutations.append(missing_field)

        reordered_root = {key: canonical[key] for key in reversed(tuple(canonical))}
        mutations.append(reordered_root)

        self_asserted = copy.deepcopy(canonical)
        self_asserted["g0ExitComplete"] = True
        mutations.append(self_asserted)

        missing_evidence = copy.deepcopy(canonical)
        missing_evidence["evidenceCatalog"].pop()
        mutations.append(missing_evidence)

        duplicate_owner = copy.deepcopy(canonical)
        duplicate_owner["ownerBindings"][1]["ownerIdentityRef"] = (
            duplicate_owner["ownerBindings"][0]["ownerIdentityRef"]
        )
        mutations.append(duplicate_owner)

        derived_evidence = copy.deepcopy(canonical)
        derived_evidence["evidenceCatalog"][0]["evidenceKind"] = "owner_acceptance"
        mutations.append(derived_evidence)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                failures = receipt_bundle._collect_complete_bundle_candidate_failures(
                    self.encoded(mutation),
                    lineage_blobs=self.raw_blobs,
                )
                self.assertGreater(len(failures), 1)
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,
                )

    def test_complete_bundle_rejects_cross_binding_and_time_drift(self) -> None:
        canonical = self.make_complete_bundle()
        mutations = []

        publication_drift = copy.deepcopy(canonical)
        publication_drift["publicationReceipt"]["artifactBindings"][5][
            "rawSha256"
        ] = "0" * 64
        mutations.append(publication_drift)

        authority_runner_drift = copy.deepcopy(canonical)
        authority_runner_drift["runnerAttestations"][0]["environmentSha256"] = (
            "0" * 64
        )
        mutations.append(authority_runner_drift)

        gate_log_drift = copy.deepcopy(canonical)
        gate_log_drift["gateReceipts"][1]["sanitizedLogSha256"] = "0" * 64
        mutations.append(gate_log_drift)

        subset_approval = copy.deepcopy(canonical)
        release_quality_index = self.roles.index("release_quality_owner")
        subset_approval["approvalReceipts"][release_quality_index][
            "acceptedBlockerIds"
        ] = ["g0_assurance_artifacts_and_baseline_gate"]
        mutations.append(subset_approval)

        early_acceptance = copy.deepcopy(canonical)
        early_acceptance["approvalReceipts"][0]["acceptedAt"] = (
            "2026-07-20T10:09:00Z"
        )
        mutations.append(early_acceptance)

        overlapping_steps = copy.deepcopy(canonical)
        overlapping_steps["runnerAttestations"][1]["orderedStepResults"][1][
            "startedAt"
        ] = "2026-07-20T10:05:30Z"
        mutations.append(overlapping_steps)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                failures = receipt_bundle._collect_complete_bundle_candidate_failures(
                    self.encoded(mutation),
                    lineage_blobs=self.raw_blobs,
                )
                self.assertGreater(len(failures), 1)
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,
                )

    def test_complete_bundle_parser_is_bounded_and_never_activates(self) -> None:
        for raw in (
            b"",
            b"null",
            b"{}",
            b"{",
            (b'{"x":' * 1_500) + b"0" + (b"}" * 1_500),
            memoryview(bytearray(receipt_bundle.MAX_COMPLETE_BUNDLE_BYTES + 1)),
        ):
            with self.subTest(size=len(raw)):
                failures = receipt_bundle._collect_complete_bundle_candidate_failures(
                    raw,
                    lineage_blobs=self.raw_blobs,
                )
                self.assertTrue(failures)
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,
                )

        released = memoryview(self.encoded(self.make_complete_bundle()))
        released.release()
        failures = receipt_bundle._collect_complete_bundle_candidate_failures(
            released,
            lineage_blobs=self.raw_blobs,
        )
        self.assertEqual(
            failures[-1],
            receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,
        )

        surrogate = self.make_complete_bundle()
        surrogate["publicationReceipt"]["repositoryRef"] = "\ud800"
        surrogate_raw = json.dumps(
            surrogate,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        failures = receipt_bundle._collect_complete_bundle_candidate_failures(
            surrogate_raw,
            lineage_blobs=self.raw_blobs,
        )
        self.assertGreater(len(failures), 1)
        self.assertEqual(
            failures[-1],
            receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,
        )

        wrong_lineage = self.raw_blobs[:-1]
        failures = receipt_bundle._collect_complete_bundle_candidate_failures(
            self.encoded(self.make_complete_bundle()),
            lineage_blobs=wrong_lineage,
        )
        self.assertEqual(
            failures[-1],
            receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,
        )

    def test_evidence_supporting_artifact_profile_is_exact_and_instances_absent(
        self,
    ) -> None:
        self.assertEqual(
            hashlib.sha256(self.evidence_artifact_profile_raw).hexdigest(),
            receipt_bundle.EXPECTED_EVIDENCE_SUPPORTING_ARTIFACT_PROFILE_RAW_SHA256,
        )
        self.assertEqual(
            receipt_bundle._collect_evidence_supporting_artifact_profile_failures(
                self.evidence_artifact_profile_raw,
                owner_catalog_input_bytes=self.owner_catalog_input_raw,
            ),
            (),
        )
        reviewed = self.evidence_artifact_profile[
            "reviewedCommitScopePayloadProfile"
        ]
        self.assertEqual(len(reviewed["expectedScopeEntries"]), 18)
        self.assertEqual(
            {entry["fileMode"] for entry in reviewed["expectedScopeEntries"]},
            {"100644", "100755"},
        )
        self.assertEqual(
            receipt_bundle._collect_absent_evidence_artifact_failures(ROOT),
            (),
        )
        evidence_candidates = self.owner_catalog_input["responses"][0][
            "evidenceCandidates"
        ]
        self.assertEqual(
            [candidate["evidenceKind"] for candidate in evidence_candidates],
            ["reviewed_commit_scope", "published_checkpoint"],
        )
        self.assertTrue(
            all(
                candidate["supportingArtifactRefCandidate"] is None
                for candidate in evidence_candidates
            )
        )
        selector_snapshot = self.evidence_artifact_profile[
            "selectorSnapshotBinding"
        ]
        self.assertEqual(
            selector_snapshot["ownerCatalogInputCandidateRawSha256"],
            receipt_bundle.EXPECTED_OWNER_CATALOG_INPUT_RAW_SHA256,
        )
        self.assertEqual(
            selector_snapshot["inputSourceRefCandidate"],
            "user-input:session-20260721:item-2",
        )
        self.assertEqual(
            [
                entry["evidenceInputRefCandidate"]
                for entry in selector_snapshot["evidenceSelectors"]
            ],
            [candidate["evidenceInputRefCandidate"] for candidate in evidence_candidates],
        )
        self.assertTrue(
            all(
                entry["supportingArtifactPresent"] is False
                and entry["supportingArtifactRefCandidate"] is None
                for entry in selector_snapshot["evidenceSelectors"]
            )
        )

        mutated_owner_input = copy.deepcopy(self.owner_catalog_input)
        mutated_owner_input["responses"][0]["inputSourceRefCandidate"] = (
            "user-input:session-20260721:item-3"
        )
        selector_drift_failures = (
            receipt_bundle._collect_evidence_supporting_artifact_profile_failures(
                self.evidence_artifact_profile_raw,
                owner_catalog_input_bytes=self.encoded(mutated_owner_input),
            )
        )
        self.assertTrue(
            any("selector snapshot" in failure for failure in selector_drift_failures),
            selector_drift_failures,
        )

        mutated_profile = copy.deepcopy(self.evidence_artifact_profile)
        mutated_profile["authorizationBoundary"]["g0ExitDerivable"] = True
        self.assertTrue(
            receipt_bundle._collect_evidence_supporting_artifact_profile_failures(
                self.encoded(mutated_profile),
                owner_catalog_input_bytes=self.owner_catalog_input_raw,
            )
        )
        mutated_selector_profile = copy.deepcopy(self.evidence_artifact_profile)
        mutated_selector_profile["selectorSnapshotBinding"][
            "inputSourceRefCandidate"
        ] = "user-input:session-20260721:item-3"
        mutated_selector_failures = (
            receipt_bundle._collect_evidence_supporting_artifact_profile_failures(
                self.encoded(mutated_selector_profile),
                owner_catalog_input_bytes=self.owner_catalog_input_raw,
            )
        )
        self.assertTrue(
            any(
                "selectorSnapshotBinding" in failure
                for failure in mutated_selector_failures
            ),
            mutated_selector_failures,
        )
        malformed_profile_mutations: list[tuple[str, dict[str, object], str]] = []
        for field in ("changeType", "fileMode"):
            malformed_scope_profile = copy.deepcopy(self.evidence_artifact_profile)
            malformed_scope_profile["reviewedCommitScopePayloadProfile"][
                "expectedScopeEntries"
            ][0][field] = []
            malformed_profile_mutations.append(
                (field, malformed_scope_profile, f".{field} is invalid")
            )
        malformed_forbidden_material = copy.deepcopy(self.evidence_artifact_profile)
        malformed_forbidden_material["sensitiveDataPolicy"]["forbiddenMaterial"] = [
            {}
        ]
        malformed_profile_mutations.append(
            (
                "forbiddenMaterial",
                malformed_forbidden_material,
                "sensitive material exclusions are incomplete",
            )
        )
        for label, malformed_profile, expected_failure in malformed_profile_mutations:
            with self.subTest(malformed_profile=label):
                failures = (
                    receipt_bundle._collect_evidence_supporting_artifact_profile_failures(
                        self.encoded(malformed_profile),
                        owner_catalog_input_bytes=self.owner_catalog_input_raw,
                    )
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    failures,
                )
        released = memoryview(self.evidence_artifact_profile_raw)
        released.release()
        self.assertTrue(
            receipt_bundle._collect_evidence_supporting_artifact_profile_failures(
                released,
                owner_catalog_input_bytes=self.owner_catalog_input_raw,
            )
        )

        with mock.patch.object(Path, "lstat", return_value=mock.Mock()):
            present_failures = (
                receipt_bundle._collect_absent_evidence_artifact_failures(ROOT)
            )
        self.assertEqual(len(present_failures), 2)
        self.assertTrue(
            all("selector reference is null" in failure for failure in present_failures)
        )

    def test_evidence_supporting_artifact_fixtures_are_always_non_authorizing(
        self,
    ) -> None:
        for evidence_kind in ("reviewed_commit_scope", "published_checkpoint"):
            with self.subTest(evidence_kind=evidence_kind):
                candidate = self.make_evidence_artifact_candidate(evidence_kind)
                raw = self.encoded(candidate)
                with mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("artifact inspection attempted file I/O"),
                ), mock.patch.object(
                    receipt_bundle.decision,
                    "read_g0_content_addressed_snapshot",
                    side_effect=AssertionError("artifact inspection attempted repository I/O"),
                ):
                    failures = (
                        receipt_bundle._collect_evidence_supporting_artifact_candidate_failures(
                            raw,
                            profile_bytes=self.evidence_artifact_profile_raw,
                            owner_catalog_input_bytes=self.owner_catalog_input_raw,
                        )
                    )
                self.assertEqual(
                    failures,
                    (receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE,),
                )
                self.assertTrue(all(value is False for value in candidate["state"].values()))
                self.assertFalse(candidate["trustBoundary"]["catalogRecordDerivable"])
                self.assertFalse(candidate["trustBoundary"]["authorityDerivable"])

    def test_evidence_supporting_artifact_rejects_drift_and_authority_claims(
        self,
    ) -> None:
        mutations: list[tuple[str, dict[str, object]]] = []

        wrong_subject = self.make_evidence_artifact_candidate("reviewed_commit_scope")
        wrong_subject["payload"]["baseCommitObjectId"] = (
            "70350f5e9e5e39d1b793862c1e58d09edf637405"
        )
        mutations.append(("followup-as-subject", wrong_subject))

        reordered_scope = self.make_evidence_artifact_candidate("reviewed_commit_scope")
        reordered_scope["payload"]["scopeEntries"].reverse()
        mutations.append(("scope-order", reordered_scope))

        traversal_scope = self.make_evidence_artifact_candidate("reviewed_commit_scope")
        traversal_scope["payload"]["scopeEntries"][0]["path"] = "../docs/handoff.md"
        mutations.append(("scope-path", traversal_scope))

        boolean_count = self.make_evidence_artifact_candidate("reviewed_commit_scope")
        boolean_count["payload"]["scopeEntryCount"] = True
        mutations.append(("boolean-count", boolean_count))

        owner_v2 = self.make_evidence_artifact_candidate("reviewed_commit_scope")
        owner_v2["payload"]["reviewClaim"][
            "ownerBindingRefCandidate"
        ] = "owner-candidate:repository-owner:v2"
        mutations.append(("owner-version", owner_v2))

        transcript_claim = self.make_evidence_artifact_candidate("published_checkpoint")
        transcript_claim["payload"]["standaloneAcquisitionTranscriptRef"] = (
            "session-transcript:self-asserted"
        )
        mutations.append(("self-asserted-transcript", transcript_claim))

        followup_checkpoint = self.make_evidence_artifact_candidate(
            "published_checkpoint"
        )
        followup_checkpoint["payload"]["commitCheckpointRawSha256"] = "0" * 64
        mutations.append(("checkpoint-drift", followup_checkpoint))

        reversed_time = self.make_evidence_artifact_candidate("published_checkpoint")
        reversed_time["payload"]["observationStartedAt"] = "2026-07-20T12:06:00Z"
        mutations.append(("time-order", reversed_time))

        promoted_state = self.make_evidence_artifact_candidate("published_checkpoint")
        promoted_state["state"]["evidenceCatalogVerified"] = True
        mutations.append(("state-promotion", promoted_state))

        false_provenance = self.make_evidence_artifact_candidate("published_checkpoint")
        false_provenance["trustBoundary"]["independentInputsPresent"] = [
            "verifier_identity"
        ]
        mutations.append(("false-provenance", false_provenance))

        wrong_profile = self.make_evidence_artifact_candidate("published_checkpoint")
        wrong_profile["profileRef"]["rawSha256"] = "0" * 64
        mutations.append(("profile-drift", wrong_profile))

        selector_source = self.make_evidence_artifact_candidate("published_checkpoint")
        selector_source["selectorBinding"]["inputSourceRefCandidate"] = (
            "user-input:session-20260721:item-3"
        )
        mutations.append(("selector-source", selector_source))

        selector_ref = self.make_evidence_artifact_candidate("published_checkpoint")
        selector_ref["selectorBinding"]["evidenceInputRefCandidate"] = (
            "evidence-input-candidate:published-checkpoint:v2"
        )
        mutations.append(("selector-reference", selector_ref))

        selector_version = self.make_evidence_artifact_candidate("published_checkpoint")
        selector_version["selectorBinding"]["candidateVersion"] = 2
        mutations.append(("selector-version", selector_version))

        selector_path = self.make_evidence_artifact_candidate("published_checkpoint")
        selector_path["selectorBinding"]["reservedArtifactPath"] = (
            "docs/evidence/g0-reviewed-commit-scope-candidate-v1.json"
        )
        mutations.append(("selector-path", selector_path))

        selector_presence = self.make_evidence_artifact_candidate("published_checkpoint")
        selector_presence["selectorBinding"]["supportingArtifactPresent"] = True
        selector_presence["selectorBinding"]["supportingArtifactRefCandidate"] = (
            "docs/evidence/g0-published-checkpoint-candidate-v1.json"
        )
        mutations.append(("selector-presence", selector_presence))

        authority_field = self.make_evidence_artifact_candidate("published_checkpoint")
        authority_field["verifierIdentityRef"] = "verifier:self-asserted"
        mutations.append(("authority-field", authority_field))

        for label, mutation in mutations:
            with self.subTest(mutation=label):
                failures = (
                    receipt_bundle._collect_evidence_supporting_artifact_candidate_failures(
                        self.encoded(mutation),
                        profile_bytes=self.evidence_artifact_profile_raw,
                        owner_catalog_input_bytes=self.owner_catalog_input_raw,
                    )
                )
                self.assertGreater(len(failures), 1)
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE,
                )

    def test_evidence_supporting_artifact_parser_is_bounded_and_snapshotted(
        self,
    ) -> None:
        candidate = self.make_evidence_artifact_candidate("reviewed_commit_scope")
        valid_raw = self.encoded(candidate)
        invalid_raws = (
            valid_raw + b"\n",
            valid_raw.replace(
                b'"schemaVersion":1,',
                b'"schemaVersion":1,"schemaVersion":1,',
                1,
            ),
            self.encoded(dict(reversed(tuple(candidate.items())))),
            memoryview(
                bytearray(receipt_bundle.MAX_EVIDENCE_SUPPORTING_ARTIFACT_BYTES + 1)
            ),
        )
        for index, raw in enumerate(invalid_raws):
            with self.subTest(invalid=index):
                failures = (
                    receipt_bundle._collect_evidence_supporting_artifact_candidate_failures(
                        raw,
                        profile_bytes=self.evidence_artifact_profile_raw,
                        owner_catalog_input_bytes=self.owner_catalog_input_raw,
                    )
                )
                self.assertGreater(len(failures), 1)
                self.assertEqual(
                    failures[-1],
                    receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE,
                )

        released = memoryview(valid_raw)
        released.release()
        self.assertEqual(
            receipt_bundle._collect_evidence_supporting_artifact_candidate_failures(
                released,
                profile_bytes=self.evidence_artifact_profile_raw,
                owner_catalog_input_bytes=self.owner_catalog_input_raw,
            )[-1],
            receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE,
        )

        mutable_artifact = bytearray(valid_raw)
        mutable_profile = bytearray(self.evidence_artifact_profile_raw)
        mutable_owner_input = bytearray(self.owner_catalog_input_raw)
        original_parser = receipt_bundle._parse_object

        def mutate_callers_after_snapshot(
            raw: bytes,
            label: str,
            failures: list[str],
        ) -> dict[str, object] | None:
            self.assertIsInstance(raw, bytes)
            mutable_artifact.extend(b" ")
            mutable_profile.extend(b" ")
            mutable_owner_input.extend(b" ")
            return original_parser(raw, label, failures)

        with mock.patch.object(
            receipt_bundle,
            "_parse_object",
            side_effect=mutate_callers_after_snapshot,
        ):
            self.assertEqual(
                receipt_bundle._collect_evidence_supporting_artifact_candidate_failures(
                    mutable_artifact,
                    profile_bytes=mutable_profile,
                    owner_catalog_input_bytes=mutable_owner_input,
                ),
                (receipt_bundle.EVIDENCE_SUPPORTING_ARTIFACT_DORMANT_MESSAGE,),
            )

if __name__ == "__main__":
    unittest.main()
