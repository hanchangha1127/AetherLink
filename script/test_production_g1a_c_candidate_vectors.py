#!/usr/bin/env python3
"""Unit tests for the independent G1a-C candidate vector oracle."""

from __future__ import annotations

import contextlib
import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import check_production_g1a_c_candidate_vectors as candidate  # noqa: E402


def _replace_record_bytes(record: dict[str, object], canonical: bytes) -> None:
    record["expectedCanonicalByteCount"] = len(canonical)
    record["expectedCanonicalHex"] = canonical.hex()
    record["expectedSha256Hex"] = candidate.base.sha256_hex(canonical)


def _replace_unsigned_field(
    fixture: dict[str, object],
    name: str,
    field_index: int,
    replacement: bytes,
) -> None:
    record = fixture["objects"][name]  # type: ignore[index]
    object_type = record["objectType"]  # type: ignore[index]
    canonical = bytes.fromhex(record["expectedCanonicalHex"])  # type: ignore[index]
    fields = candidate.base.als1_decode(
        canonical,
        object_type,
        candidate.FIELD_COUNTS[object_type],
    )
    fields[field_index] = replacement
    _replace_record_bytes(record, candidate.base.als1_encode(object_type, fields))


def _resign_field(
    fixture: dict[str, object],
    name: str,
    field_index: int,
    replacement: bytes,
) -> None:
    record = fixture["objects"][name]  # type: ignore[index]
    object_type = record["objectType"]  # type: ignore[index]
    canonical = bytes.fromhex(record["expectedCanonicalHex"])  # type: ignore[index]
    fields = candidate.base.als1_decode(
        canonical,
        object_type,
        candidate.FIELD_COUNTS[object_type],
    )
    fields[field_index] = replacement
    claims = candidate.base.als1_encode(object_type, fields[:-1])
    old_metadata = record["signatures"][0]  # type: ignore[index]
    signer = old_metadata["signer"]
    signature, metadata = candidate.signature_record(
        signer,
        old_metadata["signingDomain"],
        claims,
        candidate.KEY_SCALARS[signer],
        old_metadata["requiredPurpose"],
        old_metadata["requiredPurposeBit"],
    )
    record["expectedClaimsCanonicalHex"] = claims.hex()  # type: ignore[index]
    record["signatures"] = [metadata]  # type: ignore[index]
    _replace_record_bytes(
        record,
        candidate.base.als1_encode(object_type, fields[:-1] + [signature]),
    )


