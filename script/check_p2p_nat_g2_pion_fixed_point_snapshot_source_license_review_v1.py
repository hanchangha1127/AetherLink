#!/usr/bin/env python3
"""Inspect the exact G2 fixed-point snapshot without writing or executing it.

Run with ``python3 -I -B -S``. The default mode validates the exact retained
369-file snapshot and ZIP metadata. ``--full-scan`` additionally delegates
bounded in-memory member decoding and deterministic graph/source/license
inventory to the pinned Wave1 review implementation, then emits a compact
review-input record to stdout. Neither mode writes files, extracts archives,
executes source, starts subprocesses, or uses the network.
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
            "snapshot review requires unoptimized `python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import types
from typing import Any, Mapping, Sequence
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_fixed_point_"
    "snapshot_source_license_review_v1.py"
)
PINNED_REVIEW_RUNNER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
PINNED_REVIEW_RUNNER_RAW_SHA256 = (
    "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
)
CLOSURE_DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-combined-fixed-point-"
    "closure-review-decision-v1.json"
)
CLOSURE_DECISION_RAW_SHA256 = (
    "affc2b60fd76b07a6e5af94a9492c5b0954d743ed26160e08fab970fbbbd42bd"
)
CLOSURE_DECISION_CONTENT_SHA256 = (
    "9d58b2d1411df8d3a33ae31d5b1868528bdc1b2949574a9d21e48c380666659b"
)
CLOSURE_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-combined-v18-"
    "fixed-point-closure-review-decision-v1"
)
WAVE9_LEGACY_BUILD_SOURCE_SHA256 = (
    "042948d42899becd3c158c680d9c491ca9a57629cc893edea31ef2aae2666443"
)
WAVE9_LEGACY_BUILD_NORMALIZED_SHA256 = (
    "a46760412870548bd5bf6cfb011129769545623276e3b0385f85deb3206045f2"
)
WAVE9_LEGACY_BUILD_ORIGINAL_LINE = (
    "// +build go1.8,!go1.9 // TODO(adonovan) determine which versions "
    "we need to test here"
)
WAVE9_LEGACY_BUILD_NORMALIZED_LINE = "// +build go1.8,!go1.9"
WAVE9_LEGACY_BUILD_EXPRESSION = (
    "((go1.8 && !go1.9)) && ((!windows))"
)
EXPECTED_WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT = 2
EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES = {
    "3cac871d018b70989d15750019e4823d6e523f0fd3a10ec14a2e4e548d4fd771": {
        "relativePath": (
            "cmd/fiximports/testdata/src/old.com/bad/bad.go"
        ),
        "expectedOccurrenceCount": 15,
    },
    "6e3cc7fc92211e454f535a0002a7aca11d4a7f0a468b071b07fe4ed9b0e268da": {
        "relativePath": "go/loader/testdata/badpkgdecl.go",
        "expectedOccurrenceCount": 15,
    },
}
SELF_NORMALIZED_SHA256 = (
    "dd426c7d4094908fcdc8e05822723853878495368ee98af56fdf4ad5d2d41fb0"
)

DEPENDENCY_ROOT = Path(
    "build/offline-source/pion-ice-v4.3.0/dependencies"
)
ROOT_ARCHIVE_PATH = Path(
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
ROOT_MODULE = "github.com/pion/ice/v4"
ROOT_VERSION = "v4.3.0"
WAVE_DIRECTORIES = (
    "wave-1-v3",
    "wave-2-v3",
    *(f"wave-{index}-v1" for index in range(3, 20)),
)
EXPECTED_RESOURCE_COUNTS = (
    38,
    30,
    32,
    32,
    30,
    36,
    30,
    28,
    20,
    22,
    18,
    8,
    8,
    8,
    10,
    6,
    2,
    6,
    4,
)

EXPECTED_SOURCE_INPUT_COUNT = 369
EXPECTED_MODULE_VERSION_TUPLE_COUNT = 184
EXPECTED_ARCHIVE_COUNT = 185
EXPECTED_AGGREGATE_RAW_BYTES = 356_092_640
EXPECTED_AGGREGATE_ENTRY_COUNT = 72_304
EXPECTED_AGGREGATE_UNCOMPRESSED_BYTES = 1_359_347_284
EXPECTED_MAXIMUM_ARCHIVE_BYTES = 9_237_329
EXPECTED_MAXIMUM_ENTRIES_PER_ARCHIVE = 2_065
EXPECTED_MAXIMUM_ENTRY_BYTES = 5_477_310
EXPECTED_MAXIMUM_PATH_UTF8_BYTES = 174
EXPECTED_MAXIMUM_UNCOMPRESSED_BYTES_PER_ARCHIVE = 41_103_581
EXPECTED_LICENSE_CANDIDATE_COUNT_BY_NAME = 362
EXPECTED_GO_FILE_COUNT_BY_SUFFIX = 58_478
EXPECTED_ASSEMBLY_FILE_COUNT_BY_SUFFIX = 1_528
EXPECTED_NATIVE_FILE_COUNT_BY_SUFFIX = 110
EXPECTED_BINARY_FILE_COUNT_BY_SUFFIX = 144
EXPECTED_REVIEW_BINDING_SET_SHA256 = (
    "3423f30722a5d9be67774be1b3dc7f25544ddd9b452c914e891085f0e3e24d23"
)
EXPECTED_METADATA_PREFLIGHT_ARCHIVE_OPEN_COUNT = 369
EXPECTED_DELEGATED_FULL_SCAN_ARCHIVE_OPEN_COUNT = 185
EXPECTED_TOTAL_FULL_SCAN_ARCHIVE_OPEN_COUNT = 554

EXPECTED_PROVIDER_COVERAGE_COUNT = 185
EXPECTED_PROVIDER_COVERAGE_SHA256 = (
    "7bb38b4396173308627878a664fb2bcb17397efb54c3349343ba349b47be1a7f"
)
EXPECTED_PROVIDER_SOURCE_FILE_COUNT = 58_478
EXPECTED_PROVIDER_SOURCE_SURFACE_SHA256 = (
    "6f279a4e3ca5bc010e68150d57df561462818ccc81492636724b356172bf90fd"
)
EXPECTED_PROVIDER_PROFILES_SHA256 = (
    "c0a9b986814d2c803830db702f6c5c9c4fcb0f713dc20e8749e5877e7e195b81"
)
EXPECTED_PROVIDER_NARROW_LICENSE_CANDIDATE_COUNT = 195
EXPECTED_PROVIDER_NARROW_LICENSE_INVENTORY_SHA256 = (
    "4e6990198706a1b408b118473cd0b56ffd61c2626ea2d5bd654f4b0f97cb4e7d"
)
EXPECTED_PROVIDER_SPECIAL_SOURCE_COUNT = 11_150
EXPECTED_PROVIDER_SPECIAL_SOURCE_INVENTORY_SHA256 = (
    "861f99fd8ca01f4224047869585ce7faf9f6e960deb3dcc221bba920f2a8e162"
)
EXPECTED_PROVIDER_MODULE_METADATA_COUNT = 185
EXPECTED_PROVIDER_MODULE_METADATA_SHA256 = (
    "5454e8d2bc745c62891cd29f351f2073be826437f287c35e84b71d2270f5c9de"
)

EXPECTED_V18_GRAPH_SHA256 = (
    "a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba"
)
EXPECTED_PROVIDER_GRAPH_CANONICAL_SHA256 = (
    "98cded658dc479296a5672bb26fbcacfbd1bb9314c7d186a6f0bc8a83d25c482"
)
EXPECTED_PROVIDER_NODE_SET_SHA256 = (
    "970144c5bd6c1a7d8a13a8bdd5c9efc63fc81afab5860ca8fa77fce49871601a"
)
EXPECTED_PROVIDER_EDGE_SET_SHA256 = (
    "25cb01585c5d7fc4ec8840d038a195c513e0383e2a4931947312ea9e47e3db47"
)
EXPECTED_PROVIDER_MODULE_NODE_SET_SHA256 = (
    "78c40a9db79d821476d39323527a04cc2ac0812deff01046227114d1b1a0d598"
)
EXPECTED_PROVIDER_MODULE_EDGE_SET_SHA256 = (
    "24296f253c0a9e40a7831ccca600336e1431cce0f488154afa7851c2c6138a52"
)
EXPECTED_PROVIDER_MODULE_GRAPH_AND_FRONTIER_SHA256 = (
    "b018736e334945b584180c922534db38afe204334456ef2c0ed39e30684952ea"
)
EXPECTED_PROVIDER_GRAPH_NODE_COUNT = 132
EXPECTED_PROVIDER_GRAPH_EDGE_COUNT = 1_047
EXPECTED_PROVIDER_MODULE_NODE_COUNT = 185
EXPECTED_PROVIDER_MODULE_EDGE_COUNT = 471
EXPECTED_PROVIDER_SELECTED_VERSION_COUNT = 33

GO_RELEASE_TAGS_THROUGH_1_24 = tuple(
    f"go1.{minor}" for minor in range(1, 25)
)
EXPECTED_PROVIDER_PROFILES = (
    {
        "profileId": "android_api_26_through_36_arm64_v8a",
        "goos": "android",
        "goarch": "arm64",
        "tags": sorted(
            {
                "android",
                "arm64",
                "arm64.v8.0",
                "cgo",
                "gc",
                "linux",
                "unix",
                *GO_RELEASE_TAGS_THROUGH_1_24,
            }
        ),
    },
    {
        "profileId": "macos_14_or_newer_arm64",
        "goos": "darwin",
        "goarch": "arm64",
        "tags": sorted(
            {
                "arm64",
                "arm64.v8.0",
                "cgo",
                "darwin",
                "gc",
                "unix",
                *GO_RELEASE_TAGS_THROUGH_1_24,
            }
        ),
    },
)

PROFILES = (
    {
        "profileId": "android_api_26_through_36_arm64_v8a",
        "goos": "android",
        "goarch": "arm64",
        "compiler": "gc",
        "goVersion": "1.24",
        "cgoEnabled": True,
        "tags": ["android", "arm64", "unix", "cgo", "gc", "go1.24"],
    },
    {
        "profileId": "macos_14_or_newer_arm64",
        "goos": "darwin",
        "goarch": "arm64",
        "compiler": "gc",
        "goVersion": "1.24",
        "cgoEnabled": True,
        "tags": ["darwin", "arm64", "unix", "cgo", "gc", "go1.24"],
    },
)

MAXIMUM_CONTROL_BYTES = 4 * 1024 * 1024


class ReviewError(RuntimeError):
    """A deterministic fail-closed review error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def expected_snapshot_summary() -> dict[str, Any]:
    return {
        "sourceInputCount": EXPECTED_SOURCE_INPUT_COUNT,
        "moduleVersionTupleCount": EXPECTED_MODULE_VERSION_TUPLE_COUNT,
        "archiveCount": EXPECTED_ARCHIVE_COUNT,
        "aggregateRawBytes": EXPECTED_AGGREGATE_RAW_BYTES,
        "aggregateEntryCount": EXPECTED_AGGREGATE_ENTRY_COUNT,
        "aggregateUncompressedBytes":
            EXPECTED_AGGREGATE_UNCOMPRESSED_BYTES,
        "maximumArchiveBytes": EXPECTED_MAXIMUM_ARCHIVE_BYTES,
        "maximumEntriesPerArchive":
            EXPECTED_MAXIMUM_ENTRIES_PER_ARCHIVE,
        "maximumEntryBytes": EXPECTED_MAXIMUM_ENTRY_BYTES,
        "maximumPathUtf8Bytes": EXPECTED_MAXIMUM_PATH_UTF8_BYTES,
        "maximumUncompressedBytesPerArchive":
            EXPECTED_MAXIMUM_UNCOMPRESSED_BYTES_PER_ARCHIVE,
        "licenseCandidateCountByName":
            EXPECTED_LICENSE_CANDIDATE_COUNT_BY_NAME,
        "goFileCountBySuffix": EXPECTED_GO_FILE_COUNT_BY_SUFFIX,
        "assemblyFileCountBySuffix":
            EXPECTED_ASSEMBLY_FILE_COUNT_BY_SUFFIX,
        "nativeFileCountBySuffix": EXPECTED_NATIVE_FILE_COUNT_BY_SUFFIX,
        "binaryFileCountBySuffix": EXPECTED_BINARY_FILE_COUNT_BY_SUFFIX,
        "reviewBindingSetSha256": EXPECTED_REVIEW_BINDING_SET_SHA256,
    }


