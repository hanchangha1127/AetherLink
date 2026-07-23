#!/usr/bin/env python3
"""Build and independently validate deterministic production G1a-C vectors.

The default mode is deliberately read-only and compares the checked-in fixture
byte-for-byte with an independently rebuilt document.  ``--rewrite`` is the
only mode that writes the fixture.  This module uses only the Python standard
library and implements the small amount of P-256/DER machinery needed by the
vectors instead of delegating canonical bytes or signatures to Swift/Kotlin.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import struct
import sys
from pathlib import Path
from typing import Any, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "shared/protocol/fixtures/production-g1a-c-v1-vectors.json"

MAGIC = b"ALS1"
VERSION = 1
C1_SUITE = "aetherlink-production-authority-route-v1"
SECURE_SUITE = "aetherlink-secure-session-v1"
PROFILE = "p256_hkdf_sha256_aes256gcm_v1"
SIGNATURE_ALGORITHM = "p256_ecdsa_sha256_der_low_s_v1"
C1_TURN_KIND = "verified_turn_relay_v1"
LEGACY_TURN_KIND = "turn_relay"

P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
P256_A = P256_P - 3
P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
P256_G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)
P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d030107034200"
)

OBJECT_TYPES = {
    "secureSessionTranscript": 7,
    "previousAuthority": 8,
    "previousSnapshot": 9,
    "serviceKeyset": 10,
    "pairStatus": 11,
    "freshPairProof": 12,
    "routeCapability": 13,
    "routePlan": 14,
    "p2pConnector": 15,
    "turnConnector": 16,
    "sealedRelayConnector": 17,
    "preauthorizationSessionContext": 18,
    "p2pRouteAuthorization": 20,
    "turnRouteAuthorization": 21,
    "sealedRelayRouteAuthorization": 22,
}


class VectorError(ValueError):
    """The fixture or an independently reconstructed value is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VectorError(message)


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return sha256(data).hex()


def ascii_bytes(value: str) -> bytes:
    encoded = value.encode("ascii")
    require(encoded.decode("ascii") == value, "non-canonical ASCII")
    return encoded


def raw_digest(value: str) -> bytes:
    require(len(value) == 64 and value == value.lower(), "expected lowercase SHA-256 hex")
    require(all(char in "0123456789abcdef" for char in value), "invalid SHA-256 hex")
    return bytes.fromhex(value)


def be16(value: int) -> bytes:
    require(type(value) is int and 0 <= value < 1 << 16, "invalid UInt16")
    return struct.pack(">H", value)


def be32(value: int) -> bytes:
    require(type(value) is int and 0 <= value < 1 << 32, "invalid UInt32")
    return struct.pack(">I", value)


def be64(value: int) -> bytes:
    require(type(value) is int and 0 <= value < 1 << 64, "invalid UInt64")
    return struct.pack(">Q", value)


def als1_encode(object_type: int, fields: Iterable[bytes]) -> bytes:
    require(type(object_type) is int and 0 < object_type < 256, "invalid object type")
    output = bytearray(MAGIC + bytes((object_type, VERSION)))
    for tag, field in enumerate(fields, 1):
        require(tag < 256 and isinstance(field, bytes), "invalid ALS1 field")
        output.extend(bytes((tag,)) + be32(len(field)) + field)
    return bytes(output)


def als1_decode(data: bytes, object_type: int, field_count: int) -> list[bytes]:
    require(isinstance(data, bytes) and len(data) >= 6, "truncated ALS1 object")
    require(data[:4] == MAGIC, "wrong ALS1 magic")
    require(data[4] == object_type, "wrong ALS1 object type")
    require(data[5] == VERSION, "wrong ALS1 version")
    offset = 6
    fields: list[bytes] = []
    for expected_tag in range(1, field_count + 1):
        require(offset + 5 <= len(data), "truncated ALS1 field header")
        require(data[offset] == expected_tag, "non-sequential ALS1 tag")
        length = int.from_bytes(data[offset + 1 : offset + 5], "big")
        offset += 5
        require(offset + length <= len(data), "truncated ALS1 field")
        fields.append(data[offset : offset + length])
        offset += length
    require(offset == len(data), "trailing ALS1 bytes")
    return fields


def signature_transcript(domain: str, claims: bytes) -> bytes:
    return ascii_bytes(domain) + b"\x00" + be32(len(claims)) + claims


Point = Optional[tuple[int, int]]


def point_add(left: Point, right: Point) -> Point:
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P256_P == 0:
        return None
    if left == right:
        require(y1 != 0, "invalid P-256 doubling")
        slope = ((3 * x1 * x1 + P256_A) * pow(2 * y1, -1, P256_P)) % P256_P
    else:
        slope = ((y2 - y1) * pow((x2 - x1) % P256_P, -1, P256_P)) % P256_P
    x3 = (slope * slope - x1 - x2) % P256_P
    y3 = (slope * (x1 - x3) - y1) % P256_P
    return x3, y3


def scalar_multiply(scalar: int, point: Point = P256_G) -> Point:
    require(type(scalar) is int and 0 <= scalar < P256_N, "invalid P-256 scalar")
    result: Point = None
    addend = point
    while scalar:
        if scalar & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        scalar >>= 1
    return result


def encode_x963(point: Point) -> bytes:
    require(point is not None, "point at infinity has no SEC1 encoding")
    x, y = point
    require((y * y - (x * x * x + P256_A * x + P256_B)) % P256_P == 0, "off-curve point")
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def decode_x963(encoded: bytes) -> Point:
    require(len(encoded) == 65 and encoded[0] == 4, "non-canonical P-256 SEC1 point")
    point = (int.from_bytes(encoded[1:33], "big"), int.from_bytes(encoded[33:], "big"))
    require(point[0] < P256_P and point[1] < P256_P, "P-256 coordinate overflow")
    require((point[1] * point[1] - (point[0] ** 3 + P256_A * point[0] + P256_B)) % P256_P == 0, "off-curve P-256 point")
    return point


def public_material(scalar: int) -> tuple[bytes, bytes, str]:
    x963 = encode_x963(scalar_multiply(scalar))
    spki = P256_SPKI_PREFIX + x963
    require(len(spki) == 91, "unexpected P-256 SPKI size")
    return x963, spki, sha256_hex(spki)


