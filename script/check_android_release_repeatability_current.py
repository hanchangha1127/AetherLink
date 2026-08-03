#!/usr/bin/env python3
"""Independently read back current Android Release A/B repeatability."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
from typing import Mapping, Sequence

if __package__:
    from script import check_release_artifact_archive as archive
else:
    import check_release_artifact_archive as archive


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULT = ROOT / ".build/aetherlink-android-release-repeatability-v1/result.json"
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
PREPARE_COMMAND = (sys.executable, "-B", "script/check_product_ci.py")
BUILD_COMMAND = (
    "./gradlew", "--offline", "--no-daemon", "--console=plain", "--rerun-tasks",
    "-PaetherlinkStrictReleaseDependencyLocks=true", "-Pkotlin.incremental=false",
    ":app:assembleRelease", ":app:bundleRelease", ":app:lintRelease",
)
BUILD_TIMEOUT_SECONDS = 1_800
MAX_RESULT_BYTES = 4 * 1024 * 1024
NATIVE_LIMIT = 512 * 1024 * 1024
NATIVE_ABI_COUNT_LIMIT = 16
NATIVE_FILE_COUNT_LIMIT = 1_024
OUTPUT_GRAPH_FILE_COUNT_LIMIT = 2_048
OUTPUT_GRAPH_TOTAL_BYTES_LIMIT = 3 * 1024 * 1024 * 1024
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
NORMALIZED_COMPARISON_PATHS = frozenset({
    (archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/0/app-release-unsigned.dm").as_posix(),
    (archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/1/app-release-unsigned.dm").as_posix(),
    (archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "mapping.prt").as_posix(),
    (archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "resources.txt").as_posix(),
    (archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "seeds.txt").as_posix(),
})


class RepeatabilityCheckError(RuntimeError):
    pass


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_keys(value: object, expected: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise RepeatabilityCheckError(f"{label} must be an object")
    if set(value) != expected:
        raise RepeatabilityCheckError(f"{label} keys differ")
    return value


def exact_int(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise RepeatabilityCheckError(f"{label} must be an exact integer >= {minimum}")
    return value


def exact_bool(value: object, expected: bool, label: str) -> None:
    if type(value) is not bool or value is not expected:
        raise RepeatabilityCheckError(f"{label} must be exactly {expected}")


def hash_value(value: object, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise RepeatabilityCheckError(f"{label} must be a lowercase SHA-256")
    return value


def relative_path(value: Path) -> Path:
    if value.is_absolute() or value in (Path(""), Path("."), Path("..")) or any(part in ("", ".", "..") for part in value.parts):
        raise RepeatabilityCheckError(f"invalid relative path: {value}")
    try:
        value.as_posix().encode("ascii")
    except UnicodeEncodeError as error:
        raise RepeatabilityCheckError(f"non-ASCII relative path: {value}") from error
    return value


def stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def stable_file(relative: Path, *, root: Path, maximum_bytes: int) -> tuple[dict[str, object], bytes]:
    relative = relative_path(relative)
    path = root / relative
    try:
        before = path.lstat()
    except OSError as error:
        raise RepeatabilityCheckError(f"cannot inspect {relative}: {error}") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise RepeatabilityCheckError(f"file must be regular, non-symlink, single-link: {relative}")
    try:
        data = archive.read_stable_regular_file(path, f"repeatability readback {relative}", maximum_bytes=maximum_bytes)
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityCheckError(str(error)) from error
    after = path.lstat()
    if stat_identity(before) != stat_identity(after):
        raise RepeatabilityCheckError(f"file changed around read: {relative}")
    return ({"mode": stat.S_IMODE(after.st_mode), "path": relative.as_posix(), "sha256": sha256(data), "size": len(data)}, data)


def directory_names(path: Path, label: str, *, entries_are_directories: bool) -> set[str]:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RepeatabilityCheckError(f"cannot open {label}: {error}") from error
    try:
        before = os.fstat(descriptor)
        result: set[str] = set()
        for name in os.listdir(descriptor):
            try:
                name.encode("ascii")
            except UnicodeEncodeError as error:
                raise RepeatabilityCheckError(f"{label} contains a non-ASCII name") from error
            if name in ("", ".", "..") or "/" in name or name in result:
                raise RepeatabilityCheckError(f"{label} contains a noncanonical name")
            value = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            valid = stat.S_ISDIR(value.st_mode) if entries_are_directories else stat.S_ISREG(value.st_mode)
            if stat.S_ISLNK(value.st_mode) or not valid:
                raise RepeatabilityCheckError(f"{label}/{name} has the wrong physical type")
            result.add(name)
        if stat_identity(before) != stat_identity(os.fstat(descriptor)):
            raise RepeatabilityCheckError(f"{label} changed during inventory")
        return result
    except OSError as error:
        raise RepeatabilityCheckError(f"cannot inspect {label}: {error}") from error
    finally:
        os.close(descriptor)


def require_inventory(path: Path, expected: set[str], label: str) -> None:
    try:
        archive.require_directory_inventory(path, expected, label)
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityCheckError(str(error)) from error


def source_snapshot(*, root: Path = ROOT) -> dict[str, object]:
    try:
        paths = {Path(value) for value in archive.collect_current_source_paths(root)}
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityCheckError(str(error)) from error
    paths.update(SOURCE_EXTRAS)
    ordered = sorted(paths, key=lambda item: item.as_posix().encode("ascii"))
    digest = hashlib.sha256()
    size = 0
    for relative in ordered:
        record, _ = stable_file(relative, root=root, maximum_bytes=64 * 1024 * 1024)
        digest.update(relative.as_posix().encode("ascii") + b"\0")
        digest.update(f"{record['mode']:o}".encode("ascii") + b"\0")
        digest.update(str(record["size"]).encode("ascii") + b"\0")
        digest.update(str(record["sha256"]).encode("ascii") + b"\n")
        size += exact_int(record["size"], "source size")
    return {"algorithm": SOURCE_ALGORITHM, "fileCount": len(ordered), "sha256": digest.hexdigest(), "size": size}


def zip_members(data: bytes, label: str) -> dict[str, bytes]:
    try:
        return archive.read_safe_zip_members(data, label, maximum_members=8_192, maximum_member_bytes=268_435_456, maximum_total_uncompressed_bytes=536_870_912)
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityCheckError(str(error)) from error


def logical_members(members: Mapping[str, bytes], domain: bytes) -> str:
    return archive.logical_member_digest(dict(members), domain)


def comparison_identity(relative: Path, data: bytes) -> dict[str, str]:
    path = relative.as_posix()
    try:
        if path.endswith(".dm") and path in NORMALIZED_COMPARISON_PATHS:
            members = archive.read_safe_zip_members(data, f"repeatability baseline profile {path}", maximum_members=2, maximum_member_bytes=16_777_216, maximum_total_uncompressed_bytes=33_554_432)
            value = archive.logical_member_digest(members, b"AETHERLINK-ANDROID-DM-LOGICAL-MEMBERS-V1\0")
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
        raise RepeatabilityCheckError(str(error)) from error
    return {"kind": kind, "sha256": value}


def raw_graph_digest(records: Sequence[dict[str, object]]) -> str:
    digest = hashlib.sha256(b"AETHERLINK-ANDROID-RELEASE-RAW-OUTPUT-GRAPH-V1\0")
    digest.update(len(records).to_bytes(8, "big"))
    for record in records:
        digest.update(str(record["path"]).encode("ascii") + b"\0")
        digest.update(f"{record['mode']:o}".encode("ascii") + b"\0")
        digest.update(str(record["size"]).encode("ascii") + b"\0")
        digest.update(str(record["sha256"]).encode("ascii") + b"\n")
    return digest.hexdigest()


def comparison_graph_digest(records: Sequence[dict[str, object]]) -> str:
    digest = hashlib.sha256(b"AETHERLINK-ANDROID-RELEASE-COMPARISON-GRAPH-V1\0")
    digest.update(len(records).to_bytes(8, "big"))
    for record in records:
        comparison = record["comparison"]
        assert isinstance(comparison, dict)
        digest.update(str(record["path"]).encode("ascii") + b"\0")
        digest.update(f"{record['mode']:o}".encode("ascii") + b"\0")
        digest.update(str(comparison["kind"]).encode("ascii") + b"\0")
        digest.update(str(comparison["sha256"]).encode("ascii") + b"\n")
    return digest.hexdigest()


def capture_output_graph(*, root: Path = ROOT) -> dict[str, object]:
    apk_path = archive.ANDROID_RELEASE_APK_RELATIVE_PATH
    metadata_path = archive.ANDROID_RELEASE_APK_METADATA_RELATIVE_PATH
    aab_path = archive.ANDROID_RELEASE_AAB_RELATIVE_PATH
    mapping_root = archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH
    sdk_path = archive.ANDROID_RELEASE_SDK_DEPENDENCIES_RELATIVE_PATH
    require_inventory(root / apk_path.parent, {apk_path.name, metadata_path.name, "baselineProfiles"}, "repeatability APK directory")
    require_inventory(root / apk_path.parent / "baselineProfiles", {"0", "1"}, "repeatability profile directory")
    for index in ("0", "1"):
        require_inventory(root / apk_path.parent / "baselineProfiles" / index, {"app-release-unsigned.dm"}, f"repeatability profile {index}")
    require_inventory(root / aab_path.parent, {aab_path.name}, "repeatability AAB directory")
    require_inventory(root / mapping_root, set(archive.ANDROID_RELEASE_MAPPING_FILES), "repeatability R8 directory")
    require_inventory(root / sdk_path.parent, {sdk_path.name}, "repeatability SDK directory")
    limits: dict[Path, int] = {
        apk_path: 256 * 1024 * 1024, metadata_path: 16 * 1024 * 1024,
        aab_path: 256 * 1024 * 1024, sdk_path: 16 * 1024 * 1024,
        apk_path.parent / "baselineProfiles/0/app-release-unsigned.dm": 16 * 1024 * 1024,
        apk_path.parent / "baselineProfiles/1/app-release-unsigned.dm": 16 * 1024 * 1024,
    }
    for name in archive.ANDROID_RELEASE_MAPPING_FILES:
        limits[mapping_root / name] = archive.ANDROID_RELEASE_MAPPING_MAX_BYTES[name]
    symbol_path = archive.ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
    symbol_directory = root / symbol_path.parent
    if symbol_directory.exists() or symbol_directory.is_symlink():
        present = (root / symbol_path).exists() or (root / symbol_path).is_symlink()
        require_inventory(symbol_directory, {symbol_path.name} if present else set(), "repeatability symbol directory")
        if present:
            limits[symbol_path] = 1_073_741_824
    records: dict[str, dict[str, object]] = {}
    payloads: dict[str, bytes] = {}
    def capture(path: Path, limit: int) -> bytes:
        if len(payloads) >= OUTPUT_GRAPH_FILE_COUNT_LIMIT:
            raise RepeatabilityCheckError("output graph exceeds its file-count limit")
        record, data = stable_file(path, root=root, maximum_bytes=limit)
        if sum(map(len, payloads.values())) + len(data) > OUTPUT_GRAPH_TOTAL_BYTES_LIMIT:
            raise RepeatabilityCheckError("output graph exceeds its cumulative byte limit")
        key = path.as_posix()
        if key in payloads:
            raise RepeatabilityCheckError(f"duplicate graph path: {key}")
        record["comparison"] = comparison_identity(path, data)
        records[key], payloads[key] = record, data
        return data
    for path in sorted(limits, key=lambda item: item.as_posix().encode("ascii")):
        capture(path, limits[path])
    apk = zip_members(payloads[apk_path.as_posix()], "repeatability APK")
    aab = zip_members(payloads[aab_path.as_posix()], "repeatability AAB")
    dex_apk = {name: data for name, data in apk.items() if re.fullmatch(r"classes(?:[2-9][0-9]*)?\.dex", name)}
    dex_aab = {name.removeprefix("base/dex/"): data for name, data in aab.items() if name.startswith("base/dex/") and name.endswith(".dex")}
    if set(dex_apk) != {"classes.dex"} or dex_apk != dex_aab:
        raise RepeatabilityCheckError("APK/AAB DEX differs")
    profiles: dict[str, bytes] = {}
    for short in ("baseline.prof", "baseline.profm"):
        apk_name = "assets/dexopt/" + short
        aab_name = "BUNDLE-METADATA/com.android.tools.build.profiles/" + short
        if apk.get(apk_name) is None or apk[apk_name] != aab.get(aab_name):
            raise RepeatabilityCheckError(f"APK/AAB profile differs: {short}")
        profiles[short] = apk[apk_name]
    apk_jni = {name: data for name, data in apk.items() if name.startswith("lib/") and name.endswith(".so")}
    aab_jni = {name.removeprefix("base/"): data for name, data in aab.items() if name.startswith("base/lib/") and name.endswith(".so")}
    if not apk_jni or apk_jni != aab_jni or {PurePosixPath(name).parts[1] for name in apk_jni} != {"arm64-v8a"}:
        raise RepeatabilityCheckError("APK/AAB JNI identity differs")
    native_roots = (archive.ANDROID_RELEASE_MERGED_NATIVE_RELATIVE_PATH, archive.ANDROID_RELEASE_STRIPPED_NATIVE_RELATIVE_PATH)
    inventory: dict[str, set[str]] | None = None
    native_payloads: dict[str, dict[str, bytes]] = {}
    for native_root in native_roots:
        abis = directory_names(root / native_root, f"JNI ABI root {native_root}", entries_are_directories=True)
        if not abis:
            raise RepeatabilityCheckError("JNI ABI inventory is empty")
        if len(abis) > NATIVE_ABI_COUNT_LIMIT:
            raise RepeatabilityCheckError("JNI ABI inventory exceeds its limit")
        per_abi: dict[str, set[str]] = {}
        members: dict[str, bytes] = {}
        for abi in sorted(abis, key=lambda value: value.encode("ascii")):
            names = directory_names(root / native_root / abi, f"JNI root {native_root}/{abi}", entries_are_directories=False)
            if not names or any(not name.endswith(".so") for name in names):
                raise RepeatabilityCheckError("JNI library inventory is invalid")
            if sum(len(value) for value in per_abi.values()) + len(names) > NATIVE_FILE_COUNT_LIMIT:
                raise RepeatabilityCheckError("JNI inventory exceeds its file-count limit")
            per_abi[abi] = names
            for name in sorted(names, key=lambda value: value.encode("ascii")):
                members[f"{abi}/{name}"] = capture(native_root / abi / name, NATIVE_LIMIT)
        if inventory is None:
            inventory = per_abi
        elif inventory != per_abi:
            raise RepeatabilityCheckError("merged/stripped JNI inventory differs")
        native_payloads[native_root.as_posix()] = members
    stripped = native_payloads[archive.ANDROID_RELEASE_STRIPPED_NATIVE_RELATIVE_PATH.as_posix()]
    for name, data in apk_jni.items():
        short = PurePosixPath(name).name
        if stripped.get(f"arm64-v8a/{short}") != data:
            raise RepeatabilityCheckError(f"packaged/stripped JNI differs: {short}")
    ordered = [records[key] for key in sorted(records, key=lambda value: value.encode("ascii"))]
    return {
        "dex": {"memberCount": len(dex_apk), "logicalSha256": logical_members(dex_apk, b"AETHERLINK-ANDROID-DEX-MEMBERS-V1\0")},
        "comparisonGraphSha256": comparison_graph_digest(ordered),
        "fileCount": len(ordered), "files": ordered,
        "jni": {
            "intermediateAbis": sorted(inventory or {}),
            "logicalSha256": logical_members(apk_jni, b"AETHERLINK-ANDROID-JNI-MEMBERS-V1\0"),
            "memberCount": len(apk_jni),
            "mergedLogicalSha256": logical_members(native_payloads[archive.ANDROID_RELEASE_MERGED_NATIVE_RELATIVE_PATH.as_posix()], b"AETHERLINK-ANDROID-MERGED-JNI-MEMBERS-V1\0"),
            "packagedAbis": ["arm64-v8a"],
            "strippedLogicalSha256": logical_members(stripped, b"AETHERLINK-ANDROID-STRIPPED-JNI-MEMBERS-V1\0"),
        },
        "profiles": {"memberCount": len(profiles), "logicalSha256": logical_members(profiles, b"AETHERLINK-ANDROID-PROFILES-V1\0")},
        "rawGraphSha256": raw_graph_digest(ordered),
    }


def load_result(path: Path) -> dict[str, object]:
    try:
        before = path.lstat()
    except OSError as error:
        raise RepeatabilityCheckError(f"cannot inspect result: {error}") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o600 or before.st_size > MAX_RESULT_BYTES:
        raise RepeatabilityCheckError("result must be a bounded mode-0600 single-link regular file")
    try:
        data = archive.read_stable_regular_file(path, "Android repeatability result", maximum_bytes=MAX_RESULT_BYTES)
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityCheckError(str(error)) from error
    if stat_identity(before) != stat_identity(path.lstat()):
        raise RepeatabilityCheckError("result changed around read")
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise RepeatabilityCheckError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(data.decode("ascii"), object_pairs_hook=pairs, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise RepeatabilityCheckError(f"result JSON is invalid: {error}") from error
    if type(value) is not dict or canonical_json_bytes(value) != data:
        raise RepeatabilityCheckError("result is not canonical JSON")
    return value


def validate_source(value: object, label: str) -> dict[str, object]:
    result = exact_keys(value, {"algorithm", "fileCount", "sha256", "size"}, label)
    if result["algorithm"] != SOURCE_ALGORITHM:
        raise RepeatabilityCheckError(f"{label} algorithm differs")
    exact_int(result["fileCount"], f"{label}.fileCount", minimum=1)
    exact_int(result["size"], f"{label}.size", minimum=1)
    hash_value(result["sha256"], f"{label}.sha256")
    return result


def validate_identity(value: object, label: str) -> None:
    result = exact_keys(value, {"sha256", "size"}, label)
    hash_value(result["sha256"], f"{label}.sha256")
    exact_int(result["size"], f"{label}.size")


def validate_process(value: object, label: str) -> None:
    result = exact_keys(value, {"exitCode", "stderr", "stdout"}, label)
    if exact_int(result["exitCode"], f"{label}.exitCode") != 0:
        raise RepeatabilityCheckError(f"{label} did not pass")
    validate_identity(result["stderr"], f"{label}.stderr")
    validate_identity(result["stdout"], f"{label}.stdout")


def validate_projection(value: object, label: str) -> dict[str, object]:
    result = exact_keys(value, {"comparisonGraphSha256", "dex", "fileCount", "files", "jni", "profiles", "rawGraphSha256"}, label)
    count = exact_int(result["fileCount"], f"{label}.fileCount", minimum=1)
    hash_value(result["comparisonGraphSha256"], f"{label}.comparisonGraphSha256")
    hash_value(result["rawGraphSha256"], f"{label}.rawGraphSha256")
    files = result["files"]
    if type(files) is not list or len(files) != count:
        raise RepeatabilityCheckError(f"{label}.files count differs")
    paths: list[str] = []
    for index, value_record in enumerate(files):
        record = exact_keys(value_record, {"comparison", "mode", "path", "sha256", "size"}, f"{label}.files[{index}]")
        exact_int(record["mode"], f"{label}.files[{index}].mode")
        exact_int(record["size"], f"{label}.files[{index}].size")
        hash_value(record["sha256"], f"{label}.files[{index}].sha256")
        if type(record["path"]) is not str:
            raise RepeatabilityCheckError(f"{label}.files[{index}].path must be a string")
        relative_path(Path(record["path"]))
        comparison = exact_keys(record["comparison"], {"kind", "sha256"}, f"{label}.files[{index}].comparison")
        hash_value(comparison["sha256"], f"{label}.files[{index}].comparison.sha256")
        expected_kind = {
            path: kind
            for path, kind in (
                ((archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/0/app-release-unsigned.dm").as_posix(), DM_COMPARISON_KIND),
                ((archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/1/app-release-unsigned.dm").as_posix(), DM_COMPARISON_KIND),
                ((archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "mapping.prt").as_posix(), MAPPING_PRT_COMPARISON_KIND),
                ((archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "resources.txt").as_posix(), RESOURCES_COMPARISON_KIND),
                ((archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "seeds.txt").as_posix(), SEEDS_COMPARISON_KIND),
            )
        }.get(record["path"], RAW_COMPARISON_KIND)
        if comparison["kind"] != expected_kind:
            raise RepeatabilityCheckError(f"{label}.files[{index}] comparison kind differs")
        if expected_kind == RAW_COMPARISON_KIND and comparison["sha256"] != record["sha256"]:
            raise RepeatabilityCheckError(f"{label}.files[{index}] raw comparison hash differs")
        paths.append(record["path"])
    if paths != sorted(set(paths), key=lambda item: item.encode("ascii")) or raw_graph_digest(files) != result["rawGraphSha256"] or comparison_graph_digest(files) != result["comparisonGraphSha256"]:
        raise RepeatabilityCheckError(f"{label} file graph is not canonical")
    for section in ("dex", "profiles"):
        part = exact_keys(result[section], {"logicalSha256", "memberCount"}, f"{label}.{section}")
        exact_int(part["memberCount"], f"{label}.{section}.memberCount", minimum=1)
        hash_value(part["logicalSha256"], f"{label}.{section}.logicalSha256")
    jni = exact_keys(result["jni"], {"intermediateAbis", "logicalSha256", "memberCount", "mergedLogicalSha256", "packagedAbis", "strippedLogicalSha256"}, f"{label}.jni")
    exact_int(jni["memberCount"], f"{label}.jni.memberCount", minimum=1)
    for name in ("logicalSha256", "mergedLogicalSha256", "strippedLogicalSha256"):
        hash_value(jni[name], f"{label}.jni.{name}")
    for name in ("intermediateAbis", "packagedAbis"):
        values = jni[name]
        if type(values) is not list or not values or any(type(item) is not str for item in values) or values != sorted(set(values)):
            raise RepeatabilityCheckError(f"{label}.jni.{name} is invalid")
    if jni["packagedAbis"] != ["arm64-v8a"]:
        raise RepeatabilityCheckError(f"{label}.jni.packagedAbis differs")
    return result


def validate_ab_comparison(run_a: dict[str, object], run_b: dict[str, object], value: object) -> dict[str, object]:
    comparison = exact_keys(value, {"comparisonGraphIdentical", "fileCount", "normalizedFileCount", "rawByteIdentical", "rawDifferentFileCount", "rawDifferentPaths", "rawIdenticalFileCount", "semanticIdentical"}, "comparison")
    exact_bool(comparison["comparisonGraphIdentical"], True, "comparison.comparisonGraphIdentical")
    exact_bool(comparison["semanticIdentical"], True, "comparison.semanticIdentical")
    file_count = exact_int(comparison["fileCount"], "comparison.fileCount", minimum=1)
    normalized_count = exact_int(comparison["normalizedFileCount"], "comparison.normalizedFileCount")
    different_count = exact_int(comparison["rawDifferentFileCount"], "comparison.rawDifferentFileCount")
    identical_count = exact_int(comparison["rawIdenticalFileCount"], "comparison.rawIdenticalFileCount")
    raw_identical = comparison["rawByteIdentical"]
    if type(raw_identical) is not bool:
        raise RepeatabilityCheckError("comparison.rawByteIdentical must be an exact boolean")
    paths = comparison["rawDifferentPaths"]
    if type(paths) is not list or any(type(path) is not str for path in paths) or paths != sorted(set(paths), key=lambda item: item.encode("ascii")):
        raise RepeatabilityCheckError("comparison.rawDifferentPaths is invalid")
    files_a = run_a["files"]
    files_b = run_b["files"]
    assert isinstance(files_a, list) and isinstance(files_b, list)
    records_a = {record["path"]: record for record in files_a}
    records_b = {record["path"]: record for record in files_b}
    if set(records_a) != set(records_b):
        raise RepeatabilityCheckError("A/B file inventories differ")
    observed: list[str] = []
    observed_normalized: set[str] = set()
    for path in sorted(records_a, key=lambda item: item.encode("ascii")):
        left = records_a[path]
        right = records_b[path]
        if left["mode"] != right["mode"] or left["comparison"] != right["comparison"]:
            raise RepeatabilityCheckError(f"A/B comparison identity differs: {path}")
        if left["comparison"]["kind"] != RAW_COMPARISON_KIND:
            observed_normalized.add(path)
        if left["sha256"] != right["sha256"] or left["size"] != right["size"]:
            observed.append(path)
    if not set(observed).issubset(NORMALIZED_COMPARISON_PATHS):
        raise RepeatabilityCheckError("A/B raw differences escape normalized paths")
    if observed_normalized != NORMALIZED_COMPARISON_PATHS:
        raise RepeatabilityCheckError("A/B normalized path inventory differs")
    if run_a["comparisonGraphSha256"] != run_b["comparisonGraphSha256"]:
        raise RepeatabilityCheckError("A/B comparison graph hashes differ")
    for key in ("dex", "jni", "profiles"):
        if run_a[key] != run_b[key]:
            raise RepeatabilityCheckError(f"A/B {key} projections differ")
    if file_count != run_a["fileCount"] or file_count != run_b["fileCount"] or normalized_count != len(observed_normalized) or paths != observed or different_count != len(observed) or identical_count != file_count - len(observed) or raw_identical is not (not observed):
        raise RepeatabilityCheckError("comparison summary differs from A/B records")
    return comparison


def reject_bool(value: object, label: str = "readback") -> None:
    if type(value) is bool:
        raise RepeatabilityCheckError(f"{label} contains an unexpected boolean")
    if type(value) is dict:
        for key, item in value.items():
            reject_bool(item, f"{label}.{key}")
    elif type(value) is list:
        for index, item in enumerate(value):
            reject_bool(item, f"{label}[{index}]")


def require_exact_typed_equal(recorded: object, current: object, label: str) -> None:
    if type(recorded) is not type(current):
        raise RepeatabilityCheckError(f"{label} JSON type differs")
    if type(recorded) is dict:
        if set(recorded) != set(current):
            raise RepeatabilityCheckError(f"{label} keys differ")
        for key in recorded:
            require_exact_typed_equal(recorded[key], current[key], f"{label}.{key}")
        return
    if type(recorded) is list:
        if len(recorded) != len(current):
            raise RepeatabilityCheckError(f"{label} list length differs")
        for index, (left, right) in enumerate(zip(recorded, current)):
            require_exact_typed_equal(left, right, f"{label}[{index}]")
        return
    if recorded != current:
        raise RepeatabilityCheckError(f"{label} value differs")


def current_toolchain(*, root: Path = ROOT) -> dict[str, object]:
    environment = os.environ.copy()
    if "JAVA_HOME" not in environment and archive.ANDROID_STUDIO_JAVA_HOME.is_dir():
        environment["JAVA_HOME"] = str(archive.ANDROID_STUDIO_JAVA_HOME)
    sdk = archive.android_sdk_root(root)
    return {
        "androidBuildToolsVersion": archive.ANDROID_BUILD_TOOLS_VERSION,
        "androidNdkVersion": archive.ANDROID_NDK_VERSION,
        "androidSdkRoot": environment.get("ANDROID_SDK_ROOT", str(sdk)),
        "hostMachine": platform.machine(), "hostSystem": platform.system(),
        "javaHome": environment.get("JAVA_HOME", ""), "pythonVersion": platform.python_version(),
    }


def check(path: Path, *, root: Path = ROOT) -> dict[str, object]:
    document = load_result(path)
    exact_keys(document, {"comparison", "contract", "execution", "limitations", "readback", "runs", "schemaVersion", "source", "status", "toolchain"}, "result")
    if document["contract"] != CONTRACT or exact_int(document["schemaVersion"], "schemaVersion", minimum=1) != SCHEMA_VERSION or document["status"] != "passed" or document["limitations"] != list(LIMITATIONS):
        raise RepeatabilityCheckError("result header differs")
    execution = exact_keys(document["execution"], {"deadlineSeconds", "prepareArgv", "runs", "workflowArgv"}, "execution")
    if exact_int(execution["deadlineSeconds"], "execution.deadlineSeconds", minimum=1) != BUILD_TIMEOUT_SECONDS or execution["prepareArgv"] != list(PREPARE_COMMAND) or execution["workflowArgv"] != list(BUILD_COMMAND):
        raise RepeatabilityCheckError("execution contract differs")
    execution_runs = exact_keys(execution["runs"], {"a", "b"}, "execution.runs")
    for run_name in ("a", "b"):
        run = exact_keys(execution_runs[run_name], {"prepare", "workflow"}, f"execution.runs.{run_name}")
        validate_process(run["prepare"], f"execution.runs.{run_name}.prepare")
        validate_process(run["workflow"], f"execution.runs.{run_name}.workflow")
    source = exact_keys(document["source"], {"after", "before", "between", "stable"}, "source")
    exact_bool(source["stable"], True, "source.stable")
    source_values = [validate_source(source[name], f"source.{name}") for name in ("before", "between", "after")]
    if source_values[0] != source_values[1] or source_values[1] != source_values[2]:
        raise RepeatabilityCheckError("recorded source snapshots differ")
    runs = exact_keys(document["runs"], {"a", "b"}, "runs")
    run_a = validate_projection(runs["a"], "runs.a")
    run_b = validate_projection(runs["b"], "runs.b")
    validate_ab_comparison(run_a, run_b, document["comparison"])
    reject_bool(document["readback"])
    if document["toolchain"] != current_toolchain(root=root):
        raise RepeatabilityCheckError("current toolchain differs")
    current_source_before = source_snapshot(root=root)
    if current_source_before != source_values[0]:
        raise RepeatabilityCheckError("current source differs from recorded source")
    try:
        live_readback = archive.verify_android_release_build_outputs(root)
    except archive.ReleaseArchiveVerificationError as error:
        raise RepeatabilityCheckError(str(error)) from error
    live_graph = capture_output_graph(root=root)
    current_source_after = source_snapshot(root=root)
    if current_source_after != current_source_before:
        raise RepeatabilityCheckError("source changed during independent readback")
    require_exact_typed_equal(document["readback"], live_readback, "direct output readback")
    require_exact_typed_equal(run_b, live_graph, "current output graph")
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", nargs="?", type=Path, default=DEFAULT_RESULT)
    arguments = parser.parse_args(argv)
    try:
        document = check(arguments.result)
    except (OSError, RepeatabilityCheckError) as error:
        print(f"Android Release repeatability readback failed: {error}", file=sys.stderr)
        return 1
    print(f"Android Release repeatability readback passed: files={document['comparison']['fileCount']}; rawDifferences={document['comparison']['rawDifferentFileCount']}; graph={document['runs']['a']['comparisonGraphSha256']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
