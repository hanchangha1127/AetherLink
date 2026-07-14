#!/usr/bin/env python3
"""Mutation tests for P2P/NAT Phase A session-crypto vector validation."""

from __future__ import annotations

import copy
import unittest

from script import check_p2p_nat_session_crypto_vectors as CHECKER


def replace_once(raw, old, new):
    before, separator, after = raw.partition(old)
    if not separator:
        raise AssertionError("replacement marker missing")
    return before + new + after


class SessionCryptoVectorMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = CHECKER.parse_json(
            CHECKER.FIXTURE.read_text(encoding="utf-8"),
            "canonical session crypto fixture",
        )

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.ValidationError):
            CHECKER.validate_document(candidate)

    def test_canonical_fixture_and_sources_pass(self) -> None:
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_no_network_sources()
        CHECKER.validate_hash()

    def test_duplicate_missing_and_unknown_names_fail(self) -> None:
        self.assert_rejected(lambda value: value.pop("negativeVectors"))
        self.assert_rejected(lambda value: value.update({"networkIOAllowed": True}))
        self.assert_rejected(lambda value: value.update({"version": True}))
        raw = replace_once(
            CHECKER.FIXTURE.read_text(encoding="utf-8"),
            '  "version": 1,',
            '  "version": 0,\n  "version": 1,',
        )
        with self.assertRaises(CHECKER.ValidationError):
            CHECKER.parse_json(raw, "duplicate version")

    def test_algorithm_scalar_public_key_and_shared_secret_drift_fail(self) -> None:
        self.assert_rejected(
            lambda value: value["algorithmSuite"].update({"keyAgreement": "x25519"})
        )
        self.assert_rejected(
            lambda value: value["keyAgreement"].update({"clientPrivateScalarHex": "00" * 32})
        )
        self.assert_rejected(
            lambda value: value["keyAgreement"].update({"runtimePublicKeyX963Hex": "04" + "00" * 64})
        )
        self.assert_rejected(
            lambda value: value["keyAgreement"].update({"expectedSharedSecretHex": "00" * 32})
        )

    def test_transcript_hkdf_key_and_confirmation_drift_fail(self) -> None:
        self.assert_rejected(
            lambda value: value["cases"][0]["transcriptInput"].update({"generation": 8})
        )
        self.assert_rejected(
            lambda value: value["cases"][0].update({"expectedHkdfPrkHex": "00" * 32})
        )
        self.assert_rejected(
            lambda value: value["cases"][0]["expectedKeys"].update({"clientTrafficKeyHex": "00" * 32})
        )
        self.assert_rejected(
            lambda value: value["cases"][1]["expectedConfirmations"].update({"runtime": "00" * 32})
        )

    def test_aes_nonce_aad_ciphertext_tag_and_type_confusion_fail(self) -> None:
        self.assert_rejected(
            lambda value: value["cases"][0]["traffic"]["client"].update({"sequence": False})
        )
        self.assert_rejected(
            lambda value: value["cases"][0]["traffic"]["client"].update({"nonceHex": "00" * 12})
        )
        self.assert_rejected(
            lambda value: value["cases"][0]["traffic"]["client"].update({"aadHex": "00"})
        )
        self.assert_rejected(
            lambda value: value["cases"][0]["traffic"]["client"].update({"ciphertextHex": "00"})
        )
        self.assert_rejected(
            lambda value: value["cases"][1]["traffic"]["runtime"].update({"tagHex": "00" * 16})
        )

    def test_negative_vector_completeness_and_order_fail(self) -> None:
        self.assert_rejected(lambda value: value["negativeVectors"].pop())
        self.assert_rejected(lambda value: value["negativeVectors"].reverse())
        self.assert_rejected(
            lambda value: value["negativeVectors"][0].update({"expectedResult": "accept"})
        )
        self.assert_rejected(
            lambda value: value["negativeVectors"][0].update({"platforms": ["python"]})
        )
        self.assert_rejected(
            lambda value: value["negativeVectors"][-1].update({"platforms": ["swift", "android"]})
        )

    def test_network_dynamic_import_and_provider_bypass_markers_fail(self) -> None:
        with self.assertRaises(CHECKER.ValidationError):
            CHECKER.validate_no_network_sources(swift_text="import Network", kotlin_text="")
        with self.assertRaises(CHECKER.ValidationError):
            CHECKER.validate_no_network_sources(swift_text="", kotlin_text="import java.net.Socket")
        swift = CHECKER.SWIFT_SOURCE.read_text(encoding="utf-8")
        kotlin = CHECKER.KOTLIN_SOURCE.read_text(encoding="utf-8")
        with self.assertRaises(CHECKER.ValidationError):
            CHECKER.validate_no_network_sources(
                swift_text=swift,
                kotlin_text=kotlin + '\nMac.getInstance("HmacSHA256", "NamedProvider")',
            )
        for mutation in (
            '\njava.security.Security.getProvider("Dynamic")',
            '\nClass.forName("java.security.Provider")',
            '\nServiceLoader.load(java.security.Provider::class.java)',
            '\njava.nio.channels.SocketChannel.open()',
        ):
            with self.subTest(kotlin_mutation=mutation):
                with self.assertRaises(CHECKER.ValidationError):
                    CHECKER.validate_no_network_sources(
                        swift_text=swift,
                        kotlin_text=kotlin + mutation,
                    )
        checker = CHECKER.Path(CHECKER.__file__).read_text(encoding="utf-8")
        for mutation in (
            "\nimport importlib.util\n",
            "\nfrom urllib import request\n",
            "\n__import__('hashlib')\n",
            "\neval('1 + 1')\n",
            "\nexec('pass')\n",
        ):
            with self.subTest(checker_mutation=mutation):
                with self.assertRaises(CHECKER.ValidationError):
                    CHECKER.validate_no_network_sources(
                        swift_text=swift,
                        kotlin_text=kotlin,
                        checker_text=checker + mutation,
                    )

    def test_independent_alp1_encoder_rejects_noncanonical_transcript_fields(self) -> None:
        direct = copy.deepcopy(self.canonical["cases"][0]["transcriptInput"])
        expected = bytes.fromhex(self.canonical["cases"][0]["expectedCanonicalHex"])
        self.assertEqual(expected, CHECKER.canonical_identity_transcript(direct))
        for name, value in (
            ("sessionId", "A" * 32),
            ("generation", False),
            ("protocolFloor", True),
            ("transportContext", "udp"),
        ):
            candidate = copy.deepcopy(direct)
            candidate[name] = value
            with self.subTest(name=name):
                with self.assertRaises(CHECKER.ValidationError):
                    CHECKER.canonical_identity_transcript(candidate)


if __name__ == "__main__":
    unittest.main()
