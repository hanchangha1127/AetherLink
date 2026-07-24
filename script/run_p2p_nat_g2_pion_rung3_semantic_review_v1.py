#!/usr/bin/env python3
"""Validate or exclusively publish the bounded Pion rung-three semantic review.

The runner is deliberately self-contained.  It does not import project code,
execute reviewed source, access a network, invoke a compiler, or require any
identity proof.  Both modes read the retained ZIP through one stable
``O_NOFOLLOW`` descriptor and recreate the complete v3 lexical observation
universe from one immutable in-memory source snapshot.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "semantic review runner requires unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import io
import json
import os
import re
import stat
import struct
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG3 = f"{BASE}/rung-three"
DECISION_PATH = f"{RUNG3}/semantic-source-review-decision-v1.json"
PASS_INPUT_PATH = f"{RUNG3}/semantic-source-review-pass-input-v1.json"
RUNNER_PATH = "script/run_p2p_nat_g2_pion_rung3_semantic_review_v1.py"
PRIMARY_PASS_RECORD_PATH = (
    f"{RUNG3}/semantic-source-review-primary-pass-record-v1.json"
)
INDEPENDENT_PASS_RECORD_PATH = (
    f"{RUNG3}/semantic-source-review-independent-pass-record-v1.json"
)
PASS_RECORD_PATHS = {
    "primary": PRIMARY_PASS_RECORD_PATH,
    "independent": INDEPENDENT_PASS_RECORD_PATH,
}
ARCHIVE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
MODULE_PREFIX = "github.com/pion/ice/v4@v4.3.0/"

CLASSIFICATIONS_NAME = "semantic-source-review-classifications-v1.json"
RESULT_NAME = "semantic-source-review-result-v1.json"
MANIFEST_NAME = "semantic-source-review-manifest-v1.json"
FAILURE_NAME = "semantic-source-review-execution-failure-v1.json"
OUTPUT_NAMES = (
    CLASSIFICATIONS_NAME,
    RESULT_NAME,
    MANIFEST_NAME,
    FAILURE_NAME,
)
STAGING_NAMES = {
    name: f".{name}.staging"
    for name in OUTPUT_NAMES
}
RESERVED_OUTPUT_NAMES = OUTPUT_NAMES + tuple(
    STAGING_NAMES[name] for name in OUTPUT_NAMES
)

EXPECTED_DECISION_RAW_SHA256 = (
    "b65379bf0f97cd0558c93d818e5ecea14242a938ca5922796eb4a28f345e7cfc"
)
EXPECTED_DECISION_CONTENT_SHA256 = (
    "09ccce7ae9b0893e30d4cbf2533e947623da70f56a499e5bdd2cd3e68bc3ef6b"
)
EXPECTED_INPUT_RAW_SHA256 = (
    "21a228b16d57addfef20d0ff53ec81a7ee5846462d60d8d8fbc4ffa25addf548"
)
EXPECTED_INPUT_CONTENT_SHA256 = (
    "7240a2386d7ada48cde93792110bbcc72474b834cc1cc4c5294f945baad605be"
)
EXPECTED_PASS_RECORD_RAW_SHA256 = {
    "primary": "7d12f76bc38befc728b0f78bbda3c792e398e0984c98a86825124b3d457678fc",
    "independent": (
        "b45b7a80813bafc46a3cc0d0358b6738f408dd025b092dfd2d99a17eb8a92557"
    ),
}
EXPECTED_PASS_RECORD_CONTENT_SHA256 = {
    "primary": "323699afbb0747ca90fc1aa5bf6e8ec20cbc319408b7e1156064e4d90799f97f",
    "independent": (
        "59d5e2c09c5a3ec08b1796807b97dccadd678b5a50fcaae6d699d3b0a86868cc"
    ),
}
EXPECTED_PASS_RECORD_IDS = {
    "primary": (
        "g2-pion-ice-v4.3.0-rung3-semantic-source-review-primary-pass-record-v1"
    ),
    "independent": (
        "g2-pion-ice-v4.3.0-rung3-semantic-source-review-independent-pass-record-v1"
    ),
}
EXPECTED_PASS_CANDIDATE_COUNTS = {"primary": 14, "independent": 15}
EXPECTED_PASS_CANDIDATE_SEMANTIC_SHA256 = {
    "primary": "66481cfac724c39b2dd8a2a721b1afe939cbb3c95a7752fee62a72d61ddc4038",
    "independent": (
        "563eb28ca3aff18aa051584255bccf257ab80dbeb4f5ec1d9319dbad0d605edf"
    ),
}
CANDIDATE_SEMANTIC_DIGEST_CONTRACT = {
    "algorithm": "sha256",
    "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
    "payload": "exact_candidateFindings_rows_matching_passId_in_pass_input_array_order",
    "scope": "canonical_json_array_of_exact_pass_candidate_rows_in_pass_input_order",
}
INTEGRITY_LIMITATIONS = {
    "runnerBindingAttestsLoadedExecutingCode": False,
    "runnerBindingAttestsProcessIdentity": False,
    "runnerBindingIsAuthenticationOrAuthorityProof": False,
    "runnerBindingScope": "stable_on_disk_runner_file_bytes_sha256",
    "sameUidConcurrentMutationPrevented": False,
    "sameUidMutationAfterFinalReadbackDetectedByThisRunner": False,
    "sameUidMutationDetectionLimitedToStableReadbackWindows": True,
}
LOCATION_VALIDATION_BOUNDARY = {
    "goParserUsed": False,
    "semanticSinkReachabilityProven": False,
    "sourceClassDerivedFromPathValidated": True,
    "sourcePathMembershipValidatedAgainstSnapshot": True,
    "startAndEndLineBoundsValidatedAgainstSnapshot": True,
    "symbolResolutionPerformed": False,
}
POST_RUN_EVIDENCE_BOUNDARY = {
    "independentPostRunCheckerRequiredForFinalSuccessEvidence": True,
    "independentPostRunCheckerCompleted": False,
    "finalSuccessEvidenceEstablished": False,
}
EXPECTED_ARCHIVE_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
EXPECTED_SOURCE_TREE_SHA256 = (
    "b44b1277937432822d005632dc0ac77b0c733959c871d998fac5e3964ce39244"
)
EXPECTED_ARCHIVE_BYTES = 293_023
EXPECTED_ENTRY_COUNT = 129
EXPECTED_TOTAL_UNCOMPRESSED_BYTES = 1_131_286
EXPECTED_GO_SOURCE_COUNT = 100
EXPECTED_GO_SOURCE_BYTES = 1_077_591
EXPECTED_GO_LOGICAL_LINES = 39_064
EXPECTED_SOURCE_CLASS_COUNTS = {"example": 4, "production": 52, "test": 44}
CANDIDATE_SOURCE_CLASSES = frozenset(
    (*EXPECTED_SOURCE_CLASS_COUNTS, "dependency")
)
EXPECTED_OBSERVATION_CLASS_COUNTS = {
    "example": 117,
    "production": 1546,
    "test": 3038,
}
EXPECTED_OBSERVATION_COUNT = 4_701
EXPECTED_GO_MOD_REQUIRE_COUNT = 19
EXPECTED_GO_SUM_RECORD_COUNT = 44

MAXIMUM_ARCHIVE_BYTES = 524_288
MAXIMUM_JSON_BYTES = 4_194_304
MAXIMUM_ENTRY_COUNT = 4_096
MAXIMUM_PATH_BYTES = 1_024
MAXIMUM_PATH_COMPONENTS = 32
MAXIMUM_COMPONENT_BYTES = 255
MAXIMUM_SINGLE_FILE_BYTES = 4_194_304
MAXIMUM_GO_SOURCE_BYTES = 2_097_152
MAXIMUM_TOTAL_UNCOMPRESSED_BYTES = 67_108_864
MAXIMUM_COMPRESSION_RATIO = 200
MAXIMUM_LOGICAL_LINES_PER_SOURCE = 262_144
MAXIMUM_TOTAL_LOGICAL_LINES = 1_048_576

COMPLETE_OBSERVATION_HASH_DOMAIN = (
    b"aetherlink.g2.pion.candidate-inventory.v3.complete-observation.v1\x00"
)
OBSERVATION_SET_HASH_DOMAIN = (
    b"aetherlink.g2.pion.semantic-source-review.v1.observation-set\x00"
)
OBSERVATION_ID_HASH_DOMAIN = (
    b"aetherlink.g2.pion.semantic-source-review.v1.observation-id\x00"
)
FINDING_ID_HASH_DOMAIN = (
    b"aetherlink.g2.pion.semantic-source-review.v1.finding-id\x00"
)

PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)
VERIFICATION_UNIT_IDS = (
    "g2-r3-egress-path-coverage",
    "g2-r3-ingress-path-coverage",
    "g2-r3-address-and-resolution-adversarial",
    "g2-r3-turn-tls-service-identity",
    "g2-r3-secure-session-promotion",
    "g2-r3-resource-and-event-bounds",
    "g2-r3-secret-free-diagnostics",
    "g2-r3-deadline-shutdown",
)
PASS_IDS = ("primary", "independent")
DISPOSITIONS = frozenset(
    {"false_positive", "acceptable_existing", "patch_required", "unresolved"}
)
SEVERITIES = frozenset({"P0", "P1", "P2", "P3", "none"})
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "none": 4}

REVIEW_RULE_ROWS = (
    (
        PATCH_UNITS[0],
        (
            ("egress-dial", r"\b(?:Dial|DialContext|DialUDP|WriteTo|WriteToUDP)\b"),
            ("egress-listen", r"\b(?:Listen|ListenPacket|ListenUDP|PacketConn)\b"),
            ("candidate-io", r"\b(?:Candidate|UDPMux|UniversalUDPMux|sendBindingRequest)\b"),
        ),
    ),
    (
        PATCH_UNITS[1],
        (
            ("diagnostic-call", r"\b(?:Tracef|Debugf|Infof|Warnf|Errorf|Logf|Logger)\b"),
            ("credential-token", r"(?i)\b(?:credential|password|username|ufrag|pwd|secret)\b"),
        ),
    ),
    (
        PATCH_UNITS[2],
        (
            ("callback", r"\bOn(?:ConnectionStateChange|SelectedCandidatePairChange)\b"),
            ("channel", r"\b(?:chan|close)\b|make\s*\(\s*chan\b"),
            ("event", r"(?i)\b(?:event|callback|handler)\b"),
        ),
    ),
    (
        PATCH_UNITS[3],
        (
            ("deadline", r"\b(?:SetDeadline|SetReadDeadline|SetWriteDeadline|WithTimeout)\b"),
            ("shutdown", r"\b(?:Close|cancel|WaitGroup|Done)\b"),
            ("time-bound", r"(?i)\b(?:deadline|timeout|shutdown)\b"),
        ),
    ),
    (
        PATCH_UNITS[4],
        (
            ("transport-path", r"(?i)\b(?:tcp|udp|mdns|proxy|relay|host|srflx|upnp)\b"),
            ("network-type", r"\b(?:NetworkType|CandidateType|TCPType)\b"),
        ),
    ),
    (
        PATCH_UNITS[5],
        (
            ("resolver", r"\b(?:Resolver|LookupIP|LookupHost|ResolveIPAddr)\b"),
            ("turn-tls", r"\b(?:ServerName|InsecureSkipVerify|TLSConfig|tls\.Config|TURN)\b"),
            ("network-injection", r"\b(?:Net|TransportNet|vnet)\b"),
        ),
    ),
    (
        PATCH_UNITS[6],
        (
            ("pre-auth", r"(?i)\b(?:auth|credential|username|password|ufrag|pwd)\b"),
            ("promotion-state", r"\b(?:ConnectionState|setState|validate|Validate)\b"),
            ("one-use", r"(?i)\b(?:one.?use|single.?use|nonce|replay)\b"),
        ),
    ),
)
COMPILED_REVIEW_RULE_ROWS = tuple(
    (
        patch_unit,
        tuple((rule_id, pattern, re.compile(pattern)) for rule_id, pattern in rules),
    )
    for patch_unit, rules in REVIEW_RULE_ROWS
)
EXPECTED_UNIT_ROWS = (
    (
        PATCH_UNITS[0],
        606,
        "587bab19a6de8486e533694a29f4720ad4bea09b648f809d5e2dae8a0996ae4f",
        (("egress-dial", 87), ("egress-listen", 175), ("candidate-io", 344)),
    ),
    (
        PATCH_UNITS[1],
        600,
        "7b6a25688527a8cc25d600058499eb65ee2a4ad44550ca3b4aab5a33b32e9b8a",
        (("diagnostic-call", 334), ("credential-token", 266)),
    ),
    (
        PATCH_UNITS[2],
        482,
        "fc5279c6e0ff47ffd6c5d285ec89724daef9b67010a1ff0eb34dd2c749e05d05",
        (("callback", 59), ("channel", 394), ("event", 29)),
    ),
    (
        PATCH_UNITS[3],
        1056,
        "f8c10189b96a8e335a2612e615567a7a5a17f2e7e9aec136fcabf797f1e851ad",
        (("deadline", 127), ("shutdown", 767), ("time-bound", 162)),
    ),
    (
        PATCH_UNITS[4],
        1356,
        "f1189b22b6752fca8bcca9066d31d917004222cea0bfa5e30b92bdd081d1c299",
        (("transport-path", 839), ("network-type", 517)),
    ),
    (
        PATCH_UNITS[5],
        278,
        "ad83ba81c58c26e25f1a44b1da1e0d769a2b05bf790d8e5e5d1429b2be16d108",
        (("resolver", 14), ("turn-tls", 68), ("network-injection", 196)),
    ),
    (
        PATCH_UNITS[6],
        323,
        "103ba2454dc4b3156123dbeccdcb897b205d6adff35621d1947695a7f4a7fb39",
        (("pre-auth", 268), ("promotion-state", 55), ("one-use", 0)),
    ),
)


class ReviewError(RuntimeError):
    """A bounded validation or publication failure."""


class PublicationError(ReviewError):
    """Exclusive publication did not complete."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def content_bound(document: Mapping[str, Any], scope: str) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("contentBinding", None)
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": sha256_bytes(canonical_json_bytes(payload)),
    }
    return result