class ProductionG1aCCandidateVectorTests(unittest.TestCase):
    def test_checked_in_candidate_and_legacy_fixtures_are_exact(self) -> None:
        candidate.validate_fixture_file()
        self.assertEqual(
            candidate.base.sha256_hex(candidate.FIXTURE.read_bytes()),
            "e6bc666dbf9fded82d5681fdcfdc2c4c9cd5fa197135fc0673569d35656236af",
        )
        self.assertEqual(
            candidate.base.sha256_hex(candidate.base.FIXTURE.read_bytes()),
            candidate.LEGACY_FIXTURE_SHA256,
        )

    def test_rewrite_is_explicit_and_default_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "candidate.json"
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertEqual(candidate.main(["--fixture", str(fixture)]), 1)
                self.assertFalse(fixture.exists())
                self.assertEqual(
                    candidate.main(["--fixture", str(fixture), "--rewrite"]),
                    0,
                )
                original = fixture.read_bytes()
                self.assertEqual(candidate.main(["--fixture", str(fixture)]), 0)
                self.assertEqual(fixture.read_bytes(), original)

    def test_deterministic_keys_and_low_s_signatures_are_pinned(self) -> None:
        fixture = candidate.build_fixture()
        for name, expected_key_id in candidate.EXPECTED_KEY_IDS.items():
            self.assertEqual(fixture["keys"][name]["keyId"], expected_key_id)
        proof = fixture["objects"]["endpointProofClientPublish"]
        signature = bytes.fromhex(proof["signatures"][0]["fixedLowSDERSignatureHex"])
        _, s = candidate.base.der_decode_signature(signature)
        self.assertLessEqual(s, candidate.base.P256_N // 2)

    def test_als1_and_alp1_reject_reordered_tags_and_trailing_bytes(self) -> None:
        als1 = candidate.base.als1_encode(25, [b"one", b"two"])
        reordered_als1 = bytearray(als1)
        reordered_als1[6] = 2
        with self.assertRaises(candidate.base.VectorError):
            candidate.base.als1_decode(bytes(reordered_als1), 25, 2)
        with self.assertRaises(candidate.base.VectorError):
            candidate.base.als1_decode(als1 + b"\x00", 25, 2)

        alp1 = candidate.alp1_encode(1, [b"one", b"two"])
        reordered_alp1 = bytearray(alp1)
        reordered_alp1[6] = 2
        with self.assertRaises(candidate.CandidateVectorError):
            candidate.alp1_decode(bytes(reordered_alp1), 1, 2)
        with self.assertRaises(candidate.CandidateVectorError):
            candidate.alp1_decode(alp1 + b"\x00", 1, 2)

    def test_der_rejects_high_s_nonminimal_and_trailing_bytes(self) -> None:
        signature = candidate.base.ecdsa_sign_rfc6979(103, b"candidate strict DER")
        r, s = candidate.base.der_decode_signature(signature)
        high_s = candidate.base.der_encode_signature(r, candidate.base.P256_N - s)
        with self.assertRaises(candidate.base.VectorError):
            candidate.base.der_decode_signature(high_s)
        body = b"\x02\x02\x00\x01" + candidate.base._der_integer(s)
        nonminimal = b"\x30" + bytes((len(body),)) + body
        with self.assertRaises(candidate.base.VectorError):
            candidate.base.der_decode_signature(nonminimal)
        with self.assertRaises(candidate.base.VectorError):
            candidate.base.der_decode_signature(signature + b"\x00")

    def test_signature_domain_and_purpose_profiles_are_not_self_describing(self) -> None:
        fixture = candidate.build_fixture()
        metadata = fixture["objects"]["capabilityClientPublish"]["signatures"][0]
        metadata["signingDomain"] = (
            "AetherLink G1a-C candidate-fetch capability service signature v1"
        )
        metadata["requiredPurpose"] = "candidate_fetch"
        metadata["requiredPurposeBit"] = 0x08
        with self.assertRaisesRegex(candidate.CandidateVectorError, "signature profile"):
            candidate.validate_built_fixture(fixture)

    def test_publish_signature_cannot_be_replayed_as_fetch_signature(self) -> None:
        fixture = candidate.build_fixture()
        publish_record = fixture["objects"]["capabilityClientPublish"]
        fetch_record = fixture["objects"]["capabilityRuntimeFetchClient"]
        publish_fields = candidate.base.als1_decode(
            bytes.fromhex(publish_record["expectedCanonicalHex"]), 23, 34
        )
        fetch_fields = candidate.base.als1_decode(
            bytes.fromhex(fetch_record["expectedCanonicalHex"]), 24, 34
        )
        fetch_fields[-1] = publish_fields[-1]
        fetch_record["signatures"][0]["fixedLowSDERSignatureHex"] = publish_fields[-1].hex()
        _replace_record_bytes(fetch_record, candidate.base.als1_encode(24, fetch_fields))
        with self.assertRaises(candidate.base.VectorError):
            candidate.validate_built_fixture(fixture)

    def test_resigned_proof_with_wrong_context_is_rejected(self) -> None:
        fixture = candidate.build_fixture()
        _resign_field(
            fixture,
            "endpointProofClientPublish",
            14,
            candidate.base.ascii_bytes("00" * 32),
        )
        with self.assertRaisesRegex(candidate.CandidateVectorError, "context"):
            candidate.validate_built_fixture(fixture)

    def test_resigned_capability_with_wrong_proof_is_rejected(self) -> None:
        fixture = candidate.build_fixture()
        _resign_field(
            fixture,
            "capabilityClientPublish",
            31,
            candidate.base.ascii_bytes("00" * 32),
        )
        with self.assertRaisesRegex(candidate.CandidateVectorError, "proof digest"):
            candidate.validate_built_fixture(fixture)

    def test_resigned_receipt_with_broken_state_chain_is_rejected(self) -> None:
        fixture = candidate.build_fixture()
        _resign_field(
            fixture,
            "receiptRuntimeFetchClient",
            39,
            candidate.base.ascii_bytes("00" * 32),
        )
        with self.assertRaisesRegex(candidate.CandidateVectorError, "previous state"):
            candidate.validate_built_fixture(fixture)

    def test_grant_requires_all_four_receipts_in_operation_order(self) -> None:
        fixture = candidate.build_fixture()
        grant = fixture["objects"]["p2pGrantEvidence"]
        fields = candidate.base.als1_decode(
            bytes.fromhex(grant["expectedCanonicalHex"]), 25, 34
        )
        digests = list(candidate._unpack_digests(fields[26]))
        digests[0], digests[1] = digests[1], digests[0]
        _replace_unsigned_field(
            fixture,
            "p2pGrantEvidence",
            26,
            b"".join(candidate.base.raw_digest(item) for item in digests),
        )
        with self.assertRaisesRegex(candidate.CandidateVectorError, "receipt digest order"):
            candidate.validate_built_fixture(fixture)

    def test_grant_authorization_must_derive_from_object_25(self) -> None:
        fixture = candidate.build_fixture()
        _replace_unsigned_field(
            fixture,
            "p2pGrantAuthorization",
            2,
            candidate.base.ascii_bytes("00" * 32),
        )
        with self.assertRaisesRegex(candidate.CandidateVectorError, "evidence"):
            candidate.validate_built_fixture(fixture)

    def test_transcript_route_auth_digest_must_be_object_26(self) -> None:
        fixture = candidate.build_fixture()
        replacement = fixture["derived"]["finalP2PDirectAuthorizationDigest"]
        self.assertNotEqual(replacement, fixture["derived"]["grantAuthorizationDigest"])
        _replace_unsigned_field(
            fixture,
            "candidateSecureSessionTranscript",
            20,
            candidate.base.ascii_bytes(replacement),
        )
        with self.assertRaisesRegex(candidate.CandidateVectorError, "object 26"):
            candidate.validate_built_fixture(fixture)

    def test_mutation_inventory_covers_contract_failure_classes(self) -> None:
        fixture = candidate.build_fixture()
        mutation_ids = {item["id"] for item in fixture["mutations"]}
        required = {
            "proof_high_s",
            "proof_wrong_endpoint_key",
            "capability_wrong_key_purpose",
            "receipt_revision_gap",
            "receipt_idempotent_resign",
            "grant_only_three_receipts",
            "grant_authorization_evidence_substitution",
            "transcript_legacy_final_auth",
        }
        self.assertTrue(required.issubset(mutation_ids))
        self.assertGreaterEqual(len(mutation_ids), 24)
        self.assertFalse(fixture["expectedOutcomes"]["productionDurabilityClaim"])


if __name__ == "__main__":
    unittest.main()