def exact_binding_projection(
    bindings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    require(
        type(bindings) is list
        and len(bindings) == EXPECTED_SOURCE_INPUT_COUNT,
        "E_BINDING_SET",
    )
    projection: list[dict[str, Any]] = []
    for index, value in enumerate(bindings):
        require(type(value) is dict, "E_BINDING_SET")
        row = value
        kind = row.get("kind")
        expected_keys = {
            "path",
            "rawSha256",
            "byteSize",
            "kind",
            "module",
            "version",
            "tupleOrder",
        }
        if index == 0 or kind == "zip":
            expected_keys.add("modulePrefix")
        if index > 0:
            expected_keys.update({"tupleId", "wave"})
        require(
            set(row) == expected_keys
            and type(row.get("path")) is str
            and type(row.get("rawSha256")) is str
            and re.fullmatch(
                r"[0-9a-f]{64}",
                row["rawSha256"],
            )
            is not None
            and type(row.get("byteSize")) is int
            and row["byteSize"] >= 0
            and kind in {"root_zip", "mod", "zip"}
            and type(row.get("module")) is str
            and type(row.get("version")) is str
            and type(row.get("tupleOrder")) is int,
            "E_BINDING_SET",
        )
        if index == 0:
            require(
                kind == "root_zip"
                and row["tupleOrder"] == 0
                and row["module"] == ROOT_MODULE
                and row["version"] == ROOT_VERSION,
                "E_BINDING_SET",
            )
        else:
            tuple_order = (index + 1) // 2
            require(
                row["tupleOrder"] == tuple_order
                and row.get("tupleId")
                == f"fixed-point-snapshot-{tuple_order:03d}"
                and type(row.get("wave")) is int
                and 1 <= row["wave"] <= len(WAVE_DIRECTORIES)
                and kind == ("mod" if index % 2 == 1 else "zip"),
                "E_BINDING_SET",
            )
            peer = bindings[index - 1] if kind == "zip" else None
            if peer is not None:
                require(
                    peer["module"] == row["module"]
                    and peer["version"] == row["version"]
                    and peer["tupleOrder"] == row["tupleOrder"]
                    and peer["tupleId"] == row["tupleId"]
                    and peer["wave"] == row["wave"],
                    "E_BINDING_SET",
                )
        projection.append(
            {
                key: row[key]
                for key in (
                    "path",
                    "rawSha256",
                    "byteSize",
                    "kind",
                    "module",
                    "version",
                    "tupleOrder",
                    *(("modulePrefix",) if kind in {"root_zip", "zip"} else ()),
                )
            }
        )
    require(
        sha256(canonical_bytes(projection))
        == EXPECTED_REVIEW_BINDING_SET_SHA256,
        "E_BINDING_SET",
    )
    return projection


def normalized_self_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    require(start >= 0, "E_SELF")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    require(
        payload_end - payload_start == 64
        and raw.find(marker, payload_start) < 0,
        "E_SELF",
    )
    return raw[:payload_start] + (b"0" * 64) + raw[payload_end:]


def safe_relative(value: str) -> str:
    require(
        type(value) is str
        and value
        and not value.startswith("/")
        and "\\" not in value
        and "\x00" not in value,
        "E_PATH",
    )
    parts = value.split("/")
    require(
        all(part not in {"", ".", ".."} for part in parts)
        and PurePosixPath(value).as_posix() == value,
        "E_PATH",
    )
    return value


def file_identity(info: os.stat_result) -> tuple[int, ...]:
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


def read_stable_owner_file(
    root: Path,
    relative: str,
    maximum_bytes: int,
    *,
    owner_only: bool = True,
) -> bytes:
    relative = safe_relative(relative)
    path = root / relative
    try:
        before = os.lstat(path)
    except OSError as error:
        raise ReviewError("E_INPUT") from error
    require(
        stat.S_ISREG(before.st_mode)
        and before.st_nlink == 1
        and before.st_uid in {0, os.geteuid()}
        and 0 <= before.st_size <= maximum_bytes,
        "E_INPUT",
    )
    if owner_only:
        require(stat.S_IMODE(before.st_mode) == 0o600, "E_INPUT")
    else:
        require(stat.S_IMODE(before.st_mode) & 0o022 == 0, "E_INPUT")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        require(file_identity(opened) == file_identity(before), "E_INPUT")
        remaining = opened.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            require(bool(chunk), "E_INPUT")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(descriptor, 1) == b"", "E_INPUT")
        require(
            file_identity(os.fstat(descriptor)) == file_identity(opened),
            "E_INPUT",
        )
    except OSError as error:
        raise ReviewError("E_INPUT") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as error:
        raise ReviewError("E_INPUT") from error
    require(file_identity(after) == file_identity(before), "E_INPUT")
    raw = b"".join(chunks)
    require(len(raw) == before.st_size, "E_INPUT")
    return raw


