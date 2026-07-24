#!/usr/bin/env python3
"""Independently read back a future dependency-wave-one v3 success set.

The acquisition runner is deliberately not imported.  This checker implements
its own JSON, filesystem, ZIP, module-hash, and publication validation.  The
default and ``--preflight`` modes are read-only.  ``--record`` is reserved for
a future successful acquisition and may create only the fixed readback receipt
followed by the fixed readback manifest.
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
            "dependency wave-one v3 readback requires unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
from typing import Any, Mapping, Sequence
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
SOURCE_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
RECOVERY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v3.json"
)
CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v3.claim"
)
FINAL_DIRECTORY_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v3/accepted"
)
STAGING_PARENT_PATH = "build/offline-source/pion-ice-v4.3.0/dependencies"
STAGING_PREFIX = ".wave-1-v3-staging-"
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v3.json"
)
SUCCESS_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v3.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v3.json"
)
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json"
)

EXPECTED_SOURCE_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-identity-and-"
    "acquisition-decision-v1"
)
EXPECTED_RECOVERY_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-recovery-decision-v2"
)
EXPECTED_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-execution-permit-v3"
)
EXPECTED_READBACK_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-independent-readback-v1"
)

EXPECTED_TUPLE_COUNT = 19
EXPECTED_RESOURCE_COUNT = 38
ACQUISITION_SUCCESS_REGULAR_FILE_COUNT = 41
POST_READBACK_REGULAR_FILE_COUNT = 43
MAXIMUM_JSON_BYTES = 2_097_152
MAXIMUM_ZIP_BYTES = 16_777_216
MAXIMUM_MOD_BYTES = 1_048_576
MAXIMUM_ENTRIES_PER_ARCHIVE = 16_384
MAXIMUM_AGGREGATE_ENTRIES = 131_072
MAXIMUM_SINGLE_FILE_BYTES = 16_777_216
MAXIMUM_UNCOMPRESSED_BYTES_PER_ARCHIVE = 268_435_456
MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_073_741_824
MAXIMUM_AGGREGATE_ZIP_BYTES = 134_217_728
MAXIMUM_AGGREGATE_MOD_BYTES = 8_388_608
MAXIMUM_AGGREGATE_BYTES = 142_606_336
MAXIMUM_CENTRAL_DIRECTORY_BYTES = 8_388_608
MAXIMUM_PATH_BYTES = 1_024
MAXIMUM_PATH_COMPONENTS = 64
MAXIMUM_COMPONENT_BYTES = 255
EOCD = struct.Struct("<4s4H2LH")

HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
H1 = re.compile(r"^h1:[A-Za-z0-9+/]{43}=$")
TUPLE_ID = re.compile(r"^wave1-[0-9]{3}-[0-9a-f]{12}$")
OUTPUT_NAME = re.compile(r"^[0-9]{3}-[0-9a-f]{20}\.(?:zip|mod)$")

COUNTER_NAMES = (
    "networkRequestAttemptCount",
    "responseBodyCompletedCount",
    "validatedAndStagedResourceCount",
    "validatedAndStagedTupleCount",
    "validatedModResourceCount",
    "validatedZipResourceCount",
)
SUCCESS_COUNTERS: Mapping[str, int] = {
    "networkRequestAttemptCount": 38,
    "responseBodyCompletedCount": 38,
    "validatedAndStagedResourceCount": 38,
    "validatedAndStagedTupleCount": 19,
    "validatedModResourceCount": 19,
    "validatedZipResourceCount": 19,
}

SOURCE_ROW_KEYS = {
    "order",
    "tupleId",
    "module",
    "version",
    "zipUrl",
    "modUrl",
    "zipOutputFileName",
    "modOutputFileName",
    "zipRawByteSize",
    "zipRawSha256",
    "modRawByteSize",
    "modRawSha256",
    "moduleZipH1",
    "goModH1",
    "entryCount",
    "uncompressedByteCount",
    "modulePrefix",
    "embeddedGoModPresent",
    "embeddedGoModByteParity",
    "zipMode",
    "zipLinkCount",
    "modMode",
    "modLinkCount",
}
SUCCESS_RECEIPT_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "result",
    "permitId",
    "permitRawSha256",
    "permitContentSha256",
    "recoveryDecisionId",
    "recoveryRawSha256",
    "recoveryContentSha256",
    "decisionId",
    "decisionRawSha256",
    "decisionContentSha256",
    "claimRawSha256",
    *COUNTER_NAMES,
    "acceptedArtifactCount",
    "acceptedTupleCount",
    "aggregateZipRawByteSize",
    "aggregateModRawByteSize",
    "aggregateRawByteSize",
    "aggregateEntryCount",
    "aggregateUncompressedByteCount",
    "orderedSourceSetSha256",
    "sources",
    "legacyCompletedRequestCountForbidden",
    "independentReadbackPassed",
    "dependencySourceReviewed",
    "dependencyClosureComplete",
    "candidateSelected",
    "librarySelected",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
}
ACQUISITION_MANIFEST_KEYS = {
    "documentType",
    "schemaVersion",
    "status",
    "result",
    "permitId",
    "permitRawSha256",
    "permitContentSha256",
    "recoveryRawSha256",
    "recoveryContentSha256",
    "successReceiptPath",
    "successReceiptRawSha256",
    "finalDirectoryPath",
    *COUNTER_NAMES,
    "acceptedArtifactCount",
    "acceptedTupleCount",
    "orderedSourceSetSha256",
    "manifestWrittenLast",
    "independentReadbackPassed",
    "repositoryOwnerIdentityProofRequired",
    "externalAuthenticationRequired",
    "userActionRequired",
    "nextAction",
}


class CheckError(ValueError):
    """The independent readback failed closed."""


class MissingPath(CheckError):
    """A fixed path component is absent, rather than unsafe."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite number")
    elif type(value) is list:
        for index, child in enumerate(value):
            reject_nonfinite(child, f"{label}[{index}]")
    elif type(value) is dict:
        for key, child in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(child, f"{label}.{key}")


def strict_json(data: bytes, label: str) -> Any:
    require(
        data.endswith(b"\n") and not data.endswith(b"\n\n") and b"\r" not in data,
        f"{label}: exact single LF required",
    )

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"{label}: duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CheckError(f"{label}: invalid constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid JSON") from error
    reject_nonfinite(value, label)
    require(canonical_json_bytes(value) == data, f"{label}: non-canonical JSON")
    return value


def exact_object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict and set(value) == keys, f"{label}: schema mismatch")
    return value


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(type(value) is type(expected) and value == expected, f"{label}: mismatch")


def strict_nonnegative_int(value: Any, label: str) -> int:
    require(type(value) is int and value >= 0, f"{label}: strict integer required")
    return value


def digest(value: Any, label: str) -> str:
    require(type(value) is str and HEX_SHA256.fullmatch(value), f"{label}: SHA-256")
    return value


