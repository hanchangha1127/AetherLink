#!/usr/bin/env python3
"""Mutation tests for the dormant G0 owner trust bootstrap profile."""

from __future__ import annotations

import copy
import builtins
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

from script import check_v1_g0_independent_validation_context as independent
from script import check_v1_g0_owner_trust_bootstrap as bootstrap
from script import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]


class V1G0OwnerTrustBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_raw = (ROOT / bootstrap.PROFILE_PATH).read_bytes()
        cls.profile = json.loads(cls.profile_raw)
        cls.lineage = tuple((ROOT / path).read_bytes() for path in receipt.LINEAGE_PATHS)

    @staticmethod
    def encoded(value: object) -> bytes:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def validate(self, profile_raw: object, lineage: object | None = None) -> tuple[str, ...]:
        return bootstrap.collect_dormant_owner_trust_bootstrap_profile_failures(
            profile_raw,
            lineage_blobs=self.lineage if lineage is None else lineage,
        )

    def assert_semantic_failure(self, profile: object, needle: str) -> None:
        failures = self.validate(self.encoded(profile))
        self.assertTrue(any(needle in failure for failure in failures), failures)
        self.assertIn(bootstrap.DORMANT_MESSAGE, failures)

    def test_exact_profile_is_only_dormant_and_raw_hash_is_pinned(self) -> None:
        self.assertEqual(self.validate(self.profile_raw), (bootstrap.DORMANT_MESSAGE,))
        self.assertEqual(
            hashlib.sha256(self.profile_raw).hexdigest(),
            bootstrap.EXPECTED_PROFILE_RAW_SHA256,
        )
        self.assertEqual(
            self.profile["ownershipModel"],
            bootstrap.EXPECTED_OWNERSHIP_MODEL,
        )
        self.assertEqual(self.profile["ownershipModel"]["humanPrincipalCount"], 1)
        self.assertEqual(self.profile["ownershipModel"]["canonicalRoleCount"], 14)

        materialization_failures: list[str] = []
        effective_v3 = receipt._materialize_effective_v3(
            self.lineage,
            materialization_failures,
        )
        self.assertEqual(materialization_failures, [])
        approval_roles = [approval["role"] for approval in effective_v3["approvals"]]
        self.assertEqual(len(approval_roles), 14)
        canonical_approval_bytes = self.encoded(approval_roles)
        self.assertEqual(
            hashlib.sha256(canonical_approval_bytes).hexdigest(),
            self.profile["ownershipModel"]["canonicalRoleOrderSha256"],
        )
        derived_roles, _, _, _, _ = receipt._derive_contract_sets(effective_v3, [])
        self.assertEqual(tuple(approval_roles), derived_roles)

        blocker_first_roles: list[str] = []
        for blocker in effective_v3["g0ClosureContract"]["blockerRequirements"]:
            for role in blocker["requiredOwnerRoles"]:
                if role not in blocker_first_roles:
                    blocker_first_roles.append(role)
        self.assertNotEqual(blocker_first_roles, approval_roles)
        self.assertNotEqual(
            hashlib.sha256(self.encoded(blocker_first_roles)).hexdigest(),
            self.profile["ownershipModel"]["canonicalRoleOrderSha256"],
        )
        self.assertNotIn("ownerBindingProfile", self.profile)
        self.assertNotIn("approvalReceiptProfile", self.profile)

    def test_target_and_v3_reuse_drift_fail_closed(self) -> None:
        for section, field, replacement, needle in (
            ("contractBinding", "publicationCommitObjectId", "0" * 40, "contractBinding"),
            ("v3Reuse", "ownerRole", "release_owner", "v3Reuse"),
            ("v3Reuse", "requiredEvidenceKinds", ["published_checkpoint"], "v3Reuse"),
            (
                "v3Reuse",
                "independentTrustInput",
                "reviewed_repository_and_commit_target",
                "v3Reuse",
            ),
        ):
            changed = copy.deepcopy(self.profile)
            changed[section][field] = replacement
            self.assert_semantic_failure(changed, needle)

    def test_policy_pointer_and_adapter_authority_drift_fail_closed(self) -> None:
        for field in bootstrap.OWNERSHIP_MODEL_FIELDS:
            changed = copy.deepcopy(self.profile)
            value = changed["ownershipModel"][field]
            changed["ownershipModel"][field] = value + 1 if isinstance(value, int) else value + "_drift"
            self.assert_semantic_failure(changed, "profile.ownershipModel")

        for field in bootstrap.CONDITIONAL_POLICY_FIELDS:
            changed = copy.deepcopy(self.profile)
            changed["conditionalPolicies"][field] += "_drift"
            self.assert_semantic_failure(changed, "profile.conditionalPolicies")

        for field in ("ownerBindingProfilePointer", "approvalReceiptProfilePointer"):
            changed = copy.deepcopy(self.profile)
            changed["v3Reuse"][field] = "/forbidden"
            self.assert_semantic_failure(changed, "profile.v3Reuse")

        for field in ("genericCandidateFactoryMaySubstitute", "mayCreateAdapterResult"):
            changed = copy.deepcopy(self.profile)
            changed["adapterProjection"][field] = True
            self.assert_semantic_failure(changed, "profile.adapterProjection")

        changed = copy.deepcopy(self.profile)
        changed["adapterProjection"]["verifiedSubjectFields"] = ["targetBinding"]
        self.assert_semantic_failure(changed, "profile.adapterProjection")

    def test_selection_and_authority_state_cannot_advance(self) -> None:
        for field in bootstrap.SELECTION_FIELDS:
            changed = copy.deepcopy(self.profile)
            changed["selection"][field] = "candidate:forbidden"
            self.assert_semantic_failure(changed, "profile.selection")
        for field in bootstrap.STATE_FIELDS:
            changed = copy.deepcopy(self.profile)
            changed["state"][field] = True
            self.assert_semantic_failure(changed, "profile.state")

    def test_unknown_missing_and_reordered_fields_are_rejected(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["privateKey"] = "forbidden"
        self.assert_semantic_failure(changed, "fields or field order")

        changed = copy.deepcopy(self.profile)
        del changed["selection"]["trustAnchorRef"]
        self.assert_semantic_failure(changed, "profile.selection fields or field order")

        changed = copy.deepcopy(self.profile)
        changed["state"] = dict(reversed(tuple(changed["state"].items())))
        self.assert_semantic_failure(changed, "profile.state fields or field order")

    def test_duplicate_nonfinite_and_oversized_json_are_rejected(self) -> None:
        duplicate = self.profile_raw.replace(
            b'"schemaVersion": 1,',
            b'"schemaVersion": 1, "schemaVersion": 1,',
            1,
        )
        duplicate_failures = self.validate(duplicate)
        self.assertTrue(any("duplicate" in item.lower() for item in duplicate_failures))

        nonfinite = self.profile_raw.replace(b'"schemaVersion": 1', b'"schemaVersion": NaN', 1)
        nonfinite_failures = self.validate(nonfinite)
        self.assertTrue(any("finite" in item.lower() for item in nonfinite_failures))

        oversized = b"{" + b" " * bootstrap.MAX_PROFILE_BYTES + b"}"
        oversized_failures = self.validate(oversized)
        self.assertTrue(any("exceeds" in item for item in oversized_failures))

    def test_mutable_buffers_are_snapshotted_before_validation(self) -> None:
        profile_buffer = bytearray(self.profile_raw)
        lineage_buffers = tuple(bytearray(raw) for raw in self.lineage)
        real_snapshot = receipt._bounded_snapshot
        target_ids = {id(profile_buffer), *(id(item) for item in lineage_buffers)}
        mutated: set[int] = set()

        def snapshot_then_mutate(
            value: object,
            label: str,
            maximum_bytes: int,
            failures: list[str],
        ) -> bytes | None:
            snapshot = real_snapshot(value, label, maximum_bytes, failures)
            if id(value) in target_ids and id(value) not in mutated:
                assert isinstance(value, bytearray)
                value[0] ^= 1
                mutated.add(id(value))
            return snapshot

        with mock.patch.object(receipt, "_bounded_snapshot", side_effect=snapshot_then_mutate):
            failures = self.validate(profile_buffer, lineage_buffers)
        self.assertEqual(failures, (bootstrap.DORMANT_MESSAGE,))
        self.assertEqual(mutated, target_ids)

    def test_pure_validator_performs_no_io_crypto_or_adapter_construction(self) -> None:
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("file I/O")),
            mock.patch.object(os, "open", side_effect=AssertionError("file I/O")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network")),
            mock.patch.object(
                socket, "create_connection", side_effect=AssertionError("network")
            ),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess")),
            mock.patch.object(time, "time", side_effect=AssertionError("clock")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("clock")),
            mock.patch.object(os, "urandom", side_effect=AssertionError("entropy")),
            mock.patch.object(
                secrets, "token_bytes", side_effect=AssertionError("entropy")
            ),
            mock.patch.object(
                independent,
                "_build_candidate_independent_adapter_result",
                side_effect=AssertionError("adapter construction"),
            ),
        ):
            self.assertEqual(self.validate(self.profile_raw), (bootstrap.DORMANT_MESSAGE,))

    def test_public_api_exposes_no_authority_or_adapter_constructor(self) -> None:
        self.assertEqual(
            bootstrap.__all__,
            (
                "DORMANT_MESSAGE",
                "EXPECTED_PROFILE_RAW_SHA256",
                "MAX_PROFILE_BYTES",
                "PROFILE_PATH",
                "collect_dormant_owner_trust_bootstrap_profile_failures",
                "main",
            ),
        )
        public_callables = {
            name
            for name, value in vars(bootstrap).items()
            if not name.startswith("_") and callable(value) and name != "Path"
        }
        self.assertEqual(
            public_callables,
            {"collect_dormant_owner_trust_bootstrap_profile_failures", "main"},
        )

    def test_worktree_reader_rejects_a_symlinked_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path, raw in zip(receipt.LINEAGE_PATHS, self.lineage):
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
            profile_path = root / bootstrap.PROFILE_PATH
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_bytes(self.profile_raw)
            self.assertEqual(bootstrap._collect_worktree_failures(root), ())

            external = root / "outside-profile.json"
            external.write_bytes(self.profile_raw)
            profile_path.unlink()
            profile_path.symlink_to(external)
            failures = bootstrap._collect_worktree_failures(root)
            self.assertTrue(any("symlink" in item.lower() for item in failures), failures)

    def test_worktree_final_readback_rejects_mid_validation_replacement(self) -> None:
        targets = (
            (bootstrap.PROFILE_PATH, self.profile_raw),
            (receipt.LINEAGE_PATHS[0], self.lineage[0]),
        )
        for relative_target, original in targets:
            with self.subTest(relative_target=relative_target):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    for path, raw in zip(receipt.LINEAGE_PATHS, self.lineage):
                        destination = root / path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(raw)
                    profile_path = root / bootstrap.PROFILE_PATH
                    profile_path.parent.mkdir(parents=True, exist_ok=True)
                    profile_path.write_bytes(self.profile_raw)

                    real_validate = (
                        bootstrap.collect_dormant_owner_trust_bootstrap_profile_failures
                    )

                    def validate_then_replace(*args: object, **kwargs: object) -> tuple[str, ...]:
                        result = real_validate(*args, **kwargs)
                        (root / relative_target).write_bytes(original + b" ")
                        return result

                    with mock.patch.object(
                        bootstrap,
                        "collect_dormant_owner_trust_bootstrap_profile_failures",
                        side_effect=validate_then_replace,
                    ):
                        failures = bootstrap._collect_worktree_failures(root)
                    self.assertTrue(
                        any(
                            "bytes changed" in item or "identity changed" in item
                            for item in failures
                        ),
                        failures,
                    )


if __name__ == "__main__":
    unittest.main()
