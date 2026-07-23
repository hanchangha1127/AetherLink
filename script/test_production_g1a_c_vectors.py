#!/usr/bin/env python3
"""Unit tests for the independent production G1a-C vector reference."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check_production_g1a_c_vectors.py")
SPEC = importlib.util.spec_from_file_location("g1ac_vectors", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
g1ac = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g1ac)


class ProductionG1aCVectorTests(unittest.TestCase):
    def test_checked_in_fixture_is_exact_and_valid(self) -> None:
        g1ac.validate_fixture_file()

    def test_p256_spki_and_key_id_are_independently_derived(self) -> None:
        x963, spki, key_id = g1ac.public_material(1)
        self.assertEqual(x963, b"\x04" + g1ac.P256_G[0].to_bytes(32, "big") + g1ac.P256_G[1].to_bytes(32, "big"))
        self.assertEqual(spki, g1ac.P256_SPKI_PREFIX + x963)
        self.assertEqual(key_id, g1ac.sha256_hex(spki))

    def test_rfc6979_signature_is_deterministic_low_s_and_verifiable(self) -> None:
        message = b"AetherLink independent deterministic signature test"
        first = g1ac.ecdsa_sign_rfc6979(52, message)
        second = g1ac.ecdsa_sign_rfc6979(52, message)
        self.assertEqual(first, second)
        _, s = g1ac.der_decode_signature(first)
        self.assertLessEqual(s, g1ac.P256_N // 2)
        public, _, _ = g1ac.public_material(52)
        g1ac.ecdsa_verify(public, message, first)

    def test_strict_der_rejects_high_s_nonminimal_and_trailing_bytes(self) -> None:
        signature = g1ac.ecdsa_sign_rfc6979(3, b"strict DER")
        r, s = g1ac.der_decode_signature(signature)
        high_s = g1ac.der_encode_signature(r, g1ac.P256_N - s)
        with self.assertRaises(g1ac.VectorError):
            g1ac.der_decode_signature(high_s)
        body = b"\x02\x02\x00\x01" + g1ac._der_integer(s)
        nonminimal = b"\x30" + bytes((len(body),)) + body
        with self.assertRaises(g1ac.VectorError):
            g1ac.der_decode_signature(nonminimal)
        with self.assertRaises(g1ac.VectorError):
            g1ac.der_decode_signature(signature + b"\x00")

    def test_als1_rejects_reordered_tags_and_trailing_bytes(self) -> None:
        encoded = g1ac.als1_encode(18, [b"one", b"two"])
        reordered = bytearray(encoded)
        reordered[6] = 2
        with self.assertRaises(g1ac.VectorError):
            g1ac.als1_decode(bytes(reordered), 18, 2)
        with self.assertRaises(g1ac.VectorError):
            g1ac.als1_decode(encoded + b"\x00", 18, 2)

    def test_rewrite_is_explicit_and_default_detects_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "vectors.json"
            self.assertEqual(g1ac.main(["--fixture", str(fixture)]), 1)
            self.assertEqual(g1ac.main(["--fixture", str(fixture), "--rewrite"]), 0)
            g1ac.validate_fixture_file(fixture)
            fixture.write_bytes(fixture.read_bytes() + b" ")
            with self.assertRaises(g1ac.VectorError):
                g1ac.validate_fixture_file(fixture)

    def test_semantic_chain_keeps_context_and_authorization_digests_distinct(self) -> None:
        fixture = g1ac.build_fixture()
        derived = fixture["derived"]
        transcript = fixture["objects"]["secureSessionTranscript"]["input"]
        plan = fixture["objects"]["routePlan"]["input"]
        self.assertEqual(transcript["routeAuthDigest"], derived["turnRouteAuthorizationDigest"])
        self.assertEqual(plan["securityContextDigest"], derived["preauthorizationSessionContextDigest"])
        self.assertNotEqual(transcript["routeAuthDigest"], plan["securityContextDigest"])
        self.assertEqual(fixture["expectedOutcomes"]["durableAdmission"]["exactRetryExpected"], "replay")


if __name__ == "__main__":
    unittest.main()