def content_binding(document: Mapping[str, Any], scope: str, label: str) -> str:
    binding = exact_object(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    require_exact(binding["algorithm"], "sha256", f"{label}.algorithm")
    require_exact(
        binding["canonicalization"],
        "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        f"{label}.canonicalization",
    )
    require_exact(binding["scope"], scope, f"{label}.scope")
    expected = dict(document)
    expected.pop("contentBinding")
    observed = sha256_bytes(canonical_json_bytes(expected))
    require_exact(binding["sha256"], observed, f"{label}.content SHA")
    return observed


def safe_relative_path(value: Any, label: str) -> str:
    require(type(value) is str and value and "\x00" not in value, f"{label}: path")
    path = PurePosixPath(value)
    require(
        not path.is_absolute()
        and value == path.as_posix()
        and all(part not in {"", ".", ".."} for part in path.parts),
        f"{label}: unsafe path",
    )
    return value


def stable_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def open_root(root: Path) -> int:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        fd = os.open(root, flags)
    except OSError as error:
        raise CheckError("root: cannot open without following links") from error
    info = os.fstat(fd)
    require(stat.S_ISDIR(info.st_mode), "root: directory required")
    return fd


def open_directory_at(parent_fd: int, name: str, label: str) -> int:
    require(name not in {"", ".", ".."} and "/" not in name, f"{label}: component")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError as error:
        raise MissingPath(f"{label}: directory absent") from error
    except OSError as error:
        raise CheckError(f"{label}: cannot open directory") from error
    require(stat.S_ISDIR(os.fstat(fd).st_mode), f"{label}: directory required")
    return fd


def open_parent(root_fd: int, relative: str) -> tuple[int, str]:
    parts = PurePosixPath(safe_relative_path(relative, "path")).parts
    current = os.dup(root_fd)
    try:
        for index, part in enumerate(parts[:-1]):
            child = open_directory_at(current, part, f"path component {index}")
            os.close(current)
            current = child
        return current, parts[-1]
    except BaseException:
        os.close(current)
        raise


def path_kind(root_fd: int, relative: str) -> str:
    try:
        parent_fd, name = open_parent(root_fd, relative)
    except MissingPath:
        return "absent"
    try:
        try:
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return "absent"
        if stat.S_ISREG(info.st_mode):
            return "file"
        if stat.S_ISDIR(info.st_mode):
            return "directory"
        if stat.S_ISLNK(info.st_mode):
            return "symlink"
        return "other"
    finally:
        os.close(parent_fd)


class HeldFile:
    def __init__(
        self,
        root_fd: int,
        path: str,
        *,
        maximum_bytes: int,
        owner_only: bool,
    ) -> None:
        self.path = safe_relative_path(path, "held path")
        self.maximum_bytes = maximum_bytes
        self.owner_only = owner_only
        parent_fd, name = open_parent(root_fd, self.path)
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            self.fd = os.open(name, flags, dir_fd=parent_fd)
        except OSError as error:
            os.close(parent_fd)
            raise CheckError(f"{path}: cannot open regular file") from error
        self.parent_fd = parent_fd
        self.name = name
        self.initial = self._validated_info()
        self.initial_named = os.stat(
            name, dir_fd=parent_fd, follow_symlinks=False
        )
        require(
            stable_identity(self.initial) == stable_identity(self.initial_named),
            f"{path}: descriptor/name identity mismatch",
        )

    def _validated_info(self) -> os.stat_result:
        info = os.fstat(self.fd)
        require(stat.S_ISREG(info.st_mode), f"{self.path}: regular file required")
        require(info.st_nlink == 1, f"{self.path}: single link required")
        require(
            0 <= info.st_size <= self.maximum_bytes,
            f"{self.path}: byte limit exceeded",
        )
        if self.owner_only:
            require(info.st_uid == os.getuid(), f"{self.path}: current owner required")
            require(
                stat.S_IMODE(info.st_mode) == 0o600,
                f"{self.path}: exact mode 0600 required",
            )
        return info

    def read_pass(self) -> bytes:
        before = self._validated_info()
        require(
            stable_identity(before) == stable_identity(self.initial),
            f"{self.path}: identity changed before read",
        )
        os.lseek(self.fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        observed = 0
        while True:
            chunk = os.read(self.fd, min(1_048_576, self.maximum_bytes + 1 - observed))
            if not chunk:
                break
            observed += len(chunk)
            require(observed <= self.maximum_bytes, f"{self.path}: oversized")
            chunks.append(chunk)
        after = self._validated_info()
        require(
            observed == before.st_size
            and stable_identity(before) == stable_identity(after),
            f"{self.path}: unstable read",
        )
        return b"".join(chunks)

    def final_name_barrier(self) -> None:
        named = os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
        require(
            stable_identity(named) == stable_identity(self.initial),
            f"{self.path}: final name identity changed",
        )

    def close(self) -> None:
        os.close(self.fd)
        os.close(self.parent_fd)


def open_held_set(
    root_fd: int,
    specs: Sequence[tuple[str, int, bool]],
) -> tuple[list[HeldFile], Mapping[str, bytes]]:
    held: list[HeldFile] = []
    try:
        for path, maximum, owner_only in specs:
            held.append(
                HeldFile(
                    root_fd,
                    path,
                    maximum_bytes=maximum,
                    owner_only=owner_only,
                )
            )
        first = {item.path: item.read_pass() for item in held}
        second = {item.path: item.read_pass() for item in held}
        require(first == second, "full-set two-pass byte mismatch")
        for item in held:
            item.final_name_barrier()
        return held, first
    except BaseException:
        for item in reversed(held):
            item.close()
        raise


def directory_inventory(root_fd: int, relative: str) -> tuple[int, list[str]]:
    parts = PurePosixPath(safe_relative_path(relative, "directory")).parts
    current = os.dup(root_fd)
    try:
        for index, part in enumerate(parts):
            child = open_directory_at(current, part, f"directory component {index}")
            os.close(current)
            current = child
        info = os.fstat(current)
        require(info.st_uid == os.getuid(), f"{relative}: current owner required")
        require(
            stat.S_IMODE(info.st_mode) & 0o077 == 0,
            f"{relative}: owner-only directory required",
        )
        return current, sorted(os.listdir(current))
    except BaseException:
        os.close(current)
        raise


def directory_identity_barrier(root_fd: int, relative: str, held_fd: int) -> None:
    before = os.fstat(held_fd)
    require(stat.S_ISDIR(before.st_mode), f"{relative}: held directory")
    parts = PurePosixPath(safe_relative_path(relative, "directory barrier")).parts
    current = os.dup(root_fd)
    try:
        for index, part in enumerate(parts):
            child = open_directory_at(
                current, part, f"directory barrier component {index}"
            )
            os.close(current)
            current = child
        named = os.fstat(current)
        after = os.fstat(held_fd)
        require(
            stable_identity(before)
            == stable_identity(after)
            == stable_identity(named),
            f"{relative}: directory identity changed",
        )
    finally:
        os.close(current)


def exact_module_directive(payload: bytes, expected_module: str) -> None:
    require(b"\x00" not in payload, "external go.mod: NUL forbidden")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CheckError("external go.mod: UTF-8 required") from error
    found: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line == "module" or line.startswith("module "):
            value = line[len("module") :].strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            found.append(value)
    require(found == [expected_module], "external go.mod: exact module directive")


def dirhash_h1(rows: Sequence[tuple[str, str]]) -> str:
    aggregate = hashlib.sha256()
    for name, file_digest in sorted(rows, key=lambda row: row[0].encode("utf-8")):
        aggregate.update(file_digest.encode("ascii"))
        aggregate.update(b"  ")
        aggregate.update(name.encode("utf-8"))
        aggregate.update(b"\n")
    return "h1:" + base64.b64encode(aggregate.digest()).decode("ascii")


def single_go_mod_h1(payload: bytes) -> str:
    return dirhash_h1([("go.mod", sha256_bytes(payload))])


def inspect_zip(payload: bytes, module: str, version: str) -> Mapping[str, Any]:
    prefix = f"{module}@{version}/"
    rows: list[tuple[str, str]] = []
    names: set[str] = set()
    folded_names: set[str] = set()
    embedded: bytes | None = None
    total = 0
    eocd_offset = payload.rfind(
        b"PK\x05\x06", max(0, len(payload) - (65_535 + EOCD.size))
    )
    require(eocd_offset >= 0 and eocd_offset + EOCD.size <= len(payload), "ZIP: EOCD")
    (
        signature,
        disk_number,
        central_disk,
        disk_entries,
        total_entries,
        central_size,
        central_offset,
        comment_size,
    ) = EOCD.unpack_from(payload, eocd_offset)
    require(signature == b"PK\x05\x06", "ZIP: EOCD signature")
    require(
        disk_number == central_disk == 0
        and disk_entries == total_entries
        and total_entries not in {0, 0xFFFF}
        and central_size != 0xFFFFFFFF
        and central_offset != 0xFFFFFFFF,
        "ZIP: single-disk non-ZIP64 EOCD required",
    )
    require(
        central_size <= MAXIMUM_CENTRAL_DIRECTORY_BYTES
        and central_offset + central_size == eocd_offset
        and comment_size == 0
        and eocd_offset + EOCD.size == len(payload),
        "ZIP: central directory or trailing bytes",
    )
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            require(not archive.comment, "ZIP: archive comment forbidden")
            infos = archive.infolist()
            require(
                0 < len(infos) <= MAXIMUM_ENTRIES_PER_ARCHIVE,
                "ZIP: entry count",
            )
            for entry in infos:
                name = entry.filename
                require(
                    type(name) is str
                    and name.startswith(prefix)
                    and name != prefix
                    and "\\" not in name
                    and "\x00" not in name
                    and unicodedata.normalize("NFC", name) == name,
                    "ZIP: exact safe module prefix",
                )
                path = PurePosixPath(name)
                require(
                    not path.is_absolute()
                    and all(part not in {"", ".", ".."} for part in path.parts),
                    "ZIP: unsafe path",
                )
                require(
                    len(name.encode("utf-8")) <= MAXIMUM_PATH_BYTES
                    and len(path.parts) <= MAXIMUM_PATH_COMPONENTS
                    and all(
                        len(part.encode("utf-8")) <= MAXIMUM_COMPONENT_BYTES
                        for part in path.parts
                    ),
                    "ZIP: path bounds",
                )
                require(name not in names, "ZIP: duplicate name")
                names.add(name)
                folded = name.casefold()
                require(folded not in folded_names, "ZIP: case-fold collision")
                folded_names.add(folded)
                require(not entry.is_dir(), "ZIP: directory entry forbidden")
                require(entry.flag_bits & 0x1 == 0, "ZIP: encryption forbidden")
                require(
                    entry.flag_bits & ~0x0808 == 0,
                    "ZIP: unsupported general-purpose flags",
                )
                require(
                    entry.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED},
                    "ZIP: compression method",
                )
                require(entry.create_system in {0, 3}, "ZIP: creator system")
                require(not entry.comment, "ZIP: entry comment forbidden")
                mode = (entry.external_attr >> 16) & 0xFFFF
                if entry.create_system == 3 and mode:
                    require(
                        mode & 0o170000 in {0, stat.S_IFREG},
                        "ZIP: non-regular entry",
                    )
                    require(mode & 0o7000 == 0, "ZIP: special mode")
                require(
                    0 <= entry.file_size <= MAXIMUM_SINGLE_FILE_BYTES,
                    "ZIP: file byte limit",
                )
                with archive.open(entry, "r") as source:
                    data = source.read(MAXIMUM_SINGLE_FILE_BYTES + 1)
                    require(
                        len(data) == entry.file_size
                        and len(data) <= MAXIMUM_SINGLE_FILE_BYTES,
                        "ZIP: file read mismatch",
                    )
                total += len(data)
                require(
                    total <= MAXIMUM_UNCOMPRESSED_BYTES_PER_ARCHIVE,
                    "ZIP: uncompressed limit",
                )
                rows.append((name, sha256_bytes(data)))
                if name == prefix + "go.mod":
                    require(embedded is None, "ZIP: duplicate embedded go.mod")
                    embedded = data
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise CheckError("ZIP: invalid archive") from error
    return {
        "moduleZipH1": dirhash_h1(rows),
        "entryCount": len(rows),
        "uncompressedByteCount": total,
        "modulePrefix": prefix,
        "embeddedGoMod": embedded,
    }


def validate_source_decision(
    raw: bytes,
) -> tuple[Mapping[str, Any], list[Mapping[str, Any]], str]:
    document = strict_json(raw, "source decision")
    require(type(document) is dict, "source decision: object required")
    require_exact(
        document.get("documentType"),
        "aetherlink.g2-pion-rung3-bounded-dependency-source-identity-and-acquisition-decision",
        "source decision.documentType",
    )
    require_exact(document.get("decisionId"), EXPECTED_SOURCE_DECISION_ID, "source decision.id")
    content_sha = content_binding(
        document, "decision_without_contentBinding", "source decision"
    )
    wave = document.get("wave")
    require(type(wave) is dict, "source decision.wave")
    tuples = wave.get("tuples")
    require(
        type(tuples) is list and len(tuples) == EXPECTED_TUPLE_COUNT,
        "source decision: exact 19 tuples",
    )
    for index, item in enumerate(tuples, 1):
        require(type(item) is dict, f"source tuple {index}: object")
        require_exact(item.get("order"), index, f"source tuple {index}.order")
        require(
            type(item.get("tupleId")) is str
            and TUPLE_ID.fullmatch(item["tupleId"]),
            f"source tuple {index}.tupleId",
        )
        require(
            type(item.get("tupleSha256")) is str
            and HEX_SHA256.fullmatch(item["tupleSha256"]),
            f"source tuple {index}.tupleSha256",
        )
        require(
            item["tupleId"] == f"wave1-{index:03d}-{item['tupleSha256'][:12]}",
            f"source tuple {index}: tuple binding",
        )
        for key in ("module", "version", "url"):
            require(type(item.get(key)) is str and item[key], f"source tuple {index}.{key}")
        require(
            item["url"].endswith(".zip")
            and item.get("scheme") == "https"
            and item.get("host") == "proxy.golang.org",
            f"source tuple {index}: URL policy",
        )
        require(
            type(item.get("moduleZipH1")) is str
            and H1.fullmatch(item["moduleZipH1"]),
            f"source tuple {index}.moduleZipH1",
        )
        require(
            type(item.get("goModH1")) is str and H1.fullmatch(item["goModH1"]),
            f"source tuple {index}.goModH1",
        )
    return document, tuples, content_sha


def validate_recovery(
    raw: bytes,
    source_raw_sha: str,
    source_content_sha: str,
) -> tuple[Mapping[str, Any], str]:
    document = strict_json(raw, "recovery decision")
    require(type(document) is dict, "recovery decision: object")
    require_exact(
        document.get("documentType"),
        "aetherlink.g2-pion-dependency-wave1-recovery-decision",
        "recovery.documentType",
    )
    require_exact(document.get("schemaVersion"), "2.0", "recovery.schemaVersion")
    require_exact(document.get("decisionId"), EXPECTED_RECOVERY_DECISION_ID, "recovery.id")
    require_exact(
        document.get("status"),
        "wave1_v2_failure_read_back_recovery_v3_design_selected_execution_not_authorized",
        "recovery.status",
    )
    content_sha = content_binding(
        document, "decision_without_contentBinding", "recovery decision"
    )
    predecessor = document.get("predecessorBindings")
    require(type(predecessor) is dict, "recovery.predecessorBindings")
    source_binding = predecessor.get("sourceIdentityDecision")
    require(type(source_binding) is dict, "recovery.source binding")
    require_exact(source_binding.get("path"), SOURCE_DECISION_PATH, "recovery.source.path")
    require_exact(
        source_binding.get("rawSha256"), source_raw_sha, "recovery.source.raw"
    )
    require_exact(
        source_binding.get("contentSha256"),
        source_content_sha,
        "recovery.source.content",
    )
    namespace = document.get("v3NamespaceContract")
    require(type(namespace) is dict, "recovery.namespace")
    for key, expected in {
        "claimPath": CLAIM_PATH,
        "failureReceiptPath": FAILURE_PATH,
        "finalDirectoryPath": FINAL_DIRECTORY_PATH,
        "manifestPath": ACQUISITION_MANIFEST_PATH,
        "successReceiptPath": SUCCESS_RECEIPT_PATH,
        "stagingParentPath": STAGING_PARENT_PATH,
        "stagingNamePrefix": STAGING_PREFIX,
        "fullFreshTupleCountRequired": EXPECTED_TUPLE_COUNT,
    }.items():
        require_exact(namespace.get(key), expected, f"recovery.namespace.{key}")
    policy = document.get("selectedV3Policy")
    require(type(policy) is dict, "recovery.selectedV3Policy")
    require_exact(policy.get("expectedSuccessRequestCount"), 38, "recovery.requests")
    require_exact(policy.get("maximumRequestCount"), 38, "recovery.max requests")
    require_exact(policy.get("resourceCountPerTuple"), 2, "recovery.resources/tuple")
    require_exact(
        policy.get("resourceModel"),
        "fresh_exact_mod_then_zip_pair_for_each_tuple",
        "recovery.resourceModel",
    )
    counters = policy.get("requiredCounterSchema")
    require(type(counters) is dict, "recovery.counter schema")
    require_exact(counters.get("successValues"), dict(SUCCESS_COUNTERS) | {"acceptedArtifactCount": 38}, "recovery.success counters")
    readback = document.get("independentReadbackContract")
    require(type(readback) is dict, "recovery.readback contract")
    for key, expected in {
        "checkerPath": "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3.py",
        "checkerTestsPath": "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3.py",
        "exactRetainedResourceCount": 38,
        "acquisitionSuccessRegularFileCount": 41,
        "postReadbackRegularFileCount": 43,
        "receiptPath": READBACK_RECEIPT_PATH,
        "manifestPath": READBACK_MANIFEST_PATH,
        "manifestWrittenLast": True,
        "networkAllowed": False,
        "sourceExtractionAllowed": False,
        "sourceLoadOrExecutionAllowed": False,
    }.items():
        require_exact(readback.get(key), expected, f"recovery.readback.{key}")
    return document, content_sha


def validate_permit(
    raw: bytes,
    source_raw_sha: str,
    source_content_sha: str,
    recovery_raw_sha: str,
    recovery_content_sha: str,
) -> tuple[Mapping[str, Any], str]:
    document = strict_json(raw, "v3 permit")
    require(type(document) is dict, "v3 permit: object")
    require_exact(
        document.get("documentType"),
        "aetherlink.g2-pion-rung3-dependency-wave1-execution-permit",
        "permit.documentType",
    )
    require_exact(document.get("schemaVersion"), "3.0", "permit.schemaVersion")
    require_exact(document.get("permitId"), EXPECTED_PERMIT_ID, "permit.id")
    require_exact(
        document.get("status"),
        "wave1_v3_dependency_source_acquisition_authorized_not_consumed",
        "permit.status",
    )
    content_sha = content_binding(document, "permit_without_contentBinding", "permit")
    source = document.get("sourceDecisionBinding")
    recovery = document.get("recoveryBinding")
    require(type(source) is dict and type(recovery) is dict, "permit bindings")
    for binding, path, raw_sha, semantic_sha, label in (
        (
            source,
            SOURCE_DECISION_PATH,
            source_raw_sha,
            source_content_sha,
            "permit.source",
        ),
        (
            recovery,
            RECOVERY_DECISION_PATH,
            recovery_raw_sha,
            recovery_content_sha,
            "permit.recovery",
        ),
    ):
        require_exact(binding.get("path"), path, f"{label}.path")
        require_exact(binding.get("rawSha256"), raw_sha, f"{label}.raw")
        require_exact(binding.get("contentSha256"), semantic_sha, f"{label}.content")
    return document, content_sha


def validate_claim(
    raw: bytes,
    permit_content_sha: str,
    recovery_content_sha: str,
) -> Mapping[str, Any]:
    claim = exact_object(
        strict_json(raw, "v3 claim"),
        {
            "claimType",
            "schemaVersion",
            "createdAt",
            "permitId",
            "permitContentSha256",
            "recoveryDecisionId",
            "recoveryContentSha256",
            "rule",
            "v1OrV2ArtifactReuseAllowed",
        },
        "v3 claim",
    )
    require_exact(
        claim["claimType"],
        "aetherlink.g2-pion-dependency-wave1-v3-one-use-claim",
        "claim.type",
    )
    require_exact(claim["schemaVersion"], "3.0", "claim.schemaVersion")
    require(type(claim["createdAt"]) is str and claim["createdAt"], "claim.createdAt")
    require_exact(claim["permitId"], EXPECTED_PERMIT_ID, "claim.permitId")
    require_exact(
        claim["permitContentSha256"], permit_content_sha, "claim.permit content"
    )
    require_exact(
        claim["recoveryDecisionId"], EXPECTED_RECOVERY_DECISION_ID, "claim.recovery id"
    )
    require_exact(
        claim["recoveryContentSha256"],
        recovery_content_sha,
        "claim.recovery content",
    )
    require_exact(
        claim["rule"],
        "v3_claim_persists_after_any_network_attempt_and_blocks_retry",
        "claim.rule",
    )
    require_exact(
        claim["v1OrV2ArtifactReuseAllowed"], False, "claim.prior reuse"
    )
    return claim


def expected_output_names(
    tuples: Sequence[Mapping[str, Any]],
) -> tuple[list[str], Mapping[int, tuple[str, str]]]:
    names: list[str] = []
    by_order: dict[int, tuple[str, str]] = {}
    for item in tuples:
        order = item["order"]
        prefix = item["tupleSha256"][:20]
        zip_name = f"{order:03d}-{prefix}.zip"
        mod_name = f"{order:03d}-{prefix}.mod"
        names.extend((mod_name, zip_name))
        by_order[order] = (zip_name, mod_name)
    return sorted(names), by_order


def ordered_source_set_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(list(rows)))


