#!/usr/bin/env python3
"""Produce one source-bound Android Release A/B repeatability result."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Iterator, Mapping, Sequence

if __package__:
    from script import check_release_artifact_archive as archive
else:
    import check_release_artifact_archive as archive


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULT = (
    ROOT
    / ".build/aetherlink-android-release-repeatability-v1/result.json"
)
CONTRACT = "aetherlink-android-release-ab-repeatability-current-v1"
SCHEMA_VERSION = 1
SOURCE_ALGORITHM = "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
SOURCE_EXTRAS = (
    Path(".github/workflows/product-quality.yml"),
    Path("script/check_product_ci.py"),
    Path("script/run_android_release_repeatability_current.py"),
    Path("script/check_android_release_repeatability_current.py"),
    Path("script/test_run_android_release_repeatability_current.py"),
    Path("script/test_check_android_release_repeatability_current.py"),
)
PREPARE_COMMAND = (
    sys.executable,
    "-B",
    "script/check_product_ci.py",
)
BUILD_COMMAND = (
    "./gradlew",
    "--offline",
    "--no-daemon",
    "--console=plain",
    "--rerun-tasks",
    "-PaetherlinkStrictReleaseDependencyLocks=true",
    "-Pkotlin.incremental=false",
    ":app:assembleRelease",
    ":app:bundleRelease",
    ":app:lintRelease",
)
BUILD_TIMEOUT_SECONDS = 1_800
BUILD_OUTPUT_MAX_BYTES = 32 * 1024 * 1024
TERMINATION_GRACE_SECONDS = 5.0
MAX_RESULT_BYTES = 4 * 1024 * 1024
APK_LIMIT = 256 * 1024 * 1024
AAB_LIMIT = 256 * 1024 * 1024
NATIVE_LIMIT = 512 * 1024 * 1024
NATIVE_ABI_COUNT_LIMIT = 16
NATIVE_FILE_COUNT_LIMIT = 1_024
OUTPUT_GRAPH_FILE_COUNT_LIMIT = 2_048
OUTPUT_GRAPH_TOTAL_BYTES_LIMIT = 3 * 1024 * 1024 * 1024
SMALL_LIMIT = 16 * 1024 * 1024
LIMITATIONS = (
    "same-host-current-toolchain-only",
    "not-cross-host-or-universal-bit-for-bit-reproducibility",
    "unsigned-android-release-output-only",
    "not-install-launch-device-network-signing-store-rc-ga-or-v1-evidence",
)
DM_COMPARISON_KIND = "safe-zip-logical-members-v1"
MAPPING_PRT_COMPARISON_KIND = "r8-mapping-prt-canonical-v1"
RESOURCES_COMPARISON_KIND = "r8-resources-canonical-v1"
SEEDS_COMPARISON_KIND = "r8-line-artifact-canonical-v1"
RAW_COMPARISON_KIND = "raw-sha256-v1"
NORMALIZED_COMPARISON_PATHS = frozenset(
    {
        (archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/0/app-release-unsigned.dm").as_posix(),
        (archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/1/app-release-unsigned.dm").as_posix(),
        (archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "mapping.prt").as_posix(),
        (archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "resources.txt").as_posix(),
        (archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "seeds.txt").as_posix(),
    }
)


class RepeatabilityError(RuntimeError):
    pass


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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative_path(value: Path) -> Path:
    if (
        not isinstance(value, Path)
        or value.is_absolute()
        or value in (Path(""), Path("."), Path(".."))
        or any(part in ("", ".", "..") for part in value.parts)
        or Path(*value.parts) != value
    ):
        raise RepeatabilityError(f"invalid repository-relative path: {value!r}")
    try:
        value.as_posix().encode("ascii")
    except UnicodeEncodeError as error:
        raise RepeatabilityError(f"non-ASCII repository-relative path: {value}") from error
    return value


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def stable_file(
    relative: Path,
    *,
    root: Path = ROOT,
    maximum_bytes: int,
) -> tuple[dict[str, object], bytes]:
    relative = _relative_path(relative)
    path = root / relative
    try:
        before = path.lstat()
    except OSError as error:
        raise RepeatabilityError(f"cannot inspect {relative}: {error}") from error
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
    ):
        raise RepeatabilityError(
            f"output must be a single-link regular non-symlink file: {relative}"
        )
    try:
        data = archive.read_stable_regular_file(
            path,
            f"Android repeatability output {relative.as_posix()}",
            maximum_bytes=maximum_bytes,
        )
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityError(str(error)) from error
    try:
        after = path.lstat()
    except OSError as error:
        raise RepeatabilityError(f"cannot reinspect {relative}: {error}") from error
    if _stat_identity(before) != _stat_identity(after):
        raise RepeatabilityError(f"output changed around stable read: {relative}")
    return (
        {
            "mode": stat.S_IMODE(after.st_mode),
            "path": relative.as_posix(),
            "sha256": sha256(data),
            "size": len(data),
        },
        data,
    )


def source_snapshot(*, root: Path = ROOT) -> dict[str, object]:
    try:
        paths = {
            Path(value) for value in archive.collect_current_source_paths(root)
        }
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityError(str(error)) from error
    paths.update(SOURCE_EXTRAS)
    ordered = tuple(sorted(paths, key=lambda item: item.as_posix().encode("ascii")))
    digest = hashlib.sha256()
    total_size = 0
    for relative in ordered:
        record, _ = stable_file(
            relative,
            root=root,
            maximum_bytes=64 * 1024 * 1024,
        )
        digest.update(relative.as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(f"{record['mode']:o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
        total_size += int(record["size"])
    return {
        "algorithm": SOURCE_ALGORITHM,
        "fileCount": len(ordered),
        "sha256": digest.hexdigest(),
        "size": total_size,
    }


def _require_inventory(path: Path, names: set[str], label: str) -> None:
    try:
        archive.require_directory_inventory(path, names, label)
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityError(str(error)) from error


def directory_names(path: Path, label: str, *, entries_are_directories: bool) -> set[str]:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RepeatabilityError(f"cannot open {label}: {error}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISDIR(before.st_mode):
            raise RepeatabilityError(f"{label} must be a physical directory")
        names = os.listdir(descriptor)
        result: set[str] = set()
        for name in names:
            try:
                name.encode("ascii")
            except UnicodeEncodeError as error:
                raise RepeatabilityError(f"{label} contains a non-ASCII name") from error
            if name in ("", ".", "..") or "/" in name or name in result:
                raise RepeatabilityError(f"{label} contains a noncanonical name")
            value = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            expected = stat.S_ISDIR(value.st_mode) if entries_are_directories else stat.S_ISREG(value.st_mode)
            if stat.S_ISLNK(value.st_mode) or not expected:
                kind = "directory" if entries_are_directories else "regular file"
                raise RepeatabilityError(f"{label}/{name} must be a physical {kind}")
            result.add(name)
        after = os.fstat(descriptor)
        if _stat_identity(before) != _stat_identity(after):
            raise RepeatabilityError(f"{label} changed during inventory")
        return result
    except OSError as error:
        raise RepeatabilityError(f"cannot inspect {label}: {error}") from error
    finally:
        os.close(descriptor)


def _zip_members(data: bytes, label: str) -> dict[str, bytes]:
    try:
        return archive.read_safe_zip_members(
            data,
            label,
            maximum_members=8_192,
            maximum_member_bytes=268_435_456,
            maximum_total_uncompressed_bytes=536_870_912,
        )
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityError(str(error)) from error


def _logical_members(members: Mapping[str, bytes], domain: bytes) -> str:
    return archive.logical_member_digest(dict(members), domain)


def comparison_identity(relative: Path, data: bytes) -> dict[str, str]:
    path = relative.as_posix()
    try:
        if path.endswith(".dm") and path in NORMALIZED_COMPARISON_PATHS:
            members = archive.read_safe_zip_members(
                data,
                f"Android repeatability baseline profile {path}",
                maximum_members=2,
                maximum_member_bytes=16_777_216,
                maximum_total_uncompressed_bytes=33_554_432,
            )
            value = archive.logical_member_digest(
                members,
                b"AETHERLINK-ANDROID-DM-LOGICAL-MEMBERS-V1\0",
            )
            kind = DM_COMPARISON_KIND
        elif path.endswith("/mapping.prt"):
            value = sha256(archive.canonicalize_r8_mapping_prt(data, path))
            kind = MAPPING_PRT_COMPARISON_KIND
        elif path.endswith("/resources.txt"):
            value = sha256(archive.canonicalize_r8_resources(data, path))
            kind = RESOURCES_COMPARISON_KIND
        elif path.endswith("/seeds.txt"):
            value = sha256(archive.canonicalize_r8_line_artifact(data, path))
            kind = SEEDS_COMPARISON_KIND
        else:
            value = sha256(data)
            kind = RAW_COMPARISON_KIND
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityError(str(error)) from error
    return {"kind": kind, "sha256": value}


def _raw_graph_digest(records: Sequence[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"AETHERLINK-ANDROID-RELEASE-RAW-OUTPUT-GRAPH-V1\0")
    digest.update(len(records).to_bytes(8, "big"))
    for record in records:
        digest.update(str(record["path"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(f"{record['mode']:o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _comparison_graph_digest(records: Sequence[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"AETHERLINK-ANDROID-RELEASE-COMPARISON-GRAPH-V1\0")
    digest.update(len(records).to_bytes(8, "big"))
    for record in records:
        comparison = record["comparison"]
        assert isinstance(comparison, dict)
        digest.update(str(record["path"]).encode("ascii") + b"\0")
        digest.update(f"{record['mode']:o}".encode("ascii") + b"\0")
        digest.update(str(comparison["kind"]).encode("ascii") + b"\0")
        digest.update(str(comparison["sha256"]).encode("ascii") + b"\n")
    return digest.hexdigest()


def capture_output_graph(
    *,
    root: Path = ROOT,
) -> tuple[dict[str, object], dict[str, bytes]]:
    apk_relative = archive.ANDROID_RELEASE_APK_RELATIVE_PATH
    metadata_relative = archive.ANDROID_RELEASE_APK_METADATA_RELATIVE_PATH
    aab_relative = archive.ANDROID_RELEASE_AAB_RELATIVE_PATH
    mapping_root = archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH
    sdk_relative = archive.ANDROID_RELEASE_SDK_DEPENDENCIES_RELATIVE_PATH

    _require_inventory(
        root / apk_relative.parent,
        {apk_relative.name, metadata_relative.name, "baselineProfiles"},
        "Android repeatability APK output directory",
    )
    _require_inventory(
        root / apk_relative.parent / "baselineProfiles",
        {"0", "1"},
        "Android repeatability baseline profile directory",
    )
    for index in ("0", "1"):
        _require_inventory(
            root / apk_relative.parent / "baselineProfiles" / index,
            {"app-release-unsigned.dm"},
            f"Android repeatability baseline profile {index} directory",
        )
    _require_inventory(
        root / aab_relative.parent,
        {aab_relative.name},
        "Android repeatability AAB output directory",
    )
    _require_inventory(
        root / mapping_root,
        set(archive.ANDROID_RELEASE_MAPPING_FILES),
        "Android repeatability mapping directory",
    )
    _require_inventory(
        root / sdk_relative.parent,
        {sdk_relative.name},
        "Android repeatability SDK dependency directory",
    )

    file_limits: dict[Path, int] = {
        apk_relative: APK_LIMIT,
        metadata_relative: SMALL_LIMIT,
        aab_relative: AAB_LIMIT,
        sdk_relative: SMALL_LIMIT,
        apk_relative.parent
        / "baselineProfiles/0/app-release-unsigned.dm": SMALL_LIMIT,
        apk_relative.parent
        / "baselineProfiles/1/app-release-unsigned.dm": SMALL_LIMIT,
    }
    for name in archive.ANDROID_RELEASE_MAPPING_FILES:
        file_limits[mapping_root / name] = archive.ANDROID_RELEASE_MAPPING_MAX_BYTES[
            name
        ]

    native_symbol_relative = archive.ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
    native_symbol_directory = root / native_symbol_relative.parent
    if native_symbol_directory.exists() or native_symbol_directory.is_symlink():
        native_symbol_exists = (
            (root / native_symbol_relative).exists()
            or (root / native_symbol_relative).is_symlink()
        )
        _require_inventory(
            native_symbol_directory,
            {native_symbol_relative.name} if native_symbol_exists else set(),
            "Android repeatability native-symbol output directory",
        )
        if native_symbol_exists:
            file_limits[native_symbol_relative] = 1_073_741_824

    records_by_path: dict[str, dict[str, object]] = {}
    payloads: dict[str, bytes] = {}

    def capture(relative: Path, limit: int) -> bytes:
        if len(payloads) >= OUTPUT_GRAPH_FILE_COUNT_LIMIT:
            raise RepeatabilityError("output graph exceeds its file-count limit")
        record, data = stable_file(relative, root=root, maximum_bytes=limit)
        if sum(map(len, payloads.values())) + len(data) > OUTPUT_GRAPH_TOTAL_BYTES_LIMIT:
            raise RepeatabilityError("output graph exceeds its cumulative byte limit")
        key = relative.as_posix()
        if key in payloads:
            raise RepeatabilityError(f"duplicate output graph path: {key}")
        record["comparison"] = comparison_identity(relative, data)
        records_by_path[key] = record
        payloads[key] = data
        return data

    for relative in sorted(file_limits, key=lambda item: item.as_posix().encode("ascii")):
        capture(relative, file_limits[relative])

    apk = payloads[apk_relative.as_posix()]
    aab = payloads[aab_relative.as_posix()]
    apk_members = _zip_members(apk, "Android repeatability APK")
    aab_members = _zip_members(aab, "Android repeatability AAB")

    apk_dex = {
        name: data
        for name, data in apk_members.items()
        if name.startswith("classes") and name.endswith(".dex")
    }
    aab_dex = {
        name.removeprefix("base/dex/"): data
        for name, data in aab_members.items()
        if name.startswith("base/dex/") and name.endswith(".dex")
    }
    if set(apk_dex) != {"classes.dex"} or apk_dex != aab_dex:
        raise RepeatabilityError("APK/AAB DEX identity is not exact single-DEX")

    profile_names = (
        "assets/dexopt/baseline.prof",
        "assets/dexopt/baseline.profm",
    )
    aab_profile_prefix = "BUNDLE-METADATA/com.android.tools.build.profiles/"
    profiles: dict[str, bytes] = {}
    for name in profile_names:
        if name not in apk_members:
            raise RepeatabilityError(f"APK profile is missing: {name}")
        short_name = name.rsplit("/", 1)[1]
        aab_name = aab_profile_prefix + short_name
        if aab_members.get(aab_name) != apk_members[name]:
            raise RepeatabilityError(f"APK/AAB profile differs: {short_name}")
        profiles[short_name] = apk_members[name]

    apk_jni = {
        name: data
        for name, data in apk_members.items()
        if name.startswith("lib/") and name.endswith(".so")
    }
    aab_jni = {
        name.removeprefix("base/"): data
        for name, data in aab_members.items()
        if name.startswith("base/lib/") and name.endswith(".so")
    }
    if not apk_jni or apk_jni != aab_jni:
        raise RepeatabilityError("APK/AAB JNI member identity differs")
    if {PurePosixPath(name).parts[1] for name in apk_jni} != {"arm64-v8a"}:
        raise RepeatabilityError("JNI ABI set is not exactly arm64-v8a")

    packaged_native_names = {PurePosixPath(name).name for name in apk_jni}
    if len(packaged_native_names) != len(apk_jni):
        raise RepeatabilityError("JNI library basenames are not unique")
    native_roots = (
        archive.ANDROID_RELEASE_MERGED_NATIVE_RELATIVE_PATH,
        archive.ANDROID_RELEASE_STRIPPED_NATIVE_RELATIVE_PATH,
    )
    native_payloads: dict[str, dict[str, bytes]] = {}
    expected_native_inventory: dict[str, set[str]] | None = None
    for native_root in native_roots:
        abi_names = directory_names(
            root / native_root,
            f"Android repeatability JNI ABI root {native_root}",
            entries_are_directories=True,
        )
        if not abi_names:
            raise RepeatabilityError(f"JNI ABI inventory is empty: {native_root}")
        if len(abi_names) > NATIVE_ABI_COUNT_LIMIT:
            raise RepeatabilityError(f"JNI ABI inventory exceeds its limit: {native_root}")
        per_abi: dict[str, set[str]] = {}
        root_payloads: dict[str, bytes] = {}
        for abi in sorted(abi_names, key=lambda value: value.encode("ascii")):
            if "/" in abi or abi in (".", ".."):
                raise RepeatabilityError(f"JNI ABI inventory is invalid: {abi!r}")
            names = directory_names(
                root / native_root / abi,
                f"Android repeatability JNI library root {native_root}/{abi}",
                entries_are_directories=False,
            )
            if not names or any(not name.endswith(".so") for name in names):
                raise RepeatabilityError(
                    f"JNI library inventory is invalid: {native_root}/{abi}"
                )
            if sum(len(value) for value in per_abi.values()) + len(names) > NATIVE_FILE_COUNT_LIMIT:
                raise RepeatabilityError(f"JNI inventory exceeds its file-count limit: {native_root}")
            per_abi[abi] = set(names)
            for name in sorted(names, key=lambda value: value.encode("ascii")):
                member_name = f"{abi}/{name}"
                root_payloads[member_name] = capture(
                    native_root / abi / name,
                    NATIVE_LIMIT,
                )
        if expected_native_inventory is None:
            expected_native_inventory = per_abi
        elif expected_native_inventory != per_abi:
            raise RepeatabilityError("merged and stripped JNI inventories differ")
        native_payloads[native_root.as_posix()] = root_payloads

    stripped_payloads = native_payloads[
        archive.ANDROID_RELEASE_STRIPPED_NATIVE_RELATIVE_PATH.as_posix()
    ]
    for name in sorted(packaged_native_names):
        apk_name = f"lib/arm64-v8a/{name}"
        if stripped_payloads.get(f"arm64-v8a/{name}") != apk_jni[apk_name]:
            raise RepeatabilityError(
                f"stripped JNI output differs from APK/AAB: {name}"
            )

    records = tuple(
        records_by_path[key]
        for key in sorted(records_by_path, key=lambda item: item.encode("ascii"))
    )
    projection = {
        "dex": {
            "memberCount": len(apk_dex),
            "logicalSha256": _logical_members(
                apk_dex, b"AETHERLINK-ANDROID-DEX-MEMBERS-V1\0"
            ),
        },
        "fileCount": len(records),
        "files": list(records),
        "comparisonGraphSha256": _comparison_graph_digest(records),
        "jni": {
            "intermediateAbis": sorted(expected_native_inventory or {}),
            "mergedLogicalSha256": _logical_members(
                native_payloads[
                    archive.ANDROID_RELEASE_MERGED_NATIVE_RELATIVE_PATH.as_posix()
                ],
                b"AETHERLINK-ANDROID-MERGED-JNI-MEMBERS-V1\0",
            ),
            "memberCount": len(apk_jni),
            "packagedAbis": ["arm64-v8a"],
            "logicalSha256": _logical_members(
                apk_jni, b"AETHERLINK-ANDROID-JNI-MEMBERS-V1\0"
            ),
            "strippedLogicalSha256": _logical_members(
                stripped_payloads,
                b"AETHERLINK-ANDROID-STRIPPED-JNI-MEMBERS-V1\0",
            ),
        },
        "profiles": {
            "memberCount": len(profiles),
            "logicalSha256": _logical_members(
                profiles, b"AETHERLINK-ANDROID-PROFILES-V1\0"
            ),
        },
        "rawGraphSha256": _raw_graph_digest(records),
    }
    return projection, payloads


def validate_live_outputs(*, root: Path = ROOT) -> dict[str, object]:
    try:
        return archive.verify_android_release_build_outputs(root)
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityError(str(error)) from error


def _ensure_private_parent(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        value = path.lstat()
    except OSError as error:
        raise RepeatabilityError(f"cannot prepare private output parent: {error}") from error
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
        raise RepeatabilityError("output parent must be a physical directory")
    try:
        os.chmod(path, 0o700)
    except OSError as error:
        raise RepeatabilityError(f"cannot set private output parent mode: {error}") from error


@contextmanager
def private_snapshot(
    payloads: Mapping[str, bytes], *, parent: Path
) -> Iterator[Path]:
    _ensure_private_parent(parent)
    try:
        snapshot = Path(tempfile.mkdtemp(prefix=".run-a-", dir=parent))
        os.chmod(snapshot, 0o700)
    except OSError as error:
        raise RepeatabilityError(f"cannot create private run-A snapshot: {error}") from error
    try:
        for relative_text in sorted(payloads, key=lambda item: item.encode("ascii")):
            relative = _relative_path(Path(relative_text))
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            current = snapshot
            for part in relative.parent.parts:
                current /= part
                os.chmod(current, 0o700)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(destination, flags, 0o600)
            try:
                view = memoryview(payloads[relative_text])
                while view:
                    written = os.write(descriptor, view)
                    if written < 1:
                        raise RepeatabilityError("private snapshot write made no progress")
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        yield snapshot
    finally:
        shutil.rmtree(snapshot)


def read_private_snapshot(
    snapshot: Path, paths: Sequence[str]
) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    for relative_text in sorted(paths, key=lambda item: item.encode("ascii")):
        relative = _relative_path(Path(relative_text))
        try:
            payloads[relative_text] = archive.read_stable_regular_file(
                snapshot / relative,
                f"private run-A snapshot {relative_text}",
                maximum_bytes=NATIVE_LIMIT,
            )
        except archive.ReleaseArchiveVerificationError as error:
            raise RepeatabilityError(str(error)) from error
    return payloads


def differing_payload_paths(
    left: Mapping[str, bytes],
    right: Mapping[str, bytes],
) -> tuple[str, ...]:
    return tuple(
        path
        for path in sorted(
            set(left) | set(right),
            key=lambda item: item.encode("ascii"),
        )
        if left.get(path) != right.get(path)
    )


def compare_run_graphs(
    run_a: Mapping[str, object],
    run_b: Mapping[str, object],
    payloads_a: Mapping[str, bytes],
    payloads_b: Mapping[str, bytes],
) -> dict[str, object]:
    if set(payloads_a) != set(payloads_b):
        raise RepeatabilityError("Android Release A/B output path inventories differ")
    difference_paths = differing_payload_paths(payloads_a, payloads_b)
    if not set(difference_paths).issubset(NORMALIZED_COMPARISON_PATHS):
        unexpected = sorted(set(difference_paths) - NORMALIZED_COMPARISON_PATHS)
        raise RepeatabilityError(f"raw differences include non-normalized paths: {unexpected}")
    if run_a.get("fileCount") != run_b.get("fileCount") or run_a.get("fileCount") != len(payloads_a):
        raise RepeatabilityError("Android Release A/B file counts differ")
    if run_a.get("comparisonGraphSha256") != run_b.get("comparisonGraphSha256"):
        raise RepeatabilityError("Android Release A/B comparison graphs differ")
    for key in ("dex", "jni", "profiles"):
        if run_a.get(key) != run_b.get(key):
            raise RepeatabilityError(f"Android Release A/B {key} projection differs")
    files_a = run_a.get("files")
    files_b = run_b.get("files")
    if type(files_a) is not list or type(files_b) is not list or len(files_a) != len(files_b):
        raise RepeatabilityError("Android Release A/B file records differ")
    records_a = {str(record["path"]): record for record in files_a}
    records_b = {str(record["path"]): record for record in files_b}
    if set(records_a) != set(payloads_a) or set(records_b) != set(payloads_b):
        raise RepeatabilityError("Android Release A/B record inventories differ")
    normalized_count = 0
    for path in sorted(records_a, key=lambda value: value.encode("ascii")):
        left = records_a[path]
        right = records_b[path]
        if left.get("comparison") != right.get("comparison") or left.get("mode") != right.get("mode"):
            raise RepeatabilityError(f"Android Release comparison identity differs: {path}")
        comparison = left.get("comparison")
        if type(comparison) is not dict:
            raise RepeatabilityError(f"Android Release comparison identity is missing: {path}")
        normalized = comparison.get("kind") != RAW_COMPARISON_KIND
        if normalized != (path in NORMALIZED_COMPARISON_PATHS):
            raise RepeatabilityError(f"Android Release normalization path contract differs: {path}")
        normalized_count += int(normalized)
        if path not in difference_paths and left != right:
            raise RepeatabilityError(f"raw-identical file records differ: {path}")
    if normalized_count != len(NORMALIZED_COMPARISON_PATHS):
        raise RepeatabilityError("Android Release normalized file count differs")
    return {
        "comparisonGraphIdentical": True,
        "fileCount": len(payloads_a),
        "normalizedFileCount": normalized_count,
        "rawByteIdentical": not difference_paths,
        "rawDifferentFileCount": len(difference_paths),
        "rawDifferentPaths": list(difference_paths),
        "rawIdenticalFileCount": len(payloads_a) - len(difference_paths),
        "semanticIdentical": True,
    }


def process_group_exists(group_id: int) -> bool:
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_group_exit(process: subprocess.Popen[bytes], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None and not process_group_exists(process.pid):
            return True
        time.sleep(0.01)
    return process.poll() is not None and not process_group_exists(process.pid)


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    for signal_value in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, signal_value)
        except ProcessLookupError:
            pass
        except OSError as error:
            raise RepeatabilityError(f"cannot terminate build process group: {error}") from error
        if _wait_group_exit(process, TERMINATION_GRACE_SECONDS):
            return
    raise RepeatabilityError("build process group survived SIGTERM and SIGKILL")


def run_process(
    argv: Sequence[str],
    *,
    root: Path,
    timeout_seconds: float,
    maximum_output_bytes: int,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
    ):
        raise RepeatabilityError("process deadline must be a positive number")
    if type(maximum_output_bytes) is not int or maximum_output_bytes < 1:
        raise RepeatabilityError("process output limit must be a positive exact integer")
    try:
        process = subprocess.Popen(
            tuple(argv),
            cwd=root,
            env=dict(environment) if environment is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise RepeatabilityError(f"cannot start build graph: {error}") from error
    if process.stdout is None or process.stderr is None:
        terminate_process_group(process)
        raise RepeatabilityError("build graph did not expose bounded output streams")

    stdout = bytearray()
    stderr = bytearray()
    streams = {process.stdout.fileno(): stdout, process.stderr.fileno(): stderr}
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + float(timeout_seconds)

    def fail(message: str) -> None:
        try:
            terminate_process_group(process)
        except RepeatabilityError as cleanup_error:
            raise RepeatabilityError(f"{message}; cleanup failed: {cleanup_error}") from cleanup_error
        raise RepeatabilityError(message)

    try:
        for stream in (process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                fail("build graph exceeded its absolute deadline")
            events = selector.select(remaining)
            if not events:
                fail("build graph exceeded its absolute deadline")
            for key, _ in events:
                try:
                    chunk = os.read(key.fd, 65_536)
                except BlockingIOError:
                    continue
                except OSError as error:
                    fail(f"build output read failed: {error}")
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if len(stdout) + len(stderr) + len(chunk) > maximum_output_bytes:
                    fail("build graph output exceeded its byte limit")
                streams[key.fd].extend(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            fail("build graph exceeded its absolute deadline")
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            fail("build graph exceeded its absolute deadline")
        if process.returncode is None or process_group_exists(process.pid):
            fail("build graph process group did not fully exit")
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    if process.returncode != 0:
        tail = (stderr or stdout)[-8_192:].decode("utf-8", errors="replace")
        raise RepeatabilityError(
            f"build graph exited {process.returncode}; bounded tail:\n{tail}"
        )
    return {
        "exitCode": process.returncode,
        "stderr": {"sha256": sha256(bytes(stderr)), "size": len(stderr)},
        "stdout": {"sha256": sha256(bytes(stdout)), "size": len(stdout)},
    }


def command_environment(*, root: Path = ROOT) -> dict[str, str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    if "JAVA_HOME" not in environment and archive.ANDROID_STUDIO_JAVA_HOME.is_dir():
        environment["JAVA_HOME"] = str(archive.ANDROID_STUDIO_JAVA_HOME)
    sdk = archive.android_sdk_root(root)
    environment.setdefault("ANDROID_HOME", str(sdk))
    environment.setdefault("ANDROID_SDK_ROOT", str(sdk))
    return environment


def toolchain_identity(*, root: Path = ROOT) -> dict[str, object]:
    environment = command_environment(root=root)
    return {
        "androidBuildToolsVersion": archive.ANDROID_BUILD_TOOLS_VERSION,
        "androidNdkVersion": archive.ANDROID_NDK_VERSION,
        "androidSdkRoot": environment["ANDROID_SDK_ROOT"],
        "hostMachine": platform.machine(),
        "hostSystem": platform.system(),
        "javaHome": environment.get("JAVA_HOME", ""),
        "pythonVersion": platform.python_version(),
    }


def publish_atomic_create_only(path: Path, data: bytes) -> None:
    if len(data) > MAX_RESULT_BYTES:
        raise RepeatabilityError("result exceeds its byte limit")
    _ensure_private_parent(path.parent)
    if path.exists() or path.is_symlink():
        raise RepeatabilityError(f"result path already exists: {path}")
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path, follow_symlinks=False)
        os.unlink(temporary)
        temporary = None
        parent_descriptor = os.open(
            path.parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except OSError as error:
        raise RepeatabilityError(f"cannot atomically publish result: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    value = path.lstat()
    if (
        not stat.S_ISREG(value.st_mode)
        or stat.S_IMODE(value.st_mode) != 0o600
        or value.st_nlink != 1
    ):
        raise RepeatabilityError("published result is not an owner-only regular file")


def execute(*, root: Path = ROOT, result_path: Path = DEFAULT_RESULT) -> dict[str, object]:
    source_before = source_snapshot(root=root)
    environment = command_environment(root=root)
    prepare_a = run_process(
        PREPARE_COMMAND,
        root=root,
        timeout_seconds=BUILD_TIMEOUT_SECONDS,
        maximum_output_bytes=BUILD_OUTPUT_MAX_BYTES,
        environment=environment,
    )
    workflow_a = run_process(
        BUILD_COMMAND,
        root=root,
        timeout_seconds=BUILD_TIMEOUT_SECONDS,
        maximum_output_bytes=BUILD_OUTPUT_MAX_BYTES,
        environment=environment,
    )
    run_a_readback = validate_live_outputs(root=root)
    run_a, run_a_payloads = capture_output_graph(root=root)
    source_between = source_snapshot(root=root)
    if source_between != source_before:
        raise RepeatabilityError("source changed during run A")

    with private_snapshot(run_a_payloads, parent=result_path.parent) as snapshot:
        prepare_b = run_process(
            PREPARE_COMMAND,
            root=root,
            timeout_seconds=BUILD_TIMEOUT_SECONDS,
            maximum_output_bytes=BUILD_OUTPUT_MAX_BYTES,
            environment=environment,
        )
        workflow_b = run_process(
            BUILD_COMMAND,
            root=root,
            timeout_seconds=BUILD_TIMEOUT_SECONDS,
            maximum_output_bytes=BUILD_OUTPUT_MAX_BYTES,
            environment=environment,
        )
        source_after = source_snapshot(root=root)
        if source_after != source_between:
            raise RepeatabilityError("source changed during run B")
        run_b_readback = validate_live_outputs(root=root)
        run_b, run_b_payloads = capture_output_graph(root=root)
        snapshot_payloads = read_private_snapshot(snapshot, tuple(run_a_payloads))
        if snapshot_payloads != run_a_payloads:
            raise RepeatabilityError("private run-A snapshot differs from captured bytes")
        comparison = compare_run_graphs(
            run_a,
            run_b,
            snapshot_payloads,
            run_b_payloads,
        )
    if run_a_readback != run_b_readback:
        raise RepeatabilityError("Android Release A/B direct readback differs")

    document = {
        "execution": {
            "deadlineSeconds": BUILD_TIMEOUT_SECONDS,
            "prepareArgv": list(PREPARE_COMMAND),
            "runs": {
                "a": {"prepare": prepare_a, "workflow": workflow_a},
                "b": {"prepare": prepare_b, "workflow": workflow_b},
            },
            "workflowArgv": list(BUILD_COMMAND),
        },
        "comparison": comparison,
        "contract": CONTRACT,
        "limitations": list(LIMITATIONS),
        "readback": run_b_readback,
        "runs": {"a": run_a, "b": run_b},
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "after": source_after,
            "before": source_before,
            "between": source_between,
            "stable": True,
        },
        "status": "passed",
        "toolchain": toolchain_identity(root=root),
    }
    payload = canonical_json_bytes(document)
    publish_atomic_create_only(result_path, payload)
    return document


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a source-bound Android Release A/B repeatability graph."
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        document = execute(result_path=arguments.result)
    except (OSError, RepeatabilityError) as error:
        print(f"Android Release repeatability failed: {error}", file=sys.stderr)
        return 1
    print(
        "Android Release repeatability passed: "
        f"files={document['comparison']['fileCount']}; "
        f"rawDifferences={document['comparison']['rawDifferentFileCount']}; "
        f"graph={document['runs']['a']['comparisonGraphSha256']}; "
        f"source={document['source']['before']['sha256']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