def strict_json(raw: bytes, label: str) -> dict[str, Any]:
    require(
        raw.endswith(b"\n") and not raw.endswith(b"\n\n") and b"\r" not in raw,
        f"{label} is not canonical line-delimited JSON",
    )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewError(f"{label} is not strict UTF-8") from error

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"{label} contains a duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ReviewError(f"{label} contains a non-finite number")
            ),
        )
    except (json.JSONDecodeError, TypeError) as error:
        raise ReviewError(f"{label} is not strict JSON") from error
    require(isinstance(value, dict), f"{label} must be a JSON object")
    require(canonical_json_bytes(value) == raw, f"{label} is not canonical JSON")
    return value


def validate_content_binding(
    document: Mapping[str, Any],
    *,
    expected_scope: str,
    expected_sha256: str,
    label: str,
) -> None:
    binding = document.get("contentBinding")
    require(isinstance(binding, Mapping), f"{label} omitted contentBinding")
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": expected_scope,
            "sha256": expected_sha256,
        },
        f"{label} contentBinding drifted",
    )
    payload = dict(document)
    payload.pop("contentBinding", None)
    require(
        sha256_bytes(canonical_json_bytes(payload)) == expected_sha256,
        f"{label} content digest mismatch",
    )


def directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def file_open_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )


def create_file_flags() -> int:
    return (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def validate_safe_relative_path(path: str, *, prefix: str | None = None) -> tuple[str, ...]:
    require(type(path) is str and path != "", "relative path is empty")
    require(
        "\\" not in path
        and ":" not in path
        and "\x00" not in path
        and not path.startswith("/")
        and not path.endswith("/")
        and unicodedata.normalize("NFC", path) == path,
        "relative path is unsafe",
    )
    raw = path.encode("utf-8", errors="strict")
    require(len(raw) <= MAXIMUM_PATH_BYTES, "relative path exceeds its byte bound")
    parts = path.split("/")
    require(
        len(parts) <= MAXIMUM_PATH_COMPONENTS
        and all(
            part not in ("", ".", "..")
            and len(part.encode("utf-8")) <= MAXIMUM_COMPONENT_BYTES
            and not any(ord(character) < 32 or ord(character) == 127 for character in part)
            for part in parts
        ),
        "relative path is noncanonical",
    )
    if prefix is not None:
        require(path.startswith(prefix), "relative path escaped its fixed prefix")
    return tuple(parts)


def validate_directory_descriptor(fd: int, label: str) -> None:
    metadata = os.fstat(fd)
    require(stat.S_ISDIR(metadata.st_mode), f"{label} is not a directory")
    require(metadata.st_uid == os.getuid(), f"{label} owner drifted")
    require(not metadata.st_mode & 0o022, f"{label} is group- or world-writable")


def open_root_directory(root: Path) -> int:
    try:
        fd = os.open(os.fspath(root), directory_open_flags())
    except OSError as error:
        raise ReviewError("unable to open the repository root safely") from error
    try:
        validate_directory_descriptor(fd, "repository root")
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_relative_parent(root: Path, path: str) -> tuple[int, str]:
    parts = validate_safe_relative_path(path)
    current_fd = open_root_directory(root)
    try:
        for component in parts[:-1]:
            try:
                next_fd = os.open(component, directory_open_flags(), dir_fd=current_fd)
            except OSError as error:
                raise ReviewError("unable to open a fixed path ancestor safely") from error
            validate_directory_descriptor(next_fd, "fixed path ancestor")
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result, parts[-1]
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def read_stable_relative_file(
    root: Path,
    path: str,
    *,
    maximum_bytes: int,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    required_mode: int | None = None,
) -> tuple[bytes, os.stat_result]:
    parent_fd, name = open_relative_parent(root, path)
    file_fd = -1
    try:
        try:
            file_fd = os.open(name, file_open_flags(), dir_fd=parent_fd)
        except OSError as error:
            raise ReviewError("unable to open a fixed input safely") from error
        before = os.fstat(file_fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid()
            and before.st_nlink == 1
            and not before.st_mode & 0o022,
            "fixed input metadata drifted",
        )
        if required_mode is not None:
            require(
                stat.S_IMODE(before.st_mode) == required_mode,
                "fixed input mode drifted",
            )
        require(
            0 <= before.st_size <= maximum_bytes,
            "fixed input exceeds its byte bound",
        )
        if expected_bytes is not None:
            require(before.st_size == expected_bytes, "fixed input byte size mismatch")
        chunks: list[bytes] = []
        remaining = before.st_size + 1
        while remaining > 0:
            chunk = os.read(file_fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(file_fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        require(
            len(raw) == before.st_size
            and all(getattr(before, field) == getattr(after, field) for field in stable_fields),
            "fixed input changed during its single read",
        )
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        require(
            stat.S_ISREG(named.st_mode)
            and named.st_dev == after.st_dev
            and named.st_ino == after.st_ino,
            "fixed input path no longer names the reviewed descriptor",
        )
        if expected_sha256 is not None:
            require(sha256_bytes(raw) == expected_sha256, "fixed input SHA-256 mismatch")
        return raw, after
    except OSError as error:
        raise ReviewError("fixed input stable read failed") from error
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)


def classify_source(path: str) -> str:
    if path.startswith("examples/"):
        return "example"
    if path.endswith("_test.go"):
        return "test"
    return "production"


def _u16_field(raw: bytes) -> bytes:
    require(len(raw) <= 0xFFFF, "internal u16 field overflow")
    return struct.pack(">H", len(raw)) + raw


def observation_identity(path_bytes: bytes, line_number: int, rule_id: str) -> bytes:
    rule_bytes = rule_id.encode("utf-8")
    return (
        struct.pack(">I", len(path_bytes))
        + path_bytes
        + struct.pack(">Q", line_number)
        + _u16_field(rule_bytes)
    )


def observation_id(
    patch_unit: str,
    path_bytes: bytes,
    line_number: int,
    rule_id: str,
) -> str:
    digest = hashlib.sha256(
        OBSERVATION_ID_HASH_DOMAIN
        + _u16_field(patch_unit.encode("utf-8"))
        + observation_identity(path_bytes, line_number, rule_id)
    ).hexdigest()
    return f"G2SR1-O-{digest[:20]}"


def parse_go_mod_require_count(raw: bytes) -> int:
    require(len(raw) <= MAXIMUM_GO_SOURCE_BYTES and b"\x00" not in raw, "go.mod is invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewError("go.mod is not strict UTF-8") from error
    dependencies: set[tuple[str, str]] = set()
    in_require = False
    for source_line in text.splitlines():
        line = source_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line == "require (":
            in_require = True
            continue
        if in_require and line == ")":
            in_require = False
            continue
        fields = line.split()
        if line.startswith("require ") and len(fields) >= 3:
            dependencies.add((fields[1], fields[2]))
        elif in_require and len(fields) >= 2:
            dependencies.add((fields[0], fields[1]))
    return len(dependencies)


def parse_go_sum_record_count(raw: bytes) -> int:
    require(len(raw) <= MAXIMUM_GO_SOURCE_BYTES and b"\x00" not in raw, "go.sum is invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewError("go.sum is not strict UTF-8") from error
    rows: set[tuple[str, str, str]] = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        require(
            len(fields) == 3 and fields[2].startswith("h1:"),
            "go.sum record shape drifted",
        )
        rows.add((fields[0], fields[1], fields[2]))
    return len(rows)


def inspect_zip_structure(
    raw: bytes,
    *,
    expected_entry_count: int,
    expected_total_uncompressed_bytes: int,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    require(
        type(raw) is bytes and 0 < len(raw) <= MAXIMUM_ARCHIVE_BYTES,
        "ZIP bytes exceed their input bound",
    )
    require(
        type(expected_entry_count) is int
        and 0 <= expected_entry_count <= MAXIMUM_ENTRY_COUNT
        and type(expected_total_uncompressed_bytes) is int
        and 0 <= expected_total_uncompressed_bytes
        <= MAXIMUM_TOTAL_UNCOMPRESSED_BYTES,
        "ZIP expected totals exceed their bounds",
    )
    entries: dict[str, bytes] = {}
    tree_rows: list[bytes] = []
    total_uncompressed = 0
    entry_body_read_count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as archive:
            require(archive.comment == b"", "retained ZIP comment drifted")
            infos = archive.infolist()
            require(
                len(infos) == expected_entry_count
                and len(infos) <= MAXIMUM_ENTRY_COUNT,
                "retained ZIP entry count mismatch",
            )
            seen_full_paths: set[str] = set()
            for info in infos:
                full_path = info.filename
                require(
                    type(full_path) is str
                    and full_path.isascii()
                    and full_path.startswith(MODULE_PREFIX),
                    "retained ZIP entry encoding or prefix drifted",
                )
                validate_safe_relative_path(full_path, prefix=MODULE_PREFIX)
                relative = full_path[len(MODULE_PREFIX):]
                validate_safe_relative_path(relative)
                require(
                    full_path not in seen_full_paths
                    and relative not in entries
                    and not info.is_dir(),
                    "retained ZIP contains a duplicate or non-file entry",
                )
                seen_full_paths.add(full_path)
            for info in infos:
                require(
                    info.flag_bits == 8
                    and info.compress_type == zipfile.ZIP_DEFLATED
                    and info.create_system == 0
                    and info.external_attr == 0
                    and info.create_version == 20
                    and info.extract_version == 20
                    and info.extra == b""
                    and info.comment == b"",
                    "retained ZIP entry metadata drifted",
                )
                require(
                    0 <= info.file_size <= MAXIMUM_SINGLE_FILE_BYTES
                    and 0 <= info.compress_size <= MAXIMUM_ARCHIVE_BYTES,
                    "retained ZIP entry exceeds its byte bound",
                )
                if info.file_size:
                    require(
                        info.compress_size > 0
                        and info.file_size
                        <= info.compress_size * MAXIMUM_COMPRESSION_RATIO,
                        "retained ZIP entry exceeds its compression-ratio bound",
                    )
                total_uncompressed += info.file_size
                require(
                    total_uncompressed <= MAXIMUM_TOTAL_UNCOMPRESSED_BYTES,
                    "retained ZIP exceeds its total uncompressed bound",
                )
            for info in infos:
                relative = info.filename[len(MODULE_PREFIX):]
                body = archive.read(info)
                entry_body_read_count += 1
                require(
                    len(body) == info.file_size,
                    "retained ZIP entry changed while read from memory",
                )
                entries[relative] = body
                digest = sha256_bytes(body)
                tree_rows.append(
                    f"{relative}\0{len(body)}\0{digest}\n".encode("utf-8")
                )
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, UnicodeError) as error:
        raise ReviewError("retained ZIP failed bounded in-memory validation") from error
    require(
        len(entries) == expected_entry_count
        and entry_body_read_count == expected_entry_count
        and total_uncompressed == expected_total_uncompressed_bytes,
        "retained ZIP inventory totals drifted",
    )
    source_tree_sha256 = sha256_bytes(b"".join(sorted(tree_rows)))
    return entries, {
        "entryBodyReadCount": entry_body_read_count,
        "entryCount": len(entries),
        "sourceTreeSha256": source_tree_sha256,
        "totalUncompressedBytes": total_uncompressed,
    }


def inspect_retained_archive(
    raw: bytes,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    require(
        len(raw) == EXPECTED_ARCHIVE_BYTES
        and len(raw) <= MAXIMUM_ARCHIVE_BYTES
        and sha256_bytes(raw) == EXPECTED_ARCHIVE_SHA256,
        "retained archive identity mismatch",
    )
    entries, inventory = inspect_zip_structure(
        raw,
        expected_entry_count=EXPECTED_ENTRY_COUNT,
        expected_total_uncompressed_bytes=EXPECTED_TOTAL_UNCOMPRESSED_BYTES,
    )
    require(
        inventory["sourceTreeSha256"] == EXPECTED_SOURCE_TREE_SHA256,
        "retained ZIP source-tree digest mismatch",
    )
    return entries, inventory


def build_go_snapshot(
    entries: Mapping[str, bytes],
) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], dict[str, Any]]:
    go_sources: list[tuple[str, tuple[str, ...]]] = []
    source_class_counts = {"example": 0, "production": 0, "test": 0}
    total_bytes = 0
    total_lines = 0
    line_counts: dict[str, int] = {}
    for path in sorted(entries, key=lambda value: value.encode("utf-8")):
        if not path.endswith(".go"):
            continue
        raw = entries[path]
        require(
            len(raw) <= MAXIMUM_GO_SOURCE_BYTES and b"\x00" not in raw,
            "Go source exceeds its text boundary",
        )
        try:
            lines = tuple(raw.decode("utf-8", errors="strict").splitlines())
        except UnicodeDecodeError as error:
            raise ReviewError("Go source is not strict UTF-8") from error
        require(
            len(lines) <= MAXIMUM_LOGICAL_LINES_PER_SOURCE,
            "Go source exceeds its logical-line bound",
        )
        total_bytes += len(raw)
        total_lines += len(lines)
        require(
            total_bytes <= MAXIMUM_TOTAL_UNCOMPRESSED_BYTES
            and total_lines <= MAXIMUM_TOTAL_LOGICAL_LINES,
            "Go source snapshot exceeds its aggregate bound",
        )
        source_class_counts[classify_source(path)] += 1
        line_counts[path] = len(lines)
        go_sources.append((path, lines))
    require(
        len(go_sources) == EXPECTED_GO_SOURCE_COUNT
        and total_bytes == EXPECTED_GO_SOURCE_BYTES
        and total_lines == EXPECTED_GO_LOGICAL_LINES
        and source_class_counts == EXPECTED_SOURCE_CLASS_COUNTS,
        "Go source snapshot totals drifted",
    )
    go_mod = entries.get("go.mod")
    go_sum = entries.get("go.sum")
    require(go_mod is not None and go_sum is not None, "module metadata is absent")
    require(
        parse_go_mod_require_count(go_mod) == EXPECTED_GO_MOD_REQUIRE_COUNT
        and parse_go_sum_record_count(go_sum) == EXPECTED_GO_SUM_RECORD_COUNT,
        "dependency metadata counts drifted",
    )
    return tuple(go_sources), {
        "goSourceBodyReadCount": len(go_sources),
        "goSourceFileCount": len(go_sources),
        "goSourceLogicalLineCount": total_lines,
        "goSourceTotalBytes": total_bytes,
        "lineCounts": line_counts,
        "sourceFileClassCounts": source_class_counts,
    }


def aggregate_observations(
    go_sources: Sequence[tuple[str, Sequence[str]]],
) -> dict[str, Any]:
    unit_states: dict[str, dict[str, Any]] = {}
    for patch_unit, rules in COMPILED_REVIEW_RULE_ROWS:
        unit_hasher = hashlib.sha256()
        unit_hasher.update(COMPLETE_OBSERVATION_HASH_DOMAIN)
        unit_hasher.update(_u16_field(patch_unit.encode("utf-8")))
        unit_states[patch_unit] = {
            "hasher": unit_hasher,
            "total": 0,
            "classCounts": {"example": 0, "production": 0, "test": 0},
            "rules": {
                rule_id: {
                    "total": 0,
                    "classCounts": {"example": 0, "production": 0, "test": 0},
                }
                for rule_id, _pattern, _compiled in rules
            },
        }
    observation_set_hasher = hashlib.sha256(OBSERVATION_SET_HASH_DOMAIN)
    by_path_line: dict[tuple[str, int], list[str]] = {}
    observation_ids: set[str] = set()
    total = 0
    for path, lines in sorted(go_sources, key=lambda entry: entry[0].encode("utf-8")):
        path_bytes = path.encode("utf-8")
        source_class = classify_source(path)
        for line_number, line in enumerate(lines, start=1):
            require(type(line) is str, "Go source snapshot line type drifted")
            line_sha256 = hashlib.sha256(line.encode("utf-8")).digest()
            for patch_unit, rules in COMPILED_REVIEW_RULE_ROWS:
                unit_state = unit_states[patch_unit]
                unit_field = _u16_field(patch_unit.encode("utf-8"))
                for rule_id, _pattern, compiled in rules:
                    if compiled.search(line) is None:
                        continue
                    identity = observation_identity(path_bytes, line_number, rule_id)
                    unit_state["hasher"].update(identity)
                    unit_state["hasher"].update(line_sha256)
                    unit_state["total"] += 1
                    unit_state["classCounts"][source_class] += 1
                    rule_state = unit_state["rules"][rule_id]
                    rule_state["total"] += 1
                    rule_state["classCounts"][source_class] += 1
                    observation_set_hasher.update(unit_field)
                    observation_set_hasher.update(identity)
                    observation_set_hasher.update(line_sha256)
                    identifier = observation_id(
                        patch_unit, path_bytes, line_number, rule_id
                    )
                    require(identifier not in observation_ids, "observation ID collision")
                    observation_ids.add(identifier)
                    by_path_line.setdefault((path, line_number), []).append(identifier)
                    total += 1
    patch_rows: list[dict[str, Any]] = []
    aggregate_class_counts = {"example": 0, "production": 0, "test": 0}
    for expected_unit, expected_total, expected_digest, expected_rules in EXPECTED_UNIT_ROWS:
        state = unit_states[expected_unit]
        digest = state["hasher"].hexdigest()
        require(
            state["total"] == expected_total and digest == expected_digest,
            "complete observation unit digest or count drifted",
        )
        rules: list[dict[str, Any]] = []
        for rule_id, expected_rule_total in expected_rules:
            rule_state = state["rules"][rule_id]
            require(
                rule_state["total"] == expected_rule_total,
                "complete observation rule count drifted",
            )
            rules.append(
                {
                    "ruleId": rule_id,
                    "totalHitCount": rule_state["total"],
                    "sourceClassCounts": rule_state["classCounts"],
                }
            )
        for source_class, count in state["classCounts"].items():
            aggregate_class_counts[source_class] += count
        patch_rows.append(
            {
                "patchUnit": expected_unit,
                "totalHitCount": state["total"],
                "completeObservationSha256": digest,
                "sourceClassCounts": state["classCounts"],
                "rules": rules,
            }
        )
    require(
        total == EXPECTED_OBSERVATION_COUNT
        and len(observation_ids) == EXPECTED_OBSERVATION_COUNT
        and aggregate_class_counts == EXPECTED_OBSERVATION_CLASS_COUNTS,
        "complete observation universe totals drifted",
    )
    return {
        "defaultDisposition": "unresolved",
        "observationCount": total,
        "observationIdsUnique": True,
        "observationSetSha256": observation_set_hasher.hexdigest(),
        "sourceClassCounts": aggregate_class_counts,
        "patchUnits": patch_rows,
        "byPathLine": by_path_line,
    }


def validate_decision(document: Mapping[str, Any]) -> None:
    validate_content_binding(
        document,
        expected_scope="decision_without_contentBinding",
        expected_sha256=EXPECTED_DECISION_CONTENT_SHA256,
        label="semantic decision",
    )
    require(
        document.get("documentType")
        == "aetherlink.g2-pion-rung3-semantic-source-review-decision"
        and document.get("schemaVersion") == "1.0"
        and document.get("decisionId")
        == "g2-pion-ice-v4.3.0-rung3-semantic-source-review-decision-v1",
        "semantic decision identity drifted",
    )
    archive = document.get("archiveIdentity")
    coverage = document.get("reviewCoverage")
    contract = document.get("semanticContract")
    publication = document.get("publicationContract")
    personal = document.get("personalProjectBoundary")
    nonclaims = document.get("nonClaims")
    require(
        isinstance(archive, Mapping)
        and archive.get("retainedArchivePath") == ARCHIVE_PATH
        and archive.get("bytes") == EXPECTED_ARCHIVE_BYTES
        and archive.get("entryCount") == EXPECTED_ENTRY_COUNT
        and archive.get("rawSha256") == EXPECTED_ARCHIVE_SHA256
        and archive.get("sourceTreeSha256") == EXPECTED_SOURCE_TREE_SHA256,
        "semantic decision archive identity drifted",
    )
    require(
        isinstance(coverage, Mapping)
        and coverage.get("goSourceFileCount") == EXPECTED_GO_SOURCE_COUNT
        and coverage.get("goSourceTotalBytes") == EXPECTED_GO_SOURCE_BYTES
        and coverage.get("goSourceLogicalLineCount") == EXPECTED_GO_LOGICAL_LINES
        and coverage.get("lexicalRuleCount") == 19
        and coverage.get("patchUnitCount") == len(PATCH_UNITS)
        and coverage.get("reviewPasses") == list(PASS_IDS)
        and coverage.get("sourceClasses") == EXPECTED_SOURCE_CLASS_COUNTS
        and coverage.get("verificationUnitIds") == list(VERIFICATION_UNIT_IDS),
        "semantic decision review coverage drifted",
    )
    require(
        isinstance(contract, Mapping)
        and contract.get("archiveOpenCountPerAnalysisExecution") == 1
        and contract.get("sourceBodyReadCountPerGoFilePerAnalysisExecution") == 1
        and contract.get("reviewPassesShareOneImmutableInMemorySnapshot") is True
        and contract.get("disagreementResolution") == "force_unresolved"
        and contract.get("dependencyClosureComplete") is False,
        "semantic decision execution contract drifted",
    )
    require(
        isinstance(publication, Mapping)
        and publication.get("classificationFileName") == CLASSIFICATIONS_NAME
        and publication.get("resultFileName") == RESULT_NAME
        and publication.get("manifestFileName") == MANIFEST_NAME
        and publication.get("failureFileName") == FAILURE_NAME
        and publication.get("exclusiveNoReplacePublicationRequired") is True,
        "semantic decision publication contract drifted",
    )
    require(
        isinstance(personal, Mapping)
        and personal.get("executionPermitAuthenticationRequired") is False
        and personal.get("executionPermitDocumentRequired") is False
        and personal.get("externalIdentityProofRequired") is False
        and personal.get("repositoryOwnerAuthenticationRequired") is False
        and personal.get("userActionRequired") is False,
        "personal-project no-authentication boundary drifted",
    )
    require(
        isinstance(nonclaims, Mapping)
        and all(value is False for value in nonclaims.values()),
        "semantic decision non-claims drifted",
    )
    operation = document.get("operationBoundary")
    require(isinstance(operation, Mapping), "semantic decision operation boundary is absent")
    for key in (
        "archiveExtractionAllowed",
        "codeLoadingAllowed",
        "compilerInvocationAllowed",
        "dependencyInstallationAllowed",
        "deviceOperationAllowed",
        "dnsAllowed",
        "gitOperationAllowed",
        "networkAllowed",
        "packageManagerAllowed",
        "reviewedSourceExecutionAllowed",
        "shellAllowed",
        "socketCreationAllowed",
        "sourceMaterializationAllowed",
        "sourcePatchWriteAllowed",
        "subprocessAllowed",
    ):
        require(operation.get(key) is False, "semantic decision forbidden-operation boundary drifted")


def _validate_exact_bool_map(
    value: Any,
    *,
    required_false: Sequence[str],
    required_true: Sequence[str] = (),
) -> None:
    require(isinstance(value, Mapping), "boolean boundary must be an object")
    for key in required_false:
        require(value.get(key) is False, "a required false boundary drifted")
    for key in required_true:
        require(value.get(key) is True, "a required true boundary drifted")


def expected_unit_digest_rows() -> list[dict[str, Any]]:
    return [
        {
            "completeObservationSha256": digest,
            "patchUnit": patch_unit,
            "totalHitCount": total,
        }
        for patch_unit, total, digest, _rules in EXPECTED_UNIT_ROWS
    ]


def go_source_path_set_sha256(paths: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        raw = path.encode("utf-8", errors="strict")
        digest.update(struct.pack(">I", len(raw)))
        digest.update(raw)
    return digest.hexdigest()


def public_pass_record_binding(pass_id: str) -> dict[str, str]:
    return {
        "contentSha256": EXPECTED_PASS_RECORD_CONTENT_SHA256[pass_id],
        "passId": pass_id,
        "path": PASS_RECORD_PATHS[pass_id],
        "rawSha256": EXPECTED_PASS_RECORD_RAW_SHA256[pass_id],
        "recordId": EXPECTED_PASS_RECORD_IDS[pass_id],
    }


def candidate_semantic_binding(
    pass_id: str,
    candidate_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    require(pass_id in PASS_IDS, "candidate semantic pass ID is not fixed")
    rows = list(candidate_rows)
    digest = sha256_bytes(canonical_json_bytes(rows))
    require(
        len(rows) == EXPECTED_PASS_CANDIDATE_COUNTS[pass_id]
        and digest == EXPECTED_PASS_CANDIDATE_SEMANTIC_SHA256[pass_id],
        "pass candidate semantic digest or count drifted",
    )
    return {
        "algorithm": "sha256",
        "candidateCount": len(rows),
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": (
            "canonical_json_array_of_exact_pass_candidate_rows_in_pass_input_order"
        ),
        "sha256": digest,
    }


def public_pass_candidate_semantic_binding(pass_id: str) -> dict[str, Any]:
    return {
        "algorithm": "sha256",
        "candidateCount": EXPECTED_PASS_CANDIDATE_COUNTS[pass_id],
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "passId": pass_id,
        "scope": (
            "canonical_json_array_of_exact_pass_candidate_rows_in_pass_input_order"
        ),
        "sha256": EXPECTED_PASS_CANDIDATE_SEMANTIC_SHA256[pass_id],
    }


def validate_pass_record(
    document: Mapping[str, Any],
    *,
    pass_id: str,
    expected_candidate_semantic_binding: Mapping[str, Any],
    declaration: Mapping[str, Any],
    decision: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> None:
    require(pass_id in PASS_IDS, "semantic pass record pass ID is not fixed")
    validate_content_binding(
        document,
        expected_scope=f"{pass_id}_pass_record_without_contentBinding",
        expected_sha256=EXPECTED_PASS_RECORD_CONTENT_SHA256[pass_id],
        label=f"{pass_id} semantic pass record",
    )
    expected_keys = {
        "attempts",
        "candidateIds",
        "candidateSemanticBinding",
        "contentBinding",
        "coverage",
        "coverageAndCandidateRecordOnly",
        "dependencyBoundary",
        "documentType",
        "engineIdentityAttested",
        "inputBindings",
        "integrityLimitations",
        "locationValidationBoundary",
        "nonClaims",
        "oneUseZeroHitBoundary",
        "operationCounters",
        "passId",
        "passRecordId",
        "personalProjectBoundary",
        "recordContainsSecretValues",
        "recordContainsSourceBodies",
        "recordContainsSourceLineDigests",
        "recordIsAuthenticationAuthority",
        "recordIsSigned",
        "recordedDate",
        "reviewEngine",
        "reviewedGoSourcePathSet",
        "schemaVersion",
        "semanticJudgmentsIndependentlyReproducedByRecord",
        "status",
        "successfulAttempt",
        "writeBoundary",
    }
    require(set(document) == expected_keys, "semantic pass record schema drifted")
    require(
        document.get("documentType")
        == f"aetherlink.g2-pion-rung3-semantic-source-review-{pass_id}-pass-record"
        and document.get("schemaVersion") == "1.0"
        and document.get("passRecordId") == EXPECTED_PASS_RECORD_IDS[pass_id]
        and document.get("passId") == pass_id
        and document.get("recordedDate") == "2026-07-23"
        and document.get("status") == "pass_completed_recorded_non_attesting"
        and document.get("reviewEngine") == "gpt-5.6-sol",
        "semantic pass record identity drifted",
    )
    require(
        document.get("engineIdentityAttested") is False
        and document.get("recordIsAuthenticationAuthority") is False
        and document.get("recordIsSigned") is False
        and document.get("recordContainsSecretValues") is False
        and document.get("recordContainsSourceBodies") is False
        and document.get("recordContainsSourceLineDigests") is False
        and document.get("semanticJudgmentsIndependentlyReproducedByRecord") is False
        and document.get("coverageAndCandidateRecordOnly") is True,
        "semantic pass record non-attesting boundary drifted",
    )
    require(
        document.get("integrityLimitations") == INTEGRITY_LIMITATIONS
        and document.get("locationValidationBoundary")
        == LOCATION_VALIDATION_BOUNDARY,
        "semantic pass record integrity or location boundary drifted",
    )
    require(
        document.get("candidateSemanticBinding")
        == dict(expected_candidate_semantic_binding),
        "semantic pass record candidate binding drifted",
    )
    input_bindings = document.get("inputBindings")
    require(
        input_bindings
        == {
            "archive": {
                "bytes": EXPECTED_ARCHIVE_BYTES,
                "entryCount": EXPECTED_ENTRY_COUNT,
                "path": ARCHIVE_PATH,
                "rawSha256": EXPECTED_ARCHIVE_SHA256,
                "sourceTreeSha256": EXPECTED_SOURCE_TREE_SHA256,
            },
            "decision": {
                "contentSha256": EXPECTED_DECISION_CONTENT_SHA256,
                "path": DECISION_PATH,
                "rawSha256": EXPECTED_DECISION_RAW_SHA256,
            },
            "lexicalResult": {
                "contentSha256": (
                    "ceffb7b9856a5eca635f0f797d341796776a7221a124c97b85c65fc936b02d48"
                ),
                "path": f"{RUNG3}/offline-source-review-result-v3.json",
                "rawSha256": (
                    "ef4b8d88ec57501377a7bc9db066c04a1a379041ee1b11999f5d16c7d4447933"
                ),
            },
        }
        and decision.get("decisionId")
        == "g2-pion-ice-v4.3.0-rung3-semantic-source-review-decision-v1",
        "semantic pass record input bindings drifted",
    )
    coverage = document.get("coverage")
    require(
        coverage
        == {
            "allGoSourceBodiesReviewed": True,
            "allLexicalObservationsClassified": True,
            "defaultDisposition": "unresolved",
            "goSourceFileCount": snapshot["goSourceFileCount"],
            "goSourceLogicalLineCount": snapshot["goSourceLogicalLineCount"],
            "goSourceTotalBytes": snapshot["goSourceTotalBytes"],
            "lexicalObservationCount": observations["observationCount"],
            "lexicalRuleCount": 19,
            "observationSourceClassCounts": observations["sourceClassCounts"],
            "patchUnitCount": len(PATCH_UNITS),
            "sourceFileClassCounts": snapshot["sourceFileClassCounts"],
            "sourceTreeSha256": EXPECTED_SOURCE_TREE_SHA256,
            "unitDigests": expected_unit_digest_rows(),
            "verificationUnitCount": len(VERIFICATION_UNIT_IDS),
            "verificationUnitIds": list(VERIFICATION_UNIT_IDS),
        },
        "semantic pass record coverage drifted",
    )
    paths = sorted(snapshot["lineCounts"], key=lambda value: value.encode("utf-8"))
    path_set = document.get("reviewedGoSourcePathSet")
    require(
        path_set
        == {
            "count": len(paths),
            "order": "ascending_strict_utf8_path_bytes",
            "pathSetEncoding": "u32be_utf8_path_length_then_path_bytes_v1",
            "paths": paths,
            "sha256": go_source_path_set_sha256(paths),
        },
        "semantic pass record reviewed path set drifted",
    )
    require(
        document.get("attempts") == declaration.get("attempts")
        and document.get("successfulAttempt") == declaration.get("successfulAttempt")
        and document.get("candidateIds") == declaration.get("candidateIds"),
        "semantic pass record declaration crosswalk drifted",
    )
    expected_one_use = (
        {
            "handling": "missing_required_mechanism_gap",
            "hitCount": 0,
            "ruleId": "one-use",
            "vulnerabilityConclusionByItself": False,
        }
        if pass_id == "primary"
        else {
            "findingCandidateId": "I-GAP-ONE-USE",
            "handling": (
                "zero_lexical_hits_recorded_as_coverage_gap_not_vulnerability"
            ),
            "hitCount": 0,
            "ruleId": "one-use",
            "vulnerabilityConclusionByItself": False,
        }
    )
    require(
        document.get("oneUseZeroHitBoundary") == expected_one_use,
        "semantic pass record one-use boundary drifted",
    )
    require(
        document.get("dependencyBoundary")
        == {
            "dependencyClosureComplete": False,
            "dependencySourceReviewed": False,
            "goModRequireCount": EXPECTED_GO_MOD_REQUIRE_COUNT,
            "goSumRecordCount": EXPECTED_GO_SUM_RECORD_COUNT,
            "unresolvedDependencyBehaviorRemainsUnresolved": True,
        },
        "semantic pass record dependency boundary drifted",
    )
    require(
        document.get("operationCounters")
        == {
            "archiveOpenCountDuringRecordCreation": 0,
            "dependencyInstallationCount": 0,
            "deviceOperationCount": 0,
            "gitOperationCount": 0,
            "networkOperationCount": 0,
            "otherFileWriteCount": 0,
            "recordFileWriteCount": 1,
            "reviewedSourceCompilerInvocationCount": 0,
            "reviewedSourceExecutionCount": 0,
            "socketCreationCount": 0,
            "sourceMaterializationCount": 0,
            "sourcePatchWriteCount": 0,
        },
        "semantic pass record operation counters drifted",
    )
    require(
        document.get("writeBoundary")
        == {
            "onlyWrittenPath": PASS_RECORD_PATHS[pass_id],
            "otherFilesWritten": False,
            "writeMethod": "apply_patch",
        },
        "semantic pass record write boundary drifted",
    )
    require(
        document.get("personalProjectBoundary")
        == {
            "executionPermitAuthenticationRequired": False,
            "executionPermitDocumentRequired": False,
            "externalIdentityProofRequired": False,
            "modelIdentityIsNotAuthenticationAuthority": True,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "semantic pass record personal-project boundary drifted",
    )
    nonclaims = document.get("nonClaims")
    require(
        nonclaims
        == {
            "candidateSelected": False,
            "dependencyClosureComplete": False,
            "independentAttestationAuthorityEstablished": False,
            "librarySelected": False,
            "productionDeploymentAuthorized": False,
            "rungThreeComplete": False,
        },
        "semantic pass record non-claims drifted",
    )


def validate_pass_input(
    document: Mapping[str, Any],
    *,
    pass_records: Mapping[str, Mapping[str, Any]],
    decision: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validate_content_binding(
        document,
        expected_scope="pass_input_without_contentBinding",
        expected_sha256=EXPECTED_INPUT_CONTENT_SHA256,
        label="semantic pass input",
    )
    require(
        document.get("documentType")
        == "aetherlink.g2-pion-rung3-semantic-source-review-pass-input"
        and document.get("schemaVersion") == "1.0"
        and document.get("inputId")
        == "g2-pion-ice-v4.3.0-rung3-semantic-source-review-pass-input-v1",
        "semantic pass input identity drifted",
    )
    decision_binding = document.get("decisionBinding")
    require(
        isinstance(decision_binding, Mapping)
        and decision_binding.get("path") == DECISION_PATH
        and decision_binding.get("rawSha256") == EXPECTED_DECISION_RAW_SHA256
        and decision_binding.get("contentSha256") == EXPECTED_DECISION_CONTENT_SHA256
        and decision_binding.get("decisionId") == decision.get("decisionId"),
        "semantic pass input decision binding drifted",
    )
    _validate_exact_bool_map(
        document.get("personalProjectBoundary"),
        required_false=(
            "executionPermitAuthenticationRequired",
            "executionPermitDocumentRequired",
            "externalIdentityProofRequired",
            "repositoryOwnerAuthenticationRequired",
            "userActionRequired",
        ),
        required_true=("modelIdentityIsNotAuthenticationAuthority",),
    )
    nonclaims = document.get("nonClaims")
    require(
        isinstance(nonclaims, Mapping) and all(value is False for value in nonclaims.values()),
        "semantic pass input non-claims drifted",
    )
    dependency = document.get("dependencyBoundary")
    require(
        isinstance(dependency, Mapping)
        and dependency.get("dependencyClosureComplete") is False
        and dependency.get("dependencySourceReviewed") is False
        and dependency.get("goModRequireCount") == EXPECTED_GO_MOD_REQUIRE_COUNT
        and dependency.get("goSumRecordCount") == EXPECTED_GO_SUM_RECORD_COUNT,
        "semantic pass input dependency boundary drifted",
    )
    require(
        document.get("verificationUnitIds") == list(VERIFICATION_UNIT_IDS),
        "semantic pass input verification-unit order drifted",
    )
    require(
        document.get("unitDigests") == expected_unit_digest_rows(),
        "semantic pass input unit digests drifted",
    )
    require(
        document.get("candidateSemanticDigestContract")
        == CANDIDATE_SEMANTIC_DIGEST_CONTRACT
        and document.get("integrityLimitations") == INTEGRITY_LIMITATIONS
        and document.get("locationValidationBoundary")
        == LOCATION_VALIDATION_BOUNDARY,
        "semantic pass input digest, integrity, or location contract drifted",
    )
    expected_record_bindings = [
        public_pass_record_binding(pass_id) for pass_id in PASS_IDS
    ]
    require(
        document.get("passRecordBindings") == expected_record_bindings
        and set(pass_records) == set(PASS_IDS),
        "semantic pass record bindings drifted",
    )
    declarations = document.get("passDeclarations")
    require(
        isinstance(declarations, list)
        and len(declarations) == 2
        and [row.get("passId") for row in declarations] == list(PASS_IDS),
        "semantic pass declarations are missing or reordered",
    )
    declared_candidate_ids: dict[str, set[str]] = {}
    declarations_by_pass: dict[str, Mapping[str, Any]] = {}
    for declaration in declarations:
        pass_id = declaration["passId"]
        require(
            declaration.get("defaultDisposition") == "unresolved"
            and declaration.get("reviewEngine") == "gpt-5.6-sol"
            and declaration.get("engineIdentityAttested") is False,
            "semantic pass declaration boundary drifted",
        )
        coverage = declaration.get("coverage")
        require(
            isinstance(coverage, Mapping)
            and coverage.get("allGoSourceBodiesReviewed") is True
            and coverage.get("allLexicalObservationsClassified") is True
            and coverage.get("goSourceFileCount") == snapshot["goSourceFileCount"]
            and coverage.get("goSourceTotalBytes") == snapshot["goSourceTotalBytes"]
            and coverage.get("goSourceLogicalLineCount")
            == snapshot["goSourceLogicalLineCount"]
            and coverage.get("lexicalObservationCount")
            == observations["observationCount"]
            and coverage.get("sourceFileClassCounts")
            == snapshot["sourceFileClassCounts"]
            and coverage.get("observationSourceClassCounts")
            == observations["sourceClassCounts"]
            and coverage.get("sourceTreeSha256") == EXPECTED_SOURCE_TREE_SHA256,
            "semantic pass coverage declaration drifted",
        )
        attempts = declaration.get("attempts")
        successful_attempt = declaration.get("successfulAttempt")
        require(isinstance(attempts, list) and attempts, "semantic pass attempts are absent")
        expected_attempts = (
            [
                {
                    "archiveOpenCount": 1,
                    "attempt": 1,
                    "discardReason": None,
                    "publicationAttempted": False,
                    "status": "successful",
                }
            ]
            if pass_id == "primary"
            else [
                {
                    "archiveOpenCount": 1,
                    "attempt": 1,
                    "discardReason": (
                        "wrong_observation_order_discarded_before_publication"
                    ),
                    "publicationAttempted": False,
                    "status": "discarded",
                },
                {
                    "archiveOpenCount": 1,
                    "attempt": 2,
                    "discardReason": None,
                    "publicationAttempted": False,
                    "status": "successful",
                },
            ]
        )
        require(
            attempts == expected_attempts,
            "semantic pass attempt history drifted",
        )
        successful = [
            attempt
            for attempt in attempts
            if isinstance(attempt, Mapping) and attempt.get("status") == "successful"
        ]
        require(
            len(successful) == 1
            and successful[0].get("attempt") == successful_attempt
            and successful[0].get("archiveOpenCount") == 1
            and successful[0].get("publicationAttempted") is False,
            "semantic pass successful-attempt record drifted",
        )
        for attempt in attempts:
            require(
                isinstance(attempt, Mapping)
                and attempt.get("archiveOpenCount") == 1
                and attempt.get("publicationAttempted") is False
                and attempt.get("status") in {"successful", "discarded"},
                "semantic pass attempt record drifted",
            )
        ids = declaration.get("candidateIds")
        require(
            isinstance(ids, list)
            and ids
            and all(type(value) is str for value in ids)
            and len(ids) == len(set(ids)),
            "semantic pass candidate declaration drifted",
        )
        declared_candidate_ids[pass_id] = set(ids)
        declarations_by_pass[pass_id] = declaration

    candidates = document.get("candidateFindings")
    require(
        isinstance(candidates, list)
        and len(candidates) == 29
        and all(isinstance(candidate, dict) for candidate in candidates),
        "semantic candidate finding set drifted",
    )
    candidate_ids: set[str] = set()
    candidate_rows_by_pass: dict[str, list[dict[str, Any]]] = {
        pass_id: [] for pass_id in PASS_IDS
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    line_counts = snapshot["lineCounts"]
    for candidate in candidates:
        required_keys = {
            "candidateId",
            "canonicalInvariantId",
            "dedupGroupId",
            "dependencyBlocked",
            "findingKind",
            "locations",
            "originCandidateId",
            "passId",
            "patchUnits",
            "primarySink",
            "rationale",
            "reportedDisposition",
            "reportedInvariantId",
            "reportedSeverity",
            "requiredAction",
            "sourceClasses",
            "title",
            "verificationUnitIds",
        }
        require(set(candidate) == required_keys, "semantic candidate schema drifted")
        candidate_id = candidate["candidateId"]
        pass_id = candidate["passId"]
        group_id = candidate["dedupGroupId"]
        require(
            type(candidate_id) is str
            and candidate_id not in candidate_ids
            and pass_id in PASS_IDS
            and candidate_id in declared_candidate_ids[pass_id]
            and type(group_id) is str
            and group_id.startswith("G-")
            and candidate["reportedDisposition"] in DISPOSITIONS
            and candidate["reportedSeverity"] in SEVERITIES
            and type(candidate["dependencyBlocked"]) is bool,
            "semantic candidate identity or classification drifted",
        )
        candidate_ids.add(candidate_id)
        require(
            isinstance(candidate["patchUnits"], list)
            and len(candidate["patchUnits"]) == len(set(candidate["patchUnits"]))
            and all(unit in PATCH_UNITS for unit in candidate["patchUnits"])
            and isinstance(candidate["verificationUnitIds"], list)
            and len(candidate["verificationUnitIds"])
            == len(set(candidate["verificationUnitIds"]))
            and all(
                unit in VERIFICATION_UNIT_IDS
                for unit in candidate["verificationUnitIds"]
            )
            and isinstance(candidate["sourceClasses"], list)
            and candidate["sourceClasses"]
            and len(candidate["sourceClasses"])
            == len(set(candidate["sourceClasses"]))
            and all(
                source_class in CANDIDATE_SOURCE_CLASSES
                for source_class in candidate["sourceClasses"]
            ),
            "semantic candidate unit crosswalk drifted",
        )
        locations = candidate["locations"]
        require(isinstance(locations, list), "semantic candidate locations are invalid")
        for location in locations:
            require(
                isinstance(location, Mapping)
                and set(location) == {"endLine", "path", "startLine", "symbol"},
                "semantic candidate location schema drifted",
            )
            path = location["path"]
            start = location["startLine"]
            end = location["endLine"]
            require(
                type(path) is str
                and path in line_counts
                and type(start) is int
                and type(end) is int
                and 1 <= start <= end <= line_counts[path]
                and classify_source(path) in candidate["sourceClasses"],
                "semantic candidate location escaped the source snapshot",
            )
        primary_sink = candidate["primarySink"]
        if primary_sink is not None:
            require(
                isinstance(primary_sink, Mapping)
                and set(primary_sink) == {"line", "path", "symbol"}
                and primary_sink["path"] in line_counts
                and type(primary_sink["line"]) is int
                and 1 <= primary_sink["line"] <= line_counts[primary_sink["path"]],
                "semantic candidate primary sink is invalid",
            )
        candidate_rows_by_pass[pass_id].append(candidate)
        grouped.setdefault(group_id, []).append(candidate)
    candidates_by_id = {
        candidate["candidateId"]: candidate for candidate in candidates
    }
    expected_resolver_sink = {
        "line": 1074,
        "path": "gather.go",
        "symbol": "(*Agent).gatherCandidatesRelay",
    }
    require(
        candidates_by_id["P-SEM-002-PROMOTION"]["sourceClasses"]
        == ["production"]
        and candidates_by_id["P-SEM-007"]["primarySink"]
        == expected_resolver_sink
        and candidates_by_id["I-RESOLVE-001"]["primarySink"]
        == expected_resolver_sink
        and {
            "endLine": 1074,
            "path": "gather.go",
            "startLine": 1074,
            "symbol": "(*Agent).gatherCandidatesRelay",
        }
        in candidates_by_id["I-RESOLVE-001"]["locations"],
        "corrected production-class or resolver sink invariant drifted",
    )
    require(
        candidate_ids
        == declared_candidate_ids["primary"] | declared_candidate_ids["independent"]
        and not (
            declared_candidate_ids["primary"] & declared_candidate_ids["independent"]
        )
        and len(grouped) == 19,
        "semantic candidate declaration crosswalk drifted",
    )
    for pass_id in PASS_IDS:
        rows = candidate_rows_by_pass[pass_id]
        declaration = declarations_by_pass[pass_id]
        require(
            declaration.get("candidateIds")
            == [row["candidateId"] for row in rows],
            "semantic pass candidate input order drifted",
        )
        binding = candidate_semantic_binding(pass_id, rows)
        validate_pass_record(
            pass_records[pass_id],
            pass_id=pass_id,
            expected_candidate_semantic_binding=binding,
            declaration=declaration,
            decision=decision,
            snapshot=snapshot,
            observations=observations,
        )
    gap_rows = grouped.get("G-ONE-USE-GAP")
    require(
        isinstance(gap_rows, list)
        and len(gap_rows) == 2
        and {row["passId"] for row in gap_rows} == set(PASS_IDS)
        and all(
            row["findingKind"] == "missing_required_mechanism"
            and row["reportedDisposition"] == "unresolved"
            and row["reportedSeverity"] == "none"
            and row["locations"] == []
            and row["primarySink"] is None
            for row in gap_rows
        ),
        "zero-hit one-use mechanism gap is absent or overclaimed",
    )

    findings: list[dict[str, Any]] = []
    crosswalks: list[dict[str, Any]] = []
    by_path_line = observations["byPathLine"]
    for group_id in sorted(grouped, key=lambda value: value.encode("utf-8")):
        rows = sorted(grouped[group_id], key=lambda row: PASS_IDS.index(row["passId"]))
        require(
            len(rows) <= 2 and len({row["passId"] for row in rows}) == len(rows),
            "dedup group contains duplicate pass input",
        )
        first = rows[0]
        for row in rows[1:]:
            require(
                row["canonicalInvariantId"] == first["canonicalInvariantId"]
                and row["findingKind"] == first["findingKind"]
                and row["primarySink"] == first["primarySink"],
                "dedup group attempted a fuzzy semantic merge",
            )
        dispositions = [row["reportedDisposition"] for row in rows]
        final_disposition = (
            dispositions[0]
            if len(rows) == 2 and dispositions[0] == dispositions[1]
            else "unresolved"
        )
        severities = [row["reportedSeverity"] for row in rows]
        final_severity = min(severities, key=lambda value: SEVERITY_ORDER[value])
        identity_payload = canonical_json_bytes(
            {
                "canonicalInvariantId": first["canonicalInvariantId"],
                "findingKind": first["findingKind"],
                "primarySink": first["primarySink"],
            }
        )
        finding_id = (
            "G2SR1-F-"
            + hashlib.sha256(FINDING_ID_HASH_DOMAIN + identity_payload).hexdigest()[:20]
        )
        location_map: dict[tuple[str, int, int, str], dict[str, Any]] = {}
        linked_ids: set[str] = set()
        reports: list[dict[str, Any]] = []
        for row in rows:
            for location in row["locations"]:
                key = (
                    location["path"],
                    location["startLine"],
                    location["endLine"],
                    location["symbol"],
                )
                location_map[key] = dict(location)
                for line_number in range(location["startLine"], location["endLine"] + 1):
                    linked_ids.update(by_path_line.get((location["path"], line_number), ()))
            reports.append(
                {
                    "candidateId": row["candidateId"],
                    "passId": row["passId"],
                    "reportedDisposition": row["reportedDisposition"],
                    "reportedSeverity": row["reportedSeverity"],
                    "reportedInvariantId": row["reportedInvariantId"],
                    "title": row["title"],
                    "rationale": row["rationale"],
                    "requiredAction": row["requiredAction"],
                }
            )
        locations = [
            location_map[key]
            for key in sorted(
                location_map,
                key=lambda value: (
                    value[0].encode("utf-8"),
                    value[1],
                    value[2],
                    value[3].encode("utf-8"),
                ),
            )
        ]
        finding = {
            "findingId": finding_id,
            "dedupGroupId": group_id,
            "canonicalInvariantId": first["canonicalInvariantId"],
            "findingKind": first["findingKind"],
            "primarySink": first["primarySink"],
            "finalDisposition": final_disposition,
            "finalSeverity": final_severity,
            "dispositionAgreement": len(rows) == 2
            and dispositions[0] == dispositions[1],
            "severityAgreement": len(rows) == 2 and severities[0] == severities[1],
            "dependencyBlocked": any(row["dependencyBlocked"] for row in rows),
            "patchUnits": sorted(
                {unit for row in rows for unit in row["patchUnits"]},
                key=lambda value: PATCH_UNITS.index(value),
            ),
            "verificationUnitIds": sorted(
                {
                    unit
                    for row in rows
                    for unit in row["verificationUnitIds"]
                },
                key=lambda value: VERIFICATION_UNIT_IDS.index(value),
            ),
            "locations": locations,
            "passReports": reports,
        }
        findings.append(finding)
        crosswalks.append(
            {
                "findingId": finding_id,
                "linkedObservationCount": len(linked_ids),
                "linkedObservationIds": sorted(linked_ids),
                "locationCount": len(locations),
            }
        )
    resolution = next(
        finding for finding in findings if finding["dedupGroupId"] == "G-RESOLUTION-GATHER"
    )
    require(
        resolution["finalDisposition"] == "unresolved"
        and resolution["dispositionAgreement"] is False,
        "two-pass disagreement was not forced unresolved",
    )
    return findings, crosswalks


def assert_output_hygiene(value: Any) -> None:
    forbidden_keys = {
        "sourceBody",
        "sourceBytes",
        "sourceLine",
        "lineText",
        "lineSha256",
        "privateKey",
        "token",
        "passwordValue",
    }
    if isinstance(value, Mapping):
        require(not (set(value) & forbidden_keys), "output contains forbidden source or secret data")
        for key, child in value.items():
            require(type(key) is str, "output contains a non-string key")
            assert_output_hygiene(child)
    elif isinstance(value, list):
        for child in value:
            assert_output_hygiene(child)
    elif isinstance(value, str):
        require(
            not value.startswith("/")
            and os.fspath(ROOT) not in value
            and "BEGIN PRIVATE KEY" not in value,
            "output contains an absolute path or private material",
        )


def build_output_documents(
    *,
    runner_binding: Mapping[str, str],
    pass_record_bindings: Sequence[Mapping[str, str]],
    decision: Mapping[str, Any],
    pass_input: Mapping[str, Any],
    archive_metadata: os.stat_result,
    archive_inventory: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    observations: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    crosswalks: Sequence[Mapping[str, Any]],
) -> dict[str, bytes]:
    require(
        set(runner_binding) == {"path", "rawSha256"}
        and runner_binding.get("path") == RUNNER_PATH
        and isinstance(runner_binding.get("rawSha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", runner_binding["rawSha256"]) is not None,
        "runner byte binding drifted",
    )
    require(
        list(pass_record_bindings)
        == [public_pass_record_binding(pass_id) for pass_id in PASS_IDS],
        "output pass record bindings drifted",
    )
    pass_candidate_semantic_bindings: list[dict[str, Any]] = []
    for pass_id in PASS_IDS:
        rows = [
            row
            for row in pass_input["candidateFindings"]
            if row["passId"] == pass_id
        ]
        binding = candidate_semantic_binding(pass_id, rows)
        public_binding = {"passId": pass_id, **binding}
        require(
            public_binding == public_pass_candidate_semantic_binding(pass_id),
            "output candidate semantic binding drifted",
        )
        pass_candidate_semantic_bindings.append(public_binding)
    severity_counts = {severity: 0 for severity in ("P0", "P1", "P2", "P3", "none")}
    disposition_counts = {
        disposition: 0
        for disposition in (
            "false_positive",
            "acceptable_existing",
            "patch_required",
            "unresolved",
        )
    }
    for finding in findings:
        severity_counts[finding["finalSeverity"]] += 1
        disposition_counts[finding["finalDisposition"]] += 1
    require(severity_counts["P0"] == 0, "unexpected P0 semantic finding")
    require(
        sum(severity_counts.values()) == len(findings)
        and sum(disposition_counts.values()) == len(findings),
        "finding audit counters drifted",
    )
    public_patch_rows = observations["patchUnits"]
    classifications = content_bound(
        {
            "documentType": (
                "aetherlink.g2-pion-rung3-semantic-source-review-classifications"
            ),
            "schemaVersion": "1.0",
            "reviewId": "g2-pion-ice-v4.3.0-rung3-semantic-source-review-v1",
            "recordedDate": "2026-07-23",
            "status": "two_pass_semantic_classification_validated",
            "decisionBinding": {
                "path": DECISION_PATH,
                "rawSha256": EXPECTED_DECISION_RAW_SHA256,
                "contentSha256": EXPECTED_DECISION_CONTENT_SHA256,
            },
            "passInputBinding": {
                "path": PASS_INPUT_PATH,
                "rawSha256": EXPECTED_INPUT_RAW_SHA256,
                "contentSha256": EXPECTED_INPUT_CONTENT_SHA256,
            },
            "runnerBinding": dict(runner_binding),
            "passRecordBindings": [
                dict(binding) for binding in pass_record_bindings
            ],
            "passCandidateSemanticBindings": [
                dict(binding) for binding in pass_candidate_semantic_bindings
            ],
            "semanticJudgmentsIndependentlyReproducedByRunner": False,
            "passRecordsNonAttesting": True,
            "coverageAndLocationBoundsValidatedAgainstSnapshot": True,
            "integrityLimitations": dict(INTEGRITY_LIMITATIONS),
            "locationValidationBoundary": dict(LOCATION_VALIDATION_BOUNDARY),
            "postRunEvidenceBoundary": dict(POST_RUN_EVIDENCE_BOUNDARY),
            "archiveSnapshot": {
                "path": ARCHIVE_PATH,
                "rawSha256": EXPECTED_ARCHIVE_SHA256,
                "bytes": archive_metadata.st_size,
                "entryCount": archive_inventory["entryCount"],
                "entryBodyReadCount": archive_inventory["entryBodyReadCount"],
                "sourceTreeSha256": archive_inventory["sourceTreeSha256"],
                "filesystemExtracted": False,
                "reviewedSourceExecuted": False,
            },
            "observationClassification": {
                "complete": True,
                "passIds": list(PASS_IDS),
                "defaultDispositionByPass": {
                    "primary": "unresolved",
                    "independent": "unresolved",
                },
                "classificationRule": (
                    "every_complete_observation_defaults_unresolved_in_each_pass_"
                    "unless_an_exact_semantic_record_applies"
                ),
                "observationCountPerPass": {
                    "primary": observations["observationCount"],
                    "independent": observations["observationCount"],
                },
                "observationSetSha256": observations["observationSetSha256"],
                "observationIdsUnique": observations["observationIdsUnique"],
                "sourceClassCounts": observations["sourceClassCounts"],
                "patchUnits": public_patch_rows,
                "candidateCrosswalks": list(crosswalks),
                "sourceBodiesPublished": False,
                "sourceLineDigestsPublished": False,
            },
            "candidateClassification": {
                "inputCandidateCount": len(pass_input["candidateFindings"]),
                "deduplicatedFindingCount": len(findings),
                "deduplicationRule": (
                    "exact_canonical_invariant_finding_kind_and_primary_sink_only"
                ),
                "disagreementRule": "force_unresolved",
                "severityCounts": severity_counts,
                "dispositionCounts": disposition_counts,
                "findings": list(findings),
            },
            "dependencyBoundary": {
                "dependencySourceReviewed": False,
                "dependencyClosureComplete": False,
                "goModRequireCount": EXPECTED_GO_MOD_REQUIRE_COUNT,
                "goSumRecordCount": EXPECTED_GO_SUM_RECORD_COUNT,
            },
            "personalProjectBoundary": {
                "externalIdentityProofRequired": False,
                "repositoryOwnerAuthenticationRequired": False,
                "executionPermitAuthenticationRequired": False,
                "executionPermitDocumentRequired": False,
                "userActionRequired": False,
            },
            "nonClaims": {
                "candidateSelected": False,
                "dependencyClosureComplete": False,
                "librarySelected": False,
                "productionDeploymentAuthorized": False,
                "rungThreeComplete": False,
            },
        },
        "classifications_without_contentBinding",
    )
    result = content_bound(
        {
            "documentType": "aetherlink.g2-pion-rung3-semantic-source-review-result",
            "schemaVersion": "1.0",
            "reviewId": "g2-pion-ice-v4.3.0-rung3-semantic-source-review-v1",
            "recordedDate": "2026-07-23",
            "status": "rung3_semantic_source_review_v1_executed_semantic_closure_blocked",
            "result": (
                "two_pass_100_file_4701_observation_review_recorded_"
                "findings_and_dependency_gaps_remain"
            ),
            "nextAction": (
                "prepare_versioned_rung3_patch_and_dependency_closure_decision"
            ),
            "decisionBinding": {
                "path": DECISION_PATH,
                "rawSha256": EXPECTED_DECISION_RAW_SHA256,
                "contentSha256": EXPECTED_DECISION_CONTENT_SHA256,
            },
            "passInputBinding": {
                "path": PASS_INPUT_PATH,
                "rawSha256": EXPECTED_INPUT_RAW_SHA256,
                "contentSha256": EXPECTED_INPUT_CONTENT_SHA256,
            },
            "runnerBinding": dict(runner_binding),
            "passRecordBindings": [
                dict(binding) for binding in pass_record_bindings
            ],
            "passCandidateSemanticBindings": [
                dict(binding) for binding in pass_candidate_semantic_bindings
            ],
            "semanticJudgmentsIndependentlyReproducedByRunner": False,
            "passRecordsNonAttesting": True,
            "coverageAndLocationBoundsValidatedAgainstSnapshot": True,
            "integrityLimitations": dict(INTEGRITY_LIMITATIONS),
            "locationValidationBoundary": dict(LOCATION_VALIDATION_BOUNDARY),
            "postRunEvidenceBoundary": dict(POST_RUN_EVIDENCE_BOUNDARY),
            "coverage": {
                "semanticSourceReviewPerformed": True,
                "reviewPassCount": 2,
                "goSourceFileCount": snapshot["goSourceFileCount"],
                "goSourceBodyReadCount": snapshot["goSourceBodyReadCount"],
                "goSourceTotalBytes": snapshot["goSourceTotalBytes"],
                "goSourceLogicalLineCount": snapshot["goSourceLogicalLineCount"],
                "sourceFileClassCounts": snapshot["sourceFileClassCounts"],
                "lexicalObservationCount": observations["observationCount"],
                "observationSourceClassCounts": observations["sourceClassCounts"],
                "patchUnitCount": len(PATCH_UNITS),
                "lexicalRuleCount": 19,
                "verificationUnitCount": len(VERIFICATION_UNIT_IDS),
            },
            "findingAudit": {
                "inputCandidateCount": len(pass_input["candidateFindings"]),
                "deduplicatedFindingCount": len(findings),
                "severityCounts": severity_counts,
                "dispositionCounts": disposition_counts,
                "oneUseMissingMechanismGapRecorded": True,
                "disagreementsForcedUnresolved": True,
            },
            "closure": {
                "semanticClosureComplete": False,
                "dependencySourceReviewed": False,
                "dependencyClosureComplete": False,
                "rungThreeComplete": False,
                "candidateSelected": False,
                "librarySelected": False,
            },
            "personalProjectBoundary": {
                "externalIdentityProofRequired": False,
                "repositoryOwnerAuthenticationRequired": False,
                "executionPermitAuthenticationRequired": False,
                "executionPermitDocumentRequired": False,
                "userActionRequired": False,
            },
        },
        "result_without_contentBinding",
    )
    classifications_payload = canonical_json_bytes(classifications)
    result_payload = canonical_json_bytes(result)
    require(
        len(classifications_payload) <= MAXIMUM_JSON_BYTES
        and len(result_payload) <= MAXIMUM_JSON_BYTES,
        "semantic output exceeds its JSON bound",
    )
    manifest = content_bound(
        {
            "documentType": "aetherlink.g2-pion-rung3-semantic-source-review-manifest",
            "schemaVersion": "1.0",
            "reviewId": "g2-pion-ice-v4.3.0-rung3-semantic-source-review-v1",
            "recordedDate": "2026-07-23",
            "status": "semantic_review_atomic_commit_marker_checker_pending",
            "runnerBinding": dict(runner_binding),
            "passRecordBindings": [
                dict(binding) for binding in pass_record_bindings
            ],
            "passCandidateSemanticBindings": [
                dict(binding) for binding in pass_candidate_semantic_bindings
            ],
            "semanticJudgmentsIndependentlyReproducedByRunner": False,
            "passRecordsNonAttesting": True,
            "coverageAndLocationBoundsValidatedAgainstSnapshot": True,
            "integrityLimitations": dict(INTEGRITY_LIMITATIONS),
            "locationValidationBoundary": dict(LOCATION_VALIDATION_BOUNDARY),
            "postRunEvidenceBoundary": dict(POST_RUN_EVIDENCE_BOUNDARY),
            "artifacts": [
                {
                    "name": CLASSIFICATIONS_NAME,
                    "bytes": len(classifications_payload),
                    "rawSha256": sha256_bytes(classifications_payload),
                    "publicationOrder": 1,
                },
                {
                    "name": RESULT_NAME,
                    "bytes": len(result_payload),
                    "rawSha256": sha256_bytes(result_payload),
                    "publicationOrder": 2,
                },
            ],
            "publicationContract": {
                "manifestRole": "atomic_commit_marker",
                "classificationsAndResultFullSetReadbackCompletedBeforeCommitMarker": True,
                "perArtifactStagingAndFinalReadbackRequired": True,
                "postCommitFullSetReadbackAttemptRequiredBeforeSuccessfulRunnerReturn": True,
                "postCommitFullSetReadbackCompletionPersistedByManifest": False,
                "failureArtifactMayBePublishedAfterCommitMarker": True,
                "commitMarkerPresenceAloneIsFinalSuccessEvidence": False,
                "independentPostRunCheckerRequiredForFinalSuccessEvidence": True,
            },
            "transactionalPublicationBoundary": {
                "exclusiveNoReplace": True,
                "mode": "0600",
                "overwriteAllowed": False,
                "finalArtifactDeletionAllowed": False,
                "fixedStagingNamesRequired": True,
                "atomicNoReplaceHardLinkPromotionRequired": True,
                "successfulPromotionStagingUnlinkRequired": True,
            },
            "preCommitOperationCounters": {
                "runnerStableReadCount": 1,
                "decisionStableReadCount": 1,
                "passInputStableReadCount": 1,
                "passRecordStableReadCount": 2,
                "archiveOpenCount": 1,
                "archiveReadPassCount": 1,
                "zipEntryBodyReadCount": archive_inventory["entryBodyReadCount"],
                "goSourceBodyReadCount": snapshot["goSourceBodyReadCount"],
                "semanticPassValidationCount": 2,
                "classificationsCreateCount": 1,
                "resultCreateCount": 1,
                "dataArtifactStagingCreateCount": 2,
                "dataArtifactAtomicNoReplaceHardLinkPromotionCount": 2,
                "dataArtifactStagingUnlinkCount": 2,
                "classificationsAndResultFullSetReadbackCount": 1,
                "finalArtifactDeletionCount": 0,
            },
            "nonClaims": {
                "postRunReproductionPerformed": False,
                "postCommitFullSetReadbackCompletionPersistedByManifest": False,
                "independentPostRunCheckerCompleted": False,
                "finalSuccessEvidenceEstablished": False,
                "dependencyClosureComplete": False,
                "rungThreeComplete": False,
                "candidateSelected": False,
                "librarySelected": False,
            },
            "personalProjectBoundary": {
                "externalIdentityProofRequired": False,
                "repositoryOwnerAuthenticationRequired": False,
                "executionPermitAuthenticationRequired": False,
                "executionPermitDocumentRequired": False,
                "userActionRequired": False,
            },
        },
        "manifest_without_contentBinding",
    )
    manifest_payload = canonical_json_bytes(manifest)
    require(len(manifest_payload) <= MAXIMUM_JSON_BYTES, "manifest exceeds its JSON bound")
    documents = {
        CLASSIFICATIONS_NAME: classifications_payload,
        RESULT_NAME: result_payload,
        MANIFEST_NAME: manifest_payload,
    }
    for payload in documents.values():
        assert_output_hygiene(strict_json(payload, "generated semantic artifact"))
    return documents


def read_and_build(root: Path = ROOT) -> tuple[dict[str, bytes], dict[str, Any]]:
    runner_raw, _runner_metadata = read_stable_relative_file(
        root,
        RUNNER_PATH,
        maximum_bytes=MAXIMUM_JSON_BYTES,
    )
    decision_raw, _decision_metadata = read_stable_relative_file(
        root,
        DECISION_PATH,
        maximum_bytes=MAXIMUM_JSON_BYTES,
        expected_sha256=EXPECTED_DECISION_RAW_SHA256,
    )
    pass_input_raw, _input_metadata = read_stable_relative_file(
        root,
        PASS_INPUT_PATH,
        maximum_bytes=MAXIMUM_JSON_BYTES,
        expected_sha256=EXPECTED_INPUT_RAW_SHA256,
    )
    pass_record_raw: dict[str, bytes] = {}
    for pass_id in PASS_IDS:
        raw, _metadata = read_stable_relative_file(
            root,
            PASS_RECORD_PATHS[pass_id],
            maximum_bytes=MAXIMUM_JSON_BYTES,
            expected_sha256=EXPECTED_PASS_RECORD_RAW_SHA256[pass_id],
        )
        pass_record_raw[pass_id] = raw
    decision = strict_json(decision_raw, "semantic decision")
    pass_input = strict_json(pass_input_raw, "semantic pass input")
    pass_records = {
        pass_id: strict_json(pass_record_raw[pass_id], f"{pass_id} semantic pass record")
        for pass_id in PASS_IDS
    }
    validate_decision(decision)
    archive_raw, archive_metadata = read_stable_relative_file(
        root,
        ARCHIVE_PATH,
        maximum_bytes=MAXIMUM_ARCHIVE_BYTES,
        expected_bytes=EXPECTED_ARCHIVE_BYTES,
        expected_sha256=EXPECTED_ARCHIVE_SHA256,
        required_mode=0o600,
    )
    entries, archive_inventory = inspect_retained_archive(archive_raw)
    go_sources, snapshot = build_go_snapshot(entries)
    observations = aggregate_observations(go_sources)
    findings, crosswalks = validate_pass_input(
        pass_input,
        pass_records=pass_records,
        decision=decision,
        snapshot=snapshot,
        observations=observations,
    )
    documents = build_output_documents(
        runner_binding={
            "path": RUNNER_PATH,
            "rawSha256": sha256_bytes(runner_raw),
        },
        pass_record_bindings=[
            public_pass_record_binding(pass_id) for pass_id in PASS_IDS
        ],
        decision=decision,
        pass_input=pass_input,
        archive_metadata=archive_metadata,
        archive_inventory=archive_inventory,
        snapshot=snapshot,
        observations=observations,
        findings=findings,
        crosswalks=crosswalks,
    )
    finding_severity_counts = {
        severity: sum(
            finding["finalSeverity"] == severity for finding in findings
        )
        for severity in ("P0", "P1", "P2", "P3", "none")
    }
    finding_disposition_counts = {
        disposition: sum(
            finding["finalDisposition"] == disposition for finding in findings
        )
        for disposition in (
            "false_positive",
            "acceptable_existing",
            "patch_required",
            "unresolved",
        )
    }
    summary = {
        "status": "semantic_review_v1_check_passed",
        "runnerStableReadCount": 1,
        "passRecordStableReadCount": 2,
        "runnerBinding": {
            "path": RUNNER_PATH,
            "rawSha256": sha256_bytes(runner_raw),
        },
        "passRecordBindings": [
            public_pass_record_binding(pass_id) for pass_id in PASS_IDS
        ],
        "passCandidateSemanticBindings": [
            public_pass_candidate_semantic_binding(pass_id)
            for pass_id in PASS_IDS
        ],
        "semanticJudgmentsIndependentlyReproducedByRunner": False,
        "passRecordsNonAttesting": True,
        "coverageAndLocationBoundsValidatedAgainstSnapshot": True,
        "integrityLimitations": dict(INTEGRITY_LIMITATIONS),
        "locationValidationBoundary": dict(LOCATION_VALIDATION_BOUNDARY),
        "postRunEvidenceBoundary": dict(POST_RUN_EVIDENCE_BOUNDARY),
        "archiveOpenCount": 1,
        "archiveReadPassCount": 1,
        "zipEntryBodyReadCount": archive_inventory["entryBodyReadCount"],
        "goSourceBodyReadCount": snapshot["goSourceBodyReadCount"],
        "goSourceFileCount": snapshot["goSourceFileCount"],
        "goSourceTotalBytes": snapshot["goSourceTotalBytes"],
        "goSourceLogicalLineCount": snapshot["goSourceLogicalLineCount"],
        "sourceFileClassCounts": snapshot["sourceFileClassCounts"],
        "lexicalObservationCount": observations["observationCount"],
        "observationSourceClassCounts": observations["sourceClassCounts"],
        "patchUnitCount": len(PATCH_UNITS),
        "lexicalRuleCount": 19,
        "semanticPassValidationCount": 2,
        "inputCandidateCount": len(pass_input["candidateFindings"]),
        "deduplicatedFindingCount": len(findings),
        "findingSeverityCounts": finding_severity_counts,
        "findingDispositionCounts": finding_disposition_counts,
        "dependencyClosureComplete": False,
        "semanticClosureComplete": False,
        "candidateSelected": False,
        "librarySelected": False,
        "rungThreeComplete": False,
        "externalIdentityProofRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "userActionRequired": False,
        "artifactBytes": {
            name: len(payload) for name, payload in documents.items()
        },
        "fileWriteCount": 0,
    }
    return documents, summary


def open_output_directory(root: Path) -> int:
    parent_fd, name = open_relative_parent(root, RUNG3)
    directory_fd = -1
    try:
        directory_fd = os.open(name, directory_open_flags(), dir_fd=parent_fd)
        validate_directory_descriptor(directory_fd, "semantic output directory")
        result = directory_fd
        directory_fd = -1
        return result
    except OSError as error:
        raise PublicationError("unable to open the semantic output directory") from error
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)
        os.close(parent_fd)


def output_name_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise PublicationError("unable to inspect an output name") from error
    return True


def preflight_output_absence(directory_fd: int) -> None:
    for name in RESERVED_OUTPUT_NAMES:
        require(
            not output_name_exists(directory_fd, name),
            "semantic output preflight found an existing reserved name",
        )


def write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise PublicationError("short exclusive publication write")
        offset += written


def write_staging_readback(
    directory_fd: int,
    staging_name: str,
    payload: bytes,
) -> tuple[int, int]:
    require(
        staging_name in STAGING_NAMES.values(),
        "publication staging target is not fixed",
    )
    require(len(payload) <= MAXIMUM_JSON_BYTES, "publication payload exceeds its bound")
    fd = -1
    try:
        fd = os.open(
            staging_name,
            create_file_flags(),
            mode=0o600,
            dir_fd=directory_fd,
        )
        os.fchmod(fd, 0o600)
        write_all(fd, payload)
        os.fsync(fd)
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid()
            and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o600
            and before.st_size == len(payload),
            "staging artifact metadata drifted",
        )
        os.lseek(fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = len(payload) + 1
        while remaining > 0:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        readback = b"".join(chunks)
        after = os.fstat(fd)
        require(
            readback == payload
            and before.st_dev == after.st_dev
            and before.st_ino == after.st_ino
            and before.st_mode == after.st_mode
            and before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns
            and before.st_ctime_ns == after.st_ctime_ns,
            "staging artifact failed stable byte readback",
        )
        named = os.stat(staging_name, dir_fd=directory_fd, follow_symlinks=False)
        require(
            stat.S_ISREG(named.st_mode)
            and named.st_dev == after.st_dev
            and named.st_ino == after.st_ino,
            "staging artifact name no longer identifies its descriptor",
        )
        os.fsync(directory_fd)
        return after.st_dev, after.st_ino
    except FileExistsError as error:
        raise PublicationError("exclusive staging creation lost a name race") from error
    except OSError as error:
        raise PublicationError("exclusive staging creation failed") from error
    finally:
        if fd >= 0:
            os.close(fd)


def verify_published_payload(
    directory_fd: int,
    name: str,
    payload: bytes,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, int]:
    require(name in OUTPUT_NAMES, "published verification target is not fixed")
    fd = -1
    try:
        fd = os.open(name, file_open_flags(), dir_fd=directory_fd)
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid()
            and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o600
            and before.st_size == len(payload),
            "published artifact metadata drifted",
        )
        identity = (before.st_dev, before.st_ino)
        if expected_identity is not None:
            require(
                identity == expected_identity,
                "published artifact inode identity drifted",
            )
        chunks: list[bytes] = []
        remaining = len(payload) + 1
        while remaining > 0:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        readback = b"".join(chunks)
        after = os.fstat(fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        require(
            readback == payload
            and all(
                getattr(before, field) == getattr(after, field)
                for field in stable_fields
            ),
            "published artifact failed full stable byte readback",
        )
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        require(
            stat.S_ISREG(named.st_mode)
            and named.st_dev == after.st_dev
            and named.st_ino == after.st_ino
            and named.st_nlink == 1,
            "published artifact name no longer identifies its descriptor",
        )
        return identity
    except OSError as error:
        raise PublicationError("published artifact verification failed") from error
    finally:
        if fd >= 0:
            os.close(fd)


def promote_staging_no_replace(
    directory_fd: int,
    staging_name: str,
    final_name: str,
    payload: bytes,
    expected_identity: tuple[int, int],
) -> tuple[int, int]:
    require(
        final_name in OUTPUT_NAMES
        and STAGING_NAMES[final_name] == staging_name,
        "staging promotion target is not fixed",
    )
    try:
        staged = os.stat(staging_name, dir_fd=directory_fd, follow_symlinks=False)
        require(
            stat.S_ISREG(staged.st_mode)
            and staged.st_uid == os.getuid()
            and staged.st_nlink == 1
            and stat.S_IMODE(staged.st_mode) == 0o600
            and staged.st_size == len(payload)
            and (staged.st_dev, staged.st_ino) == expected_identity,
            "staging artifact drifted before promotion",
        )
        os.link(
            staging_name,
            final_name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        linked_staging = os.stat(
            staging_name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        linked_final = os.stat(
            final_name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        require(
            (linked_staging.st_dev, linked_staging.st_ino) == expected_identity
            and (linked_final.st_dev, linked_final.st_ino) == expected_identity
            and linked_staging.st_nlink == 2
            and linked_final.st_nlink == 2,
            "atomic hard-link promotion identity drifted",
        )
        os.unlink(staging_name, dir_fd=directory_fd)
        os.fsync(directory_fd)
        return verify_published_payload(
            directory_fd,
            final_name,
            payload,
            expected_identity=expected_identity,
        )
    except FileExistsError as error:
        raise PublicationError("atomic no-replace promotion lost a destination race") from error
    except OSError as error:
        raise PublicationError("atomic no-replace promotion failed") from error


def publish_one_transactional(
    directory_fd: int,
    name: str,
    payload: bytes,
) -> tuple[int, int]:
    require(name in OUTPUT_NAMES, "transactional publication target is not fixed")
    staging_name = STAGING_NAMES[name]
    identity = write_staging_readback(directory_fd, staging_name, payload)
    return promote_staging_no_replace(
        directory_fd,
        staging_name,
        name,
        payload,
        identity,
    )


def verify_payload_set(
    directory_fd: int,
    names: Sequence[str],
    documents: Mapping[str, bytes],
    identities: Mapping[str, tuple[int, int]],
) -> None:
    for name in names:
        verify_published_payload(
            directory_fd,
            name,
            documents[name],
            expected_identity=identities[name],
        )


def failure_document(
    stage: str,
    observed_names: Sequence[str],
    successfully_read_back_names: Sequence[str],
    *,
    runner_binding: Mapping[str, str],
    pass_record_bindings: Sequence[Mapping[str, str]],
    pass_candidate_semantic_bindings: Sequence[Mapping[str, Any]],
) -> bytes:
    document = content_bound(
        {
            "documentType": (
                "aetherlink.g2-pion-rung3-semantic-source-review-execution-failure"
            ),
            "schemaVersion": "1.0",
            "reviewId": "g2-pion-ice-v4.3.0-rung3-semantic-source-review-v1",
            "recordedDate": "2026-07-23",
            "status": "partial_publication_failure_recorded_no_retry_or_overwrite",
            "failureStage": stage,
            "errorCategory": "exclusive_publication_incomplete",
            "observedOutputNames": list(observed_names),
            "successfullyReadBackArtifactNames": list(successfully_read_back_names),
            "automaticRetryAllowed": False,
            "overwriteAllowed": False,
            "finalArtifactDeletionAllowed": False,
            "failedStagingOrFinalCleanupAllowed": False,
            "exceptionTextPublished": False,
            "sourceBodyPublished": False,
            "absolutePathPublished": False,
            "runnerBinding": dict(runner_binding),
            "passRecordBindings": [
                dict(binding) for binding in pass_record_bindings
            ],
            "passCandidateSemanticBindings": [
                dict(binding) for binding in pass_candidate_semantic_bindings
            ],
            "semanticJudgmentsIndependentlyReproducedByRunner": False,
            "passRecordsNonAttesting": True,
            "coverageAndLocationBoundsValidatedAgainstSnapshot": True,
            "integrityLimitations": dict(INTEGRITY_LIMITATIONS),
            "locationValidationBoundary": dict(LOCATION_VALIDATION_BOUNDARY),
            "postRunEvidenceBoundary": dict(POST_RUN_EVIDENCE_BOUNDARY),
            "commitMarkerObservedBeforeFailureRecord": (
                MANIFEST_NAME in observed_names
            ),
            "failureArtifactMayFollowCommitMarker": True,
            "commitMarkerPresenceAloneIsFinalSuccessEvidence": False,
            "postCommitFullSetReadbackCompletionPersistedByCommitMarker": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "executionPermitAuthenticationRequired": False,
            "executionPermitDocumentRequired": False,
            "userActionRequired": False,
        },
        "execution_failure_without_contentBinding",
    )
    payload = canonical_json_bytes(document)
    require(len(payload) <= MAXIMUM_JSON_BYTES, "failure artifact exceeds its bound")
    return payload


def publish_documents(root: Path, documents: Mapping[str, bytes]) -> dict[str, Any]:
    require(
        tuple(documents) == (CLASSIFICATIONS_NAME, RESULT_NAME, MANIFEST_NAME),
        "publication document order drifted",
    )
    parsed = {
        name: strict_json(documents[name], f"publication {name}")
        for name in (CLASSIFICATIONS_NAME, RESULT_NAME, MANIFEST_NAME)
    }
    runner_binding = parsed[CLASSIFICATIONS_NAME].get("runnerBinding")
    pass_record_bindings = parsed[CLASSIFICATIONS_NAME].get("passRecordBindings")
    pass_candidate_semantic_bindings = parsed[CLASSIFICATIONS_NAME].get(
        "passCandidateSemanticBindings"
    )
    require(
        isinstance(runner_binding, Mapping)
        and isinstance(pass_record_bindings, list)
        and isinstance(pass_candidate_semantic_bindings, list)
        and all(
            parsed[name].get("runnerBinding") == runner_binding
            and parsed[name].get("passRecordBindings") == pass_record_bindings
            and parsed[name].get("passCandidateSemanticBindings")
            == pass_candidate_semantic_bindings
            and parsed[name].get(
                "semanticJudgmentsIndependentlyReproducedByRunner"
            )
            is False
            and parsed[name].get("passRecordsNonAttesting") is True
            and parsed[name].get(
                "coverageAndLocationBoundsValidatedAgainstSnapshot"
            )
            is True
            and parsed[name].get("integrityLimitations")
            == INTEGRITY_LIMITATIONS
            and parsed[name].get("locationValidationBoundary")
            == LOCATION_VALIDATION_BOUNDARY
            and parsed[name].get("postRunEvidenceBoundary")
            == POST_RUN_EVIDENCE_BOUNDARY
            for name in (CLASSIFICATIONS_NAME, RESULT_NAME, MANIFEST_NAME)
        ),
        "publication evidence bindings or transparency boundary drifted",
    )
    require(
        pass_record_bindings
        == [public_pass_record_binding(pass_id) for pass_id in PASS_IDS],
        "publication pass record bindings drifted",
    )
    require(
        pass_candidate_semantic_bindings
        == [
            public_pass_candidate_semantic_binding(pass_id)
            for pass_id in PASS_IDS
        ],
        "publication pass candidate semantic bindings drifted",
    )
    expected_manifest_artifacts = [
        {
            "name": name,
            "bytes": len(documents[name]),
            "rawSha256": sha256_bytes(documents[name]),
            "publicationOrder": order,
        }
        for order, name in enumerate(
            (CLASSIFICATIONS_NAME, RESULT_NAME),
            start=1,
        )
    ]
    require(
        parsed[MANIFEST_NAME].get("artifacts") == expected_manifest_artifacts,
        "publication manifest artifact bindings drifted",
    )
    directory_fd = open_output_directory(root)
    try:
        preflight_output_absence(directory_fd)
        completed: list[str] = []
        identities: dict[str, tuple[int, int]] = {}
        current_stage = "preflight"
        try:
            for current_stage, name in (
                ("classifications", CLASSIFICATIONS_NAME),
                ("result", RESULT_NAME),
            ):
                identities[name] = publish_one_transactional(
                    directory_fd,
                    name,
                    documents[name],
                )
                completed.append(name)
            current_stage = "pre_commit_marker_full_set_readback"
            verify_payload_set(
                directory_fd,
                (CLASSIFICATIONS_NAME, RESULT_NAME),
                documents,
                identities,
            )
            current_stage = "commit_marker"
            identities[MANIFEST_NAME] = publish_one_transactional(
                directory_fd,
                MANIFEST_NAME,
                documents[MANIFEST_NAME],
            )
            completed.append(MANIFEST_NAME)
            current_stage = "post_commit_full_set_readback"
            verify_payload_set(
                directory_fd,
                (CLASSIFICATIONS_NAME, RESULT_NAME, MANIFEST_NAME),
                documents,
                identities,
            )
            require(
                not output_name_exists(directory_fd, FAILURE_NAME)
                and all(
                    not output_name_exists(directory_fd, staging_name)
                    for staging_name in STAGING_NAMES.values()
                ),
                "successful publication retained failure or staging state",
            )
            os.fsync(directory_fd)
        except BaseException as error:
            observed = [
                name
                for name in RESERVED_OUTPUT_NAMES
                if output_name_exists(directory_fd, name)
            ]
            if (
                observed
                and not output_name_exists(directory_fd, FAILURE_NAME)
                and not output_name_exists(
                    directory_fd,
                    STAGING_NAMES[FAILURE_NAME],
                )
            ):
                try:
                    publish_one_transactional(
                        directory_fd,
                        FAILURE_NAME,
                        failure_document(
                            current_stage,
                            observed,
                            completed,
                            runner_binding=runner_binding,
                            pass_record_bindings=pass_record_bindings,
                            pass_candidate_semantic_bindings=(
                                pass_candidate_semantic_bindings
                            ),
                        ),
                    )
                except BaseException:
                    pass
            if isinstance(error, PublicationError):
                raise
            raise PublicationError("semantic publication stopped after partial state") from error
        require(
            completed == [CLASSIFICATIONS_NAME, RESULT_NAME, MANIFEST_NAME],
            "commit-marker publication did not complete",
        )
        return {
            "status": (
                "semantic_review_v1_commit_marker_published_"
                "post_commit_readback_passed_checker_pending"
            ),
            "publishedArtifactNames": completed,
            "commitMarkerPublished": True,
            "commitMarkerPublishedAfterDataArtifacts": True,
            "postCommitFullSetReadbackCompleted": True,
            "failureArtifactPublished": False,
            "independentPostRunCheckerCompleted": False,
            "finalSuccessEvidenceEstablished": False,
            "fileWriteCount": 3,
            "failureFileWriteCount": 0,
            "overwriteCount": 0,
            "stagingCreateCount": 3,
            "atomicNoReplaceHardLinkPromotionCount": 3,
            "stagingUnlinkCount": 3,
            "finalArtifactDeletionCount": 0,
        }
    finally:
        os.close(directory_fd)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or exclusively publish the rung-three semantic review",
        allow_abbrev=False,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--publish", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    require_isolated_interpreter()
    arguments = parse_arguments(argv)
    try:
        documents, summary = read_and_build(ROOT)
        if arguments.check:
            summary["mode"] = "check"
            summary["publicationAttempted"] = False
            sys.stdout.buffer.write(canonical_json_bytes(summary))
            return 0
        publication = publish_documents(ROOT, documents)
        publication.update(
            {
                "mode": "publish",
                "archiveOpenCount": summary["archiveOpenCount"],
                "archiveReadPassCount": summary["archiveReadPassCount"],
                "goSourceBodyReadCount": summary["goSourceBodyReadCount"],
                "lexicalObservationCount": summary["lexicalObservationCount"],
                "externalIdentityProofRequired": False,
                "repositoryOwnerAuthenticationRequired": False,
                "userActionRequired": False,
            }
        )
        sys.stdout.buffer.write(canonical_json_bytes(publication))
        return 0
    except ReviewError:
        failure = {
            "status": "semantic_review_v1_failed_closed",
            "errorCode": "bounded_validation_or_exclusive_publication_failed",
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
        }
        sys.stderr.buffer.write(canonical_json_bytes(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