def parse_module_directive(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewError("E_MODULE") from error
    for line in text.splitlines():
        value = line.split("//", 1)[0].strip()
        if value.startswith("module "):
            module = value.split(None, 1)[1].strip()
            if (
                len(module) >= 2
                and module[0] == module[-1]
                and module[0] in {'"', "'", "`"}
            ):
                module = module[1:-1]
            require(
                bool(module)
                and " " not in module
                and "\\" not in module
                and "\x00" not in module,
                "E_MODULE",
            )
            return module
    raise ReviewError("E_MODULE")


def safe_archive_name(name: str) -> str:
    require(
        type(name) is str
        and name
        and not name.endswith("/")
        and not name.startswith("/")
        and "\\" not in name
        and "\x00" not in name
        and "\n" not in name
        and "\r" not in name
        and unicodedata.normalize("NFC", name) == name,
        "E_ARCHIVE",
    )
    require(
        all(part not in {"", ".", ".."} for part in name.split("/")),
        "E_ARCHIVE",
    )
    return name


def archive_prefix(name: str) -> str:
    at = name.find("@")
    slash = name.find("/", at)
    require(at > 0 and slash > at + 1, "E_ARCHIVE")
    return name[: slash + 1]


def is_license_path(relative: str) -> bool:
    name = PurePosixPath(relative).name.casefold()
    suffix = PurePosixPath(name).suffix
    excluded_source_suffixes = {
        ".go",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hh",
        ".hpp",
        ".m",
        ".mm",
        ".s",
        ".asm",
        ".rs",
        ".java",
        ".kt",
        ".swift",
        ".py",
        ".sh",
    }
    return suffix not in excluded_source_suffixes and bool(
        re.fullmatch(
            (
                r"(?:license|copying|notice|copyright|authors?|patents?|"
                r"third[-_]?party(?:[-_]?licenses?)?)(?:$|[._-].*)"
            ),
            name,
            flags=re.IGNORECASE,
        )
    )


def inspect_archive_metadata(
    raw: bytes,
    expected_module: str,
    expected_version: str,
) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r", allowZip64=False) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ReviewError("E_ARCHIVE") from error
    require(
        0 < len(infos) <= EXPECTED_MAXIMUM_ENTRIES_PER_ARCHIVE,
        "E_ARCHIVE",
    )
    names: set[str] = set()
    folded: set[str] = set()
    prefixes: set[str] = set()
    uncompressed = 0
    maximum_entry = 0
    maximum_path = 0
    license_count = 0
    suffix_counts = {
        "go": 0,
        "assembly": 0,
        "native": 0,
        "binary": 0,
    }
    for info in infos:
        name = safe_archive_name(info.filename)
        folded_name = name.casefold()
        require(
            name not in names
            and folded_name not in folded
            and not (info.flag_bits & 0x1)
            and info.compress_type
            in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED},
            "E_ARCHIVE",
        )
        mode = (info.external_attr >> 16) & 0xFFFF
        require(mode == 0 or stat.S_ISREG(mode), "E_ARCHIVE")
        require(
            0 <= info.file_size <= EXPECTED_MAXIMUM_ENTRY_BYTES,
            "E_ARCHIVE",
        )
        names.add(name)
        folded.add(folded_name)
        prefix = archive_prefix(name)
        prefixes.add(prefix)
        uncompressed += info.file_size
        maximum_entry = max(maximum_entry, info.file_size)
        maximum_path = max(maximum_path, len(name.encode("utf-8")))
    require(len(prefixes) == 1, "E_ARCHIVE")
    prefix = next(iter(prefixes))
    expected_prefix = f"{expected_module}@{expected_version}/"
    require(prefix == expected_prefix, "E_MODULE")
    for name in names:
        relative = name[len(prefix) :]
        suffix = PurePosixPath(relative.casefold()).suffix
        if is_license_path(relative):
            license_count += 1
        if suffix == ".go":
            suffix_counts["go"] += 1
        if suffix in {".s", ".asm"}:
            suffix_counts["assembly"] += 1
        if suffix in {
            ".c",
            ".cc",
            ".cpp",
            ".cxx",
            ".h",
            ".hh",
            ".hpp",
            ".m",
            ".mm",
        }:
            suffix_counts["native"] += 1
        if suffix in {
            ".a",
            ".so",
            ".dylib",
            ".dll",
            ".lib",
            ".exe",
            ".o",
            ".obj",
            ".syso",
        }:
            suffix_counts["binary"] += 1
    return {
        "modulePrefix": prefix,
        "entryCount": len(infos),
        "uncompressedByteCount": uncompressed,
        "maximumEntryBytes": maximum_entry,
        "maximumPathUtf8Bytes": maximum_path,
        "licenseCandidateCountByName": license_count,
        "suffixCounts": suffix_counts,
    }


