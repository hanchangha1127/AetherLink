#!/usr/bin/env python3
"""Mutation tests for the dormant V3 independent validation context boundary."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
import unittest
from unittest import mock

from script import check_v1_g0_independent_validation_context as independent
from script import check_v1_g0_receipt_bundle as receipt_bundle
from script import test_v1_g0_receipt_bundle as receipt_bundle_tests


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SUBJECT_SHA256 = (
    "63a09934fbfcdaaa2efe0204398c08ccfec65f493e32dc47bed778624a370ce1",
    "b0f0206e20eee129c740cda13211370cf9e0b9ec0a645aeee26573dacda35fdc",
    "3f41229faa3dd0be0006ad9349e6ca5b4fb3b02fe2257e16e67f8f082c6e1d34",
    "fc0f7ad5d04f5164bd54663aa74c4df62e84f63d6efbaa2ce4c09656bc61fc36",
    "1f7c35efbf6f84edb895f586b58f6499ae7d6766b9c9c73853550354a22d0357",
    "c4f7f3a07478b03b56189762b9ea16dcf0e761cbcc24b2c6e8a162030af2d308",
    "6271c6cbdf8b117304cffda724ee43555ffcf897dfa8bfe8dbdfac7a17ebb1f7",
)


class V1G0IndependentValidationContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture_class = receipt_bundle_tests.V1G0ReceiptBundleContractTests
        fixture_class.setUpClass()
        cls.fixture = fixture_class(
            "test_exact_complete_bundle_fixture_is_structural_only_and_dormant"
        )
        cls.raw_blobs = tuple(
            (ROOT / path).read_bytes() for path in receipt_bundle.LINEAGE_PATHS
        )

    @staticmethod
    def encoded(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
    def canonical(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @classmethod
    def make_bundle_and_materials(
        cls,
    ) -> tuple[dict[str, object], tuple[tuple[str, bytes], ...]]:
        bundle = cls.fixture.make_complete_bundle()
        observations: list[tuple[str, bytes]] = []
        evidence_catalog = bundle["evidenceCatalog"]
        assert isinstance(evidence_catalog, list)
        for index, evidence in enumerate(evidence_catalog):
            assert isinstance(evidence, dict)
            raw = cls.canonical(
                {
                    "evidenceKind": evidence["evidenceKind"],
                    "fixtureIndex": index,
                    "sanitized": True,
                }
            )
            evidence["artifactByteLength"] = len(raw)
            evidence["artifactSha256"] = hashlib.sha256(raw).hexdigest()
            observations.append((f"artifact:{evidence['artifactPath']}", raw))

        runner_attestations = bundle["runnerAttestations"]
        gate_receipts = bundle["gateReceipts"]
        assert isinstance(runner_attestations, list)
        assert isinstance(gate_receipts, list)
        for index, runner in enumerate(runner_attestations):
            assert isinstance(runner, dict)
            runner_ref = runner["runnerAttestationRef"]
            assert isinstance(runner_ref, str)
            raw_by_kind = {
                "toolchain": cls.canonical(
                    {"runner": runner_ref, "kind": "toolchain", "version": index + 1}
                ),
                "dependency": cls.canonical(
                    {"runner": runner_ref, "kind": "dependency", "version": index + 1}
                ),
                "observation": cls.canonical(
                    {"runner": runner_ref, "kind": "observation", "version": index + 1}
                ),
                "log": (
                    f"sanitized complete stdout/stderr for {runner_ref}\n"
                ).encode("utf-8"),
            }
            field_by_kind = {
                "toolchain": "toolchainManifestSha256",
                "dependency": "dependencyManifestSha256",
                "observation": "observationManifestSha256",
                "log": "sanitizedLogSha256",
            }
            for kind in ("toolchain", "dependency", "observation", "log"):
                raw = raw_by_kind[kind]
                runner[field_by_kind[kind]] = hashlib.sha256(raw).hexdigest()
                observations.append((f"runner:{runner_ref}:{kind}", raw))
            gate = gate_receipts[index]
            assert isinstance(gate, dict)
            gate["sanitizedLogSha256"] = runner["sanitizedLogSha256"]
        return bundle, tuple(observations)

    @staticmethod
    def target_binding(bundle: dict[str, object]) -> tuple[str, str, str, str, str, str]:
        publication = bundle["publicationReceipt"]
        assert isinstance(publication, dict)
        repository_ref = publication["repositoryRef"]
        commit_object_id = publication["commitObjectId"]
        assert isinstance(repository_ref, str)
        assert isinstance(commit_object_id, str)
        return (
            repository_ref,
            commit_object_id,
            receipt_bundle.V3_CHECKPOINT_PATH,
            receipt_bundle.LINEAGE_RAW_SHA256[-1],
            receipt_bundle.EXPECTED_EFFECTIVE_V3_SHA256,
            receipt_bundle.EXPECTED_CLOSURE_V3_SHA256,
        )

    @classmethod
    def expected_subjects(
        cls,
        bundle: dict[str, object],
        trusted_time: str,
    ) -> dict[str, object]:
        publication = bundle["publicationReceipt"]
        runner_attestations = bundle["runnerAttestations"]
        gate_receipts = bundle["gateReceipts"]
        assert isinstance(publication, dict)
        assert isinstance(runner_attestations, list)
        assert isinstance(gate_receipts, list)
        binding = cls.target_binding(bundle)
        target = {
            "repositoryRef": binding[0],
            "commitObjectId": binding[1],
            "checkpointPath": binding[2],
            "checkpointRawSha256": binding[3],
            "effectiveAssuranceCanonicalSha256": binding[4],
            "effectiveClosureCanonicalSha256": binding[5],
        }
        return {
            "reviewed_repository_and_commit_target": {
                "targetBinding": target,
                "publicationReceipt": publication,
            },
            "independent_remote_v3_checkpoint_bytes": {
                "targetBinding": target,
                "remoteCheckpointPath": publication["remoteCheckpointPath"],
                "remoteCheckpointRawSha256": publication[
                    "remoteCheckpointRawSha256"
                ],
                "remoteReadbackAt": publication["remoteReadbackAt"],
                "remoteReadbackSha256": publication["remoteReadbackSha256"],
            },
            "trusted_owner_identity_registry_and_revocation_snapshot": {
                "targetBinding": target,
                "ownerBindings": bundle["ownerBindings"],
                "approvalReceipts": bundle["approvalReceipts"],
            },
            "trusted_authority_issuer_registry_and_revocation_snapshot": {
                "targetBinding": target,
                "authorityBindings": bundle["authorityBindings"],
            },
            "trusted_runner_registry_and_attestation_verifier_outputs": {
                "targetBinding": target,
                "runnerAttestations": runner_attestations,
                "gateReceipts": gate_receipts,
            },
            "exact_artifact_log_and_runner_manifest_bytes": {
                "targetBinding": target,
                "evidenceCatalog": bundle["evidenceCatalog"],
                "runnerMaterialBindings": [
                    {
                        "runnerAttestationRef": runner["runnerAttestationRef"],
                        "toolchainManifestSha256": runner[
                            "toolchainManifestSha256"
                        ],
                        "dependencyManifestSha256": runner[
                            "dependencyManifestSha256"
                        ],
                        "observationManifestSha256": runner[
                            "observationManifestSha256"
                        ],
                        "sanitizedLogSha256": runner["sanitizedLogSha256"],
                    }
                    for runner in runner_attestations
                    if isinstance(runner, dict)
                ],
                "gateLogBindings": [
                    {
                        "runnerAttestationRef": gate["runnerAttestationRef"],
                        "sanitizedLogSha256": gate["sanitizedLogSha256"],
                    }
                    for gate in gate_receipts
                    if isinstance(gate, dict)
                ],
            },
            "trusted_validation_time": {
                "targetBinding": target,
                "trustedValidationTime": trusted_time,
            },
        }

    @classmethod
    def make_results(
        cls,
        bundle: dict[str, object],
        materials: tuple[tuple[str, object], ...],
        *,
        lineage: tuple[object, ...] | None = None,
        times: tuple[str, ...] | None = None,
        adapter_refs: tuple[str, ...] | None = None,
        observation_refs: tuple[str, ...] | None = None,
        target_overrides: dict[int, dict[str, str]] | None = None,
        observation_overrides: dict[int, tuple[tuple[str, object], ...]] | None = None,
        mutable_subjects: bool = False,
    ) -> tuple[independent._IndependentAdapterResult, ...]:
        if lineage is None:
            lineage = cls.raw_blobs
        if times is None:
            times = (
                "2026-07-20T10:00:00Z",
                "2026-07-20T10:00:00Z",
                "2026-07-20T10:16:00Z",
                "2026-07-20T10:09:00Z",
                "2026-07-20T10:09:00Z",
                "2026-07-20T10:11:00Z",
                "2026-07-20T10:20:00Z",
            )
        if adapter_refs is None:
            adapter_refs = tuple(f"trusted-adapter:{index + 1}" for index in range(7))
        if observation_refs is None:
            observation_refs = tuple(
                f"independent-observation:{index + 1}" for index in range(7)
            )
        target_overrides = target_overrides or {}
        observation_overrides = observation_overrides or {}
        binding = cls.target_binding(bundle)
        trusted_time = times[-1]
        subjects = cls.expected_subjects(bundle, trusted_time)
        kinds = tuple(subjects)
        observations: tuple[tuple[tuple[str, object], ...], ...] = (
            tuple(zip(receipt_bundle.LINEAGE_PATHS, lineage)),
            ((receipt_bundle.V3_CHECKPOINT_PATH, lineage[-1]),),
            (("owner-registry-and-revocation-snapshot", b"owner-registry-v1"),),
            (("authority-registry-and-revocation-snapshot", b"authority-registry-v1"),),
            (("runner-registry-and-verifier-output", b"runner-verifier-v1"),),
            materials,
            (("trusted-validation-time-token", b"trusted-time-source-v1"),),
        )
        results: list[independent._IndependentAdapterResult] = []
        for index, kind in enumerate(kinds):
            target = {
                "repository_ref": binding[0],
                "commit_object_id": binding[1],
                "checkpoint_path": binding[2],
                "checkpoint_raw_sha256": binding[3],
                "effective_assurance_sha256": binding[4],
                "effective_closure_sha256": binding[5],
            }
            target.update(target_overrides.get(index, {}))
            subject_bytes: object = cls.canonical(copy.deepcopy(subjects[kind]))
            if mutable_subjects:
                subject_bytes = bytearray(subject_bytes)
            results.append(
                independent._build_candidate_independent_adapter_result(
                    kind=kind,
                    **target,
                    adapter_ref=adapter_refs[index],
                    observation_ref=observation_refs[index],
                    observed_at=times[index],
                    verified_subject=subject_bytes,
                    observation_blobs=observation_overrides.get(
                        index,
                        observations[index],
                    ),
                )
            )
        return tuple(results)

    @classmethod
    def make_context(
        cls,
        bundle: dict[str, object],
        materials: tuple[tuple[str, object], ...],
        **result_options: object,
    ) -> independent._IndependentValidationContext:
        lineage = result_options.get("lineage", cls.raw_blobs)
        assert isinstance(lineage, tuple)
        results = cls.make_results(bundle, materials, **result_options)
        return independent._build_candidate_independent_validation_context(
            lineage_blobs=lineage,
            adapter_results=results,
        )

    def test_effective_policy_has_exact_seven_inputs_and_static_checker_is_dormant(
        self,
    ) -> None:
        failures: list[str] = []
        inputs = independent._effective_independent_trust_inputs(
            self.raw_blobs,
            failures,
        )
        self.assertEqual(failures, [])
        self.assertEqual(
            inputs,
            (
                "reviewed_repository_and_commit_target",
                "independent_remote_v3_checkpoint_bytes",
                "trusted_owner_identity_registry_and_revocation_snapshot",
                "trusted_authority_issuer_registry_and_revocation_snapshot",
                "trusted_runner_registry_and_attestation_verifier_outputs",
                "exact_artifact_log_and_runner_manifest_bytes",
                "trusted_validation_time",
            ),
        )
        self.assertEqual(independent._collect_worktree_contract_failures(), ())
        self.assertEqual(independent.__all__, ())

    def test_exact_context_and_material_bytes_remain_dormant(self) -> None:
        bundle, materials = self.make_bundle_and_materials()
        subjects = self.expected_subjects(bundle, "2026-07-20T10:20:00Z")
        self.assertEqual(
            tuple(
                hashlib.sha256(self.canonical(subject)).hexdigest()
                for subject in subjects.values()
            ),
            EXPECTED_SUBJECT_SHA256,
        )
        context = self.make_context(bundle, materials)
        raw = self.encoded(bundle)
        self.assertEqual(
            receipt_bundle._collect_complete_bundle_candidate_failures(
                raw,
                lineage_blobs=self.raw_blobs,
            ),
            (receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,),
        )
        self.assertEqual(
            independent._collect_context_bound_complete_bundle_failures(
                raw,
                context=context,
            ),
            (independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,),
        )

    def test_result_and_context_are_factory_only_deep_immutable_snapshots(self) -> None:
        bundle, immutable_materials = self.make_bundle_and_materials()
        mutable_lineage = tuple(bytearray(raw) for raw in self.raw_blobs)
        mutable_materials = tuple(
            (label, bytearray(raw)) for label, raw in immutable_materials
        )
        context = self.make_context(
            bundle,
            mutable_materials,
            lineage=mutable_lineage,
        )
        for raw in mutable_lineage:
            raw[0] ^= 1
        for _, raw in mutable_materials:
            assert isinstance(raw, bytearray)
            raw[0] ^= 1
        self.assertEqual(
            independent._collect_context_bound_complete_bundle_failures(
                self.encoded(bundle),
                context=context,
            ),
            (independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,),
        )
        with self.assertRaises(AttributeError):
            context._trusted_validation_time = "2026-07-20T10:30:00Z"
        with self.assertRaises(AttributeError):
            context._adapter_results[0]._subject_bytes = b"forged"
        with self.assertRaises(TypeError):
            independent._IndependentValidationContext(object(), (), (), "")
        with self.assertRaises(TypeError):
            independent._IndependentAdapterResult(
                object(),
                "kind",
                ("", "", "", "", "", ""),
                "adapter",
                "observation",
                "2026-07-20T10:00:00Z",
                b"{}",
                (),
            )
        forged = object.__new__(independent._IndependentValidationContext)
        self.assertEqual(
            independent._collect_context_bound_complete_bundle_failures(
                self.encoded(bundle),
                context=forged,
            ),
            (
                "independent validation context is not factory-owned",
                independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,
            ),
        )
        malformed = independent._new_context_identity(
            (self.raw_blobs, (), "2026-07-20T10:20:00Z")
        )
        self.assertEqual(
            independent._collect_context_bound_complete_bundle_failures(
                self.encoded(bundle),
                context=malformed,
            ),
            (
                "independent validation context is not factory-owned",
                independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,
            ),
        )

    def test_context_rejects_missing_reordered_ambiguous_and_drifted_inputs(self) -> None:
        bundle, materials = self.make_bundle_and_materials()
        results = self.make_results(bundle, materials)
        cases: tuple[tuple[object, ...], ...] = (
            results[:-1],
            tuple(reversed(results)),
            results + (results[-1],),
            results[:1] + (object(),) + results[2:],
        )
        for index, candidate in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(independent._IndependentValidationContextError):
                    independent._build_candidate_independent_validation_context(
                        lineage_blobs=self.raw_blobs,
                        adapter_results=candidate,
                    )

        duplicate_refs = tuple("trusted-adapter:duplicate" for _ in range(7))
        with self.assertRaises(independent._IndependentValidationContextError):
            self.make_context(bundle, materials, adapter_refs=duplicate_refs)
        duplicate_observations = tuple(
            "independent-observation:duplicate" for _ in range(7)
        )
        with self.assertRaises(independent._IndependentValidationContextError):
            self.make_context(
                bundle,
                materials,
                observation_refs=duplicate_observations,
            )
        with self.assertRaises(independent._IndependentValidationContextError):
            self.make_context(
                bundle,
                materials,
                target_overrides={3: {"repository_ref": "repository:other"}},
            )
        with self.assertRaises(independent._IndependentValidationContextError):
            self.make_context(
                bundle,
                materials,
                observation_overrides={
                    1: ((receipt_bundle.V3_CHECKPOINT_PATH, self.raw_blobs[-1] + b" "),)
                },
            )
        early_trusted_times = (
            "2026-07-20T10:00:00Z",
            "2026-07-20T10:00:00Z",
            "2026-07-20T10:16:00Z",
            "2026-07-20T10:09:00Z",
            "2026-07-20T10:09:00Z",
            "2026-07-20T10:11:00Z",
            "2026-07-20T10:10:00Z",
        )
        with self.assertRaises(independent._IndependentValidationContextError):
            self.make_context(bundle, materials, times=early_trusted_times)

    def test_adapter_result_rejects_oversized_released_or_duplicate_observations(
        self,
    ) -> None:
        bundle, materials = self.make_bundle_and_materials()
        binding = self.target_binding(bundle)
        subject = self.expected_subjects(bundle, "2026-07-20T10:20:00Z")[
            "trusted_validation_time"
        ]

        def build(
            observations: tuple[tuple[str, object], ...],
            *,
            subject_bytes: object | None = None,
        ) -> object:
            return independent._build_candidate_independent_adapter_result(
                kind="trusted_validation_time",
                repository_ref=binding[0],
                commit_object_id=binding[1],
                checkpoint_path=binding[2],
                checkpoint_raw_sha256=binding[3],
                effective_assurance_sha256=binding[4],
                effective_closure_sha256=binding[5],
                adapter_ref="trusted-adapter:time",
                observation_ref="independent-observation:time",
                observed_at="2026-07-20T10:20:00Z",
                verified_subject=(
                    self.canonical(subject) if subject_bytes is None else subject_bytes
                ),
                observation_blobs=observations,
            )

        released = memoryview(b"released")
        released.release()
        cases = (
            (("oversized", bytearray(independent.MAX_ADAPTER_OBSERVATION_BYTES + 1)),),
            (("released", released),),
            (("same", b"one"), ("same", b"two")),
            (),
        )
        for index, observations in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(independent._IndependentAdapterResultError):
                    build(observations)

        with mock.patch.object(independent, "MAX_ADAPTER_SUBJECT_BYTES", 8):
            with self.assertRaises(independent._IndependentAdapterResultError):
                build((("time", b"time"),))
        with mock.patch.object(independent, "MAX_ADAPTER_OBSERVATION_COUNT", 1):
            with self.assertRaises(independent._IndependentAdapterResultError):
                build((("one", b"one"), ("two", b"two")))
        with mock.patch.object(independent, "MAX_ADAPTER_TOTAL_OBSERVATION_BYTES", 3):
            with self.assertRaises(independent._IndependentAdapterResultError):
                build((("aggregate", b"four"),))

        context = self.make_context(bundle, materials)
        raw = self.encoded(bundle)
        with mock.patch.object(
            receipt_bundle,
            "MAX_COMPLETE_BUNDLE_BYTES",
            len(raw) - 1,
        ):
            failures = independent._collect_context_bound_complete_bundle_failures(
                raw,
                context=context,
            )
        self.assertTrue(any("exceeds" in failure for failure in failures), failures)
        self.assertEqual(
            failures[-1],
            independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,
        )

    def test_context_rejects_coordinated_structurally_valid_self_asserted_drift(
        self,
    ) -> None:
        trusted_bundle, materials = self.make_bundle_and_materials()
        context = self.make_context(trusted_bundle, materials)
        candidates: list[dict[str, object]] = []

        repository_drift = copy.deepcopy(trusted_bundle)
        publication = repository_drift["publicationReceipt"]
        assert isinstance(publication, dict)
        publication["repositoryRef"] = "repository:coordinated-other"
        candidates.append(repository_drift)

        owner_drift = copy.deepcopy(trusted_bundle)
        owners = owner_drift["ownerBindings"]
        approvals = owner_drift["approvalReceipts"]
        assert isinstance(owners, list) and isinstance(approvals, list)
        assert isinstance(owners[0], dict) and isinstance(approvals[0], dict)
        owners[0]["ownerIdentityRef"] = "owner:coordinated-other"
        approvals[0]["ownerIdentityRef"] = "owner:coordinated-other"
        candidates.append(owner_drift)

        artifact_drift = copy.deepcopy(trusted_bundle)
        evidence = artifact_drift["evidenceCatalog"]
        assert isinstance(evidence, list) and isinstance(evidence[0], dict)
        evidence[0]["artifactSha256"] = "f" * 64
        candidates.append(artifact_drift)

        log_drift = copy.deepcopy(trusted_bundle)
        runners = log_drift["runnerAttestations"]
        gates = log_drift["gateReceipts"]
        assert isinstance(runners, list) and isinstance(gates, list)
        assert isinstance(runners[0], dict) and isinstance(gates[0], dict)
        runners[0]["sanitizedLogSha256"] = "e" * 64
        gates[0]["sanitizedLogSha256"] = "e" * 64
        candidates.append(log_drift)

        authority_drift = copy.deepcopy(trusted_bundle)
        authorities = authority_drift["authorityBindings"]
        assert isinstance(authorities, list) and isinstance(authorities[0], dict)
        authorities[0]["authorityIssuerRef"] = "authority-issuer:coordinated-other"
        authorities[0]["revocationRef"] = "authority-revocation:coordinated-other"
        candidates.append(authority_drift)

        runner_identity_drift = copy.deepcopy(trusted_bundle)
        drifted_runners = runner_identity_drift["runnerAttestations"]
        assert isinstance(drifted_runners, list) and isinstance(drifted_runners[0], dict)
        drifted_runners[0]["runnerIdentityRef"] = "trusted-runner:coordinated-other"
        drifted_runners[0]["provenanceRef"] = "runner-provenance:coordinated-other"
        candidates.append(runner_identity_drift)

        evidence_verifier_drift = copy.deepcopy(trusted_bundle)
        drifted_evidence = evidence_verifier_drift["evidenceCatalog"]
        assert isinstance(drifted_evidence, list) and isinstance(drifted_evidence[0], dict)
        drifted_evidence[0]["verifierIdentityRef"] = "verifier:coordinated-other"
        drifted_evidence[0]["provenanceRef"] = "evidence-provenance:coordinated-other"
        candidates.append(evidence_verifier_drift)

        remote_time_drift = copy.deepcopy(trusted_bundle)
        drifted_publication = remote_time_drift["publicationReceipt"]
        assert isinstance(drifted_publication, dict)
        drifted_publication["remoteReadbackAt"] = "2026-07-20T10:01:00Z"
        candidates.append(remote_time_drift)

        for index, candidate in enumerate(candidates):
            with self.subTest(case=index):
                raw = self.encoded(candidate)
                self.assertEqual(
                    receipt_bundle._collect_complete_bundle_candidate_failures(
                        raw,
                        lineage_blobs=self.raw_blobs,
                    ),
                    (receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,),
                )
                failures = independent._collect_context_bound_complete_bundle_failures(
                    raw,
                    context=context,
                )
                self.assertGreater(len(failures), 1)
                self.assertEqual(
                    failures[-1],
                    independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,
                )

    def test_material_coverage_hash_and_length_are_bound_to_exact_bytes(self) -> None:
        bundle, materials = self.make_bundle_and_materials()
        flipped = bytes([materials[1][1][0] ^ 1]) + materials[1][1][1:]
        length_drift_bundle = copy.deepcopy(bundle)
        length_drift_evidence = length_drift_bundle["evidenceCatalog"]
        assert isinstance(length_drift_evidence, list)
        assert isinstance(length_drift_evidence[0], dict)
        length_drift_evidence[0]["artifactByteLength"] += 1
        cases = (
            (bundle, materials[:-1], "coverage is not exact"),
            (bundle, materials + (("orphan:extra", b"extra"),), "coverage is not exact"),
            (
                bundle,
                (materials[1], materials[0]) + materials[2:],
                "coverage is not exact",
            ),
            (
                bundle,
                materials[:1] + ((materials[1][0], flipped),) + materials[2:],
                "SHA-256 does not match",
            ),
            (length_drift_bundle, materials, "byte length does not match"),
        )
        for index, (candidate_bundle, candidate_materials, expected_failure) in enumerate(cases):
            with self.subTest(case=index):
                context = self.make_context(candidate_bundle, candidate_materials)
                failures = independent._collect_context_bound_complete_bundle_failures(
                    self.encoded(candidate_bundle),
                    context=context,
                )
                self.assertGreater(len(failures), 1)
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    failures,
                )
                self.assertEqual(
                    failures[-1],
                    independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,
                )

    def test_bundle_times_are_bounded_by_independent_observations_and_trusted_time(
        self,
    ) -> None:
        bundle, materials = self.make_bundle_and_materials()
        approvals = bundle["approvalReceipts"]
        assert isinstance(approvals, list)
        for approval in approvals:
            assert isinstance(approval, dict)
            approval["acceptedAt"] = "2026-07-20T10:19:00Z"
        times = (
            "2026-07-20T10:00:00Z",
            "2026-07-20T10:00:00Z",
            "2026-07-20T10:18:00Z",
            "2026-07-20T10:09:00Z",
            "2026-07-20T10:09:00Z",
            "2026-07-20T10:11:00Z",
            "2026-07-20T10:18:00Z",
        )
        context = self.make_context(bundle, materials, times=times)
        self.assertEqual(
            receipt_bundle._collect_complete_bundle_candidate_failures(
                self.encoded(bundle),
                lineage_blobs=self.raw_blobs,
            ),
            (receipt_bundle.COMPLETE_BUNDLE_DORMANT_MESSAGE,),
        )
        failures = independent._collect_context_bound_complete_bundle_failures(
            self.encoded(bundle),
            context=context,
        )
        self.assertTrue(any("trusted validation time" in item for item in failures))
        self.assertTrue(any("predates the records" in item for item in failures))

    def test_supplied_inputs_are_single_snapshotted_and_pure(self) -> None:
        bundle, immutable_materials = self.make_bundle_and_materials()
        reviewed_lineage = tuple(bytearray(raw) for raw in self.raw_blobs)
        context_lineage = tuple(bytearray(raw) for raw in self.raw_blobs)
        remote_checkpoint = bytearray(self.raw_blobs[-1])
        mutable_materials = tuple(
            (label, bytearray(raw)) for label, raw in immutable_materials
        )
        mutable_bundle = bytearray(self.encoded(bundle))
        original_snapshot = receipt_bundle._bounded_snapshot
        snapshot_counts: dict[int, int] = {}
        retained_buffers: dict[int, bytearray] = {}

        def mutate_after_snapshot(
            value: object,
            label: str,
            maximum_bytes: int,
            failures: list[str],
        ) -> bytes | None:
            raw = original_snapshot(value, label, maximum_bytes, failures)
            if isinstance(value, bytearray) and raw is not None:
                identity = id(value)
                retained_buffers[identity] = value
                snapshot_counts[identity] = snapshot_counts.get(identity, 0) + 1
                if snapshot_counts[identity] == 1:
                    value[:] = b"{}"
            return raw

        with (
            mock.patch.object(
                receipt_bundle,
                "_bounded_snapshot",
                side_effect=mutate_after_snapshot,
            ),
            mock.patch("builtins.open", side_effect=AssertionError("unexpected file I/O")),
            mock.patch.object(Path, "open", side_effect=AssertionError("unexpected file I/O")),
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected file I/O")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("unexpected socket I/O")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("unexpected process I/O")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("unexpected process I/O")),
            mock.patch.object(time, "time", side_effect=AssertionError("unexpected clock I/O")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("unexpected clock I/O")),
        ):
            results = self.make_results(
                bundle,
                mutable_materials,
                lineage=reviewed_lineage,
                observation_overrides={
                    1: ((receipt_bundle.V3_CHECKPOINT_PATH, remote_checkpoint),),
                },
                mutable_subjects=True,
            )
            context = independent._build_candidate_independent_validation_context(
                lineage_blobs=context_lineage,
                adapter_results=results,
            )
            self.assertEqual(
                independent._collect_context_bound_complete_bundle_failures(
                    mutable_bundle,
                    context=context,
                ),
                (independent.INDEPENDENT_VALIDATION_CONTEXT_DORMANT_MESSAGE,),
            )
        self.assertEqual(len(snapshot_counts), 44)
        self.assertEqual(set(snapshot_counts.values()), {1})


if __name__ == "__main__":
    unittest.main()
