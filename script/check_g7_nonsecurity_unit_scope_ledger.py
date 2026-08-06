#!/usr/bin/env python3
"""Validate the reviewed local non-security G7 unit-test scope ledger.

The ledger is a review record, not an oracle for the semantic judgement in each
row.  This checker proves that the record is canonical, exhaustive for the
current Swift and Android-core discoveries, bound to the reviewed source bytes,
and (with ``--evidence``) that every locally eligible identity is present in the
already independently checked execution manifests.

The Android evidence path validates the owner-only binding records and their
eligible testcase manifests. It does not reopen the raw JUnit XML, run-marker,
or source-input bytes; the separately ordered product-CI readback owns that
check.

It deliberately does not import the G7 producer or product-CI checker.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
LEDGER_RELATIVE_PATH = Path("script/g7_nonsecurity_unit_scope_ledger_v1.json")
SWIFT_TEST_LIST_RELATIVE_PATH = Path(
    ".build/aetherlink-product-ci-swift-test-list-v1.txt"
)
SWIFT_PARENT_RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-current-run-v1/"
    "parent-result.json"
)
ANDROID_BINDING_RELATIVE_PATHS = {
    "protocol": Path(
        "apps/android/core/protocol/build/test-results/testDebugUnitTest/"
        "aetherlink-core-nonsecurity-test-result-binding-v1.json"
    ),
    "transport": Path(
        "apps/android/core/transport/build/test-results/testDebugUnitTest/"
        "aetherlink-core-nonsecurity-test-result-binding-v1.json"
    ),
}

SCHEMA_VERSION = 1
SCOPE = "aetherlink-g7-local-nonsecurity-unit-scope-ledger-v1"
SOURCE_ALGORITHM = "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
SWIFT_DISCOVERY_COUNT = 2_175
SWIFT_DISCOVERY_MANIFEST_SHA256 = (
    "a8121a99615da2b2b5b39535f5a8fb0ee03bf48fc2a4773d0aced5bac4a5041a"
)
ANDROID_CORE_DISCOVERY_COUNT = 595
ANDROID_CORE_DISCOVERY_MANIFEST_SHA256 = (
    "bb7668ee064063af3755c20b8eb1986e98aeedb3a69477e844840b26a051afb4"
)

# Updated only after the complete reviewed ledger has been generated and read
# back.  Keeping these pins in a checker separate from the data prevents an
# edited ledger from silently becoming the accepted review record.
LEDGER_BYTES = 1_859_933
LEDGER_SHA256 = "d5ed9eaff8dd7820b97e65a104d94fd59ebba16a9d611782e5d5cc739d1e8d49"

MAXIMUM_LEDGER_BYTES = 4 * 1024 * 1024
MAXIMUM_SOURCE_FILE_BYTES = 32 * 1024 * 1024
MAXIMUM_SOURCE_TOTAL_BYTES = 512 * 1024 * 1024
MAXIMUM_EVIDENCE_BYTES = 4 * 1024 * 1024

ELIGIBLE_DISPOSITIONS = frozenset(
    {
        "eligible_nonsecurity_no_socket",
        "eligible_nonsecurity_local_socket",
    }
)
EXCLUDED_DISPOSITIONS = frozenset(
    {
        "excluded_security_auth_crypto",
        "excluded_external_network_live_provider",
        "excluded_device_os",
    }
)
DISPOSITIONS = ELIGIBLE_DISPOSITIONS | EXCLUDED_DISPOSITIONS
REASON_CODES = frozenset(
    {
        "reviewed_no_socket_execution",
        "reviewed_local_socket_execution",
        "security_auth_crypto_execution_path",
        "external_network_or_live_provider_execution_path",
        "device_or_os_integration_execution_path",
    }
)
EXPECTED_REASON_BY_DISPOSITION = {
    "eligible_nonsecurity_no_socket": "reviewed_no_socket_execution",
    "eligible_nonsecurity_local_socket": "reviewed_local_socket_execution",
    "excluded_security_auth_crypto": "security_auth_crypto_execution_path",
    "excluded_external_network_live_provider": (
        "external_network_or_live_provider_execution_path"
    ),
    "excluded_device_os": "device_or_os_integration_execution_path",
}
AUDIT_REASONS_BY_PLATFORM_DISPOSITION = {
    "swift": {
        "eligible_nonsecurity_no_socket": frozenset(
            {
                "historical_reviewed_execution",
                "pure_swift_task_cancellation_helper_only",
            }
        ),
        "eligible_nonsecurity_local_socket": frozenset(
            {"historical_reviewed_execution"}
        ),
        "excluded_security_auth_crypto": frozenset(
            {"security_auth_crypto_scope"}
        ),
        "excluded_external_network_live_provider": frozenset(
            {"live_provider_required", "network_relay_transport_scope"}
        ),
        "excluded_device_os": frozenset(),
    },
    "androidCore": {
        "eligible_nonsecurity_no_socket": frozenset(
            {
                "in_memory_frame_writer_no_route_or_socket",
                "injected_cleanup_no_android_service_or_socket",
                "injected_fake_socket_no_os_network",
                "local_protocol_codec_or_product_schema",
                "pure_endpoint_value_validation",
                "pure_saturating_arithmetic",
            }
        ),
        "eligible_nonsecurity_local_socket": frozenset(),
        "excluded_security_auth_crypto": frozenset(
            {
                "anti_replay_security_window",
                "discovery_route_token_identity_or_metadata_security",
                "p2p_address_admission_security_policy",
                "p2p_identity_proof_readiness_state",
                "p2p_pairing_crypto_route_or_authorization_contract",
                "p2p_route_security_preparation",
                "paired_identity_route_or_production_secure_composition",
                "pairing_auth_relay_route_or_transport_binding_protocol",
                "pairing_identity_proof_key_or_authority_state",
                "relay_route_registration_auth_or_crypto",
                "relay_route_secret_or_security_preparation",
                "secure_channel_auth_crypto_or_authority_lifecycle",
                "security_hardening_parser_path_or_storage_boundary",
                "trusted_source_grant_or_authorization_mixed_protocol",
            }
        ),
        "excluded_external_network_live_provider": frozenset(
            {"opens_loopback_server_socket"}
        ),
        "excluded_device_os": frozenset(),
    },
}
CLAIMS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeAndroidUnitSuiteClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "localNonsecurityUnitScopeClassified": True,
    "securityAuthenticationCryptographyExecuted": False,
    "v1Claimed": False,
}

SWIFT_IDENTITY_PATTERN = re.compile(
    r"(?P<module>[A-Za-z0-9_]+Tests)\."
    r"(?P<class>[A-Za-z0-9_]+Tests)/(?P<method>test[A-Za-z0-9_]+)"
)
ANDROID_IDENTITY_PATTERN = re.compile(
    r"(?P<module>pairing|protocol|transport):"
    r"(?P<class>com\.localagentbridge\.android\.core\."
    r"[A-Za-z0-9_.]+Test)\.(?P<method>[A-Za-z0-9_]+)"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SOURCE_PATH_PATTERN = re.compile(r"[A-Za-z0-9_.+/-]+")
SYMBOL_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_:.+-]*")
AUDIT_REASON_PATTERN = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")


class ScopeLedgerError(RuntimeError):
    """Raised when the scope ledger or its execution evidence fails closed."""


@dataclass(frozen=True)
class HeldFile:
    path: Path
    descriptor: int
    initial_stat: os.stat_result


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def manifest_sha256(values: Iterable[str]) -> str:
    payload = json.dumps(
        sorted(values),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def android_binding_manifest_sha256(
    entries: Iterable[Mapping[str, object]],
) -> str:
    pairs = sorted(
        (entry["className"], entry["methodName"])
        for entry in entries
    )
    return hashlib.sha256(
        json.dumps(pairs, ensure_ascii=True, separators=(",", ":")).encode(
            "ascii"
        )
    ).hexdigest()


def stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def open_held_file(
    path: Path,
    *,
    maximum_bytes: int,
    expected_mode: int | None = None,
    owner_only: bool = False,
) -> HeldFile:
    absolute = path.absolute()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as error:
        raise ScopeLedgerError(
            f"cannot open a file without following links: {path}: {error}"
        ) from error
    try:
        status = os.fstat(descriptor)
        mode = stat.S_IMODE(status.st_mode)
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_nlink != 1
            or status.st_size <= 0
            or status.st_size > maximum_bytes
        ):
            raise ScopeLedgerError(
                f"file must be a bounded single-link regular file: {path}"
            )
        if expected_mode is not None and mode != expected_mode:
            raise ScopeLedgerError(
                f"file mode differs for {path}: expected {expected_mode:04o}"
            )
        if owner_only and (status.st_uid != os.getuid() or mode != 0o600):
            raise ScopeLedgerError(
                f"evidence must be owner-only mode 0600: {path}"
            )
        return HeldFile(absolute, descriptor, status)
    except BaseException:
        os.close(descriptor)
        raise


def read_held_file(held: HeldFile, *, maximum_bytes: int) -> bytes:
    os.lseek(held.descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(held.descriptor, 64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > maximum_bytes:
            raise ScopeLedgerError(f"file exceeds its byte limit: {held.path}")
        chunks.append(chunk)
    raw = b"".join(chunks)
    if len(raw) != held.initial_stat.st_size:
        raise ScopeLedgerError(f"file size changed during read: {held.path}")
    return raw


def require_held_file_unchanged(held: HeldFile) -> None:
    try:
        descriptor_status = os.fstat(held.descriptor)
        path_status = os.lstat(held.path)
    except OSError as error:
        raise ScopeLedgerError(
            f"cannot complete file identity readback: {held.path}: {error}"
        ) from error
    if (
        stat_identity(descriptor_status) != stat_identity(held.initial_stat)
        or stat_identity(path_status) != stat_identity(held.initial_stat)
    ):
        raise ScopeLedgerError(f"file identity changed around read: {held.path}")


def read_stable_file(
    path: Path,
    *,
    maximum_bytes: int,
    expected_mode: int | None = None,
    owner_only: bool = False,
) -> tuple[bytes, int]:
    held = open_held_file(
        path,
        maximum_bytes=maximum_bytes,
        expected_mode=expected_mode,
        owner_only=owner_only,
    )
    try:
        raw = read_held_file(held, maximum_bytes=maximum_bytes)
        require_held_file_unchanged(held)
        return raw, stat.S_IMODE(held.initial_stat.st_mode)
    finally:
        os.close(held.descriptor)


def parse_canonical_json(raw: bytes, label: str) -> dict[str, object]:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ScopeLedgerError(f"{label} has a duplicate key: {key}")
            result[key] = value
        return result

    try:
        text = raw.decode("ascii")
        value = json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ScopeLedgerError(
                    f"{label} contains a non-finite number: {token}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ScopeLedgerError(f"{label} is not canonical ASCII JSON: {error}") from error
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        raise ScopeLedgerError(f"{label} bytes are not canonical ASCII JSON")
    return value


def closed_mapping(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise ScopeLedgerError(f"{label} has a different closed schema")
    return value


def exact_int(
    value: object,
    label: str,
    *,
    minimum: int = 0,
) -> int:
    if type(value) is not int or value < minimum:
        raise ScopeLedgerError(f"{label} must be an exact integer >= {minimum}")
    return value


def exact_sha256(value: object, label: str) -> str:
    if type(value) is not str or SHA256_PATTERN.fullmatch(value) is None:
        raise ScopeLedgerError(f"{label} must be a lowercase SHA-256")
    return value


def exact_ascii(value: object, label: str, pattern: re.Pattern[str]) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ScopeLedgerError(f"{label} is not a canonical ASCII value")
    return value


def source_relative_paths(root: Path) -> tuple[Path, ...]:
    candidates: set[Path] = {Path("Package.swift")}
    macos_root = root / "apps/macos"
    if not macos_root.is_dir():
        raise ScopeLedgerError("apps/macos source root is missing")
    for path in macos_root.rglob("*"):
        relative = path.relative_to(root)
        if any(
            component in {".build", ".swiftpm", "build", "DerivedData"}
            for component in relative.parts
        ):
            continue
        if path.is_symlink():
            raise ScopeLedgerError(
                f"reviewed macOS source closure contains a symlink: {relative}"
            )
        if path.is_file():
            candidates.add(relative)

    android_core_root = root / "apps/android/core"
    if not android_core_root.is_dir():
        raise ScopeLedgerError("apps/android/core source root is missing")
    for path in android_core_root.rglob("*"):
        relative = path.relative_to(root)
        if "build" in relative.parts or ".gradle" in relative.parts:
            continue
        if path.is_symlink():
            raise ScopeLedgerError(
                f"reviewed Android source closure contains a symlink: {relative}"
            )
        if path.is_file():
            candidates.add(relative)
    for relative in (
        Path("apps/android/build.gradle.kts"),
        Path("apps/android/settings.gradle.kts"),
        Path("apps/android/gradle.properties"),
        Path("apps/android/gradle/libs.versions.toml"),
    ):
        if (root / relative).is_file():
            candidates.add(relative)
    return tuple(sorted(candidates, key=lambda item: item.as_posix().encode("ascii")))


def source_closure(root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    total_bytes = 0
    paths = source_relative_paths(root)
    for relative in paths:
        absolute = root / relative
        raw, mode = read_stable_file(
            absolute,
            maximum_bytes=MAXIMUM_SOURCE_FILE_BYTES,
        )
        total_bytes += len(raw)
        if total_bytes > MAXIMUM_SOURCE_TOTAL_BYTES:
            raise ScopeLedgerError("reviewed source closure exceeds its byte limit")
        file_sha256 = hashlib.sha256(raw).hexdigest()
        digest.update(relative.as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(f"{mode:04o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(str(len(raw)).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_sha256.encode("ascii"))
        digest.update(b"\n")
    return {
        "algorithm": SOURCE_ALGORITHM,
        "fileCount": len(paths),
        "sha256": digest.hexdigest(),
        "totalBytes": total_bytes,
    }


def swift_discovery(
    root: Path,
    test_list_relative_path: Path = SWIFT_TEST_LIST_RELATIVE_PATH,
) -> tuple[str, ...]:
    raw, _ = read_stable_file(
        root / test_list_relative_path,
        maximum_bytes=4 * 1024 * 1024,
        owner_only=True,
    )
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ScopeLedgerError(f"Swift discovery is not ASCII: {error}") from error
    if not text.endswith("\n") or "\r" in text:
        raise ScopeLedgerError("Swift discovery must use canonical LF lines")
    raw_identities = tuple(text.splitlines())
    if (
        not raw_identities
        or len(set(raw_identities)) != len(raw_identities)
        or any(
            SWIFT_IDENTITY_PATTERN.fullmatch(identity) is None
            for identity in raw_identities
        )
    ):
        raise ScopeLedgerError("Swift discovery identities are not canonical and unique")
    return tuple(sorted(raw_identities))


def kotlin_code_projection(source: str) -> str:
    """Mask Kotlin comments and literals while preserving source offsets."""

    projected = list(source)
    index = 0
    length = len(source)
    while index < length:
        if source.startswith("//", index):
            end = source.find("\n", index + 2)
            if end < 0:
                end = length
            for position in range(index, end):
                projected[position] = " "
            index = end
            continue
        if source.startswith("/*", index):
            start = index
            depth = 1
            index += 2
            while index < length and depth:
                if source.startswith("/*", index):
                    depth += 1
                    index += 2
                elif source.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                raise ScopeLedgerError("Android core test source has an open comment")
            for position in range(start, index):
                if projected[position] != "\n":
                    projected[position] = " "
            continue
        if source.startswith('"""', index):
            start = index
            end = source.find('"""', index + 3)
            if end < 0:
                raise ScopeLedgerError("Android core test source has an open raw string")
            index = end + 3
            while index < length and source[index] == '"':
                index += 1
            for position in range(start, index):
                if projected[position] != "\n":
                    projected[position] = " "
            continue
        if source[index] in {'"', "'"}:
            start = index
            quote = source[index]
            index += 1
            escaped = False
            while index < length:
                character = source[index]
                index += 1
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    break
            else:
                raise ScopeLedgerError("Android core test source has an open literal")
            for position in range(start, index):
                if projected[position] != "\n":
                    projected[position] = " "
            continue
        index += 1
    return "".join(projected)


