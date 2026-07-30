#!/usr/bin/env python3
"""Create a deterministic local Android/macOS release evidence archive."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import functools
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script.check_release_version_ledger import (
    ReleaseVersion,
    artifact_contract_failures,
    load_release_version_ledger,
    source_contract_failures,
)
from script.generate_release_compliance import (
    ComplianceError,
    build_release_compliance,
)


DEFAULT_OUTPUT_ROOT = ROOT / "dist/releases"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
MANIFEST_SCHEMA_VERSION = 2
MEMBER_SCHEMA_VERSION = 1
CHANNEL = "local"
ARCHIVE_REVISION = "v1"

ANDROID_APK = (
    ROOT
    / "apps/android/app/build/outputs/apk/release/app-release-unsigned.apk"
)
ANDROID_APK_METADATA = (
    ROOT / "apps/android/app/build/outputs/apk/release/output-metadata.json"
)
ANDROID_AAB = (
    ROOT / "apps/android/app/build/outputs/bundle/release/app-release.aab"
)
ANDROID_MAPPING_DIR = (
    ROOT / "apps/android/app/build/outputs/mapping/release"
)
ANDROID_SDK_DEPENDENCIES = (
    ROOT
    / "apps/android/app/build/outputs/sdk-dependencies/release"
    / "sdkDependencies.txt"
)
ANDROID_NATIVE_SYMBOL_ARCHIVE = (
    ROOT
    / "apps/android/app/build/outputs/native-debug-symbols/release"
    / "native-debug-symbols.zip"
)
ANDROID_MERGED_NATIVE_LIBS = (
    ROOT
    / "apps/android/app/build/intermediates/merged_native_libs/release"
    / "mergeReleaseNativeLibs/out/lib"
)
ANDROID_STRIPPED_NATIVE_LIBS = (
    ROOT
    / "apps/android/app/build/intermediates/stripped_native_libs/release"
    / "stripReleaseDebugSymbols/out/lib"
)
MACOS_APP = ROOT / "dist/AetherLink.app"
DEFAULT_MACOS_BUILD_ROOT = ROOT / ".build"
REPRO_SWIFT_SCRATCH_PATH = Path(
    "/private/tmp/aetherlink-g6-swift-scratch-v1"
)
LEDGER_PATH = ROOT / "release/version-ledger.tsv"
GRADLE_LOCK_PATHS = (
    "apps/android/app/gradle.lockfile",
    "apps/android/core/pairing/gradle.lockfile",
    "apps/android/core/protocol/gradle.lockfile",
    "apps/android/core/transport/gradle.lockfile",
    "buildscript-gradle.lockfile",
    "settings-gradle.lockfile",
)
GRADLE_IGNORED_DEPENDENCIES = (
    "org.jetbrains.kotlin:kotlin-stdlib-common",
)
ANDROID_XML_NAMESPACE = "http://schemas.android.com/apk/res/android"
BUNDLETOOL_CLASSPATH_MARKER = "AETHERLINK_BUNDLETOOL_CLASSPATH="
BUNDLETOOL_MAIN_CLASS = (
    "com.android.tools.build.bundletool.BundleToolMain"
)
BUNDLETOOL_VERSION = "1.18.3"
BUNDLETOOL_TIMEOUT_SECONDS = 60
AAPT2_TIMEOUT_SECONDS = 60
ANDROID_BACKUP_POLICY_BUILD = 15
BASE_BUNDLE_MANIFEST_VERIFIED_FIELDS = (
    "applicationId",
    "minSdk",
    "targetSdk",
    "versionCode",
    "versionName",
)
BACKUP_POLICY_BUNDLE_MANIFEST_VERIFIED_FIELDS = (
    "allowBackup",
    "dataExtractionRules",
    "fullBackupContent",
)
BACKUP_POLICY_APK_MANIFEST_VERIFIED_FIELDS = (
    "allowBackup",
    "dataExtractionRules",
    "fullBackupContent",
)
LEGACY_BACKUP_EXCLUDE_DOMAINS = (
    "root",
    "file",
    "database",
    "sharedpref",
    "external",
)
DATA_EXTRACTION_EXCLUDE_DOMAINS = (
    *LEGACY_BACKUP_EXCLUDE_DOMAINS,
    "device_root",
    "device_file",
    "device_database",
    "device_sharedpref",
)
ANDROID_STUDIO_JAVA_HOME = Path(
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
)

MAPPING_FILES = (
    "configuration.txt",
    "mapping.prt",
    "mapping.txt",
    "resources.txt",
    "seeds.txt",
    "usage.txt",
)
ARCHIVE_NORMALIZATIONS = (
    "android/mapping/configuration.txt:"
    "declared-extracted-file-root-markers",
    "android/mapping/mapping.prt:"
    "sorted-members-fixed-metadata-deflate-9",
    "android/mapping/resources.txt:"
    "semantic-reachability-sorted-unique-lines",
    "android/mapping/seeds.txt:bytewise-sorted-unique-lines",
)

SOURCE_REQUIRED_FILES = (
    "Package.swift",
    "build.gradle.kts",
    "settings.gradle.kts",
    "settings-gradle.lockfile",
    "gradle.properties",
    "gradlew",
    "buildscript-gradle.lockfile",
    "gradle/gradle-daemon-jvm.properties",
    "gradle/libs.versions.toml",
    "gradle/wrapper/gradle-wrapper.jar",
    "gradle/wrapper/gradle-wrapper.properties",
    "apps/android/app/build.gradle.kts",
    "apps/android/app/gradle.lockfile",
    "apps/android/core/pairing/build.gradle.kts",
    "apps/android/core/pairing/gradle.lockfile",
    "apps/android/core/protocol/build.gradle.kts",
    "apps/android/core/protocol/gradle.lockfile",
    "apps/android/core/transport/build.gradle.kts",
    "apps/android/core/transport/gradle.lockfile",
    "release/release-compliance-metadata-v1.json",
    "release/third-party-license-inventory-v1.json",
    "release/version-ledger.tsv",
    "script/build_and_run.sh",
    "script/build_release_artifacts.sh",
    "script/check_release_compliance.py",
    "script/check_release_version_ledger.py",
    "script/generate_release_compliance.py",
    "script/package_release_artifacts.py",
    "script/check_release_artifact_archive.py",
    "script/run_clean_release_reproducibility.py",
    "script/run_macos_local_dmg_install_smoke.py",
    "script/run_macos_runtime_chat_cross_process_smoke.py",
    "script/test_run_macos_runtime_chat_cross_process_smoke.py",
)
SOURCE_OPTIONAL_FILES = ("Package.resolved",)
SOURCE_ROOTS = (
    "apps/android/app/src",
    "apps/android/core/pairing/src",
    "apps/android/core/protocol/src",
    "apps/android/core/transport/src",
    "apps/macos/P2PNATContracts/Sources",
    "apps/macos/Protocol/Sources",
    "apps/macos/TrustedDevices/Sources",
    "apps/macos/Pairing/Sources",
    "apps/macos/Transport/Sources",
    "apps/macos/OllamaBackend/Sources",
    "apps/macos/LMStudioBackend/Sources",
    "apps/macos/DocumentIngestion/Sources",
    "apps/macos/CompanionCore/Sources",
    "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources",
    "apps/macos/LocalAgentBridgeApp/Sources",
)


class ReleaseArchiveError(ValueError):
    """Raised when release inputs cannot form one canonical local archive."""


@dataclass(frozen=True)
class ArchiveMember:
    path: str
    data: bytes
    mode: int

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    @property
    def size(self) -> int:
        return len(self.data)


def canonical_json_bytes(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise ReleaseArchiveError(f"value is not canonical JSON: {error}") from error
    return encoded + b"\n"


def validate_member_path(member_path: str) -> None:
    try:
        raw = member_path.encode("ascii")
    except UnicodeEncodeError as error:
        raise ReleaseArchiveError(
            f"archive member path must be ASCII: {member_path!r}"
        ) from error
    if not raw or b"\\" in raw or raw.startswith(b"/"):
        raise ReleaseArchiveError(f"unsafe archive member path: {member_path!r}")
    pure = PurePosixPath(member_path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ReleaseArchiveError(f"unsafe archive member path: {member_path!r}")


def normalized_mode(file_mode: int) -> int:
    return 0o755 if file_mode & 0o111 else 0o644


def read_stable_regular_file(path: Path) -> tuple[bytes, int]:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ReleaseArchiveError(f"cannot open regular file {path}: {error}") from error

    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ReleaseArchiveError(f"release input is not a regular file: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    stable_fields = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_fields = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    data = b"".join(chunks)
    if stable_fields != after_fields or len(data) != before.st_size:
        raise ReleaseArchiveError(f"release input changed while being read: {path}")
    return data, normalized_mode(before.st_mode)


def resolve_macos_dsym_path() -> Path:
    configured = os.environ.get("AETHERLINK_REPRO_SWIFT_SCRATCH_PATH")
    if configured is None:
        build_root = DEFAULT_MACOS_BUILD_ROOT
    else:
        if configured != str(REPRO_SWIFT_SCRATCH_PATH):
            raise ReleaseArchiveError(
                "reproducible Swift scratch path differs from the fixed "
                "release path"
            )
        try:
            scratch_status = REPRO_SWIFT_SCRATCH_PATH.lstat()
            physical_scratch = REPRO_SWIFT_SCRATCH_PATH.resolve(strict=True)
        except OSError as error:
            raise ReleaseArchiveError(
                f"cannot inspect reproducible Swift scratch path: {error}"
            ) from error
        if (
            stat.S_ISLNK(scratch_status.st_mode)
            or not stat.S_ISDIR(scratch_status.st_mode)
            or scratch_status.st_uid != os.getuid()
            or physical_scratch != REPRO_SWIFT_SCRATCH_PATH
        ):
            raise ReleaseArchiveError(
                "reproducible Swift scratch path must be a physical "
                "owner-controlled directory"
            )
        physical_root = ROOT.resolve()
        if (
            physical_scratch == physical_root
            or physical_root in physical_scratch.parents
        ):
            raise ReleaseArchiveError(
                "reproducible Swift scratch path must be outside the source root"
            )
        build_root = physical_scratch
    return build_root / "arm64-apple-macosx/release/AetherLink.dSYM"


def canonicalize_r8_line_artifact(data: bytes, label: str) -> bytes:
    if not data or b"\r" in data or not data.endswith(b"\n"):
        raise ReleaseArchiveError(
            f"{label} must be nonempty LF-terminated text"
        )
    lines = data[:-1].split(b"\n")
    if (
        not lines
        or any(not line for line in lines)
        or len(lines) != len(set(lines))
    ):
        raise ReleaseArchiveError(
            f"{label} must contain nonempty unique lines"
        )
    return b"\n".join(sorted(lines)) + b"\n"


def canonicalize_r8_resources(data: bytes, label: str) -> bytes:
    if not data or b"\r" in data or b"\0" in data or not data.endswith(b"\n"):
        raise ReleaseArchiveError(
            f"{label} must be nonempty LF-terminated ASCII text"
        )
    raw_lines = data[:-1].split(b"\n")
    if not raw_lines or any(not line for line in raw_lines):
        raise ReleaseArchiveError(
            f"{label} must contain nonempty resource-state lines"
        )

    reachable_from = b" reachable from "
    reachable_suffix = b" is reachable."
    unreachable_suffix = b" is not reachable."
    resource_key_pattern = re.compile(
        rb"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[0-9]+"
    )
    normalized: list[bytes] = []
    for line in raw_lines:
        if any(byte < 0x20 or byte > 0x7E for byte in line):
            raise ReleaseArchiveError(
                f"{label} contains a non-printable resource-state byte"
            )
        if line.count(reachable_from) == 1:
            key, reason = line.split(reachable_from, 1)
            if not reason:
                raise ReleaseArchiveError(
                    f"{label} contains an empty reachability reason"
                )
            suffix = reachable_suffix
        elif line.endswith(reachable_suffix):
            key = line[: -len(reachable_suffix)]
            suffix = reachable_suffix
        elif line.endswith(unreachable_suffix):
            key = line[: -len(unreachable_suffix)]
            suffix = unreachable_suffix
        else:
            raise ReleaseArchiveError(
                f"{label} contains an unsupported resource-state line"
            )
        if resource_key_pattern.fullmatch(key) is None:
            raise ReleaseArchiveError(
                f"{label} contains an invalid resource identity"
            )
        normalized.append(key + suffix)

    if len(normalized) != len(set(normalized)):
        raise ReleaseArchiveError(
            f"{label} contains duplicate canonical resource states"
        )
    return b"\n".join(sorted(normalized)) + b"\n"


def canonicalize_r8_configuration(data: bytes, label: str) -> bytes:
    if not data or b"\0" in data or not data.endswith(b"\n"):
        raise ReleaseArchiveError(
            f"{label} must be nonempty LF-terminated text without NUL"
        )
    extracted_token = b"(extracted file: "
    opening_prefix = (
        b"# The proguard configuration file for the following section is "
    )
    closing_prefix = b"# End of content from "
    try:
        root_markers = (
            (os.fsencode(str(ROOT.resolve())), b"<SOURCE_ROOT>"),
            (
                os.fsencode(
                    str(
                        Path(
                            os.environ.get(
                                "GRADLE_USER_HOME",
                                Path.home() / ".gradle",
                            )
                        ).resolve()
                    )
                ),
                b"<GRADLE_USER_HOME>",
            ),
        )
    except UnicodeEncodeError as error:
        raise ReleaseArchiveError(
            f"{label} normalization roots must be ASCII"
        ) from error
    if (
        len({root for root, _ in root_markers}) != len(root_markers)
        or any(not root.isascii() for root, _ in root_markers)
    ):
        raise ReleaseArchiveError(
            f"{label} normalization roots must be distinct ASCII paths"
        )

    normalized_lines: list[bytes] = []
    marker_counts = {marker: 0 for _, marker in root_markers}
    active_pair: tuple[bytes, bytes] | None = None
    pair_count = 0
    for line in data[:-1].split(b"\n"):
        if extracted_token not in line:
            normalized_lines.append(line)
            continue
        if (
            b"\r" in line
            or b"\\" in line
            or line.count(extracted_token) != 1
            or not line.endswith(b")")
        ):
            raise ReleaseArchiveError(
                f"{label} contains a malformed extracted-file comment"
            )
        comment, extracted = line.split(extracted_token, 1)
        if comment.startswith(opening_prefix):
            identity = comment[len(opening_prefix):]
            is_opening = True
        elif comment.startswith(closing_prefix):
            identity = comment[len(closing_prefix):]
            is_opening = False
        else:
            raise ReleaseArchiveError(
                f"{label} contains an unexpected extracted-file comment"
            )
        if not identity or not identity.endswith(b" "):
            raise ReleaseArchiveError(
                f"{label} contains an invalid extracted-file identity"
            )
        identity = identity[:-1]
        if not identity or b"\0" in identity or b"\r" in identity:
            raise ReleaseArchiveError(
                f"{label} contains an invalid extracted-file identity"
            )

        path = extracted[:-1]
        matches = [
            (root, marker)
            for root, marker in root_markers
            if path.startswith(root + b"/")
        ]
        if len(matches) != 1:
            raise ReleaseArchiveError(
                f"{label} extracted-file path is outside declared roots"
            )
        root, marker = matches[0]
        suffix = path[len(root):]
        components = suffix[1:].split(b"/")
        if (
            not suffix.startswith(b"/")
            or not components
            or any(component in (b"", b".", b"..") for component in components)
        ):
            raise ReleaseArchiveError(
                f"{label} extracted-file path is not canonical"
            )
        canonical_path = marker + suffix
        pair = (identity, canonical_path)
        if is_opening:
            if active_pair is not None:
                raise ReleaseArchiveError(
                    f"{label} contains nested extracted-file sections"
                )
            active_pair = pair
        else:
            if active_pair != pair:
                raise ReleaseArchiveError(
                    f"{label} extracted-file section endpoints differ"
                )
            active_pair = None
            pair_count += 1
        marker_counts[marker] += 1
        normalized_lines.append(
            comment + extracted_token + canonical_path + b")"
        )

    if active_pair is not None or pair_count == 0:
        raise ReleaseArchiveError(
            f"{label} contains an incomplete extracted-file section"
        )
    if any(count == 0 for count in marker_counts.values()):
        raise ReleaseArchiveError(
            f"{label} must reference both declared extracted-file roots"
        )
    return b"\n".join(normalized_lines) + b"\n"


def canonicalize_r8_mapping_prt(data: bytes, label: str) -> bytes:
    entries: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as source:
            if source.comment:
                raise ReleaseArchiveError(
                    f"{label} must not contain a ZIP comment"
                )
            names = [info.filename for info in source.infolist()]
            if not names or len(names) != len(set(names)):
                raise ReleaseArchiveError(
                    f"{label} must contain unique ZIP members"
                )
            for info in source.infolist():
                validate_member_path(info.filename)
                if info.is_dir() or info.flag_bits & 0x1:
                    raise ReleaseArchiveError(
                        f"{label} contains a directory or encrypted member"
                    )
                entries.append((info.filename, source.read(info)))
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ReleaseArchiveError(
            f"{label} is not a readable ZIP: {error}"
        ) from error

    entries.sort(key=lambda entry: entry[0].encode("ascii"))
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
        strict_timestamps=True,
    ) as archive:
        archive.comment = b""
        for name, payload in entries:
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(
                info,
                payload,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return output.getvalue()


def collect_tree_members(
    source_root: Path,
    archive_prefix: str,
) -> list[ArchiveMember]:
    if source_root.is_symlink() or not source_root.is_dir():
        raise ReleaseArchiveError(
            f"release directory must be a real directory: {source_root}"
        )

    members: list[ArchiveMember] = []
    for candidate in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise ReleaseArchiveError(
                f"release directory contains a symlink: {candidate}"
            )
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ReleaseArchiveError(
                f"release directory contains a special file: {candidate}"
            )
        relative = candidate.relative_to(source_root).as_posix()
        member_path = f"{archive_prefix}/{relative}"
        validate_member_path(member_path)
        data, mode = read_stable_regular_file(candidate)
        members.append(ArchiveMember(member_path, data, mode))
    if not members:
        raise ReleaseArchiveError(f"release directory is empty: {source_root}")
    return members


def collect_source_paths(root: Path = ROOT) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for relative in SOURCE_REQUIRED_FILES:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ReleaseArchiveError(f"required source input is missing: {relative}")
        candidates.add(path)
    for relative in SOURCE_OPTIONAL_FILES:
        path = root / relative
        if path.is_symlink():
            raise ReleaseArchiveError(f"optional source input is a symlink: {relative}")
        if path.is_file():
            candidates.add(path)
    for relative in SOURCE_ROOTS:
        source_root = root / relative
        if source_root.is_symlink() or not source_root.is_dir():
            raise ReleaseArchiveError(f"required source root is missing: {relative}")
        for candidate in source_root.rglob("*"):
            if candidate.is_symlink():
                raise ReleaseArchiveError(
                    f"source root contains a symlink: "
                    f"{candidate.relative_to(root).as_posix()}"
                )
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise ReleaseArchiveError(
                    f"source root contains a special file: "
                    f"{candidate.relative_to(root).as_posix()}"
                )
            candidates.add(candidate)
    return tuple(
        sorted(
            candidates,
            key=lambda item: item.relative_to(root).as_posix().encode("ascii"),
        )
    )


def source_snapshot(root: Path = ROOT) -> dict[str, object]:
    files: list[dict[str, object]] = []
    digest = hashlib.sha256()
    for path in collect_source_paths(root):
        relative = path.relative_to(root).as_posix()
        validate_member_path(relative)
        data, mode = read_stable_regular_file(path)
        file_digest = hashlib.sha256(data).hexdigest()
        record = (
            relative.encode("ascii")
            + b"\0"
            + f"{mode:o}".encode("ascii")
            + b"\0"
            + str(len(data)).encode("ascii")
            + b"\0"
            + file_digest.encode("ascii")
            + b"\n"
        )
        digest.update(record)
        files.append(
            {
                "mode": f"{mode:04o}",
                "path": relative,
                "sha256": file_digest,
                "size": len(data),
            }
        )
    return {
        "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        "fileCount": len(files),
        "files": files,
        "sha256": digest.hexdigest(),
    }


def run_text(command: list[str], *, root: Path = ROOT) -> str:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    if (
        "JAVA_HOME" not in environment
        and ANDROID_STUDIO_JAVA_HOME.is_dir()
    ):
        environment["JAVA_HOME"] = str(ANDROID_STUDIO_JAVA_HOME)
    try:
        result = subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
            env=environment,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveError(
            f"command failed while collecting release metadata: {command!r}: {error}"
        ) from error
    return "\n".join(
        line.rstrip() for line in (result.stdout + result.stderr).splitlines()
    ).strip()


def run_aapt2_dump(command: list[str], root: Path = ROOT) -> str:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
            env=environment,
            text=True,
            timeout=AAPT2_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ReleaseArchiveError(
            "aapt2 APK manifest readback timed out after "
            f"{AAPT2_TIMEOUT_SECONDS} seconds"
        ) from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveError(
            f"aapt2 APK manifest readback failed: {command!r}: {error}"
        ) from error
    if result.stderr:
        raise ReleaseArchiveError(
            "aapt2 APK manifest readback emitted unexpected stderr"
        )
    return "\n".join(
        line.rstrip() for line in result.stdout.splitlines()
    ).strip()


def parse_gradle_lockfile(
    data: bytes,
    label: str,
) -> dict[str, int]:
    if (
        not data
        or data.startswith(b"\xef\xbb\xbf")
        or b"\r" in data
        or not data.endswith(b"\n")
    ):
        raise ReleaseArchiveError(
            f"{label} must be nonempty BOM-free ASCII/LF text"
        )
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ReleaseArchiveError(
            f"{label} must contain only ASCII"
        ) from error
    expected_header = [
        "# This is a Gradle generated file for dependency locking.",
        "# Manual edits can break the build and are not advised.",
        "# This file is expected to be part of source control.",
    ]
    if lines[:3] != expected_header or len(lines) < 4:
        raise ReleaseArchiveError(
            f"{label} has an unexpected Gradle lock header"
        )
    module_keys: list[str] = []
    empty_configurations: list[str] = []
    all_configurations: set[str] = set()
    for line in lines[3:]:
        if not line or line.startswith("#") or line.count("=") != 1:
            raise ReleaseArchiveError(
                f"{label} contains a malformed lock entry"
            )
        module, configuration_text = line.split("=", 1)
        configurations = (
            configuration_text.split(",")
            if configuration_text
            else []
        )
        if (
            configurations != sorted(set(configurations))
            or any(
                re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None
                for name in configurations
            )
        ):
            raise ReleaseArchiveError(
                f"{label} contains noncanonical configuration names"
        )
        if module == "empty":
            if line != lines[-1]:
                raise ReleaseArchiveError(
                    f"{label} has a noncanonical empty entry"
                )
            empty_configurations = configurations
            all_configurations.update(configurations)
            continue
        if (
            len(module.split(":")) != 3
            or any(not component for component in module.split(":"))
            or not configurations
        ):
            raise ReleaseArchiveError(
                f"{label} contains a malformed module lock"
            )
        module_keys.append(module)
        all_configurations.update(configurations)
    if module_keys != sorted(set(module_keys)):
        raise ReleaseArchiveError(
            f"{label} module locks must be strictly sorted and unique"
        )
    if not module_keys and not empty_configurations:
        raise ReleaseArchiveError(
            f"{label} must lock modules or empty configurations"
        )
    return {
        "configurationCount": len(all_configurations),
        "emptyConfigurationCount": len(empty_configurations),
        "moduleCount": len(module_keys),
    }


def swift_package_dump(root: Path = ROOT) -> dict[str, object]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            [
                "swift",
                "package",
                "--package-path",
                str(root),
                "dump-package",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            env=environment,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveError(
            f"SwiftPM package inventory failed: {error}"
        ) from error
    if result.stderr.strip():
        raise ReleaseArchiveError(
            "SwiftPM package inventory emitted unexpected standard error"
        )
    try:
        package = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseArchiveError(
            f"SwiftPM package inventory is invalid JSON: {error}"
        ) from error
    if type(package) is not dict or package.get("name") != "AetherLink":
        raise ReleaseArchiveError(
            "SwiftPM package inventory has an unexpected identity"
        )
    dependencies = package.get("dependencies")
    if type(dependencies) is not list:
        raise ReleaseArchiveError(
            "SwiftPM package dependencies must be an array"
        )
    return package


def dependency_locking_metadata(
    root: Path = ROOT,
) -> dict[str, object]:
    lock_records: list[dict[str, object]] = []
    for relative in GRADLE_LOCK_PATHS:
        data, _ = read_stable_regular_file(root / relative)
        shape = parse_gradle_lockfile(data, relative)
        lock_records.append(
            {
                **shape,
                "path": relative,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )

    package = swift_package_dump(root)
    dependencies = package["dependencies"]
    assert isinstance(dependencies, list)
    package_resolved = root / "Package.resolved"
    if dependencies:
        if package_resolved.is_symlink() or not package_resolved.is_file():
            raise ReleaseArchiveError(
                "SwiftPM external dependencies require Package.resolved"
            )
        resolved_data, _ = read_stable_regular_file(package_resolved)
        package_resolved_record: dict[str, object] | None = {
            "path": "Package.resolved",
            "sha256": hashlib.sha256(resolved_data).hexdigest(),
            "size": len(resolved_data),
        }
        resolved_status = "required-external-dependencies-locked"
    else:
        if package_resolved.exists() or package_resolved.is_symlink():
            raise ReleaseArchiveError(
                "zero-dependency SwiftPM package must not retain Package.resolved"
            )
        package_resolved_record = None
        resolved_status = "not-applicable-no-external-dependencies"

    return {
        "gradle": {
            "ignoredDependencies": list(GRADLE_IGNORED_DEPENDENCIES),
            "lockFiles": lock_records,
            "strictProperty": "aetherlinkStrictReleaseDependencyLocks=true",
            "verificationScope": (
                "settings-buildscript-and-clean-release-resolved-configurations"
                "-except-declared-ignored-dependencies"
            ),
        },
        "swiftPackageManager": {
            "externalDependencyCount": len(dependencies),
            "packageResolved": package_resolved_record,
            "status": resolved_status,
        },
    }


def java_executable() -> Path:
    configured_home = os.environ.get("JAVA_HOME")
    if configured_home:
        candidate = Path(configured_home) / "bin/java"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    studio_candidate = ANDROID_STUDIO_JAVA_HOME / "bin/java"
    if studio_candidate.is_file() and os.access(studio_candidate, os.X_OK):
        return studio_candidate
    discovered = shutil.which("java")
    if discovered:
        return Path(discovered)
    raise ReleaseArchiveError("cannot locate a Java executable for bundletool")


@functools.lru_cache(maxsize=None)
def bundletool_runtime_classpath(root: Path = ROOT) -> str:
    output = run_text(
        [
            str(root / "gradlew"),
            "--offline",
            "--no-daemon",
            "--console=plain",
            "--quiet",
            "printBundletoolRuntimeClasspath",
        ],
        root=root,
    )
    lines = output.splitlines()
    if (
        len(lines) != 1
        or not lines[0].startswith(BUNDLETOOL_CLASSPATH_MARKER)
    ):
        raise ReleaseArchiveError(
            "Gradle did not emit one bundletool runtime classpath"
        )
    classpath = lines[0].removeprefix(BUNDLETOOL_CLASSPATH_MARKER)
    entries = classpath.split(os.pathsep)
    bundletool_jars = [
        Path(entry).name
        for entry in entries
        if re.fullmatch(
            r"bundletool-[0-9][0-9.]*\.jar",
            Path(entry).name,
        )
    ]
    if (
        not entries
        or len(entries) != len(set(entries))
        or any(
            not Path(entry).is_absolute()
            or not Path(entry).is_file()
            or Path(entry).suffix != ".jar"
            for entry in entries
        )
        or bundletool_jars != [f"bundletool-{BUNDLETOOL_VERSION}.jar"]
    ):
        raise ReleaseArchiveError(
            "Gradle emitted an invalid bundletool runtime classpath"
        )
    return classpath


def run_bundletool(
    arguments: list[str],
    *,
    root: Path = ROOT,
) -> str:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            [
                str(java_executable()),
                "-cp",
                bundletool_runtime_classpath(root),
                BUNDLETOOL_MAIN_CLASS,
                *arguments,
            ],
            cwd=root,
            check=True,
            capture_output=True,
            env=environment,
            text=True,
            timeout=BUNDLETOOL_TIMEOUT_SECONDS,
        )
    except OSError as error:
        raise ReleaseArchiveError(
            f"bundletool command could not start: {error}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ReleaseArchiveError(
            "bundletool command timed out after "
            f"{BUNDLETOOL_TIMEOUT_SECONDS} seconds: {arguments[0]}"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()[-4_000:]
        raise ReleaseArchiveError(
            f"bundletool command failed ({error.returncode}): {arguments[0]}"
            + (f"\n{detail}" if detail else "")
        ) from error
    if result.stderr.strip():
        raise ReleaseArchiveError(
            "bundletool emitted unexpected standard-error output"
        )
    return result.stdout.strip()


def validate_bundletool_validation_output(output: str) -> None:
    lines = output.splitlines()
    if lines[:3] != [
        "App Bundle information",
        "------------",
        "Feature modules:",
    ]:
        raise ReleaseArchiveError(
            "bundletool validate output has an unexpected header"
        )
    feature_modules = [
        line.removeprefix("\tFeature module: ")
        for line in lines[3:]
        if line.startswith("\tFeature module: ")
    ]
    if feature_modules != ["base"]:
        raise ReleaseArchiveError(
            "bundletool validate output must contain only the base module"
        )


def bundle_structure_validation_claim_for_build(
    build_number: int,
) -> dict[str, object] | None:
    if type(build_number) is not int or build_number < 1:
        raise ReleaseArchiveError(
            "Android bundle validation build number is invalid"
        )
    if build_number <= 10:
        return None
    return {
        "member": "android/bundle/app-release.aab",
        "moduleSet": ["base"],
        "status": "passed",
        "tool": "bundletool validate",
    }


def parse_bundletool_manifest(
    output: str,
    *,
    backup_policy_required: bool = False,
) -> dict[str, object]:
    if type(backup_policy_required) is not bool:
        raise ReleaseArchiveError(
            "bundletool backup-policy requirement must be a boolean"
        )
    try:
        manifest = ET.fromstring(output)
    except ET.ParseError as error:
        raise ReleaseArchiveError(
            f"bundletool manifest output is invalid XML: {error}"
        ) from error
    if manifest.tag != "manifest":
        raise ReleaseArchiveError(
            "bundletool manifest output has an unexpected root element"
        )
    uses_sdk = [
        child for child in manifest
        if child.tag == "uses-sdk"
    ]
    if len(uses_sdk) != 1:
        raise ReleaseArchiveError(
            "bundletool manifest output must contain one uses-sdk element"
        )
    applications = [
        child for child in manifest
        if child.tag == "application"
    ]
    if len(applications) != 1:
        raise ReleaseArchiveError(
            "bundletool manifest output must contain one application element"
        )
    android_attribute = f"{{{ANDROID_XML_NAMESPACE}}}"
    application = applications[0]
    application_id = manifest.get("package")
    version_code_text = manifest.get(
        f"{android_attribute}versionCode"
    )
    version_name = manifest.get(f"{android_attribute}versionName")
    min_sdk_text = uses_sdk[0].get(
        f"{android_attribute}minSdkVersion"
    )
    target_sdk_text = uses_sdk[0].get(
        f"{android_attribute}targetSdkVersion"
    )
    allow_backup = application.get(f"{android_attribute}allowBackup")
    full_backup_content = application.get(
        f"{android_attribute}fullBackupContent"
    )
    data_extraction_rules = application.get(
        f"{android_attribute}dataExtractionRules"
    )
    for value, label in (
        (version_code_text, "versionCode"),
        (min_sdk_text, "minSdk"),
        (target_sdk_text, "targetSdk"),
    ):
        if (
            type(value) is not str
            or re.fullmatch(r"[1-9][0-9]*", value) is None
        ):
            raise ReleaseArchiveError(
                f"bundletool manifest {label} is not a positive decimal"
            )
    if type(application_id) is not str or not application_id:
        raise ReleaseArchiveError(
            "bundletool manifest package is missing"
        )
    if type(version_name) is not str or not version_name:
        raise ReleaseArchiveError(
            "bundletool manifest versionName is missing"
        )
    if allow_backup != "false":
        raise ReleaseArchiveError(
            "bundletool manifest allowBackup must be exactly false"
        )
    expected_policy_references = (
        "@xml/backup_rules",
        "@xml/data_extraction_rules",
    )
    actual_policy_references = (
        full_backup_content,
        data_extraction_rules,
    )
    if backup_policy_required:
        if actual_policy_references != expected_policy_references:
            raise ReleaseArchiveError(
                "bundletool manifest backup-policy references differ "
                "from the V1 contract"
            )
    elif actual_policy_references != (None, None):
        raise ReleaseArchiveError(
            "historical bundletool manifest unexpectedly contains "
            "backup-policy references"
        )
    assert isinstance(version_code_text, str)
    assert isinstance(min_sdk_text, str)
    assert isinstance(target_sdk_text, str)
    result: dict[str, object] = {
        "applicationId": application_id,
        "minSdk": int(min_sdk_text),
        "targetSdk": int(target_sdk_text),
        "versionCode": int(version_code_text),
        "versionName": version_name,
    }
    if backup_policy_required:
        result.update(
            {
                "allowBackup": False,
                "dataExtractionRules": data_extraction_rules,
                "fullBackupContent": full_backup_content,
            }
        )
    return result


def inspect_aab_manifest(
    aab_data: bytes,
    root: Path = ROOT,
    *,
    backup_policy_required: bool = False,
) -> dict[str, object]:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="aetherlink-release-bundle-",
        suffix=".aab",
    )
    try:
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(aab_data)
        validation = run_bundletool(
            [
                "validate",
                f"--bundle={temporary_name}",
            ],
            root=root,
        )
        validate_bundletool_validation_output(validation)
        manifest = run_bundletool(
            [
                "dump",
                "manifest",
                f"--bundle={temporary_name}",
                "--module=base",
            ],
            root=root,
        )
        parsed_manifest = parse_bundletool_manifest(
            manifest,
            backup_policy_required=backup_policy_required,
        )
        if backup_policy_required:
            packaged_policy = inspect_aab_backup_policy(
                Path(temporary_name),
                root,
            )
            expected_policy = {
                "allowBackup": parsed_manifest["allowBackup"],
                "dataExtractionRules": (
                    parsed_manifest["dataExtractionRules"]
                ),
                "fullBackupContent": (
                    parsed_manifest["fullBackupContent"]
                ),
            }
            if packaged_policy != expected_policy:
                raise ReleaseArchiveError(
                    "AAB universal-APK backup-policy readback differs "
                    "from the bundle manifest"
                )
        return parsed_manifest
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def create_ephemeral_aab_readback_keystore(
    path: Path,
    root: Path = ROOT,
) -> None:
    keytool = java_executable().with_name("keytool")
    if not keytool.is_file() or not os.access(keytool, os.X_OK):
        raise ReleaseArchiveError(
            "cannot locate keytool beside the bundletool Java runtime"
        )
    command = [
        str(keytool),
        "-genkeypair",
        "-keystore",
        str(path),
        "-storetype",
        "PKCS12",
        "-storepass",
        "aetherlink-readback",
        "-keypass",
        "aetherlink-readback",
        "-alias",
        "readback",
        "-dname",
        "CN=AetherLink Local Readback",
        "-keyalg",
        "RSA",
        "-keysize",
        "2048",
        "-validity",
        "1",
        "-noprompt",
    ]
    try:
        subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
            env={**os.environ, "LC_ALL": "C"},
            text=True,
            timeout=BUNDLETOOL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ReleaseArchiveError(
            "ephemeral AAB readback key generation timed out"
        ) from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveError(
            "ephemeral AAB readback key generation failed"
        ) from error


def inspect_aab_backup_policy(
    aab_path: Path,
    root: Path = ROOT,
) -> dict[str, object]:
    aapt2 = find_android_build_tool("aapt2", root)
    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-release-aab-policy-"
        ) as directory:
            temporary_root = Path(directory)
            keystore = temporary_root / "readback.p12"
            apks_path = temporary_root / "readback.apks"
            create_ephemeral_aab_readback_keystore(keystore, root)
            run_bundletool(
                [
                    "build-apks",
                    f"--bundle={aab_path}",
                    f"--output={apks_path}",
                    "--mode=universal",
                    "--overwrite",
                    f"--aapt2={aapt2}",
                    f"--ks={keystore}",
                    "--ks-pass=pass:aetherlink-readback",
                    "--ks-key-alias=readback",
                    "--key-pass=pass:aetherlink-readback",
                ],
                root=root,
            )
            with zipfile.ZipFile(apks_path, "r") as archive:
                if archive.namelist().count("universal.apk") != 1:
                    raise ReleaseArchiveError(
                        "bundletool readback APKS must contain exactly one "
                        "universal.apk"
                    )
                universal_apk = archive.read("universal.apk")
    except ReleaseArchiveError:
        raise
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        raise ReleaseArchiveError(
            "cannot read bundletool universal-APK policy output"
        ) from error
    return inspect_apk_backup_policy(universal_apk, root)


def bundletool_version(root: Path = ROOT) -> str:
    version = run_bundletool(["version"], root=root)
    if version != BUNDLETOOL_VERSION:
        raise ReleaseArchiveError(
            "bundletool version differs from the pinned release tool "
            f"({version!r} != {BUNDLETOOL_VERSION!r})"
        )
    return version


def android_sdk_root(root: Path = ROOT) -> Path:
    local_properties = root / "local.properties"
    if local_properties.is_file():
        for line in local_properties.read_text(encoding="utf-8").splitlines():
            if line.startswith("sdk.dir="):
                return Path(line.removeprefix("sdk.dir=").replace("\\:", ":"))
    for variable in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(variable)
        if value:
            return Path(value)
    return Path.home() / "Library/Android/sdk"


def android_build_tool_version(path: Path) -> tuple[int, ...]:
    try:
        return tuple(int(component) for component in path.parent.name.split("."))
    except ValueError:
        return ()


def find_android_build_tool(name: str, root: Path = ROOT) -> Path:
    sdk_root = android_sdk_root(root)
    candidates = [
        path
        for path in (sdk_root / "build-tools").glob(f"*/{name}")
        if path.is_file() and os.access(path, os.X_OK)
    ]
    versioned = [
        (android_build_tool_version(path), path)
        for path in candidates
        if android_build_tool_version(path)
    ]
    if not versioned:
        raise ReleaseArchiveError(
            f"cannot locate {name} under Android SDK {sdk_root}"
        )
    return max(versioned)[1]


def parse_aapt2_badging(output: str) -> dict[str, object]:
    package_matches = re.findall(
        r"^package: name='([^']+)' versionCode='([^']+)' "
        r"versionName='([^']+)'(?:\s|$)",
        output,
        re.MULTILINE,
    )
    sdk_matches = re.findall(
        r"^(?:sdkVersion|minSdkVersion):'([^']+)'$",
        output,
        re.MULTILINE,
    )
    target_matches = re.findall(
        r"^targetSdkVersion:'([^']+)'$",
        output,
        re.MULTILINE,
    )
    native_matches = re.findall(r"^native-code:(.*)$", output, re.MULTILINE)
    if (
        len(package_matches) != 1
        or len(sdk_matches) != 1
        or len(target_matches) != 1
        or len(native_matches) != 1
    ):
        raise ReleaseArchiveError("aapt2 badging output has an unexpected shape")
    package_name, version_code_text, version_name = package_matches[0]
    if re.fullmatch(r"[1-9][0-9]*", version_code_text) is None:
        raise ReleaseArchiveError("aapt2 versionCode is not a positive decimal")
    if re.fullmatch(r"[1-9][0-9]*", sdk_matches[0]) is None:
        raise ReleaseArchiveError("aapt2 minSdk is not a positive decimal")
    if re.fullmatch(r"[1-9][0-9]*", target_matches[0]) is None:
        raise ReleaseArchiveError("aapt2 targetSdk is not a positive decimal")
    native_abis = re.findall(r"'([^']+)'", native_matches[0])
    if not native_abis or len(native_abis) != len(set(native_abis)):
        raise ReleaseArchiveError("aapt2 native-code ABI list is invalid")
    return {
        "applicationId": package_name,
        "minSdk": int(sdk_matches[0]),
        "nativeAbis": native_abis,
        "targetSdk": int(target_matches[0]),
        "versionCode": int(version_code_text),
        "versionName": version_name,
    }


def parse_aapt2_apk_backup_policy(
    xmltree_output: str,
    resources_output: str,
) -> dict[str, object]:
    lines = xmltree_output.splitlines()
    manifest_entries: list[tuple[int, int]] = []
    application_entries: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        manifest_match = re.fullmatch(
            r"( *)E: manifest \(line=[1-9][0-9]*\)",
            line,
        )
        if manifest_match is not None:
            manifest_entries.append((index, len(manifest_match.group(1))))
        match = re.fullmatch(
            r"( *)E: application \(line=[1-9][0-9]*\)",
            line,
        )
        if match is not None:
            application_entries.append((index, len(match.group(1))))
    if len(manifest_entries) != 1:
        raise ReleaseArchiveError(
            "aapt2 APK manifest output must contain exactly one manifest root"
        )
    if len(application_entries) != 1:
        raise ReleaseArchiveError(
            "aapt2 APK manifest must contain exactly one application element"
        )

    manifest_index, manifest_indent = manifest_entries[0]
    application_index, application_indent = application_entries[0]
    if (
        application_index <= manifest_index
        or application_indent != manifest_indent + 4
    ):
        raise ReleaseArchiveError(
            "aapt2 APK application must be a direct manifest child"
        )
    attribute_prefix = " " * (application_indent + 2)
    attribute_pattern = re.compile(
        r"^"
        + re.escape(attribute_prefix)
        + r"A: "
        + re.escape(ANDROID_XML_NAMESPACE)
        + r":(allowBackup|dataExtractionRules|fullBackupContent)"
        + r"\(0x[0-9a-f]{8}\)=([^ ]+)$"
    )
    attributes: dict[str, list[str]] = {}
    for line in lines[application_index + 1 :]:
        element = re.match(r"^( *)E: ", line)
        if (
            element is not None
            and len(element.group(1)) <= application_indent
        ):
            break
        match = attribute_pattern.fullmatch(line)
        if match is not None:
            attributes.setdefault(match.group(1), []).append(match.group(2))

    expected_attribute_names = {
        "allowBackup",
        "dataExtractionRules",
        "fullBackupContent",
    }
    if (
        set(attributes) != expected_attribute_names
        or any(len(values) != 1 for values in attributes.values())
    ):
        raise ReleaseArchiveError(
            "aapt2 APK manifest backup-policy attributes differ "
            "from the V1 contract"
        )
    if attributes["allowBackup"] != ["false"]:
        raise ReleaseArchiveError(
            "aapt2 APK manifest allowBackup must be exactly false"
        )

    resource_entries = re.findall(
        r"^\s*resource (0x[0-9a-f]{8}) xml/([a-z][a-z0-9_]*)$",
        resources_output,
        re.MULTILINE,
    )
    resources: dict[str, str] = {}
    for resource_id, resource_name in resource_entries:
        if resource_id in resources:
            raise ReleaseArchiveError(
                "aapt2 APK resources contain a duplicate XML resource ID"
            )
        resources[resource_id] = resource_name

    resolved: dict[str, str] = {}
    for attribute_name, expected_resource_name in (
        ("dataExtractionRules", "data_extraction_rules"),
        ("fullBackupContent", "backup_rules"),
    ):
        encoded_reference = attributes[attribute_name][0]
        match = re.fullmatch(r"@(0x[0-9a-f]{8})", encoded_reference)
        if match is None:
            raise ReleaseArchiveError(
                "aapt2 APK manifest backup-policy reference "
                "is not a compiled resource ID"
            )
        resource_name = resources.get(match.group(1))
        if resource_name != expected_resource_name:
            raise ReleaseArchiveError(
                "aapt2 APK manifest backup-policy resource mapping differs "
                "from the V1 contract"
            )
        resolved[attribute_name] = f"@xml/{resource_name}"

    return {
        "allowBackup": False,
        "dataExtractionRules": resolved["dataExtractionRules"],
        "fullBackupContent": resolved["fullBackupContent"],
    }


def parse_aapt2_xml_resource_paths(
    resources_output: str,
) -> dict[str, str]:
    expected_names = {"backup_rules", "data_extraction_rules"}
    resources: dict[str, list[str]] = {}
    active_name: str | None = None
    active_indent = -1
    resource_pattern = re.compile(
        r"^( *)resource 0x[0-9a-f]{8} "
        r"xml/(backup_rules|data_extraction_rules)$"
    )
    file_pattern = re.compile(
        r"^( *)\(\) \(file\) "
        r"(res/[A-Za-z0-9_./-]+\.xml) type=XML$"
    )
    for line in resources_output.splitlines():
        resource_match = resource_pattern.fullmatch(line)
        if resource_match is not None:
            active_name = resource_match.group(2)
            active_indent = len(resource_match.group(1))
            if active_name in resources:
                raise ReleaseArchiveError(
                    "aapt2 APK resources contain a duplicate backup-policy "
                    "resource"
                )
            resources[active_name] = []
            continue
        file_match = file_pattern.fullmatch(line)
        if (
            file_match is not None
            and active_name is not None
            and len(file_match.group(1)) > active_indent
        ):
            resources[active_name].append(file_match.group(2))
            continue
        next_entry = re.match(r"^( *)resource ", line)
        if (
            next_entry is not None
            and active_name is not None
            and len(next_entry.group(1)) <= active_indent
        ):
            active_name = None
            active_indent = -1

    if set(resources) != expected_names:
        raise ReleaseArchiveError(
            "aapt2 APK resources omit a backup-policy file path"
        )
    if any(len(paths) != 1 for paths in resources.values()):
        raise ReleaseArchiveError(
            "aapt2 APK backup-policy resources must each resolve to one "
            "default XML file"
        )
    resolved = {name: paths[0] for name, paths in resources.items()}
    if len(set(resolved.values())) != len(resolved):
        raise ReleaseArchiveError(
            "aapt2 APK backup-policy resources share one compiled XML file"
        )
    return resolved


def parse_aapt2_xmltree_document(
    output: str,
    *,
    label: str,
) -> dict[str, object]:
    roots: list[dict[str, object]] = []
    stack: list[tuple[int, dict[str, object]]] = []
    element_pattern = re.compile(
        r"^( *)E: ([a-z][a-z0-9-]*) \(line=[1-9][0-9]*\)$"
    )
    attribute_pattern = re.compile(
        r'^( *)A: (domain|path)="([^"]*)" \(Raw: "([^"]*)"\)$'
    )
    for line in output.splitlines():
        element_match = element_pattern.fullmatch(line)
        if element_match is not None:
            indent = len(element_match.group(1))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            node: dict[str, object] = {
                "attributes": {},
                "children": [],
                "name": element_match.group(2),
            }
            if stack:
                if indent != stack[-1][0] + 4:
                    raise ReleaseArchiveError(
                        f"aapt2 {label} XML tree has invalid nesting"
                    )
                parent_children = stack[-1][1]["children"]
                assert isinstance(parent_children, list)
                parent_children.append(node)
            else:
                if indent != 0 or roots:
                    raise ReleaseArchiveError(
                        f"aapt2 {label} XML tree has multiple roots"
                    )
                roots.append(node)
            stack.append((indent, node))
            continue

        attribute_match = attribute_pattern.fullmatch(line)
        if attribute_match is not None:
            indent = len(attribute_match.group(1))
            if not stack or indent != stack[-1][0] + 2:
                raise ReleaseArchiveError(
                    f"aapt2 {label} XML tree has an unbound attribute"
                )
            name = attribute_match.group(2)
            value = attribute_match.group(3)
            if value != attribute_match.group(4):
                raise ReleaseArchiveError(
                    f"aapt2 {label} XML tree has mismatched raw attributes"
                )
            attributes = stack[-1][1]["attributes"]
            assert isinstance(attributes, dict)
            if name in attributes:
                raise ReleaseArchiveError(
                    f"aapt2 {label} XML tree has a duplicate attribute"
                )
            attributes[name] = value
            continue

        raise ReleaseArchiveError(
            f"aapt2 {label} XML tree contains an unexpected line"
        )

    if len(roots) != 1:
        raise ReleaseArchiveError(
            f"aapt2 {label} XML tree must contain exactly one root"
        )
    return roots[0]


def validate_aapt2_backup_policy_xmltrees(
    backup_rules_output: str,
    data_extraction_rules_output: str,
) -> None:
    def exclude_node(domain: str) -> dict[str, object]:
        return {
            "attributes": {"domain": domain, "path": "."},
            "children": [],
            "name": "exclude",
        }

    expected_backup = {
        "attributes": {},
        "children": [
            exclude_node(domain)
            for domain in LEGACY_BACKUP_EXCLUDE_DOMAINS
        ],
        "name": "full-backup-content",
    }
    expected_extraction = {
        "attributes": {},
        "children": [
            {
                "attributes": {},
                "children": [
                    exclude_node(domain)
                    for domain in DATA_EXTRACTION_EXCLUDE_DOMAINS
                ],
                "name": section,
            }
            for section in ("cloud-backup", "device-transfer")
        ],
        "name": "data-extraction-rules",
    }
    actual_backup = parse_aapt2_xmltree_document(
        backup_rules_output,
        label="backup_rules",
    )
    actual_extraction = parse_aapt2_xmltree_document(
        data_extraction_rules_output,
        label="data_extraction_rules",
    )
    if actual_backup != expected_backup:
        raise ReleaseArchiveError(
            "packaged backup_rules XML differs from the V1 exclusion contract"
        )
    if actual_extraction != expected_extraction:
        raise ReleaseArchiveError(
            "packaged data_extraction_rules XML differs from the V1 "
            "exclusion contract"
        )


def inspect_apk_badging(apk_data: bytes, root: Path = ROOT) -> dict[str, object]:
    aapt2 = find_android_build_tool("aapt2", root)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="aetherlink-release-apk-",
        suffix=".apk",
    )
    try:
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(apk_data)
        badging = run_text(
            [str(aapt2), "dump", "badging", temporary_name],
            root=root,
        )
        return parse_aapt2_badging(badging)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def inspect_apk_backup_policy(
    apk_data: bytes,
    root: Path = ROOT,
) -> dict[str, object]:
    aapt2 = find_android_build_tool("aapt2", root)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="aetherlink-release-apk-policy-",
        suffix=".apk",
    )
    try:
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(apk_data)
        xmltree = run_aapt2_dump(
            [
                str(aapt2),
                "dump",
                "xmltree",
                "--file",
                "AndroidManifest.xml",
                temporary_name,
            ],
            root,
        )
        resources = run_aapt2_dump(
            [
                str(aapt2),
                "dump",
                "resources",
                "--no-values",
                temporary_name,
            ],
            root,
        )
        manifest_policy = parse_aapt2_apk_backup_policy(
            xmltree,
            resources,
        )
        resources_with_values = run_aapt2_dump(
            [
                str(aapt2),
                "dump",
                "resources",
                temporary_name,
            ],
            root,
        )
        resource_paths = parse_aapt2_xml_resource_paths(
            resources_with_values
        )
        backup_rules = run_aapt2_dump(
            [
                str(aapt2),
                "dump",
                "xmltree",
                "--file",
                resource_paths["backup_rules"],
                temporary_name,
            ],
            root,
        )
        data_extraction_rules = run_aapt2_dump(
            [
                str(aapt2),
                "dump",
                "xmltree",
                "--file",
                resource_paths["data_extraction_rules"],
                temporary_name,
            ],
            root,
        )
        validate_aapt2_backup_policy_xmltrees(
            backup_rules,
            data_extraction_rules,
        )
        return manifest_policy
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def git_metadata(root: Path = ROOT) -> dict[str, object]:
    head = run_text(["git", "rev-parse", "HEAD"], root=root)
    origin_main = run_text(["git", "rev-parse", "origin/main"], root=root)
    status_text = run_text(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        root=root,
    )
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise ReleaseArchiveError(f"unexpected Git HEAD: {head!r}")
    if re.fullmatch(r"[0-9a-f]{40}", origin_main) is None:
        raise ReleaseArchiveError(f"unexpected origin/main: {origin_main!r}")
    return {
        "head": head,
        "originMain": origin_main,
        "worktreeState": "dirty-content-snapshot" if status_text else "clean",
    }


def toolchain_metadata(root: Path = ROOT) -> dict[str, object]:
    versions_text = (
        root / "gradle/libs.versions.toml"
    ).read_text(encoding="utf-8")
    version_values: dict[str, str] = {}
    for name in ("agp", "kotlin"):
        match = re.search(
            rf"^{re.escape(name)}\s*=\s*\"([^\"]+)\"\s*$",
            versions_text,
            re.MULTILINE,
        )
        if match is None:
            raise ReleaseArchiveError(
                f"cannot resolve {name} from gradle/libs.versions.toml"
            )
        version_values[name] = match.group(1)
    wrapper = (
        root / "gradle/wrapper/gradle-wrapper.properties"
    ).read_text(encoding="utf-8")
    gradle_match = re.search(r"gradle-([0-9][0-9.]*)-", wrapper)
    swift_tools_match = re.match(
        r"// swift-tools-version:\s*([0-9.]+)",
        (root / "Package.swift").read_text(encoding="utf-8"),
    )
    if gradle_match is None or swift_tools_match is None:
        raise ReleaseArchiveError("cannot resolve pinned Gradle or Swift tools version")
    return {
        "aapt2": run_text(
            [str(find_android_build_tool("aapt2", root)), "version"],
            root=root,
        ),
        "androidGradlePlugin": version_values["agp"],
        "bundletool": bundletool_version(root),
        "gradleWrapper": gradle_match.group(1),
        "java": run_text([str(java_executable()), "-version"], root=root),
        "kotlin": version_values["kotlin"],
        "swift": run_text(["swift", "--version"], root=root),
        "swiftTools": swift_tools_match.group(1),
        "xcode": run_text(["xcodebuild", "-version"], root=root),
    }


def parse_dwarfdump_uuid(path: Path) -> tuple[str, str]:
    output = run_text(["/usr/bin/dwarfdump", "--uuid", str(path)])
    matches = re.findall(
        r"^UUID:\s*([0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12})\s+"
        r"\(([^)]+)\)",
        output,
        re.MULTILINE,
    )
    if len(matches) != 1:
        raise ReleaseArchiveError(
            f"expected one Mach-O UUID for {path}, found {matches!r}"
        )
    return matches[0]


def find_llvm_readelf(root: Path = ROOT) -> Path:
    sdk_root = android_sdk_root(root)
    candidates = sorted(
        sdk_root.glob("ndk/*/toolchains/llvm/prebuilt/*/bin/llvm-readelf"),
        key=lambda item: item.as_posix(),
    )
    if not candidates:
        raise ReleaseArchiveError(
            f"cannot locate llvm-readelf under Android SDK {sdk_root}"
        )
    return candidates[-1]


def inspect_elf(
    path: Path,
    llvm_readelf: Path,
) -> tuple[str | None, bool]:
    notes = run_text([str(llvm_readelf), "-n", str(path)])
    build_id_match = re.search(r"Build ID:\s*([0-9a-fA-F]+)", notes)
    sections = run_text([str(llvm_readelf), "-W", "-S", str(path)])
    has_debug_metadata = (
        re.search(r"\.symtab(?:\s|$)", sections) is not None
        or re.search(r"\.debug_[A-Za-z0-9_.-]+", sections) is not None
    )
    build_id = build_id_match.group(1).lower() if build_id_match else None
    return build_id, has_debug_metadata


def android_metadata(
    apk_data: bytes,
    aab_data: bytes,
    mapping_data: bytes,
    current: ReleaseVersion,
    root: Path = ROOT,
) -> dict[str, object]:
    try:
        apk_metadata = json.loads(
            ANDROID_APK_METADATA.read_text(encoding="utf-8")
        )
        if type(apk_metadata) is not dict:
            raise ValueError("APK metadata root must be an object")
        if apk_metadata.get("applicationId") != "com.localagentbridge.android":
            raise ValueError("unexpected APK metadata applicationId")
        if apk_metadata.get("variantName") != "release":
            raise ValueError("unexpected APK metadata variantName")
        elements = apk_metadata["elements"]
        if type(elements) is not list or len(elements) != 1:
            raise ValueError("expected one APK metadata element")
        apk_element = elements[0]
        if type(apk_element) is not dict:
            raise ValueError("APK metadata element must be an object")
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise ReleaseArchiveError(f"invalid Android APK metadata: {error}") from error
    if type(apk_element.get("versionCode")) is not int:
        raise ReleaseArchiveError("Android versionCode must be an integer")
    if apk_element["versionCode"] != current.build_number:
        raise ReleaseArchiveError("Android APK versionCode does not match ledger")
    if apk_element.get("versionName") != current.marketing_version:
        raise ReleaseArchiveError("Android APK versionName does not match ledger")
    backup_policy_required = (
        current.build_number >= ANDROID_BACKUP_POLICY_BUILD
    )
    apk_badging = inspect_apk_badging(apk_data, root)
    expected_badging = {
        "applicationId": "com.localagentbridge.android",
        "minSdk": 26,
        "nativeAbis": ["arm64-v8a"],
        "targetSdk": 36,
        "versionCode": current.build_number,
        "versionName": current.marketing_version,
    }
    if apk_badging != expected_badging:
        raise ReleaseArchiveError(
            f"Android APK badging differs from V1 contract: {apk_badging!r}"
        )
    if backup_policy_required:
        apk_backup_policy = inspect_apk_backup_policy(apk_data, root)
        expected_apk_backup_policy = {
            "allowBackup": False,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "fullBackupContent": "@xml/backup_rules",
        }
        if apk_backup_policy != expected_apk_backup_policy:
            raise ReleaseArchiveError(
                "Android APK backup policy differs from the V1 contract: "
                f"{apk_backup_policy!r}"
            )
    expected_bundle_manifest = {
        "applicationId": expected_badging["applicationId"],
        "minSdk": expected_badging["minSdk"],
        "targetSdk": expected_badging["targetSdk"],
        "versionCode": expected_badging["versionCode"],
        "versionName": expected_badging["versionName"],
    }
    if backup_policy_required:
        expected_bundle_manifest.update(
            {
                "allowBackup": False,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
            }
        )
    aab_manifest = inspect_aab_manifest(
        aab_data,
        root,
        backup_policy_required=backup_policy_required,
    )
    if aab_manifest != expected_bundle_manifest:
        raise ReleaseArchiveError(
            "Android AAB manifest differs from the V1 contract: "
            f"{aab_manifest!r}"
        )

    try:
        with zipfile.ZipFile(io.BytesIO(aab_data), "r") as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)):
                raise ReleaseArchiveError("AAB contains duplicate entries")
            embedded_mapping = bundle.read(
                "BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map"
            )
            native_names = sorted(
                name
                for name in names
                if name.startswith("base/lib/") and name.endswith(".so")
            )
            native_symbol_names = sorted(
                name
                for name in names
                if name.startswith(
                    "BUNDLE-METADATA/com.android.tools.build.debugsymbols/"
                )
            )
            native_bytes = {name: bundle.read(name) for name in native_names}
            signed_entries = sorted(
                name
                for name in names
                if re.fullmatch(
                    r"META-INF/[^/]+\.(?:RSA|DSA|EC|SF)",
                    name,
                    re.IGNORECASE,
                )
            )
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ReleaseArchiveError(f"invalid Android AAB: {error}") from error

    if embedded_mapping != mapping_data:
        raise ReleaseArchiveError(
            "AAB embedded R8 mapping does not match mapping.txt"
        )
    if not native_names:
        raise ReleaseArchiveError("Android AAB contains no JNI libraries")

    llvm_readelf = find_llvm_readelf(root)
    native_libraries: list[dict[str, object]] = []
    any_merged_debug_metadata = False
    for name in native_names:
        parts = PurePosixPath(name).parts
        if len(parts) != 4:
            raise ReleaseArchiveError(f"unexpected AAB native path: {name}")
        _, _, abi, library_name = parts
        merged_path = ANDROID_MERGED_NATIVE_LIBS / abi / library_name
        stripped_path = ANDROID_STRIPPED_NATIVE_LIBS / abi / library_name
        merged_data, _ = read_stable_regular_file(merged_path)
        stripped_data, _ = read_stable_regular_file(stripped_path)
        if stripped_data != native_bytes[name]:
            raise ReleaseArchiveError(
                f"AAB JNI member does not match stripped build output: {name}"
            )
        build_id, has_debug_metadata = inspect_elf(merged_path, llvm_readelf)
        if build_id is None:
            raise ReleaseArchiveError(
                f"merged JNI library has no GNU Build ID: {name}"
            )
        if not has_debug_metadata and merged_data != stripped_data:
            raise ReleaseArchiveError(
                f"pre-stripped JNI input differs from packaged output: {name}"
            )
        any_merged_debug_metadata |= has_debug_metadata
        native_libraries.append(
            {
                "abi": abi,
                "buildId": build_id,
                "memberPath": name,
                "mergedInputSha256": hashlib.sha256(merged_data).hexdigest(),
                "name": library_name,
                "sha256": hashlib.sha256(native_bytes[name]).hexdigest(),
                "size": len(native_bytes[name]),
            }
        )

    abis = sorted({str(item["abi"]) for item in native_libraries})
    if abis != ["arm64-v8a"]:
        raise ReleaseArchiveError(
            f"Android V1 Release must contain only arm64-v8a, found {abis}"
        )

    native_archive_present = ANDROID_NATIVE_SYMBOL_ARCHIVE.is_file()
    if native_archive_present:
        if not native_symbol_names:
            raise ReleaseArchiveError(
                "native symbol archive exists but AAB has no embedded native symbols"
            )
        native_symbol_status = "available"
    else:
        if native_symbol_names:
            raise ReleaseArchiveError(
                "AAB native symbols exist without the expected standalone archive"
            )
        if any_merged_debug_metadata:
            raise ReleaseArchiveError(
                "merged JNI libraries contain debug metadata but AGP produced no archive"
            )
        native_symbol_status = "unavailable-upstream-prestripped"

    metadata: dict[str, object] = {
        "abis": abis,
        "applicationId": apk_badging["applicationId"],
        "bundleManifestReadback": {
            "member": "android/bundle/app-release.aab",
            "tool": "bundletool dump manifest",
            "verifiedFields": [
                *BASE_BUNDLE_MANIFEST_VERIFIED_FIELDS,
                *(
                    BACKUP_POLICY_BUNDLE_MANIFEST_VERIFIED_FIELDS
                    if backup_policy_required
                    else ()
                ),
            ],
        },
        "mappingEmbeddedByteIdentical": True,
        "minSdk": apk_badging["minSdk"],
        "nativeLibraries": native_libraries,
        "nativeSymbols": {
            "archiveMember": (
                "android/native-debug-symbols/native-debug-symbols.zip"
                if native_archive_present
                else None
            ),
            "requestedLevel": "SYMBOL_TABLE",
            "status": native_symbol_status,
        },
        "signatureState": "unsigned" if not signed_entries else "signed",
        "targetSdk": apk_badging["targetSdk"],
        "versionCode": current.build_number,
        "versionName": current.marketing_version,
    }
    if backup_policy_required:
        metadata["apkManifestReadback"] = {
            "member": "android/apk/app-release-unsigned.apk",
            "tool": "aapt2 dump xmltree + resources --no-values",
            "verifiedFields": [
                *BACKUP_POLICY_APK_MANIFEST_VERIFIED_FIELDS,
            ],
        }
    bundle_structure_validation = (
        bundle_structure_validation_claim_for_build(
            current.build_number
        )
    )
    if bundle_structure_validation is not None:
        metadata[
            "bundleStructureValidation"
        ] = bundle_structure_validation
    return metadata


def macos_metadata(
    current: ReleaseVersion,
    macos_dsym: Path,
) -> dict[str, object]:
    info_path = MACOS_APP / "Contents/Info.plist"
    try:
        info = plistlib.loads(read_stable_regular_file(info_path)[0])
    except (plistlib.InvalidFileException, KeyError, TypeError) as error:
        raise ReleaseArchiveError(f"invalid macOS Info.plist: {error}") from error
    expected = {
        "CFBundleIdentifier": "dev.aetherlink.companion",
        "CFBundleShortVersionString": current.marketing_version,
        "CFBundleVersion": str(current.build_number),
        "LSMinimumSystemVersion": "14.0",
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise ReleaseArchiveError(
                f"macOS {key} does not match release contract "
                f"({info.get(key)!r} != {value!r})"
            )

    executable = MACOS_APP / "Contents/MacOS/AetherLink"
    app_uuid, app_architecture = parse_dwarfdump_uuid(executable)
    dsym_uuid, dsym_architecture = parse_dwarfdump_uuid(macos_dsym)
    if (app_uuid, app_architecture) != (dsym_uuid, dsym_architecture):
        raise ReleaseArchiveError("macOS app and dSYM UUID/architecture differ")
    architectures = run_text(["/usr/bin/lipo", "-archs", str(executable)]).split()
    if architectures != ["arm64"]:
        raise ReleaseArchiveError(
            f"macOS V1 Release must be thin arm64, found {architectures}"
        )
    signature_details = run_text(
        ["/usr/bin/codesign", "-dv", "--verbose=4", str(MACOS_APP)]
    )
    if "Signature=adhoc" not in signature_details:
        raise ReleaseArchiveError("macOS local package must retain its ad-hoc label")
    run_text(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(MACOS_APP)]
    )

    localization_root = (
        MACOS_APP
        / "Contents/Resources/AetherLink_LocalAgentBridge.bundle"
    )
    locales = sorted(
        path.name.removesuffix(".lproj")
        for path in localization_root.glob("*.lproj")
        if path.is_dir() and not path.is_symlink()
    )
    if locales != ["en", "fr", "ja", "ko", "zh-hans"]:
        raise ReleaseArchiveError(
            f"macOS packaged locales differ from V1 set: {locales}"
        )
    return {
        "architectures": architectures,
        "bundleId": expected["CFBundleIdentifier"],
        "buildNumber": current.build_number,
        "dSYM": {
            "architecture": dsym_architecture,
            "uuid": dsym_uuid,
        },
        "locales": locales,
        "marketingVersion": current.marketing_version,
        "minimumSystemVersion": expected["LSMinimumSystemVersion"],
        "signatureState": "ad-hoc-local",
        "uuid": app_uuid,
    }


def member_record(member: ArchiveMember) -> dict[str, object]:
    return {
        "mode": f"{member.mode:04o}",
        "path": member.path,
        "sha256": member.sha256,
        "size": member.size,
    }


def release_id(current: ReleaseVersion) -> str:
    return (
        f"aetherlink-{current.marketing_version}+{current.build_number}-"
        f"{CHANNEL}-{ARCHIVE_REVISION}"
    )


def collect_release_members(
    current: ReleaseVersion,
    source: dict[str, object],
) -> tuple[
    list[ArchiveMember],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    macos_dsym = resolve_macos_dsym_path()
    exact_files = {
        "android/apk/app-release-unsigned.apk": ANDROID_APK,
        "android/apk/output-metadata.json": ANDROID_APK_METADATA,
        "android/bundle/app-release.aab": ANDROID_AAB,
        "android/sdk-dependencies/sdkDependencies.txt": ANDROID_SDK_DEPENDENCIES,
    }
    for name in MAPPING_FILES:
        exact_files[f"android/mapping/{name}"] = ANDROID_MAPPING_DIR / name
    if ANDROID_NATIVE_SYMBOL_ARCHIVE.is_file():
        exact_files[
            "android/native-debug-symbols/native-debug-symbols.zip"
        ] = ANDROID_NATIVE_SYMBOL_ARCHIVE

    members: list[ArchiveMember] = []
    loaded: dict[str, bytes] = {}
    for member_path, source_path in sorted(exact_files.items()):
        validate_member_path(member_path)
        data, mode = read_stable_regular_file(source_path)
        if not data:
            raise ReleaseArchiveError(f"release artifact is empty: {source_path}")
        if member_path == "android/mapping/configuration.txt":
            data = canonicalize_r8_configuration(data, member_path)
        elif member_path == "android/mapping/mapping.prt":
            data = canonicalize_r8_mapping_prt(data, member_path)
        elif member_path == "android/mapping/resources.txt":
            data = canonicalize_r8_resources(data, member_path)
        elif member_path == "android/mapping/seeds.txt":
            data = canonicalize_r8_line_artifact(data, member_path)
        loaded[member_path] = data
        members.append(ArchiveMember(member_path, data, mode))

    android = android_metadata(
        loaded["android/apk/app-release-unsigned.apk"],
        loaded["android/bundle/app-release.aab"],
        loaded["android/mapping/mapping.txt"],
        current,
    )
    macos = macos_metadata(current, macos_dsym)
    native_status_bytes = canonical_json_bytes(
        {
            "nativeLibraries": android["nativeLibraries"],
            "nativeSymbols": android["nativeSymbols"],
            "schemaVersion": MEMBER_SCHEMA_VERSION,
        }
    )
    members.append(
        ArchiveMember(
            "android/native-symbol-status.json",
            native_status_bytes,
            0o644,
        )
    )
    source_bytes = canonical_json_bytes(
        {
            "schemaVersion": MEMBER_SCHEMA_VERSION,
            "snapshot": source,
        }
    )
    members.append(ArchiveMember("source-files.json", source_bytes, 0o644))
    try:
        compliance_members, compliance = build_release_compliance(
            marketing_version=current.marketing_version,
            build_number=current.build_number,
            source_snapshot_sha256=str(source["sha256"]),
            root=ROOT,
        )
    except ComplianceError as error:
        raise ReleaseArchiveError(
            f"release compliance inputs are invalid: {error}"
        ) from error
    for member_path, data in compliance_members:
        validate_member_path(member_path)
        if not data:
            raise ReleaseArchiveError(
                f"release compliance member is empty: {member_path}"
            )
        members.append(ArchiveMember(member_path, data, 0o644))
    members.extend(collect_tree_members(MACOS_APP, "macos/AetherLink.app"))
    members.extend(collect_tree_members(macos_dsym, "macos/AetherLink.dSYM"))
    members.sort(key=lambda member: member.path.encode("ascii"))
    if len({member.path for member in members}) != len(members):
        raise ReleaseArchiveError("release payload contains duplicate member paths")
    return members, android, macos, compliance


def build_manifest(
    current: ReleaseVersion,
    members: list[ArchiveMember],
    source: dict[str, object],
    android: dict[str, object],
    macos: dict[str, object],
    compliance: dict[str, object],
) -> dict[str, object]:
    ledger_data, _ = read_stable_regular_file(LEDGER_PATH)
    git = git_metadata()
    return {
        "archive": {
            "artifactPathPolicy": (
                "raw-paths-with-declared-r8-byte-normalization"
            ),
            "compression": "stored",
            "entryOrder": "manifest-first-then-ascii-path",
            "entryTimestamp": "1980-01-01T00:00:00",
            "extendedAttributesIncluded": False,
            "memberCountExcludingManifest": len(members),
            "normalizations": list(ARCHIVE_NORMALIZATIONS),
            "reproducibilityScope": (
                "canonical-container-for-normalized-release-inputs"
            ),
        },
        "channel": CHANNEL,
        "compliance": compliance,
        "dependencyLocking": dependency_locking_metadata(),
        "ledger": {
            "path": LEDGER_PATH.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(ledger_data).hexdigest(),
            "size": len(ledger_data),
        },
        "members": [member_record(member) for member in members],
        "platforms": {
            "android": android,
            "macos": macos,
        },
        "product": "AetherLink",
        "release": {
            "buildNumber": current.build_number,
            "marketingVersion": current.marketing_version,
            "releaseId": release_id(current),
        },
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "source": {
            **git,
            "fileCount": source["fileCount"],
            "member": "source-files.json",
            "snapshotAlgorithm": source["algorithm"],
            "snapshotSha256": source["sha256"],
        },
        "toolchains": toolchain_metadata(),
    }


def write_canonical_zip(
    path: Path,
    manifest_bytes: bytes,
    members: list[ArchiveMember],
) -> None:
    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_STORED,
        allowZip64=True,
        strict_timestamps=True,
    ) as archive:
        archive.comment = b""
        ordered = [ArchiveMember("manifest.json", manifest_bytes, 0o644), *members]
        for member in ordered:
            validate_member_path(member.path)
            info = zipfile.ZipInfo(member.path, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (member.mode & 0xFFFF) << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(info, member.data)


def same_files(left: Path, right: Path) -> bool:
    if not left.is_file() or not right.is_file():
        return False
    if left.stat().st_size != right.stat().st_size:
        return False
    return hashlib.sha256(left.read_bytes()).digest() == hashlib.sha256(
        right.read_bytes()
    ).digest()


def file_size_and_sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def publish_archive_directory(
    output_root: Path,
    archive_id: str,
    archive_bytes_path: Path,
    manifest_bytes: bytes,
    *,
    expected_sidecars: dict[str, tuple[int, str]] | None = None,
) -> tuple[Path, bool]:
    output_root.mkdir(parents=True, exist_ok=True)
    final_directory = output_root / archive_id
    temporary_directory = Path(
        tempfile.mkdtemp(prefix=f".{archive_id}.tmp-", dir=output_root)
    )
    archive_name = f"{archive_id}.zip"
    manifest_name = f"{archive_id}.manifest.json"
    checksum_name = f"{archive_id}.zip.sha256"
    temporary_archive = temporary_directory / archive_name
    temporary_manifest = temporary_directory / manifest_name
    temporary_checksum = temporary_directory / checksum_name
    try:
        shutil.copyfile(archive_bytes_path, temporary_archive)
        temporary_manifest.write_bytes(manifest_bytes)
        archive_digest = hashlib.sha256(temporary_archive.read_bytes()).hexdigest()
        temporary_checksum.write_text(
            f"{archive_digest}  {archive_name}\n",
            encoding="ascii",
        )
        expected_names = {archive_name, manifest_name, checksum_name}
        if expected_sidecars is not None:
            if (
                type(expected_sidecars) is not dict
                or set(expected_sidecars) != expected_names
                or any(
                    type(identity) is not tuple
                    or len(identity) != 2
                    or type(identity[0]) is not int
                    or identity[0] < 0
                    or type(identity[1]) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", identity[1]) is None
                    for identity in expected_sidecars.values()
                )
            ):
                raise ReleaseArchiveError(
                    "expected release sidecar identities are invalid"
                )
            actual_sidecars = {
                name: file_size_and_sha256(temporary_directory / name)
                for name in sorted(expected_names)
            }
            if actual_sidecars != expected_sidecars:
                raise ReleaseArchiveError(
                    "release archive candidate differs from the qualified "
                    "sidecar identities"
                )
        if final_directory.exists():
            if not final_directory.is_dir() or final_directory.is_symlink():
                raise ReleaseArchiveError(
                    f"release archive target is not a real directory: "
                    f"{final_directory}"
                )
            actual_names = {path.name for path in final_directory.iterdir()}
            if actual_names != expected_names:
                raise ReleaseArchiveError(
                    f"existing release archive has unexpected files: "
                    f"{sorted(actual_names)}"
                )
            for name in sorted(expected_names):
                if not same_files(temporary_directory / name, final_directory / name):
                    raise ReleaseArchiveError(
                        f"existing release archive differs; increment the shared build number instead of overwriting {final_directory}"
                    )
            return final_directory, True
        os.replace(temporary_directory, final_directory)
        return final_directory, False
    finally:
        if temporary_directory.exists():
            shutil.rmtree(temporary_directory)


def create_release_archive(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, bool]:
    current = load_release_version_ledger()[-1]
    failures = source_contract_failures(current) + artifact_contract_failures(current)
    if failures:
        raise ReleaseArchiveError(
            "release version contract failed:\n - " + "\n - ".join(failures)
        )
    source_before = source_snapshot()
    members, android, macos, compliance = collect_release_members(
        current,
        source_before,
    )
    source_after = source_snapshot()
    if source_before != source_after:
        raise ReleaseArchiveError(
            "build source inputs changed while the release archive was assembled"
        )
    manifest = build_manifest(
        current,
        members,
        source_before,
        android,
        macos,
        compliance,
    )
    manifest_bytes = canonical_json_bytes(manifest)
    output_root.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{release_id(current)}.zip-",
        dir=output_root,
    )
    os.close(file_descriptor)
    temporary_archive = Path(temporary_name)
    try:
        write_canonical_zip(temporary_archive, manifest_bytes, members)
        return publish_archive_directory(
            output_root,
            release_id(current),
            temporary_archive,
            manifest_bytes,
        )
    finally:
        if temporary_archive.exists():
            temporary_archive.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "source-digest",
        help="print the canonical current build-input snapshot digest",
    )
    create_parser = subparsers.add_parser(
        "create",
        help="create or idempotently confirm the local release evidence archive",
    )
    create_parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    arguments = parser.parse_args()
    try:
        if arguments.command == "source-digest":
            print(source_snapshot()["sha256"])
            return 0
        directory, existed = create_release_archive(arguments.output_root)
    except ReleaseArchiveError as error:
        print(f"Release archive failed: {error}", file=os.sys.stderr)
        return 1
    state = "already matched" if existed else "created"
    print(f"Release archive {state}: {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
