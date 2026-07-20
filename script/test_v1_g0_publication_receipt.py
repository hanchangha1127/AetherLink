#!/usr/bin/env python3
"""Mutation tests for dormant V2 G0 composite publication validation."""

from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import unittest

from script import check_v1_g0_decision as decision
from script import check_v1_g0_publication_receipt as publication


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_REF = "repository:aetherlink-reviewed"
COMMIT_OBJECT_ID = "a" * 40
REMOTE_READBACK_AT = "2026-07-20T10:00:00Z"


class V1G0PublicationReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.commit_blobs = tuple(
            (path, (ROOT / path).read_bytes())
            for path in publication.COMMIT_BLOB_PATHS
        )

    def make_context(
        self,
        *,
        commit_blobs: tuple[tuple[str, object], ...] | None = None,
        reviewed_repository_ref: str = REPOSITORY_REF,
        reviewed_commit_object_id: str = COMMIT_OBJECT_ID,
        reviewed_target_provenance_ref: str = "review:ticket-1",
        commit_repository_ref: str = REPOSITORY_REF,
        resolved_commit_object_id: str = COMMIT_OBJECT_ID,
        commit_provenance_ref: str = "git-object:reader-1",
        remote_repository_ref: str = REPOSITORY_REF,
        remote_commit_object_id: str = COMMIT_OBJECT_ID,
        remote_checkpoint_path: str = publication.AMENDMENT_CHECKPOINT_PATH,
        remote_checkpoint_bytes: object | None = None,
        remote_readback_at: str = REMOTE_READBACK_AT,
        remote_provenance_ref: str = "remote:reader-2",
    ) -> object:
        selected_blobs = self.commit_blobs if commit_blobs is None else commit_blobs
        selected_remote = (
            self.commit_blobs[-1][1]
            if remote_checkpoint_bytes is None
            else remote_checkpoint_bytes
        )
        return publication._build_candidate_publication_validation_context(
            reviewed_repository_ref=reviewed_repository_ref,
            reviewed_commit_object_id=reviewed_commit_object_id,
            reviewed_target_provenance_ref=reviewed_target_provenance_ref,
            commit_repository_ref=commit_repository_ref,
            resolved_commit_object_id=resolved_commit_object_id,
            commit_blobs=selected_blobs,
            commit_provenance_ref=commit_provenance_ref,
            remote_repository_ref=remote_repository_ref,
            remote_commit_object_id=remote_commit_object_id,
            remote_checkpoint_path=remote_checkpoint_path,
            remote_checkpoint_bytes=selected_remote,
            remote_readback_at=remote_readback_at,
            remote_provenance_ref=remote_provenance_ref,
        )

    def receipt(self) -> dict[str, object]:
        return {
            "repositoryRef": REPOSITORY_REF,
            "commitObjectId": COMMIT_OBJECT_ID,
            "parentAssurancePath": publication.PARENT_ASSURANCE_PATH,
            "parentAssuranceSha256": decision.EXPECTED_ASSURANCE_BYTE_SHA256,
            "parentCheckpointPath": publication.PARENT_CHECKPOINT_PATH,
            "parentCheckpointSha256": (
                decision.EXPECTED_ASSURANCE_CHECKPOINT_BYTE_SHA256
            ),
            "amendmentPath": publication.AMENDMENT_PATH,
            "amendmentSha256": decision.EXPECTED_ASSURANCE_AMENDMENT_BYTE_SHA256,
            "amendmentCheckpointPath": publication.AMENDMENT_CHECKPOINT_PATH,
            "amendmentCheckpointSha256": (
                decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256
            ),
            "effectiveAssuranceCanonicalSha256": (
                decision.EXPECTED_EFFECTIVE_ASSURANCE_V2_CANONICAL_SHA256
            ),
            "remoteReadbackAt": REMOTE_READBACK_AT,
            "remoteReadbackSha256": (
                decision.EXPECTED_ASSURANCE_AMENDMENT_CHECKPOINT_BYTE_SHA256
            ),
            "result": "verified",
        }

    @staticmethod
    def encoded(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    def test_exact_four_blob_bundle_reconstructs_without_worktree_reads(self) -> None:
        self.assertEqual(
            publication.collect_amendment_bundle_failures(
                *(raw for _, raw in self.commit_blobs)
            ),
            (),
        )
        for index in range(len(self.commit_blobs)):
            mutated = [raw for _, raw in self.commit_blobs]
            mutated[index] += b" "
            with self.subTest(blob=index):
                self.assertTrue(
                    publication.collect_amendment_bundle_failures(*mutated)
                )

        nested_schema_mutation = self.commit_blobs[2][1].replace(
            b'"path": "/g0ClosureContract/schemaVersion",\n      "value": 2',
            b'"path": "/g0ClosureContract/schemaVersion",\n      "value": 1',
            1,
        )
        self.assertNotEqual(nested_schema_mutation, self.commit_blobs[2][1])
        self.assertTrue(
            publication.collect_amendment_bundle_failures(
                self.commit_blobs[0][1],
                self.commit_blobs[1][1],
                nested_schema_mutation,
                self.commit_blobs[3][1],
            )
        )
        deeply_nested = (b'{"x":' * 800) + b"0" + (b"}" * 800)
        nesting_failures = publication.collect_amendment_bundle_failures(
            deeply_nested,
            self.commit_blobs[1][1],
            self.commit_blobs[2][1],
            self.commit_blobs[3][1],
        )
        self.assertTrue(nesting_failures)

        released = memoryview(self.commit_blobs[0][1])
        released.release()
        released_failures = publication.collect_amendment_bundle_failures(
            released,
            self.commit_blobs[1][1],
            self.commit_blobs[2][1],
            self.commit_blobs[3][1],
        )
        self.assertTrue(released_failures)
        self.assertIn("not a readable byte buffer", released_failures[0])

    def test_context_rejects_ambiguous_or_non_independent_inputs(self) -> None:
        mutations = (
            {"commit_blobs": self.commit_blobs[:-1]},
            {"commit_blobs": tuple(reversed(self.commit_blobs))},
            {"commit_blobs": self.commit_blobs * 1_000},
            {"commit_repository_ref": "repository:other"},
            {"resolved_commit_object_id": "b" * 40},
            {"remote_repository_ref": "repository:other"},
            {"remote_commit_object_id": "b" * 40},
            {"remote_checkpoint_path": publication.PARENT_CHECKPOINT_PATH},
            {"remote_checkpoint_bytes": self.commit_blobs[3][1] + b" "},
            {"remote_readback_at": "2026-07-20T10:00:00+00:00"},
            {"remote_provenance_ref": "git-object:reader-1"},
            {"remote_provenance_ref": "origin/main"},
            {"commit_provenance_ref": "local-reflog:main"},
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                with self.assertRaises(publication._PublicationValidationContextError):
                    self.make_context(**mutation)

    def test_context_snapshots_mutable_inputs_and_is_factory_only(self) -> None:
        mutable_blobs = tuple(
            (path, bytearray(raw)) for path, raw in self.commit_blobs
        )
        mutable_remote = bytearray(self.commit_blobs[-1][1])
        context = self.make_context(
            commit_blobs=mutable_blobs,
            remote_checkpoint_bytes=mutable_remote,
        )
        for _, raw in mutable_blobs:
            raw[0] ^= 1
        mutable_remote[0] ^= 1
        self.assertEqual(
            publication._collect_composite_publication_receipt_candidate_failures(
                self.encoded(self.receipt()),
                context=context,
            ),
            (publication._PUBLICATION_CANDIDATE_DISABLED_MESSAGE,),
        )
        with self.assertRaises(AttributeError):
            context._repository_ref = "repository:mutated"
        with self.assertRaises(AttributeError):
            object.__setattr__(context, "_repository_ref", "repository:mutated")
        with self.assertRaises(TypeError):
            publication._PublicationValidationContext(  # type: ignore[attr-defined]
                object(),
                REPOSITORY_REF,
                COMMIT_OBJECT_ID,
                self.commit_blobs,
                self.commit_blobs[-1][1],
                REMOTE_READBACK_AT,
            )
        forged = tuple.__new__(publication._PublicationValidationContext, ())
        self.assertEqual(
            publication._collect_composite_publication_receipt_candidate_failures(
                self.encoded(self.receipt()),
                context=forged,
            ),
            ("publication validation context is not factory-owned",),
        )
        self.assertNotIn("_PublicationValidationContext", publication.__all__)

    def test_matching_fixture_remains_disabled_and_does_not_mutate_state(self) -> None:
        context = self.make_context()
        amendment_before = copy.deepcopy(
            json.loads((ROOT / publication.AMENDMENT_PATH).read_text(encoding="utf-8"))
        )
        self.assertEqual(
            publication._collect_composite_publication_receipt_candidate_failures(
                self.encoded(self.receipt()),
                context=context,
            ),
            (publication._PUBLICATION_CANDIDATE_DISABLED_MESSAGE,),
        )
        amendment_after = json.loads(
            (ROOT / publication.AMENDMENT_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(amendment_after, amendment_before)
        self.assertEqual(amendment_after["acceptance"]["amendmentPublicationReceipt"], "absent")
        self.assertFalse(amendment_after["acceptance"]["effectiveAssuranceActivated"])
        self.assertFalse(amendment_after["acceptance"]["g0ExitComplete"])
        self.assertFalse(amendment_after["acceptance"]["g1aMayStartNow"])
        self.assertFalse(
            any(
                "authority" in slot.lower() or "activation" in slot.lower()
                for slot in context.__slots__
            )
        )

    def test_receipt_requires_exact_fields_order_and_string_types(self) -> None:
        context = self.make_context()
        canonical = self.receipt()
        mutations: list[dict[str, object]] = []
        for field in publication.PUBLICATION_RECEIPT_FIELDS:
            missing = copy.deepcopy(canonical)
            missing.pop(field)
            mutations.append(missing)

            wrong_type = copy.deepcopy(canonical)
            wrong_type[field] = 1
            mutations.append(wrong_type)
        unknown = copy.deepcopy(canonical)
        unknown["implicitAuthority"] = True
        mutations.append(unknown)
        reordered = {key: canonical[key] for key in reversed(tuple(canonical))}
        mutations.append(reordered)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertTrue(
                    publication._collect_composite_publication_receipt_candidate_failures(
                        self.encoded(mutation),
                        context=context,
                    )
                )

    def test_receipt_rejects_malformed_duplicate_nonfinite_and_oversized_json(self) -> None:
        context = self.make_context()
        canonical = self.encoded(self.receipt())
        duplicate = canonical.replace(
            b'{"repositoryRef":',
            b'{"repositoryRef":"duplicate","repositoryRef":',
            1,
        )
        nonfinite = canonical.replace(b'"result":"verified"', b'"result":NaN')
        deeply_nested = (b'{"x":' * 1_500) + b"0" + (b"}" * 1_500)
        for raw in (
            b"",
            b"null",
            b"{}",
            b"[]",
            b"{",
            duplicate,
            nonfinite,
            deeply_nested,
            memoryview(bytearray(publication.MAX_PUBLICATION_RECEIPT_BYTES + 1)),
            b"{" + (b" " * publication.MAX_PUBLICATION_RECEIPT_BYTES) + b"}",
        ):
            with self.subTest(raw=raw[:32]):
                self.assertTrue(
                    publication._collect_composite_publication_receipt_candidate_failures(
                        raw,
                        context=context,
                    )
                )

    def test_receipt_cannot_define_its_own_target_or_verification_result(self) -> None:
        context = self.make_context()
        canonical = self.receipt()
        mutations = {
            "repositoryRef": "repository:self-asserted",
            "commitObjectId": "b" * 40,
            "parentAssurancePath": publication.AMENDMENT_PATH,
            "parentAssuranceSha256": "0" * 64,
            "parentCheckpointPath": publication.AMENDMENT_CHECKPOINT_PATH,
            "parentCheckpointSha256": "0" * 64,
            "amendmentPath": publication.PARENT_ASSURANCE_PATH,
            "amendmentSha256": "0" * 64,
            "amendmentCheckpointPath": publication.PARENT_CHECKPOINT_PATH,
            "amendmentCheckpointSha256": "0" * 64,
            "effectiveAssuranceCanonicalSha256": "0" * 64,
            "remoteReadbackAt": "2026-07-20T10:00:00+00:00",
            "remoteReadbackSha256": "0" * 64,
            "result": "passed",
        }
        for field, value in mutations.items():
            mutated = copy.deepcopy(canonical)
            mutated[field] = value
            with self.subTest(field=field):
                self.assertTrue(
                    publication._collect_composite_publication_receipt_candidate_failures(
                        self.encoded(mutated),
                        context=context,
                    )
                )

    def test_canonical_candidate_rejects_every_supplied_receipt_bundle(self) -> None:
        self.assertEqual(decision.collect_failures(), [])
        complete_looking = self.encoded(
            {
                "documentType": "aetherlink.v1-g0-receipt-bundle",
                "schemaVersion": "1.0",
                "publicationReceipt": self.receipt(),
                "evidenceCatalog": [],
                "authorityRecords": [],
                "runnerAttestations": [],
                "gateReceipts": [],
                "approvalReceipts": [],
            }
        )
        for supplied in (
            None,
            b"",
            b"null",
            b"{}",
            b"[]",
            self.encoded(self.receipt()),
            complete_looking,
        ):
            with self.subTest(supplied=supplied):
                self.assertEqual(
                    decision.collect_failures(receipt_bundle=supplied),
                    [decision.G0_RECEIPT_ACTIVATION_DISABLED_MESSAGE],
                )
        signature = inspect.signature(decision.collect_failures)
        self.assertEqual(
            set(signature.parameters),
            {"raw_json", "markdown", "root", "verify_files", "receipt_bundle"},
        )


if __name__ == "__main__":
    unittest.main()
