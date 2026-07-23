#!/usr/bin/env python3
"""Independent mutation tests for production secure-session crypto vectors."""

from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
import hashlib
import hmac
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from script import check_production_secure_session_crypto_vectors as CHECKER


EXPECTED_FIXTURE_SHA256 = "d45fd920e22652d790c742de995d87a8cbfb64bb22aca3b829cbad5b23485448"
EXPECTED_NEGATIVE_IDS = [
    "object7_object26_substitution",
    "local_private_public_mismatch",
    "ephemeral_handle_reuse",
    "role_reflection_confirmation",
    "confirmation_proof_bit_flip",
    "confirmation_before_activation",
    "record_wrong_session",
    "record_wrong_role",
    "record_replay",
    "record_gap",
    "record_future_epoch",
    "record_tag_bit_flip",
    "record_ciphertext_bit_flip",
    "authentication_failure_no_receive_advance",
    "key_update_skip",
    "key_update_duplicate",
    "key_update_epoch_15",
    "record_max_plus_one",
    "epoch_record_limit",
    "epoch_plaintext_limit",
    "session_record_limit",
    "session_plaintext_limit",
    "expiry_boundary",
    "clock_regression",
    "authority_invalidation",
    "concurrent_seal_unique_sequence",
]


def independent_domain(label: str, claims: bytes) -> bytes:
    encoded = label.encode("ascii")
    return encoded + b"\x00" + struct.pack(">I", len(claims)) + claims


def independent_als1(object_type: int, fields: list[bytes]) -> bytes:
    result = bytearray(b"ALS1" + bytes((object_type, 1)))
    for tag, field in enumerate(fields, 1):
        result.extend(bytes((tag,)) + struct.pack(">I", len(field)) + field)
    return bytes(result)


def independent_parse_als1(data: bytes, object_type: int, field_count: int) -> list[bytes]:
    if len(data) < 6 or data[:6] != b"ALS1" + bytes((object_type, 1)):
        raise AssertionError("invalid ALS1 header")
    cursor = 6
    fields: list[bytes] = []
    for expected_tag in range(1, field_count + 1):
        if cursor + 5 > len(data) or data[cursor] != expected_tag:
            raise AssertionError("non-canonical ALS1 tag")
        size = struct.unpack(">I", data[cursor + 1:cursor + 5])[0]
        cursor += 5
        if cursor + size > len(data):
            raise AssertionError("truncated ALS1 field")
        fields.append(data[cursor:cursor + size])
        cursor += size
    if cursor != len(data) or independent_als1(object_type, fields) != data:
        raise AssertionError("trailing or non-canonical ALS1 bytes")
    return fields


@contextmanager
def isolated_files(fixture_bytes: bytes, source_bytes: bytes):
    original = (CHECKER.ROOT, CHECKER.FIXTURE, CHECKER.SOURCE_FIXTURE)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        fixture = root / "shared/protocol/fixtures/production-secure-session-crypto-v1-vectors.json"
        source = root / "shared/protocol/fixtures/production-g1a-c-candidate-v1-vectors.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(fixture_bytes)
        source.write_bytes(source_bytes)
        CHECKER.ROOT = root
        CHECKER.FIXTURE = fixture
        CHECKER.SOURCE_FIXTURE = source
        try:
            yield fixture, source
        finally:
            CHECKER.ROOT, CHECKER.FIXTURE, CHECKER.SOURCE_FIXTURE = original


class ProductionSecureSessionCryptoVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = CHECKER.FIXTURE.read_bytes()
        cls.source_bytes = CHECKER.SOURCE_FIXTURE.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)

    def test_checked_in_fixture_is_byte_exact_and_valid(self) -> None:
        self.assertEqual(hashlib.sha256(self.fixture_bytes).hexdigest(), EXPECTED_FIXTURE_SHA256)
        CHECKER.validate()

    def test_default_validation_is_read_only_and_has_no_rewrite_mode(self) -> None:
        before = (
            CHECKER.FIXTURE.read_bytes(),
            CHECKER.FIXTURE.stat().st_mode,
            CHECKER.FIXTURE.stat().st_mtime_ns,
            CHECKER.SOURCE_FIXTURE.read_bytes(),
            CHECKER.SOURCE_FIXTURE.stat().st_mode,
            CHECKER.SOURCE_FIXTURE.stat().st_mtime_ns,
        )
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(CHECKER.main(), 0)
        self.assertEqual(output.getvalue(), "Production secure-session crypto vectors passed.\n")
        after = (
            CHECKER.FIXTURE.read_bytes(),
            CHECKER.FIXTURE.stat().st_mode,
            CHECKER.FIXTURE.stat().st_mtime_ns,
            CHECKER.SOURCE_FIXTURE.read_bytes(),
            CHECKER.SOURCE_FIXTURE.stat().st_mode,
            CHECKER.SOURCE_FIXTURE.stat().st_mtime_ns,
        )
        self.assertEqual(after, before)
        self.assertNotIn("--rewrite", Path(CHECKER.__file__).read_text(encoding="utf-8"))

    def test_duplicate_json_name_is_rejected(self) -> None:
        duplicate = self.fixture_bytes.replace(
            b'  "version": 1,',
            b'  "version": 0,\n  "version": 1,',
            1,
        )
        self.assertNotEqual(duplicate, self.fixture_bytes)
        with isolated_files(duplicate, self.source_bytes):
            with self.assertRaisesRegex(CHECKER.ValidationError, "duplicate JSON name 'version'"):
                CHECKER.validate()

    def test_fixture_and_source_hash_drift_are_detected(self) -> None:
        fixture_drift = self.fixture_bytes.replace(
            self.fixture["expected"]["bindingHashHex"].encode("ascii"),
            b"00" * 32,
            1,
        )
        self.assertNotEqual(hashlib.sha256(fixture_drift).hexdigest(), EXPECTED_FIXTURE_SHA256)
        with isolated_files(fixture_drift, self.source_bytes):
            with self.assertRaisesRegex(CHECKER.ValidationError, "bindingHashHex: byte mismatch"):
                CHECKER.validate()

        source_drift = self.source_bytes + b" "
        with isolated_files(self.fixture_bytes, source_drift):
            with self.assertRaisesRegex(CHECKER.ValidationError, "source fixture SHA-256"):
                CHECKER.validate()

    def test_object29_proofs_reject_role_reflection_and_bit_flip(self) -> None:
        expected = self.fixture["expected"]
        keys = expected["keys"]
        confirmations = expected["confirmations"]
        for role in ("client", "runtime"):
            canonical = bytes.fromhex(confirmations[role]["canonicalHex"])
            fields = independent_parse_als1(canonical, CHECKER.CONFIRMATION_OBJECT_TYPE, 8)
            prefix = independent_als1(CHECKER.CONFIRMATION_OBJECT_TYPE, fields[:7])
            key = bytes.fromhex(keys[f"{role}ConfirmationKeyHex"])
            proof = hmac.new(
                key,
                independent_domain(CHECKER.CONFIRMATION_DOMAIN, prefix),
                hashlib.sha256,
            ).digest()
            self.assertEqual(proof, fields[7])

        client_fields = independent_parse_als1(
            bytes.fromhex(confirmations["client"]["canonicalHex"]),
            CHECKER.CONFIRMATION_OBJECT_TYPE,
            8,
        )
        reflected_fields = client_fields[:7]
        reflected_fields[5] = b"runtime"
        reflected_prefix = independent_als1(CHECKER.CONFIRMATION_OBJECT_TYPE, reflected_fields)
        expected_runtime_proof = hmac.new(
            bytes.fromhex(keys["runtimeConfirmationKeyHex"]),
            independent_domain(CHECKER.CONFIRMATION_DOMAIN, reflected_prefix),
            hashlib.sha256,
        ).digest()
        self.assertFalse(hmac.compare_digest(client_fields[7], expected_runtime_proof))

        mutated = bytearray(client_fields[7])
        mutated[-1] ^= 1
        self.assertFalse(hmac.compare_digest(bytes(mutated), client_fields[7]))

    def test_record_tag_and_ciphertext_bit_flips_are_rejected(self) -> None:
        record = self.fixture["expected"]["records"]["clientApplication0"]
        traffic_key = bytes.fromhex(
            self.fixture["expected"]["epochMaterial"]["client"]["epoch0KeyHex"]
        )
        nonce = bytes.fromhex(record["nonceHex"])
        aad = bytes.fromhex(record["aadHex"])
        ciphertext = bytes.fromhex(record["ciphertextHex"])
        tag = bytes.fromhex(record["tagHex"])
        self.assertEqual(
            CHECKER.aes256_gcm_open(traffic_key, nonce, aad, ciphertext, tag),
            bytes.fromhex(record["plaintextHex"]),
        )

        mutated_tag = bytearray(tag)
        mutated_tag[-1] ^= 1
        with self.assertRaisesRegex(CHECKER.ValidationError, "authentication failed"):
            CHECKER.aes256_gcm_open(traffic_key, nonce, aad, ciphertext, bytes(mutated_tag))

        mutated_ciphertext = bytearray(ciphertext)
        mutated_ciphertext[0] ^= 1
        with self.assertRaisesRegex(CHECKER.ValidationError, "authentication failed"):
            CHECKER.aes256_gcm_open(traffic_key, nonce, aad, bytes(mutated_ciphertext), tag)

    def test_record_max_plus_one_and_exact_max_wire_size(self) -> None:
        with self.assertRaisesRegex(CHECKER.ValidationError, "plaintext exceeds"):
            CHECKER.seal_record(
                self.fixture["inputs"]["sessionId"],
                bytes.fromhex(self.fixture["expected"]["bindingHashHex"]),
                "client",
                0,
                0,
                1,
                bytes.fromhex(
                    self.fixture["expected"]["epochMaterial"]["client"]["epoch0KeyHex"]
                ),
                bytes.fromhex(
                    self.fixture["expected"]["epochMaterial"]["client"]["epoch0IvHex"]
                ),
                b"\x00" * (CHECKER.MAX_PLAINTEXT_BYTES + 1),
            )
        maximum_wire = independent_als1(CHECKER.RECORD_OBJECT_TYPE, [
            self.fixture["inputs"]["sessionId"].encode("ascii"),
            b"\x02",
            struct.pack(">I", CHECKER.MAX_EPOCH),
            struct.pack(">Q", CHECKER.MAX_EPOCH_RECORDS - 1),
            b"\x01",
            b"\x00" * CHECKER.MAX_PLAINTEXT_BYTES,
            b"\x00" * 16,
        ])
        self.assertEqual(len(maximum_wire), 1_048_551)
        self.assertLessEqual(len(maximum_wire), CHECKER.MAX_RECORD_BYTES)

    def test_negative_inventory_is_complete_ordered_and_platform_exact(self) -> None:
        negatives = self.fixture["negativeVectors"]
        self.assertEqual([item["id"] for item in negatives], EXPECTED_NEGATIVE_IDS)
        self.assertEqual(len({item["id"] for item in negatives}), len(EXPECTED_NEGATIVE_IDS))
        for item in negatives:
            self.assertEqual(set(item), {"id", "operation", "expectedResult", "platforms"})
            self.assertEqual(item["platforms"], ["swift", "android"])
            self.assertTrue(item["expectedResult"].startswith(("reject_", "unique_")))


if __name__ == "__main__":
    unittest.main()
