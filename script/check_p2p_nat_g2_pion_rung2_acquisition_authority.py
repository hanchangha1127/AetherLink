#!/usr/bin/env python3
"""Validate G2 Pion rung-two provenance and one-use acquisition authority.

This validator is deliberately offline. It authenticates the recorded Go
checksum-database tree and inclusion proof, pins the exact pre-acquisition
state, and never performs source acquisition, compilation, or Git writes.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
RUNG_ONE_ROOT = (
    ROOT
    / "docs/security-hardening/production-p2p-nat-v1"
    / "g2-pion-restricted-fork-v1"
)
RUNG_TWO_ROOT = RUNG_ONE_ROOT / "rung-two"

PROFILE_PATH = RUNG_ONE_ROOT / "restricted-fork-profile.json"
RUNG_ONE_MANIFEST_PATH = RUNG_ONE_ROOT / "evidence-manifest-v1.json"
PROVENANCE_PATH = RUNG_TWO_ROOT / "provenance-observation-v1.json"
DECISION_PATH = RUNG_TWO_ROOT / "source-acquisition-decision-v1.json"
DECISION_MARKDOWN_PATH = RUNG_TWO_ROOT / "source-acquisition-decision-v1.md"
PROGRESS_PATH = RUNG_TWO_ROOT / "source-acquisition-progress-v1.json"
EVIDENCE_MANIFEST_PATH = RUNG_TWO_ROOT / "evidence-manifest-v2.json"
CANONICAL_DOC_SUPERSESSION_PATH = (
    RUNG_TWO_ROOT / "canonical-document-supersession-v1.json"
)
CANONICAL_DOC_SUPERSESSION_V2_PATH = (
    RUNG_TWO_ROOT / "canonical-document-supersession-v2.json"
)
CANONICAL_SYNC_MANIFEST_V4_PATH = RUNG_TWO_ROOT / "evidence-manifest-v4.json"

EXPECTED_RAW_SHA256 = {
    PROFILE_PATH: "10e9436ae9b8f24c4447d12f8087b4f121810841ae33526e08fcc3d862d60a0f",
    RUNG_ONE_MANIFEST_PATH: "98e0e53955e21a833fe19852ce00f64df2dc808506bdb222c9b8a20bc8006d00",
    PROVENANCE_PATH: "6b0b55023849480c0a7ea05449b98cc2e27d9fd1d704c794aace9e04d0afe4f0",
    DECISION_PATH: "8a7ec91354b27ffc4cdf8dcce2f6baa93a10dfadfd7c896266ce42b1ae854c10",
    DECISION_MARKDOWN_PATH: "1c14cfd54cb0e4c5cec647b9cb42a9f9352e8809556e74a7a27c163e047ebb72",
    PROGRESS_PATH: "25b00486c80a6a769be0ab25ad8a7d2e5f27652f5799682892de0561a10ca2cd",
    EVIDENCE_MANIFEST_PATH: "46437bbfcb99c852009f03dbe8736aa95399ee1b053b517a3ab8c00dc796d445",
    CANONICAL_DOC_SUPERSESSION_PATH: "51b1eb43a6b57441ddcb307d37db86420cea9932ea89e316c50730215bf4d816",
    CANONICAL_DOC_SUPERSESSION_V2_PATH: "3a2b74ecde45b69204b9687904a4f88d731dfc532046e472ec22a4873765309a",
}

EXPECTED_SEMANTIC_SHA256 = {
    PROFILE_PATH: "9c929d186eedb10cc890d5540597724d6df1d719f174ed1965c79e4d50324be6",
    PROVENANCE_PATH: "8245170900e1c19cea0df7b65d641f3a74d7d6db85392216b7ad4f20da17a5e1",
    DECISION_PATH: "e49f17012acc8f6a3663311bc89074de309a4a174f9032909f87bd0fa9404eed",
    PROGRESS_PATH: "92592186087c211560bfc021aea423f5380d9d09aedddaa937e62276ef771c33",
    EVIDENCE_MANIFEST_PATH: "8934d039a8f73c58872de9cfe74b118a8f0b88a5701412b1611aaa0212dc4b09",
    CANONICAL_DOC_SUPERSESSION_PATH: "f33ffd58ca37a7a3d604281d328344c7081c9fd80ce8d64e5d1280ba9e40d6c2",
    CANONICAL_DOC_SUPERSESSION_V2_PATH: "1c1245ceb52e0f2b90fcd89934b02fedaf3985466b4e4b53d9c1821d85921932",
}

RUNG_ONE_COLLECTION_SHA256 = (
    "9e395c4c4f7f61a4810d47cf96ff57b47c1908c73ea459181f1c06f26a35d704"
)
RUNG_TWO_COLLECTION_SHA256 = (
    "cf0a8773a7b78f6f41be7c6b475660136f376d0f39524a1d5fc11eb72f7397ee"
)

MODULE_PATH = "github.com/pion/ice/v4"
MODULE_VERSION = "v4.3.0"
MODULE_VERSION_ID = f"{MODULE_PATH}@{MODULE_VERSION}"
REPOSITORY_URL = "https://github.com/pion/ice"
COMMIT = "1e8716372f2bb52e45bf2a7172e4fb1004251c46"
TREE = "df59c87a634cfea261582cd9932554663112a975"
SOURCE_URL = "https://proxy.golang.org/github.com/pion/ice/v4/@v/v4.3.0.zip"
SOURCE_HOST = "proxy.golang.org"
SOURCE_PATH = "/github.com/pion/ice/v4/@v/v4.3.0.zip"
OUTPUT_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
RAW_ARCHIVE_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
MODULE_H1 = "h1:X8l4s9zV2HeTKX33nulWAFXAEo5KhIVzOsY62/3t/LM="
GO_MOD_H1 = "h1:obAyD+J+Hzs7QA7Y8YXHp5uIn6gb7z87pKedXZkrcFU="

SUMDB_VERIFIER_KEY = (
    "sum.golang.org+033de0ae+"
    "Ac4zctda0e5eza+HJyk9SxEdh+s3Ux18htTTAD8OuAn8"
)
SUMDB_RECORD_NUMBER = 57312466
SUMDB_TREE_SIZE = 57871495
SUMDB_ROOT_HASH_BASE64 = "CXAe1gevwtmEqZ3aCCTvv6+nJY5F29T4UGHfB73rJTo="
SUMDB_SIGNATURE_BASE64 = (
    "Az3grl3EvFerct68O5eNpkq2v5oVwQN6i7f9wO42XflhUmA6BqeLeAxOBU8DSuxB3yTRtGL8ithf0vSqbu5PqDWnYAs="
)
SUMDB_RECORD_HASH_BASE64 = "gJpj337cdtVFcrcLfZnDSqUzErcx0jdwOvIdZPZqDOw="
SUMDB_SIGNED_TREE_TEXT_SHA256 = (
    "5192e92f2cbd4744e25a15c8617b86057400f8828d32b27e9efcf1b90bc65b45"
)
SUMDB_LOOKUP_RAW_SHA256 = (
    "7b445772a66ae3e1615210a65f1bf3495080c833e96afe0c29cd9f2b115e4d82"
)

PROVENANCE_TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "observationId", "recordedDate", "status",
    "evidenceClass", "parentRungOne", "upstreamIdentity",
    "githubCommitSignatureObservation", "goProxyZipObservation",
    "goChecksumObservation", "checksumDatabaseObservation", "executionBoundary",
    "crossFileHashBindings",
}
DECISION_TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "decisionId", "recordedDate", "status",
    "result", "nextAction", "parentRungOne", "provenanceObservation",
    "sourceIdentity", "provenancePolicy", "acquisitionPermit",
    "requiredPostAcquisitionChecks", "rollback", "executionBoundary",
    "crossFileHashBindings",
}
PROGRESS_TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "progressId", "recordedDate", "status",
    "result", "nextAction", "decisionBinding", "provenanceBinding",
    "expectedArchive", "permitState", "requestObservation",
    "verificationObservation", "artifactObservation", "executionBoundary",
}
MANIFEST_TOP_LEVEL_KEYS = {
    "documentType", "schemaVersion", "decisionId", "recordedDate",
    "orderingRule", "collectionDigestAlgorithm", "artifactCount", "artifacts",
    "collectionSha256", "sourceAcquisitionExecuted",
    "externalIdentityProofRequired", "userActionRequired",
}

EXPECTED_MANIFEST_ROWS = (
    (
        "G2R2E001",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/restricted-fork-profile.json",
        EXPECTED_RAW_SHA256[PROFILE_PATH],
        "immutable_rung_one_profile_predecessor",
    ),
    (
        "G2R2E002",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/evidence-manifest-v1.json",
        EXPECTED_RAW_SHA256[RUNG_ONE_MANIFEST_PATH],
        "immutable_rung_one_evidence_predecessor",
    ),
    (
        "G2R2E003",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/provenance-observation-v1.json",
        EXPECTED_RAW_SHA256[PROVENANCE_PATH],
        "signed_sumdb_tree_and_record_inclusion_provenance",
    ),
    (
        "G2R2E004",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/source-acquisition-decision-v1.json",
        EXPECTED_RAW_SHA256[DECISION_PATH],
        "one_use_exact_archive_acquisition_decision",
    ),
    (
        "G2R2E005",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/source-acquisition-decision-v1.md",
        EXPECTED_RAW_SHA256[DECISION_MARKDOWN_PATH],
        "human_readable_rung_two_decision",
    ),
    (
        "G2R2E006",
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/source-acquisition-progress-v1.json",
        EXPECTED_RAW_SHA256[PROGRESS_PATH],
        "authorized_not_consumed_zero_request_progress",
    ),
)


class RungTwoValidationError(ValueError):
    """Raised when a rung-two authority artifact fails closed."""


def fail(message: str) -> None:
    raise RungTwoValidationError(message)


def reject_duplicate_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object contains duplicate name {key!r}")
        result[key] = value
    return result


def reject_non_finite_constant(value: str) -> None:
    fail(f"JSON contains non-finite numeric constant {value!r}")


def parse_json(raw: str) -> Any:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_names,
            parse_constant=reject_non_finite_constant,
        )
    except RungTwoValidationError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid JSON: {error}")
    reject_non_finite_values(value)
    return value


def reject_non_finite_values(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        fail(f"{path} contains a non-finite number")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                fail(f"{path} contains a non-string object name")
            reject_non_finite_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_non_finite_values(child, f"{path}[{index}]")


def load_json(path: Path) -> dict[str, Any]:
    try:
        raw = secure_read_bytes(path).decode("utf-8")
    except (OSError, UnicodeError) as error:
        fail(f"unable to read {path.relative_to(ROOT)}: {error}")
    value = parse_json(raw)
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain one JSON object")
    return value


def secure_repo_file_descriptor(path: Path) -> int:
    """Open one repo-owned, single-link regular file without following symlinks."""

    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        fail(f"security evidence path is outside the repository: {path}")
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        fail(f"security evidence path is noncanonical: {relative}")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    directory_flags |= getattr(os, "O_CLOEXEC", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    file_flags |= getattr(os, "O_NOFOLLOW", 0)

    directory_fd = -1
    file_fd = -1
    try:
        directory_fd = os.open(ROOT, directory_flags)
        for index, component in enumerate(parts[:-1]):
            metadata = os.fstat(directory_fd)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o022
            ):
                fail(
                    f"security evidence ancestor before {component!r} must be an "
                    "owner-controlled non-writable directory"
                )
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        ancestor = os.fstat(directory_fd)
        if (
            not stat.S_ISDIR(ancestor.st_mode)
            or ancestor.st_uid != os.getuid()
            or ancestor.st_mode & 0o022
        ):
            fail("security evidence leaf directory is not owner-controlled")
        file_fd = os.open(parts[-1], file_flags, dir_fd=directory_fd)
        leaf = os.fstat(file_fd)
        if (
            not stat.S_ISREG(leaf.st_mode)
            or leaf.st_uid != os.getuid()
            or leaf.st_nlink != 1
            or leaf.st_mode & 0o022
        ):
            fail(
                f"{relative.as_posix()} must be one owner-controlled, single-link "
                "regular file"
            )
        result = file_fd
        file_fd = -1
        return result
    except RungTwoValidationError:
        raise
    except OSError as error:
        fail(f"unable to securely open {relative.as_posix()}: {error}")
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if directory_fd >= 0:
            os.close(directory_fd)


def secure_read_bytes(path: Path, maximum_bytes: int = 16 * 1024 * 1024) -> bytes:
    file_fd = secure_repo_file_descriptor(path)
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = os.read(file_fd, 64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                fail(
                    f"{path.relative_to(ROOT)} exceeds the {maximum_bytes}-byte "
                    "evidence read ceiling"
                )
            chunks.append(chunk)
    except OSError as error:
        fail(f"unable to read {path.relative_to(ROOT)}: {error}")
    finally:
        os.close(file_fd)
    return b"".join(chunks)


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(secure_read_bytes(path)).hexdigest()


def semantic_sha256(value: Any) -> str:
    reject_non_finite_values(value)
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        fail(f"value cannot be represented as strict JSON: {error}")
    return hashlib.sha256(payload).hexdigest()


def require_exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        fail(f"{path} schema mismatch; missing={missing}, unknown={unknown}")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{path} must be an array")
    return value


def require_exact_type(value: Any, expected_type: type, path: str) -> None:
    if type(value) is not expected_type:
        fail(f"{path} must be {expected_type.__name__}, got {type(value).__name__}")


def require_equal(actual: Any, expected: Any, path: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        fail(f"{path} must equal {expected!r}, got {actual!r}")


def require_hex(value: Any, length: int, path: str) -> str:
    require_exact_type(value, str, path)
    if len(value) != length or re.fullmatch(r"[0-9a-f]+", value) is None:
        fail(f"{path} must be exactly {length} lowercase hexadecimal characters")
    return value


def require_semantic_hash(value: Any, expected: str, path: str) -> None:
    observed = semantic_sha256(value)
    if observed != expected:
        fail(f"{path} semantic SHA-256 mismatch: expected {expected}, got {observed}")


def require_safe_repo_relative_path(value: Any, path: str) -> str:
    require_exact_type(value, str, path)
    if not value or len(value.encode("utf-8")) > 1024:
        fail(f"{path} must be a non-empty path no longer than 1024 UTF-8 bytes")
    if "\\" in value or "\x00" in value or value.startswith("/"):
        fail(f"{path} is not a safe repo-relative POSIX path")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        fail(f"{path} contains an empty, dot, or parent segment")
    if any(len(segment.encode("utf-8")) > 255 for segment in segments):
        fail(f"{path} contains an overlong segment")
    if str(PurePosixPath(value)) != value:
        fail(f"{path} is not canonical POSIX syntax")
    return value


def require_exact_source_url(value: Any, path: str) -> None:
    require_equal(value, SOURCE_URL, path)
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != SOURCE_HOST:
        fail(f"{path} must use the exact HTTPS host without an explicit port")
    if parsed.hostname != SOURCE_HOST or parsed.port is not None:
        fail(f"{path} contains a noncanonical host or port")
    if parsed.username is not None or parsed.password is not None:
        fail(f"{path} must not contain user information")
    if parsed.path != SOURCE_PATH or unquote(parsed.path) != parsed.path:
        fail(f"{path} contains a noncanonical or percent-encoded path")
    if parsed.query or parsed.fragment:
        fail(f"{path} must not contain a query or fragment")


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def verify_file_shape_and_hash(path: Path, expected_sha256: str) -> None:
    observed = raw_sha256(path)
    if observed != expected_sha256:
        fail(
            f"{path.relative_to(ROOT)} byte SHA-256 mismatch: "
            f"expected {expected_sha256}, got {observed}"
        )


def verify_pretty_json_bytes(path: Path, document: Any) -> None:
    try:
        observed = secure_read_bytes(path)
    except OSError as error:
        fail(f"unable to read {path.relative_to(ROOT)}: {error}")
    expected = canonical_json_bytes(document)
    if observed != expected:
        fail(f"{path.relative_to(ROOT)} must use canonical two-space JSON plus final LF")


def decode_base64_canonical(value: Any, expected_length: int, path: str) -> bytes:
    require_exact_type(value, str, path)
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        fail(f"{path} is not strict standard Base64: {error}")
    if len(decoded) != expected_length:
        fail(f"{path} must decode to {expected_length} bytes, got {len(decoded)}")
    if base64.b64encode(decoded).decode("ascii") != value:
        fail(f"{path} is not canonically padded Base64")
    return decoded


# Minimal, dependency-free Ed25519 verifier for the fixed public SumDB note.
# It rejects noncanonical points, negative zero, non-prime-subgroup points, and
# small-order inputs before checking the RFC 8032 verification equation.
ED25519_Q = 2**255 - 19
ED25519_L = 2**252 + 27742317777372353535851937790883648493


def ed25519_inverse(value: int) -> int:
    return pow(value, ED25519_Q - 2, ED25519_Q)


ED25519_D = (-121665 * ed25519_inverse(121666)) % ED25519_Q
ED25519_I = pow(2, (ED25519_Q - 1) // 4, ED25519_Q)
Ed25519Point = tuple[int, int]
ED25519_IDENTITY: Ed25519Point = (0, 1)


def ed25519_recover_x(y_coordinate: int) -> int:
    numerator = (y_coordinate * y_coordinate - 1) % ED25519_Q
    denominator = (ED25519_D * y_coordinate * y_coordinate + 1) % ED25519_Q
    if denominator == 0:
        fail("Ed25519 point has a zero denominator")
    xx = numerator * ed25519_inverse(denominator) % ED25519_Q
    x_coordinate = pow(xx, (ED25519_Q + 3) // 8, ED25519_Q)
    if (x_coordinate * x_coordinate - xx) % ED25519_Q != 0:
        x_coordinate = x_coordinate * ED25519_I % ED25519_Q
    if (x_coordinate * x_coordinate - xx) % ED25519_Q != 0:
        fail("Ed25519 point does not have a square-root x coordinate")
    if x_coordinate & 1:
        x_coordinate = ED25519_Q - x_coordinate
    return x_coordinate


def ed25519_add(left: Ed25519Point, right: Ed25519Point) -> Ed25519Point:
    x1, y1 = left
    x2, y2 = right
    product = ED25519_D * x1 * x2 * y1 * y2 % ED25519_Q
    denominator_x = (1 + product) % ED25519_Q
    denominator_y = (1 - product) % ED25519_Q
    if denominator_x == 0 or denominator_y == 0:
        fail("Ed25519 point addition encountered a zero denominator")
    return (
        (x1 * y2 + x2 * y1) * ed25519_inverse(denominator_x) % ED25519_Q,
        (y1 * y2 + x1 * x2) * ed25519_inverse(denominator_y) % ED25519_Q,
    )


def ed25519_scalar_multiply(scalar: int, point: Ed25519Point) -> Ed25519Point:
    result = ED25519_IDENTITY
    addend = point
    while scalar:
        if scalar & 1:
            result = ed25519_add(result, addend)
        addend = ed25519_add(addend, addend)
        scalar >>= 1
    return result


ED25519_BASE_Y = 4 * ed25519_inverse(5) % ED25519_Q
ED25519_BASE: Ed25519Point = (
    ed25519_recover_x(ED25519_BASE_Y),
    ED25519_BASE_Y,
)


def ed25519_encode_point(point: Ed25519Point) -> bytes:
    x_coordinate, y_coordinate = point
    encoded = y_coordinate | ((x_coordinate & 1) << 255)
    return encoded.to_bytes(32, "little")


def ed25519_decode_point(encoded: bytes, path: str) -> Ed25519Point:
    if len(encoded) != 32:
        fail(f"{path} must contain one 32-byte encoded point")
    y_with_sign = int.from_bytes(encoded, "little")
    sign_bit = y_with_sign >> 255
    y_coordinate = y_with_sign & ((1 << 255) - 1)
    if y_coordinate >= ED25519_Q:
        fail(f"{path} has a noncanonical y coordinate")
    x_coordinate = ed25519_recover_x(y_coordinate)
    if (x_coordinate & 1) != sign_bit:
        x_coordinate = ED25519_Q - x_coordinate
    if x_coordinate == 0 and sign_bit == 1:
        fail(f"{path} encodes negative zero")
    point = (x_coordinate, y_coordinate)
    if ed25519_encode_point(point) != encoded:
        fail(f"{path} is not a canonical point encoding")
    if point == ED25519_IDENTITY:
        fail(f"{path} must not be the identity point")
    if ed25519_scalar_multiply(ED25519_L, point) != ED25519_IDENTITY:
        fail(f"{path} is not in the prime-order subgroup")
    if ed25519_scalar_multiply(8, point) == ED25519_IDENTITY:
        fail(f"{path} is a small-order point")
    return point


def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> None:
    if len(public_key) != 32 or len(signature) != 64:
        fail("Ed25519 public key/signature length is invalid")
    encoded_r = signature[:32]
    scalar_s = int.from_bytes(signature[32:], "little")
    if scalar_s >= ED25519_L:
        fail("Ed25519 signature scalar S is noncanonical")
    point_r = ed25519_decode_point(encoded_r, "sumdb.signature.R")
    point_a = ed25519_decode_point(public_key, "sumdb.verifierKey.publicKey")
    challenge = int.from_bytes(
        hashlib.sha512(encoded_r + public_key + message).digest(), "little"
    ) % ED25519_L
    left = ed25519_scalar_multiply(scalar_s, ED25519_BASE)
    right = ed25519_add(point_r, ed25519_scalar_multiply(challenge, point_a))
    if left != right:
        fail("sumdb signed-tree Ed25519 signature verification failed")


def rfc6962_leaf_hash(payload: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + payload).digest()


def rfc6962_node_hash(left: bytes, right: bytes) -> bytes:
    if len(left) != 32 or len(right) != 32:
        fail("RFC 6962 node inputs must each be 32 bytes")
    return hashlib.sha256(b"\x01" + left + right).digest()


def verify_rfc6962_inclusion(
    leaf_payload: bytes,
    leaf_index: int,
    tree_size: int,
    proof: Sequence[bytes],
    expected_root: bytes,
) -> None:
    if type(leaf_index) is not int or type(tree_size) is not int:
        fail("RFC 6962 leaf index and tree size must be integers, not booleans")
    if tree_size <= 0 or not 0 <= leaf_index < tree_size:
        fail("RFC 6962 leaf index is outside the signed tree")
    if len(expected_root) != 32:
        fail("RFC 6962 expected root must be 32 bytes")
    if any(len(item) != 32 for item in proof):
        fail("each RFC 6962 proof element must be 32 bytes")

    fn = leaf_index
    sn = tree_size - 1
    root = rfc6962_leaf_hash(leaf_payload)
    for proof_index, sibling in enumerate(proof):
        if sn == 0:
            fail(f"RFC 6962 proof contains an extra element at index {proof_index}")
        if (fn & 1) == 1 or fn == sn:
            root = rfc6962_node_hash(sibling, root)
            while fn != 0 and (fn & 1) == 0:
                fn >>= 1
                sn >>= 1
        else:
            root = rfc6962_node_hash(root, sibling)
        fn >>= 1
        sn >>= 1
    if sn != 0:
        fail("RFC 6962 proof ended before the signed tree root was reached")
    if fn != 0:
        fail("RFC 6962 proof left a nonzero leaf index")
    if root != expected_root:
        fail("RFC 6962 inclusion proof root does not match the signed tree")


def expected_sumdb_record_bytes() -> bytes:
    return (
        f"{MODULE_PATH} {MODULE_VERSION} {MODULE_H1}\n"
        f"{MODULE_PATH} {MODULE_VERSION}/go.mod {GO_MOD_H1}\n"
    ).encode("utf-8")


def expected_signed_tree_bytes() -> bytes:
    return (
        "go.sum database tree\n"
        f"{SUMDB_TREE_SIZE}\n"
        f"{SUMDB_ROOT_HASH_BASE64}\n"
    ).encode("utf-8")


def verify_sumdb_evidence(provenance: Mapping[str, Any]) -> None:
    checksum = provenance["checksumDatabaseObservation"]
    require_equal(checksum["verifierKey"], SUMDB_VERIFIER_KEY, "provenance.checksum.verifierKey")
    require_equal(checksum["recordNumber"], SUMDB_RECORD_NUMBER, "provenance.checksum.recordNumber")
    require_equal(checksum["recordHashBase64"], SUMDB_RECORD_HASH_BASE64, "provenance.checksum.recordHash")
    require_equal(checksum["lookupRawSha256"], SUMDB_LOOKUP_RAW_SHA256, "provenance.checksum.lookupRawSha256")

    key_match = re.fullmatch(r"([^+]+)\+([0-9a-f]{8})\+(.+)", SUMDB_VERIFIER_KEY)
    if key_match is None:
        fail("fixed sumdb verifier key has invalid note syntax")
    verifier_name, verifier_hash_hex, verifier_payload_base64 = key_match.groups()
    try:
        verifier_key_payload = base64.b64decode(verifier_payload_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        fail(f"fixed sumdb verifier key payload is invalid: {error}")
    if base64.b64encode(verifier_key_payload).decode("ascii") != verifier_payload_base64:
        fail("fixed sumdb verifier key payload is not canonical Base64")
    if len(verifier_key_payload) != 33 or verifier_key_payload[0] != 1:
        fail("sumdb verifier key must be a 33-byte Ed25519 note key")
    expected_key_hash = hashlib.sha256(
        verifier_name.encode("utf-8") + b"\n" + verifier_key_payload
    ).digest()[:4]
    if expected_key_hash.hex() != verifier_hash_hex:
        fail("sumdb verifier-key hash does not match its public key payload")

    signed_tree = checksum["signedTree"]
    require_equal(signed_tree["treeSize"], SUMDB_TREE_SIZE, "provenance.checksum.signedTree.treeSize")
    require_equal(signed_tree["rootHashBase64"], SUMDB_ROOT_HASH_BASE64, "provenance.checksum.signedTree.root")
    require_equal(signed_tree["signatureBase64"], SUMDB_SIGNATURE_BASE64, "provenance.checksum.signedTree.signature")
    require_equal(
        signed_tree["signedTreeTextSha256"],
        SUMDB_SIGNED_TREE_TEXT_SHA256,
        "provenance.checksum.signedTree.textSha256",
    )
    signed_tree_payload = expected_signed_tree_bytes()
    if hashlib.sha256(signed_tree_payload).hexdigest() != SUMDB_SIGNED_TREE_TEXT_SHA256:
        fail("sumdb signed-tree text SHA-256 did not recompute")
    root_hash = decode_base64_canonical(
        signed_tree["rootHashBase64"], 32, "provenance.checksum.signedTree.root"
    )
    note_signature = decode_base64_canonical(
        signed_tree["signatureBase64"], 68, "provenance.checksum.signedTree.signature"
    )
    if note_signature[:4] != expected_key_hash:
        fail("sumdb note signature key hash does not match the verifier key")
    verify_ed25519(verifier_key_payload[1:], signed_tree_payload, note_signature[4:])

    record_payload = expected_sumdb_record_bytes()
    expected_record_hash = decode_base64_canonical(
        checksum["recordHashBase64"], 32, "provenance.checksum.recordHash"
    )
    if rfc6962_leaf_hash(record_payload) != expected_record_hash:
        fail("sumdb record leaf hash did not recompute from the exact go.sum lines")

    inclusion = checksum["inclusionProof"]
    require_equal(inclusion["recordNumber"], SUMDB_RECORD_NUMBER, "provenance.checksum.proof.recordNumber")
    require_equal(inclusion["treeSize"], SUMDB_TREE_SIZE, "provenance.checksum.proof.treeSize")
    proof_values = require_list(inclusion["proofHashesBase64"], "provenance.checksum.proof.hashes")
    if len(proof_values) != 25:
        fail(f"sumdb inclusion proof must contain exactly 25 hashes, got {len(proof_values)}")
    proof_hashes = [
        decode_base64_canonical(value, 32, f"provenance.checksum.proof.hashes[{index}]")
        for index, value in enumerate(proof_values)
    ]
    verify_rfc6962_inclusion(
        record_payload,
        SUMDB_RECORD_NUMBER,
        SUMDB_TREE_SIZE,
        proof_hashes,
        root_hash,
    )


def validate_parent_rung_one(parent: Any, *, decision_form: bool) -> None:
    expected_keys = {
        "profilePath", "profileSha256", "profileSemanticSha256",
        "evidenceManifestPath", "evidenceManifestSha256",
        "evidenceCollectionSha256",
    }
    if decision_form:
        expected_keys |= {"requiredStatus", "requiredResult", "requiredNextAction"}
        status_key, result_key, action_key = "requiredStatus", "requiredResult", "requiredNextAction"
    else:
        expected_keys |= {"status", "result", "nextAction"}
        status_key, result_key, action_key = "status", "result", "nextAction"
    parent = require_exact_keys(parent, expected_keys, "parentRungOne")
    require_equal(
        parent["profilePath"],
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/restricted-fork-profile.json",
        "parentRungOne.profilePath",
    )
    require_equal(parent["profileSha256"], EXPECTED_RAW_SHA256[PROFILE_PATH], "parentRungOne.profileSha256")
    require_equal(parent["profileSemanticSha256"], EXPECTED_SEMANTIC_SHA256[PROFILE_PATH], "parentRungOne.profileSemanticSha256")
    require_equal(
        parent["evidenceManifestPath"],
        "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/evidence-manifest-v1.json",
        "parentRungOne.evidenceManifestPath",
    )
    require_equal(parent["evidenceManifestSha256"], EXPECTED_RAW_SHA256[RUNG_ONE_MANIFEST_PATH], "parentRungOne.evidenceManifestSha256")
    require_equal(parent["evidenceCollectionSha256"], RUNG_ONE_COLLECTION_SHA256, "parentRungOne.evidenceCollectionSha256")
    require_equal(parent[status_key], "rung1_profile_complete_candidate_not_selected", f"parentRungOne.{status_key}")
    require_equal(parent[result_key], "pion_restricted_fork_profile_ready_for_rung2_decision_only", f"parentRungOne.{result_key}")
    require_equal(parent[action_key], "prepare_versioned_rung2_source_identity_and_acquisition_decision", f"parentRungOne.{action_key}")


def validate_provenance_document(document: dict[str, Any], require_semantic: bool = True) -> None:
    require_exact_keys(document, PROVENANCE_TOP_LEVEL_KEYS, "provenance")
    if require_semantic:
        require_semantic_hash(document, EXPECTED_SEMANTIC_SHA256[PROVENANCE_PATH], "provenance")
    identity = {
        "documentType": "aetherlink.g2-rung2-source-provenance-observation",
        "schemaVersion": "1.0",
        "observationId": "g2-pion-ice-v4.3.0-rung2-provenance-observation-v1",
        "recordedDate": "2026-07-23",
        "status": "provenance_signature_and_inclusion_proof_locally_verified_acquisition_not_executed",
        "evidenceClass": "public_read_only_provenance_observation_not_acquisition_receipt",
    }
    for key, expected in identity.items():
        require_equal(document[key], expected, f"provenance.{key}")
    validate_parent_rung_one(document["parentRungOne"], decision_form=False)

    upstream = require_exact_keys(
        document["upstreamIdentity"],
        {"repositoryUrl", "modulePath", "version", "tag", "tagType",
         "commitObjectIdAlgorithm", "commit", "treeObjectIdAlgorithm", "tree", "sourceRole"},
        "provenance.upstreamIdentity",
    )
    expected_upstream = {
        "repositoryUrl": REPOSITORY_URL, "modulePath": MODULE_PATH,
        "version": MODULE_VERSION, "tag": MODULE_VERSION, "tagType": "lightweight",
        "commitObjectIdAlgorithm": "git-sha1", "commit": COMMIT,
        "treeObjectIdAlgorithm": "git-sha1", "tree": TREE,
        "sourceRole": "upstream_base_for_not_yet_implemented_restricted_fork",
    }
    for key, expected in expected_upstream.items():
        require_equal(upstream[key], expected, f"provenance.upstreamIdentity.{key}")

    signature = require_exact_keys(
        document["githubCommitSignatureObservation"],
        {"status", "signedObject", "keyFingerprint", "proxyZipAuthenticatedByThisObservation", "localReverificationStatus"},
        "provenance.githubCommitSignatureObservation",
    )
    require_equal(signature["status"], "valid_observed_only", "provenance.githubSignature.status")
    require_equal(signature["signedObject"], "git_commit_object", "provenance.githubSignature.signedObject")
    require_hex(signature["keyFingerprint"], 40, "provenance.githubSignature.keyFingerprint")
    require_equal(signature["keyFingerprint"], "686e6e5f8d157de2b8dfa974a8cd240651db01b6", "provenance.githubSignature.keyFingerprint")
    require_equal(signature["proxyZipAuthenticatedByThisObservation"], False, "provenance.githubSignature.proxyZipAuthenticated")
    require_equal(signature["localReverificationStatus"], "not_executed", "provenance.githubSignature.localReverificationStatus")

    proxy = require_exact_keys(
        document["goProxyZipObservation"],
        {"url", "scheme", "host", "contentLengthBytes", "etagOrRawSha256Candidate", "rawBytesRetained", "localRawSha256RecomputationStatus"},
        "provenance.goProxyZipObservation",
    )
    require_exact_source_url(proxy["url"], "provenance.goProxyZipObservation.url")
    require_equal(proxy["scheme"], "https", "provenance.goProxyZipObservation.scheme")
    require_equal(proxy["host"], SOURCE_HOST, "provenance.goProxyZipObservation.host")
    require_equal(proxy["contentLengthBytes"], 293023, "provenance.goProxyZipObservation.contentLengthBytes")
    require_equal(proxy["etagOrRawSha256Candidate"], RAW_ARCHIVE_SHA256, "provenance.goProxyZipObservation.etagCandidate")
    require_equal(proxy["rawBytesRetained"], False, "provenance.goProxyZipObservation.rawBytesRetained")
    require_equal(proxy["localRawSha256RecomputationStatus"], "not_executed", "provenance.goProxyZipObservation.localRawSha256Status")

    checksums = require_exact_keys(
        document["goChecksumObservation"],
        {"moduleVersion", "moduleH1", "goModH1", "localModuleH1RecomputationStatus"},
        "provenance.goChecksumObservation",
    )
    require_equal(checksums["moduleVersion"], MODULE_VERSION_ID, "provenance.goChecksum.moduleVersion")
    require_equal(checksums["moduleH1"], MODULE_H1, "provenance.goChecksum.moduleH1")
    require_equal(checksums["goModH1"], GO_MOD_H1, "provenance.goChecksum.goModH1")
    require_equal(checksums["localModuleH1RecomputationStatus"], "not_executed", "provenance.goChecksum.localRecomputation")

    checksum_db = require_exact_keys(
        document["checksumDatabaseObservation"],
        {"name", "verifierKey", "lookupRawSha256", "recordNumber", "recordHashBase64",
         "signedTree", "inclusionProof", "localVerification", "status"},
        "provenance.checksumDatabaseObservation",
    )
    require_equal(checksum_db["name"], "sum.golang.org", "provenance.checksum.name")
    require_exact_keys(checksum_db["signedTree"], {"treeSize", "rootHashBase64", "signatureBase64", "signedTreeTextSha256"}, "provenance.checksum.signedTree")
    require_exact_keys(checksum_db["inclusionProof"], {"recordNumber", "treeSize", "proofHashesBase64"}, "provenance.checksum.inclusionProof")
    local_verification = require_exact_keys(
        checksum_db["localVerification"],
        {"verifierKeyHashRecomputed", "ed25519SignedTreeVerified", "recordHashRecomputed", "rfc6962InclusionProofVerified", "verificationUsesOnlyRecordedPublicInputs"},
        "provenance.checksum.localVerification",
    )
    for key, value in local_verification.items():
        require_equal(value, True, f"provenance.checksum.localVerification.{key}")
    require_equal(checksum_db["status"], "signed_tree_and_record_inclusion_locally_verified", "provenance.checksum.status")
    verify_sumdb_evidence(document)

    boundary = require_exact_keys(
        document["executionBoundary"],
        {"sourceAcquisitionExecuted", "sourceRetained", "archiveExtracted", "sourceExecuted",
         "compilerInvocationAllowed", "codeLoadingAllowed", "socketCreationAllowed",
         "runtimeNetworkIoAllowed", "deviceExecutionAllowed", "productionDeploymentAllowed",
         "gitOperationAllowed", "externalIdentityProofRequired", "userActionRequired"},
        "provenance.executionBoundary",
    )
    for key, value in boundary.items():
        require_equal(value, False, f"provenance.executionBoundary.{key}")
    forward = require_exact_keys(
        document["crossFileHashBindings"],
        {"prospectiveSourceAcquisitionDecisionPath", "prospectiveSourceAcquisitionDecisionId", "status"},
        "provenance.crossFileHashBindings",
    )
    require_equal(forward["prospectiveSourceAcquisitionDecisionPath"], DECISION_PATH.relative_to(ROOT).as_posix(), "provenance.crossFile.decisionPath")
    require_equal(forward["prospectiveSourceAcquisitionDecisionId"], "g2-pion-ice-v4.3.0-source-acquisition-decision-v1", "provenance.crossFile.decisionId")
    require_equal(forward["status"], "forward_identity_only_no_cyclic_hash_claim", "provenance.crossFile.status")


def validate_decision_document(document: dict[str, Any], require_semantic: bool = True) -> None:
    require_exact_keys(document, DECISION_TOP_LEVEL_KEYS, "decision")
    if require_semantic:
        require_semantic_hash(document, EXPECTED_SEMANTIC_SHA256[DECISION_PATH], "decision")
    expected_identity = {
        "documentType": "aetherlink.g2-rung2-source-acquisition-decision",
        "schemaVersion": "1.0",
        "decisionId": "g2-pion-ice-v4.3.0-source-acquisition-decision-v1",
        "recordedDate": "2026-07-23",
        "status": "rung2_source_identity_decision_recorded_acquisition_not_executed",
        "result": "exact_go_module_archive_identity_bound_acquisition_allowed_once",
        "nextAction": "execute_bounded_source_acquisition_once_and_record_receipt",
    }
    for key, expected in expected_identity.items():
        require_equal(document[key], expected, f"decision.{key}")
    validate_parent_rung_one(document["parentRungOne"], decision_form=True)

    provenance = require_exact_keys(
        document["provenanceObservation"],
        {"path", "sha256", "hashBindingStatus", "observationStatusRequired"},
        "decision.provenanceObservation",
    )
    require_equal(provenance["path"], PROVENANCE_PATH.relative_to(ROOT).as_posix(), "decision.provenance.path")
    require_equal(provenance["sha256"], EXPECTED_RAW_SHA256[PROVENANCE_PATH], "decision.provenance.sha256")
    require_equal(provenance["hashBindingStatus"], "bound", "decision.provenance.bindingStatus")
    require_equal(provenance["observationStatusRequired"], "provenance_signature_and_inclusion_proof_locally_verified_acquisition_not_executed", "decision.provenance.requiredStatus")

    source = require_exact_keys(
        document["sourceIdentity"],
        {"repositoryUrl", "modulePath", "version", "tag", "tagType", "commit", "tree",
         "patchSeriesId", "patchSeriesImplementationStatus", "sourceBaselineBoundForOfflineReview",
         "candidateSelected", "librarySelected"},
        "decision.sourceIdentity",
    )
    expected_source = {
        "repositoryUrl": REPOSITORY_URL, "modulePath": MODULE_PATH, "version": MODULE_VERSION,
        "tag": MODULE_VERSION, "tagType": "lightweight", "commit": COMMIT, "tree": TREE,
        "patchSeriesId": "aetherlink-pion-ice-v4.3.0-restriction-v1",
        "patchSeriesImplementationStatus": "not_implemented",
        "sourceBaselineBoundForOfflineReview": True,
        "candidateSelected": False, "librarySelected": False,
    }
    for key, expected in expected_source.items():
        require_equal(source[key], expected, f"decision.sourceIdentity.{key}")

    policy = require_exact_keys(
        document["provenancePolicy"],
        {"githubCommitSignatureStatus", "githubCommitSignatureKeyFingerprint",
         "githubCommitSignatureAuthenticatesProxyZip", "sumdbVerifierKey", "sumdbRecordNumber",
         "sumdbTreeSize", "sumdbRootHashBase64", "sumdbSignatureBase64",
         "sumdbSignedTreeTextSha256", "sumdbRecordHashBase64", "sumdbLookupRawSha256",
         "sumdbEd25519SignedTreeVerified", "sumdbRecordInclusionProofVerified",
         "postAcquisitionRule"},
        "decision.provenancePolicy",
    )
    expected_policy = {
        "githubCommitSignatureStatus": "valid_observed_only",
        "githubCommitSignatureKeyFingerprint": "686e6e5f8d157de2b8dfa974a8cd240651db01b6",
        "githubCommitSignatureAuthenticatesProxyZip": False,
        "sumdbVerifierKey": SUMDB_VERIFIER_KEY, "sumdbRecordNumber": SUMDB_RECORD_NUMBER,
        "sumdbTreeSize": SUMDB_TREE_SIZE, "sumdbRootHashBase64": SUMDB_ROOT_HASH_BASE64,
        "sumdbSignatureBase64": SUMDB_SIGNATURE_BASE64,
        "sumdbSignedTreeTextSha256": SUMDB_SIGNED_TREE_TEXT_SHA256,
        "sumdbRecordHashBase64": SUMDB_RECORD_HASH_BASE64,
        "sumdbLookupRawSha256": SUMDB_LOOKUP_RAW_SHA256,
        "sumdbEd25519SignedTreeVerified": True, "sumdbRecordInclusionProofVerified": True,
        "postAcquisitionRule": "accept_only_if_decision_pinned_raw_sha256_module_h1_and_go_mod_h1_all_match_and_bound_sumdb_evidence_verifies",
    }
    for key, expected in expected_policy.items():
        require_equal(policy[key], expected, f"decision.provenancePolicy.{key}")

    permit = require_exact_keys(
        document["acquisitionPermit"],
        {"status", "mode", "maximumRequestCount", "atomicPermitClaimRequired",
         "existingOutputOrClaimRule", "sourceAcquisitionAllowed", "sourceAcquisitionNetworkIoAllowed",
         "url", "scheme", "allowedHost", "allowedPath", "tlsCertificateValidationRequired",
         "tlsHostnameValidationRequired", "ambientProxyAllowed", "redirectsAllowed",
         "credentialsAllowed", "urlQueryAllowed", "urlFragmentAllowed", "packageManagerAllowed",
         "goCommandAllowed", "gitCommandAllowed", "shellAllowed", "dependencyFetchAllowed",
         "totalDeadlineMilliseconds", "expectedContentLengthBytes", "maximumResponseBytes",
         "outputPath", "archiveOnly", "archiveExtractionAllowed", "sourceExecutionAllowed"},
        "decision.acquisitionPermit",
    )
    permit_expected = {
        "status": "authorized_not_consumed", "mode": "single_exact_archive_request",
        "maximumRequestCount": 1, "atomicPermitClaimRequired": True,
        "existingOutputOrClaimRule": "fail_closed_before_network_io",
        "sourceAcquisitionAllowed": True, "sourceAcquisitionNetworkIoAllowed": True,
        "url": SOURCE_URL, "scheme": "https", "allowedHost": SOURCE_HOST,
        "allowedPath": SOURCE_PATH, "tlsCertificateValidationRequired": True,
        "tlsHostnameValidationRequired": True, "ambientProxyAllowed": False,
        "redirectsAllowed": False, "credentialsAllowed": False,
        "urlQueryAllowed": False, "urlFragmentAllowed": False,
        "packageManagerAllowed": False, "goCommandAllowed": False, "gitCommandAllowed": False,
        "shellAllowed": False, "dependencyFetchAllowed": False,
        "totalDeadlineMilliseconds": 30000, "expectedContentLengthBytes": 293023,
        "maximumResponseBytes": 524288, "outputPath": OUTPUT_PATH,
        "archiveOnly": True, "archiveExtractionAllowed": False, "sourceExecutionAllowed": False,
    }
    for key, expected in permit_expected.items():
        require_equal(permit[key], expected, f"decision.acquisitionPermit.{key}")
    require_exact_source_url(permit["url"], "decision.acquisitionPermit.url")
    require_safe_repo_relative_path(permit["outputPath"], "decision.acquisitionPermit.outputPath")
    if permit["expectedContentLengthBytes"] >= permit["maximumResponseBytes"]:
        fail("decision expected content length must be below the response ceiling")

    checks = require_exact_keys(
        document["requiredPostAcquisitionChecks"],
        {"rawSha256", "rawSha256TrustRole", "moduleH1", "goModH1",
         "rawSha256MatchRequired", "moduleH1MatchRequired", "goModH1MatchRequired",
         "moduleH1MustBeComputedFromZipWithoutExtraction", "contentLengthMatchRequired",
         "sumdbSignatureAndInclusionProofVerificationRequired", "mismatchRule"},
        "decision.requiredPostAcquisitionChecks",
    )
    expected_checks = {
        "rawSha256": RAW_ARCHIVE_SHA256,
        "rawSha256TrustRole": "decision_pinned_prior_public_response_reproducibility_check_not_independent_upstream_authentication",
        "moduleH1": MODULE_H1, "goModH1": GO_MOD_H1,
        "rawSha256MatchRequired": True, "moduleH1MatchRequired": True,
        "goModH1MatchRequired": True, "moduleH1MustBeComputedFromZipWithoutExtraction": True,
        "contentLengthMatchRequired": True,
        "sumdbSignatureAndInclusionProofVerificationRequired": True,
        "mismatchRule": "delete_or_quarantine_bytes_close_permit_and_require_new_versioned_decision",
    }
    for key, expected in expected_checks.items():
        require_equal(checks[key], expected, f"decision.requiredChecks.{key}")
    require_hex(checks["rawSha256"], 64, "decision.requiredChecks.rawSha256")

    rollback = require_exact_keys(
        document["rollback"],
        {"onAnyFailure", "automaticRetryAllowed", "alternateMirrorAllowed",
         "wrapperFallbackAllowed", "newDecisionRequiredAfterFailure"},
        "decision.rollback",
    )
    require_equal(rollback["onAnyFailure"], "remove_or_quarantine_unaccepted_archive_and_preserve_relay_only_sealed_fallback", "decision.rollback.onAnyFailure")
    for key in ("automaticRetryAllowed", "alternateMirrorAllowed", "wrapperFallbackAllowed"):
        require_equal(rollback[key], False, f"decision.rollback.{key}")
    require_equal(rollback["newDecisionRequiredAfterFailure"], True, "decision.rollback.newDecisionRequiredAfterFailure")

    boundary = require_exact_keys(
        document["executionBoundary"],
        {"decisionRecorded", "acquisitionExecuted", "permitConsumed", "candidateSelected",
         "librarySelected", "dependencyInstallationAllowed", "compilerInvocationAllowed",
         "codeLoadingAllowed", "socketCreationAllowed", "runtimeNetworkIoAllowed",
         "deviceExecutionAllowed", "productionDeploymentAllowed", "gitOperationAllowed",
         "externalIdentityProofRequired", "userActionRequired",
         "repositoryOwnerAuthenticationRequired", "productEndpointAuthenticationRequired"},
        "decision.executionBoundary",
    )
    require_equal(boundary["decisionRecorded"], True, "decision.executionBoundary.decisionRecorded")
    require_equal(boundary["productEndpointAuthenticationRequired"], True, "decision.executionBoundary.productEndpointAuthenticationRequired")
    for key in set(boundary) - {"decisionRecorded", "productEndpointAuthenticationRequired"}:
        require_equal(boundary[key], False, f"decision.executionBoundary.{key}")

    forward = require_exact_keys(
        document["crossFileHashBindings"], {"progressPath", "progressId", "status"},
        "decision.crossFileHashBindings",
    )
    require_equal(forward["progressPath"], PROGRESS_PATH.relative_to(ROOT).as_posix(), "decision.crossFile.progressPath")
    require_equal(forward["progressId"], "g2-pion-ice-v4.3.0-source-acquisition-progress-v1", "decision.crossFile.progressId")
    require_equal(forward["status"], "forward_identity_only_no_cyclic_hash_claim", "decision.crossFile.status")


def validate_progress_document(document: dict[str, Any], require_semantic: bool = True) -> None:
    require_exact_keys(document, PROGRESS_TOP_LEVEL_KEYS, "progress")
    if require_semantic:
        require_semantic_hash(document, EXPECTED_SEMANTIC_SHA256[PROGRESS_PATH], "progress")
    expected_identity = {
        "documentType": "aetherlink.g2-rung2-source-acquisition-progress",
        "schemaVersion": "1.0", "progressId": "g2-pion-ice-v4.3.0-source-acquisition-progress-v1",
        "recordedDate": "2026-07-23", "status": "authorized_not_consumed",
        "result": None, "nextAction": "execute_bounded_source_acquisition_once_and_record_receipt",
    }
    for key, expected in expected_identity.items():
        require_equal(document[key], expected, f"progress.{key}")

    decision_binding = require_exact_keys(document["decisionBinding"], {"path", "sha256", "status"}, "progress.decisionBinding")
    require_equal(decision_binding["path"], DECISION_PATH.relative_to(ROOT).as_posix(), "progress.decisionBinding.path")
    require_equal(decision_binding["sha256"], EXPECTED_RAW_SHA256[DECISION_PATH], "progress.decisionBinding.sha256")
    require_equal(decision_binding["status"], "bound", "progress.decisionBinding.status")
    provenance_binding = require_exact_keys(document["provenanceBinding"], {"path", "sha256", "status"}, "progress.provenanceBinding")
    require_equal(provenance_binding["path"], PROVENANCE_PATH.relative_to(ROOT).as_posix(), "progress.provenanceBinding.path")
    require_equal(provenance_binding["sha256"], EXPECTED_RAW_SHA256[PROVENANCE_PATH], "progress.provenanceBinding.sha256")
    require_equal(provenance_binding["status"], "bound", "progress.provenanceBinding.status")

    archive = require_exact_keys(
        document["expectedArchive"],
        {"modulePath", "version", "url", "contentLengthBytes", "maximumResponseBytes",
         "rawSha256", "moduleH1", "goModH1", "outputPath"},
        "progress.expectedArchive",
    )
    expected_archive = {
        "modulePath": MODULE_PATH, "version": MODULE_VERSION, "url": SOURCE_URL,
        "contentLengthBytes": 293023, "maximumResponseBytes": 524288,
        "rawSha256": RAW_ARCHIVE_SHA256, "moduleH1": MODULE_H1,
        "goModH1": GO_MOD_H1, "outputPath": OUTPUT_PATH,
    }
    for key, expected in expected_archive.items():
        require_equal(archive[key], expected, f"progress.expectedArchive.{key}")
    require_exact_source_url(archive["url"], "progress.expectedArchive.url")
    require_safe_repo_relative_path(archive["outputPath"], "progress.expectedArchive.outputPath")

    permit_state = require_exact_keys(
        document["permitState"],
        {"authorized", "consumed", "atomicClaimCreated", "maximumRequestCount",
         "requestCount", "totalDeadlineMilliseconds"},
        "progress.permitState",
    )
    expected_permit = {
        "authorized": True, "consumed": False, "atomicClaimCreated": False,
        "maximumRequestCount": 1, "requestCount": 0, "totalDeadlineMilliseconds": 30000,
    }
    for key, expected in expected_permit.items():
        require_equal(permit_state[key], expected, f"progress.permitState.{key}")

    request = require_exact_keys(
        document["requestObservation"],
        {"started", "completed", "startedAt", "completedAt", "requestedUrl", "finalUrl",
         "httpStatus", "redirectCount", "observedContentLengthBytes", "receivedBytes",
         "observedEtag", "failureReason"},
        "progress.requestObservation",
    )
    for key in ("started", "completed"):
        require_equal(request[key], False, f"progress.requestObservation.{key}")
    for key in set(request) - {"started", "completed"}:
        require_equal(request[key], None, f"progress.requestObservation.{key}")

    verification = require_exact_keys(
        document["verificationObservation"],
        {"rawSha256", "rawSha256Matches", "moduleH1", "moduleH1Matches", "goModH1",
         "goModH1Matches", "sumdbSignatureVerified", "sumdbInclusionProofVerified",
         "allRequiredChecksPassed"},
        "progress.verificationObservation",
    )
    for key in ("rawSha256", "moduleH1", "goModH1"):
        require_equal(verification[key], None, f"progress.verificationObservation.{key}")
    for key in set(verification) - {"rawSha256", "moduleH1", "goModH1"}:
        require_equal(verification[key], False, f"progress.verificationObservation.{key}")

    artifact = require_exact_keys(
        document["artifactObservation"],
        {"outputFileExists", "outputPath", "sourceAcquired", "sourceRetained",
         "archiveExtracted", "sourceExecuted", "quarantined", "removedAfterFailure"},
        "progress.artifactObservation",
    )
    require_equal(artifact["outputPath"], None, "progress.artifactObservation.outputPath")
    for key in set(artifact) - {"outputPath"}:
        require_equal(artifact[key], False, f"progress.artifactObservation.{key}")

    boundary = require_exact_keys(
        document["executionBoundary"],
        {"candidateSelected", "librarySelected", "dependencyInstallationAllowed",
         "compilerInvocationAllowed", "codeLoadingAllowed", "socketCreationAllowed",
         "runtimeNetworkIoAllowed", "deviceExecutionAllowed", "productionDeploymentAllowed",
         "gitOperationAllowed", "externalIdentityProofRequired", "userActionRequired"},
        "progress.executionBoundary",
    )
    for key, value in boundary.items():
        require_equal(value, False, f"progress.executionBoundary.{key}")


def manifest_collection_digest(rows: Iterable[tuple[str, str, str]]) -> str:
    payload = "".join(
        f"{evidence_id}\t{sha256_value}\t{repo_path}\n"
        for evidence_id, repo_path, sha256_value in rows
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_evidence_manifest(
    document: dict[str, Any],
    require_semantic: bool = True,
    verify_artifact_files: bool = True,
) -> None:
    require_exact_keys(document, MANIFEST_TOP_LEVEL_KEYS, "manifest")
    if require_semantic:
        require_semantic_hash(document, EXPECTED_SEMANTIC_SHA256[EVIDENCE_MANIFEST_PATH], "manifest")
    expected_identity = {
        "documentType": "aetherlink.g2-pion-rung2-source-acquisition-evidence-manifest",
        "schemaVersion": "1.0",
        "decisionId": "g2-pion-ice-v4.3.0-source-acquisition-decision-v1",
        "recordedDate": "2026-07-23", "orderingRule": "ascending_evidence_id",
        "collectionDigestAlgorithm": "sha256_utf8_lf_of_evidence_id_tab_sha256_tab_repo_relative_path_newline",
        "artifactCount": 6, "collectionSha256": RUNG_TWO_COLLECTION_SHA256,
        "sourceAcquisitionExecuted": False, "externalIdentityProofRequired": False,
        "userActionRequired": False,
    }
    for key, expected in expected_identity.items():
        require_equal(document[key], expected, f"manifest.{key}")
    artifacts = require_list(document["artifacts"], "manifest.artifacts")
    if len(artifacts) != len(EXPECTED_MANIFEST_ROWS):
        fail(f"manifest must contain exactly {len(EXPECTED_MANIFEST_ROWS)} artifacts")
    observed_ids: set[str] = set()
    observed_paths: set[str] = set()
    digest_rows: list[tuple[str, str, str]] = []
    for index, (artifact, expected_row) in enumerate(zip(artifacts, EXPECTED_MANIFEST_ROWS)):
        artifact = require_exact_keys(artifact, {"evidenceId", "path", "sha256", "role"}, f"manifest.artifacts[{index}]")
        expected_id, expected_path, expected_hash, expected_role = expected_row
        require_equal(artifact["evidenceId"], expected_id, f"manifest.artifacts[{index}].evidenceId")
        require_equal(artifact["path"], expected_path, f"manifest.artifacts[{index}].path")
        require_equal(artifact["sha256"], expected_hash, f"manifest.artifacts[{index}].sha256")
        require_equal(artifact["role"], expected_role, f"manifest.artifacts[{index}].role")
        require_safe_repo_relative_path(artifact["path"], f"manifest.artifacts[{index}].path")
        require_hex(artifact["sha256"], 64, f"manifest.artifacts[{index}].sha256")
        if artifact["evidenceId"] in observed_ids or artifact["path"] in observed_paths:
            fail("manifest contains a duplicate evidence ID or path")
        observed_ids.add(artifact["evidenceId"])
        observed_paths.add(artifact["path"])
        digest_rows.append((artifact["evidenceId"], artifact["path"], artifact["sha256"]))
        if verify_artifact_files:
            artifact_path = ROOT / artifact["path"]
            verify_file_shape_and_hash(artifact_path, artifact["sha256"])
    if [row[0] for row in digest_rows] != sorted(row[0] for row in digest_rows):
        fail("manifest evidence IDs are not in ascending order")
    observed_collection = manifest_collection_digest(digest_rows)
    if observed_collection != document["collectionSha256"]:
        fail(
            "manifest collection SHA-256 mismatch: "
            f"expected {document['collectionSha256']}, got {observed_collection}"
        )


def validate_markdown_text(text: str) -> None:
    require_exact_type(text, str, "decisionMarkdown")
    normalized = " ".join(text.split())
    required_fragments = (
        "rung2_source_identity_decision_recorded_acquisition_not_executed",
        "authorized_not_consumed",
        "No candidate or library is selected.",
        SOURCE_URL,
        RAW_ARCHIVE_SHA256,
        MODULE_H1,
        GO_MOD_H1,
        "not an independent upstream authentication root",
        "atomically claim the permit",
        "TLS certificate and hostname validation are mandatory",
        "Repository-owner authentication, external identity proof, and user action are not required.",
        "Product endpoint authentication remains mandatory and separate.",
        "it does not implicitly open that rung",
    )
    for fragment in required_fragments:
        if fragment not in normalized:
            fail(f"decision markdown is missing required fragment {fragment!r}")
    forbidden_fragments = (
        "source acquisition completed",
        "source acquired successfully",
        "all required checks passed",
        "candidate selected for implementation",
        "globally consistent checksum database",
        "freshness verified",
        "GitHub commit cryptographically bound to the proxy ZIP",
    )
    lowered = normalized.lower()
    for fragment in forbidden_fragments:
        if fragment.lower() in lowered:
            fail(f"decision markdown contains fabricated claim {fragment!r}")


def validate_markdown() -> None:
    try:
        text = secure_read_bytes(DECISION_MARKDOWN_PATH).decode("utf-8")
    except (OSError, UnicodeError) as error:
        fail(f"unable to read decision markdown: {error}")
    validate_markdown_text(text)


def read_exact_git_object(arguments: Sequence[str], maximum_bytes: int) -> bytes:
    """Read one historical Git object without checkout, mutation, or networking."""

    environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        result = subprocess.run(
            ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", *arguments],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        fail(f"unable to read historical Git object: {error}")
    if result.returncode != 0:
        fail(
            "historical Git object read failed: "
            + result.stderr[:512].decode("utf-8", errors="replace")
        )
    if len(result.stdout) > maximum_bytes:
        fail("historical Git object exceeds its read ceiling")
    return result.stdout


def validate_canonical_document_supersession(
    *, verify_superseded_current_files: bool = False
) -> None:
    document = load_json(CANONICAL_DOC_SUPERSESSION_PATH)
    verify_pretty_json_bytes(CANONICAL_DOC_SUPERSESSION_PATH, document)
    require_semantic_hash(
        document,
        EXPECTED_SEMANTIC_SHA256[CANONICAL_DOC_SUPERSESSION_PATH],
        "canonicalDocSupersession",
    )
    require_exact_keys(
        document,
        {
            "documentType", "schemaVersion", "supersessionId", "recordedDate",
            "status", "reason", "predecessorManifestBinding",
            "historicalGitSnapshot", "currentDocumentState",
            "currentEvidenceBinding", "executionBoundary",
        },
        "canonicalDocSupersession",
    )
    expected_identity = {
        "documentType": "aetherlink.g2-canonical-document-supersession",
        "schemaVersion": "1.0",
        "supersessionId": "g2-pion-rung2-canonical-document-supersession-v1",
        "recordedDate": "2026-07-23",
        "status": "historical_rung1_bytes_git_preserved_current_docs_advanced_to_rung2_receipt",
        "reason": "roadmap_and_handoff_are_living_canonical_documents_and_must_advance_without_rewriting_the_rung1_snapshot",
    }
    for key, expected in expected_identity.items():
        require_equal(document[key], expected, f"canonicalDocSupersession.{key}")
    predecessor = require_exact_keys(
        document["predecessorManifestBinding"],
        {"path", "sha256", "collectionSha256"},
        "canonicalDocSupersession.predecessorManifestBinding",
    )
    predecessor_expected = {
        "path": RUNG_ONE_MANIFEST_PATH.relative_to(ROOT).as_posix(),
        "sha256": EXPECTED_RAW_SHA256[RUNG_ONE_MANIFEST_PATH],
        "collectionSha256": RUNG_ONE_COLLECTION_SHA256,
    }
    for key, expected in predecessor_expected.items():
        require_equal(
            predecessor[key], expected,
            f"canonicalDocSupersession.predecessorManifestBinding.{key}",
        )

    historical = require_exact_keys(
        document["historicalGitSnapshot"],
        {"commit", "tree", "objectReadMode", "readOnlyGitObjectVerificationRequired", "documents"},
        "canonicalDocSupersession.historicalGitSnapshot",
    )
    historical_commit = "3bf9615024a3959f61d4bb749f8930dd07ea4385"
    historical_tree = "a0640a2484e2ec249a5cfb0180ab26e8a0493d98"
    require_equal(historical["commit"], historical_commit, "canonicalDocSupersession.historical.commit")
    require_equal(historical["tree"], historical_tree, "canonicalDocSupersession.historical.tree")
    require_equal(historical["objectReadMode"], "exact_commit_tree_blob_read_only_no_checkout", "canonicalDocSupersession.historical.objectReadMode")
    require_equal(historical["readOnlyGitObjectVerificationRequired"], True, "canonicalDocSupersession.historical.readOnlyGitObjectVerificationRequired")
    commit_bytes = read_exact_git_object(["cat-file", "commit", historical_commit], 64 * 1024)
    if not commit_bytes.startswith(f"tree {historical_tree}\n".encode("ascii")):
        fail("historical Git commit does not bind the recorded root tree")
    historical_rows = (
        (
            "G2E003", "docs/roadmap.md",
            "2fcb2e60b39d6ea843179d84c29bb57ac5219d20b2b2454c0165e420e1c462a5",
            "historical_rung1_canonical_roadmap_snapshot",
        ),
        (
            "G2E004", "docs/handoff.md",
            "f3f43bd602660bc01d5fcbde54550423abcc72ae73ce705021d1ef3b4f4fd2d4",
            "historical_rung1_canonical_handoff_snapshot",
        ),
    )
    historical_documents = require_list(
        historical["documents"], "canonicalDocSupersession.historical.documents"
    )
    if len(historical_documents) != len(historical_rows):
        fail("canonicalDocSupersession must bind exactly two historical documents")
    for index, (item, expected) in enumerate(zip(historical_documents, historical_rows)):
        item = require_exact_keys(
            item, {"evidenceId", "path", "sha256", "role"},
            f"canonicalDocSupersession.historical.documents[{index}]",
        )
        for key, expected_value in zip(("evidenceId", "path", "sha256", "role"), expected):
            require_equal(
                item[key], expected_value,
                f"canonicalDocSupersession.historical.documents[{index}].{key}",
            )
        blob = read_exact_git_object(
            ["cat-file", "blob", f"{historical_commit}:{item['path']}"],
            1024 * 1024,
        )
        if hashlib.sha256(blob).hexdigest() != item["sha256"]:
            fail(f"historical Git blob hash mismatch for {item['path']}")

    current = require_exact_keys(
        document["currentDocumentState"], {"status", "nextAction", "documents"},
        "canonicalDocSupersession.currentDocumentState",
    )
    require_equal(current["status"], "synchronized_to_acquisition_complete_archive_retained_not_extracted", "canonicalDocSupersession.current.status")
    require_equal(current["nextAction"], "prepare_versioned_rung3_offline_source_review_decision", "canonicalDocSupersession.current.nextAction")
    current_rows = (
        ("docs/roadmap.md", "b4a78169161f9a72788cc5c4dc7e55fe53ac720ec65095e9fe4562ce5c47d45d", "current_canonical_v1_delivery_roadmap"),
        ("docs/handoff.md", "e4b659e737402e359ec3e99d1a7b871176cdb1ea53ec986da5f9884089858987", "current_canonical_session_handoff"),
    )
    current_documents = require_list(current["documents"], "canonicalDocSupersession.current.documents")
    if len(current_documents) != len(current_rows):
        fail("canonicalDocSupersession must bind exactly two current documents")
    for index, (item, expected) in enumerate(zip(current_documents, current_rows)):
        item = require_exact_keys(item, {"path", "sha256", "role"}, f"canonicalDocSupersession.current.documents[{index}]")
        for key, expected_value in zip(("path", "sha256", "role"), expected):
            require_equal(item[key], expected_value, f"canonicalDocSupersession.current.documents[{index}].{key}")
        if verify_superseded_current_files:
            verify_file_shape_and_hash(ROOT / item["path"], item["sha256"])

    evidence = require_exact_keys(
        document["currentEvidenceBinding"],
        {"receiptPath", "receiptSha256", "progressPath", "progressSha256", "manifestPath", "manifestSha256"},
        "canonicalDocSupersession.currentEvidenceBinding",
    )
    evidence_expected = {
        "receiptPath": "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/source-acquisition-receipt-v1.json",
        "receiptSha256": "3faa5d1d12b7d52b9c2f74a68a2bd83d2bbd459342e56fe6a20caf1ac61409f6",
        "progressPath": "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/source-acquisition-progress-v2.json",
        "progressSha256": "df1ad52bc6fff294b9bb54fd94a8eaacd76d9ff2b179be4a6752a867d229196f",
        "manifestPath": "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-two/evidence-manifest-v3.json",
        "manifestSha256": "8ed1a2667153f77270531d7c373f5f61ed9eb9080bceab7c804c9b686259537e",
    }
    for key, expected in evidence_expected.items():
        require_equal(evidence[key], expected, f"canonicalDocSupersession.currentEvidenceBinding.{key}")
        if key.endswith("Sha256"):
            require_hex(evidence[key], 64, f"canonicalDocSupersession.currentEvidenceBinding.{key}")

    boundary = require_exact_keys(
        document["executionBoundary"],
        {
            "historicalDecisionRewritten", "historicalReceiptRewritten",
            "archiveExtracted", "sourceReviewPerformed", "candidateSelected",
            "librarySelected", "compilerInvocationAllowed", "codeLoadingAllowed",
            "socketCreationAllowed", "runtimeNetworkIoAllowed", "deviceExecutionAllowed",
            "productionDeploymentAllowed", "gitWriteOperationAllowed",
            "externalIdentityProofRequired", "userActionRequired",
            "repositoryOwnerAuthenticationRequired",
            "rungThreeOfflineReviewDecisionPreparationAllowed",
            "rungThreeOfflineReviewExecutionAllowed",
        },
        "canonicalDocSupersession.executionBoundary",
    )
    for key, value in boundary.items():
        require_equal(
            value,
            key == "rungThreeOfflineReviewDecisionPreparationAllowed",
            f"canonicalDocSupersession.executionBoundary.{key}",
        )


CURRENT_CANONICAL_DOCUMENT_PATHS = (
    "docs/roadmap.md",
    "docs/handoff.md",
    "README.md",
    "shared/protocol/README.md",
    "docs/progress.md",
    "docs/qa-evidence.md",
)
CURRENT_CANONICAL_FORBIDDEN_PHRASES = (
    "current pre-acquisition result",
    "current restricted-fork rung-one result",
    "current restricted-fork rung-one",
    "active pre-acquisition direction",
    "prepare the separate rung-two exact-source identity/acquisition decision",
    "preparation of its separate rung-two technical decision",
    "preparation of a separate rung-two technical decision",
    "opens only preparation of a separate rung-two",
    "proceed only to preparation of a separate rung-two",
    "rung-two source-identity and acquisition decision",
    "rung-two provenance/acquisition decision",
    "explicit user decision",
)
CURRENT_CANONICAL_NORMALIZATION_RULE = (
    "unicode_preserving_split_whitespace_join_single_ascii_space_then_lowercase"
)
CURRENT_CANONICAL_ROADMAP_SECTION_HEADINGS = (
    "### G2 - Select A New P2P/NAT Stack Under Fresh Authority",
    "### Immediate Execution Queue",
)
HISTORICAL_RUNG_TWO_PREPARATION_MARKERS = (
    "prepare_versioned_rung2_source_identity_and_acquisition_decision",
    "preparation of a separate rung-two",
    "rung-two source-identity and acquisition decision",
    "rung-two provenance/acquisition decision",
)


def normalized_markdown_text(text: str) -> str:
    return " ".join(text.split()).lower()


def markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        fail(f"canonical roadmap is missing section heading {heading!r}")
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def validate_current_canonical_document_semantics(
    texts: Mapping[str, str] | None = None,
) -> None:
    if texts is None:
        loaded: dict[str, str] = {}
        for relative_path in CURRENT_CANONICAL_DOCUMENT_PATHS:
            try:
                loaded[relative_path] = secure_read_bytes(ROOT / relative_path).decode("utf-8")
            except (OSError, UnicodeError) as error:
                fail(f"unable to read current canonical document {relative_path}: {error}")
        texts = loaded
    require_equal(
        tuple(texts.keys()),
        CURRENT_CANONICAL_DOCUMENT_PATHS,
        "canonicalDocSupersessionV2.semanticGuard.scope",
    )
    for relative_path, text in texts.items():
        require_exact_type(text, str, f"canonicalDocSupersessionV2.semanticGuard.{relative_path}")
        normalized = normalized_markdown_text(text)
        if "at_that_checkpoint" not in normalized:
            fail(f"{relative_path} must mark historical G2 direction with at_that_checkpoint")
        if "prepare_versioned_rung3_offline_source_review_decision" not in normalized:
            fail(f"{relative_path} must name the exact current rung-three preparation action")
        for phrase in CURRENT_CANONICAL_FORBIDDEN_PHRASES:
            if phrase in normalized:
                fail(f"{relative_path} contains superseded current-step phrase {phrase!r}")
    roadmap = texts["docs/roadmap.md"]
    for heading in CURRENT_CANONICAL_ROADMAP_SECTION_HEADINGS:
        section = markdown_section(roadmap, heading)
        normalized_section = normalized_markdown_text(section)
        if "prepare_versioned_rung3_offline_source_review_decision" not in normalized_section:
            fail(f"canonical roadmap section {heading!r} lacks the current rung-three action")
        for paragraph in re.split(r"\n\s*\n", section):
            normalized_paragraph = normalized_markdown_text(paragraph)
            if any(
                marker in normalized_paragraph
                for marker in HISTORICAL_RUNG_TWO_PREPARATION_MARKERS
            ) and "at_that_checkpoint" not in normalized_paragraph:
                fail(
                    f"canonical roadmap section {heading!r} contains an unscoped "
                    "historical rung-two preparation instruction"
                )


def validate_canonical_document_supersession_v2(
    *, verify_superseded_current_files: bool = False
) -> None:
    path = CANONICAL_DOC_SUPERSESSION_V2_PATH
    document = load_json(path)
    verify_pretty_json_bytes(path, document)
    require_semantic_hash(
        document,
        EXPECTED_SEMANTIC_SHA256[path],
        "canonicalDocSupersessionV2",
    )
    require_exact_keys(
        document,
        {
            "documentType", "schemaVersion", "supersessionId", "recordedDate",
            "status", "reason", "predecessorSupersessionBinding",
            "predecessorManifestBinding", "previousDocumentState",
            "currentDocumentState", "semanticGuard", "executionBoundary",
        },
        "canonicalDocSupersessionV2",
    )
    expected_identity = {
        "documentType": "aetherlink.g2-canonical-document-supersession",
        "schemaVersion": "1.0",
        "supersessionId": "g2-pion-rung2-canonical-document-supersession-v2",
        "recordedDate": "2026-07-23",
        "status": "historical_v4_semantic_conflict_corrected_current_docs_advanced_to_unambiguous_rung3_preparation",
        "reason": "historical_checkpoint_sections_must_not_override_the_consumed_rung2_receipt_or_reselect_a_completed_acquisition_step",
    }
    for key, expected in expected_identity.items():
        require_equal(document[key], expected, f"canonicalDocSupersessionV2.{key}")

    require_exact_keys(
        document["predecessorSupersessionBinding"],
        {"path", "sha256", "semanticSha256"},
        "canonicalDocSupersessionV2.predecessorSupersessionBinding",
    )
    predecessor_supersession = {
        "path": CANONICAL_DOC_SUPERSESSION_PATH.relative_to(ROOT).as_posix(),
        "sha256": EXPECTED_RAW_SHA256[CANONICAL_DOC_SUPERSESSION_PATH],
        "semanticSha256": EXPECTED_SEMANTIC_SHA256[CANONICAL_DOC_SUPERSESSION_PATH],
    }
    require_equal(
        document["predecessorSupersessionBinding"],
        predecessor_supersession,
        "canonicalDocSupersessionV2.predecessorSupersessionBinding",
    )
    verify_file_shape_and_hash(
        CANONICAL_DOC_SUPERSESSION_PATH,
        predecessor_supersession["sha256"],
    )

    predecessor_manifest = {
        "path": CANONICAL_SYNC_MANIFEST_V4_PATH.relative_to(ROOT).as_posix(),
        "sha256": "eb2352de7623706095b6208edcc58b9550e1a1501ed2482739f89525c74da022",
        "collectionSha256": "a2f2ab09307a5b1408d65699b3746782f8e6de6ece8e98891241dc350bc4cae3",
    }
    require_exact_keys(
        document["predecessorManifestBinding"],
        {"path", "sha256", "collectionSha256"},
        "canonicalDocSupersessionV2.predecessorManifestBinding",
    )
    require_equal(
        document["predecessorManifestBinding"],
        predecessor_manifest,
        "canonicalDocSupersessionV2.predecessorManifestBinding",
    )
    verify_file_shape_and_hash(
        CANONICAL_SYNC_MANIFEST_V4_PATH,
        predecessor_manifest["sha256"],
    )

    previous_rows = (
        ("docs/roadmap.md", "b4a78169161f9a72788cc5c4dc7e55fe53ac720ec65095e9fe4562ce5c47d45d", "previous_canonical_v1_delivery_roadmap"),
        ("docs/handoff.md", "e4b659e737402e359ec3e99d1a7b871176cdb1ea53ec986da5f9884089858987", "previous_canonical_session_handoff"),
        ("README.md", "0c760bc7409629e70e9ddc170f295640c15738ad41ce76d6cb4c85a23194d0ae", "previous_root_project_status"),
        ("shared/protocol/README.md", "319771b5614e71125809202c5625ade90416e19f29ca2dd5da7237bed8df24a0", "previous_shared_protocol_status"),
        ("docs/progress.md", "d4f6885a898ad4468348999bed169837530663e87d94bd1b413aec21b1730cb1", "previous_progress_status"),
        ("docs/qa-evidence.md", "f2458587f32fa3d93862dd84501544046bc4859291225fbf4eda8a07200a8880", "previous_qa_checklist"),
    )
    current_rows = (
        ("docs/roadmap.md", "067fe008fb7be9c73883cf50bd9f9d44764025fb8197e18fbe46d79bf1ef110e", "current_canonical_v1_delivery_roadmap"),
        ("docs/handoff.md", "8117a2eea69f9fc2241145fec833700da1076f3e387b3b8a8a09ab725c207ae8", "current_canonical_session_handoff"),
        ("README.md", "aca5762ff01056401e8e6824d96a548c589493a9dd28d7d4c07524913b41fdfc", "current_root_project_status"),
        ("shared/protocol/README.md", "50e6337bf9685a3b3e064f954a7bb25dc129a19cf79a7ec536d990c60c73df40", "current_shared_protocol_status"),
        ("docs/progress.md", "10d878b77bdfee4ebd0d0a104bdb3aa7ae80bfaf2130b293852b4fb04c50c1c4", "current_progress_status"),
        ("docs/qa-evidence.md", "fe7b7535c3aa4d27b1e079d3be4fcfa5a13f1dba32c9a528b739a082fa348832", "current_qa_checklist"),
    )
    for state_name, expected_status, expected_rows, verify_files in (
        (
            "previousDocumentState",
            "rung2_acquisition_complete_with_ambiguous_historical_current_wording",
            previous_rows,
            False,
        ),
        (
            "currentDocumentState",
            "rung2_acquisition_complete_archive_retained_not_extracted_semantically_unambiguous",
            current_rows,
            verify_superseded_current_files,
        ),
    ):
        expected_keys = {"status", "documents"}
        if state_name == "currentDocumentState":
            expected_keys.add("nextAction")
        state = require_exact_keys(
            document[state_name], expected_keys, f"canonicalDocSupersessionV2.{state_name}"
        )
        require_equal(
            state["status"], expected_status, f"canonicalDocSupersessionV2.{state_name}.status"
        )
        if state_name == "currentDocumentState":
            require_equal(
                state["nextAction"],
                "prepare_versioned_rung3_offline_source_review_decision",
                "canonicalDocSupersessionV2.currentDocumentState.nextAction",
            )
        rows = require_list(
            state["documents"], f"canonicalDocSupersessionV2.{state_name}.documents"
        )
        if len(rows) != len(expected_rows):
            fail(f"canonicalDocSupersessionV2.{state_name} must bind exactly six documents")
        for index, (item, expected_row) in enumerate(zip(rows, expected_rows)):
            item = require_exact_keys(
                item,
                {"path", "sha256", "role"},
                f"canonicalDocSupersessionV2.{state_name}.documents[{index}]",
            )
            expected_item = dict(zip(("path", "sha256", "role"), expected_row))
            require_equal(
                item,
                expected_item,
                f"canonicalDocSupersessionV2.{state_name}.documents[{index}]",
            )
            if verify_files:
                verify_file_shape_and_hash(ROOT / item["path"], item["sha256"])

    semantic_guard = require_exact_keys(
        document["semanticGuard"],
        {
            "scope", "historicalCheckpointToken", "requiredCurrentNextAction",
            "forbiddenCurrentPhrases", "normalizationRule", "roadmapSectionScopes",
        },
        "canonicalDocSupersessionV2.semanticGuard",
    )
    require_equal(
        semantic_guard,
        {
            "scope": list(CURRENT_CANONICAL_DOCUMENT_PATHS),
            "historicalCheckpointToken": "at_that_checkpoint",
            "requiredCurrentNextAction": "prepare_versioned_rung3_offline_source_review_decision",
            "forbiddenCurrentPhrases": list(CURRENT_CANONICAL_FORBIDDEN_PHRASES),
            "normalizationRule": CURRENT_CANONICAL_NORMALIZATION_RULE,
            "roadmapSectionScopes": list(CURRENT_CANONICAL_ROADMAP_SECTION_HEADINGS),
        },
        "canonicalDocSupersessionV2.semanticGuard",
    )
    if verify_superseded_current_files:
        validate_current_canonical_document_semantics()

    boundary = require_exact_keys(
        document["executionBoundary"],
        {
            "historicalDecisionRewritten", "historicalReceiptRewritten",
            "archiveExtracted", "sourceReviewPerformed", "candidateSelected",
            "librarySelected", "compilerInvocationAllowed", "codeLoadingAllowed",
            "socketCreationAllowed", "runtimeNetworkIoAllowed", "deviceExecutionAllowed",
            "productionDeploymentAllowed", "gitWriteOperationAllowed",
            "externalIdentityProofRequired", "userActionRequired",
            "repositoryOwnerAuthenticationRequired",
            "rungThreeOfflineReviewDecisionPreparationAllowed",
            "rungThreeOfflineReviewExecutionAllowed",
        },
        "canonicalDocSupersessionV2.executionBoundary",
    )
    for key, value in boundary.items():
        require_equal(
            value,
            key == "rungThreeOfflineReviewDecisionPreparationAllowed",
            f"canonicalDocSupersessionV2.executionBoundary.{key}",
        )


def validate_cross_document_bindings(
    provenance: Mapping[str, Any],
    decision: Mapping[str, Any],
    progress: Mapping[str, Any],
) -> None:
    if raw_sha256(PROVENANCE_PATH) != decision["provenanceObservation"]["sha256"]:
        fail("decision provenance byte binding does not match the current file")
    if raw_sha256(DECISION_PATH) != progress["decisionBinding"]["sha256"]:
        fail("progress decision byte binding does not match the current file")
    if raw_sha256(PROVENANCE_PATH) != progress["provenanceBinding"]["sha256"]:
        fail("progress provenance byte binding does not match the current file")

    upstream = provenance["upstreamIdentity"]
    source = decision["sourceIdentity"]
    for key in ("repositoryUrl", "modulePath", "version", "tag", "tagType", "commit", "tree"):
        if upstream[key] != source[key]:
            fail(f"provenance/decision source identity drift at {key}")
    proxy = provenance["goProxyZipObservation"]
    permit = decision["acquisitionPermit"]
    archive = progress["expectedArchive"]
    for value, expected, label in (
        (proxy["url"], permit["url"], "provenance/permit URL"),
        (permit["url"], archive["url"], "permit/progress URL"),
        (proxy["contentLengthBytes"], permit["expectedContentLengthBytes"], "content length"),
        (permit["expectedContentLengthBytes"], archive["contentLengthBytes"], "progress content length"),
        (permit["maximumResponseBytes"], archive["maximumResponseBytes"], "maximum response"),
        (permit["outputPath"], archive["outputPath"], "output path"),
    ):
        if value != expected:
            fail(f"cross-document drift at {label}")
    go_checksums = provenance["goChecksumObservation"]
    required_checks = decision["requiredPostAcquisitionChecks"]
    for key in ("moduleH1", "goModH1"):
        if go_checksums[key] != required_checks[key] or required_checks[key] != archive[key]:
            fail(f"cross-document checksum drift at {key}")
    if proxy["etagOrRawSha256Candidate"] != required_checks["rawSha256"]:
        fail("prior raw response observation and decision-pinned raw SHA-256 drifted")
    if required_checks["rawSha256"] != archive["rawSha256"]:
        fail("decision/progress raw SHA-256 drifted")


def validate_repository() -> None:
    for path, expected_hash in EXPECTED_RAW_SHA256.items():
        verify_file_shape_and_hash(path, expected_hash)

    profile = load_json(PROFILE_PATH)
    require_semantic_hash(profile, EXPECTED_SEMANTIC_SHA256[PROFILE_PATH], "rungOne.profile")
    rung_one_manifest = load_json(RUNG_ONE_MANIFEST_PATH)
    require_equal(
        rung_one_manifest.get("collectionSha256"),
        RUNG_ONE_COLLECTION_SHA256,
        "rungOne.manifest.collectionSha256",
    )

    provenance = load_json(PROVENANCE_PATH)
    decision = load_json(DECISION_PATH)
    progress = load_json(PROGRESS_PATH)
    manifest = load_json(EVIDENCE_MANIFEST_PATH)
    for path, document in (
        (PROVENANCE_PATH, provenance),
        (DECISION_PATH, decision),
        (PROGRESS_PATH, progress),
        (EVIDENCE_MANIFEST_PATH, manifest),
    ):
        verify_pretty_json_bytes(path, document)

    validate_provenance_document(provenance)
    validate_decision_document(decision)
    validate_progress_document(progress)
    validate_evidence_manifest(manifest, verify_artifact_files=False)
    for _, artifact_path, artifact_hash, _ in EXPECTED_MANIFEST_ROWS[:2]:
        verify_file_shape_and_hash(ROOT / artifact_path, artifact_hash)
    validate_canonical_document_supersession()
    validate_canonical_document_supersession_v2()
    validate_cross_document_bindings(provenance, decision, progress)
    validate_markdown()


def print_hashes() -> None:
    for path in EXPECTED_RAW_SHA256:
        print(f"{path.relative_to(ROOT).as_posix()}\t{raw_sha256(path)}")
        if path.suffix == ".json":
            print(f"{path.relative_to(ROOT).as_posix()}#semantic\t{semantic_sha256(load_json(path))}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-hashes", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.print_hashes:
            print_hashes()
            return 0
        validate_repository()
    except RungTwoValidationError as error:
        print(f"G2 Pion rung-two validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "G2 Pion historical rung-two acquisition authority passed: public SumDB "
        "signature and inclusion proof verified; the immutable checkpoint records "
        "the exact request as authorized but not yet consumed; the historical "
        "canonical-document supersession chain is verified while the current "
        "successor is checked by the rung-three validator; "
        "no user or owner authentication required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