def validate_receipt_and_resources(
    receipt_raw: bytes,
    tuples: Sequence[Mapping[str, Any]],
    *,
    permit_raw_sha: str,
    permit_content_sha: str,
    recovery_raw_sha: str,
    recovery_content_sha: str,
    source_raw_sha: str,
    source_content_sha: str,
    claim_raw_sha: str,
    resource_bytes: Mapping[str, bytes],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    receipt = exact_object(
        strict_json(receipt_raw, "v3 success receipt"),
        SUCCESS_RECEIPT_KEYS,
        "v3 success receipt",
    )
    fixed = {
        "documentType": "aetherlink.g2-pion-dependency-wave1-v3-acquisition-receipt",
        "schemaVersion": "3.0",
        "status": "acquired_pending_independent_readback",
        "result": "fresh_exact_19_dependency_zip_mod_pairs_acquired_and_hash_verified",
        "permitId": EXPECTED_PERMIT_ID,
        "permitRawSha256": permit_raw_sha,
        "permitContentSha256": permit_content_sha,
        "recoveryDecisionId": EXPECTED_RECOVERY_DECISION_ID,
        "recoveryRawSha256": recovery_raw_sha,
        "recoveryContentSha256": recovery_content_sha,
        "decisionId": EXPECTED_SOURCE_DECISION_ID,
        "decisionRawSha256": source_raw_sha,
        "decisionContentSha256": source_content_sha,
        "claimRawSha256": claim_raw_sha,
        **SUCCESS_COUNTERS,
        "acceptedArtifactCount": 38,
        "acceptedTupleCount": 19,
        "legacyCompletedRequestCountForbidden": True,
        "independentReadbackPassed": False,
        "dependencySourceReviewed": False,
        "dependencyClosureComplete": False,
        "candidateSelected": False,
        "librarySelected": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "run_separate_wave1_v3_independent_readback",
    }
    for key, expected in fixed.items():
        require_exact(receipt[key], expected, f"receipt.{key}")
    require(("completed" + "RequestCount") not in receipt, "legacy counter forbidden")
    rows = receipt["sources"]
    require(type(rows) is list and len(rows) == 19, "receipt.sources: exact 19")
    expected_names, name_map = expected_output_names(tuples)
    require(sorted(resource_bytes) == expected_names, "resource byte map inventory")

    aggregate_zip = 0
    aggregate_mod = 0
    aggregate_entries = 0
    aggregate_uncompressed = 0
    observations: dict[str, Any] = {}
    for index, (row_value, item) in enumerate(zip(rows, tuples), 1):
        row = exact_object(row_value, SOURCE_ROW_KEYS, f"source row {index}")
        zip_name, mod_name = name_map[index]
        zip_payload = resource_bytes[zip_name]
        mod_payload = resource_bytes[mod_name]
        require(OUTPUT_NAME.fullmatch(zip_name) and OUTPUT_NAME.fullmatch(mod_name), "output name")
        zip_url = item["url"]
        mod_url = zip_url[:-4] + ".mod"
        for key, expected in {
            "order": index,
            "tupleId": item["tupleId"],
            "module": item["module"],
            "version": item["version"],
            "zipUrl": zip_url,
            "modUrl": mod_url,
            "zipOutputFileName": zip_name,
            "modOutputFileName": mod_name,
            "zipRawByteSize": len(zip_payload),
            "zipRawSha256": sha256_bytes(zip_payload),
            "modRawByteSize": len(mod_payload),
            "modRawSha256": sha256_bytes(mod_payload),
            "moduleZipH1": item["moduleZipH1"],
            "goModH1": item["goModH1"],
            "modulePrefix": f"{item['module']}@{item['version']}/",
            "zipMode": "0600",
            "zipLinkCount": 1,
            "modMode": "0600",
            "modLinkCount": 1,
        }.items():
            require_exact(row[key], expected, f"source row {index}.{key}")
        require(len(zip_payload) <= MAXIMUM_ZIP_BYTES, "aggregate ZIP member limit")
        require(len(mod_payload) <= MAXIMUM_MOD_BYTES, "aggregate mod member limit")
        exact_module_directive(mod_payload, item["module"])
        require_exact(
            single_go_mod_h1(mod_payload), item["goModH1"], f"source row {index}.mod H1"
        )
        inspected = inspect_zip(zip_payload, item["module"], item["version"])
        require_exact(
            inspected["moduleZipH1"],
            item["moduleZipH1"],
            f"source row {index}.ZIP H1",
        )
        for key in ("entryCount", "uncompressedByteCount", "modulePrefix"):
            require_exact(row[key], inspected[key], f"source row {index}.{key}")
        embedded = inspected["embeddedGoMod"]
        require_exact(
            row["embeddedGoModPresent"], embedded is not None, f"source row {index}.embedded"
        )
        require_exact(
            row["embeddedGoModByteParity"],
            embedded is None or embedded == mod_payload,
            f"source row {index}.embedded parity",
        )
        require(
            embedded is None or embedded == mod_payload,
            f"source row {index}: embedded/external go.mod mismatch",
        )
        aggregate_zip += len(zip_payload)
        aggregate_mod += len(mod_payload)
        aggregate_entries += inspected["entryCount"]
        aggregate_uncompressed += inspected["uncompressedByteCount"]
        require(aggregate_zip <= MAXIMUM_AGGREGATE_ZIP_BYTES, "aggregate ZIP bytes")
        require(aggregate_mod <= MAXIMUM_AGGREGATE_MOD_BYTES, "aggregate mod bytes")
        require(
            aggregate_entries <= MAXIMUM_AGGREGATE_ENTRIES,
            "aggregate ZIP entries",
        )
        require(
            aggregate_uncompressed <= MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
            "aggregate uncompressed bytes",
        )
        observations[item["tupleId"]] = {
            "embeddedGoModPresent": embedded is not None,
            "embeddedGoModByteParity": embedded is None or embedded == mod_payload,
        }
    aggregates = {
        "aggregateZipRawByteSize": aggregate_zip,
        "aggregateModRawByteSize": aggregate_mod,
        "aggregateRawByteSize": aggregate_zip + aggregate_mod,
        "aggregateEntryCount": aggregate_entries,
        "aggregateUncompressedByteCount": aggregate_uncompressed,
    }
    require(
        aggregates["aggregateRawByteSize"] <= MAXIMUM_AGGREGATE_BYTES,
        "aggregate retained bytes",
    )
    for key, expected in aggregates.items():
        require_exact(receipt[key], expected, f"receipt.{key}")
    require_exact(
        receipt["orderedSourceSetSha256"],
        ordered_source_set_sha256(rows),
        "receipt.orderedSourceSetSha256",
    )
    return receipt, observations


def validate_acquisition_manifest(
    raw: bytes,
    receipt_raw: bytes,
    receipt: Mapping[str, Any],
    *,
    permit_raw_sha: str,
    permit_content_sha: str,
    recovery_raw_sha: str,
    recovery_content_sha: str,
) -> Mapping[str, Any]:
    manifest = exact_object(
        strict_json(raw, "v3 acquisition manifest"),
        ACQUISITION_MANIFEST_KEYS,
        "v3 acquisition manifest",
    )
    expected = {
        "documentType": "aetherlink.g2-pion-dependency-wave1-v3-acquisition-manifest",
        "schemaVersion": "3.0",
        "status": "wave1_v3_acquisition_publication_complete_pending_independent_readback",
        "result": "receipt_and_fresh_exact_19_zip_mod_pairs_published_manifest_written_last",
        "permitId": EXPECTED_PERMIT_ID,
        "permitRawSha256": permit_raw_sha,
        "permitContentSha256": permit_content_sha,
        "recoveryRawSha256": recovery_raw_sha,
        "recoveryContentSha256": recovery_content_sha,
        "successReceiptPath": SUCCESS_RECEIPT_PATH,
        "successReceiptRawSha256": sha256_bytes(receipt_raw),
        "finalDirectoryPath": FINAL_DIRECTORY_PATH,
        **SUCCESS_COUNTERS,
        "acceptedArtifactCount": 38,
        "acceptedTupleCount": 19,
        "orderedSourceSetSha256": receipt["orderedSourceSetSha256"],
        "manifestWrittenLast": True,
        "independentReadbackPassed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "run_separate_wave1_v3_independent_readback",
    }
    require_exact(dict(manifest), expected, "acquisition manifest")
    return manifest


def build_readback_receipt(
    *,
    source_raw: bytes,
    source_content_sha: str,
    recovery_raw: bytes,
    recovery_content_sha: str,
    permit_raw: bytes,
    permit_content_sha: str,
    claim_raw: bytes,
    receipt_raw: bytes,
    acquisition_manifest_raw: bytes,
    receipt: Mapping[str, Any],
    resource_bytes: Mapping[str, bytes],
    observations: Mapping[str, Any],
) -> Mapping[str, Any]:
    document: dict[str, Any] = {
        "documentType": "aetherlink.g2-pion-dependency-wave1-v3-independent-readback-receipt",
        "schemaVersion": "1.0",
        "readbackId": EXPECTED_READBACK_ID,
        "status": "wave1_v3_independent_readback_complete_manifest_pending",
        "result": "two_stable_passes_exact_38_resource_hash_and_h1_readback_complete",
        "sourceDecisionBinding": {
            "path": SOURCE_DECISION_PATH,
            "rawSha256": sha256_bytes(source_raw),
            "contentSha256": source_content_sha,
        },
        "recoveryDecisionBinding": {
            "path": RECOVERY_DECISION_PATH,
            "rawSha256": sha256_bytes(recovery_raw),
            "contentSha256": recovery_content_sha,
        },
        "executionPermitBinding": {
            "path": PERMIT_PATH,
            "rawSha256": sha256_bytes(permit_raw),
            "contentSha256": permit_content_sha,
        },
        "claimBinding": {
            "path": CLAIM_PATH,
            "rawSha256": sha256_bytes(claim_raw),
        },
        "acquisitionReceiptBinding": {
            "path": SUCCESS_RECEIPT_PATH,
            "rawSha256": sha256_bytes(receipt_raw),
        },
        "acquisitionManifestBinding": {
            "path": ACQUISITION_MANIFEST_PATH,
            "rawSha256": sha256_bytes(acquisition_manifest_raw),
        },
        "finalDirectoryPath": FINAL_DIRECTORY_PATH,
        "retainedResourceCount": 38,
        "retainedZipCount": 19,
        "retainedModCount": 19,
        "acquisitionSuccessRegularFileCount": 41,
        "orderedSourceSetSha256": receipt["orderedSourceSetSha256"],
        "resourceRawSha256": [
            {"name": name, "rawSha256": sha256_bytes(resource_bytes[name])}
            for name in sorted(resource_bytes)
        ],
        "tupleObservations": observations,
        "twoStableFullSetReadbackPassesCompleted": True,
        "finalNameIdentityBarrierCompleted": True,
        "exactInventoryValidated": True,
        "ownerOnlySingleLinkValidated": True,
        "moduleZipH1Recomputed": True,
        "externalGoModH1Recomputed": True,
        "embeddedGoModParityRecheckedWhenPresent": True,
        "sourceExtractionPerformed": False,
        "sourceLoadOrExecutionPerformed": False,
        "networkUsed": False,
        "gitOperationPerformed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "publish_wave1_v3_independent_readback_manifest_last",
    }
    document["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "readback_receipt_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(document)),
    }
    return document


