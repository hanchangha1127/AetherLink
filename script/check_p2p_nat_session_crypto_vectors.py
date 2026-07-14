#!/usr/bin/env python3
"""Validate transport-neutral P2P/NAT Phase A session-crypto vectors."""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "shared/protocol/fixtures/production-p2p-nat-v1-session-crypto-vectors.json"
SWIFT_SOURCE = ROOT / "apps/macos/P2PNATContracts/Sources/P2PNATSessionCrypto.swift"
KOTLIN_SOURCE = ROOT / "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat/P2pNatSessionCrypto.kt"
FIXTURE_SHA256 = "4693f71330b5f40f9b99b4445c24fba8fa0939c4ae76f8b9bf3c9644b08f29c9"
P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
P256_A = P256_P - 3
P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
P256_G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)
ALGORITHMS = {
    "transcript": "existing_canonical_ALP1_transport_neutral_identity_session_transcript",
    "keyAgreement": "ephemeral_p256_ecdh",
    "keyDerivation": "hkdf_sha256_rfc5869",
    "trafficProtection": "aes_256_gcm",
    "nonceConstruction": "sender_role_ascii_4_plus_uint64_be_sequence",
    "keyConfirmation": "bidirectional_transcript_bound_hmac_sha256",
    "androidProviderPolicy": "provider_neutral_jca_no_named_provider_no_android_keystore_dependency",
}
EXPECTED_AES = {
    ("direct", "client"): (
        "6469726563742d636c69656e742d70686173652d612d766563746f72",
        "2ca1a5fdaf6d55a7f30cf4d7bf515f4c2dc5ced0db490a29b2e474a1",
        "343762c496f341f2a1734c82d0ee9b55",
    ),
    ("direct", "runtime"): (
        "6469726563742d72756e74696d652d70686173652d612d766563746f72",
        "587049f627e77cb32215cc89e0fc5021096f15596111f8787108e06d85",
        "f8090bc7d2a0fab83143abdd02c9d70a",
    ),
    ("relay", "client"): (
        "72656c61792d636c69656e742d70686173652d612d766563746f72",
        "45afa7f97d1062dd4e365eb3d0263f787b3ac6320b3a3aa636f4af",
        "60cc41afaa7271686614891d97eada4f",
    ),
    ("relay", "runtime"): (
        "72656c61792d72756e74696d652d70686173652d612d766563746f72",
        "1eb7fe1340498158ef5a1e6ffffff06f9ffa4c3deced5a4fb58bf8fe",
        "0ff05cbd0dd2c201551f8d3dc60fbc13",
    ),
}
EXPECTED_NEGATIVES = [
    {"id": "off_curve_public_key", "operation": "derive_keys", "mutation": "runtime_public_key_all_zero_coordinates", "expectedResult": "reject_before_key_agreement", "platforms": ["swift", "android"]},
    {"id": "truncated_public_key", "operation": "derive_keys", "mutation": "runtime_public_key_remove_last_byte", "expectedResult": "reject_before_key_agreement", "platforms": ["swift", "android"]},
    {"id": "zero_private_scalar", "operation": "construct_test_key", "mutation": "all_zero_scalar", "expectedResult": "reject_invalid_scalar", "platforms": ["swift", "android"]},
    {"id": "out_of_range_private_scalar", "operation": "construct_test_key", "mutation": "p256_group_order_scalar", "expectedResult": "reject_invalid_scalar", "platforms": ["swift", "android"]},
    {"id": "transcript_substitution", "operation": "open", "mutation": "change_pair_binding_digest", "expectedResult": "reject_authentication", "platforms": ["swift", "android"]},
    {"id": "role_reflection", "operation": "accept_confirmation", "mutation": "client_proof_as_runtime_proof", "expectedResult": "reject_confirmation", "platforms": ["swift", "android"]},
    {"id": "generation_replay", "operation": "open", "mutation": "increment_transcript_generation", "expectedResult": "reject_authentication", "platforms": ["swift", "android"]},
    {"id": "nonce_reuse", "operation": "open", "mutation": "replay_sequence_zero_payload_after_receive_advance", "expectedResult": "reject_authentication_without_counter_advance", "platforms": ["swift", "android"]},
    {"id": "modified_gcm_tag", "operation": "open", "mutation": "flip_final_tag_bit", "expectedResult": "reject_authentication_without_counter_advance", "platforms": ["swift", "android"]},
    {"id": "provider_failure", "operation": "derive_keys", "mutation": "unavailable_hmac_algorithm", "expectedResult": "reject_without_provider_fallback", "platforms": ["android"]},
]


