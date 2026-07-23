#!/usr/bin/env python3
"""Validate the socket-free ALS1 object-7/object-26 secure-session crypto vectors."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "shared/protocol/fixtures/production-secure-session-crypto-v1-vectors.json"
SOURCE_FIXTURE = ROOT / "shared/protocol/fixtures/production-g1a-c-candidate-v1-vectors.json"

SUITE = "aetherlink-secure-session-v1"
PROFILE = "p256_hkdf_sha256_aes256gcm_v1"
CONFIRMATION_OBJECT_TYPE = 29
RECORD_OBJECT_TYPE = 30
MAX_CONFIRMATION_BYTES = 384
MAX_RECORD_BYTES = 1_048_576
MAX_PLAINTEXT_BYTES = 1_048_448
MAX_EPOCH = 15
MAX_EPOCH_RECORDS = 1 << 20
MAX_EPOCH_PLAINTEXT_BYTES = 1 << 30
MAX_SESSION_RECORDS = 1 << 24
MAX_SESSION_PLAINTEXT_BYTES = 1 << 34

BINDING_DOMAIN = "AetherLink production secure-session object7+object26 binding v1"
ROOT_DOMAIN = "AetherLink production secure-session HKDF root v1"
TRAFFIC_KEY_DOMAIN = "AetherLink production secure-session traffic key v1"
TRAFFIC_IV_DOMAIN = "AetherLink production secure-session traffic iv v1"
TRAFFIC_UPDATE_DOMAIN = "AetherLink production secure-session traffic update v1"
CONFIRMATION_DOMAIN = "AetherLink production secure-session key confirmation v1"
RECORD_AAD_DOMAIN = "AetherLink production secure-session record AAD v1"

P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
P256_A = P256_P - 3
P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
P256_G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)

SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)
RCON = (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40)


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


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(), object_pairs_hook=reject_duplicate_names)
    except (OSError, json.JSONDecodeError) as error:
        fail(f"{path.relative_to(ROOT)}: {error}")


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        fail(f"{label}: exact key set drifted; actual={actual}")
    return value


def hex_bytes(value: Any, size: int | None, label: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-f]{2})*", value):
        fail(f"{label}: expected canonical lowercase even-length hex")
    result = bytes.fromhex(value)
    if size is not None and len(result) != size:
        fail(f"{label}: expected {size} bytes, got {len(result)}")
    return result


def uint(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        fail(f"{label}: expected non-negative integer")
    return value


def domain(label: str, claims: bytes) -> bytes:
    encoded = label.encode("ascii")
    return encoded + b"\x00" + struct.pack(">I", len(claims)) + claims


def als1(object_type: int, fields: list[bytes]) -> bytes:
    if not 0 < object_type < 256 or not 0 < len(fields) < 256:
        fail("ALS1 object type or field count is invalid")
    output = bytearray(b"ALS1" + bytes((object_type, 1)))
    for tag, field in enumerate(fields, 1):
        output.extend(bytes((tag,)) + struct.pack(">I", len(field)) + field)
    return bytes(output)


def parse_als1(data: bytes, object_type: int, field_count: int, maximum: int) -> list[bytes]:
    if len(data) > maximum or len(data) < 6 or data[:4] != b"ALS1":
        fail("malformed or oversized ALS1 object")
    if data[4] != object_type or data[5] != 1:
        fail("wrong ALS1 type or version")
    cursor = 6
    fields: list[bytes] = []
    for expected_tag in range(1, field_count + 1):
        if cursor + 5 > len(data) or data[cursor] != expected_tag:
            fail("missing, duplicate, unknown, or reordered ALS1 field")
        length = struct.unpack(">I", data[cursor + 1:cursor + 5])[0]
        cursor += 5
        if length > maximum or cursor + length > len(data):
            fail("invalid ALS1 field length")
        fields.append(data[cursor:cursor + length])
        cursor += length
    if cursor != len(data) or als1(object_type, fields) != data:
        fail("trailing or non-canonical ALS1 bytes")
    return fields


def point(encoded: bytes, label: str) -> tuple[int, int]:
    if len(encoded) != 65 or encoded[0] != 4:
        fail(f"{label}: expected uncompressed P-256 point")
    x = int.from_bytes(encoded[1:33], "big")
    y = int.from_bytes(encoded[33:], "big")
    if x >= P256_P or y >= P256_P:
        fail(f"{label}: coordinate outside P-256 field")
    if (y * y - (x * x * x + P256_A * x + P256_B)) % P256_P:
        fail(f"{label}: point is off P-256")
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
    if not 0 < scalar < P256_N:
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
    if not 0 < size <= 255 * 32:
        fail("invalid HKDF output size")
    result = bytearray()
    previous = b""
    counter = 1
    while len(result) < size:
        previous = hmac.new(prk, previous + info + bytes((counter,)), hashlib.sha256).digest()
        result.extend(previous)
        counter += 1
    return bytes(result[:size])


def xtime(value: int) -> int:
    return ((value << 1) ^ (0x11B if value & 0x80 else 0)) & 0xFF


def aes256_round_keys(key: bytes) -> list[bytes]:
    if len(key) != 32:
        fail("AES-256 key must be 32 bytes")
    words = [list(key[index:index + 4]) for index in range(0, 32, 4)]
    for index in range(8, 60):
        temp = words[index - 1].copy()
        if index % 8 == 0:
            temp = [SBOX[temp[1]], SBOX[temp[2]], SBOX[temp[3]], SBOX[temp[0]]]
            temp[0] ^= RCON[index // 8]
        elif index % 8 == 4:
            temp = [SBOX[value] for value in temp]
        words.append([left ^ right for left, right in zip(words[index - 8], temp)])
    return [bytes(sum(words[index:index + 4], [])) for index in range(0, 60, 4)]


def aes256_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != 16:
        fail("AES block must be 16 bytes")
    round_keys = aes256_round_keys(key)
    state = [value ^ round_keys[0][index] for index, value in enumerate(block)]
    for round_index in range(1, 15):
        state = [SBOX[value] for value in state]
        state = [state[((column + row) % 4) * 4 + row] for column in range(4) for row in range(4)]
        if round_index != 14:
            mixed: list[int] = []
            for column in range(4):
                a0, a1, a2, a3 = state[column * 4:column * 4 + 4]
                total = a0 ^ a1 ^ a2 ^ a3
                mixed.extend((
                    a0 ^ total ^ xtime(a0 ^ a1),
                    a1 ^ total ^ xtime(a1 ^ a2),
                    a2 ^ total ^ xtime(a2 ^ a3),
                    a3 ^ total ^ xtime(a3 ^ a0),
                ))
            state = mixed
        state = [value ^ round_keys[round_index][index] for index, value in enumerate(state)]
    return bytes(state)


def gcm_multiply(left: int, right: int) -> int:
    result = 0
    value = right
    for bit in range(128):
        if left & (1 << (127 - bit)):
            result ^= value
        value = (value >> 1) ^ (0xE1000000000000000000000000000000 if value & 1 else 0)
    return result


def ghash(hash_subkey: bytes, aad: bytes, ciphertext: bytes) -> bytes:
    value = 0
    h_value = int.from_bytes(hash_subkey, "big")
    material = (
        aad + b"\x00" * ((-len(aad)) % 16)
        + ciphertext + b"\x00" * ((-len(ciphertext)) % 16)
        + struct.pack(">QQ", len(aad) * 8, len(ciphertext) * 8)
    )
    for offset in range(0, len(material), 16):
        value = gcm_multiply(value ^ int.from_bytes(material[offset:offset + 16], "big"), h_value)
    return value.to_bytes(16, "big")


def aes256_gcm_seal(key: bytes, nonce: bytes, aad: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    if len(nonce) != 12:
        fail("AES-GCM nonce must be 12 bytes")
    j0 = nonce + b"\x00\x00\x00\x01"
    ciphertext = bytearray()
    counter = 2
    for offset in range(0, len(plaintext), 16):
        stream = aes256_encrypt_block(key, nonce + struct.pack(">I", counter))
        block = plaintext[offset:offset + 16]
        ciphertext.extend(bytes(left ^ right for left, right in zip(block, stream)))
        counter = (counter + 1) & 0xFFFFFFFF
        if counter == 0 and offset + 16 < len(plaintext):
            fail("AES-GCM counter exhausted")
    ciphertext_bytes = bytes(ciphertext)
    authentication = ghash(aes256_encrypt_block(key, b"\x00" * 16), aad, ciphertext_bytes)
    tag = bytes(
        left ^ right for left, right in zip(aes256_encrypt_block(key, j0), authentication)
    )
    return ciphertext_bytes, tag


def aes256_gcm_open(key: bytes, nonce: bytes, aad: bytes, ciphertext: bytes, tag: bytes) -> bytes:
    if len(tag) != 16:
        fail("AES-GCM tag must be 16 bytes")
    expected_ciphertext, expected_tag = aes256_gcm_seal(key, nonce, aad, b"\x00" * len(ciphertext))
    # CTR is symmetric; recover plaintext with the same keystream used above.
    plaintext = bytes(left ^ right for left, right in zip(ciphertext, expected_ciphertext))
    _, actual_tag = aes256_gcm_seal(key, nonce, aad, plaintext)
    if not hmac.compare_digest(actual_tag, tag):
        fail("AES-GCM authentication failed")
    return plaintext


def role_byte(role: str) -> bytes:
    if role == "client":
        return b"\x01"
    if role == "runtime":
        return b"\x02"
    fail("invalid secure-session role")


def epoch_material(secret: bytes, binding_hash: bytes, role: str, epoch: int) -> tuple[bytes, bytes]:
    context = binding_hash + role_byte(role) + struct.pack(">I", epoch)
    return (
        hkdf_expand(secret, domain(TRAFFIC_KEY_DOMAIN, context), 32),
        hkdf_expand(secret, domain(TRAFFIC_IV_DOMAIN, context), 12),
    )


def next_epoch_secret(secret: bytes, binding_hash: bytes, role: str, next_epoch: int) -> bytes:
    context = binding_hash + role_byte(role) + struct.pack(">I", next_epoch)
    return hkdf_expand(secret, domain(TRAFFIC_UPDATE_DOMAIN, context), 32)


def confirmation_prefix(
    session_id: str,
    transcript_digest: str,
    grant_digest: str,
    role: str,
) -> bytes:
    return als1(CONFIRMATION_OBJECT_TYPE, [
        SUITE.encode("ascii"),
        PROFILE.encode("ascii"),
        session_id.encode("ascii"),
        transcript_digest.encode("ascii"),
        grant_digest.encode("ascii"),
        role.encode("ascii"),
        struct.pack(">I", 0),
    ])


def confirmation_bytes(prefix: bytes, key: bytes) -> tuple[bytes, bytes]:
    proof = hmac.new(key, domain(CONFIRMATION_DOMAIN, prefix), hashlib.sha256).digest()
    fields = parse_als1(prefix, CONFIRMATION_OBJECT_TYPE, 7, MAX_CONFIRMATION_BYTES)
    encoded = als1(CONFIRMATION_OBJECT_TYPE, fields + [proof])
    if len(encoded) > MAX_CONFIRMATION_BYTES:
        fail("confirmation object exceeds contract limit")
    return proof, encoded


def record_prefix(session_id: str, role: str, epoch: int, sequence: int, content_type: int) -> bytes:
    return als1(RECORD_OBJECT_TYPE, [
        session_id.encode("ascii"),
        role_byte(role),
        struct.pack(">I", epoch),
        struct.pack(">Q", sequence),
        bytes((content_type,)),
    ])


def record_aad(binding_hash: bytes, prefix: bytes, ciphertext_size: int) -> bytes:
    claims = binding_hash + struct.pack(">I", len(prefix)) + prefix + struct.pack(">I", ciphertext_size)
    return domain(RECORD_AAD_DOMAIN, claims)


def nonce(static_iv: bytes, sequence: int) -> bytes:
    sequence_block = b"\x00" * 4 + struct.pack(">Q", sequence)
    return bytes(left ^ right for left, right in zip(static_iv, sequence_block))


def seal_record(
    session_id: str,
    binding_hash: bytes,
    role: str,
    epoch: int,
    sequence: int,
    content_type: int,
    key: bytes,
    static_iv: bytes,
    plaintext: bytes,
) -> dict[str, bytes]:
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        fail("plaintext exceeds secure-session record limit")
    prefix = record_prefix(session_id, role, epoch, sequence, content_type)
    aad = record_aad(binding_hash, prefix, len(plaintext))
    nonce_bytes = nonce(static_iv, sequence)
    ciphertext, tag = aes256_gcm_seal(key, nonce_bytes, aad, plaintext)
    fields = parse_als1(prefix, RECORD_OBJECT_TYPE, 5, MAX_RECORD_BYTES)
    canonical = als1(RECORD_OBJECT_TYPE, fields + [ciphertext, tag])
    if len(canonical) > MAX_RECORD_BYTES:
        fail("encrypted record exceeds wire limit")
    return {
        "prefix": prefix,
        "aad": aad,
        "nonce": nonce_bytes,
        "ciphertext": ciphertext,
        "tag": tag,
        "canonical": canonical,
    }


def require_equal(actual: bytes | str | int, expected: Any, label: str) -> None:
    if isinstance(actual, bytes):
        expected_bytes = hex_bytes(expected, len(actual), label)
        if actual != expected_bytes:
            fail(f"{label}: byte mismatch; actual={actual.hex()}")
    elif actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def verify_aes_self_tests() -> None:
    zero_key = b"\x00" * 32
    require_equal(
        aes256_encrypt_block(zero_key, b"\x00" * 16),
        "dc95c078a2408989ad48a21492842087",
        "AES-256 block self-test",
    )
    ciphertext, tag = aes256_gcm_seal(zero_key, b"\x00" * 12, b"", b"")
    require_equal(ciphertext, "", "AES-256-GCM empty ciphertext self-test")
    require_equal(tag, "530f8afbc74536b9a963b4f1c4cb738b", "AES-256-GCM empty tag self-test")


def validate() -> None:
    verify_aes_self_tests()
    fixture = exact_keys(
        load_json(FIXTURE),
        {"schema", "version", "sourceFixture", "contract", "inputs", "expected", "negativeVectors"},
        "fixture",
    )
    source = load_json(SOURCE_FIXTURE)
    require_equal(fixture["schema"], "aetherlink-production-secure-session-crypto-v1-vectors", "schema")
    require_equal(fixture["version"], 1, "version")

    source_link = exact_keys(fixture["sourceFixture"], {"path", "sha256"}, "source fixture link")
    require_equal(source_link["path"], str(SOURCE_FIXTURE.relative_to(ROOT)), "source fixture path")
    source_digest = hashlib.sha256(SOURCE_FIXTURE.read_bytes()).hexdigest()
    require_equal(source_digest, source_link["sha256"], "source fixture SHA-256")

    contract = exact_keys(
        fixture["contract"],
        {"suite", "profile", "objectTypes", "limits", "domains", "roleBytes", "contentTypes"},
        "contract",
    )
    require_equal(contract["suite"], SUITE, "suite")
    require_equal(contract["profile"], PROFILE, "profile")
    if contract["objectTypes"] != {"confirmation": 29, "encryptedRecord": 30}:
        fail("object type contract drifted")
    expected_limits = {
        "maximumConfirmationBytes": MAX_CONFIRMATION_BYTES,
        "maximumEncryptedRecordBytes": MAX_RECORD_BYTES,
        "maximumPlaintextBytes": MAX_PLAINTEXT_BYTES,
        "maximumEpoch": MAX_EPOCH,
        "maximumRecordsPerEpoch": MAX_EPOCH_RECORDS,
        "maximumPlaintextBytesPerEpoch": MAX_EPOCH_PLAINTEXT_BYTES,
        "maximumRecordsPerSession": MAX_SESSION_RECORDS,
        "maximumPlaintextBytesPerSession": MAX_SESSION_PLAINTEXT_BYTES,
    }
    if contract["limits"] != expected_limits:
        fail("secure-session limits drifted")
    expected_domains = {
        "binding": BINDING_DOMAIN,
        "hkdfRoot": ROOT_DOMAIN,
        "trafficKey": TRAFFIC_KEY_DOMAIN,
        "trafficIv": TRAFFIC_IV_DOMAIN,
        "trafficUpdate": TRAFFIC_UPDATE_DOMAIN,
        "confirmation": CONFIRMATION_DOMAIN,
        "recordAad": RECORD_AAD_DOMAIN,
    }
    if contract["domains"] != expected_domains:
        fail("domain separation labels drifted")
    if contract["roleBytes"] != {"client": 1, "runtime": 2}:
        fail("role-byte contract drifted")
    if contract["contentTypes"] != {"application": 1, "keyUpdate": 2}:
        fail("record content-type contract drifted")

    inputs = exact_keys(
        fixture["inputs"],
        {
            "transcriptObjectKey", "grantAuthorizationObjectKey",
            "clientEphemeralKey", "runtimeEphemeralKey", "sessionId",
        },
        "inputs",
    )
    source_objects = source["objects"]
    source_keys = source["keys"]
    require_equal(inputs["transcriptObjectKey"], "candidateSecureSessionTranscript", "transcript object key")
    require_equal(inputs["grantAuthorizationObjectKey"], "p2pGrantAuthorization", "grant object key")
    require_equal(inputs["clientEphemeralKey"], "clientEphemeral", "client ephemeral key link")
    require_equal(inputs["runtimeEphemeralKey"], "runtimeEphemeral", "runtime ephemeral key link")
    require_equal(
        inputs["sessionId"],
        source_objects["candidateSecureSessionTranscript"]["input"]["sessionId"],
        "session ID",
    )

    transcript = hex_bytes(
        source_objects[inputs["transcriptObjectKey"]]["expectedCanonicalHex"], None, "object 7"
    )
    grant = hex_bytes(
        source_objects[inputs["grantAuthorizationObjectKey"]]["expectedCanonicalHex"], None, "object 26"
    )
    transcript_fields = parse_als1(transcript, 7, 21, 1_024)
    grant_fields = parse_als1(grant, 26, 18, 2_048)
    transcript_digest = hashlib.sha256(transcript).hexdigest()
    grant_digest = hashlib.sha256(grant).hexdigest()
    if transcript_fields[20] != grant_digest.encode("ascii"):
        fail("object 7 is not bound to the exact object 26 digest")
    if transcript_fields[1] != grant_fields[9] or transcript_fields[2] != grant_fields[4]:
        fail("object 7/object 26 session or pair binding drifted")

    binding_claims = struct.pack(">I", len(transcript)) + transcript + struct.pack(">I", len(grant)) + grant
    binding_transcript = domain(BINDING_DOMAIN, binding_claims)
    binding_hash = hashlib.sha256(binding_transcript).digest()
    client_key = source_keys[inputs["clientEphemeralKey"]]
    runtime_key = source_keys[inputs["runtimeEphemeralKey"]]
    client_scalar = int.from_bytes(hex_bytes(client_key["privateScalarHex"], 32, "client scalar"), "big")
    runtime_scalar = int.from_bytes(hex_bytes(runtime_key["privateScalarHex"], 32, "runtime scalar"), "big")
    client_public = hex_bytes(client_key["publicKeyX963Hex"], 65, "client public key")
    runtime_public = hex_bytes(runtime_key["publicKeyX963Hex"], 65, "runtime public key")
    if encode_point(multiply(P256_G, client_scalar)) != client_public:
        fail("client scalar/public-key mismatch")
    if encode_point(multiply(P256_G, runtime_scalar)) != runtime_public:
        fail("runtime scalar/public-key mismatch")
    client_shared = multiply(point(runtime_public, "runtime public key"), client_scalar)[0].to_bytes(32, "big")
    runtime_shared = multiply(point(client_public, "client public key"), runtime_scalar)[0].to_bytes(32, "big")
    if client_shared != runtime_shared or not any(client_shared):
        fail("P-256 ECDH shared secret mismatch or all-zero result")
    prk = hmac.new(binding_hash, client_shared, hashlib.sha256).digest()
    root_info = domain(ROOT_DOMAIN, binding_hash)
    okm = hkdf_expand(prk, root_info, 128)
    keys = {
        "clientConfirmationKeyHex": okm[0:32],
        "runtimeConfirmationKeyHex": okm[32:64],
        "clientEpoch0SecretHex": okm[64:96],
        "runtimeEpoch0SecretHex": okm[96:128],
    }

    expected = exact_keys(
        fixture["expected"],
        {
            "transcriptSha256Hex", "grantAuthorizationSha256Hex", "bindingHashHex",
            "sharedSecretHex", "hkdfSaltHex",
            "hkdfPrkHex", "hkdfRootInfoHex", "hkdfOkmHex", "keys", "epochMaterial",
            "confirmations", "records",
        },
        "expected",
    )
    for label, actual in (
        ("transcriptSha256Hex", bytes.fromhex(transcript_digest)),
        ("grantAuthorizationSha256Hex", bytes.fromhex(grant_digest)),
        ("bindingHashHex", binding_hash),
        ("sharedSecretHex", client_shared),
        ("hkdfSaltHex", binding_hash),
        ("hkdfPrkHex", prk),
        ("hkdfRootInfoHex", root_info),
        ("hkdfOkmHex", okm),
    ):
        require_equal(actual, expected[label], label)
    expected_keys = exact_keys(expected["keys"], set(keys), "expected keys")
    for label, actual in keys.items():
        require_equal(actual, expected_keys[label], label)

    material: dict[str, dict[str, bytes]] = {}
    for role, secret in (("client", okm[64:96]), ("runtime", okm[96:128])):
        key0, iv0 = epoch_material(secret, binding_hash, role, 0)
        secret1 = next_epoch_secret(secret, binding_hash, role, 1)
        key1, iv1 = epoch_material(secret1, binding_hash, role, 1)
        material[role] = {
            "epoch0KeyHex": key0,
            "epoch0IvHex": iv0,
            "epoch1SecretHex": secret1,
            "epoch1KeyHex": key1,
            "epoch1IvHex": iv1,
        }
    expected_material = exact_keys(expected["epochMaterial"], {"client", "runtime"}, "epoch material")
    for role, values in material.items():
        item = exact_keys(expected_material[role], set(values), f"{role} epoch material")
        for label, actual in values.items():
            require_equal(actual, item[label], f"{role}.{label}")

    confirmations = exact_keys(expected["confirmations"], {"client", "runtime"}, "confirmations")
    for role, confirmation_key in (("client", okm[0:32]), ("runtime", okm[32:64])):
        prefix = confirmation_prefix(inputs["sessionId"], transcript_digest, grant_digest, role)
        proof, canonical = confirmation_bytes(prefix, confirmation_key)
        item = exact_keys(
            confirmations[role],
            {"prefixHex", "proofHex", "canonicalHex", "sha256Hex"},
            f"{role} confirmation",
        )
        require_equal(prefix, item["prefixHex"], f"{role} confirmation prefix")
        require_equal(proof, item["proofHex"], f"{role} confirmation proof")
        require_equal(canonical, item["canonicalHex"], f"{role} confirmation canonical")
        require_equal(hashlib.sha256(canonical).digest(), item["sha256Hex"], f"{role} confirmation digest")
        decoded = parse_als1(canonical, CONFIRMATION_OBJECT_TYPE, 8, MAX_CONFIRMATION_BYTES)
        if decoded[-1] != proof:
            fail(f"{role} confirmation proof decode mismatch")

    records = exact_keys(
        expected["records"],
        {"clientApplication0", "runtimeApplication0", "clientKeyUpdate1", "clientEpoch1Application0"},
        "records",
    )
    record_cases = (
        ("clientApplication0", "client", 0, 0, 1, b"client application record", material["client"]["epoch0KeyHex"], material["client"]["epoch0IvHex"]),
        ("runtimeApplication0", "runtime", 0, 0, 1, b"runtime application record", material["runtime"]["epoch0KeyHex"], material["runtime"]["epoch0IvHex"]),
        ("clientKeyUpdate1", "client", 0, 1, 2, struct.pack(">I", 1), material["client"]["epoch0KeyHex"], material["client"]["epoch0IvHex"]),
        ("clientEpoch1Application0", "client", 1, 0, 1, b"client epoch one record", material["client"]["epoch1KeyHex"], material["client"]["epoch1IvHex"]),
    )
    for case_id, role, epoch, sequence, content_type, plaintext, traffic_key, static_iv in record_cases:
        actual = seal_record(
            inputs["sessionId"], binding_hash, role, epoch, sequence,
            content_type, traffic_key, static_iv, plaintext,
        )
        item = exact_keys(
            records[case_id],
            {
                "role", "epoch", "sequence", "contentType", "plaintextHex", "prefixHex",
                "aadHex", "nonceHex", "ciphertextHex", "tagHex", "canonicalHex", "sha256Hex",
            },
            case_id,
        )
        require_equal(item["role"], role, f"{case_id}.role")
        require_equal(uint(item["epoch"], f"{case_id}.epoch"), epoch, f"{case_id}.epoch")
        require_equal(uint(item["sequence"], f"{case_id}.sequence"), sequence, f"{case_id}.sequence")
        require_equal(item["contentType"], "application" if content_type == 1 else "key_update", f"{case_id}.contentType")
        require_equal(plaintext, item["plaintextHex"], f"{case_id}.plaintext")
        for label in ("prefix", "aad", "nonce", "ciphertext", "tag", "canonical"):
            require_equal(actual[label], item[f"{label}Hex"], f"{case_id}.{label}")
        require_equal(hashlib.sha256(actual["canonical"]).digest(), item["sha256Hex"], f"{case_id}.digest")
        decoded = parse_als1(actual["canonical"], RECORD_OBJECT_TYPE, 7, MAX_RECORD_BYTES)
        opened = aes256_gcm_open(
            traffic_key,
            actual["nonce"],
            actual["aad"],
            decoded[5],
            decoded[6],
        )
        if opened != plaintext:
            fail(f"{case_id}: AES-GCM round trip mismatch")

    negative_ids = [
        "object7_object26_substitution", "local_private_public_mismatch", "ephemeral_handle_reuse",
        "role_reflection_confirmation", "confirmation_proof_bit_flip", "confirmation_before_activation",
        "record_wrong_session", "record_wrong_role", "record_replay", "record_gap",
        "record_future_epoch", "record_tag_bit_flip", "record_ciphertext_bit_flip",
        "authentication_failure_no_receive_advance", "key_update_skip", "key_update_duplicate",
        "key_update_epoch_15", "record_max_plus_one", "epoch_record_limit",
        "epoch_plaintext_limit", "session_record_limit", "session_plaintext_limit",
        "expiry_boundary", "clock_regression", "authority_invalidation", "concurrent_seal_unique_sequence",
    ]
    negatives = fixture["negativeVectors"]
    if not isinstance(negatives, list):
        fail("negativeVectors must be a list")
    actual_ids: list[str] = []
    for index, raw in enumerate(negatives):
        item = exact_keys(raw, {"id", "operation", "expectedResult", "platforms"}, f"negative[{index}]")
        actual_ids.append(item["id"])
        if item["platforms"] != ["swift", "android"]:
            fail(f"negative[{index}] platform scope drifted")
    if actual_ids != negative_ids or len(set(actual_ids)) != len(actual_ids):
        fail("negative vector inventory drifted or contains duplicates")

    # Independent executable mutations for the cryptographic negatives.
    client_confirmation = hex_bytes(confirmations["client"]["canonicalHex"], None, "client confirmation")
    runtime_confirmation = hex_bytes(confirmations["runtime"]["canonicalHex"], None, "runtime confirmation")
    if hmac.compare_digest(client_confirmation[-32:], runtime_confirmation[-32:]):
        fail("role-reflected confirmations unexpectedly match")
    mutated_confirmation = bytearray(runtime_confirmation)
    mutated_confirmation[-1] ^= 1
    expected_runtime_prefix = confirmation_prefix(inputs["sessionId"], transcript_digest, grant_digest, "runtime")
    expected_runtime_proof, _ = confirmation_bytes(expected_runtime_prefix, okm[32:64])
    if hmac.compare_digest(bytes(mutated_confirmation[-32:]), expected_runtime_proof):
        fail("mutated confirmation proof was accepted")

    first_record = records["clientApplication0"]
    record_key = material["client"]["epoch0KeyHex"]
    record_nonce = hex_bytes(first_record["nonceHex"], 12, "record nonce")
    record_aad_bytes = hex_bytes(first_record["aadHex"], None, "record AAD")
    record_ciphertext = hex_bytes(first_record["ciphertextHex"], None, "record ciphertext")
    record_tag = bytearray(hex_bytes(first_record["tagHex"], 16, "record tag"))
    record_tag[-1] ^= 1
    try:
        aes256_gcm_open(record_key, record_nonce, record_aad_bytes, record_ciphertext, bytes(record_tag))
    except ValidationError:
        pass
    else:
        fail("modified GCM tag was accepted")
    record_ciphertext_mutated = bytearray(record_ciphertext)
    if record_ciphertext_mutated:
        record_ciphertext_mutated[0] ^= 1
        try:
            aes256_gcm_open(record_key, record_nonce, record_aad_bytes, bytes(record_ciphertext_mutated), bytes(record_tag[:-1] + bytes((record_tag[-1] ^ 1,))))
        except ValidationError:
            pass
        else:
            fail("modified ciphertext was accepted")

    max_wire_size = len(als1(RECORD_OBJECT_TYPE, [
        inputs["sessionId"].encode("ascii"), b"\x02", struct.pack(">I", MAX_EPOCH),
        struct.pack(">Q", MAX_EPOCH_RECORDS - 1), b"\x01",
        b"\x00" * MAX_PLAINTEXT_BYTES, b"\x00" * 16,
    ]))
    if max_wire_size != 1_048_551 or max_wire_size > MAX_RECORD_BYTES:
        fail(f"maximum encrypted-record wire size drifted: {max_wire_size}")


def main() -> int:
    try:
        validate()
    except ValidationError as error:
        print(f"production secure-session crypto vector check failed: {error}", file=sys.stderr)
        return 1
    print("Production secure-session crypto vectors passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