def android_core_discovery(root: Path) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    test_root = root / "apps/android/core"
    paths = sorted(
        test_root.glob("*/src/test/**/*.kt"),
        key=lambda item: item.relative_to(root).as_posix().encode("ascii"),
    )
    if not paths:
        raise ScopeLedgerError("Android core test sources are missing")
    for path in paths:
        relative = path.relative_to(root)
        raw, _ = read_stable_file(path, maximum_bytes=MAXIMUM_SOURCE_FILE_BYTES)
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ScopeLedgerError(
                f"Android core test source is not UTF-8: {relative}: {error}"
            ) from error
        code = kotlin_code_projection(source)
        package_match = re.search(
            r"(?m)^package\s+([A-Za-z0-9_.]+)\s*$",
            code,
        )
        class_name = path.stem
        if (
            package_match is None
            or re.search(
                rf"(?m)^\s*(?:internal\s+|public\s+|private\s+)?"
                rf"(?:open\s+)?class\s+{re.escape(class_name)}\b",
                code,
            )
            is None
        ):
            raise ScopeLedgerError(
                f"Android core test class cannot be reconstructed: {relative}"
            )
        methods = re.findall(
            r"@(?:[A-Za-z_][A-Za-z0-9_]*\.)*Test\b"
            r"(?:\s*\(\s*\))?"
            r"(?:\s|@[A-Za-z_][A-Za-z0-9_.]*(?:\([^)]*\))?)*"
            r"(?:(?:public|internal|private|protected|open|final|abstract|"
            r"override|suspend|inline|tailrec|operator|infix|external)\s+)*"
            r"fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            code,
        )
        if not methods or len(methods) != len(set(methods)):
            raise ScopeLedgerError(
                f"Android core @Test methods are missing or duplicated: {relative}"
            )
        module = relative.parts[3]
        qualified_class = f"{package_match.group(1)}.{class_name}"
        for method in methods:
            rows.append(
                {
                    "className": qualified_class,
                    "identity": f"{module}:{qualified_class}.{method}",
                    "methodName": method,
                    "module": module,
                    "sourcePath": relative.as_posix(),
                }
            )
    rows.sort(key=lambda row: row["identity"].encode("ascii"))
    identities = [row["identity"] for row in rows]
    if len(identities) != len(set(identities)):
        raise ScopeLedgerError("Android core discovery contains duplicate identities")
    return tuple(rows)