class ValidationError(ValueError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON name {key!r}")
        result[key] = value
    return result


def parse_json(raw: str, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=reject_duplicate_names)
    except json.JSONDecodeError as error:
        fail(f"{label}: invalid JSON: {error}")


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        fail(f"{label}: exact key set drifted; actual={actual}")
    return value


def type_exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            type_exact_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            type_exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def hex_bytes(value: Any, size: int | None, label: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-f]{2})+", value):
        fail(f"{label}: expected canonical lowercase hex")
    result = bytes.fromhex(value)
    if size is not None and len(result) != size:
        fail(f"{label}: expected {size} bytes")
    return result


def uint(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= 1 << 63:
        fail(f"{label}: expected non-negative signed-64-compatible integer")
    return value


def point(encoded: bytes, label: str) -> tuple[int, int]:
    if len(encoded) != 65 or encoded[0] != 4:
        fail(f"{label}: expected canonical uncompressed P-256 point")
    x = int.from_bytes(encoded[1:33], "big")
    y = int.from_bytes(encoded[33:], "big")
    if x >= P256_P or y >= P256_P or (y * y - (x * x * x + P256_A * x + P256_B)) % P256_P:
        fail(f"{label}: point is not on P-256")
    return x, y


def add(left: tuple[int, int] | None, right: tuple[int, int] | None) -> tuple[int, int] | None:
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P256_P == 0:
        return None
    if left == right:
        slope = (3 * x1 * x1 + P256_A) * pow(2 * y1, -1, P256_P) % P256_P
    else:
        slope = (y2 - y1) * pow((x2 - x1) % P256_P, -1, P256_P) % P256_P
    x3 = (slope * slope - x1 - x2) % P256_P
    return x3, (slope * (x1 - x3) - y1) % P256_P


def multiply(base: tuple[int, int], scalar: int) -> tuple[int, int]:
    if scalar <= 0 or scalar >= P256_N:
        fail("private scalar is outside P-256 group order")
    result: tuple[int, int] | None = None
    addend: tuple[int, int] | None = base
    while scalar:
        if scalar & 1:
            result = add(result, addend)
        addend = add(addend, addend)
        scalar >>= 1
    if result is None:
        fail("P-256 scalar multiplication reached infinity")
    return result


def encode_point(value: tuple[int, int]) -> bytes:
    return b"\x04" + value[0].to_bytes(32, "big") + value[1].to_bytes(32, "big")


def hkdf_expand(prk: bytes, info: bytes, size: int) -> bytes:
    output = b""
    previous = b""
    counter = 1
    while len(output) < size:
        previous = hmac.new(prk, previous + info + bytes((counter,)), hashlib.sha256).digest()
        output += previous
        counter += 1
    return output[:size]


def canonical_identity_transcript(value: Any) -> bytes:
    item = exact_keys(
        value,
        {
            "sessionId", "pairBindingDigest", "clientFingerprint", "runtimeFingerprint",
            "clientEphemeralKeyHex", "runtimeEphemeralKeyHex", "generation", "pathReceiptDigest",
            "transportContext", "fallbackReason", "protocolFloor",
        },
        "identity transcript",
    )

    def lower_hex_text(name: str, size: int) -> bytes:
        encoded = hex_bytes(item[name], size, f"identity transcript.{name}")
        return encoded.hex().encode("ascii")

    client_key = hex_bytes(item["clientEphemeralKeyHex"], 65, "identity transcript.client key")
    runtime_key = hex_bytes(item["runtimeEphemeralKeyHex"], 65, "identity transcript.runtime key")
    point(client_key, "identity transcript.client key")
    point(runtime_key, "identity transcript.runtime key")
    generation = item["generation"]
    if isinstance(generation, bool) or not isinstance(generation, int) or not 0 < generation < 1 << 64:
        fail("identity transcript.generation: expected positive uint64")
    floor = item["protocolFloor"]
    if isinstance(floor, bool) or not isinstance(floor, int) or floor != 1:
        fail("identity transcript.protocolFloor: expected integer 1")
    transport = item["transportContext"]
    fallback = item["fallbackReason"]
    if transport not in {"direct", "relay"} or fallback not in {"none", "direct_failed", "consent_lost"}:
        fail("identity transcript transport or fallback is invalid")

    fields = [
        b"aetherlink-p2p-v1",
        lower_hex_text("sessionId", 16),
        lower_hex_text("pairBindingDigest", 32),
        lower_hex_text("clientFingerprint", 32),
        lower_hex_text("runtimeFingerprint", 32),
        client_key,
        runtime_key,
        struct.pack(">Q", generation),
        lower_hex_text("pathReceiptDigest", 32),
        transport.encode("ascii"),
        fallback.encode("ascii"),
        struct.pack(">I", floor),
    ]
    encoded = bytearray(b"ALP1\x04\x01")
    for tag, field in enumerate(fields, 1):
        encoded.extend(bytes((tag,)) + struct.pack(">I", len(field)) + field)
    return bytes(encoded)


def validate_document(document: Any) -> None:
    root = exact_keys(
        document,
        {"schema", "version", "algorithmSuite", "keyAgreement", "cases", "negativeVectors"},
        "fixture",
    )
    if (
        root["schema"] != "aetherlink-production-p2p-nat-v1-session-crypto-vectors"
        or type(root["version"]) is not int
        or root["version"] != 1
    ):
        fail("fixture identity drifted")
    if not type_exact_equal(root["algorithmSuite"], ALGORITHMS):
        fail("algorithm suite drifted")

    agreement = exact_keys(
        root["keyAgreement"],
        {
            "clientPrivateScalarHex", "runtimePrivateScalarHex", "clientPublicKeyX963Hex",
            "runtimePublicKeyX963Hex", "expectedSharedSecretHex", "leadingZeroNormalizationCase",
        },
        "keyAgreement",
    )
    client_scalar = int.from_bytes(hex_bytes(agreement["clientPrivateScalarHex"], 32, "client scalar"), "big")
    runtime_scalar = int.from_bytes(hex_bytes(agreement["runtimePrivateScalarHex"], 32, "runtime scalar"), "big")
    client_public = hex_bytes(agreement["clientPublicKeyX963Hex"], 65, "client public key")
    runtime_public = hex_bytes(agreement["runtimePublicKeyX963Hex"], 65, "runtime public key")
    if client_public != encode_point(multiply(P256_G, client_scalar)):
        fail("client public key does not match private scalar")
    if runtime_public != encode_point(multiply(P256_G, runtime_scalar)):
        fail("runtime public key does not match private scalar")
    shared = multiply(point(runtime_public, "runtime public key"), client_scalar)[0].to_bytes(32, "big")
    if shared != hex_bytes(agreement["expectedSharedSecretHex"], 32, "shared secret"):
        fail("shared secret drifted")

    padding = exact_keys(
        agreement["leadingZeroNormalizationCase"],
        {
            "clientPrivateScalarHex", "runtimePrivateScalarHex", "clientPublicKeyX963Hex",
            "runtimePublicKeyX963Hex", "expectedSharedSecretHex",
        },
        "leading-zero case",
    )
    padding_client_scalar = int.from_bytes(hex_bytes(padding["clientPrivateScalarHex"], 32, "padding client scalar"), "big")
    padding_runtime_scalar = int.from_bytes(hex_bytes(padding["runtimePrivateScalarHex"], 32, "padding runtime scalar"), "big")
    padding_client_public = encode_point(multiply(P256_G, padding_client_scalar))
    padding_runtime_public = encode_point(multiply(P256_G, padding_runtime_scalar))
    if padding_client_public != hex_bytes(padding["clientPublicKeyX963Hex"], 65, "padding client public"):
        fail("padding client public key drifted")
    if padding_runtime_public != hex_bytes(padding["runtimePublicKeyX963Hex"], 65, "padding runtime public"):
        fail("padding runtime public key drifted")
    padding_shared = multiply(point(padding_runtime_public, "padding runtime public"), padding_client_scalar)[0].to_bytes(32, "big")
    if padding_shared[0] != 0 or padding_shared != hex_bytes(padding["expectedSharedSecretHex"], 32, "padding shared secret"):
        fail("leading-zero shared secret normalization drifted")

    cases = root["cases"]
    if not isinstance(cases, list) or [case.get("id") for case in cases if isinstance(case, dict)] != ["direct", "relay"]:
        fail("session cases must be exactly direct then relay")
    for case in cases:
        validate_case(case, shared)

    negatives = root["negativeVectors"]
    if not type_exact_equal(negatives, EXPECTED_NEGATIVES):
        fail("negative-vector contract or order drifted")
    for index, item in enumerate(negatives):
        exact_keys(item, {"id", "operation", "mutation", "expectedResult", "platforms"}, f"negativeVectors[{index}]")
        if not all(isinstance(item[field], str) and item[field] for field in ("id", "operation", "mutation", "expectedResult")):
            fail(f"negativeVectors[{index}] fields must be non-empty strings")
        if item["platforms"] not in (["swift", "android"], ["android"]):
            fail(f"negativeVectors[{index}] has invalid platform scope")


def validate_case(case: Any, shared: bytes) -> None:
    item = exact_keys(
        case,
        {
            "id", "transcriptInput", "expectedCanonicalHex", "expectedTranscriptSha256Hex",
            "expectedHkdfSaltHex", "expectedHkdfInfoHex", "expectedHkdfPrkHex",
            "expectedHkdfOkmHex", "expectedKeys", "expectedConfirmations", "traffic",
        },
        "session case",
    )
    case_id = item["id"]
    if case_id not in {"direct", "relay"}:
        fail("unknown session case")
    transcript_input = exact_keys(
        item["transcriptInput"],
        {
            "sessionId", "pairBindingDigest", "clientFingerprint", "runtimeFingerprint",
            "clientEphemeralKeyHex", "runtimeEphemeralKeyHex", "generation", "pathReceiptDigest",
            "transportContext", "fallbackReason", "protocolFloor",
        },
        f"{case_id}.transcriptInput",
    )
    expected_transport = "direct" if case_id == "direct" else "relay"
    expected_fallback = "none" if case_id == "direct" else "consent_lost"
    if transcript_input["transportContext"] != expected_transport or transcript_input["fallbackReason"] != expected_fallback:
        fail(f"{case_id}: transport context drifted")
    encoded = canonical_identity_transcript(transcript_input)
    if encoded != hex_bytes(item["expectedCanonicalHex"], None, f"{case_id}.canonical"):
        fail(f"{case_id}: canonical transcript drifted")
    digest = hashlib.sha256(encoded).digest()
    salt = hex_bytes(item["expectedHkdfSaltHex"], 32, f"{case_id}.salt")
    if digest != salt or digest != hex_bytes(item["expectedTranscriptSha256Hex"], 32, f"{case_id}.digest"):
        fail(f"{case_id}: transcript digest/salt drifted")
    info = b"aetherlink-p2p-v1/session-keys/v1\x00" + digest
    prk = hmac.new(digest, shared, hashlib.sha256).digest()
    okm = hkdf_expand(prk, info, 96)
    if info != hex_bytes(item["expectedHkdfInfoHex"], None, f"{case_id}.info"):
        fail(f"{case_id}: HKDF info drifted")
    if prk != hex_bytes(item["expectedHkdfPrkHex"], 32, f"{case_id}.prk"):
        fail(f"{case_id}: HKDF PRK drifted")
    if okm != hex_bytes(item["expectedHkdfOkmHex"], 96, f"{case_id}.okm"):
        fail(f"{case_id}: HKDF OKM drifted")
    keys = exact_keys(
        item["expectedKeys"],
        {"clientTrafficKeyHex", "runtimeTrafficKeyHex", "confirmationKeyHex"},
        f"{case_id}.keys",
    )
    expected_keys = [
        hex_bytes(keys["clientTrafficKeyHex"], 32, f"{case_id}.client key"),
        hex_bytes(keys["runtimeTrafficKeyHex"], 32, f"{case_id}.runtime key"),
        hex_bytes(keys["confirmationKeyHex"], 32, f"{case_id}.confirmation key"),
    ]
    if b"".join(expected_keys) != okm:
        fail(f"{case_id}: key split drifted")
    confirmations = exact_keys(item["expectedConfirmations"], {"client", "runtime"}, f"{case_id}.confirmations")
    for role in ("client", "runtime"):
        confirmation_input = encoded + f"aetherlink-p2p-v1:key-confirmation:{role}".encode()
        expected = hmac.new(expected_keys[2], confirmation_input, hashlib.sha256).digest()
        if expected != hex_bytes(confirmations[role], 32, f"{case_id}.{role} confirmation"):
            fail(f"{case_id}: {role} confirmation drifted")

    traffic = exact_keys(item["traffic"], {"client", "runtime"}, f"{case_id}.traffic")
    for role in ("client", "runtime"):
        vector = exact_keys(
            traffic[role],
            {"sequence", "nonceHex", "aadHex", "plaintextHex", "ciphertextHex", "tagHex"},
            f"{case_id}.{role}.traffic",
        )
        sequence = uint(vector["sequence"], f"{case_id}.{role}.sequence")
        if sequence != 0:
            fail(f"{case_id}.{role}: first vector sequence must be zero")
        direction = b"CLNT" if role == "client" else b"RUNT"
        nonce = direction + sequence.to_bytes(8, "big")
        aad = encoded + f"aetherlink-p2p-v1:traffic:{role}:".encode() + sequence.to_bytes(8, "big")
        if nonce != hex_bytes(vector["nonceHex"], 12, f"{case_id}.{role}.nonce"):
            fail(f"{case_id}.{role}: nonce drifted")
        if aad != hex_bytes(vector["aadHex"], None, f"{case_id}.{role}.aad"):
            fail(f"{case_id}.{role}: AAD drifted")
        plaintext, ciphertext, tag = EXPECTED_AES[(case_id, role)]
        if (vector["plaintextHex"], vector["ciphertextHex"], vector["tagHex"]) != (plaintext, ciphertext, tag):
            fail(f"{case_id}.{role}: AES-GCM fixed vector drifted")
        if len(hex_bytes(ciphertext, None, f"{case_id}.{role}.ciphertext")) != len(hex_bytes(plaintext, None, f"{case_id}.{role}.plaintext")):
            fail(f"{case_id}.{role}: AES-GCM ciphertext length drifted")
        hex_bytes(tag, 16, f"{case_id}.{role}.tag")


def validate_no_network_sources(
    swift_text: str | None = None,
    kotlin_text: str | None = None,
    checker_text: str | None = None,
) -> None:
    swift = SWIFT_SOURCE.read_text(encoding="utf-8") if swift_text is None else swift_text
    kotlin = KOTLIN_SOURCE.read_text(encoding="utf-8") if kotlin_text is None else kotlin_text
    checker = Path(__file__).read_text(encoding="utf-8") if checker_text is None else checker_text
    forbidden_swift = (
        "import Network", "import Darwin", "import Glibc", "URLSession", "CFStream",
        "NWConnection", "socket(", "connect(", "bind(",
    )
    forbidden_kotlin = (
        "java.net.", "java.nio.channels.SocketChannel", "Socket", "Datagram", "URL(",
        "URLConnection", "HttpClient", "ProxySelector", "InetAddress", "android.net.",
    )
    for marker in forbidden_swift:
        if marker in swift:
            fail(f"Swift session crypto contains network marker {marker!r}")
    for marker in forbidden_kotlin:
        if marker in kotlin:
            fail(f"Kotlin session crypto contains network marker {marker!r}")
    for required in ("P256.KeyAgreement.PrivateKey", "HKDF<SHA256>", "AES.GCM", "HMAC<SHA256>"):
        if required not in swift:
            fail(f"Swift session crypto is missing {required!r}")
    for required in ("ECGenParameterSpec(P256_CURVE_NAME)", 'KeyAgreement.getInstance(algorithms.keyAgreement)', 'Cipher.getInstance(algorithms.cipher)', 'Mac.getInstance(algorithm)'):
        if required not in kotlin:
            fail(f"Kotlin session crypto is missing {required!r}")
    if re.search(
        r"(?:KeyAgreement|Cipher|Mac|KeyPairGenerator|KeyFactory|AlgorithmParameters)"
        r"\.getInstance\(\s*[^,\n()]+\s*,",
        kotlin,
    ):
        fail("Kotlin session crypto must not select a named JCA provider")
    for marker in (
        "java.security.Security", "getProvider(", "addProvider(", "insertProviderAt(",
        "Class.forName(", "ServiceLoader", "kotlin.reflect", "java.lang.reflect",
    ):
        if marker in kotlin:
            fail(f"Kotlin session crypto contains dynamic provider marker {marker!r}")

    try:
        tree = ast.parse(checker)
    except SyntaxError as error:
        fail(f"session crypto checker source is invalid Python: {error}")
    forbidden_modules = {"importlib", "socket", "urllib", "http", "requests", "ftplib"}
    forbidden_calls = {"__import__", "eval", "exec"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name.split(".", 1)[0] for alias in node.names]
            if any(module in forbidden_modules for module in modules):
                fail("session crypto checker contains dynamic import or network module")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module in forbidden_modules:
                fail("session crypto checker contains dynamic import or network module")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in forbidden_calls:
                fail(f"session crypto checker contains forbidden dynamic call {node.func.id!r}")


def validate_hash() -> None:
    actual = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    if actual != FIXTURE_SHA256:
        fail(f"session crypto fixture SHA-256 drifted; expected {FIXTURE_SHA256}, got {actual}")


def main() -> int:
    try:
        document = parse_json(FIXTURE.read_text(encoding="utf-8"), "session crypto fixture")
        validate_document(document)
        validate_no_network_sources()
        validate_hash()
    except (OSError, ValidationError, ValueError) as error:
        print(f"P2P/NAT session crypto vector check failed: {error}", file=sys.stderr)
        return 1
    print("P2P/NAT Phase A session crypto vectors passed (direct+relay ALP1; sockets=0; network I/O=0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