def tuple_base_names(accepted: Path) -> list[str]:
    try:
        entries = list(accepted.iterdir())
    except OSError as error:
        raise ReviewError("E_LAYOUT") from error
    require(
        all(
            entry.is_file()
            and entry.suffix in {".mod", ".zip"}
            and entry.name.count(".") == 1
            for entry in entries
        ),
        "E_LAYOUT",
    )
    base_names = {entry.stem for entry in entries}
    try:
        ordered = sorted(
            base_names,
            key=lambda value: int(value.split("-", 1)[0]),
        )
    except (ValueError, IndexError) as error:
        raise ReviewError("E_LAYOUT") from error
    require(
        len(entries) == len(ordered) * 2
        and [int(value.split("-", 1)[0]) for value in ordered]
        == list(range(1, len(ordered) + 1)),
        "E_LAYOUT",
    )
    return ordered


def detect_archive_prefix(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r", allowZip64=False) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ReviewError("E_ARCHIVE") from error
    require(bool(infos), "E_ARCHIVE")
    prefixes = {archive_prefix(info.filename) for info in infos}
    require(len(prefixes) == 1, "E_ARCHIVE")
    return next(iter(prefixes))


def build_snapshot(root: Path = ROOT) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    root_relative = ROOT_ARCHIVE_PATH.as_posix()
    root_raw = read_stable_owner_file(
        root,
        root_relative,
        EXPECTED_MAXIMUM_ARCHIVE_BYTES,
    )
    root_metadata = inspect_archive_metadata(
        root_raw,
        ROOT_MODULE,
        ROOT_VERSION,
    )
    bindings.append(
        {
            "path": root_relative,
            "rawSha256": sha256(root_raw),
            "byteSize": len(root_raw),
            "kind": "root_zip",
            "module": ROOT_MODULE,
            "version": ROOT_VERSION,
            "tupleOrder": 0,
            "modulePrefix": root_metadata["modulePrefix"],
        }
    )
    archive_metadata = [root_metadata]
    tuple_order = 0
    require(
        len(WAVE_DIRECTORIES) == len(EXPECTED_RESOURCE_COUNTS),
        "E_LAYOUT",
    )
    for wave_index, (directory, expected_count) in enumerate(
        zip(WAVE_DIRECTORIES, EXPECTED_RESOURCE_COUNTS),
        start=1,
    ):
        accepted = root / DEPENDENCY_ROOT / directory / "accepted"
        bases = tuple_base_names(accepted)
        require(len(bases) * 2 == expected_count, "E_LAYOUT")
        for base in bases:
            tuple_order += 1
            mod_relative = (
                DEPENDENCY_ROOT / directory / "accepted" / f"{base}.mod"
            ).as_posix()
            zip_relative = (
                DEPENDENCY_ROOT / directory / "accepted" / f"{base}.zip"
            ).as_posix()
            mod_raw = read_stable_owner_file(
                root,
                mod_relative,
                EXPECTED_MAXIMUM_ARCHIVE_BYTES,
            )
            zip_raw = read_stable_owner_file(
                root,
                zip_relative,
                EXPECTED_MAXIMUM_ARCHIVE_BYTES,
            )
            module = parse_module_directive(mod_raw)
            prefix = detect_archive_prefix(zip_raw)
            left = prefix[:-1]
            at = left.find("@")
            require(at > 0, "E_MODULE")
            version = left[at + 1 :]
            metadata = inspect_archive_metadata(zip_raw, module, version)
            tuple_id = f"fixed-point-snapshot-{tuple_order:03d}"
            common = {
                "module": module,
                "version": version,
                "tupleOrder": tuple_order,
                "tupleId": tuple_id,
                "wave": wave_index,
            }
            bindings.extend(
                (
                    {
                        **common,
                        "path": mod_relative,
                        "rawSha256": sha256(mod_raw),
                        "byteSize": len(mod_raw),
                        "kind": "mod",
                    },
                    {
                        **common,
                        "path": zip_relative,
                        "rawSha256": sha256(zip_raw),
                        "byteSize": len(zip_raw),
                        "kind": "zip",
                        "modulePrefix": metadata["modulePrefix"],
                    },
                )
            )
            archive_metadata.append(metadata)
    binding_projection = exact_binding_projection(bindings)
    summary = {
        "sourceInputCount": len(bindings),
        "moduleVersionTupleCount": tuple_order,
        "archiveCount": len(archive_metadata),
        "aggregateRawBytes": sum(row["byteSize"] for row in bindings),
        "aggregateEntryCount": sum(
            row["entryCount"] for row in archive_metadata
        ),
        "aggregateUncompressedBytes": sum(
            row["uncompressedByteCount"] for row in archive_metadata
        ),
        "maximumArchiveBytes": max(
            row["byteSize"]
            for row in bindings
            if row["kind"] in {"root_zip", "zip"}
        ),
        "maximumEntriesPerArchive": max(
            row["entryCount"] for row in archive_metadata
        ),
        "maximumEntryBytes": max(
            row["maximumEntryBytes"] for row in archive_metadata
        ),
        "maximumPathUtf8Bytes": max(
            row["maximumPathUtf8Bytes"] for row in archive_metadata
        ),
        "maximumUncompressedBytesPerArchive": max(
            row["uncompressedByteCount"] for row in archive_metadata
        ),
        "licenseCandidateCountByName": sum(
            row["licenseCandidateCountByName"] for row in archive_metadata
        ),
        "goFileCountBySuffix": sum(
            row["suffixCounts"]["go"] for row in archive_metadata
        ),
        "assemblyFileCountBySuffix": sum(
            row["suffixCounts"]["assembly"] for row in archive_metadata
        ),
        "nativeFileCountBySuffix": sum(
            row["suffixCounts"]["native"] for row in archive_metadata
        ),
        "binaryFileCountBySuffix": sum(
            row["suffixCounts"]["binary"] for row in archive_metadata
        ),
        "reviewBindingSetSha256": sha256(
            canonical_bytes(binding_projection)
        ),
    }
    expected = expected_snapshot_summary()
    require(summary == expected, "E_SNAPSHOT")
    return bindings, summary


def strict_control_json(raw: bytes) -> dict[str, Any]:
    require(len(raw) <= MAXIMUM_CONTROL_BYTES, "E_CONTROL")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReviewError("E_CONTROL") from error
    require(type(value) is dict, "E_CONTROL")
    return value


def validate_controls(root: Path = ROOT) -> None:
    self_raw = read_stable_owner_file(
        root,
        SELF_PATH,
        MAXIMUM_CONTROL_BYTES,
        owner_only=False,
    )
    require(
        sha256(normalized_self_bytes(self_raw)) == SELF_NORMALIZED_SHA256,
        "E_SELF",
    )
    runner_raw = read_stable_owner_file(
        root,
        PINNED_REVIEW_RUNNER_PATH,
        MAXIMUM_CONTROL_BYTES,
        owner_only=False,
    )
    require(
        sha256(runner_raw) == PINNED_REVIEW_RUNNER_RAW_SHA256,
        "E_RUNNER",
    )
    closure_raw = read_stable_owner_file(
        root,
        CLOSURE_DECISION_PATH,
        MAXIMUM_CONTROL_BYTES,
        owner_only=False,
    )
    require(
        sha256(closure_raw) == CLOSURE_DECISION_RAW_SHA256,
        "E_CLOSURE",
    )
    closure = strict_control_json(closure_raw)
    require(
        closure.get("contentBinding", {}).get("sha256")
        == CLOSURE_DECISION_CONTENT_SHA256
        and closure.get("closure", {}).get(
            "dependencyFixedPointReached"
        )
        is True
        and closure.get("authority", {}).get(
            "externalAuthenticationRequired"
        )
        is False
        and closure.get("authority", {}).get("userActionRequired") is False,
        "E_CLOSURE",
    )


def load_pinned_review_runner(root: Path = ROOT) -> types.ModuleType:
    path = root / PINNED_REVIEW_RUNNER_PATH
    spec = importlib.util.spec_from_file_location(
        "g2_pion_fixed_point_snapshot_review_provider_v1",
        path,
    )
    require(spec is not None and spec.loader is not None, "E_RUNNER")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException as error:
        raise ReviewError("E_RUNNER") from error
    original_extract = module.extract_build_expression
    original_inspect_zip = module.inspect_zip_bytes
    compatibility_state = {
        "wave9LegacyBuildCount": 0,
        "wave9LegacyNonProductionOccurrenceCount": 0,
        "malformedNonProductionBuildCountBySha256": {
            digest: 0 for digest in EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES
        },
        "malformedNonProductionOccurrenceCountBySha256": {
            digest: 0 for digest in EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES
        },
    }

    def exact_legacy_extract(text: str) -> str | None:
        try:
            return original_extract(text)
        except module.ReviewFailure as error:
            raw = text.encode("utf-8", errors="strict")
            digest = sha256(raw)
            if (
                error.code == "E_BUILD_CONSTRAINT"
                and error.phase == "source_inventory"
                and digest == WAVE9_LEGACY_BUILD_SOURCE_SHA256
                and text.count(WAVE9_LEGACY_BUILD_ORIGINAL_LINE) == 1
            ):
                before, separator, after = text.partition(
                    WAVE9_LEGACY_BUILD_ORIGINAL_LINE
                )
                require(
                    separator == WAVE9_LEGACY_BUILD_ORIGINAL_LINE,
                    "E_LEGACY_BUILD",
                )
                normalized = (
                    before + WAVE9_LEGACY_BUILD_NORMALIZED_LINE + after
                )
                require(
                    sha256(normalized.encode("utf-8", errors="strict"))
                    == WAVE9_LEGACY_BUILD_NORMALIZED_SHA256,
                    "E_LEGACY_BUILD",
                )
                expression = original_extract(normalized)
                require(
                    expression == WAVE9_LEGACY_BUILD_EXPRESSION,
                    "E_LEGACY_BUILD",
                )
                compatibility_state["wave9LegacyBuildCount"] += 1
                return expression
            if (
                error.code == "E_BUILD_CONSTRAINT"
                and error.phase == "source_inventory"
                and digest in EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES
            ):
                compatibility_state[
                    "malformedNonProductionBuildCountBySha256"
                ][digest] += 1
                return None
            raise

    def exact_nonproduction_inspect_zip(
        raw: bytes,
        binding: Mapping[str, Any],
        limits: Mapping[str, Any],
    ) -> dict[str, Any]:
        reviewed = original_inspect_zip(raw, binding, limits)
        sources = reviewed.get("sources")
        require(type(sources) is list, "E_FIXTURE_COMPATIBILITY")
        for source in sources:
            require(type(source) is dict, "E_FIXTURE_COMPATIBILITY")
            digest = source.get("rawSha256")
            if digest == WAVE9_LEGACY_BUILD_SOURCE_SHA256:
                require(
                    source.get("sourceClass") != "production",
                    "E_FIXTURE_COMPATIBILITY",
                )
                compatibility_state[
                    "wave9LegacyNonProductionOccurrenceCount"
                ] += 1
            fixture = EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES.get(digest)
            if fixture is not None:
                require(
                    reviewed.get("module") == "golang.org/x/tools"
                    and source.get("sourceClass") == "example"
                    and source.get("relativePath")
                    == fixture["relativePath"],
                    "E_FIXTURE_COMPATIBILITY",
                )
                compatibility_state[
                    "malformedNonProductionOccurrenceCountBySha256"
                ][digest] += 1
        return reviewed

    module.extract_build_expression = exact_legacy_extract
    module.inspect_zip_bytes = exact_nonproduction_inspect_zip
    module.snapshot_legacy_compatibility_state = compatibility_state
    for name in (
        "execute_with_authority",
        "write_exclusive",
        "manifest_document",
        "durable_failure_document",
        "claim_document",
        "main",
    ):
        if hasattr(module, name):
            delattr(module, name)
    return module


def runner_bindings(bindings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **dict(row),
            "maximumBytes": row["byteSize"],
            "ownerOnly": True,
        }
        for row in bindings
    ]