def build_readback_manifest(
    readback_receipt_raw: bytes,
    readback_receipt: Mapping[str, Any],
    acquisition_manifest_raw: bytes,
) -> Mapping[str, Any]:
    document: dict[str, Any] = {
        "documentType": "aetherlink.g2-pion-dependency-wave1-v3-independent-readback-manifest",
        "schemaVersion": "1.0",
        "manifestId": (
            "g2-pion-ice-v4.3.0-rung3-dependency-wave1-independent-readback-"
            "manifest-v1"
        ),
        "status": "wave1_v3_independent_readback_publication_complete",
        "result": "independent_readback_receipt_published_then_manifest_written_last",
        "readbackReceiptBinding": {
            "path": READBACK_RECEIPT_PATH,
            "rawSha256": sha256_bytes(readback_receipt_raw),
            "contentSha256": readback_receipt["contentBinding"]["sha256"],
        },
        "acquisitionManifestBinding": {
            "path": ACQUISITION_MANIFEST_PATH,
            "rawSha256": sha256_bytes(acquisition_manifest_raw),
        },
        "retainedResourceCount": 38,
        "acquisitionSuccessRegularFileCount": 41,
        "postReadbackRegularFileCount": 43,
        "manifestWrittenLast": True,
        "independentReadbackPassed": True,
        "sourceExtractionPerformed": False,
        "sourceLoadOrExecutionPerformed": False,
        "networkUsed": False,
        "gitOperationPerformed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "prepare_separate_dependency_source_review_wave",
    }
    document["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "readback_manifest_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(document)),
    }
    return document