def _rfc6979_k(private_scalar: int, digest: bytes) -> int:
    require(len(digest) == 32, "RFC6979 requires SHA-256 digest")
    x = private_scalar.to_bytes(32, "big")
    h1 = (int.from_bytes(digest, "big") % P256_N).to_bytes(32, "big")
    value = b"\x01" * 32
    key = b"\x00" * 32
    key = hmac.new(key, value + b"\x00" + x + h1, hashlib.sha256).digest()
    value = hmac.new(key, value, hashlib.sha256).digest()
    key = hmac.new(key, value + b"\x01" + x + h1, hashlib.sha256).digest()
    value = hmac.new(key, value, hashlib.sha256).digest()
    while True:
        value = hmac.new(key, value, hashlib.sha256).digest()
        candidate = int.from_bytes(value, "big")
        if 1 <= candidate < P256_N:
            return candidate
        key = hmac.new(key, value + b"\x00", hashlib.sha256).digest()
        value = hmac.new(key, value, hashlib.sha256).digest()


def _der_integer(value: int) -> bytes:
    require(0 < value < P256_N, "invalid ECDSA integer")
    encoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if encoded[0] & 0x80:
        encoded = b"\x00" + encoded
    return b"\x02" + bytes((len(encoded),)) + encoded


def der_encode_signature(r: int, s: int) -> bytes:
    body = _der_integer(r) + _der_integer(s)
    require(len(body) < 128, "unexpected long DER signature")
    return b"\x30" + bytes((len(body),)) + body