def compact_full_scan(
    bindings: Sequence[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    root: Path = ROOT,
) -> dict[str, Any]:
    require(
        type(snapshot) is dict
        and snapshot == expected_snapshot_summary(),
        "E_SNAPSHOT",
    )
    exact_binding_projection(bindings)
    runner = load_pinned_review_runner(root)
    permit = {
        "permitId": (
            "local-read-only-fixed-point-snapshot-review-contract-v1"
        ),
        "decisionBinding": {
            "decisionId": CLOSURE_DECISION_ID,
            "contentSha256": CLOSURE_DECISION_CONTENT_SHA256,
            "profiles": [
                {
                    "profileId": profile["profileId"],
                    "tags": list(profile["tags"]),
                }
                for profile in PROFILES
            ]
        },
        "contentBinding": {
            "sha256": CLOSURE_DECISION_CONTENT_SHA256,
        },
        "resourceLimits": {
            "maximumArchiveBytes": EXPECTED_MAXIMUM_ARCHIVE_BYTES,
            "maximumSingleFileBytes": EXPECTED_MAXIMUM_ENTRY_BYTES,
            "maximumEntriesPerArchive":
                EXPECTED_MAXIMUM_ENTRIES_PER_ARCHIVE,
            "maximumAggregateEntries": EXPECTED_AGGREGATE_ENTRY_COUNT,
            "maximumAggregateUncompressedBytes":
                EXPECTED_AGGREGATE_UNCOMPRESSED_BYTES,
            "maximumGraphNodes": 512,
            "maximumGraphEdges": 4_096,
            "maximumResultOrFailureBytes": 64 * 1024 * 1024,
        },
    }
    held_bindings = runner_bindings(bindings)
    try:
        with runner.HeldInputSet(root, held_bindings) as held:
            reviewed = runner.review_held_inputs(
                permit,
                held_bindings,
                held,
            )
            held.final_barrier()
    except BaseException as error:
        raise ReviewError("E_FULL_SCAN") from error
    try:
        compatibility = runner.snapshot_legacy_compatibility_state
        require(
            type(compatibility) is dict
            and compatibility.get("wave9LegacyBuildCount")
            == EXPECTED_WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
            and compatibility.get(
                "wave9LegacyNonProductionOccurrenceCount"
            )
            == EXPECTED_WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
            "E_LEGACY_BUILD",
        )
        build_counts = compatibility.get(
            "malformedNonProductionBuildCountBySha256"
        )
        occurrence_counts = compatibility.get(
            "malformedNonProductionOccurrenceCountBySha256"
        )
        require(
            type(build_counts) is dict
            and type(occurrence_counts) is dict
            and set(build_counts)
            == set(EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES)
            and set(occurrence_counts)
            == set(EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES),
            "E_FIXTURE_COMPATIBILITY",
        )
        for digest, fixture in (
            EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES.items()
        ):
            require(
                build_counts.get(digest)
                == fixture["expectedOccurrenceCount"]
                and occurrence_counts.get(digest)
                == fixture["expectedOccurrenceCount"],
                "E_FIXTURE_COMPATIBILITY",
            )

        require(type(reviewed) is dict, "E_FULL_SCAN")
        coverage = reviewed.get("coverage")
        source_surface = reviewed.get("sourceSurface")
        license_inventory = reviewed.get("licenseInventory")
        special_inventory = reviewed.get("specialSourceInventory")
        module_metadata = reviewed.get("moduleMetadata")
        graph = reviewed.get("graphDiscovery")
        require(
            type(coverage) is dict
            and type(source_surface) is dict
            and type(license_inventory) is dict
            and type(special_inventory) is dict
            and type(module_metadata) is dict
            and type(graph) is dict,
            "E_FULL_SCAN",
        )
        coverage_rows = coverage.get("modules")
        profiles = source_surface.get("profiles")
        license_rows = license_inventory.get("entries")
        special_rows = special_inventory.get("entries")
        metadata_rows = module_metadata.get("modules")
        require(
            type(coverage_rows) is list
            and type(profiles) is list
            and type(license_rows) is list
            and type(special_rows) is list
            and type(metadata_rows) is list,
            "E_FULL_SCAN",
        )

        expected_profiles = [
            {
                "profileId": row["profileId"],
                "goos": row["goos"],
                "goarch": row["goarch"],
                "tags": list(row["tags"]),
            }
            for row in EXPECTED_PROVIDER_PROFILES
        ]
        coverage_sha256 = sha256(canonical_bytes(coverage_rows))
        profiles_sha256 = sha256(canonical_bytes(profiles))
        narrow_license_sha256 = sha256(canonical_bytes(license_rows))
        special_sha256 = sha256(canonical_bytes(special_rows))
        metadata_sha256 = sha256(canonical_bytes(metadata_rows))
        graph_canonical_sha256 = sha256(canonical_bytes(graph))

        require(
            len(coverage_rows) == EXPECTED_PROVIDER_COVERAGE_COUNT
            and coverage_sha256 == EXPECTED_PROVIDER_COVERAGE_SHA256
            and coverage.get("aggregateEntryCount")
            == EXPECTED_AGGREGATE_ENTRY_COUNT
            and coverage.get("aggregateUncompressedBytes")
            == EXPECTED_AGGREGATE_UNCOMPRESSED_BYTES
            and coverage.get("omittedArchiveCount") == 0
            and coverage.get("filesystemExtractionCount") == 0,
            "E_FULL_SCAN",
        )
        require(
            profiles == expected_profiles
            and profiles_sha256 == EXPECTED_PROVIDER_PROFILES_SHA256
            and source_surface.get("sourceFileCount")
            == EXPECTED_PROVIDER_SOURCE_FILE_COUNT
            and source_surface.get("sourceSurfaceSha256")
            == EXPECTED_PROVIDER_SOURCE_SURFACE_SHA256,
            "E_FULL_SCAN",
        )
        require(
            len(license_rows)
            == EXPECTED_PROVIDER_NARROW_LICENSE_CANDIDATE_COUNT
            and narrow_license_sha256
            == EXPECTED_PROVIDER_NARROW_LICENSE_INVENTORY_SHA256
            and license_inventory.get("licenseCandidateCount")
            == EXPECTED_PROVIDER_NARROW_LICENSE_CANDIDATE_COUNT
            and license_inventory.get("compatibilityReviewed") is False,
            "E_FULL_SCAN",
        )
        require(
            len(special_rows) == EXPECTED_PROVIDER_SPECIAL_SOURCE_COUNT
            and special_sha256
            == EXPECTED_PROVIDER_SPECIAL_SOURCE_INVENTORY_SHA256
            and special_inventory.get("specialSourceCount")
            == EXPECTED_PROVIDER_SPECIAL_SOURCE_COUNT
            and special_inventory.get("executed") is False,
            "E_FULL_SCAN",
        )
        require(
            len(metadata_rows) == EXPECTED_PROVIDER_MODULE_METADATA_COUNT
            and metadata_sha256
            == EXPECTED_PROVIDER_MODULE_METADATA_SHA256,
            "E_FULL_SCAN",
        )
        require(
            graph_canonical_sha256
            == EXPECTED_PROVIDER_GRAPH_CANONICAL_SHA256
            and graph.get("algorithm")
            == "go1.24_mvs_profile_union_fixed_point_v1"
            and graph.get("graphSha256") == EXPECTED_V18_GRAPH_SHA256
            and graph.get("reconstructionProjectionSha256")
            == EXPECTED_V18_GRAPH_SHA256
            and graph.get("nodeSetSha256")
            == EXPECTED_PROVIDER_NODE_SET_SHA256
            and graph.get("edgeSetSha256")
            == EXPECTED_PROVIDER_EDGE_SET_SHA256
            and graph.get("moduleNodeSetSha256")
            == EXPECTED_PROVIDER_MODULE_NODE_SET_SHA256
            and graph.get("moduleEdgeSetSha256")
            == EXPECTED_PROVIDER_MODULE_EDGE_SET_SHA256
            and graph.get("moduleGraphAndFrontierSha256")
            == EXPECTED_PROVIDER_MODULE_GRAPH_AND_FRONTIER_SHA256
            and graph.get("graphNodeCount")
            == EXPECTED_PROVIDER_GRAPH_NODE_COUNT
            and graph.get("graphEdgeCount")
            == EXPECTED_PROVIDER_GRAPH_EDGE_COUNT
            and graph.get("moduleNodeCount")
            == EXPECTED_PROVIDER_MODULE_NODE_COUNT
            and graph.get("moduleEdgeCount")
            == EXPECTED_PROVIDER_MODULE_EDGE_COUNT
            and type(graph.get("selectedVersions")) is list
            and len(graph["selectedVersions"])
            == EXPECTED_PROVIDER_SELECTED_VERSION_COUNT
            and graph.get("exactFrontier") == []
            and graph.get("newlyReachableTuples") == []
            and graph.get("unmappedExternalImports") == []
            and graph.get("unresolvedDeclaredExternalImports") == []
            and graph.get("newTupleCount") == 0
            and graph.get("unmappedExternalImportCount") == 0
            and graph.get("unresolvedDeclaredExternalImportCount") == 0
            and graph.get("fixedPointReached") is True
            and graph.get("independentReproductionPassed") is True
            and graph.get("reconstructionCount") == 2,
            "E_FULL_SCAN",
        )

        result = {
            "schemaVersion": "1.0",
            "documentType": (
                "aetherlink.g2-pion-fixed-point-snapshot-"
                "source-license-review-input"
            ),
            "status": (
                "exact_snapshot_static_review_input_projection_complete_"
                "independent_two_pass_review_pending"
            ),
            "closurePredecessorBinding": {
                "decisionId": CLOSURE_DECISION_ID,
                "rawSha256": CLOSURE_DECISION_RAW_SHA256,
                "contentSha256": CLOSURE_DECISION_CONTENT_SHA256,
            },
            "snapshotBinding": dict(snapshot),
            "profiles": profiles,
            "coverage": {
                "moduleCoverageCount": len(coverage_rows),
                "moduleCoverageSha256": coverage_sha256,
                "sourceFileCount":
                    source_surface["sourceFileCount"],
                "sourceSurfaceSha256":
                    source_surface["sourceSurfaceSha256"],
                "pinnedRunnerNarrowLicenseCandidateCount":
                    len(license_rows),
                "pinnedRunnerNarrowLicenseInventorySha256":
                    narrow_license_sha256,
                "broadLicenseCandidateCountByName":
                    snapshot["licenseCandidateCountByName"],
                "specialSourceCount": len(special_rows),
                "specialSourceInventorySha256": special_sha256,
                "moduleMetadataCount": len(metadata_rows),
                "moduleMetadataSha256": metadata_sha256,
            },
            "graph": {
                "algorithm": graph["algorithm"],
                "fixedPointReached": True,
                "newTupleCount": 0,
                "unmappedExternalImportCount": 0,
                "unresolvedDeclaredExternalImportCount": 0,
                "graphSha256": graph["graphSha256"],
                "canonicalProjectionSha256": graph_canonical_sha256,
                "nodeSetSha256": graph["nodeSetSha256"],
                "edgeSetSha256": graph["edgeSetSha256"],
                "moduleNodeSetSha256":
                    graph["moduleNodeSetSha256"],
                "moduleEdgeSetSha256":
                    graph["moduleEdgeSetSha256"],
                "moduleGraphAndFrontierSha256":
                    graph["moduleGraphAndFrontierSha256"],
                "graphNodeCount": graph["graphNodeCount"],
                "graphEdgeCount": graph["graphEdgeCount"],
                "moduleNodeCount": graph["moduleNodeCount"],
                "moduleEdgeCount": graph["moduleEdgeCount"],
                "selectedVersionCount": len(
                    graph["selectedVersions"]
                ),
            },
            "reviewContract": {
                "independentPassCountRequired": 2,
                "independentPassCountCompleted": 0,
                "requiredModel": "GPT-5.6 Sol",
                "passOutputsAttestAuthority": False,
                "disagreementDisposition": "unresolved",
                "reviewPerformedByThisAdapter": False,
                "inventoryProjectionIsSbom": False,
                "inventoryProjectionIsLicenseCompatibilityDecision": False,
                "inventoryProjectionIsSecurityAcceptance": False,
            },
            "operationCounters": {
                "metadataPreflightZipArchiveOpenCount":
                    EXPECTED_METADATA_PREFLIGHT_ARCHIVE_OPEN_COUNT,
                "delegatedFullScanZipArchiveOpenCount":
                    EXPECTED_DELEGATED_FULL_SCAN_ARCHIVE_OPEN_COUNT,
                "totalZipArchiveOpenCount":
                    EXPECTED_TOTAL_FULL_SCAN_ARCHIVE_OPEN_COUNT,
                "archiveExtractionCount": 0,
                "sourceExecutionCount": 0,
                "sourceCompilationCount": 0,
                "subprocessCount": 0,
                "networkOperationCount": 0,
                "fileWriteCount": 0,
                "wave9PinnedLegacyBuildCompatibilityCount":
                    EXPECTED_WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
                "malformedNonProductionGoFixtureCompatibilityCount":
                    sum(
                        row["expectedOccurrenceCount"]
                        for row in (
                            EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES.values()
                        )
                    ),
            },
            "closure": {
                "dependencyFixedPointReached": True,
                "dependencySourceReviewed": False,
                "dependencyClosureComplete": False,
                "semanticClosureComplete": False,
                "licenseCompatibilityReviewed": False,
                "securityReviewComplete": False,
                "rungThreeComplete": False,
                "candidateSelected": False,
                "librarySelected": False,
                "releaseReady": False,
            },
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "perform_two_independent_gpt_5_6_sol_"
                "fixed_point_snapshot_source_license_security_review_passes"
            ),
        }
    except ReviewError:
        raise
    except BaseException as error:
        raise ReviewError("E_FULL_SCAN") from error
    return result


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ReviewError("E_ARGUMENT")