def source_text(root: Path, relative: str) -> str:
    raw, _ = read_stable_file(
        root / relative,
        maximum_bytes=MAXIMUM_SOURCE_FILE_BYTES,
    )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ScopeLedgerError(
            f"ledger sourcePath is not UTF-8: {relative}: {error}"
        ) from error


def validate_entries(
    value: object,
    *,
    platform: str,
    discovered: Sequence[str],
    source_by_identity: Mapping[str, str],
    root: Path,
) -> tuple[dict[str, object], ...]:
    if type(value) is not list or len(value) != len(discovered):
        raise ScopeLedgerError(f"{platform} ledger entry count differs from discovery")
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    cached_sources: dict[str, str] = {}
    expected_order = list(discovered)
    for index, item in enumerate(value):
        label = f"{platform}.entries[{index}]"
        row = closed_mapping(
            item,
            {
                "auditReasonCode",
                "className",
                "disposition",
                "identity",
                "methodName",
                "reasonCode",
                "sourcePath",
                "triggerSymbols",
            },
            label,
        )
        identity_pattern = (
            SWIFT_IDENTITY_PATTERN if platform == "swift" else ANDROID_IDENTITY_PATTERN
        )
        identity = exact_ascii(row["identity"], f"{label}.identity", identity_pattern)
        if identity != expected_order[index]:
            raise ScopeLedgerError(f"{platform} ledger identities are not exact sorted discovery")
        if identity in seen:
            raise ScopeLedgerError(f"{platform} ledger identity is duplicated: {identity}")
        seen.add(identity)
        match = identity_pattern.fullmatch(identity)
        assert match is not None
        class_name = exact_ascii(
            row["className"],
            f"{label}.className",
            re.compile(r"[A-Za-z0-9_.]+Tests?|[A-Za-z0-9_.]+Test"),
        )
        method_name = exact_ascii(
            row["methodName"],
            f"{label}.methodName",
            re.compile(r"(?:test)?[A-Za-z0-9_]+"),
        )
        expected_class = match.group("class")
        expected_method = match.group("method")
        if class_name != expected_class or method_name != expected_method:
            raise ScopeLedgerError(f"{label} class or method projection differs")
        source_path = exact_ascii(
            row["sourcePath"],
            f"{label}.sourcePath",
            SOURCE_PATH_PATTERN,
        )
        if source_path != source_by_identity[identity]:
            raise ScopeLedgerError(f"{label} sourcePath differs from discovery mapping")
        disposition = row["disposition"]
        reason_code = row["reasonCode"]
        audit_reason_code = exact_ascii(
            row["auditReasonCode"],
            f"{label}.auditReasonCode",
            AUDIT_REASON_PATTERN,
        )
        if type(disposition) is not str or disposition not in DISPOSITIONS:
            raise ScopeLedgerError(f"{label}.disposition is not allowed")
        if type(reason_code) is not str or reason_code not in REASON_CODES:
            raise ScopeLedgerError(f"{label}.reasonCode is not allowed")
        if EXPECTED_REASON_BY_DISPOSITION[disposition] != reason_code:
            raise ScopeLedgerError(f"{label} disposition and reasonCode disagree")
        if audit_reason_code not in AUDIT_REASONS_BY_PLATFORM_DISPOSITION[
            platform
        ][disposition]:
            raise ScopeLedgerError(
                f"{label} disposition and auditReasonCode disagree"
            )
        symbols = row["triggerSymbols"]
        if (
            type(symbols) is not list
            or not symbols
            or len(symbols) > 16
            or any(
                type(symbol) is not str
                or SYMBOL_PATTERN.fullmatch(symbol) is None
                for symbol in symbols
            )
            or len(symbols) != len(set(symbols))
            or symbols[0] != method_name
        ):
            raise ScopeLedgerError(f"{label}.triggerSymbols are not canonical")
        if source_path not in cached_sources:
            cached_sources[source_path] = source_text(root, source_path)
        source = cached_sources[source_path]
        if method_name not in source:
            raise ScopeLedgerError(f"{label} method is absent from its sourcePath")
        missing_symbols = [symbol for symbol in symbols if symbol not in source]
        if missing_symbols:
            raise ScopeLedgerError(
                f"{label}.triggerSymbols are absent from sourcePath: "
                f"{missing_symbols}"
            )
        entries.append(dict(row))
    return tuple(entries)