def validate_readback_documents(
    receipt_raw: bytes,
    manifest_raw: bytes,
    expected_receipt: Mapping[str, Any],
    acquisition_manifest_raw: bytes,
) -> None:
    receipt = strict_json(receipt_raw, "readback receipt")
    require(type(receipt) is dict, "readback receipt: object")
    require_exact(receipt, expected_receipt, "readback receipt")
    content_binding(
        receipt, "readback_receipt_without_contentBinding", "readback receipt"
    )
    expected_manifest = build_readback_manifest(
        receipt_raw, receipt, acquisition_manifest_raw
    )
    manifest = strict_json(manifest_raw, "readback manifest")
    require_exact(manifest, expected_manifest, "readback manifest")
    content_binding(
        manifest, "readback_manifest_without_contentBinding", "readback manifest"
    )


def validate_state(root: Path = ROOT) -> dict[str, Any]:
    root_fd = open_root(root)
    held: list[HeldFile] = []
    accepted_fd = -1
    staging_fd = -1
    try:
        kinds = {
            path: path_kind(root_fd, path)
            for path in (
                CLAIM_PATH,
                FAILURE_PATH,
                SUCCESS_RECEIPT_PATH,
                ACQUISITION_MANIFEST_PATH,
                FINAL_DIRECTORY_PATH,
                READBACK_RECEIPT_PATH,
                READBACK_MANIFEST_PATH,
            )
        }
        staging_names: list[str] = []
        try:
            staging_fd, parent_names = directory_inventory(root_fd, STAGING_PARENT_PATH)
            staging_names = [name for name in parent_names if name.startswith(STAGING_PREFIX)]
        except CheckError:
            if any(kind != "absent" for kind in kinds.values()):
                raise
        acquisition_present = (
            kinds[CLAIM_PATH] == "file"
            and kinds[SUCCESS_RECEIPT_PATH] == "file"
            and kinds[ACQUISITION_MANIFEST_PATH] == "file"
            and kinds[FINAL_DIRECTORY_PATH] == "directory"
        )
        readback_present = (
            kinds[READBACK_RECEIPT_PATH] == "file"
            and kinds[READBACK_MANIFEST_PATH] == "file"
        )
        all_absent = all(kind == "absent" for kind in kinds.values())
        if all_absent and not staging_names:
            return {
                "documentType": "aetherlink.g2-pion-dependency-wave1-v3-readback-preflight",
                "schemaVersion": "1.0",
                "status": "absent_not_acquired",
                "validationPassed": True,
                "observedRegularFileCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "authenticationRequired": False,
                "nextAction": "await_separately_authorized_v3_acquisition",
            }
        require(kinds[FAILURE_PATH] == "absent", "v3 failure receipt present")
        require(not staging_names, "v3 staging residue present")
        require(acquisition_present, "partial or incoherent v3 success state")
        require(
            readback_present
            or (
                kinds[READBACK_RECEIPT_PATH] == "absent"
                and kinds[READBACK_MANIFEST_PATH] == "absent"
            ),
            "partial readback publication",
        )
        specs: list[tuple[str, int, bool]] = [
            (SOURCE_DECISION_PATH, MAXIMUM_JSON_BYTES, False),
            (RECOVERY_DECISION_PATH, MAXIMUM_JSON_BYTES, False),
            (PERMIT_PATH, MAXIMUM_JSON_BYTES, False),
            (CLAIM_PATH, MAXIMUM_JSON_BYTES, True),
            (SUCCESS_RECEIPT_PATH, MAXIMUM_JSON_BYTES, True),
            (ACQUISITION_MANIFEST_PATH, MAXIMUM_JSON_BYTES, True),
        ]
        accepted_fd, names = directory_inventory(root_fd, FINAL_DIRECTORY_PATH)
        source_probe = HeldFile(
            root_fd,
            SOURCE_DECISION_PATH,
            maximum_bytes=MAXIMUM_JSON_BYTES,
            owner_only=False,
        )
        try:
            source_raw_probe = source_probe.read_pass()
            _, tuples_probe, _ = validate_source_decision(source_raw_probe)
        finally:
            source_probe.close()
        expected_names, _ = expected_output_names(tuples_probe)
        require(names == expected_names, "accepted directory exact 38-file inventory")
        for name in expected_names:
            specs.append(
                (
                    f"{FINAL_DIRECTORY_PATH}/{name}",
                    MAXIMUM_ZIP_BYTES if name.endswith(".zip") else MAXIMUM_MOD_BYTES,
                    True,
                )
            )
        if readback_present:
            specs.extend(
                (
                    (READBACK_RECEIPT_PATH, MAXIMUM_JSON_BYTES, True),
                    (READBACK_MANIFEST_PATH, MAXIMUM_JSON_BYTES, True),
                )
            )
        held, raw = open_held_set(root_fd, specs)
        require(
            sorted(os.listdir(accepted_fd)) == expected_names,
            "accepted inventory changed during readback",
        )
        directory_identity_barrier(root_fd, FINAL_DIRECTORY_PATH, accepted_fd)
        if staging_fd >= 0:
            require(
                not any(name.startswith(STAGING_PREFIX) for name in os.listdir(staging_fd)),
                "staging appeared during readback",
            )
            directory_identity_barrier(root_fd, STAGING_PARENT_PATH, staging_fd)
        source, tuples, source_content_sha = validate_source_decision(
            raw[SOURCE_DECISION_PATH]
        )
        recovery, recovery_content_sha = validate_recovery(
            raw[RECOVERY_DECISION_PATH],
            sha256_bytes(raw[SOURCE_DECISION_PATH]),
            source_content_sha,
        )
        permit, permit_content_sha = validate_permit(
            raw[PERMIT_PATH],
            sha256_bytes(raw[SOURCE_DECISION_PATH]),
            source_content_sha,
            sha256_bytes(raw[RECOVERY_DECISION_PATH]),
            recovery_content_sha,
        )
        validate_claim(
            raw[CLAIM_PATH], permit_content_sha, recovery_content_sha
        )
        resource_bytes = {
            name: raw[f"{FINAL_DIRECTORY_PATH}/{name}"] for name in expected_names
        }
        receipt, observations = validate_receipt_and_resources(
            raw[SUCCESS_RECEIPT_PATH],
            tuples,
            permit_raw_sha=sha256_bytes(raw[PERMIT_PATH]),
            permit_content_sha=permit_content_sha,
            recovery_raw_sha=sha256_bytes(raw[RECOVERY_DECISION_PATH]),
            recovery_content_sha=recovery_content_sha,
            source_raw_sha=sha256_bytes(raw[SOURCE_DECISION_PATH]),
            source_content_sha=source_content_sha,
            claim_raw_sha=sha256_bytes(raw[CLAIM_PATH]),
            resource_bytes=resource_bytes,
        )
        validate_acquisition_manifest(
            raw[ACQUISITION_MANIFEST_PATH],
            raw[SUCCESS_RECEIPT_PATH],
            receipt,
            permit_raw_sha=sha256_bytes(raw[PERMIT_PATH]),
            permit_content_sha=permit_content_sha,
            recovery_raw_sha=sha256_bytes(raw[RECOVERY_DECISION_PATH]),
            recovery_content_sha=recovery_content_sha,
        )
        expected_readback = build_readback_receipt(
            source_raw=raw[SOURCE_DECISION_PATH],
            source_content_sha=source_content_sha,
            recovery_raw=raw[RECOVERY_DECISION_PATH],
            recovery_content_sha=recovery_content_sha,
            permit_raw=raw[PERMIT_PATH],
            permit_content_sha=permit_content_sha,
            claim_raw=raw[CLAIM_PATH],
            receipt_raw=raw[SUCCESS_RECEIPT_PATH],
            acquisition_manifest_raw=raw[ACQUISITION_MANIFEST_PATH],
            receipt=receipt,
            resource_bytes=resource_bytes,
            observations=observations,
        )
        if readback_present:
            validate_readback_documents(
                raw[READBACK_RECEIPT_PATH],
                raw[READBACK_MANIFEST_PATH],
                expected_readback,
                raw[ACQUISITION_MANIFEST_PATH],
            )
        return {
            "documentType": "aetherlink.g2-pion-dependency-wave1-v3-readback-preflight",
            "schemaVersion": "1.0",
            "status": (
                "independent_readback_complete"
                if readback_present
                else "acquired_pending_independent_readback"
            ),
            "validationPassed": True,
            "observedRegularFileCount": (
                POST_READBACK_REGULAR_FILE_COUNT
                if readback_present
                else ACQUISITION_SUCCESS_REGULAR_FILE_COUNT
            ),
            "retainedResourceCount": 38,
            "retainedZipCount": 19,
            "retainedModCount": 19,
            "orderedSourceSetSha256": receipt["orderedSourceSetSha256"],
            "readbackReceiptCandidate": expected_readback,
            "networkOperationCount": 0,
            "fileWriteCount": 0,
            "authenticationRequired": False,
            "nextAction": (
                "prepare_separate_dependency_source_review_wave"
                if readback_present
                else "record_independent_readback_receipt_then_manifest_last"
            ),
        }
    finally:
        for item in reversed(held):
            item.close()
        if accepted_fd >= 0:
            os.close(accepted_fd)
        if staging_fd >= 0:
            os.close(staging_fd)
        os.close(root_fd)