def parse_arguments(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    parser.add_argument(
        "--full-scan",
        action="store_true",
        help="decode and classify all retained archive members in memory",
    )
    return parser.parse_args(argv)


def inventory_result(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "documentType": (
            "aetherlink.g2-pion-fixed-point-snapshot-"
            "source-license-review-preflight"
        ),
        "status": "exact_snapshot_preflight_validated",
        "validationPassed": True,
        "snapshotBinding": dict(snapshot),
        "profiles": [dict(profile) for profile in PROFILES],
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "fileWriteCount": 0,
        "nextAction": (
            "run_same_adapter_with_full_scan_for_"
            "deterministic_review_input_projection"
        ),
    }


def error_result(code: str) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "documentType": (
            "aetherlink.g2-pion-fixed-point-snapshot-"
            "source-license-review-error"
        ),
        "status": "verification_failed",
        "error": code,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "fileWriteCount": 0,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = parse_arguments(argv)
        validate_controls(ROOT)
        bindings, snapshot = build_snapshot(ROOT)
        if arguments.full_scan:
            result = compact_full_scan(bindings, snapshot, ROOT)
        else:
            result = inventory_result(snapshot)
        sys.stdout.buffer.write(canonical_bytes(result))
        sys.stdout.buffer.flush()
        return 0
    except ReviewError as error:
        sys.stdout.buffer.write(canonical_bytes(error_result(error.code)))
        sys.stdout.buffer.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
