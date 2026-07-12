#!/usr/bin/env python3
"""Independently validate the shared ALP1 v1 P2P/NAT contract vectors."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "shared/protocol/fixtures/production-p2p-nat-v1-vectors.json"
SUITE = "aetherlink-p2p-v1"
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX_ANY = re.compile(r"(?:[0-9a-f]{2})+\Z")
P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
P256_A = P256_P - 3
P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
P256_G = bytes.fromhex("046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5")
P256_2G = bytes.fromhex("047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1")
MAX_FRAME_BYTES = {1: 8291, 2: 16384, 3: 404, 4: 532, 5: 300}
TTL_MILLIS = 600_000
CLOCK_SKEW_MILLIS = 30_000


class Rejection(ValueError):
    def __init__(self, rejection_class: str, message: str) -> None:
        super().__init__(message)
        self.rejection_class = rejection_class


def fail(message: str) -> None:
    raise ValueError(message)


def exact_keys(value: Any, keys: list[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or list(value) != keys:
        fail(f"{path}: expected exact ordered keys {keys}")
    return value


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON: duplicate key {key!r}")
        result[key] = value
    return result


def text(value: Any, path: str, allowed: set[str] | None = None) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 0x20 or ord(char) > 0x7E for char in value):
        fail(f"{path}: expected printable ASCII string")
    if allowed is not None and value not in allowed:
        fail(f"{path}: unexpected value {value!r}")
    return value


def hex_value(value: Any, path: str, size: int | None = None) -> bytes:
    if not isinstance(value, str) or not HEX_ANY.fullmatch(value):
        fail(f"{path}: expected non-empty canonical lowercase even-length hex")
    decoded = bytes.fromhex(value)
    if size is not None and len(decoded) != size:
        fail(f"{path}: expected {size} bytes")
    return decoded


def hex_text(value: Any, path: str, length: int) -> str:
    pattern = HEX32 if length == 32 else HEX64
    if not isinstance(value, str) or not pattern.fullmatch(value):
        fail(f"{path}: expected {length} canonical lowercase hex characters")
    return value


def uint(value: Any, path: str, bits: int, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value >= 1 << bits:
        fail(f"{path}: expected {'positive ' if positive else ''}UInt{bits}")
    return value


def p256_key(value: Any, path: str) -> bytes:
    encoded = hex_value(value, path, 65)
    require_p256_bytes(encoded, path)
    return encoded


def require_p256_bytes(encoded: bytes, path: str) -> None:
    if encoded[0] != 4:
        fail(f"{path}: expected uncompressed SEC1 point")
    x, y = int.from_bytes(encoded[1:33], "big"), int.from_bytes(encoded[33:], "big")
    if x >= P256_P or y >= P256_P or (y * y - (x * x * x + P256_A * x + P256_B)) % P256_P:
        fail(f"{path}: point is not on P-256")


def ascii_bytes(value: Any, path: str, allowed: set[str] | None = None) -> bytes:
    return text(value, path, allowed).encode("ascii")


def frame(object_type: int, fields: list[bytes]) -> bytes:
    encoded = bytearray(b"ALP1" + bytes((object_type, 1)))
    for tag, field in enumerate(fields, 1):
        encoded.extend(bytes((tag,)) + struct.pack(">I", len(field)) + field)
    return bytes(encoded)


def common_ids(value: dict[str, Any], path: str) -> tuple[bytes, bytes]:
    return (
        hex_text(value["sessionId"], f"{path}.sessionId", 32).encode("ascii"),
        hex_text(value["pairBindingDigest"], f"{path}.pairBindingDigest", 64).encode("ascii"),
    )


def candidate_batch(value: Any) -> bytes:
    path = "objects.candidateBatch.input"
    obj = exact_keys(value, ["sessionId", "generation", "sequence", "expiresAtMillis", "senderRole", "candidates"], path)
    candidates = obj["candidates"]
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 32:
        fail(f"{path}.candidates: expected 1..32 candidates")
    encoded_candidates: list[bytes] = []
    kinds = {"host": 1, "server_reflexive": 2, "peer_reflexive": 3, "relay": 4}
    families = {"ipv4": (4, 4), "ipv6": (6, 16)}
    for index, raw in enumerate(candidates):
        item_path = f"{path}.candidates[{index}]"
        item = exact_keys(raw, ["kind", "family", "port", "priority", "foundationHex", "addressHex"], item_path)
        kind = text(item["kind"], f"{item_path}.kind", set(kinds))
        family = text(item["family"], f"{item_path}.family", set(families))
        family_wire, address_size = families[family]
        encoded_candidates.append(bytes((kinds[kind], family_wire, 1)) + struct.pack(">H", uint(item["port"], f"{item_path}.port", 16, True)) + struct.pack(">I", uint(item["priority"], f"{item_path}.priority", 32)) + hex_value(item["foundationHex"], f"{item_path}.foundationHex", 8) + bytes((address_size,)) + hex_value(item["addressHex"], f"{item_path}.addressHex", address_size))
        if item["port"] < 1024:
            fail(f"{item_path}.port: ports below 1024 are forbidden")
    if len(set(encoded_candidates)) != len(encoded_candidates):
        fail(f"{path}.candidates: duplicate candidate")
    expected_order = sorted(encoded_candidates, key=lambda item: (-int.from_bytes(item[5:9], "big"), item))
    if encoded_candidates != expected_order:
        fail(f"{path}.candidates: candidates are not in canonical order")
    blob = struct.pack(">H", len(encoded_candidates)) + b"".join(encoded_candidates)
    if len(blob) > 8192:
        fail(f"{path}.candidates: candidate blob exceeds 8192 bytes")
    return frame(1, [hex_text(obj["sessionId"], f"{path}.sessionId", 32).encode("ascii"), struct.pack(">Q", uint(obj["generation"], f"{path}.generation", 64, True)), struct.pack(">Q", uint(obj["sequence"], f"{path}.sequence", 64)), struct.pack(">Q", uint(obj["expiresAtMillis"], f"{path}.expiresAtMillis", 64, True)), ascii_bytes(obj["senderRole"], f"{path}.senderRole", {"client", "runtime"}), blob])


def sealed_record(value: Any) -> bytes:
    path = "objects.sealedRouteRecord.input"
    obj = exact_keys(value, ["sessionId", "pairBindingDigest", "senderRole", "generation", "sequence", "expiresAtMillis", "antiReplayNonce", "ephemeralPublicKeyHex", "sealNonceHex", "ciphertextHex"], path)
    session, pair = common_ids(obj, path)
    ephemeral_key = p256_key(obj["ephemeralPublicKeyHex"], f"{path}.ephemeralPublicKeyHex")
    if ephemeral_key != P256_G:
        fail(f"{path}.ephemeralPublicKeyHex: expected the P-256 generator")
    encoded = frame(2, [SUITE.encode(), session, pair, ascii_bytes(obj["senderRole"], f"{path}.senderRole", {"client", "runtime"}), struct.pack(">Q", uint(obj["generation"], f"{path}.generation", 64, True)), struct.pack(">Q", uint(obj["sequence"], f"{path}.sequence", 64)), struct.pack(">Q", uint(obj["expiresAtMillis"], f"{path}.expiresAtMillis", 64, True)), hex_text(obj["antiReplayNonce"], f"{path}.antiReplayNonce", 32).encode(), ephemeral_key, hex_value(obj["sealNonceHex"], f"{path}.sealNonceHex", 12), hex_value(obj["ciphertextHex"], f"{path}.ciphertextHex")])
    if len(encoded) > 16384:
        fail(f"{path}: sealed record exceeds 16384 bytes")
    return encoded


def relay_capability(value: Any) -> bytes:
    path = "objects.relayCapability.input"
    obj = exact_keys(value, ["sessionId", "pairBindingDigest", "clientFingerprint", "runtimeFingerprint", "relayServiceDigest", "expiresAtMillis", "quotaBytes", "capabilityNonce"], path)
    session, pair = common_ids(obj, path)
    return frame(3, [SUITE.encode(), session, pair, hex_text(obj["clientFingerprint"], f"{path}.clientFingerprint", 64).encode(), hex_text(obj["runtimeFingerprint"], f"{path}.runtimeFingerprint", 64).encode(), hex_text(obj["relayServiceDigest"], f"{path}.relayServiceDigest", 64).encode(), struct.pack(">Q", uint(obj["expiresAtMillis"], f"{path}.expiresAtMillis", 64, True)), struct.pack(">Q", uint(obj["quotaBytes"], f"{path}.quotaBytes", 64, True)), hex_text(obj["capabilityNonce"], f"{path}.capabilityNonce", 32).encode()])


def identity_transcript(value: Any) -> bytes:
    path = "objects.identitySessionTranscript.input"
    obj = exact_keys(value, ["sessionId", "pairBindingDigest", "clientFingerprint", "runtimeFingerprint", "clientEphemeralKeyHex", "runtimeEphemeralKeyHex", "generation", "pathReceiptDigest", "transportContext", "fallbackReason", "protocolFloor"], path)
    session, pair = common_ids(obj, path)
    floor = uint(obj["protocolFloor"], f"{path}.protocolFloor", 32, True)
    if floor != 1:
        fail(f"{path}.protocolFloor: expected 1")
    client_key = p256_key(obj["clientEphemeralKeyHex"], f"{path}.clientEphemeralKeyHex")
    runtime_key = p256_key(obj["runtimeEphemeralKeyHex"], f"{path}.runtimeEphemeralKeyHex")
    if client_key != P256_G or runtime_key != P256_2G:
        fail(f"{path}: expected the P-256 generator and 2G keys")
    return frame(4, [SUITE.encode(), session, pair, hex_text(obj["clientFingerprint"], f"{path}.clientFingerprint", 64).encode(), hex_text(obj["runtimeFingerprint"], f"{path}.runtimeFingerprint", 64).encode(), client_key, runtime_key, struct.pack(">Q", uint(obj["generation"], f"{path}.generation", 64, True)), hex_text(obj["pathReceiptDigest"], f"{path}.pathReceiptDigest", 64).encode(), ascii_bytes(obj["transportContext"], f"{path}.transportContext", {"direct", "relay"}), ascii_bytes(obj["fallbackReason"], f"{path}.fallbackReason", {"none", "direct_failed", "consent_lost"}), struct.pack(">I", floor)])


def path_receipt(value: Any) -> bytes:
    path = "objects.pathValidationReceipt.input"
    obj = exact_keys(value, ["sessionId", "generation", "candidatePairDigest", "transportContext", "clientObservedPathDigest", "runtimeObservedPathDigest", "validatedAtMillis", "expiresAtMillis"], path)
    validated = uint(obj["validatedAtMillis"], f"{path}.validatedAtMillis", 64, True)
    expires = uint(obj["expiresAtMillis"], f"{path}.expiresAtMillis", 64, True)
    if expires <= validated:
        fail(f"{path}.expiresAtMillis: must follow validation")
    if expires - validated > TTL_MILLIS:
        fail(f"{path}.expiresAtMillis: lifetime exceeds TTL")
    return frame(5, [hex_text(obj["sessionId"], f"{path}.sessionId", 32).encode(), struct.pack(">Q", uint(obj["generation"], f"{path}.generation", 64, True)), hex_text(obj["candidatePairDigest"], f"{path}.candidatePairDigest", 64).encode(), ascii_bytes(obj["transportContext"], f"{path}.transportContext", {"direct", "relay"}), hex_text(obj["clientObservedPathDigest"], f"{path}.clientObservedPathDigest", 64).encode(), hex_text(obj["runtimeObservedPathDigest"], f"{path}.runtimeObservedPathDigest", 64).encode(), struct.pack(">Q", validated), struct.pack(">Q", expires)])


def reject(rejection_class: str, message: str) -> None:
    raise Rejection(rejection_class, message)


def parse_canonical(encoded: bytes, object_type: int, field_count: int) -> list[bytes]:
    if len(encoded) > MAX_FRAME_BYTES[object_type]:
        reject("limitExceeded", "frame exceeds pre-parse ceiling")
    if len(encoded) < 6 or encoded[:4] != b"ALP1" or encoded[4] != object_type or encoded[5] != 1:
        reject("invalidValue", "invalid canonical header")
    fields: list[bytes] = []
    offset = 6
    for expected_tag in range(1, field_count + 1):
        if offset >= len(encoded):
            reject("invalidField", "missing field")
        actual_tag = encoded[offset]
        offset += 1
        if actual_tag < expected_tag:
            reject("duplicateField", "duplicate canonical tag")
        if actual_tag > expected_tag:
            rejection_class = "invalidFieldOrder" if actual_tag <= field_count else "unknownField"
            reject(rejection_class, "out-of-order or unknown canonical tag")
        if offset + 4 > len(encoded):
            reject("invalidLength", "truncated field length")
        length = struct.unpack(">I", encoded[offset:offset + 4])[0]
        offset += 4
        if length > len(encoded) - offset:
            reject("invalidLength", "field length exceeds remaining bytes")
        fields.append(encoded[offset:offset + length])
        offset += length
    if offset != len(encoded):
        reject("trailingBytes", "trailing canonical data")
    return fields


def reject_invalid_value(callback: Callable[[], None]) -> None:
    try:
        callback()
    except ValueError as error:
        reject("invalidValue", str(error))


def validate_negative_vector(operation: str, encoded: bytes, now_millis: int | None) -> None:
    if operation == "decodeCandidateBatch":
        parse_canonical(encoded, 1, 6)
        return
    if operation == "decodeSealedRouteRecord":
        fields = parse_canonical(encoded, 2, 11)
        reject_invalid_value(lambda: require_p256_bytes(fields[8], "negative.ephemeralPublicKey"))
        return
    if operation == "decodeIdentitySessionTranscript":
        fields = parse_canonical(encoded, 4, 12)
        reject_invalid_value(lambda: require_p256_bytes(fields[5], "negative.clientEphemeralKey"))
        reject_invalid_value(lambda: require_p256_bytes(fields[6], "negative.runtimeEphemeralKey"))
        return
    if operation in {"decodePathValidationReceipt", "decodeFreshPathValidationReceipt"}:
        fields = parse_canonical(encoded, 5, 8)
        if len(fields[6]) != 8 or len(fields[7]) != 8:
            reject("invalidValue", "invalid path receipt timestamp width")
        validated, expires = struct.unpack(">Q", fields[6])[0], struct.unpack(">Q", fields[7])[0]
        if validated == 0 or expires <= validated or expires - validated > TTL_MILLIS:
            reject("invalidValue", "invalid path receipt lifetime")
        if operation == "decodeFreshPathValidationReceipt":
            if now_millis is None:
                fail("negative vector: fresh operation requires nowMillis")
            validation_upper = min((1 << 64) - 1, now_millis + CLOCK_SKEW_MILLIS)
            expiry_lower = max(0, now_millis - CLOCK_SKEW_MILLIS)
            expiry_upper = min((1 << 64) - 1, now_millis + TTL_MILLIS + CLOCK_SKEW_MILLIS)
            if validated > validation_upper or not expiry_lower < expires <= expiry_upper:
                reject("invalidValue", "path receipt is not fresh")
        return
    fail(f"negative vector: unsupported operation {operation!r}")


def check_fixture() -> None:
    root = json.loads(FIXTURE.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    exact_keys(root, ["schema", "version", "suite", "objects", "transcriptChecks", "negativeCanonicalVectors"], "root")
    if root["schema"] != "aetherlink-production-p2p-nat-v1-vectors" or root["version"] != 1 or root["suite"] != SUITE:
        fail("root: invalid schema, version, or suite")
    objects = exact_keys(root["objects"], ["candidateBatch", "sealedRouteRecord", "relayCapability", "identitySessionTranscript", "relayIdentitySessionTranscript", "maximumIdentitySessionTranscript", "pathValidationReceipt"], "objects")
    encoders: dict[str, Callable[[Any], bytes]] = {"candidateBatch": candidate_batch, "sealedRouteRecord": sealed_record, "relayCapability": relay_capability, "identitySessionTranscript": identity_transcript, "relayIdentitySessionTranscript": identity_transcript, "maximumIdentitySessionTranscript": identity_transcript, "pathValidationReceipt": path_receipt}
    encoded: dict[str, bytes] = {}
    for name, encode in encoders.items():
        keys = ["input", "expectedCanonicalByteCount", "expectedCanonicalHex"] if name in {"relayIdentitySessionTranscript", "maximumIdentitySessionTranscript"} else ["input", "expectedCanonicalHex"]
        vector = exact_keys(objects[name], keys, f"objects.{name}")
        expected = hex_value(vector["expectedCanonicalHex"], f"objects.{name}.expectedCanonicalHex")
        encoded[name] = encode(vector["input"])
        if encoded[name] != expected:
            fail(f"objects.{name}.expectedCanonicalHex: canonical bytes mismatch")
        if "expectedCanonicalByteCount" in vector and len(expected) != uint(vector["expectedCanonicalByteCount"], f"objects.{name}.expectedCanonicalByteCount", 16, True):
            fail(f"objects.{name}.expectedCanonicalByteCount: byte count mismatch")
    transcript_names = ("identitySessionTranscript", "relayIdentitySessionTranscript", "maximumIdentitySessionTranscript")
    checks_root = exact_keys(root["transcriptChecks"], list(transcript_names), "transcriptChecks")
    for name in transcript_names:
        checks = exact_keys(checks_root[name], ["confirmationKeyHex", "expectedSha256Hex", "expectedHmacSha256"], f"transcriptChecks.{name}")
        key = hex_value(checks["confirmationKeyHex"], f"transcriptChecks.{name}.confirmationKeyHex", 32)
        transcript = encoded[name]
        expected_digest = hex_value(checks["expectedSha256Hex"], f"transcriptChecks.{name}.expectedSha256Hex", 32)
        if hashlib.sha256(transcript).digest() != expected_digest:
            fail(f"transcriptChecks.{name}.expectedSha256Hex: digest mismatch")
        macs = exact_keys(checks["expectedHmacSha256"], ["client", "runtime"], f"transcriptChecks.{name}.expectedHmacSha256")
        for role in ("client", "runtime"):
            expected = hex_value(macs[role], f"transcriptChecks.{name}.expectedHmacSha256.{role}", 32)
            message = transcript + f"{SUITE}:key-confirmation:{role}".encode("ascii")
            if hmac.new(key, message, hashlib.sha256).digest() != expected:
                fail(f"transcriptChecks.{name}.expectedHmacSha256.{role}: HMAC mismatch")
    negatives = root["negativeCanonicalVectors"]
    if not isinstance(negatives, list) or len(negatives) != 9:
        fail("negativeCanonicalVectors: expected exactly 9 vectors")
    seen_ids: set[str] = set()
    allowed_classes = {"invalidValue", "duplicateField", "invalidFieldOrder", "trailingBytes", "limitExceeded"}
    for index, raw in enumerate(negatives):
        path = f"negativeCanonicalVectors[{index}]"
        has_now = isinstance(raw, dict) and "nowMillis" in raw
        keys = ["id", "operation", "nowMillis", "canonicalHex", "expectedRejectionClass"] if has_now else ["id", "operation", "canonicalHex", "expectedRejectionClass"]
        vector = exact_keys(raw, keys, path)
        vector_id = text(vector["id"], f"{path}.id")
        if vector_id in seen_ids:
            fail(f"{path}.id: duplicate vector id")
        seen_ids.add(vector_id)
        operation = text(vector["operation"], f"{path}.operation")
        expected_class = text(vector["expectedRejectionClass"], f"{path}.expectedRejectionClass", allowed_classes)
        now_millis = uint(vector["nowMillis"], f"{path}.nowMillis", 64, True) if has_now else None
        try:
            validate_negative_vector(operation, hex_value(vector["canonicalHex"], f"{path}.canonicalHex"), now_millis)
        except Rejection as rejection:
            if rejection.rejection_class != expected_class:
                fail(f"{path}: expected {expected_class}, independently classified {rejection.rejection_class}")
        else:
            fail(f"{path}: vector was accepted")


def check_no_network_sources() -> None:
    roots = [
        ROOT / "apps/android/core/protocol/src/main/java/com/localagentbridge/android/core/protocol/p2pnat",
        ROOT / "apps/android/core/transport/src/main/java/com/localagentbridge/android/core/transport/p2pnat",
        ROOT / "apps/macos/P2PNATContracts/Sources",
        ROOT / "apps/macos/P2PNATConformance/Sources",
    ]
    forbidden = {
        "route token": re.compile(r"(?<![A-Za-z0-9_])route(?:token|_token|-token)(?![A-Za-z0-9_])", re.IGNORECASE),
        "Java network API": re.compile(r"(?:^\s*import\s+java\.net(?:\.|\s*$)|\bjava\.net\.|\b(?:InetAddress|Socket|ServerSocket|DatagramSocket|DatagramPacket|SocketFactory|SSLSocketFactory)\b|\.(?:getByName|getAllByName|getHostName|createSocket)\s*\()", re.MULTILINE),
        "Java NIO channel API": re.compile(r"(?:^\s*import\s+java\.nio\.channels\.(?:SocketChannel|DatagramChannel)\s*$|\bjava\.nio\.channels\.(?:SocketChannel|DatagramChannel)\b|\b(?:SocketChannel|DatagramChannel)\b)", re.MULTILINE),
        "Android HTTP client library": re.compile(r"(?:^\s*import\s+(?:okhttp3|io\.ktor\.client|retrofit2|org\.apache\.http|java\.net\.http)(?:\.|\s*$)|\b(?:OkHttpClient|HttpClient|Retrofit|HttpURLConnection|WebSocket)\b)", re.MULTILINE),
        "Apple URL loading or Network framework": re.compile(r"(?:^\s*import\s+Network\s*$|\bURLSession\b|\bNW(?:Connection|Listener|Endpoint|Parameters|Path|Browser|Protocol)\b)", re.MULTILINE),
        "Apple CFStream socket API": re.compile(r"\bCFStreamCreatePairWithSocket(?:ToHost|ToCFHost|ToNetService)?\b"),
        "Swift URL-backed loading": re.compile(r"(?:\bURL\s*\(\s*string\s*:|\b(?:Data|String)(?:\.init)?\s*\(\s*contentsOf\s*:\s*(?:URL\s*\(|[A-Za-z_][A-Za-z0-9_]*))"),
        "Swift HTTP client library": re.compile(r"(?:^\s*import\s+(?:AsyncHTTPClient|Alamofire|NIOHTTP1|NIOWebSocket)\s*$|\b(?:HTTPClient|AF\.request|WebSocketTask)\b)", re.MULTILINE),
        "POSIX socket API": re.compile(r"(?<![A-Za-z0-9_])(?:(?:Darwin|Glibc)\.)?(?:socket|connect)\s*\("),
        "hostname or DNS API": re.compile(r"\b(?:getaddrinfo|CFHost|NSHost|DNSService[A-Za-z]*)\b"),
        "ICE/STUN/TURN implementation": re.compile(r"\b(?:ICE|STUN|TURN)\b", re.IGNORECASE),
    }
    coverage_examples = {
        "Java network API": [
            "SocketFactory.getDefault().createSocket(host, port)",
        ],
        "Android HTTP client library": [
            "import okhttp3.OkHttpClient",
            "import io.ktor.client.HttpClient",
        ],
        "Swift URL-backed loading": [
            "let body = try Data(contentsOf: endpoint)",
            "let body = try Data.init(contentsOf: endpoint)",
            "let text = try String.init(contentsOf: endpoint)",
        ],
        "Apple CFStream socket API": [
            "CFStreamCreatePairWithSocketToHost(nil, host, port, &input, &output)",
        ],
    }
    for label, examples in coverage_examples.items():
        for example in examples:
            if not forbidden[label].search(example):
                fail(f"no-network pattern coverage regression: {label}: {example}")
    for root in roots:
        if not root.is_dir():
            fail(f"missing production source directory: {root.relative_to(ROOT)}")
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.suffix in {".kt", ".swift"}):
            source = path.read_text(encoding="utf-8")
            for label, pattern in forbidden.items():
                match = pattern.search(source)
                if match:
                    line = source.count("\n", 0, match.start()) + 1
                    fail(f"{path.relative_to(ROOT)}:{line}: forbidden {label} usage")


def main() -> int:
    try:
        check_fixture()
        check_no_network_sources()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"P2P/NAT contract vector check failed: {error}", file=sys.stderr)
        return 1
    print("P2P/NAT contract vectors passed (7 ALP1 objects; 9 negative vectors; no network APIs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
