#!/usr/bin/env python3
"""Mutation tests for the dormant V3 G0 receipt-bundle contract lineage."""

from __future__ import annotations

import copy
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
        self.assertEqual(receipt_bundle.__all__, [])
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


if __name__ == "__main__":
    unittest.main()