def der_decode_signature(signature: bytes, require_low_s: bool = True) -> tuple[int, int]:
    require(8 <= len(signature) <= 72, "invalid DER signature size")
    require(signature[0] == 0x30 and signature[1] == len(signature) - 2, "invalid DER sequence")
    offset = 2
    values: list[int] = []
    for _ in range(2):
        require(offset + 2 <= len(signature) and signature[offset] == 2, "invalid DER integer")
        length = signature[offset + 1]
        offset += 2
        require(0 < length <= 33 and offset + length <= len(signature), "invalid DER integer length")
        encoded = signature[offset : offset + length]
        offset += length
        if encoded[0] == 0:
            require(len(encoded) > 1 and encoded[1] & 0x80, "redundant DER zero")
            encoded = encoded[1:]
        else:
            require(not encoded[0] & 0x80, "negative DER integer")
        require(len(encoded) <= 32 and any(encoded), "invalid ECDSA integer")
        value = int.from_bytes(encoded, "big")
        require(0 < value < P256_N, "ECDSA integer outside P-256 order")
        values.append(value)
    require(offset == len(signature), "trailing DER bytes")
    if require_low_s:
        require(values[1] <= P256_N // 2, "high-S signature")
    require(der_encode_signature(*values) == signature, "non-minimal DER signature")
    return values[0], values[1]


def ecdsa_sign_rfc6979(private_scalar: int, message: bytes) -> bytes:
    require(0 < private_scalar < P256_N, "invalid signing scalar")
    digest = sha256(message)
    z = int.from_bytes(digest, "big")
    k = _rfc6979_k(private_scalar, digest)
    point = scalar_multiply(k)
    require(point is not None, "invalid RFC6979 point")
    r = point[0] % P256_N
    s = (pow(k, -1, P256_N) * (z + r * private_scalar)) % P256_N
    require(r != 0 and s != 0, "degenerate ECDSA signature")
    s = min(s, P256_N - s)
    signature = der_encode_signature(r, s)
    der_decode_signature(signature)
    return signature


def ecdsa_verify(public_x963: bytes, message: bytes, signature: bytes) -> None:
    r, s = der_decode_signature(signature)
    public = decode_x963(public_x963)
    z = int.from_bytes(sha256(message), "big")
    inverse = pow(s, -1, P256_N)
    point = point_add(
        scalar_multiply((z * inverse) % P256_N),
        scalar_multiply((r * inverse) % P256_N, public),
    )
    require(point is not None and point[0] % P256_N == r, "invalid ECDSA signature")


def key_record(name: str, scalar: int) -> dict[str, Any]:
    x963, spki, key_id = public_material(scalar)
    return {
        "name": name,
        "privateScalarHex": scalar.to_bytes(32, "big").hex(),
        "publicKeyX963Hex": x963.hex(),
        "publicKeySPKIDERHex": spki.hex(),
        "keyId": key_id,
    }


def object_record(
    object_type: int,
    coverage: str,
    input_value: dict[str, Any],
    canonical: bytes,
    claims: bytes | None = None,
    signatures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "objectType": object_type,
        "coverage": coverage,
        "input": input_value,
        "expectedCanonicalByteCount": len(canonical),
        "expectedCanonicalHex": canonical.hex(),
        "expectedSha256Hex": sha256_hex(canonical),
    }
    if claims is not None:
        record["expectedClaimsCanonicalHex"] = claims.hex()
    if signatures is not None:
        record["signatures"] = signatures
    return record


def signed_signature_record(signer: str, domain: str, claims: bytes, scalar: int) -> tuple[bytes, dict[str, Any]]:
    transcript = signature_transcript(domain, claims)
    signature = ecdsa_sign_rfc6979(scalar, transcript)
    return signature, {
        "signer": signer,
        "signingDomain": domain,
        "expectedSigningTranscriptHex": transcript.hex(),
        "expectedSigningTranscriptSha256Hex": sha256_hex(transcript),
        "fixedLowSDERSignatureHex": signature.hex(),
    }


def recovery_reuse_digest(pair_digest: str, secret: bytes) -> str:
    claims = raw_digest(pair_digest) + be32(len(secret)) + secret
    return sha256_hex(signature_transcript(
        "AetherLink G1a-C secret-material reuse commitment v1", claims
    ))


def recovery_purpose_digest(domain: str, pair_digest: str, reuse_digest: str) -> str:
    claims = raw_digest(pair_digest) + raw_digest(reuse_digest)
    return sha256_hex(signature_transcript(domain, claims))


def recovery_commitments(pair_digest: str, endpoint: bytes, route: bytes) -> dict[str, str]:
    endpoint_reuse = recovery_reuse_digest(pair_digest, endpoint)
    route_reuse = recovery_reuse_digest(pair_digest, route)
    return {
        "endpointTrafficSecretCommitment": recovery_purpose_digest(
            "AetherLink G1a-C endpoint-traffic-secret commitment v1", pair_digest, endpoint_reuse
        ),
        "routeTokenSeedCommitment": recovery_purpose_digest(
            "AetherLink G1a-C route-token-seed commitment v1", pair_digest, route_reuse
        ),
        "endpointTrafficSecretReuseDigest": endpoint_reuse,
        "routeTokenSeedReuseDigest": route_reuse,
    }


def route_handle_digest(kind: str, route_handle: str) -> str:
    encoded = route_handle.encode("utf-8")
    require(0 < len(encoded) <= 512, "invalid route handle")
    claims = be32(len(encoded)) + encoded
    return sha256_hex(signature_transcript(
        f"AetherLink G1a-C route-handle commitment {kind} v1", claims
    ))


def credential_digest(kind: str, route_handle: str, nonce: str, secret: bytes) -> str:
    handle = route_handle.encode("utf-8")
    nonce_bytes = nonce.encode("utf-8")
    require(0 < len(handle) <= 512 and 0 < len(nonce_bytes) <= 512, "invalid connector text")
    require(32 <= len(secret) <= 512, "invalid connector secret")
    claims = (
        be32(len(handle)) + handle + be32(len(nonce_bytes)) + nonce_bytes
        + be32(len(secret)) + secret
    )
    return sha256_hex(signature_transcript(
        f"AetherLink G1a-C credential commitment {kind} v1", claims
    ))


def authority_bytes(value: dict[str, Any]) -> bytes:
    return als1_encode(8, [
        ascii_bytes(SECURE_SUITE), ascii_bytes(value["pairBindingDigest"]),
        be64(value["pairEpoch"]), ascii_bytes(value["clientIdentityFingerprint"]),
        ascii_bytes(value["runtimeIdentityFingerprint"]), be64(value["generation"]),
        be64(value["serviceConfigVersion"]), be64(value["keysetVersion"]),
        be64(value["revocationCounter"]), be32(value["protocolFloor"]),
        ascii_bytes(PROFILE), ascii_bytes(value["status"]), ascii_bytes(value["transitionId"]),
        ascii_bytes(value["transitionRequestDigest"]), ascii_bytes(value["acceptedReceiptDigest"]),
        be64(value["authorityRevision"]),
    ])


def snapshot_bytes(value: dict[str, Any], authority: bytes) -> bytes:
    consumed = b"".join(
        ascii_bytes(entry["sessionId"]) + ascii_bytes(entry["transcriptDigest"])
        for entry in value["consumedEntries"]
    )
    fields = [
        ascii_bytes(SECURE_SUITE), authority, be64(value["localRevision"]),
        be32(len(value["consumedEntries"])), consumed,
    ]
    if value["transitionHistory"]:
        history = b"".join(
            raw_digest(entry["transitionId"]) + raw_digest(entry["transitionRequestDigest"])
            for entry in value["transitionHistory"]
        )
        fields.extend([be32(len(value["transitionHistory"])), history])
    return als1_encode(9, fields)


def connector_bytes(value: dict[str, Any]) -> bytes:
    return als1_encode(value["objectType"], [
        ascii_bytes(C1_SUITE), ascii_bytes(value["kind"]), bytes.fromhex(value["addressHex"]),
        be16(value["port"]), ascii_bytes(value["serverName"]), ascii_bytes(value["transport"]),
        ascii_bytes(value["routeHandleDigest"]), ascii_bytes(value["credentialCommitmentDigest"]),
        ascii_bytes(value["pathReceiptDigest"]), ascii_bytes(value["leaseDigest"]),
        ascii_bytes(value["allocationDigest"]),
    ])


def authorization_bytes(object_type: int, value: dict[str, Any]) -> bytes:
    return als1_encode(object_type, [
        ascii_bytes(C1_SUITE), ascii_bytes(value["pairBindingDigest"]), be64(value["pairEpoch"]),
        be64(value["generation"]), ascii_bytes(value["pairAuthorityDigest"]),
        ascii_bytes(value["routeCapabilityDigest"]), ascii_bytes(value["routePlanClaimsDigest"]),
        ascii_bytes(value["selectedPathReceiptDigest"]), ascii_bytes(value["serviceIdDigest"]),
        be64(value["keysetVersion"]),
    ])


def build_fixture() -> dict[str, Any]:
    now_ms = 1_000_000
    scalars = {
        "root": 1,
        "status": 2,
        "route": 3,
        "clientEphemeral": 30,
        "runtimeEphemeral": 31,
        "previousClientIdentity": 50,
        "survivorRuntimeIdentity": 51,
        "replacementClientIdentity": 52,
    }
    keys = {name: key_record(name, scalar) for name, scalar in scalars.items()}
    service_digest = "a" * 64
    pair_digest = "d" * 64
    path_digest = "7" * 64
    lease_digest = "6" * 64
    allocation_digest = "8" * 64
    previous_endpoint = bytes.fromhex("11" * 32)
    previous_route = bytes.fromhex("12" * 32)
    next_endpoint = bytes.fromhex("13" * 32)
    next_route = bytes.fromhex("14" * 32)
    connector_secret = bytes.fromhex("5a" * 32)
    previous_recovery = recovery_commitments(pair_digest, previous_endpoint, previous_route)
    next_recovery = recovery_commitments(pair_digest, next_endpoint, next_route)

    previous_authority_input = {
        "pairBindingDigest": pair_digest,
        "pairEpoch": 1,
        "clientIdentityFingerprint": keys["previousClientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["survivorRuntimeIdentity"]["keyId"],
        "generation": 1,
        "serviceConfigVersion": 1,
        "keysetVersion": 1,
        "revocationCounter": 0,
        "protocolFloor": 1,
        "status": "active",
        "transitionId": "1" * 64,
        "transitionRequestDigest": "2" * 64,
        "acceptedReceiptDigest": "e" * 64,
        "authorityRevision": 1,
    }
    previous_authority = authority_bytes(previous_authority_input)
    previous_snapshot_input = {
        "authority": "previousAuthority",
        "localRevision": 1,
        "consumedEntries": [],
        "transitionHistory": [],
    }
    previous_snapshot = snapshot_bytes(previous_snapshot_input, previous_authority)

    delegated = []
    for name, purpose in (("status", 1), ("route", 2)):
        delegated.append({
            "keysetVersion": 1,
            "keyId": keys[name]["keyId"],
            "purposes": purpose,
            "notBeforeMs": 999_000,
            "expiresAtMs": 1_100_000,
            "revokedAtMs": 0,
            "publicKeyX963Hex": keys[name]["publicKeyX963Hex"],
        })
    delegated.sort(key=lambda entry: entry["keyId"])
    keyset_input = {
        "serviceIdDigest": service_digest,
        "keysetVersion": 1,
        "previousKeysetDigest": "none",
        "issuedAtMs": 999_000,
        "expiresAtMs": 1_100_000,
        "rootKeyId": keys["root"]["keyId"],
        "delegatedKeys": delegated,
    }
    packed_delegated = b"".join(
        be64(entry["keysetVersion"]) + raw_digest(entry["keyId"]) + be32(entry["purposes"])
        + be64(entry["notBeforeMs"]) + be64(entry["expiresAtMs"])
        + be64(entry["revokedAtMs"]) + bytes.fromhex(entry["publicKeyX963Hex"])
        for entry in delegated
    )
    keyset_claim_fields = [
        ascii_bytes(C1_SUITE), ascii_bytes(service_digest), be64(1), ascii_bytes("none"),
        be64(999_000), be64(1_100_000), ascii_bytes(keys["root"]["keyId"]),
        be32(len(delegated)), packed_delegated, ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    keyset_claims = als1_encode(10, keyset_claim_fields)
    keyset_signature, keyset_signature_record = signed_signature_record(
        "root", "AetherLink G1a-C service-keyset root signature v1", keyset_claims, scalars["root"]
    )
    keyset = als1_encode(10, keyset_claim_fields + [keyset_signature])

    proof_input = {
        "transitionId": "f" * 64,
        "replacementRole": "client",
        "previousAuthorityDigest": sha256_hex(previous_authority),
        "previousPairBindingDigest": pair_digest,
        "nextPairBindingDigest": pair_digest,
        "previousPairEpoch": 1,
        "nextPairEpoch": 2,
        "previousClientIdentityFingerprint": keys["previousClientIdentity"]["keyId"],
        "nextClientIdentityFingerprint": keys["replacementClientIdentity"]["keyId"],
        "previousRuntimeIdentityFingerprint": keys["survivorRuntimeIdentity"]["keyId"],
        "nextRuntimeIdentityFingerprint": keys["survivorRuntimeIdentity"]["keyId"],
        "nextGeneration": 2,
        "nextServiceConfigVersion": 1,
        "nextKeysetVersion": 1,
        "nextRevocationCounter": 0,
        "nextProtocolFloor": 1,
        "nextAuthorityRevision": 2,
        "issuedAtMs": 999_900,
        "expiresAtMs": 1_010_000,
        "freshPairingRequestDigest": "3" * 64,
        "freshPairingResultDigest": "4" * 64,
        "freshTransportBindingDigest": "5" * 64,
        "previousEndpointTrafficSecretCommitment": previous_recovery["endpointTrafficSecretCommitment"],
        "nextEndpointTrafficSecretCommitment": next_recovery["endpointTrafficSecretCommitment"],
        "previousRouteTokenSeedCommitment": previous_recovery["routeTokenSeedCommitment"],
        "nextRouteTokenSeedCommitment": next_recovery["routeTokenSeedCommitment"],
        "previousEndpointTrafficSecretReuseDigest": previous_recovery["endpointTrafficSecretReuseDigest"],
        "nextEndpointTrafficSecretReuseDigest": next_recovery["endpointTrafficSecretReuseDigest"],
        "previousRouteTokenSeedReuseDigest": previous_recovery["routeTokenSeedReuseDigest"],
        "nextRouteTokenSeedReuseDigest": next_recovery["routeTokenSeedReuseDigest"],
        "survivorRole": "runtime",
        "replacementSignerRole": "client",
    }
    proof_claim_fields = [
        ascii_bytes(C1_SUITE), ascii_bytes(proof_input["transitionId"]), ascii_bytes("client"),
        ascii_bytes(proof_input["previousAuthorityDigest"]), ascii_bytes(pair_digest),
        ascii_bytes(pair_digest), be64(1), be64(2),
        ascii_bytes(proof_input["previousClientIdentityFingerprint"]),
        ascii_bytes(proof_input["nextClientIdentityFingerprint"]),
        ascii_bytes(proof_input["previousRuntimeIdentityFingerprint"]),
        ascii_bytes(proof_input["nextRuntimeIdentityFingerprint"]),
        be64(2), be64(1), be64(1), be64(0), be32(1), be64(2), be64(999_900),
        be64(1_010_000), ascii_bytes("3" * 64), ascii_bytes("4" * 64), ascii_bytes("5" * 64),
        ascii_bytes(proof_input["previousEndpointTrafficSecretCommitment"]),
        ascii_bytes(proof_input["nextEndpointTrafficSecretCommitment"]),
        ascii_bytes(proof_input["previousRouteTokenSeedCommitment"]),
        ascii_bytes(proof_input["nextRouteTokenSeedCommitment"]),
        ascii_bytes(proof_input["previousEndpointTrafficSecretReuseDigest"]),
        ascii_bytes(proof_input["nextEndpointTrafficSecretReuseDigest"]),
        ascii_bytes(proof_input["previousRouteTokenSeedReuseDigest"]),
        ascii_bytes(proof_input["nextRouteTokenSeedReuseDigest"]),
        ascii_bytes(SIGNATURE_ALGORITHM), ascii_bytes("runtime"), ascii_bytes("client"),
    ]
    proof_claims = als1_encode(12, proof_claim_fields)
    survivor_signature, survivor_record = signed_signature_record(
        "survivorRuntimeIdentity",
        "AetherLink G1a-C fresh-pair survivor runtime signature v1",
        proof_claims,
        scalars["survivorRuntimeIdentity"],
    )
    replacement_signature, replacement_record = signed_signature_record(
        "replacementClientIdentity",
        "AetherLink G1a-C fresh-pair replacement client signature v1",
        proof_claims,
        scalars["replacementClientIdentity"],
    )
    proof = als1_encode(12, proof_claim_fields + [survivor_signature, replacement_signature])
    proof_digest = sha256_hex(proof)
    transition_request_digest = sha256_hex(proof_claims)

    next_authority_input = {
        "pairBindingDigest": pair_digest,
        "pairEpoch": 2,
        "clientIdentityFingerprint": keys["replacementClientIdentity"]["keyId"],
        "runtimeIdentityFingerprint": keys["survivorRuntimeIdentity"]["keyId"],
        "generation": 2,
        "serviceConfigVersion": 1,
        "keysetVersion": 1,
        "revocationCounter": 0,
        "protocolFloor": 1,
        "status": "active",
        "transitionId": "f" * 64,
        "transitionRequestDigest": transition_request_digest,
        "acceptedReceiptDigest": proof_digest,
        "authorityRevision": 2,
    }
    next_authority = authority_bytes(next_authority_input)
    history = [{
        "transitionId": previous_authority_input["transitionId"],
        "transitionRequestDigest": previous_authority_input["transitionRequestDigest"],
    }]
    next_snapshot_input = {
        "authority": "nextAuthority",
        "localRevision": 2,
        "consumedEntries": [],
        "transitionHistory": history,
    }
    next_snapshot = snapshot_bytes(next_snapshot_input, next_authority)

    status_input = {
        "serviceIdDigest": service_digest,
        "keysetVersion": 1,
        "signingKeyId": keys["status"]["keyId"],
        "issuedAtMs": 999_950,
        "expiresAtMs": 1_010_000,
        "requesterRole": "runtime",
        "requestNonce": "9" * 64,
        "transitionKind": "fresh_pair",
        "previousAuthorityDigest": sha256_hex(previous_authority),
        "evidenceKind": "dual_signed_fresh_pair",
        "authorizationEvidenceDigest": proof_digest,
        "authority": "nextAuthority",
        "transitionHistory": history,
    }
    packed_history = b"".join(
        raw_digest(entry["transitionId"]) + raw_digest(entry["transitionRequestDigest"])
        for entry in history
    )
    status_claim_fields = [
        ascii_bytes(C1_SUITE), ascii_bytes(service_digest), be64(1),
        ascii_bytes(keys["status"]["keyId"]), be64(999_950), be64(1_010_000),
        ascii_bytes("runtime"), ascii_bytes("9" * 64), ascii_bytes("fresh_pair"),
        ascii_bytes(sha256_hex(previous_authority)), ascii_bytes("dual_signed_fresh_pair"),
        ascii_bytes(proof_digest), next_authority, be32(len(history)), packed_history,
        ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    status_claims = als1_encode(11, status_claim_fields)
    status_signature, status_signature_record = signed_signature_record(
        "status", "AetherLink G1a-C pair-status service signature v1", status_claims, scalars["status"]
    )
    status = als1_encode(11, status_claim_fields + [status_signature])

    context_input = {
        "revision": 1,
        "sessionId": "a" * 32,
        "pairBindingDigest": pair_digest,
        "pairEpoch": 2,
        "clientIdentityFingerprint": next_authority_input["clientIdentityFingerprint"],
        "runtimeIdentityFingerprint": next_authority_input["runtimeIdentityFingerprint"],
        "clientRole": "client",
        "runtimeRole": "runtime",
        "clientEphemeralPublicKeyHex": keys["clientEphemeral"]["publicKeyX963Hex"],
        "runtimeEphemeralPublicKeyHex": keys["runtimeEphemeral"]["publicKeyX963Hex"],
        "clientNonce": "b" * 32,
        "runtimeNonce": "c" * 32,
        "generation": 2,
        "serviceConfigVersion": 1,
        "keysetVersion": 1,
        "revocationCounter": 0,
        "protocolVersion": 1,
        "minimumProtocolVersion": 1,
        "profile": PROFILE,
        "routeKind": C1_TURN_KIND,
    }
    context_fields = [
        ascii_bytes(C1_SUITE), be64(1), ascii_bytes(context_input["sessionId"]),
        ascii_bytes(pair_digest), be64(2),
        ascii_bytes(context_input["clientIdentityFingerprint"]),
        ascii_bytes(context_input["runtimeIdentityFingerprint"]),
        ascii_bytes("client"), ascii_bytes("runtime"),
        bytes.fromhex(context_input["clientEphemeralPublicKeyHex"]),
        bytes.fromhex(context_input["runtimeEphemeralPublicKeyHex"]),
        ascii_bytes(context_input["clientNonce"]), ascii_bytes(context_input["runtimeNonce"]),
        be64(2), be64(1), be64(1), be64(0), be32(1), be32(1), ascii_bytes(PROFILE),
        ascii_bytes(C1_TURN_KIND),
    ]
    context = als1_encode(18, context_fields)

    route_handle = "relay-01"
    connector_nonce = "nonce-01"
    turn_connector_input = {
        "objectType": 16,
        "kind": C1_TURN_KIND,
        "addressHex": "7f000001",
        "port": 443,
        "serverName": "relay.example",
        "transport": "tls_tcp",
        "routeHandleDigest": route_handle_digest(C1_TURN_KIND, route_handle),
        "credentialCommitmentDigest": credential_digest(
            C1_TURN_KIND, route_handle, connector_nonce, connector_secret
        ),
        "pathReceiptDigest": path_digest,
        "leaseDigest": lease_digest,
        "allocationDigest": allocation_digest,
    }
    turn_connector = connector_bytes(turn_connector_input)

    plan_input = {
        "planId": "0" * 64,
        "revision": 1,
        "kind": C1_TURN_KIND,
        "pairAuthorityDigest": sha256_hex(next_authority),
        "pairBindingDigest": pair_digest,
        "pairEpoch": 2,
        "generation": 2,
        "clientIdentityFingerprint": next_authority_input["clientIdentityFingerprint"],
        "runtimeIdentityFingerprint": next_authority_input["runtimeIdentityFingerprint"],
        "connector": "turnConnector",
        "securityContextDigest": sha256_hex(context),
        "selectedPathReceiptDigest": path_digest,
        "notBeforeMs": 999_990,
        "expiresAtMs": 1_020_000,
    }
    plan_fields = [
        ascii_bytes(C1_SUITE), ascii_bytes(plan_input["planId"]), be64(1), ascii_bytes(C1_TURN_KIND),
        ascii_bytes(plan_input["pairAuthorityDigest"]), ascii_bytes(pair_digest), be64(2), be64(2),
        ascii_bytes(plan_input["clientIdentityFingerprint"]),
        ascii_bytes(plan_input["runtimeIdentityFingerprint"]), turn_connector,
        ascii_bytes(plan_input["securityContextDigest"]), ascii_bytes(path_digest),
        be64(999_990), be64(1_020_000),
    ]
    plan = als1_encode(14, plan_fields)

    capability_input = {
        "serviceIdDigest": service_digest,
        "keysetVersion": 1,
        "signingKeyId": keys["route"]["keyId"],
        "capabilityId": "c" * 64,
        "issuedAtMs": 999_900,
        "notBeforeMs": 999_990,
        "expiresAtMs": 1_030_000,
        "pairAuthorityDigest": sha256_hex(next_authority),
        "pairBindingDigest": pair_digest,
        "pairEpoch": 2,
        "clientIdentityFingerprint": next_authority_input["clientIdentityFingerprint"],
        "runtimeIdentityFingerprint": next_authority_input["runtimeIdentityFingerprint"],
        "generation": 2,
        "serviceConfigVersion": 1,
        "revocationCounter": 0,
        "protocolFloor": 1,
        "kind": C1_TURN_KIND,
        "routePlanClaimsDigest": sha256_hex(plan),
        "maxUses": 1,
    }
    capability_claim_fields = [
        ascii_bytes(C1_SUITE), ascii_bytes(service_digest), be64(1),
        ascii_bytes(keys["route"]["keyId"]), ascii_bytes("c" * 64), be64(999_900),
        be64(999_990), be64(1_030_000), ascii_bytes(capability_input["pairAuthorityDigest"]),
        ascii_bytes(pair_digest), be64(2),
        ascii_bytes(capability_input["clientIdentityFingerprint"]),
        ascii_bytes(capability_input["runtimeIdentityFingerprint"]),
        be64(2), be64(1), be64(0), be32(1), ascii_bytes(C1_TURN_KIND),
        ascii_bytes(capability_input["routePlanClaimsDigest"]), be32(1),
        ascii_bytes(SIGNATURE_ALGORITHM),
    ]
    capability_claims = als1_encode(13, capability_claim_fields)
    capability_signature, capability_signature_record = signed_signature_record(
        "route", "AetherLink G1a-C route-capability service signature v1",
        capability_claims, scalars["route"]
    )
    capability = als1_encode(13, capability_claim_fields + [capability_signature])

    authorization_input = {
        "pairBindingDigest": pair_digest,
        "pairEpoch": 2,
        "generation": 2,
        "pairAuthorityDigest": sha256_hex(next_authority),
        "routeCapabilityDigest": sha256_hex(capability),
        "routePlanClaimsDigest": sha256_hex(plan),
        "selectedPathReceiptDigest": path_digest,
        "serviceIdDigest": service_digest,
        "keysetVersion": 1,
    }
    turn_authorization = authorization_bytes(21, authorization_input)

    transcript_input = {
        "sessionId": context_input["sessionId"],
        "pairBindingDigest": pair_digest,
        "pairEpoch": 2,
        "clientIdentityFingerprint": context_input["clientIdentityFingerprint"],
        "runtimeIdentityFingerprint": context_input["runtimeIdentityFingerprint"],
        "clientRole": "client",
        "runtimeRole": "runtime",
        "clientEphemeralPublicKeyHex": context_input["clientEphemeralPublicKeyHex"],
        "runtimeEphemeralPublicKeyHex": context_input["runtimeEphemeralPublicKeyHex"],
        "clientNonce": context_input["clientNonce"],
        "runtimeNonce": context_input["runtimeNonce"],
        "generation": 2,
        "serviceConfigVersion": 1,
        "keysetVersion": 1,
        "revocationCounter": 0,
        "protocolVersion": 1,
        "minimumProtocolVersion": 1,
        "profile": PROFILE,
        "routeKind": LEGACY_TURN_KIND,
        "routeAuthDigest": sha256_hex(turn_authorization),
    }
    transcript = als1_encode(7, [
        ascii_bytes(SECURE_SUITE), ascii_bytes(transcript_input["sessionId"]),
        ascii_bytes(pair_digest), be64(2),
        ascii_bytes(transcript_input["clientIdentityFingerprint"]),
        ascii_bytes(transcript_input["runtimeIdentityFingerprint"]),
        ascii_bytes("client"), ascii_bytes("runtime"),
        bytes.fromhex(transcript_input["clientEphemeralPublicKeyHex"]),
        bytes.fromhex(transcript_input["runtimeEphemeralPublicKeyHex"]),
        ascii_bytes(transcript_input["clientNonce"]), ascii_bytes(transcript_input["runtimeNonce"]),
        be64(2), be64(1), be64(1), be64(0), be32(1), be32(1), ascii_bytes(PROFILE),
        ascii_bytes(LEGACY_TURN_KIND), ascii_bytes(transcript_input["routeAuthDigest"]),
    ])

    handle_bytes = route_handle.encode("utf-8")
    nonce_bytes = connector_nonce.encode("utf-8")
    connector_input_claims = (
        turn_connector + be32(len(handle_bytes)) + handle_bytes + be32(len(nonce_bytes))
        + nonce_bytes + raw_digest(turn_connector_input["credentialCommitmentDigest"])
    )
    connector_input_commitment = sha256_hex(signature_transcript(
        "AetherLink G1a-C verified connector-input commitment v1", connector_input_claims
    ))
    admitted_snapshot_input = {
        "authority": "nextAuthority",
        "localRevision": 3,
        "consumedEntries": [{
            "sessionId": context_input["sessionId"],
            "transcriptDigest": sha256_hex(transcript),
        }],
        "transitionHistory": history,
    }
    admitted_snapshot = snapshot_bytes(admitted_snapshot_input, next_authority)
    permit_claims = (
        sha256(transcript) + turn_authorization + plan + turn_connector + capability + context
        + raw_digest(connector_input_commitment) + sha256(admitted_snapshot)
    )
    permit_digest = sha256_hex(signature_transcript(
        "AetherLink G1a-C durable admission permit v1", permit_claims
    ))

    codec_connectors: dict[str, tuple[dict[str, Any], bytes]] = {}
    for name, object_type, kind, server, transport, lease, allocation in (
        ("p2pConnector", 15, "verified_p2p_direct_v1", "none", "udp", "none", "none"),
        ("sealedRelayConnector", 17, "verified_sealed_relay_v1", "relay.example", "tls_tcp", lease_digest, allocation_digest),
    ):
        value = {
            "objectType": object_type,
            "kind": kind,
            "addressHex": "7f000001",
            "port": 443,
            "serverName": server,
            "transport": transport,
            "routeHandleDigest": route_handle_digest(kind, route_handle),
            "credentialCommitmentDigest": credential_digest(kind, route_handle, connector_nonce, connector_secret),
            "pathReceiptDigest": path_digest,
            "leaseDigest": lease,
            "allocationDigest": allocation,
        }
        codec_connectors[name] = value, connector_bytes(value)
    p2p_authorization = authorization_bytes(20, authorization_input)
    sealed_authorization = authorization_bytes(22, authorization_input)

    objects = {
        "previousAuthority": object_record(8, "semantic", previous_authority_input, previous_authority),
        "previousSnapshot": object_record(9, "semantic", previous_snapshot_input, previous_snapshot),
        "serviceKeyset": object_record(
            10, "semantic", keyset_input, keyset, keyset_claims, [keyset_signature_record]
        ),
        "freshPairProof": object_record(
            12, "semantic", proof_input, proof, proof_claims,
            [survivor_record, replacement_record],
        ),
        "nextAuthority": object_record(8, "semantic", next_authority_input, next_authority),
        "pairStatus": object_record(
            11, "semantic", status_input, status, status_claims, [status_signature_record]
        ),
        "nextSnapshot": object_record(9, "semantic", next_snapshot_input, next_snapshot),
        "preauthorizationSessionContext": object_record(18, "semantic", context_input, context),
        "turnConnector": object_record(16, "semantic", turn_connector_input, turn_connector),
        "routePlan": object_record(14, "semantic", plan_input, plan),
        "routeCapability": object_record(
            13, "semantic", capability_input, capability, capability_claims,
            [capability_signature_record],
        ),
        "turnRouteAuthorization": object_record(21, "semantic", authorization_input, turn_authorization),
        "secureSessionTranscript": object_record(7, "semantic", transcript_input, transcript),
        "admittedSnapshot": object_record(9, "semantic", admitted_snapshot_input, admitted_snapshot),
        "p2pConnector": object_record(15, "codec_only", codec_connectors["p2pConnector"][0], codec_connectors["p2pConnector"][1]),
        "sealedRelayConnector": object_record(17, "codec_only", codec_connectors["sealedRelayConnector"][0], codec_connectors["sealedRelayConnector"][1]),
        "p2pRouteAuthorization": object_record(20, "codec_only", authorization_input, p2p_authorization),
        "sealedRelayRouteAuthorization": object_record(22, "codec_only", authorization_input, sealed_authorization),
    }

    return {
        "schema": "aetherlink-production-g1a-c-v1-vectors",
        "version": 1,
        "magic": MAGIC.decode("ascii"),
        "suite": C1_SUITE,
        "secureSessionSuite": SECURE_SUITE,
        "signatureAlgorithm": SIGNATURE_ALGORITHM,
        "generationProfile": "python-stdlib-rfc6979-sha256-test-only-v1",
        "constants": {
            "nowMs": now_ms,
            "minimumAcceptedKeysetVersion": 1,
            "maximumClockSkewMs": 30_000,
            "maximumKeysetLifetimeMs": 2_678_400_000,
            "maximumStatusLifetimeMs": 300_000,
            "maximumFreshPairLifetimeMs": 300_000,
            "maximumRouteLifetimeMs": 600_000,
            "protocolVersion": 1,
            "minimumProtocolVersion": 1,
            "profile": PROFILE,
        },
        "syntheticMaterials": {
            "testOnly": True,
            "warning": "Public deterministic test material; never use these scalars or secrets in production.",
            "previousEndpointTrafficSecretHex": previous_endpoint.hex(),
            "previousRouteTokenSeedHex": previous_route.hex(),
            "nextEndpointTrafficSecretHex": next_endpoint.hex(),
            "nextRouteTokenSeedHex": next_route.hex(),
            "connectorSecretHex": connector_secret.hex(),
            "routeHandle": route_handle,
            "connectorNonce": connector_nonce,
        },
        "keys": keys,
        "objects": objects,
        "derived": {
            "previousRecoveryCommitments": previous_recovery,
            "nextRecoveryCommitments": next_recovery,
            "freshPairTransitionRequestDigest": transition_request_digest,
            "freshPairProofDigest": proof_digest,
            "previousAuthorityDigest": sha256_hex(previous_authority),
            "previousSnapshotDigest": sha256_hex(previous_snapshot),
            "nextAuthorityDigest": sha256_hex(next_authority),
            "nextSnapshotDigest": sha256_hex(next_snapshot),
            "preauthorizationSessionContextDigest": sha256_hex(context),
            "routePlanClaimsDigest": sha256_hex(plan),
            "routeCapabilityDigest": sha256_hex(capability),
            "turnRouteAuthorizationDigest": sha256_hex(turn_authorization),
            "secureSessionTranscriptDigest": sha256_hex(transcript),
            "connectorInputCommitmentDigest": connector_input_commitment,
            "admittedSnapshotDigest": sha256_hex(admitted_snapshot),
            "durableAdmissionPermitDigest": permit_digest,
        },
        "expectedOutcomes": {
            "freshPairApply": {
                "disposition": "applied",
                "localRevision": 2,
                "snapshotDigest": sha256_hex(next_snapshot),
                "idempotentRetryDisposition": "idempotent",
            },
            "turnRouteBinding": {
                "contextObjectType": 18,
                "authorizationObjectType": 21,
                "transcriptObjectType": 7,
                "routeAuthDigestSource": "turnRouteAuthorization",
                "securityContextDigestSource": "preauthorizationSessionContext",
            },
            "durableAdmission": {
                "disposition": "admitted",
                "localRevision": 3,
                "snapshotDigest": sha256_hex(admitted_snapshot),
                "permitBindingDigest": permit_digest,
                "exactRetryExpected": "replay",
            },
            "codecOnly": [15, 17, 20, 22],
        },
        "mutations": [
            {"id": "reordered_tag", "target": "serviceKeyset", "mutation": "swap_tags_1_2", "expected": "malformedCanonical"},
            {"id": "trailing_byte", "target": "turnConnector", "mutation": "append_00", "expected": "malformedCanonical"},
            {"id": "high_s", "target": "serviceKeyset", "mutation": "replace_s_with_n_minus_s", "expected": "highS"},
            {"id": "non_minimal_der", "target": "routeCapability", "mutation": "prepend_redundant_integer_zero", "expected": "nonCanonicalSignature"},
            {"id": "rollback_floor", "target": "serviceKeyset", "mutation": "minimumAcceptedKeysetVersion_2", "expected": "keysetRollback"},
            {"id": "same_revision_divergent_history", "target": "pairStatus", "mutation": "alter_history_request_digest", "expected": "stateMismatch"},
            {"id": "fresh_epoch_plus_two", "target": "freshPairProof", "mutation": "nextPairEpoch_3", "expected": "invalidFreshPair"},
            {"id": "swapped_fresh_signatures", "target": "freshPairProof", "mutation": "swap_tags_35_36", "expected": "invalidSignature"},
            {"id": "reused_recovery_secret", "target": "freshPairProof", "mutation": "next_endpoint_equals_previous", "expected": "invalidFreshPair"},
            {"id": "wrong_security_context", "target": "routePlan", "mutation": "securityContextDigest_zero", "expected": "routeMismatch"},
            {"id": "wrong_route_auth_source", "target": "secureSessionTranscript", "mutation": "routeAuthDigest_context_digest", "expected": "routeMismatch"},
            {"id": "expired_plan_reuse", "target": "routePlan", "mutation": "nowMs_1020000", "expected": "expired"},
            {"id": "wrong_connector_secret", "target": "turnConnector", "mutation": "connectorSecret_first_byte_00", "expected": "routeMismatch"},
            {"id": "missing_connector_input", "target": "turnRouteAuthorization", "mutation": "omit_verified_connector_input", "expected": "routeMismatch"},
            {"id": "cross_kind_authorization", "target": "p2pRouteAuthorization", "mutation": "use_in_turn_transcript", "expected": "routeMismatch"},
            {"id": "admission_replay", "target": "admittedSnapshot", "mutation": "admit_same_session_again", "expected": "replay"},
        ],
        "reservedObjectTypes": [19],
    }


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_built_fixture(fixture: dict[str, Any]) -> None:
    keys = fixture["keys"]
    for name, key in keys.items():
        scalar = int(key["privateScalarHex"], 16)
        x963, spki, key_id = public_material(scalar)
        require(key["name"] == name, f"{name}: key name mismatch")
        require(key["publicKeyX963Hex"] == x963.hex(), f"{name}: X9.63 mismatch")
        require(key["publicKeySPKIDERHex"] == spki.hex(), f"{name}: SPKI mismatch")
        require(key["keyId"] == key_id, f"{name}: key ID mismatch")

    field_counts = {7: 21, 8: 16, 10: 11, 11: 17, 12: 36, 13: 22, 14: 15,
                    15: 11, 16: 11, 17: 11, 18: 21, 20: 10, 21: 10, 22: 10}
    for name, record in fixture["objects"].items():
        canonical = bytes.fromhex(record["expectedCanonicalHex"])
        require(record["expectedCanonicalByteCount"] == len(canonical), f"{name}: byte count mismatch")
        require(record["expectedSha256Hex"] == sha256_hex(canonical), f"{name}: digest mismatch")
        object_type = record["objectType"]
        if object_type == 9:
            count = 7 if record["input"]["transitionHistory"] else 5
        else:
            count = field_counts[object_type]
        als1_decode(canonical, object_type, count)
        signatures = record.get("signatures", [])
        if signatures:
            claims = bytes.fromhex(record["expectedClaimsCanonicalHex"])
            signed_fields = als1_decode(canonical, object_type, count)
            signature_fields = signed_fields[-len(signatures):]
            require(
                als1_encode(object_type, signed_fields[:-len(signatures)]) == claims,
                f"{name}: signed claims mismatch",
            )
            for signature_meta, signature in zip(signatures, signature_fields):
                transcript = signature_transcript(signature_meta["signingDomain"], claims)
                require(signature_meta["expectedSigningTranscriptHex"] == transcript.hex(), f"{name}: transcript mismatch")
                require(signature_meta["expectedSigningTranscriptSha256Hex"] == sha256_hex(transcript), f"{name}: transcript digest mismatch")
                require(signature_meta["fixedLowSDERSignatureHex"] == signature.hex(), f"{name}: signature field mismatch")
                ecdsa_verify(bytes.fromhex(keys[signature_meta["signer"]]["publicKeyX963Hex"]), transcript, signature)

    derived = fixture["derived"]
    require(
        fixture["objects"]["secureSessionTranscript"]["input"]["routeAuthDigest"]
        == derived["turnRouteAuthorizationDigest"],
        "object 7 routeAuthDigest must be object 21 digest",
    )
    require(
        fixture["objects"]["routePlan"]["input"]["securityContextDigest"]
        == derived["preauthorizationSessionContextDigest"],
        "object 14 securityContextDigest must be object 18 digest",
    )
    require(
        derived["freshPairTransitionRequestDigest"]
        == sha256_hex(bytes.fromhex(fixture["objects"]["freshPairProof"]["expectedClaimsCanonicalHex"])),
        "object 12 transition request digest must hash unsigned claims",
    )
    recovery = list(fixture["derived"]["previousRecoveryCommitments"].values()) + list(
        fixture["derived"]["nextRecoveryCommitments"].values()
    )
    require(len(set(recovery)) == len(recovery), "recovery commitments must be domain-separated and fresh")
    require(fixture["reservedObjectTypes"] == [19], "object 19 must remain reserved")


def validate_fixture_file(path: Path = FIXTURE) -> None:
    expected = build_fixture()
    validate_built_fixture(expected)
    require(path.exists(), f"missing fixture: {path}; run with --rewrite")
    actual_bytes = path.read_bytes()
    expected_bytes = canonical_json_bytes(expected)
    require(actual_bytes == expected_bytes, f"{path}: bytes differ; inspect drift or run explicit --rewrite")
    actual = json.loads(actual_bytes, object_pairs_hook=_reject_duplicate_keys)
    require(actual == expected, f"{path}: parsed fixture mismatch")
    validate_built_fixture(actual)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--rewrite", action="store_true", help="explicitly regenerate the fixture")
    args = parser.parse_args(argv)
    try:
        expected = build_fixture()
        validate_built_fixture(expected)
        if args.rewrite:
            args.fixture.parent.mkdir(parents=True, exist_ok=True)
            args.fixture.write_bytes(canonical_json_bytes(expected))
            print(f"rewrote {args.fixture}")
        else:
            validate_fixture_file(args.fixture)
            print(f"validated {args.fixture}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"G1a-C vector validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