def write_exclusive_owner_only(root_fd: int, relative: str, payload: bytes) -> None:
    require(len(payload) <= MAXIMUM_JSON_BYTES, f"{relative}: output limit")
    parent_fd, name = open_parent(root_fd, relative)
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    fd = -1
    try:
        fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
        os.fchmod(fd, 0o600)
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            require(written > 0, f"{relative}: short write")
            offset += written
        os.fsync(fd)
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == len(payload),
            f"{relative}: published identity",
        )
        os.lseek(fd, 0, os.SEEK_SET)
        reread = b""
        while len(reread) < len(payload):
            chunk = os.read(fd, len(payload) - len(reread))
            if not chunk:
                break
            reread += chunk
        require(reread == payload, f"{relative}: exact write readback")
        os.fsync(parent_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent_fd)


def record_readback(root: Path = ROOT) -> dict[str, Any]:
    state = validate_state(root)
    require(
        state["status"] == "acquired_pending_independent_readback",
        "record requires complete acquisition and absent readback outputs",
    )
    receipt = state["readbackReceiptCandidate"]
    receipt_raw = canonical_json_bytes(receipt)
    manifest = build_readback_manifest(
        receipt_raw,
        receipt,
        canonical_json_bytes(
            strict_json(
                HeldPathRead(root, ACQUISITION_MANIFEST_PATH, MAXIMUM_JSON_BYTES),
                "acquisition manifest record reread",
            )
        ),
    )
    manifest_raw = canonical_json_bytes(manifest)
    root_fd = open_root(root)
    try:
        write_exclusive_owner_only(root_fd, READBACK_RECEIPT_PATH, receipt_raw)
        write_exclusive_owner_only(root_fd, READBACK_MANIFEST_PATH, manifest_raw)
    finally:
        os.close(root_fd)
    final = validate_state(root)
    require(final["status"] == "independent_readback_complete", "record final readback")
    return {
        "documentType": "aetherlink.g2-pion-dependency-wave1-v3-readback-record-result",
        "schemaVersion": "1.0",
        "status": "independent_readback_complete",
        "readbackReceiptRawSha256": sha256_bytes(receipt_raw),
        "readbackManifestRawSha256": sha256_bytes(manifest_raw),
        "networkOperationCount": 0,
        "fileWriteCount": 2,
        "authenticationRequired": False,
        "nextAction": final["nextAction"],
    }


def HeldPathRead(root: Path, relative: str, maximum: int) -> bytes:
    root_fd = open_root(root)
    held: HeldFile | None = None
    try:
        held = HeldFile(root_fd, relative, maximum_bytes=maximum, owner_only=True)
        first = held.read_pass()
        second = held.read_pass()
        require(first == second, f"{relative}: record reread")
        held.final_name_barrier()
        return first
    finally:
        if held is not None:
            held.close()
        os.close(root_fd)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--record", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = record_readback(args.root) if args.record else validate_state(args.root)
    except (CheckError, OSError) as error:
        print(
            canonical_json_bytes(
                {
                    "documentType": "aetherlink.g2-pion-dependency-wave1-v3-readback-result",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "validationPassed": False,
                    "error": str(error),
                    "networkOperationCount": 0,
                    "authenticationRequired": False,
                }
            ).decode("utf-8"),
            end="",
        )
        return 1
    printable = dict(result)
    printable.pop("readbackReceiptCandidate", None)
    print(canonical_json_bytes(printable).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