def validate_discovery_record(
    value: object,
    *,
    label: str,
    identities: Sequence[str],
    expected_count: int,
    expected_manifest_sha256: str,
) -> None:
    row = closed_mapping(value, {"manifestSha256", "tests"}, label)
    count = exact_int(row["tests"], f"{label}.tests", minimum=1)
    digest = exact_sha256(row["manifestSha256"], f"{label}.manifestSha256")
    actual_digest = manifest_sha256(identities)
    if (
        count != len(identities)
        or digest != actual_digest
        or count != expected_count
        or digest != expected_manifest_sha256
    ):
        raise ScopeLedgerError(f"{label} differs from current pinned discovery")


def read_and_validate_ledger(
    *,
    root: Path = ROOT,
    ledger_relative_path: Path = LEDGER_RELATIVE_PATH,
    test_list_relative_path: Path = SWIFT_TEST_LIST_RELATIVE_PATH,
    require_pin: bool = True,
) -> tuple[dict[str, object], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    raw, _ = read_stable_file(
        root / ledger_relative_path,
        maximum_bytes=MAXIMUM_LEDGER_BYTES,
        expected_mode=0o644,
    )
    if require_pin and (
        len(raw) != LEDGER_BYTES or hashlib.sha256(raw).hexdigest() != LEDGER_SHA256
    ):
        raise ScopeLedgerError("scope ledger byte identity differs from its checker pin")
    ledger = parse_canonical_json(raw, "scope ledger")
    row = closed_mapping(
        ledger,
        {
            "androidCore",
            "claims",
            "review",
            "schemaVersion",
            "scope",
            "sourceClosure",
            "swift",
        },
        "scope ledger",
    )
    if exact_int(row["schemaVersion"], "schemaVersion", minimum=1) != SCHEMA_VERSION:
        raise ScopeLedgerError("scope ledger schemaVersion differs")
    if row["scope"] != SCOPE:
        raise ScopeLedgerError("scope ledger scope differs")
    claims = closed_mapping(row["claims"], set(CLAIMS), "claims")
    for key, expected in CLAIMS.items():
        if type(claims[key]) is not bool or claims[key] is not expected:
            raise ScopeLedgerError(f"claims.{key} differs")
    review = closed_mapping(
        row["review"],
        {"method", "reviewedAt", "reviewerModel", "semanticJudgementReproduced"},
        "review",
    )
    if review != {
        "method": "per-test-source-and-execution-path-review-v1",
        "reviewedAt": "2026-08-03",
        "reviewerModel": "gpt-5.6-sol",
        "semanticJudgementReproduced": False,
    }:
        raise ScopeLedgerError("scope ledger review metadata differs")
    closure = closed_mapping(
        row["sourceClosure"],
        {"algorithm", "fileCount", "sha256", "totalBytes"},
        "sourceClosure",
    )
    exact_int(closure["fileCount"], "sourceClosure.fileCount", minimum=1)
    exact_int(closure["totalBytes"], "sourceClosure.totalBytes", minimum=1)
    exact_sha256(closure["sha256"], "sourceClosure.sha256")
    if closure["algorithm"] != SOURCE_ALGORITHM or closure != source_closure(root):
        raise ScopeLedgerError("scope ledger source closure differs from current source")

    swift_identities = swift_discovery(root, test_list_relative_path)
    swift_section = closed_mapping(row["swift"], {"discovery", "entries"}, "swift")
    validate_discovery_record(
        swift_section["discovery"],
        label="swift.discovery",
        identities=swift_identities,
        expected_count=SWIFT_DISCOVERY_COUNT,
        expected_manifest_sha256=SWIFT_DISCOVERY_MANIFEST_SHA256,
    )

    swift_source_map: dict[str, str] = {}
    swift_test_paths = tuple(
        path
        for path in source_relative_paths(root)
        if path.suffix == ".swift" and "Tests" in path.parts
    )
    swift_source_cache = {
        path.as_posix(): source_text(root, path.as_posix())
        for path in swift_test_paths
    }
    swift_class_paths: dict[str, set[str]] = {}
    swift_method_paths: dict[str, set[str]] = {}
    for path, source in swift_source_cache.items():
        for class_name in re.findall(
            r"\b(?:class|extension)\s+([A-Za-z0-9_]+)\b",
            source,
        ):
            swift_class_paths.setdefault(class_name, set()).add(path)
        for method_name in re.findall(
            r"\bfunc\s+(test[A-Za-z0-9_]+)\s*\(",
            source,
        ):
            swift_method_paths.setdefault(method_name, set()).add(path)
    for identity in swift_identities:
        match = SWIFT_IDENTITY_PATTERN.fullmatch(identity)
        assert match is not None
        method = match.group("method")
        class_name = match.group("class")
        candidates = sorted(
            swift_class_paths.get(class_name, set())
            & swift_method_paths.get(method, set())
        )
        if len(candidates) != 1:
            raise ScopeLedgerError(
                f"Swift discovery source mapping is not unique: {identity}: {candidates}"
            )
        swift_source_map[identity] = candidates[0]
    swift_entries = validate_entries(
        swift_section["entries"],
        platform="swift",
        discovered=swift_identities,
        source_by_identity=swift_source_map,
        root=root,
    )

    android_rows = android_core_discovery(root)
    android_identities = tuple(row["identity"] for row in android_rows)
    android_section = closed_mapping(
        row["androidCore"], {"discovery", "entries"}, "androidCore"
    )
    validate_discovery_record(
        android_section["discovery"],
        label="androidCore.discovery",
        identities=android_identities,
        expected_count=ANDROID_CORE_DISCOVERY_COUNT,
        expected_manifest_sha256=ANDROID_CORE_DISCOVERY_MANIFEST_SHA256,
    )
    android_source_map = {
        item["identity"]: item["sourcePath"] for item in android_rows
    }
    android_entries = validate_entries(
        android_section["entries"],
        platform="androidCore",
        discovered=android_identities,
        source_by_identity=android_source_map,
        root=root,
    )
    return ledger, swift_entries, android_entries


def read_evidence_json(root: Path, relative: Path, label: str) -> dict[str, object]:
    raw, _ = read_stable_file(
        root / relative,
        maximum_bytes=MAXIMUM_EVIDENCE_BYTES,
        owner_only=True,
    )
    return parse_canonical_json(raw, label)


def validate_swift_evidence(
    root: Path,
    entries: Sequence[Mapping[str, object]],
) -> None:
    result = read_evidence_json(
        root,
        SWIFT_PARENT_RESULT_RELATIVE_PATH,
        "Swift parent result",
    )
    row = closed_mapping(
        result,
        {
            "artifacts",
            "contract",
            "coverage",
            "execution",
            "limitations",
            "result",
            "schemaVersion",
            "sourceInputs",
        },
        "Swift parent result",
    )
    if (
        row["contract"] != "aetherlink-g7-nonsecurity-merge-full-current-parent-v1"
        or row["result"] != "passed"
        or type(row["schemaVersion"]) is not int
        or row["schemaVersion"] != 1
    ):
        raise ScopeLedgerError("Swift parent result identity or status differs")
    limitations = row["limitations"]
    if type(limitations) is not dict or any(
        type(value) is not bool for value in limitations.values()
    ):
        raise ScopeLedgerError("Swift parent limitations are not exact booleans")
    for false_claim in (
        "canonicalG7ExitClaimed",
        "canonicalMergeFullClaimed",
        "completeSwiftSuiteClaimed",
        "securityAuthenticationOrCryptographyExecuted",
        "v1Claimed",
    ):
        if limitations.get(false_claim) is not False:
            raise ScopeLedgerError(f"Swift parent falsely changes {false_claim}")
    coverage = row["coverage"]
    if type(coverage) is not dict:
        raise ScopeLedgerError("Swift parent coverage is not an object")
    eligible = tuple(
        entry["identity"]
        for entry in entries
        if entry["disposition"] in ELIGIBLE_DISPOSITIONS
    )
    no_socket = tuple(
        entry["identity"]
        for entry in entries
        if entry["disposition"] == "eligible_nonsecurity_no_socket"
    )
    local_socket = tuple(
        entry["identity"]
        for entry in entries
        if entry["disposition"] == "eligible_nonsecurity_local_socket"
    )
    excluded = tuple(
        entry["identity"]
        for entry in entries
        if entry["disposition"] in EXCLUDED_DISPOSITIONS
    )
    for key, identities in (
        ("discovered", tuple(entry["identity"] for entry in entries)),
        ("reviewedExecuted", eligible),
        ("noSocketExecuted", no_socket),
        ("localSocketExecuted", local_socket),
        ("remaining", excluded),
    ):
        record = closed_mapping(
            coverage.get(key), {"manifestSha256", "tests"}, f"coverage.{key}"
        )
        if (
            exact_int(record["tests"], f"coverage.{key}.tests") != len(identities)
            or exact_sha256(
                record["manifestSha256"], f"coverage.{key}.manifestSha256"
            )
            != manifest_sha256(identities)
        ):
            raise ScopeLedgerError(f"Swift eligible scope differs from {key} evidence")


def validate_android_evidence(
    root: Path,
    entries: Sequence[Mapping[str, object]],
) -> None:
    eligible = [
        entry for entry in entries if entry["disposition"] in ELIGIBLE_DISPOSITIONS
    ]
    counts = Counter(entry["identity"].split(":", 1)[0] for entry in eligible)
    if counts.get("pairing", 0) != 0:
        raise ScopeLedgerError("eligible Android pairing tests lack an execution binding")
    for module, relative in ANDROID_BINDING_RELATIVE_PATHS.items():
        module_entries = [
            entry for entry in eligible if entry["identity"].startswith(f"{module}:")
        ]
        binding = read_evidence_json(root, relative, f"Android {module} binding")
        row = closed_mapping(
            binding,
            {
                "contract",
                "reports",
                "runMarker",
                "sourceInputs",
                "testcaseManifestSha256",
                "tests",
            },
            f"Android {module} binding",
        )
        if row["contract"] != f"android-core-{module}-nonsecurity-junit-v1":
            raise ScopeLedgerError(f"Android {module} binding contract differs")
        expected_report_names = sorted(
            {
                f"TEST-{entry['className']}.xml"
                for entry in module_entries
            }
        )
        reports = row["reports"]
        if type(reports) is not list or len(reports) != len(expected_report_names):
            raise ScopeLedgerError(f"Android {module} binding reports differ")
        actual_report_names: list[str] = []
        for index, report in enumerate(reports):
            report_row = closed_mapping(
                report,
                {"bytes", "name", "sha256"},
                f"Android {module} reports[{index}]",
            )
            exact_int(
                report_row["bytes"],
                f"Android {module} reports[{index}].bytes",
                minimum=1,
            )
            exact_sha256(
                report_row["sha256"],
                f"Android {module} reports[{index}].sha256",
            )
            if type(report_row["name"]) is not str:
                raise ScopeLedgerError(
                    f"Android {module} reports[{index}].name differs"
                )
            actual_report_names.append(report_row["name"])
        if actual_report_names != expected_report_names:
            raise ScopeLedgerError(f"Android {module} binding report names differ")
        run_marker = closed_mapping(
            row["runMarker"], {"bytes", "sha256"}, f"Android {module} runMarker"
        )
        exact_int(run_marker["bytes"], f"Android {module} runMarker.bytes", minimum=1)
        exact_sha256(run_marker["sha256"], f"Android {module} runMarker.sha256")
        source_inputs = closed_mapping(
            row["sourceInputs"],
            {"count", "sha256"},
            f"Android {module} sourceInputs",
        )
        exact_int(
            source_inputs["count"],
            f"Android {module} sourceInputs.count",
            minimum=1,
        )
        exact_sha256(
            source_inputs["sha256"],
            f"Android {module} sourceInputs.sha256",
        )
        if (
            exact_int(row["tests"], f"Android {module} tests") != len(module_entries)
            or exact_sha256(
                row["testcaseManifestSha256"],
                f"Android {module} testcaseManifestSha256",
            )
            != android_binding_manifest_sha256(module_entries)
        ):
            raise ScopeLedgerError(
                f"Android {module} eligible scope differs from execution evidence"
            )


def scope_summary(
    swift_entries: Sequence[Mapping[str, object]],
    android_entries: Sequence[Mapping[str, object]],
    *,
    binding_records_validated: bool,
) -> dict[str, object]:
    if type(binding_records_validated) is not bool:
        raise ScopeLedgerError("binding_records_validated must be an exact boolean")

    def platform_summary(entries: Sequence[Mapping[str, object]]) -> dict[str, object]:
        counts = Counter(str(entry["disposition"]) for entry in entries)
        eligible = sum(counts[name] for name in ELIGIBLE_DISPOSITIONS)
        excluded = sum(counts[name] for name in EXCLUDED_DISPOSITIONS)
        return {
            "classifiedTests": len(entries),
            "dispositions": {name: counts[name] for name in sorted(DISPOSITIONS)},
            "eligibleTests": eligible,
            "excludedTests": excluded,
            "unclassifiedTests": 0,
        }

    return {
        "androidCore": platform_summary(android_entries),
        "executionBindingRecordsValidated": binding_records_validated,
        "localNonsecurityUnitScopeClassified": True,
        "rawAndroidJUnitOutputsReopenedByThisChecker": False,
        "swift": platform_summary(swift_entries),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        action="store_true",
        help=(
            "validate eligible manifests in current execution binding records; "
            "raw Android outputs remain owned by the product-CI readback"
        ),
    )
    arguments = parser.parse_args()
    try:
        _ledger, swift_entries, android_entries = read_and_validate_ledger()
        if arguments.evidence:
            validate_swift_evidence(ROOT, swift_entries)
            validate_android_evidence(ROOT, android_entries)
        summary = scope_summary(
            swift_entries,
            android_entries,
            binding_records_validated=arguments.evidence,
        )
    except ScopeLedgerError as error:
        print(f"G7 non-security unit scope ledger failed: {error}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(canonical_json_bytes(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
