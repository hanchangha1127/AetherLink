#!/usr/bin/env python3
"""Mutation tests for the dormant G0 baseline-evidence readiness contract."""

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

from script import check_v1_g0_baseline_evidence_readiness as readiness
from script import check_v1_g0_checkpoint as checkpoint
from script import check_v1_g0_decision as decision
from script import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]


class V1G0BaselineEvidenceReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_raw = (ROOT / readiness.PROFILE_PATH).read_bytes()
        cls.profile = json.loads(cls.profile_raw)
        cls.lineage = tuple((ROOT / path).read_bytes() for path in receipt.LINEAGE_PATHS)
        cls.documents = tuple(json.loads(raw) for raw in cls.lineage)
        effective_v2 = decision.apply_assurance_amendment_operations(
            cls.documents[0], cls.documents[2]["operations"], []
        )
        cls.effective_v3 = receipt._apply_v3_operations(
            effective_v2, cls.documents[4]["operations"], []
        )
        source_blobs: list[bytes] = []
        for source in cls.effective_v3["sourceRecords"]:
            relative_path = source["path"]
            current = (ROOT / relative_path).read_bytes()
            observed = hashlib.sha256(current).hexdigest()
            compatible = checkpoint.historical_source_compatible_sha256(
                relative_path,
                observed,
            )
            if compatible == observed:
                source_blobs.append(current)
                continue
            historical = subprocess.run(
                [
                    "git",
                    "show",
                    f"{checkpoint.EXPECTED_IMPLEMENTATION_REVISION}:{relative_path}",
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
            if hashlib.sha256(historical).hexdigest() != compatible:
                raise AssertionError(
                    f"historical G0 source bytes do not match {relative_path}"
                )
            source_blobs.append(historical)
        cls.source_blobs = tuple(source_blobs)
        cls.compiled_static_pair = (
            readiness.compile_dormant_static_baseline_evidence_pair(
                cls.profile_raw,
                lineage_blobs=cls.lineage,
                source_blobs=cls.source_blobs,
            )
        )
        cls.compiled_static_candidates = {
            json.loads(raw)["evidenceKind"]: json.loads(raw)
            for raw, _ in cls.compiled_static_pair
        }

    @staticmethod
    def encoded(value: object, *, sort_keys: bool = False) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=sort_keys,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def mutating_snapshot_side_effect(
        buffers: tuple[bytearray, ...],
    ) -> tuple[object, set[int], set[int]]:
        real_snapshot = receipt._bounded_snapshot
        expected_ids = {id(value) for value in buffers}
        mutated_ids: set[int] = set()

        def snapshot_then_mutate(
            value: object,
            label: str,
            maximum_bytes: int,
            failures: list[str],
        ) -> bytes | None:
            snapshot = real_snapshot(value, label, maximum_bytes, failures)
            value_id = id(value)
            if value_id in expected_ids and value_id not in mutated_ids:
                assert isinstance(value, bytearray)
                value[0] ^= 1
                mutated_ids.add(value_id)
            return snapshot

        return snapshot_then_mutate, mutated_ids, expected_ids

    @classmethod
    def manifest_entries(cls, evidence_kind: str) -> list[dict[str, object]]:
        plan = cls.profile["evidencePlans"][readiness.EVIDENCE_KINDS.index(evidence_kind)]
        blobs = cls.observation_blobs(evidence_kind)
        return [
            {
                "inputRole": role,
                "sourceRef": f"observation/{role.replace('_', '-')}",
                "contentType": "application/octet-stream",
                "byteLength": len(raw),
                "rawSha256": hashlib.sha256(raw).hexdigest(),
                "canonicalSha256": None,
            }
            for role, raw in zip(plan["requiredManifestRoles"], blobs)
        ]

    @classmethod
    def observation_blobs(cls, evidence_kind: str) -> tuple[bytes, ...]:
        if evidence_kind not in readiness.EXECUTION_EVIDENCE_KINDS:
            return ()
        plan = cls.profile["evidencePlans"][
            readiness.EVIDENCE_KINDS.index(evidence_kind)
        ]
        blobs: list[bytes] = []
        for role in plan["requiredManifestRoles"]:
            if role == "sanitized_ordered_stdout_stderr":
                raw = (
                    b"synthetic preface\n"
                    + readiness.NO_DEVICE_SUCCESS_MARKER
                    + b"\nsynthetic suffix\n"
                    if evidence_kind == "separately_authorized_full_gate_result"
                    else b"shared synthetic release log\n"
                )
            elif role.startswith("unsigned_") or role == "output_manifest":
                raw = f"synthetic output for {role}\n".encode("utf-8")
            else:
                raw = f"shared synthetic observation for {role}\n".encode("utf-8")
            blobs.append(raw)
        return tuple(blobs)

    @classmethod
    def make_candidate(cls, evidence_kind: str) -> dict[str, object]:
        if evidence_kind in readiness.STATIC_EVIDENCE_KINDS:
            return copy.deepcopy(cls.compiled_static_candidates[evidence_kind])
        index = readiness.EVIDENCE_KINDS.index(evidence_kind)
        source_plan = cls.profile["evidencePlans"][index]
        plan = {
            field: copy.deepcopy(source_plan[field])
            for field in readiness.CANDIDATE_PLAN_FIELDS
        }
        entries = cls.manifest_entries(evidence_kind)
        entries_digest = hashlib.sha256(cls.encoded(entries)).hexdigest()
        manifest = {
            "serialization": "utf8_compact_json_manifest_entry_field_order_v1",
            "entries": entries,
            "entriesCanonicalSha256": entries_digest,
        }
        suffix = {
            "separately_authorized_full_gate_result": "full-gate",
            "android_release_compile_result": "release-pair",
            "macos_release_compile_result": "release-pair",
        }[evidence_kind]
        observation_by_role = dict(
            zip(plan["requiredManifestRoles"], cls.observation_blobs(evidence_kind))
        )
        output_role = {
            "separately_authorized_full_gate_result": "output_manifest",
            "android_release_compile_result": "unsigned_android_release_output_manifest",
            "macos_release_compile_result": "unsigned_macos_release_output_manifest",
        }[evidence_kind]
        payload: dict[str, object] = {
            "executionSessionRefCandidate": f"execution-session-candidate:{suffix}:v1",
            "authorizationRefCandidate": f"authority-candidate:{suffix}:v1",
            "sourcePublicationCommit": receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
            "commandProfileId": plan["commandProfileId"],
            "commandProfileSha256": plan["commandProfileSha256"],
            "commandArgvSha256": plan["commandArgvSha256"],
            "workingDirectorySha256": hashlib.sha256(
                observation_by_role["working_directory"]
            ).hexdigest(),
            "environmentSha256": hashlib.sha256(
                observation_by_role["environment"]
            ).hexdigest(),
            "allowedSideEffectsSha256": plan["allowedSideEffectsSha256"],
            "stepIndex": plan["commandStepIndex"],
            "stepId": plan["commandStepId"],
            "stepArgvSha256": plan["commandStepArgvSha256"],
            "toolchainManifestSha256": hashlib.sha256(
                observation_by_role["toolchain"]
            ).hexdigest(),
            "dependencyManifestSha256": hashlib.sha256(
                observation_by_role["dependencies"]
            ).hexdigest(),
            "observationManifestSha256": hashlib.sha256(
                observation_by_role["egress_process_observation_manifest"]
            ).hexdigest(),
            "sanitizedLogSha256": hashlib.sha256(
                observation_by_role["sanitized_ordered_stdout_stderr"]
            ).hexdigest(),
            "outputManifestSha256": hashlib.sha256(
                observation_by_role[output_role]
            ).hexdigest(),
        }
        if evidence_kind == "macos_release_compile_result":
            started_at = "2026-07-21T03:01:00Z"
            completed_at = "2026-07-21T03:02:00Z"
        else:
            started_at = "2026-07-21T03:00:00Z"
            completed_at = "2026-07-21T03:01:00Z"
        exit_code = 0
        result_profile = cls.profile["resultProfiles"][index]
        return {
            "documentType": "aetherlink.v1-g0-baseline-evidence-candidate",
            "schemaVersion": 1,
            "artifactId": readiness._artifact_id(evidence_kind),
            "evidenceKind": evidence_kind,
            "status": "prepared_unverified_non_authorizing",
            "profileRef": {
                "path": readiness.PROFILE_PATH,
                "profileId": cls.profile["profileId"],
                "rawSha256": readiness.EXPECTED_PROFILE_RAW_SHA256,
            },
            "contractBinding": copy.deepcopy(cls.profile["contractBinding"]),
            "plan": plan,
            "manifest": manifest,
            "result": {
                "resultClass": result_profile["resultClass"],
                "manifestCanonicalSha256": entries_digest,
                "startedAt": started_at,
                "completedAt": completed_at,
                "exitCode": exit_code,
                "payload": payload,
            },
            "trustBoundary": {
                "observationClass": "synthetic_fixture_or_unverified_session_observation_only",
                "independentInputsPresent": [],
                "requiredIndependentInputsAbsent": [
                    "authenticated_provenance",
                    "trusted_authority_and_runner_attestation",
                    "independent_artifact_byte_verification",
                ],
                "catalogRecordDerivable": False,
                "authorityDerivable": False,
                "runnerAttestationDerivable": False,
                "gateReceiptDerivable": False,
            },
            "state": {
                "executionAuthorized": False,
                "evidenceVerified": False,
                "ownerAcceptanceDerived": False,
                "blockerClosureDerived": False,
                "receiptActivationAllowed": False,
                "g0ExitComplete": False,
                "g1aMayStartNow": False,
            },
        }

    @classmethod
    def rebind_observation_blob(
        cls,
        candidate: dict[str, object],
        blobs: tuple[bytes, ...],
        role: str,
        replacement: bytes,
    ) -> tuple[dict[str, object], tuple[bytes, ...]]:
        changed = copy.deepcopy(candidate)
        roles = changed["plan"]["requiredManifestRoles"]
        index = roles.index(role)
        updated_blobs = list(blobs)
        updated_blobs[index] = replacement
        entry = changed["manifest"]["entries"][index]
        entry["byteLength"] = len(replacement)
        entry["rawSha256"] = hashlib.sha256(replacement).hexdigest()
        entries_digest = hashlib.sha256(
            cls.encoded(changed["manifest"]["entries"])
        ).hexdigest()
        changed["manifest"]["entriesCanonicalSha256"] = entries_digest
        changed["result"]["manifestCanonicalSha256"] = entries_digest
        payload_field = {
            "sanitized_ordered_stdout_stderr": "sanitizedLogSha256",
            "working_directory": "workingDirectorySha256",
            "environment": "environmentSha256",
            "toolchain": "toolchainManifestSha256",
            "dependencies": "dependencyManifestSha256",
            "egress_process_observation_manifest": "observationManifestSha256",
            "output_manifest": "outputManifestSha256",
            "unsigned_android_release_output_manifest": "outputManifestSha256",
            "unsigned_macos_release_output_manifest": "outputManifestSha256",
        }.get(role)
        if payload_field is not None:
            changed["result"]["payload"][payload_field] = hashlib.sha256(
                replacement
            ).hexdigest()
        return changed, tuple(updated_blobs)

    @classmethod
    def validate(cls, candidate: object) -> tuple[str, ...]:
        evidence_kind = (
            candidate.get("evidenceKind") if isinstance(candidate, dict) else None
        )
        return readiness.collect_baseline_evidence_candidate_failures(
            cls.encoded(candidate),
            profile_bytes=cls.profile_raw,
            lineage_blobs=cls.lineage,
            source_blobs=(
                cls.source_blobs
                if evidence_kind == "source_hash_readback"
                else None
            ),
            manifest_blobs=(
                cls.observation_blobs(evidence_kind)
                if evidence_kind in readiness.EXECUTION_EVIDENCE_KINDS
                else None
            ),
        )

    def test_profile_and_dormant_plan_are_exact_and_deterministic(self) -> None:
        self.assertEqual(
            readiness.collect_baseline_evidence_readiness_profile_failures(
                self.profile_raw, lineage_blobs=self.lineage
            ),
            (),
        )
        first = readiness.compile_dormant_baseline_evidence_readiness_plan(
            self.profile_raw, lineage_blobs=self.lineage
        )
        second = readiness.compile_dormant_baseline_evidence_readiness_plan(
            bytearray(self.profile_raw),
            lineage_blobs=tuple(bytearray(raw) for raw in self.lineage),
        )
        self.assertEqual(first, second)
        plan = json.loads(first[0])
        self.assertEqual(
            [command["currentAuthorizationState"] for command in plan["commands"]],
            ["not_authorized", "not_authorized"],
        )
        self.assertTrue(all(not command["executionAllowed"] for command in plan["commands"]))
        self.assertTrue(
            all(value is False for value in plan["state"].values())
        )

    def test_static_candidate_compiler_is_exact_deterministic_and_dormant(self) -> None:
        first = readiness.compile_dormant_static_baseline_evidence_pair(
            self.profile_raw,
            lineage_blobs=self.lineage,
            source_blobs=self.source_blobs,
        )
        profile_buffer = bytearray(self.profile_raw)
        lineage_buffers = tuple(bytearray(raw) for raw in self.lineage)
        source_buffers = tuple(bytearray(raw) for raw in self.source_blobs)
        snapshot_side_effect, mutated_ids, expected_ids = (
            self.mutating_snapshot_side_effect(
                (profile_buffer, *lineage_buffers, *source_buffers)
            )
        )
        with mock.patch.object(
            receipt, "_bounded_snapshot", side_effect=snapshot_side_effect
        ) as snapshot:
            second = readiness.compile_dormant_static_baseline_evidence_pair(
                profile_buffer,
                lineage_blobs=lineage_buffers,
                source_blobs=source_buffers,
            )
        self.assertEqual(first, second)
        self.assertEqual(mutated_ids, expected_ids)
        labels = [call.args[1] for call in snapshot.call_args_list]
        self.assertEqual(labels.count("G0 baseline evidence readiness profile"), 1)
        for role in receipt.LINEAGE_ROLES:
            self.assertEqual(
                labels.count(f"G0 baseline evidence readiness lineage {role}"), 1
            )
        for index in range(29):
            self.assertEqual(labels.count(f"static compiler source blobs[{index}]"), 1)
        self.assertEqual(
            [json.loads(raw)["evidenceKind"] for raw, _ in first],
            list(readiness.STATIC_EVIDENCE_KINDS),
        )
        self.assertEqual(
            [(len(raw), digest) for raw, digest in first],
            [
                (
                    5_763,
                    "2d193cb2f3bddf4d202129b4a746a3bd3cbba05f1a879e748f8001eb5c138db4",
                ),
                (
                    10_771,
                    "5df6ba51f3177424407078424fcff90dc2faa8d1c1d4e80e79e96486c3a54fc6",
                ),
            ],
        )
        for raw, digest in first:
            candidate = json.loads(raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            self.assertEqual(self.encoded(candidate), raw)
            self.assertTrue(all(value is False for value in candidate["state"].values()))
            failures = readiness.collect_baseline_evidence_candidate_failures(
                raw,
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=(
                    self.source_blobs
                    if candidate["evidenceKind"] == "source_hash_readback"
                    else None
                ),
            )
            self.assertEqual(failures, (readiness.DORMANT_MESSAGE,))
        self.assertEqual(
            readiness.collect_static_candidate_pair_failures(
                first[0][0],
                first[1][0],
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=self.source_blobs,
            ),
            (readiness.DORMANT_MESSAGE,),
        )

    def test_static_candidate_pair_rejects_swaps_duplicates_and_mutation(self) -> None:
        assurance_raw = self.compiled_static_pair[0][0]
        source_raw = self.compiled_static_pair[1][0]
        for first, second in (
            (source_raw, assurance_raw),
            (assurance_raw, assurance_raw),
            (source_raw, source_raw),
        ):
            failures = readiness.collect_static_candidate_pair_failures(
                first,
                second,
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=self.source_blobs,
            )
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)
        for mutate in (
            lambda value: value["profileRef"].__setitem__("rawSha256", "0" * 64),
            lambda value: value["contractBinding"].__setitem__(
                "publicationCommitObjectId", "0" * 40
            ),
        ):
            changed = json.loads(source_raw)
            mutate(changed)
            failures = readiness.collect_static_candidate_pair_failures(
                assurance_raw,
                self.encoded(changed),
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=self.source_blobs,
            )
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)
        changed_sources = list(self.source_blobs)
        changed_sources[-1] += b"\n"
        with self.assertRaisesRegex(ValueError, "static baseline evidence compilation failed"):
            readiness.compile_dormant_static_baseline_evidence_pair(
                self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=tuple(changed_sources),
            )
        failures = readiness.collect_static_candidate_pair_failures(
            assurance_raw,
            source_raw,
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
            source_blobs=tuple(changed_sources),
        )
        self.assertGreater(len(failures), 1)
        self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)

        reordered_sources = list(self.source_blobs)
        reordered_sources[0], reordered_sources[1] = (
            reordered_sources[1],
            reordered_sources[0],
        )
        with self.assertRaisesRegex(ValueError, "static baseline evidence compilation failed"):
            readiness.compile_dormant_static_baseline_evidence_pair(
                self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=tuple(reordered_sources),
            )

        assurance_buffer = bytearray(assurance_raw)
        source_candidate_buffer = bytearray(source_raw)
        profile_buffer = bytearray(self.profile_raw)
        lineage_buffers = tuple(bytearray(raw) for raw in self.lineage)
        source_buffers = tuple(bytearray(raw) for raw in self.source_blobs)
        snapshot_side_effect, mutated_ids, expected_ids = (
            self.mutating_snapshot_side_effect(
                (
                    assurance_buffer,
                    source_candidate_buffer,
                    profile_buffer,
                    *lineage_buffers,
                    *source_buffers,
                )
            )
        )
        with mock.patch.object(
            receipt, "_bounded_snapshot", side_effect=snapshot_side_effect
        ) as snapshot:
            exact = readiness.collect_static_candidate_pair_failures(
                assurance_buffer,
                source_candidate_buffer,
                profile_bytes=profile_buffer,
                lineage_blobs=lineage_buffers,
                source_blobs=source_buffers,
            )
        self.assertEqual(exact, (readiness.DORMANT_MESSAGE,))
        self.assertEqual(mutated_ids, expected_ids)
        labels = [call.args[1] for call in snapshot.call_args_list]
        self.assertEqual(labels.count("canonical assurance static candidate"), 1)
        self.assertEqual(labels.count("source readback static candidate"), 1)
        self.assertEqual(labels.count("G0 baseline evidence readiness profile"), 1)
        for role in receipt.LINEAGE_ROLES:
            self.assertEqual(
                labels.count(f"G0 baseline evidence readiness lineage {role}"), 1
            )
        for index in range(29):
            self.assertEqual(labels.count(f"static pair source blobs[{index}]"), 1)

    def test_all_five_candidate_shapes_return_only_dormant_sentinel(self) -> None:
        for evidence_kind in readiness.EVIDENCE_KINDS:
            with self.subTest(evidence_kind=evidence_kind):
                self.assertEqual(
                    self.validate(self.make_candidate(evidence_kind)),
                    (readiness.DORMANT_MESSAGE,),
                )

    def test_valid_release_pair_is_still_only_dormant(self) -> None:
        android = self.make_candidate("android_release_compile_result")
        macos = self.make_candidate("macos_release_compile_result")
        self.assertEqual(
            readiness.collect_release_candidate_pair_failures(
                self.encoded(android),
                self.encoded(macos),
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                android_manifest_blobs=self.observation_blobs(
                    "android_release_compile_result"
                ),
                macos_manifest_blobs=self.observation_blobs(
                    "macos_release_compile_result"
                ),
            ),
            (readiness.DORMANT_MESSAGE,),
        )

    def test_profile_command_and_authority_drift_fail_closed(self) -> None:
        for mutate in (
            lambda value: value["commandProfileBindings"][0].__setitem__(
                "currentAuthorizationState", "authorized"
            ),
            lambda value: value["commandProfileBindings"][1].__setitem__(
                "orderedStepsCanonicalSha256", "0" * 64
            ),
            lambda value: value["authorizationBoundary"].__setitem__(
                "candidateValidationMayExecuteCommands", True
            ),
        ):
            profile = copy.deepcopy(self.profile)
            mutate(profile)
            failures = readiness.collect_baseline_evidence_readiness_profile_failures(
                self.encoded(profile), lineage_blobs=self.lineage
            )
            self.assertTrue(failures)

    def test_profile_evidence_order_and_reserved_path_drift_fail_closed(self) -> None:
        for mutate in (
            lambda value: value["evidencePlans"].reverse(),
            lambda value: value["artifactPaths"][0].__setitem__(
                "path", "../g0-canonical-assurance-hash.json"
            ),
            lambda value: value["contractBinding"]["requiredEvidenceKinds"].append(
                "owner_acceptance"
            ),
        ):
            profile = copy.deepcopy(self.profile)
            mutate(profile)
            failures = readiness.collect_baseline_evidence_readiness_profile_failures(
                self.encoded(profile), lineage_blobs=self.lineage
            )
            self.assertTrue(failures)

    def test_run_plan_authority_promotion_fails_closed(self) -> None:
        plan_raw, _ = readiness.compile_dormant_baseline_evidence_readiness_plan(
            self.profile_raw, lineage_blobs=self.lineage
        )
        plan = json.loads(plan_raw)
        profile = json.loads(self.profile_raw)
        for field, value in (
            ("currentAuthorizationState", "authorized"),
            ("authorizationRefCandidate", "authority-candidate:full-gate:v1"),
            ("executionAllowed", True),
        ):
            candidate_plan = copy.deepcopy(plan)
            candidate_plan["commands"][0][field] = value
            self.assertTrue(
                readiness._collect_run_plan_failures(
                    candidate_plan,
                    profile_raw=self.profile_raw,
                    profile=profile,
                )
            )

    def test_candidate_root_status_state_and_derived_kind_fail_closed(self) -> None:
        mutations = []
        candidate = self.make_candidate("canonical_assurance_hash")
        promoted = copy.deepcopy(candidate)
        promoted["status"] = "verified"
        mutations.append(promoted)
        promoted = copy.deepcopy(candidate)
        promoted["state"]["evidenceVerified"] = True
        mutations.append(promoted)
        derived = copy.deepcopy(candidate)
        derived["evidenceKind"] = "owner_acceptance"
        mutations.append(derived)
        extra = copy.deepcopy(candidate)
        extra["activated"] = True
        mutations.append(extra)
        for mutated in mutations:
            failures = self.validate(mutated)
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)
            self.assertEqual(failures.count(readiness.DORMANT_MESSAGE), 1)

    def test_lineage_manifest_hash_length_and_order_drift_fail_closed(self) -> None:
        candidate = self.make_candidate("canonical_assurance_hash")
        mutations = []
        changed = copy.deepcopy(candidate)
        changed["manifest"]["entries"][0]["byteLength"] += 1
        changed["manifest"]["entriesCanonicalSha256"] = hashlib.sha256(
            self.encoded(changed["manifest"]["entries"])
        ).hexdigest()
        changed["result"]["manifestCanonicalSha256"] = changed["manifest"][
            "entriesCanonicalSha256"
        ]
        mutations.append(changed)
        changed = copy.deepcopy(candidate)
        changed["manifest"]["entries"][0]["rawSha256"] = "0" * 64
        mutations.append(changed)
        changed = copy.deepcopy(candidate)
        changed["manifest"]["entries"].reverse()
        mutations.append(changed)
        for mutated in mutations:
            failures = self.validate(mutated)
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)

    def test_source_manifest_count_order_and_hash_drift_fail_closed(self) -> None:
        candidate = self.make_candidate("source_hash_readback")
        mutations = []
        changed = copy.deepcopy(candidate)
        changed["manifest"]["entries"][0], changed["manifest"]["entries"][1] = (
            changed["manifest"]["entries"][1],
            changed["manifest"]["entries"][0],
        )
        mutations.append(changed)
        changed = copy.deepcopy(candidate)
        changed["manifest"]["entries"][0]["sourceRef"] = "docs/wrong.json"
        mutations.append(changed)
        changed = copy.deepcopy(candidate)
        changed["result"]["payload"]["sourceRecordCount"] = 28
        mutations.append(changed)
        changed = copy.deepcopy(candidate)
        changed["result"]["payload"]["mismatchCount"] = 1
        mutations.append(changed)
        for mutated in mutations:
            failures = self.validate(mutated)
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)

    def test_execution_plan_and_result_cross_binding_drift_fail_closed(self) -> None:
        candidate = self.make_candidate("android_release_compile_result")
        for field, value in (
            ("commandProfileSha256", "0" * 64),
            ("commandArgvSha256", "1" * 64),
            ("stepIndex", 1),
            ("stepId", "macos_release_compilation"),
            ("stepArgvSha256", "2" * 64),
            ("allowedSideEffectsSha256", "3" * 64),
        ):
            changed = copy.deepcopy(candidate)
            changed["result"]["payload"][field] = value
            failures = self.validate(changed)
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)

    def test_nonzero_boolean_exit_and_reversed_time_fail_closed(self) -> None:
        candidate = self.make_candidate("separately_authorized_full_gate_result")
        for value in (1, True):
            changed = copy.deepcopy(candidate)
            changed["result"]["exitCode"] = value
            self.assertGreater(len(self.validate(changed)), 1)
        changed = copy.deepcopy(candidate)
        changed["result"]["startedAt"] = "2026-07-21T03:02:00Z"
        changed["result"]["completedAt"] = "2026-07-21T03:01:00Z"
        self.assertGreater(len(self.validate(changed)), 1)

    def test_release_pair_session_environment_and_step_time_drift_fail_closed(self) -> None:
        android = self.make_candidate("android_release_compile_result")
        macos = self.make_candidate("macos_release_compile_result")
        for mutate in (
            lambda value: value["result"]["payload"].__setitem__(
                "executionSessionRefCandidate", "execution-session-candidate:other:v1"
            ),
            lambda value: value["result"]["payload"].__setitem__(
                "environmentSha256", "9" * 64
            ),
            lambda value: value["result"].__setitem__(
                "startedAt", "2026-07-21T03:00:30Z"
            ),
        ):
            changed = copy.deepcopy(macos)
            mutate(changed)
            failures = readiness.collect_release_candidate_pair_failures(
                self.encoded(android),
                self.encoded(changed),
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                android_manifest_blobs=self.observation_blobs(
                    "android_release_compile_result"
                ),
                macos_manifest_blobs=self.observation_blobs(
                    "macos_release_compile_result"
                ),
            )
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)

    def test_source_bytes_are_required_and_rehashed(self) -> None:
        candidate = self.make_candidate("source_hash_readback")
        raw = self.encoded(candidate)
        missing = readiness.collect_baseline_evidence_candidate_failures(
            raw,
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
        )
        self.assertGreater(len(missing), 1)
        changed_blobs = list(self.source_blobs)
        changed_blobs[0] += b"\n"
        drifted = readiness.collect_baseline_evidence_candidate_failures(
            raw,
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
            source_blobs=tuple(changed_blobs),
        )
        self.assertGreater(len(drifted), 1)
        self.assertEqual(drifted[-1], readiness.DORMANT_MESSAGE)

    def test_execution_manifest_bytes_are_required_and_payload_cross_bound(self) -> None:
        evidence_kind = "android_release_compile_result"
        candidate = self.make_candidate(evidence_kind)
        raw = self.encoded(candidate)
        missing = readiness.collect_baseline_evidence_candidate_failures(
            raw,
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
        )
        self.assertGreater(len(missing), 1)
        blobs = self.observation_blobs(evidence_kind)
        changed, changed_blobs = self.rebind_observation_blob(
            candidate,
            blobs,
            "environment",
            b"different synthetic environment manifest\n",
        )
        changed["result"]["payload"]["environmentSha256"] = candidate["result"][
            "payload"
        ]["environmentSha256"]
        failures = readiness.collect_baseline_evidence_candidate_failures(
            self.encoded(changed),
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
            manifest_blobs=changed_blobs,
        )
        self.assertGreater(len(failures), 1)
        self.assertTrue(any("environmentSha256 manifest binding" in item for item in failures))

        changed, changed_blobs = self.rebind_observation_blob(
            candidate,
            blobs,
            "egress_process_observation_manifest",
            b"different canonical egress and process observation manifest\n",
        )
        changed["result"]["payload"]["observationManifestSha256"] = candidate[
            "result"
        ]["payload"]["observationManifestSha256"]
        failures = readiness.collect_baseline_evidence_candidate_failures(
            self.encoded(changed),
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
            manifest_blobs=changed_blobs,
        )
        self.assertGreater(len(failures), 1)
        self.assertTrue(
            any("observationManifestSha256 manifest binding" in item for item in failures)
        )

    def test_full_gate_success_marker_is_required_exactly_once(self) -> None:
        evidence_kind = "separately_authorized_full_gate_result"
        candidate = self.make_candidate(evidence_kind)
        blobs = self.observation_blobs(evidence_kind)
        for replacement in (
            b"synthetic log without the required marker\n",
            readiness.NO_DEVICE_SUCCESS_MARKER
            + b"\n"
            + readiness.NO_DEVICE_SUCCESS_MARKER
            + b"\n",
        ):
            changed, changed_blobs = self.rebind_observation_blob(
                candidate,
                blobs,
                "sanitized_ordered_stdout_stderr",
                replacement,
            )
            failures = readiness.collect_baseline_evidence_candidate_failures(
                self.encoded(changed),
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                manifest_blobs=changed_blobs,
            )
            self.assertGreater(len(failures), 1)
            self.assertTrue(any("success marker once" in item for item in failures))

    def test_candidate_requires_exact_compact_bytes_and_manifest_bounds(self) -> None:
        candidate = self.make_candidate("canonical_assurance_hash")
        failures = readiness.collect_baseline_evidence_candidate_failures(
            self.encoded(candidate) + b"\n",
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
        )
        self.assertTrue(any("compact canonical bytes" in item for item in failures))
        changed = copy.deepcopy(candidate)
        changed["manifest"]["entries"][0]["byteLength"] = (
            readiness.MAX_MANIFEST_BLOB_BYTES + 1
        )
        digest = hashlib.sha256(
            self.encoded(changed["manifest"]["entries"])
        ).hexdigest()
        changed["manifest"]["entriesCanonicalSha256"] = digest
        changed["result"]["manifestCanonicalSha256"] = digest
        failures = self.validate(changed)
        self.assertTrue(any("byteLength is invalid" in item for item in failures))

    def test_release_pair_cross_binds_shared_log_and_snapshots_candidates_once(self) -> None:
        android = self.make_candidate("android_release_compile_result")
        macos = self.make_candidate("macos_release_compile_result")
        android_blobs = self.observation_blobs("android_release_compile_result")
        macos_blobs = self.observation_blobs("macos_release_compile_result")
        changed_macos, changed_macos_blobs = self.rebind_observation_blob(
            macos,
            macos_blobs,
            "sanitized_ordered_stdout_stderr",
            b"different but individually well-formed release log\n",
        )
        failures = readiness.collect_release_candidate_pair_failures(
            self.encoded(android),
            self.encoded(changed_macos),
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
            android_manifest_blobs=android_blobs,
            macos_manifest_blobs=changed_macos_blobs,
        )
        self.assertGreater(len(failures), 1)
        self.assertTrue(
            any(
                "sanitizedLogSha256" in item
                or "sanitized_ordered_stdout_stderr" in item
                for item in failures
            )
        )

        with mock.patch.object(
            receipt, "_bounded_snapshot", wraps=receipt._bounded_snapshot
        ) as snapshot:
            exact = readiness.collect_release_candidate_pair_failures(
                bytearray(self.encoded(android)),
                bytearray(self.encoded(macos)),
                profile_bytes=bytearray(self.profile_raw),
                lineage_blobs=tuple(bytearray(raw) for raw in self.lineage),
                android_manifest_blobs=tuple(bytearray(raw) for raw in android_blobs),
                macos_manifest_blobs=tuple(bytearray(raw) for raw in macos_blobs),
            )
        self.assertEqual(exact, (readiness.DORMANT_MESSAGE,))
        labels = [call.args[1] for call in snapshot.call_args_list]
        self.assertEqual(labels.count("Android release candidate"), 1)
        self.assertEqual(labels.count("macOS release candidate"), 1)

    def test_duplicate_key_oversize_huge_integer_and_lone_surrogate_fail_closed(self) -> None:
        candidate = self.make_candidate("canonical_assurance_hash")
        raw = self.encoded(candidate)
        duplicate = raw.replace(
            b'"schemaVersion":1,',
            b'"schemaVersion":1,"schemaVersion":1,',
            1,
        )
        huge_integer = raw.replace(
            b'"schemaVersion":1,',
            b'"schemaVersion":' + (b"9" * 129) + b",",
            1,
        )
        surrogate = copy.deepcopy(candidate)
        surrogate["artifactId"] = "\ud800"
        surrogate_raw = json.dumps(
            surrogate, ensure_ascii=True, separators=(",", ":")
        ).encode("utf-8")
        for malformed in (
            duplicate,
            huge_integer,
            surrogate_raw,
            b" " * (readiness.MAX_CANDIDATE_BYTES + 1),
        ):
            failures = readiness.collect_baseline_evidence_candidate_failures(
                malformed,
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
            )
            self.assertGreater(len(failures), 1)
            self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)

    def test_mutable_buffers_are_snapshotted_and_released_view_fails_closed(self) -> None:
        candidate_raw = bytearray(
            self.encoded(self.make_candidate("canonical_assurance_hash"))
        )
        failures = readiness.collect_baseline_evidence_candidate_failures(
            candidate_raw,
            profile_bytes=bytearray(self.profile_raw),
            lineage_blobs=tuple(bytearray(raw) for raw in self.lineage),
        )
        self.assertEqual(failures, (readiness.DORMANT_MESSAGE,))
        released = memoryview(candidate_raw)
        released.release()
        failures = readiness.collect_baseline_evidence_candidate_failures(
            released,
            profile_bytes=self.profile_raw,
            lineage_blobs=self.lineage,
        )
        self.assertGreater(len(failures), 1)
        self.assertEqual(failures[-1], readiness.DORMANT_MESSAGE)

    def test_pure_entry_points_perform_no_file_process_socket_or_clock_io(self) -> None:
        candidate_raw = self.encoded(
            self.make_candidate("separately_authorized_full_gate_result")
        )
        source_candidate_raw = self.encoded(
            self.make_candidate("source_hash_readback")
        )
        with (
            mock.patch("builtins.open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "open", side_effect=AssertionError("Path I/O")),
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("Path I/O")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("process I/O")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("socket I/O")),
            mock.patch.object(time, "time", side_effect=AssertionError("clock I/O")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("clock I/O")),
        ):
            plan = readiness.compile_dormant_baseline_evidence_readiness_plan(
                self.profile_raw, lineage_blobs=self.lineage
            )
            static_pair = readiness.compile_dormant_static_baseline_evidence_pair(
                self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=self.source_blobs,
            )
            static_pair_failures = readiness.collect_static_candidate_pair_failures(
                static_pair[0][0],
                static_pair[1][0],
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=self.source_blobs,
            )
            failures = readiness.collect_baseline_evidence_candidate_failures(
                candidate_raw,
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                manifest_blobs=self.observation_blobs(
                    "separately_authorized_full_gate_result"
                ),
            )
            source_failures = readiness.collect_baseline_evidence_candidate_failures(
                source_candidate_raw,
                profile_bytes=self.profile_raw,
                lineage_blobs=self.lineage,
                source_blobs=self.source_blobs,
            )
        self.assertTrue(plan[0])
        self.assertTrue(static_pair[0][0])
        self.assertEqual(static_pair_failures, (readiness.DORMANT_MESSAGE,))
        self.assertEqual(failures, (readiness.DORMANT_MESSAGE,))
        self.assertEqual(source_failures, (readiness.DORMANT_MESSAGE,))


if __name__ == "__main__":
    unittest.main()
