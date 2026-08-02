#!/usr/bin/env python3
"""Independently read back a canonical local release evidence archive."""

from __future__ import annotations

import argparse
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
import zlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script.check_release_version_ledger import (
    LedgerError,
    ReleaseVersion,
    load_release_version_ledger,
)
from script.check_release_compliance import (
    ComplianceVerificationError,
    verify_release_compliance,
)


DEFAULT_OUTPUT_ROOT = ROOT / "dist/releases"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
LEGACY_MANIFEST_SCHEMA_VERSION = 1
CURRENT_MANIFEST_SCHEMA_VERSION = 2
MEMBER_SCHEMA_VERSION = 1
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
GRADLE_IGNORED_DEPENDENCY_PARENT = {
    "org.jetbrains.kotlin:kotlin-stdlib-common": (
        "org.jetbrains.kotlin:kotlin-stdlib"
    ),
}
ANDROID_XML_NAMESPACE = "http://schemas.android.com/apk/res/android"
BUNDLETOOL_CLASSPATH_MARKER = "AETHERLINK_BUNDLETOOL_CLASSPATH="
BUNDLETOOL_MAIN_CLASS = (
    "com.android.tools.build.bundletool.BundleToolMain"
)
BUNDLETOOL_VERSION = "1.18.3"
BUNDLETOOL_TIMEOUT_SECONDS = 60
AAPT2_TIMEOUT_SECONDS = 60
ANDROID_BUILD_TOOLS_VERSION = "36.0.0"
ANDROID_NDK_VERSION = "28.2.13676358"
ANDROID_RELEASE_SDK_DEPENDENCIES_SHA256 = (
    "a8d5bf95bcb9d96daef3be37aed81344f992bdac5f15ce6926ff10af393f71cf"
)
ANDROID_RELEASE_SDK_DEPENDENCIES_PROTOBUF_SHA256 = (
    "2a061d9f10804b3c4a2e6e63eae2d39cea066700863a0e87993562f052e20ca0"
)
ANDROID_RELEASE_R8_MAPPING_SHA256 = (
    "25726643b405661101d4e938ca5e5d525cc09e0fe00ed49296d7e7e87cdc3383"
)
ANDROID_RELEASE_R8_MAPPING_PRT_LOGICAL_SHA256 = (
    "6b3fe34fe61466d9d274848f7085a135c53476e09d32d4826f4e8563cce0fde8"
)
ANDROID_RELEASE_APK_BASELINE_PROFILE_SHA256 = (
    "9872d570c48fdcf7bd21ca3c35f42124f1251110c407e36662d3ca1cc4209fb8"
)
ANDROID_RELEASE_APK_BASELINE_PROFILE_METADATA_SHA256 = (
    "085b63a646d83a869ba06e2468259f564c2e472780d2f87a3b081f17a067eaeb"
)
ANDROID_RELEASE_API31_DM_PROFILE_SHA256 = (
    "4ca2bff94b68bc5adc046b378eac4532aade7f76cca6e44ed82938ff53869ff8"
)
ANDROID_RELEASE_DEX_SHA256 = (
    "80faf2ed2d61b3231e6ffaf13f3a96271d756cabf0403afcac58b9def41f4a10"
)
ANDROID_BACKUP_POLICY_BUILD = 15
ANDROID_ENTRY_POINT_TOPOLOGY_BUILD = 23
ANDROID_APPLICATION_SHELL_BUILD = 23
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
ENTRY_POINT_TOPOLOGY_MANIFEST_VERIFIED_FIELDS = (
    "entryPointTopology",
)
APPLICATION_SHELL_MANIFEST_VERIFIED_FIELDS = (
    "applicationShell",
)
ANDROID_MAIN_ACTIVITY = "com.localagentbridge.android.MainActivity"
ANDROID_SHARE_MIME_TYPE_COUNT = 44
ANDROID_SHARE_MIME_TYPES_CANONICAL_SHA256 = (
    "a04e83ed785b94ca4160981bb069104949742c6102008a452f650118f7902a8f"
)
ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES = {
    "icon": "@mipmap/ic_launcher",
    "label": "@string/app_name",
    "localeConfig": "@xml/locales_config",
    "roundIcon": "@mipmap/ic_launcher_round",
    "theme": "@style/AppTheme",
}
ANDROID_LOCALE_CONFIG_LOCALES = (
    "en",
    "ko",
    "ja",
    "zh-CN",
    "fr",
)
ANDROID_LOCALIZED_STRING_RESOURCE = "@string/status_title"
ANDROID_LOCALIZED_STRING_VALUES = {
    "default": "Pairing & Connection",
    "en": "Pairing & Connection",
    "fr": "Jumelage et connexion",
    "ja": "ペアリングと接続",
    "ko": "페어링 및 연결",
    "zh-CN": "配对与连接",
}
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
LEGACY_ARCHIVE_NORMALIZATIONS_BUILD_1_TO_3 = (
    "android/mapping/mapping.prt:"
    "sorted-members-fixed-metadata-deflate-9",
    "android/mapping/resources.txt:bytewise-sorted-unique-lines",
    "android/mapping/seeds.txt:bytewise-sorted-unique-lines",
)
LEGACY_ARCHIVE_NORMALIZATIONS_BUILD_4 = (
    "android/mapping/configuration.txt:"
    "declared-extracted-file-root-markers",
    "android/mapping/mapping.prt:"
    "sorted-members-fixed-metadata-deflate-9",
    "android/mapping/resources.txt:bytewise-sorted-unique-lines",
    "android/mapping/seeds.txt:bytewise-sorted-unique-lines",
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
ANDROID_STUDIO_JAVA_HOME = Path(
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
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
    "script/run_macos_clean_home_installed_app_smoke.py",
    "script/run_macos_clean_home_installed_state_recovery_smoke.py",
    "script/run_macos_isolated_uninstall_reinstall_smoke.py",
    "script/test_run_macos_isolated_uninstall_reinstall_smoke.py",
    "script/run_macos_isolated_upgrade_smoke.py",
    "script/run_macos_local_dmg_install_smoke.py",
    "script/run_macos_local_dmg_install_smoke_v2.py",
    "script/run_macos_local_dmg_uninstall_reinstall_smoke.py",
    (
        "script/"
        "run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
    ),
    (
        "script/run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ),
    (
        "script/test_run_macos_local_dmg_uninstall_reinstall_"
        "abrupt_process_state_recovery_smoke.py"
    ),
    "script/run_macos_build24_idle_resource_stability_smoke.py",
    (
        "script/run_macos_current_source_lane_a_"
        "idle_resource_stability_smoke.py"
    ),
    (
        "script/test_run_macos_current_source_lane_a_"
        "idle_resource_stability_smoke.py"
    ),
    "script/run_macos_current_unsealed_install_recovery_smoke.py",
    "script/test_run_macos_current_unsealed_install_recovery_smoke.py",
    "script/run_macos_packaged_app_lifecycle_smoke.py",
    "script/run_macos_packaged_app_state_recovery_smoke.py",
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
ANDROID_RELEASE_APK_RELATIVE_PATH = Path(
    "apps/android/app/build/outputs/apk/release/app-release-unsigned.apk"
)
ANDROID_RELEASE_APK_METADATA_RELATIVE_PATH = Path(
    "apps/android/app/build/outputs/apk/release/output-metadata.json"
)
ANDROID_RELEASE_AAB_RELATIVE_PATH = Path(
    "apps/android/app/build/outputs/bundle/release/app-release.aab"
)
ANDROID_RELEASE_MAPPING_RELATIVE_PATH = Path(
    "apps/android/app/build/outputs/mapping/release"
)
ANDROID_RELEASE_SDK_DEPENDENCIES_RELATIVE_PATH = Path(
    "apps/android/app/build/outputs/sdk-dependencies/release/"
    "sdkDependencies.txt"
)
ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH = Path(
    "apps/android/app/build/outputs/native-debug-symbols/release/"
    "native-debug-symbols.zip"
)
ANDROID_RELEASE_MERGED_NATIVE_RELATIVE_PATH = Path(
    "apps/android/app/build/intermediates/merged_native_libs/release/"
    "mergeReleaseNativeLibs/out/lib"
)
ANDROID_RELEASE_STRIPPED_NATIVE_RELATIVE_PATH = Path(
    "apps/android/app/build/intermediates/stripped_native_libs/release/"
    "stripReleaseDebugSymbols/out/lib"
)
ANDROID_RELEASE_MAPPING_FILES = (
    "configuration.txt",
    "mapping.prt",
    "mapping.txt",
    "resources.txt",
    "seeds.txt",
    "usage.txt",
)
ANDROID_RELEASE_APK_MAX_MEMBER_COUNT = 4_096
ANDROID_RELEASE_APK_MAX_MEMBER_BYTES = 134_217_728
ANDROID_RELEASE_APK_MAX_TOTAL_UNCOMPRESSED_BYTES = 268_435_456
ANDROID_RELEASE_AAB_MAX_MEMBER_COUNT = 4_096
ANDROID_RELEASE_AAB_MAX_MEMBER_BYTES = 134_217_728
ANDROID_RELEASE_AAB_MAX_TOTAL_UNCOMPRESSED_BYTES = 268_435_456
ANDROID_RELEASE_R8_PRT_MAX_MEMBER_COUNT = 16_384
ANDROID_RELEASE_R8_PRT_MAX_MEMBER_BYTES = 16_777_216
ANDROID_RELEASE_R8_PRT_MAX_TOTAL_UNCOMPRESSED_BYTES = 268_435_456
ANDROID_RELEASE_MAPPING_MAX_BYTES = {
    "configuration.txt": 4_194_304,
    "mapping.prt": 134_217_728,
    "mapping.txt": 268_435_456,
    "resources.txt": 33_554_432,
    "seeds.txt": 33_554_432,
    "usage.txt": 134_217_728,
}
ANDROID_RELEASE_MAPPING_MAX_TOTAL_BYTES = 536_870_912
MACOS_UNSEALED_OUTPUT_RELATIVE_PATH = Path("dist/unsealed-package-only")
MACOS_UNSEALED_SOURCE_RECEIPT_NAME = "source-receipt.json"
MACOS_UNSEALED_SOURCE_RECEIPT_SCHEMA_VERSION = 1
MACOS_UNSEALED_SOURCE_RECEIPT_MAX_BYTES = 4_096
MACOS_UNSEALED_OUTPUT_CONTRACT = (
    "macos-unsealed-app-dsym-source-bound-v1"
)
MACOS_UNSEALED_APP_FILES = (
    "Contents/Info.plist",
    "Contents/MacOS/AetherLink",
    "Contents/Resources/AppIcon.icns",
    (
        "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
        "Info.plist"
    ),
    *(
        "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
        f"{locale}.lproj/Localizable.strings"
        for locale in ("en", "fr", "ja", "ko", "zh-hans")
    ),
)
MACOS_UNSEALED_DSYM_FILES = (
    "Contents/Info.plist",
    "Contents/Resources/DWARF/AetherLink",
    "Contents/Resources/Relocations/aarch64/AetherLink.yml",
)
MACOS_UNSEALED_APP_INVENTORY = {
    "": {"Contents"},
    "Contents": {"Info.plist", "MacOS", "Resources"},
    "Contents/MacOS": {"AetherLink"},
    "Contents/Resources": {
        "AetherLink_LocalAgentBridge.bundle",
        "AppIcon.icns",
    },
    "Contents/Resources/AetherLink_LocalAgentBridge.bundle": {
        "Info.plist",
        "en.lproj",
        "fr.lproj",
        "ja.lproj",
        "ko.lproj",
        "zh-hans.lproj",
    },
    **{
        (
            "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
            f"{locale}.lproj"
        ): {"Localizable.strings"}
        for locale in ("en", "fr", "ja", "ko", "zh-hans")
    },
}
MACOS_UNSEALED_DSYM_INVENTORY = {
    "": {"Contents"},
    "Contents": {"Info.plist", "Resources"},
    "Contents/Resources": {"DWARF", "Relocations"},
    "Contents/Resources/DWARF": {"AetherLink"},
    "Contents/Resources/Relocations": {"aarch64"},
    "Contents/Resources/Relocations/aarch64": {"AetherLink.yml"},
}
MACOS_UNSEALED_APP_MAX_BYTES = {
    "Contents/Info.plist": 1_048_576,
    "Contents/MacOS/AetherLink": 536_870_912,
    "Contents/Resources/AppIcon.icns": 16_777_216,
    (
        "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
        "Info.plist"
    ): 1_048_576,
    **{
        (
            "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
            f"{locale}.lproj/Localizable.strings"
        ): 4_194_304
        for locale in ("en", "fr", "ja", "ko", "zh-hans")
    },
}
MACOS_UNSEALED_DSYM_MAX_BYTES = {
    "Contents/Info.plist": 1_048_576,
    "Contents/Resources/DWARF/AetherLink": 1_073_741_824,
    "Contents/Resources/Relocations/aarch64/AetherLink.yml": 268_435_456,
}
MACOS_READBACK_TOOL_TIMEOUT_SECONDS = 30
MACOS_READBACK_TOOL_MAX_OUTPUT_BYTES = 1_048_576


class ReleaseArchiveVerificationError(ValueError):
    """Raised when a local release evidence archive does not read back."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise ReleaseArchiveVerificationError(
            f"value is not canonical JSON: {error}"
        ) from error


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseArchiveVerificationError(
                f"JSON object contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def reject_json_constant(value: str) -> object:
    raise ReleaseArchiveVerificationError(
        f"non-finite JSON constant is not allowed: {value}"
    )


def parse_canonical_json(data: bytes, label: str) -> dict[str, object]:
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not data.endswith(b"\n"):
        raise ReleaseArchiveVerificationError(
            f"{label} must be BOM-free UTF-8 with one final LF and no CR"
        )
    try:
        text = data.decode("ascii")
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_json_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ReleaseArchiveVerificationError,
    ) as error:
        if isinstance(error, ReleaseArchiveVerificationError):
            raise
        raise ReleaseArchiveVerificationError(
            f"{label} is invalid canonical JSON: {error}"
        ) from error
    if type(value) is not dict:
        raise ReleaseArchiveVerificationError(f"{label} root must be an object")
    if canonical_json_bytes(value) != data:
        raise ReleaseArchiveVerificationError(
            f"{label} is not in canonical sorted compact form"
        )
    return value


def validate_member_path(member_path: str) -> None:
    try:
        raw = member_path.encode("ascii")
    except UnicodeEncodeError as error:
        raise ReleaseArchiveVerificationError(
            f"archive member path must be ASCII: {member_path!r}"
        ) from error
    if not raw or b"\\" in raw or raw.startswith(b"/"):
        raise ReleaseArchiveVerificationError(
            f"unsafe archive member path: {member_path!r}"
        )
    pure = PurePosixPath(member_path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise ReleaseArchiveVerificationError(
            f"unsafe archive member path: {member_path!r}"
        )


def normalized_mode(file_mode: int) -> int:
    return 0o755 if file_mode & 0o111 else 0o644


def canonicalize_r8_line_artifact(data: bytes, label: str) -> bytes:
    if not data or b"\r" in data or not data.endswith(b"\n"):
        raise ReleaseArchiveVerificationError(
            f"{label} must be nonempty LF-terminated text"
        )
    lines = data[:-1].split(b"\n")
    if (
        not lines
        or any(not line for line in lines)
        or len(lines) != len(set(lines))
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} must contain nonempty unique lines"
        )
    return b"\n".join(sorted(lines)) + b"\n"


def canonicalize_r8_resources(data: bytes, label: str) -> bytes:
    if not data or b"\r" in data or b"\0" in data or not data.endswith(b"\n"):
        raise ReleaseArchiveVerificationError(
            f"{label} must be nonempty LF-terminated ASCII text"
        )
    raw_lines = data[:-1].split(b"\n")
    if not raw_lines or any(not line for line in raw_lines):
        raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
                f"{label} contains a non-printable resource-state byte"
            )
        if line.count(reachable_from) == 1:
            key, reason = line.split(reachable_from, 1)
            if not reason:
                raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
                f"{label} contains an unsupported resource-state line"
            )
        if resource_key_pattern.fullmatch(key) is None:
            raise ReleaseArchiveVerificationError(
                f"{label} contains an invalid resource identity"
            )
        normalized.append(key + suffix)

    if len(normalized) != len(set(normalized)):
        raise ReleaseArchiveVerificationError(
            f"{label} contains duplicate canonical resource states"
        )
    return b"\n".join(sorted(normalized)) + b"\n"


def archive_normalizations_for_build(build_number: int) -> tuple[str, ...]:
    if build_number <= 3:
        return LEGACY_ARCHIVE_NORMALIZATIONS_BUILD_1_TO_3
    if build_number == 4:
        return LEGACY_ARCHIVE_NORMALIZATIONS_BUILD_4
    return ARCHIVE_NORMALIZATIONS


def validate_canonical_r8_configuration(data: bytes, label: str) -> None:
    if not data or b"\0" in data or not data.endswith(b"\n"):
        raise ReleaseArchiveVerificationError(
            f"{label} must be nonempty LF-terminated text without NUL"
        )
    extracted_token = b"(extracted file: "
    opening_prefix = (
        b"# The proguard configuration file for the following section is "
    )
    closing_prefix = b"# End of content from "
    markers = (b"<SOURCE_ROOT>", b"<GRADLE_USER_HOME>")
    marker_counts = {marker: 0 for marker in markers}
    active_pair: tuple[bytes, bytes] | None = None
    pair_count = 0
    for line in data[:-1].split(b"\n"):
        if extracted_token not in line:
            continue
        if (
            b"\r" in line
            or b"\\" in line
            or line.count(extracted_token) != 1
            or not line.endswith(b")")
        ):
            raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
                f"{label} contains an unexpected extracted-file comment"
            )
        if not identity or not identity.endswith(b" "):
            raise ReleaseArchiveVerificationError(
                f"{label} contains an invalid extracted-file identity"
            )
        identity = identity[:-1]
        if not identity or b"\0" in identity or b"\r" in identity:
            raise ReleaseArchiveVerificationError(
                f"{label} contains an invalid extracted-file identity"
            )

        path = extracted[:-1]
        matches = [
            marker
            for marker in markers
            if path.startswith(marker + b"/")
        ]
        if len(matches) != 1:
            raise ReleaseArchiveVerificationError(
                f"{label} contains a noncanonical extracted-file root"
            )
        marker = matches[0]
        suffix = path[len(marker):]
        components = suffix[1:].split(b"/")
        if (
            not suffix.startswith(b"/")
            or not components
            or any(component in (b"", b".", b"..") for component in components)
        ):
            raise ReleaseArchiveVerificationError(
                f"{label} contains a noncanonical extracted-file path"
            )
        pair = (identity, path)
        if is_opening:
            if active_pair is not None:
                raise ReleaseArchiveVerificationError(
                    f"{label} contains nested extracted-file sections"
                )
            active_pair = pair
        else:
            if active_pair != pair:
                raise ReleaseArchiveVerificationError(
                    f"{label} extracted-file section endpoints differ"
                )
            active_pair = None
            pair_count += 1
        marker_counts[marker] += 1

    if active_pair is not None or pair_count == 0:
        raise ReleaseArchiveVerificationError(
            f"{label} contains an incomplete extracted-file section"
        )
    if any(count == 0 for count in marker_counts.values()):
        raise ReleaseArchiveVerificationError(
            f"{label} must reference both canonical extracted-file roots"
        )


def canonicalize_r8_mapping_prt(data: bytes, label: str) -> bytes:
    entries = list(
        read_safe_zip_members(
            data,
            label,
            maximum_members=ANDROID_RELEASE_R8_PRT_MAX_MEMBER_COUNT,
            maximum_member_bytes=ANDROID_RELEASE_R8_PRT_MAX_MEMBER_BYTES,
            maximum_total_uncompressed_bytes=(
                ANDROID_RELEASE_R8_PRT_MAX_TOTAL_UNCOMPRESSED_BYTES
            ),
        ).items()
    )
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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def logical_member_digest(
    members: dict[str, bytes],
    domain: bytes,
) -> str:
    digest = hashlib.sha256()
    digest.update(domain)
    digest.update(len(members).to_bytes(8, "big"))
    for name, payload in sorted(
        members.items(),
        key=lambda item: item[0].encode("ascii"),
    ):
        name_bytes = name.encode("ascii")
        digest.update(len(name_bytes).to_bytes(8, "big"))
        digest.update(name_bytes)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def read_stable_regular_file(
    path: Path,
    label: str,
    *,
    maximum_bytes: int = 1_073_741_824,
    allow_empty: bool = False,
) -> bytes:
    if type(maximum_bytes) is not int or maximum_bytes < 1:
        raise ReleaseArchiveVerificationError(
            f"{label} read limit must be a positive integer"
        )
    try:
        before = path.lstat()
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} cannot be inspected: {error}"
        ) from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise ReleaseArchiveVerificationError(
            f"{label} must be a regular non-symlink file"
        )
    if before.st_size > maximum_bytes:
        raise ReleaseArchiveVerificationError(
            f"{label} exceeds the {maximum_bytes}-byte read limit"
        )
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} cannot be opened without following links: {error}"
        ) from error
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (before.st_dev, before.st_ino)
            != (opened.st_dev, opened.st_ino)
        ):
            raise ReleaseArchiveVerificationError(
                f"{label} changed before it was opened"
            )
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            data = handle.read(maximum_bytes + 1)
            after = os.fstat(handle.fileno())
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} cannot be read: {error}"
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(data) > maximum_bytes:
        raise ReleaseArchiveVerificationError(
            f"{label} exceeds the {maximum_bytes}-byte read limit"
        )
    try:
        final = path.lstat()
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} cannot be inspected after read: {error}"
        ) from error
    identity_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    before_identity = tuple(getattr(before, field) for field in identity_fields)
    opened_identity = tuple(getattr(opened, field) for field in identity_fields)
    after_identity = tuple(getattr(after, field) for field in identity_fields)
    final_identity = tuple(getattr(final, field) for field in identity_fields)
    if (
        before_identity != opened_identity
        or opened_identity != after_identity
        or after_identity != final_identity
        or len(data) != after.st_size
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} changed while it was read"
        )
    if not data and not allow_empty:
        raise ReleaseArchiveVerificationError(f"{label} must not be empty")
    return data


def parse_json_without_duplicate_keys(
    data: bytes,
    label: str,
) -> object:
    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ReleaseArchiveVerificationError(
                    f"{label} contains duplicate JSON key {key!r}"
                )
            result[key] = value
        return result

    def reject_nonstandard_constant(value: str) -> object:
        raise ReleaseArchiveVerificationError(
            f"{label} contains nonstandard JSON constant {value!r}"
        )

    try:
        text = data.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonstandard_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseArchiveVerificationError(
            f"{label} is not valid UTF-8 JSON: {error}"
        ) from error


def require_directory_inventory(
    path: Path,
    expected_names: set[str],
    label: str,
) -> None:
    try:
        status = path.lstat()
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} cannot be inspected: {error}"
        ) from error
    if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
        raise ReleaseArchiveVerificationError(
            f"{label} must be a physical directory"
        )
    try:
        actual_names = {entry.name for entry in path.iterdir()}
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} cannot be listed: {error}"
        ) from error
    if actual_names != expected_names:
        raise ReleaseArchiveVerificationError(
            f"{label} inventory differs; missing="
            f"{sorted(expected_names - actual_names)}, "
            f"extra={sorted(actual_names - expected_names)}"
        )


def read_exact_physical_tree(
    root: Path,
    *,
    inventory: dict[str, set[str]],
    expected_files: tuple[str, ...],
    maximum_bytes: dict[str, int],
    executable_files: set[str],
    maximum_total_bytes: int,
    digest_domain: bytes,
    label: str,
) -> tuple[dict[str, bytes], dict[str, int], dict[str, object]]:
    if set(expected_files) != set(maximum_bytes):
        raise ReleaseArchiveVerificationError(
            f"{label} internal file-limit contract differs"
        )
    if type(maximum_total_bytes) is not int or maximum_total_bytes < 1:
        raise ReleaseArchiveVerificationError(
            f"{label} total read limit must be a positive integer"
        )
    for relative, expected_names in inventory.items():
        require_directory_inventory(
            root / relative if relative else root,
            expected_names,
            f"{label} directory {relative or '.'}",
        )

    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    total_size = 0
    for relative in expected_files:
        path = root / relative
        data = read_stable_regular_file(
            path,
            f"{label} file {relative}",
            maximum_bytes=maximum_bytes[relative],
        )
        try:
            status = path.lstat()
        except OSError as error:
            raise ReleaseArchiveVerificationError(
                f"{label} file mode cannot be inspected for {relative}: "
                f"{error}"
            ) from error
        mode = normalized_mode(status.st_mode)
        expected_mode = 0o755 if relative in executable_files else 0o644
        if mode != expected_mode:
            raise ReleaseArchiveVerificationError(
                f"{label} normalized mode differs for {relative}: "
                f"{mode:04o} != {expected_mode:04o}"
            )
        total_size += len(data)
        if total_size > maximum_total_bytes:
            raise ReleaseArchiveVerificationError(
                f"{label} exceeds the {maximum_total_bytes}-byte total "
                "read limit"
            )
        files[relative] = data
        modes[relative] = mode

    for relative, expected_names in inventory.items():
        require_directory_inventory(
            root / relative if relative else root,
            expected_names,
            f"{label} directory {relative or '.'} after read",
        )

    digest_members = {
        relative: f"{modes[relative]:04o}\0".encode("ascii") + data
        for relative, data in files.items()
    }
    return files, modes, {
        "fileCount": len(files),
        "sha256": logical_member_digest(digest_members, digest_domain),
        "size": total_size,
    }


def parse_exact_plist_dictionary(
    data: bytes,
    *,
    expected_keys: set[str],
    label: str,
) -> dict[str, object]:
    if b"\r" in data or not data.startswith(b"<?xml"):
        raise ReleaseArchiveVerificationError(
            f"{label} must be an XML plist with LF line endings"
        )
    try:
        xml_root = ET.fromstring(data)
        value = plistlib.loads(data)
    except (ET.ParseError, plistlib.InvalidFileException, ValueError) as error:
        raise ReleaseArchiveVerificationError(
            f"{label} is invalid: {error}"
        ) from error
    if xml_root.tag != "plist" or len(xml_root) != 1 or xml_root[0].tag != "dict":
        raise ReleaseArchiveVerificationError(
            f"{label} must contain one top-level dictionary"
        )
    children = list(xml_root[0])
    if len(children) % 2 != 0:
        raise ReleaseArchiveVerificationError(
            f"{label} dictionary key/value sequence is incomplete"
        )
    keys: list[str] = []
    for index in range(0, len(children), 2):
        key = children[index]
        if key.tag != "key" or key.text is None:
            raise ReleaseArchiveVerificationError(
                f"{label} dictionary contains a non-key entry"
            )
        keys.append(key.text)
    if len(keys) != len(set(keys)):
        raise ReleaseArchiveVerificationError(
            f"{label} contains a duplicate dictionary key"
        )
    if type(value) is not dict:
        raise ReleaseArchiveVerificationError(
            f"{label} top-level value must be a dictionary"
        )
    require_exact_keys(value, expected_keys, label)
    if set(keys) != expected_keys:
        raise ReleaseArchiveVerificationError(
            f"{label} XML key set differs from its parsed dictionary"
        )
    return value


def materialize_exact_tree(
    root: Path,
    files: dict[str, bytes],
    modes: dict[str, int],
) -> None:
    for relative, data in files.items():
        target = root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(modes[relative])


def require_exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ReleaseArchiveVerificationError(f"{label} must be an integer")
    return value


def require_string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ReleaseArchiveVerificationError(f"{label} must be a string")
    return value


def require_exact_keys(
    value: dict[str, object],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise ReleaseArchiveVerificationError(
            f"{label} field set differs; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def expected_android_manifest_keys(build_number: int) -> set[str]:
    if type(build_number) is not int or build_number < 1:
        raise ReleaseArchiveVerificationError(
            "Android manifest build number is invalid"
        )
    keys = {
        "abis",
        "applicationId",
        "bundleManifestReadback",
        "mappingEmbeddedByteIdentical",
        "minSdk",
        "nativeLibraries",
        "nativeSymbols",
        "signatureState",
        "targetSdk",
        "versionCode",
        "versionName",
    }
    if build_number >= 11:
        keys.add("bundleStructureValidation")
    if build_number >= ANDROID_BACKUP_POLICY_BUILD:
        keys.add("apkManifestReadback")
    if build_number >= ANDROID_ENTRY_POINT_TOPOLOGY_BUILD:
        keys.add("entryPointTopology")
    if build_number >= ANDROID_APPLICATION_SHELL_BUILD:
        keys.add("applicationShell")
    return keys


def verify_android_application_shell_claim(
    value: object,
) -> dict[str, object]:
    if type(value) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android application-shell claim must be an object"
        )
    require_exact_keys(
        value,
        {
            "localeConfigLocales",
            "localizedString",
            "manifestResources",
        },
        "platforms.android.applicationShell",
    )

    manifest_resources = value.get("manifestResources")
    if type(manifest_resources) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android application-shell manifestResources must be an object"
        )
    require_exact_keys(
        manifest_resources,
        set(ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES),
        "platforms.android.applicationShell.manifestResources",
    )
    for name, expected in (
        ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES.items()
    ):
        actual = manifest_resources.get(name)
        if type(actual) is not str or actual != expected:
            raise ReleaseArchiveVerificationError(
                "Android application-shell manifest resource differs "
                f"for {name}"
            )

    locales = value.get("localeConfigLocales")
    if (
        type(locales) is not list
        or any(type(locale) is not str for locale in locales)
        or locales != list(ANDROID_LOCALE_CONFIG_LOCALES)
    ):
        raise ReleaseArchiveVerificationError(
            "Android application-shell localeConfigLocales differ "
            "from the V1 contract"
        )

    localized_string = value.get("localizedString")
    if type(localized_string) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android application-shell localizedString must be an object"
        )
    require_exact_keys(
        localized_string,
        {"resource", "values"},
        "platforms.android.applicationShell.localizedString",
    )
    if (
        type(localized_string.get("resource")) is not str
        or localized_string["resource"]
        != ANDROID_LOCALIZED_STRING_RESOURCE
    ):
        raise ReleaseArchiveVerificationError(
            "Android application-shell localized resource differs "
            "from the V1 contract"
        )
    values = localized_string.get("values")
    if type(values) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android application-shell localized values must be an object"
        )
    require_exact_keys(
        values,
        set(ANDROID_LOCALIZED_STRING_VALUES),
        "platforms.android.applicationShell.localizedString.values",
    )
    for locale, expected in ANDROID_LOCALIZED_STRING_VALUES.items():
        actual = values.get(locale)
        if type(actual) is not str or actual != expected:
            raise ReleaseArchiveVerificationError(
                "Android application-shell localized value differs "
                f"for {locale}"
            )
    return value


def verify_android_entry_point_topology_claim(
    value: object,
) -> dict[str, object]:
    if type(value) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android entry-point topology claim must be an object"
        )
    require_exact_keys(
        value,
        {"activity", "deepLink", "launcher", "share"},
        "platforms.android.entryPointTopology",
    )
    expected_fixed_sections = {
        "activity": {
            "documentLaunchMode": "never",
            "exported": True,
            "launchMode": "singleTask",
            "name": ANDROID_MAIN_ACTIVITY,
        },
        "deepLink": {
            "action": "android.intent.action.VIEW",
            "categories": [
                "android.intent.category.BROWSABLE",
                "android.intent.category.DEFAULT",
            ],
            "host": "pair",
            "scheme": "aetherlink",
        },
        "launcher": {
            "action": "android.intent.action.MAIN",
            "category": "android.intent.category.LAUNCHER",
        },
    }
    for section_name, expected in expected_fixed_sections.items():
        actual = value.get(section_name)
        if type(actual) is not dict:
            raise ReleaseArchiveVerificationError(
                f"Android entry-point {section_name} must be an object"
            )
        require_exact_keys(
            actual,
            set(expected),
            f"platforms.android.entryPointTopology.{section_name}",
        )
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if (
                type(actual_value) is not type(expected_value)
                or actual_value != expected_value
            ):
                raise ReleaseArchiveVerificationError(
                    "Android entry-point topology differs for "
                    f"{section_name}.{key}"
                )

    share = value.get("share")
    if type(share) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android entry-point share claim must be an object"
        )
    require_exact_keys(
        share,
        {"actions", "category", "mimeTypes"},
        "platforms.android.entryPointTopology.share",
    )
    if (
        type(share.get("actions")) is not list
        or share["actions"]
        != [
            "android.intent.action.SEND",
            "android.intent.action.SEND_MULTIPLE",
        ]
        or any(type(action) is not str for action in share["actions"])
        or type(share.get("category")) is not str
        or share["category"] != "android.intent.category.DEFAULT"
    ):
        raise ReleaseArchiveVerificationError(
            "Android entry-point share action/category claim differs"
        )
    mime_types = share.get("mimeTypes")
    if (
        type(mime_types) is not list
        or any(type(mime_type) is not str for mime_type in mime_types)
        or mime_types != sorted(mime_types)
        or len(mime_types) != len(set(mime_types))
        or len(mime_types) != ANDROID_SHARE_MIME_TYPE_COUNT
        or hashlib.sha256(canonical_json_bytes(mime_types)).hexdigest()
        != ANDROID_SHARE_MIME_TYPES_CANONICAL_SHA256
    ):
        raise ReleaseArchiveVerificationError(
            "Android entry-point share MIME claim differs from V1"
        )
    return value


def verify_bundle_structure_validation_claim(
    android: dict[str, object],
    build_number: int,
) -> None:
    if type(build_number) is not int or build_number < 1:
        raise ReleaseArchiveVerificationError(
            "Android bundle validation build number is invalid"
        )
    if build_number <= 10:
        if "bundleStructureValidation" in android:
            raise ReleaseArchiveVerificationError(
                "historical Android manifest has a future validation claim"
            )
        return
    claim = android.get("bundleStructureValidation")
    if type(claim) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android AAB structure validation claim is missing"
        )
    require_exact_keys(
        claim,
        {"member", "moduleSet", "status", "tool"},
        "platforms.android.bundleStructureValidation",
    )
    if claim != {
        "member": "android/bundle/app-release.aab",
        "moduleSet": ["base"],
        "status": "passed",
        "tool": "bundletool validate",
    }:
        raise ReleaseArchiveVerificationError(
            "Android AAB structure validation claim is not canonical"
        )


def run_text(command: list[str], cwd: Path) -> str:
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
            cwd=cwd,
            capture_output=True,
            env=environment,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveVerificationError(
            f"readback command failed: {command!r}: {error}"
        ) from error
    return "\n".join(
        line.rstrip() for line in (result.stdout + result.stderr).splitlines()
    ).strip()


def run_macos_readback_tool(command: list[str], cwd: Path) -> str:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            env=environment,
            check=False,
            timeout=MACOS_READBACK_TOOL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ReleaseArchiveVerificationError(
            "macOS build-output readback command timed out after "
            f"{MACOS_READBACK_TOOL_TIMEOUT_SECONDS} seconds: {command!r}"
        ) from error
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"macOS build-output readback command failed to start: "
            f"{command!r}: {error}"
        ) from error
    output = result.stdout + result.stderr
    if len(output) > MACOS_READBACK_TOOL_MAX_OUTPUT_BYTES:
        raise ReleaseArchiveVerificationError(
            "macOS build-output readback command exceeded the "
            f"{MACOS_READBACK_TOOL_MAX_OUTPUT_BYTES}-byte output limit"
        )
    if result.returncode != 0:
        raise ReleaseArchiveVerificationError(
            "macOS build-output readback command failed with exit "
            f"{result.returncode}: {command!r}"
        )
    try:
        text = output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReleaseArchiveVerificationError(
            "macOS build-output readback command emitted non-UTF-8 output"
        ) from error
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def run_aapt2_dump(command: list[str], root: Path = ROOT) -> str:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            env=environment,
            text=True,
            check=True,
            timeout=AAPT2_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ReleaseArchiveVerificationError(
            "aapt2 APK manifest readback timed out after "
            f"{AAPT2_TIMEOUT_SECONDS} seconds"
        ) from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveVerificationError(
            f"aapt2 APK manifest readback failed: {command!r}: {error}"
        ) from error
    if result.stderr:
        raise ReleaseArchiveVerificationError(
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
        raise ReleaseArchiveVerificationError(
            f"{label} must be nonempty BOM-free ASCII/LF text"
        )
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} must contain only ASCII"
        ) from error
    expected_header = [
        "# This is a Gradle generated file for dependency locking.",
        "# Manual edits can break the build and are not advised.",
        "# This file is expected to be part of source control.",
    ]
    if lines[:3] != expected_header or len(lines) < 4:
        raise ReleaseArchiveVerificationError(
            f"{label} has an unexpected Gradle lock header"
        )
    module_keys: list[str] = []
    empty_configurations: list[str] = []
    all_configurations: set[str] = set()
    for line in lines[3:]:
        if not line or line.startswith("#") or line.count("=") != 1:
            raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
                f"{label} contains noncanonical configuration names"
        )
        if module == "empty":
            if line != lines[-1]:
                raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
                f"{label} contains a malformed module lock"
            )
        module_keys.append(module)
        all_configurations.update(configurations)
    if module_keys != sorted(set(module_keys)):
        raise ReleaseArchiveVerificationError(
            f"{label} module locks must be strictly sorted and unique"
        )
    if not module_keys and not empty_configurations:
        raise ReleaseArchiveVerificationError(
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
        raise ReleaseArchiveVerificationError(
            f"SwiftPM package readback failed: {error}"
        ) from error
    if result.stderr.strip():
        raise ReleaseArchiveVerificationError(
            "SwiftPM package readback emitted unexpected standard error"
        )
    try:
        package = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseArchiveVerificationError(
            f"SwiftPM package readback is invalid JSON: {error}"
        ) from error
    if type(package) is not dict or package.get("name") != "AetherLink":
        raise ReleaseArchiveVerificationError(
            "SwiftPM package readback has an unexpected identity"
        )
    dependencies = package.get("dependencies")
    if type(dependencies) is not list:
        raise ReleaseArchiveVerificationError(
            "SwiftPM package dependencies must be an array"
        )
    return package


def dependency_locking_metadata(
    root: Path = ROOT,
) -> dict[str, object]:
    lock_records: list[dict[str, object]] = []
    for relative in GRADLE_LOCK_PATHS:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ReleaseArchiveVerificationError(
                f"dependency lock is missing or not regular: {relative}"
            )
        data = path.read_bytes()
        shape = parse_gradle_lockfile(data, relative)
        lock_records.append(
            {
                **shape,
                "path": relative,
                "sha256": sha256(data),
                "size": len(data),
            }
        )

    package = swift_package_dump(root)
    dependencies = package["dependencies"]
    assert isinstance(dependencies, list)
    package_resolved = root / "Package.resolved"
    if dependencies:
        if package_resolved.is_symlink() or not package_resolved.is_file():
            raise ReleaseArchiveVerificationError(
                "SwiftPM external dependencies require Package.resolved"
            )
        resolved_data = package_resolved.read_bytes()
        package_resolved_record: dict[str, object] | None = {
            "path": "Package.resolved",
            "sha256": sha256(resolved_data),
            "size": len(resolved_data),
        }
        resolved_status = "required-external-dependencies-locked"
    else:
        if package_resolved.exists() or package_resolved.is_symlink():
            raise ReleaseArchiveVerificationError(
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
    raise ReleaseArchiveVerificationError(
        "cannot locate a Java executable for bundletool readback"
    )


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
        root,
    )
    lines = output.splitlines()
    if (
        len(lines) != 1
        or not lines[0].startswith(BUNDLETOOL_CLASSPATH_MARKER)
    ):
        raise ReleaseArchiveVerificationError(
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
        raise ReleaseArchiveVerificationError(
            "Gradle emitted an invalid bundletool runtime classpath"
        )
    return classpath


def run_bundletool(
    arguments: list[str],
    *,
    root: Path = ROOT,
) -> str:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C.UTF-8"
    try:
        result = subprocess.run(
            [
                str(java_executable()),
                "-Dfile.encoding=UTF-8",
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
        raise ReleaseArchiveVerificationError(
            f"bundletool readback command could not start: {error}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ReleaseArchiveVerificationError(
            "bundletool readback command timed out after "
            f"{BUNDLETOOL_TIMEOUT_SECONDS} seconds: {arguments[0]}"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()[-4_000:]
        raise ReleaseArchiveVerificationError(
            "bundletool readback command failed "
            f"({error.returncode}): {arguments[0]}"
            + (f"\n{detail}" if detail else "")
        ) from error
    if result.stderr.strip():
        raise ReleaseArchiveVerificationError(
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
        raise ReleaseArchiveVerificationError(
            "bundletool validate readback has an unexpected header"
        )
    feature_modules = [
        line.removeprefix("\tFeature module: ")
        for line in lines[3:]
        if line.startswith("\tFeature module: ")
    ]
    if feature_modules != ["base"]:
        raise ReleaseArchiveVerificationError(
            "bundletool validate readback must contain only the base module"
        )


def _bundletool_manifest_node(
    element: ET.Element,
) -> dict[str, object]:
    android_prefix = f"{{{ANDROID_XML_NAMESPACE}}}"
    attributes: dict[str, object] = {}
    for raw_name, value in element.attrib.items():
        if raw_name.startswith(android_prefix):
            name = raw_name.removeprefix(android_prefix)
        elif raw_name.startswith("{"):
            name = raw_name
        else:
            name = f"unqualified:{raw_name}"
        if name in attributes:
            raise ReleaseArchiveVerificationError(
                "bundletool manifest has duplicate normalized attributes"
            )
        attributes[name] = value
    return {
        "attributes": attributes,
        "children": [
            _bundletool_manifest_node(child)
            for child in element
        ],
        "name": element.tag,
    }


def _manifest_node_parts(
    node: dict[str, object],
    *,
    label: str,
) -> tuple[str, dict[str, object], list[dict[str, object]]]:
    if set(node) != {"attributes", "children", "name"}:
        raise ReleaseArchiveVerificationError(
            f"{label} manifest node has an unexpected shape"
        )
    name = node["name"]
    attributes = node["attributes"]
    children = node["children"]
    if (
        type(name) is not str
        or type(attributes) is not dict
        or type(children) is not list
        or any(type(child) is not dict for child in children)
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} manifest node has invalid field types"
        )
    return name, attributes, children


def _android_entry_point_topology(
    application: dict[str, object],
) -> dict[str, object]:
    application_name, _, application_children = _manifest_node_parts(
        application,
        label="application",
    )
    if application_name != "application":
        raise ReleaseArchiveVerificationError(
            "entry-point topology input must be an application element"
        )
    if any(
        _manifest_node_parts(child, label="application child")[0]
        == "activity-alias"
        for child in application_children
    ):
        raise ReleaseArchiveVerificationError(
            "Android V1 entry-point topology must not contain activity aliases"
        )

    target_activities: list[dict[str, object]] = []
    for child in application_children:
        child_name, child_attributes, _ = _manifest_node_parts(
            child,
            label="application child",
        )
        if (
            child_name == "activity"
            and child_attributes.get("name") == ANDROID_MAIN_ACTIVITY
        ):
            target_activities.append(child)
    if len(target_activities) != 1:
        raise ReleaseArchiveVerificationError(
            "Android V1 manifest must contain exactly one MainActivity"
        )

    _, activity_attributes, activity_children = _manifest_node_parts(
        target_activities[0],
        label="MainActivity",
    )
    if set(activity_attributes) != {
        "documentLaunchMode",
        "exported",
        "launchMode",
        "name",
    }:
        raise ReleaseArchiveVerificationError(
            "Android MainActivity attributes differ from the V1 contract"
        )
    if activity_attributes["name"] != ANDROID_MAIN_ACTIVITY:
        raise ReleaseArchiveVerificationError(
            "Android MainActivity name differs from the V1 contract"
        )
    exported = activity_attributes["exported"]
    if not (
        (type(exported) is bool and exported is True)
        or (type(exported) is str and exported == "true")
    ):
        raise ReleaseArchiveVerificationError(
            "Android MainActivity exported must be exactly true"
        )
    launch_mode = activity_attributes["launchMode"]
    if not (
        (type(launch_mode) is int and launch_mode == 2)
        or (type(launch_mode) is str and launch_mode == "2")
    ):
        raise ReleaseArchiveVerificationError(
            "Android MainActivity launchMode must compile as singleTask"
        )
    document_launch_mode = activity_attributes["documentLaunchMode"]
    if not (
        (type(document_launch_mode) is int and document_launch_mode == 3)
        or (
            type(document_launch_mode) is str
            and document_launch_mode == "3"
        )
    ):
        raise ReleaseArchiveVerificationError(
            "Android MainActivity documentLaunchMode must compile as never"
        )
    if len(activity_children) != 4:
        raise ReleaseArchiveVerificationError(
            "Android MainActivity must contain exactly four intent filters"
        )

    filters: dict[str, dict[str, object]] = {}
    for intent_filter in activity_children:
        filter_name, filter_attributes, filter_children = (
            _manifest_node_parts(
                intent_filter,
                label="MainActivity child",
            )
        )
        if filter_name != "intent-filter" or filter_attributes:
            raise ReleaseArchiveVerificationError(
                "Android MainActivity may contain only un-attributed "
                "intent-filter children"
            )
        actions: list[str] = []
        categories: list[str] = []
        data: list[dict[str, str]] = []
        for child in filter_children:
            child_name, child_attributes, child_children = (
                _manifest_node_parts(
                    child,
                    label="intent-filter child",
                )
            )
            if child_children:
                raise ReleaseArchiveVerificationError(
                    "Android intent-filter leaf contains nested elements"
                )
            if child_name in ("action", "category"):
                if (
                    set(child_attributes) != {"name"}
                    or type(child_attributes["name"]) is not str
                    or not child_attributes["name"]
                ):
                    raise ReleaseArchiveVerificationError(
                        f"Android {child_name} has invalid attributes"
                    )
                if child_name == "action":
                    actions.append(child_attributes["name"])
                else:
                    categories.append(child_attributes["name"])
                continue
            if child_name == "data":
                if (
                    not child_attributes
                    or any(
                        type(key) is not str
                        or type(value) is not str
                        or not value
                        for key, value in child_attributes.items()
                    )
                ):
                    raise ReleaseArchiveVerificationError(
                        "Android intent-filter data has invalid attributes"
                    )
                data.append(dict(child_attributes))
                continue
            raise ReleaseArchiveVerificationError(
                "Android intent-filter contains an unexpected child"
            )
        if len(actions) != 1 or len(set(categories)) != len(categories):
            raise ReleaseArchiveVerificationError(
                "Android intent-filter action/category cardinality is invalid"
            )
        action = actions[0]
        if action in filters:
            raise ReleaseArchiveVerificationError(
                "Android MainActivity contains a duplicate action filter"
            )
        encoded_data = [
            canonical_json_bytes(record)
            for record in data
        ]
        if len(encoded_data) != len(set(encoded_data)):
            raise ReleaseArchiveVerificationError(
                "Android intent-filter contains duplicate data records"
            )
        filters[action] = {
            "categories": sorted(categories),
            "data": data,
        }

    launcher_action = "android.intent.action.MAIN"
    view_action = "android.intent.action.VIEW"
    send_action = "android.intent.action.SEND"
    send_multiple_action = "android.intent.action.SEND_MULTIPLE"
    if set(filters) != {
        launcher_action,
        view_action,
        send_action,
        send_multiple_action,
    }:
        raise ReleaseArchiveVerificationError(
            "Android MainActivity action set differs from the V1 contract"
        )
    if filters[launcher_action] != {
        "categories": ["android.intent.category.LAUNCHER"],
        "data": [],
    }:
        raise ReleaseArchiveVerificationError(
            "Android launcher filter differs from the V1 contract"
        )
    if filters[view_action] != {
        "categories": [
            "android.intent.category.BROWSABLE",
            "android.intent.category.DEFAULT",
        ],
        "data": [{"host": "pair", "scheme": "aetherlink"}],
    }:
        raise ReleaseArchiveVerificationError(
            "Android pairing deep-link filter differs from the V1 contract"
        )

    share_mime_types: dict[str, list[str]] = {}
    for action in (send_action, send_multiple_action):
        share_filter = filters[action]
        if share_filter["categories"] != [
            "android.intent.category.DEFAULT"
        ]:
            raise ReleaseArchiveVerificationError(
                "Android share filter category differs from the V1 contract"
            )
        records = share_filter["data"]
        assert isinstance(records, list)
        mime_types: list[str] = []
        for record in records:
            if (
                type(record) is not dict
                or set(record) != {"mimeType"}
                or type(record["mimeType"]) is not str
            ):
                raise ReleaseArchiveVerificationError(
                    "Android share filter data must contain only MIME types"
                )
            mime_types.append(record["mimeType"])
        if len(mime_types) != len(set(mime_types)):
            raise ReleaseArchiveVerificationError(
                "Android share filter contains duplicate MIME types"
            )
        ordered_mime_types = sorted(mime_types)
        if (
            len(ordered_mime_types) != ANDROID_SHARE_MIME_TYPE_COUNT
            or hashlib.sha256(
                canonical_json_bytes(ordered_mime_types)
            ).hexdigest()
            != ANDROID_SHARE_MIME_TYPES_CANONICAL_SHA256
        ):
            raise ReleaseArchiveVerificationError(
                "Android share MIME set differs from the V1 contract"
            )
        share_mime_types[action] = ordered_mime_types
    if share_mime_types[send_action] != share_mime_types[
        send_multiple_action
    ]:
        raise ReleaseArchiveVerificationError(
            "Android single and multiple share MIME sets differ"
        )

    return {
        "activity": {
            "documentLaunchMode": "never",
            "exported": True,
            "launchMode": "singleTask",
            "name": ANDROID_MAIN_ACTIVITY,
        },
        "deepLink": {
            "action": view_action,
            "categories": [
                "android.intent.category.BROWSABLE",
                "android.intent.category.DEFAULT",
            ],
            "host": "pair",
            "scheme": "aetherlink",
        },
        "launcher": {
            "action": launcher_action,
            "category": "android.intent.category.LAUNCHER",
        },
        "share": {
            "actions": [
                send_action,
                send_multiple_action,
            ],
            "category": "android.intent.category.DEFAULT",
            "mimeTypes": share_mime_types[send_action],
        },
    }


def parse_aapt2_entry_point_topology(
    output: str,
) -> dict[str, object]:
    roots: list[dict[str, object]] = []
    stack: list[tuple[int, dict[str, object]]] = []
    element_pattern = re.compile(
        r"^( *)E: ([a-z][a-z0-9-]*) \(line=[1-9][0-9]*\)$"
    )
    attribute_pattern = re.compile(
        r"^( *)A: "
        r"(?:(http://schemas\.android\.com/apk/res/android):)?"
        r"([A-Za-z][A-Za-z0-9]*)"
        r"(?:\(0x[0-9a-f]{8}\))?=(.*)$"
    )
    namespace_pattern = re.compile(
        r"^N: [A-Za-z][A-Za-z0-9_-]*="
        r"[^ ]+ \(line=[1-9][0-9]*\)$"
    )
    for line in output.splitlines():
        if not line or namespace_pattern.fullmatch(line) is not None:
            continue
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
                    raise ReleaseArchiveVerificationError(
                        "aapt2 Android manifest has invalid nesting"
                    )
                parent_children = stack[-1][1]["children"]
                assert isinstance(parent_children, list)
                parent_children.append(node)
            else:
                if roots:
                    raise ReleaseArchiveVerificationError(
                        "aapt2 Android manifest has multiple roots"
                    )
                roots.append(node)
            stack.append((indent, node))
            continue

        attribute_match = attribute_pattern.fullmatch(line)
        if attribute_match is not None:
            indent = len(attribute_match.group(1))
            if not stack or indent != stack[-1][0] + 2:
                raise ReleaseArchiveVerificationError(
                    "aapt2 Android manifest has an unbound attribute"
                )
            name = attribute_match.group(3)
            if attribute_match.group(2) is None:
                name = f"unqualified:{name}"
            encoded_value = attribute_match.group(4)
            quoted = re.fullmatch(
                r'"(.*)" \(Raw: "(.*)"\)',
                encoded_value,
            )
            if quoted is not None:
                if quoted.group(1) != quoted.group(2):
                    raise ReleaseArchiveVerificationError(
                        "aapt2 Android manifest decoded/raw values differ"
                    )
                value: object = quoted.group(1)
            elif encoded_value == "true":
                value = True
            elif encoded_value == "false":
                value = False
            elif re.fullmatch(r"[0-9]+", encoded_value) is not None:
                value = int(encoded_value)
            else:
                value = encoded_value
            attributes = stack[-1][1]["attributes"]
            assert isinstance(attributes, dict)
            if name in attributes:
                raise ReleaseArchiveVerificationError(
                    "aapt2 Android manifest has a duplicate attribute"
                )
            attributes[name] = value
            continue
        raise ReleaseArchiveVerificationError(
            "aapt2 Android manifest contains an unrecognized line"
        )

    if len(roots) != 1:
        raise ReleaseArchiveVerificationError(
            "aapt2 Android manifest must contain one root"
        )
    root_name, _, root_children = _manifest_node_parts(
        roots[0],
        label="manifest root",
    )
    if root_name != "manifest":
        raise ReleaseArchiveVerificationError(
            "aapt2 Android manifest root element is unexpected"
        )
    applications = [
        child
        for child in root_children
        if _manifest_node_parts(
            child,
            label="manifest child",
        )[0]
        == "application"
    ]
    if len(applications) != 1:
        raise ReleaseArchiveVerificationError(
            "aapt2 Android manifest must contain one application element"
        )
    return _android_entry_point_topology(applications[0])


def parse_bundletool_localized_string(output: str) -> dict[str, object]:
    lines = output.splitlines()
    if (
        len(lines) != 8
        or lines[0] != "Package 'com.localagentbridge.android':"
        or re.fullmatch(
            r"0x[0-9a-f]{8} - string/status_title",
            lines[1],
        )
        is None
    ):
        raise ReleaseArchiveVerificationError(
            "bundletool localized-string output has an unexpected shape"
        )

    values: dict[str, str] = {}
    config_pattern = re.compile(
        r'^\t(?:(\(default\))|locale: ("(?:[^"\\]|\\.)*")) '
        r'- \[STR\] ("(?:[^"\\]|\\.)*")$'
    )
    for line in lines[2:]:
        match = config_pattern.fullmatch(line)
        if match is None:
            raise ReleaseArchiveVerificationError(
                "bundletool localized-string output contains an invalid config"
            )
        if match.group(1) is not None:
            config = "default"
        else:
            try:
                config = json.loads(match.group(2))
            except json.JSONDecodeError as error:
                raise ReleaseArchiveVerificationError(
                    "bundletool localized-string locale is invalid JSON"
                ) from error
        try:
            value = json.loads(match.group(3))
        except json.JSONDecodeError as error:
            raise ReleaseArchiveVerificationError(
                "bundletool localized-string value is invalid JSON"
            ) from error
        if (
            type(config) is not str
            or type(value) is not str
            or config in values
        ):
            raise ReleaseArchiveVerificationError(
                "bundletool localized-string configs are not unique strings"
            )
        values[config] = value

    if values != ANDROID_LOCALIZED_STRING_VALUES:
        raise ReleaseArchiveVerificationError(
            "bundletool localized-string payload differs from the V1 contract"
        )
    return {
        "resource": ANDROID_LOCALIZED_STRING_RESOURCE,
        "values": values,
    }


def parse_bundletool_language_split_contract(output: str) -> None:
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        raise ReleaseArchiveVerificationError(
            "bundletool config output is invalid JSON"
        ) from error
    if type(value) is not dict:
        raise ReleaseArchiveVerificationError(
            "bundletool config output root must be an object"
        )
    try:
        optimizations = value["optimizations"]
        splits_config = optimizations["splitsConfig"]
        dimensions = splits_config["splitDimension"]
    except (KeyError, TypeError) as error:
        raise ReleaseArchiveVerificationError(
            "bundletool config omits the split-dimension contract"
        ) from error
    if (
        type(optimizations) is not dict
        or type(splits_config) is not dict
        or type(dimensions) is not list
    ):
        raise ReleaseArchiveVerificationError(
            "bundletool split-dimension contract has invalid types"
        )
    language_dimensions = [
        dimension
        for dimension in dimensions
        if type(dimension) is dict
        and dimension.get("value") == "LANGUAGE"
    ]
    if (
        any(type(dimension) is not dict for dimension in dimensions)
        or len(language_dimensions) != 1
        or set(language_dimensions[0]) != {"negate", "value"}
        or language_dimensions[0]["negate"] is not True
    ):
        raise ReleaseArchiveVerificationError(
            "bundletool language splitting must be exactly disabled"
        )


def parse_bundletool_manifest(
    output: str,
    *,
    backup_policy_required: bool = False,
    entry_point_topology_required: bool = False,
    application_shell_required: bool = False,
) -> dict[str, object]:
    if type(backup_policy_required) is not bool:
        raise ReleaseArchiveVerificationError(
            "bundletool backup-policy requirement must be a boolean"
        )
    if type(entry_point_topology_required) is not bool:
        raise ReleaseArchiveVerificationError(
            "bundletool entry-point topology requirement must be a boolean"
        )
    if type(application_shell_required) is not bool:
        raise ReleaseArchiveVerificationError(
            "bundletool application-shell requirement must be a boolean"
        )
    try:
        manifest = ET.fromstring(output)
    except ET.ParseError as error:
        raise ReleaseArchiveVerificationError(
            f"bundletool manifest readback is invalid XML: {error}"
        ) from error
    if manifest.tag != "manifest":
        raise ReleaseArchiveVerificationError(
            "bundletool manifest readback has an unexpected root element"
        )
    uses_sdk = [
        child for child in manifest
        if child.tag == "uses-sdk"
    ]
    if len(uses_sdk) != 1:
        raise ReleaseArchiveVerificationError(
            "bundletool manifest readback must contain one uses-sdk element"
        )
    applications = [
        child for child in manifest
        if child.tag == "application"
    ]
    if len(applications) != 1:
        raise ReleaseArchiveVerificationError(
            "bundletool manifest readback must contain one application element"
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
    application_shell_resources = {
        name: application.get(f"{android_attribute}{name}")
        for name in ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES
    }
    for value, label in (
        (version_code_text, "versionCode"),
        (min_sdk_text, "minSdk"),
        (target_sdk_text, "targetSdk"),
    ):
        if (
            type(value) is not str
            or re.fullmatch(r"[1-9][0-9]*", value) is None
        ):
            raise ReleaseArchiveVerificationError(
                f"bundletool manifest {label} is not a positive decimal"
            )
    if type(application_id) is not str or not application_id:
        raise ReleaseArchiveVerificationError(
            "bundletool manifest package is missing"
        )
    if type(version_name) is not str or not version_name:
        raise ReleaseArchiveVerificationError(
            "bundletool manifest versionName is missing"
        )
    if allow_backup != "false":
        raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
                "bundletool manifest backup-policy references differ "
                "from the V1 contract"
            )
    elif actual_policy_references != (None, None):
        raise ReleaseArchiveVerificationError(
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
    if entry_point_topology_required:
        result["entryPointTopology"] = _android_entry_point_topology(
            _bundletool_manifest_node(application)
        )
    if application_shell_required:
        unexpected_namespaces = [
            attribute
            for attribute in application.attrib
            if (
                attribute.rsplit("}", 1)[-1]
                in ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES
                and not attribute.startswith(f"{{{ANDROID_XML_NAMESPACE}}}")
            )
        ]
        if unexpected_namespaces:
            raise ReleaseArchiveVerificationError(
                "bundletool application-shell resources use an "
                "unexpected namespace"
            )
        if (
            application_shell_resources
            != ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES
        ):
            raise ReleaseArchiveVerificationError(
                "bundletool application-shell resources differ "
                "from the V1 contract"
            )
        result["applicationShell"] = {
            "manifestResources": dict(application_shell_resources),
        }
    return result


def inspect_aab_manifest(
    aab_data: bytes,
    root: Path = ROOT,
    *,
    backup_policy_required: bool = False,
    entry_point_topology_required: bool = False,
    application_shell_required: bool = False,
) -> dict[str, object]:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="aetherlink-release-readback-bundle-",
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
            entry_point_topology_required=(
                entry_point_topology_required
            ),
            application_shell_required=application_shell_required,
        )
        if application_shell_required:
            localized_string = parse_bundletool_localized_string(
                run_bundletool(
                    [
                        "dump",
                        "resources",
                        f"--bundle={temporary_name}",
                        "--resource=string/status_title",
                        "--values",
                    ],
                    root=root,
                )
            )
            parse_bundletool_language_split_contract(
                run_bundletool(
                    [
                        "dump",
                        "config",
                        f"--bundle={temporary_name}",
                    ],
                    root=root,
                )
            )
            direct_shell = parsed_manifest["applicationShell"]
            assert isinstance(direct_shell, dict)
            direct_shell["localizedString"] = localized_string
        if backup_policy_required or application_shell_required:
            packaged_policy = inspect_aab_backup_policy(
                Path(temporary_name),
                root,
                application_shell_required=application_shell_required,
            )
        if backup_policy_required:
            expected_policy = {
                "allowBackup": parsed_manifest["allowBackup"],
                "dataExtractionRules": (
                    parsed_manifest["dataExtractionRules"]
                ),
                "fullBackupContent": (
                    parsed_manifest["fullBackupContent"]
                ),
            }
            actual_policy = {
                name: packaged_policy.get(name)
                for name in expected_policy
            }
            if actual_policy != expected_policy:
                raise ReleaseArchiveVerificationError(
                    "AAB universal-APK backup-policy readback differs "
                    "from the bundle manifest"
                )
        if application_shell_required:
            packaged_shell = packaged_policy.get("applicationShell")
            direct_shell = parsed_manifest["applicationShell"]
            if (
                type(packaged_shell) is not dict
                or type(direct_shell) is not dict
                or {
                    "localizedString": packaged_shell.get(
                        "localizedString"
                    ),
                    "manifestResources": packaged_shell.get(
                        "manifestResources"
                    ),
                }
                != direct_shell
            ):
                raise ReleaseArchiveVerificationError(
                    "AAB direct application-shell readback differs "
                    "from its universal APK"
                )
            parsed_manifest["applicationShell"] = packaged_shell
        return parsed_manifest
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def create_ephemeral_aab_readback_keystore(
    path: Path,
    root: Path = ROOT,
) -> None:
    keytool = java_executable().with_name("keytool")
    if not keytool.is_file() or not os.access(keytool, os.X_OK):
        raise ReleaseArchiveVerificationError(
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
        raise ReleaseArchiveVerificationError(
            "ephemeral AAB readback key generation timed out"
        ) from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveVerificationError(
            "ephemeral AAB readback key generation failed"
        ) from error


def inspect_aab_backup_policy(
    aab_path: Path,
    root: Path = ROOT,
    *,
    application_shell_required: bool = False,
) -> dict[str, object]:
    if type(application_shell_required) is not bool:
        raise ReleaseArchiveVerificationError(
            "AAB application-shell requirement must be a boolean"
        )
    aapt2 = find_android_build_tool("aapt2", root)
    try:
        with tempfile.TemporaryDirectory(
            prefix="aetherlink-release-readback-aab-policy-"
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
                    raise ReleaseArchiveVerificationError(
                        "bundletool readback APKS must contain exactly one "
                        "universal.apk"
                    )
                universal_apk = archive.read("universal.apk")
    except ReleaseArchiveVerificationError:
        raise
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        raise ReleaseArchiveVerificationError(
            "cannot read bundletool universal-APK policy output"
        ) from error
    return inspect_apk_backup_policy(
        universal_apk,
        root,
        application_shell_required=application_shell_required,
    )


def bundletool_version(root: Path = ROOT) -> str:
    version = run_bundletool(["version"], root=root)
    if version != BUNDLETOOL_VERSION:
        raise ReleaseArchiveVerificationError(
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


def find_android_build_tool(name: str, root: Path = ROOT) -> Path:
    sdk_root = android_sdk_root(root)
    path = sdk_root / "build-tools" / ANDROID_BUILD_TOOLS_VERSION / name
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ReleaseArchiveVerificationError(
            f"cannot locate pinned Build Tools {ANDROID_BUILD_TOOLS_VERSION} "
            f"{name} under Android SDK {sdk_root}"
        )
    return path


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
        raise ReleaseArchiveVerificationError(
            "aapt2 badging output has an unexpected shape"
        )
    package_name, version_code_text, version_name = package_matches[0]
    for value, label in (
        (version_code_text, "versionCode"),
        (sdk_matches[0], "minSdk"),
        (target_matches[0], "targetSdk"),
    ):
        if re.fullmatch(r"[1-9][0-9]*", value) is None:
            raise ReleaseArchiveVerificationError(
                f"aapt2 {label} is not a positive decimal"
            )
    native_abis = re.findall(r"'([^']+)'", native_matches[0])
    if not native_abis or len(native_abis) != len(set(native_abis)):
        raise ReleaseArchiveVerificationError(
            "aapt2 native-code ABI list is invalid"
        )
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
        raise ReleaseArchiveVerificationError(
            "aapt2 APK manifest output must contain exactly one manifest root"
        )
    if len(application_entries) != 1:
        raise ReleaseArchiveVerificationError(
            "aapt2 APK manifest must contain exactly one application element"
        )

    manifest_index, manifest_indent = manifest_entries[0]
    application_index, application_indent = application_entries[0]
    if (
        application_index <= manifest_index
        or application_indent != manifest_indent + 4
    ):
        raise ReleaseArchiveVerificationError(
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
        raise ReleaseArchiveVerificationError(
            "aapt2 APK manifest backup-policy attributes differ "
            "from the V1 contract"
        )
    if attributes["allowBackup"] != ["false"]:
        raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
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
            raise ReleaseArchiveVerificationError(
                "aapt2 APK manifest backup-policy reference "
                "is not a compiled resource ID"
            )
        resource_name = resources.get(match.group(1))
        if resource_name != expected_resource_name:
            raise ReleaseArchiveVerificationError(
                "aapt2 APK manifest backup-policy resource mapping differs "
                "from the V1 contract"
            )
        resolved[attribute_name] = f"@xml/{resource_name}"

    return {
        "allowBackup": False,
        "dataExtractionRules": resolved["dataExtractionRules"],
        "fullBackupContent": resolved["fullBackupContent"],
    }


def parse_aapt2_application_shell_manifest(
    xmltree_output: str,
    resources_output: str,
) -> dict[str, str]:
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
        application_match = re.fullmatch(
            r"( *)E: application \(line=[1-9][0-9]*\)",
            line,
        )
        if application_match is not None:
            application_entries.append(
                (index, len(application_match.group(1)))
            )
    if len(manifest_entries) != 1 or len(application_entries) != 1:
        raise ReleaseArchiveVerificationError(
            "aapt2 application-shell manifest must contain one "
            "manifest and one application"
        )
    manifest_index, manifest_indent = manifest_entries[0]
    application_index, application_indent = application_entries[0]
    if (
        application_index <= manifest_index
        or application_indent != manifest_indent + 4
    ):
        raise ReleaseArchiveVerificationError(
            "aapt2 application-shell application is not a direct child"
        )

    attribute_names = tuple(
        ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES
    )
    attribute_pattern = re.compile(
        r"^"
        + re.escape(" " * (application_indent + 2))
        + r"A: "
        + re.escape(ANDROID_XML_NAMESPACE)
        + r":("
        + "|".join(re.escape(name) for name in attribute_names)
        + r")\(0x[0-9a-f]{8}\)=(@0x[0-9a-f]{8})$"
    )
    selected_attribute_pattern = re.compile(
        r"^"
        + re.escape(" " * (application_indent + 2))
        + r"A: (?:(?:"
        + re.escape(ANDROID_XML_NAMESPACE)
        + r"):)?("
        + "|".join(re.escape(name) for name in attribute_names)
        + r")(?:\(0x[0-9a-f]{8}\))?=.*$"
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
        elif selected_attribute_pattern.fullmatch(line) is not None:
            raise ReleaseArchiveVerificationError(
                "aapt2 application-shell attribute is malformed "
                "or unqualified"
            )
    if (
        set(attributes) != set(attribute_names)
        or any(len(values) != 1 for values in attributes.values())
    ):
        raise ReleaseArchiveVerificationError(
            "aapt2 application-shell attributes differ from the V1 contract"
        )

    resource_pattern = re.compile(
        r"^\s*resource (0x[0-9a-f]{8}) "
        r"([a-z][a-z0-9_]*)/([A-Za-z][A-Za-z0-9_]*)$"
    )
    resources_by_id: dict[str, str] = {}
    ids_by_resource: dict[str, list[str]] = {}
    for line in resources_output.splitlines():
        match = resource_pattern.fullmatch(line)
        if match is None:
            continue
        resource_id = match.group(1)
        resource = f"{match.group(2)}/{match.group(3)}"
        if resource_id in resources_by_id:
            raise ReleaseArchiveVerificationError(
                "aapt2 application-shell resources contain a duplicate ID"
            )
        resources_by_id[resource_id] = resource
        ids_by_resource.setdefault(resource, []).append(resource_id)

    resolved: dict[str, str] = {}
    for attribute_name, expected_reference in (
        ANDROID_APPLICATION_SHELL_MANIFEST_RESOURCES.items()
    ):
        expected_resource = expected_reference.removeprefix("@")
        if len(ids_by_resource.get(expected_resource, [])) != 1:
            raise ReleaseArchiveVerificationError(
                "aapt2 application-shell resource name is not unique"
            )
        resource_id = attributes[attribute_name][0].removeprefix("@")
        if resources_by_id.get(resource_id) != expected_resource:
            raise ReleaseArchiveVerificationError(
                "aapt2 application-shell resource mapping differs "
                "from the V1 contract"
            )
        resolved[attribute_name] = expected_reference
    return resolved


def parse_aapt2_locale_config(output: str) -> list[str]:
    lines = output.splitlines()
    if (
        len(lines) != 2 + 2 * len(ANDROID_LOCALE_CONFIG_LOCALES)
        or re.fullmatch(
            r"N: android="
            + re.escape(ANDROID_XML_NAMESPACE)
            + r" \(line=[1-9][0-9]*\)",
            lines[0] if lines else "",
        )
        is None
        or re.fullmatch(
            r"  E: locale-config \(line=[1-9][0-9]*\)",
            lines[1] if len(lines) > 1 else "",
        )
        is None
    ):
        raise ReleaseArchiveVerificationError(
            "aapt2 localeConfig XML has an unexpected document shape"
        )
    locale_pattern = re.compile(
        r'        A: '
        + re.escape(ANDROID_XML_NAMESPACE)
        + r':name\(0x[0-9a-f]{8}\)="([^"]+)" '
        r'\(Raw: "([^"]+)"\)'
    )
    locales: list[str] = []
    for offset in range(2, len(lines), 2):
        if re.fullmatch(
            r"      E: locale \(line=[1-9][0-9]*\)",
            lines[offset],
        ) is None:
            raise ReleaseArchiveVerificationError(
                "aapt2 localeConfig contains an unexpected child"
            )
        match = locale_pattern.fullmatch(lines[offset + 1])
        if match is None or match.group(1) != match.group(2):
            raise ReleaseArchiveVerificationError(
                "aapt2 localeConfig locale name is invalid"
            )
        locales.append(match.group(1))
    if locales != list(ANDROID_LOCALE_CONFIG_LOCALES):
        raise ReleaseArchiveVerificationError(
            "aapt2 localeConfig locales differ from the V1 contract"
        )
    return locales


def parse_aapt2_localized_string(output: str) -> dict[str, object]:
    lines = output.splitlines()
    resource_pattern = re.compile(
        r"^( *)resource 0x[0-9a-f]{8} string/status_title$"
    )
    entries = [
        (index, len(match.group(1)))
        for index, line in enumerate(lines)
        if (match := resource_pattern.fullmatch(line)) is not None
    ]
    if len(entries) != 1:
        raise ReleaseArchiveVerificationError(
            "aapt2 localized-string resource must appear exactly once"
        )
    resource_index, resource_indent = entries[0]
    config_pattern = re.compile(
        r'^( *)\(([^)]*)\) "([^"\r\n]*)"$'
    )
    values: dict[str, str] = {}
    config_names = {
        "": "default",
        "en": "en",
        "fr": "fr",
        "ja": "ja",
        "ko": "ko",
        "zh-rCN": "zh-CN",
    }
    for line in lines[resource_index + 1 :]:
        if not line:
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= resource_indent:
            break
        match = config_pattern.fullmatch(line)
        if match is None:
            raise ReleaseArchiveVerificationError(
                "aapt2 localized-string config has an unsupported shape"
            )
        canonical_config = config_names.get(match.group(2))
        if canonical_config is None or canonical_config in values:
            raise ReleaseArchiveVerificationError(
                "aapt2 localized-string configs differ from the V1 contract"
            )
        values[canonical_config] = match.group(3)
    if values != ANDROID_LOCALIZED_STRING_VALUES:
        raise ReleaseArchiveVerificationError(
            "aapt2 localized-string payload differs from the V1 contract"
        )
    return {
        "resource": ANDROID_LOCALIZED_STRING_RESOURCE,
        "values": values,
    }


def parse_aapt2_xml_resource_paths(
    resources_output: str,
    *,
    application_shell_required: bool = False,
) -> dict[str, str]:
    if type(application_shell_required) is not bool:
        raise ReleaseArchiveVerificationError(
            "APK application-shell resource-path requirement must be a boolean"
        )
    expected_names = {"backup_rules", "data_extraction_rules"}
    if application_shell_required:
        expected_names.add("locales_config")
    resources: dict[str, list[str]] = {}
    active_name: str | None = None
    active_indent = -1
    resource_pattern = re.compile(
        r"^( *)resource 0x[0-9a-f]{8} "
        r"xml/(backup_rules|data_extraction_rules|locales_config)$"
    )
    file_pattern = re.compile(
        r"^( *)\(\) \(file\) "
        r"(res/[A-Za-z0-9_./-]+\.xml) type=XML$"
    )
    for line in resources_output.splitlines():
        resource_match = resource_pattern.fullmatch(line)
        if resource_match is not None:
            selected_name = resource_match.group(2)
            if selected_name not in expected_names:
                active_name = None
                active_indent = -1
                continue
            active_name = selected_name
            active_indent = len(resource_match.group(1))
            if active_name in resources:
                raise ReleaseArchiveVerificationError(
                    "aapt2 APK resources contain a duplicate selected XML "
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
        raise ReleaseArchiveVerificationError(
            "aapt2 APK resources omit a selected XML file path"
        )
    if any(len(paths) != 1 for paths in resources.values()):
        raise ReleaseArchiveVerificationError(
            "aapt2 APK selected XML resources must each resolve to one "
            "default XML file"
        )
    resolved = {name: paths[0] for name, paths in resources.items()}
    if len(set(resolved.values())) != len(resolved):
        raise ReleaseArchiveVerificationError(
            "aapt2 APK selected XML resources share one compiled XML file"
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
                    raise ReleaseArchiveVerificationError(
                        f"aapt2 {label} XML tree has invalid nesting"
                    )
                parent_children = stack[-1][1]["children"]
                assert isinstance(parent_children, list)
                parent_children.append(node)
            else:
                if indent != 0 or roots:
                    raise ReleaseArchiveVerificationError(
                        f"aapt2 {label} XML tree has multiple roots"
                    )
                roots.append(node)
            stack.append((indent, node))
            continue

        attribute_match = attribute_pattern.fullmatch(line)
        if attribute_match is not None:
            indent = len(attribute_match.group(1))
            if not stack or indent != stack[-1][0] + 2:
                raise ReleaseArchiveVerificationError(
                    f"aapt2 {label} XML tree has an unbound attribute"
                )
            name = attribute_match.group(2)
            value = attribute_match.group(3)
            if value != attribute_match.group(4):
                raise ReleaseArchiveVerificationError(
                    f"aapt2 {label} XML tree has mismatched raw attributes"
                )
            attributes = stack[-1][1]["attributes"]
            assert isinstance(attributes, dict)
            if name in attributes:
                raise ReleaseArchiveVerificationError(
                    f"aapt2 {label} XML tree has a duplicate attribute"
                )
            attributes[name] = value
            continue

        raise ReleaseArchiveVerificationError(
            f"aapt2 {label} XML tree contains an unexpected line"
        )

    if len(roots) != 1:
        raise ReleaseArchiveVerificationError(
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
        raise ReleaseArchiveVerificationError(
            "packaged backup_rules XML differs from the V1 exclusion contract"
        )
    if actual_extraction != expected_extraction:
        raise ReleaseArchiveVerificationError(
            "packaged data_extraction_rules XML differs from the V1 "
            "exclusion contract"
        )


def inspect_apk_badging(apk_data: bytes, root: Path = ROOT) -> dict[str, object]:
    aapt2 = find_android_build_tool("aapt2", root)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="aetherlink-release-readback-apk-",
        suffix=".apk",
    )
    try:
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(apk_data)
        badging = run_text(
            [str(aapt2), "dump", "badging", temporary_name],
            root,
        )
        return parse_aapt2_badging(badging)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def inspect_apk_backup_policy(
    apk_data: bytes,
    root: Path = ROOT,
    *,
    entry_point_topology_required: bool = False,
    application_shell_required: bool = False,
) -> dict[str, object]:
    if type(entry_point_topology_required) is not bool:
        raise ReleaseArchiveVerificationError(
            "APK entry-point topology requirement must be a boolean"
        )
    if type(application_shell_required) is not bool:
        raise ReleaseArchiveVerificationError(
            "APK application-shell requirement must be a boolean"
        )
    aapt2 = find_android_build_tool("aapt2", root)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="aetherlink-release-readback-apk-policy-",
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
            resources_with_values,
            application_shell_required=application_shell_required,
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
        if application_shell_required:
            locale_config = run_aapt2_dump(
                [
                    str(aapt2),
                    "dump",
                    "xmltree",
                    "--file",
                    resource_paths["locales_config"],
                    temporary_name,
                ],
                root,
            )
            manifest_policy["applicationShell"] = {
                "localeConfigLocales": parse_aapt2_locale_config(
                    locale_config
                ),
                "localizedString": parse_aapt2_localized_string(
                    resources_with_values
                ),
                "manifestResources": (
                    parse_aapt2_application_shell_manifest(
                        xmltree,
                        resources,
                    )
                ),
            }
        if entry_point_topology_required:
            manifest_policy["entryPointTopology"] = (
                parse_aapt2_entry_point_topology(xmltree)
            )
        return manifest_policy
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def validate_android_art_profile_payload(
    data: bytes,
    label: str,
    *,
    expected_magic: bytes,
    expected_version: bytes,
) -> None:
    if (
        len(data) <= 8
        or len(expected_magic) != 4
        or len(expected_version) != 4
        or data[:4] != expected_magic
        or data[4:8] != expected_version
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} has an unexpected ART profile header"
        )


def parse_android_release_output_metadata(
    data: bytes,
    current: ReleaseVersion,
    apk_directory: Path,
    apk_members: dict[str, bytes],
    aab_members: dict[str, bytes],
) -> dict[str, object]:
    metadata = parse_json_without_duplicate_keys(
        data,
        "Android Release output-metadata.json",
    )
    if type(metadata) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata root must be an object"
        )
    artifact_type = metadata.get("artifactType")
    if artifact_type != {"type": "APK", "kind": "Directory"}:
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata artifact type is unexpected"
        )
    if require_exact_int(
        metadata.get("version"),
        "Android Release output metadata version",
    ) != 3:
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata schema must be version 3"
        )
    if (
        metadata.get("applicationId")
        != "com.localagentbridge.android"
        or metadata.get("variantName") != "release"
        or metadata.get("elementType") != "File"
        or require_exact_int(
            metadata.get("minSdkVersionForDexing"),
            "Android Release output metadata minSdkVersionForDexing",
        )
        != 26
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata identity differs from V1"
        )
    elements = metadata.get("elements")
    if type(elements) is not list or len(elements) != 1:
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata must contain one element"
        )
    element = elements[0]
    if type(element) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata element must be an object"
        )
    if (
        element.get("type") != "SINGLE"
        or element.get("filters") != []
        or element.get("attributes") != []
        or element.get("outputFile") != "app-release-unsigned.apk"
        or require_exact_int(
            element.get("versionCode"),
            "Android Release output metadata versionCode",
        )
        != current.build_number
        or element.get("versionName") != current.marketing_version
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata element differs from ledger"
        )

    baseline_profiles = metadata.get("baselineProfiles")
    if type(baseline_profiles) is not list or len(baseline_profiles) != 2:
        raise ReleaseArchiveVerificationError(
            "Android Release output metadata must describe two baseline "
            "profile API ranges"
        )
    expected_ranges = [(28, 30), (31, 2_147_483_647)]
    observed_ranges: list[tuple[int, int]] = []
    profile_paths: list[str] = []
    profile_records: list[tuple[int, int, dict[str, bytes]]] = []
    for index, profile in enumerate(baseline_profiles):
        if type(profile) is not dict:
            raise ReleaseArchiveVerificationError(
                "Android Release baseline profile entry must be an object"
            )
        min_api = require_exact_int(
            profile.get("minApi"),
            f"Android baselineProfiles[{index}].minApi",
        )
        max_api = require_exact_int(
            profile.get("maxApi"),
            f"Android baselineProfiles[{index}].maxApi",
        )
        observed_ranges.append((min_api, max_api))
        paths = profile.get("baselineProfiles")
        if (
            type(paths) is not list
            or len(paths) != 1
            or type(paths[0]) is not str
        ):
            raise ReleaseArchiveVerificationError(
                "Android Release baseline profile range must name one file"
            )
        pure = PurePosixPath(paths[0])
        if (
            pure.is_absolute()
            or len(pure.parts) != 3
            or pure.parts[0] != "baselineProfiles"
            or any(part in ("", ".", "..") for part in pure.parts)
            or pure.suffix != ".dm"
        ):
            raise ReleaseArchiveVerificationError(
                "Android Release baseline profile path is noncanonical"
            )
        profile_paths.append(paths[0])
    if observed_ranges != expected_ranges:
        raise ReleaseArchiveVerificationError(
            "Android Release baseline profile API ranges differ from V1"
        )
    if len(profile_paths) != len(set(profile_paths)):
        raise ReleaseArchiveVerificationError(
            "Android Release baseline profile paths must be unique"
        )

    expected_inventory = {
        "app-release-unsigned.apk",
        "output-metadata.json",
        "baselineProfiles",
    }
    require_directory_inventory(
        apk_directory,
        expected_inventory,
        "Android Release APK output directory",
    )
    baseline_root = apk_directory / "baselineProfiles"
    try:
        baseline_root_status = baseline_root.lstat()
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"Android Release baseline profile root cannot be inspected: {error}"
        ) from error
    if stat.S_ISLNK(baseline_root_status.st_mode) or not stat.S_ISDIR(
        baseline_root_status.st_mode
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release baseline profile root must be a non-symlink "
            "directory"
        )
    expected_baseline_entries: set[str] = set()
    for (min_api, max_api), relative in zip(
        observed_ranges,
        profile_paths,
    ):
        pure = PurePosixPath(relative)
        expected_baseline_entries.add("/".join(pure.parts[1:]))
        expected_baseline_entries.add(pure.parts[1])
        profile_data = read_stable_regular_file(
            apk_directory.joinpath(*pure.parts),
            f"Android Release baseline profile {relative}",
            maximum_bytes=67_108_864,
        )
        profile_members = read_safe_zip_members(
            profile_data,
            f"Android Release baseline profile {relative}",
            maximum_members=2,
            maximum_member_bytes=16_777_216,
            maximum_total_uncompressed_bytes=33_554_432,
        )
        if set(profile_members) != {"primary.prof", "primary.profm"}:
            raise ReleaseArchiveVerificationError(
                "Android Release baseline profile must contain exactly "
                f"primary.prof and primary.profm: {relative}"
            )
        profile_records.append((min_api, max_api, profile_members))
    try:
        actual_baseline_entries = {
            entry.relative_to(baseline_root).as_posix()
            for entry in baseline_root.rglob("*")
        }
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"Android Release baseline profile inventory failed: {error}"
        ) from error
    if actual_baseline_entries != expected_baseline_entries:
        raise ReleaseArchiveVerificationError(
            "Android Release baseline profile inventory differs; "
            f"missing={sorted(expected_baseline_entries - actual_baseline_entries)}, "
            f"extra={sorted(actual_baseline_entries - expected_baseline_entries)}"
        )
    for entry in baseline_root.rglob("*"):
        status = entry.lstat()
        if stat.S_ISLNK(status.st_mode) or not (
            stat.S_ISDIR(status.st_mode) or stat.S_ISREG(status.st_mode)
        ):
            raise ReleaseArchiveVerificationError(
                "Android Release baseline profile tree contains an unsafe entry"
            )

    apk_profile_names = {
        name
        for name in apk_members
        if name.startswith("assets/dexopt/baseline.")
    }
    expected_apk_profile_names = {
        "assets/dexopt/baseline.prof",
        "assets/dexopt/baseline.profm",
    }
    if apk_profile_names != expected_apk_profile_names:
        raise ReleaseArchiveVerificationError(
            "Android Release APK baseline profile inventory differs"
        )
    aab_profile_prefix = (
        "BUNDLE-METADATA/com.android.tools.build.profiles/"
    )
    aab_profile_names = {
        name for name in aab_members if name.startswith(aab_profile_prefix)
    }
    expected_aab_profile_names = {
        f"{aab_profile_prefix}baseline.prof",
        f"{aab_profile_prefix}baseline.profm",
    }
    if aab_profile_names != expected_aab_profile_names:
        raise ReleaseArchiveVerificationError(
            "Android Release AAB baseline profile inventory differs"
        )

    apk_profile = apk_members["assets/dexopt/baseline.prof"]
    apk_profile_metadata = apk_members["assets/dexopt/baseline.profm"]
    if (
        aab_members[f"{aab_profile_prefix}baseline.prof"] != apk_profile
        or aab_members[f"{aab_profile_prefix}baseline.profm"]
        != apk_profile_metadata
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release APK and AAB baseline profile payloads differ"
        )
    validate_android_art_profile_payload(
        apk_profile,
        "Android Release APK baseline.prof",
        expected_magic=b"pro\0",
        expected_version=b"010\0",
    )
    validate_android_art_profile_payload(
        apk_profile_metadata,
        "Android Release APK baseline.profm",
        expected_magic=b"prm\0",
        expected_version=b"002\0",
    )
    if (
        sha256(apk_profile) != ANDROID_RELEASE_APK_BASELINE_PROFILE_SHA256
        or sha256(apk_profile_metadata)
        != ANDROID_RELEASE_APK_BASELINE_PROFILE_METADATA_SHA256
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release APK/AAB baseline profiles differ from the "
            "pinned V1 profile identities"
        )

    profiles_by_range = {
        (min_api, max_api): members
        for min_api, max_api, members in profile_records
    }
    api_28_profile = profiles_by_range[(28, 30)]
    api_31_profile = profiles_by_range[(31, 2_147_483_647)]
    if (
        api_28_profile["primary.prof"] != apk_profile
        or api_28_profile["primary.profm"] != apk_profile_metadata
        or api_31_profile["primary.profm"] != apk_profile_metadata
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release DM profiles are not bound to the APK/AAB "
            "baseline profile payloads"
        )
    validate_android_art_profile_payload(
        api_31_profile["primary.prof"],
        "Android Release API 31+ DM primary.prof",
        expected_magic=b"pro\0",
        expected_version=b"015\0",
    )
    if (
        sha256(api_31_profile["primary.prof"])
        != ANDROID_RELEASE_API31_DM_PROFILE_SHA256
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release API 31+ DM primary.prof differs from the "
            "pinned V1 converted-profile identity"
        )
    return {
        "baselineProfileCount": len(profile_paths),
        "outputFile": element["outputFile"],
    }


def validate_android_r8_partition_source_prefix(
    prefix: bytes,
    class_name_pattern: re.Pattern[str],
    partition_name: str,
) -> None:
    label = f"Android Release mapping.prt partition {partition_name}"
    if (
        not prefix.startswith(b"# ")
        or not prefix.endswith(b"\n")
        or prefix.count(b"\n") != 1
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} has an unexpected source-file prefix"
        )
    value = parse_json_without_duplicate_keys(
        prefix[2:-1],
        f"{label} source-file prefix",
    )
    if type(value) is not dict:
        raise ReleaseArchiveVerificationError(
            f"{label} source-file prefix must be an object"
        )
    require_exact_keys(
        value,
        {"id", "fileNameMappings"},
        f"{label} source-file prefix",
    )
    file_name_mappings = value.get("fileNameMappings")
    if (
        value.get("id") != "partitionSourceFiles"
        or type(file_name_mappings) is not dict
        or not file_name_mappings
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} source-file mapping differs"
        )
    for class_identity, source_file in file_name_mappings.items():
        if (
            type(class_identity) is not str
            or class_name_pattern.fullmatch(class_identity) is None
            or type(source_file) is not str
            or not source_file
            or len(source_file) > 512
            or any(ord(character) < 33 or ord(character) > 126 for character in source_file)
            or "/" in source_file
            or "\\" in source_file
        ):
            raise ReleaseArchiveVerificationError(
                f"{label} contains an invalid source-file identity"
            )


def validate_android_r8_prt_metadata(
    data: bytes,
    partition_names: list[str],
    expected_mapping_header: bytes,
    original_names: list[str],
) -> None:
    label = "Android Release mapping.prt METADATA"
    cursor = 0

    def take(length: int) -> bytes:
        nonlocal cursor
        if length < 0 or cursor + length > len(data):
            raise ReleaseArchiveVerificationError(
                f"{label} is truncated"
            )
        value = data[cursor : cursor + length]
        cursor += length
        return value

    def read_unsigned(length: int) -> int:
        return int.from_bytes(take(length), "big")

    if take(2) != b"\xaa\xa8" or read_unsigned(2) != 1:
        raise ReleaseArchiveVerificationError(
            f"{label} header differs"
        )
    version_length = read_unsigned(2)
    if version_length != 3 or take(version_length) != b"2.2":
        raise ReleaseArchiveVerificationError(
            f"{label} mapping version differs"
        )
    partition_name_bytes = b";".join(
        name.encode("ascii") for name in partition_names
    )
    if (
        read_unsigned(4) != len(partition_name_bytes)
        or take(len(partition_name_bytes)) != partition_name_bytes
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} partition inventory differs"
        )
    tail_length = read_unsigned(4)
    if tail_length != len(data) - cursor:
        raise ReleaseArchiveVerificationError(
            f"{label} tail length differs"
        )
    if read_unsigned(2) != 2 or read_unsigned(4) != 0:
        raise ReleaseArchiveVerificationError(
            f"{label} partition map header differs"
        )
    header_length = read_unsigned(2)
    if (
        header_length != len(expected_mapping_header)
        or take(header_length) != expected_mapping_header
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} is not bound to mapping.txt"
        )
    if read_unsigned(2) != 1:
        raise ReleaseArchiveVerificationError(
            f"{label} package-map version differs"
        )
    package_length = read_unsigned(4)
    packages_data = take(package_length)
    if cursor != len(data):
        raise ReleaseArchiveVerificationError(
            f"{label} contains trailing bytes"
        )
    if not packages_data.startswith(b"\n") or not packages_data.endswith(b"\n"):
        raise ReleaseArchiveVerificationError(
            f"{label} package inventory is not LF-delimited"
        )
    try:
        packages = packages_data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ReleaseArchiveVerificationError(
            f"{label} package inventory must be ASCII"
        ) from error
    if (
        not packages
        or packages[0] != ""
        or any(not package for package in packages[1:])
        or packages[1:] != sorted(set(packages[1:]))
    ):
        raise ReleaseArchiveVerificationError(
            f"{label} package inventory is noncanonical"
        )
    for package in packages[1:]:
        if not any(
            original_name.startswith(package + ".")
            for original_name in original_names
        ):
            raise ReleaseArchiveVerificationError(
                f"{label} contains an unbound package identity"
            )


def validate_android_release_mapping_outputs(
    mapping_outputs: dict[str, bytes],
) -> None:
    if set(mapping_outputs) != set(ANDROID_RELEASE_MAPPING_FILES):
        raise ReleaseArchiveVerificationError(
            "Android Release R8 mapping file set differs"
        )
    configuration = mapping_outputs["configuration.txt"]
    if b"\0" in configuration or not configuration.endswith(b"\n"):
        raise ReleaseArchiveVerificationError(
            "Android Release R8 configuration must be LF-terminated "
            "and NUL-free"
        )
    mapping_prt = mapping_outputs["mapping.prt"]
    canonicalize_r8_resources(
        mapping_outputs["resources.txt"],
        "Android Release resources.txt",
    )
    canonicalize_r8_line_artifact(
        mapping_outputs["seeds.txt"],
        "Android Release seeds.txt",
    )
    for name in ("mapping.txt", "usage.txt"):
        data = mapping_outputs[name]
        if b"\0" in data or b"\r" in data or not data.endswith(b"\n"):
            raise ReleaseArchiveVerificationError(
                f"Android Release {name} must be LF-terminated and NUL-free"
            )
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ReleaseArchiveVerificationError(
                f"Android Release {name} must be UTF-8 text"
            ) from error

    mapping = mapping_outputs["mapping.txt"]
    header_match = re.match(
        rb"\A# compiler: R8\n"
        rb"# compiler_version: ([0-9]+\.[0-9]+\.[0-9]+(?:[-+]"
        rb"[A-Za-z0-9_.-]+)?)\n"
        rb"# min_api: ([0-9]+)\n"
        rb"# common_typos_disable\n"
        rb'# \{"id":"com\.android\.tools\.r8\.mapping",'
        rb'"version":"2\.2"\}\n'
        rb"# pg_map_id: ([0-9a-f]{64})\n"
        rb"# pg_map_hash: SHA-256 ([0-9a-f]{64})\n",
        mapping,
    )
    if header_match is None:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.txt R8 header differs"
        )
    if int(header_match.group(2)) != 26:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.txt min_api must be 26"
        )
    mapping_body = mapping[header_match.end() :]
    if hashlib.sha256(mapping_body).hexdigest().encode("ascii") != (
        header_match.group(4)
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.txt pg_map_hash differs from its body"
        )
    if header_match.group(3) == b"0" * 64:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.txt pg_map_id must be nonzero"
        )

    java_identifier = r"[A-Za-z_$][A-Za-z0-9_$-]*"
    class_name = rf"{java_identifier}(?:\.{java_identifier})*"
    class_identity_pattern = re.compile(rf"^{class_name}$")
    class_mapping_pattern = re.compile(
        rf"^({class_name}) -> ({class_name}):$"
    )
    original_names: list[str] = []
    obfuscated_names: list[str] = []
    mapping_blocks: dict[str, bytes] = {}
    current_obfuscated_name: str | None = None
    current_block: list[bytes] = []
    for raw_line in mapping_body.splitlines(keepends=True):
        if raw_line and not raw_line.startswith((b" ", b"#")):
            if not raw_line.endswith(b"\n"):
                raise ReleaseArchiveVerificationError(
                    "Android Release mapping.txt contains an unterminated "
                    "top-level class mapping"
                )
            try:
                line = raw_line[:-1].decode("utf-8")
            except UnicodeDecodeError as error:
                raise ReleaseArchiveVerificationError(
                    "Android Release mapping.txt class identity must be UTF-8"
                ) from error
            class_match = class_mapping_pattern.fullmatch(line)
            if class_match is None:
                raise ReleaseArchiveVerificationError(
                    "Android Release mapping.txt contains a malformed "
                    f"top-level class mapping: {line!r}"
                )
            if current_obfuscated_name is not None:
                mapping_blocks[current_obfuscated_name] = b"".join(
                    current_block
                )
            elif current_block:
                raise ReleaseArchiveVerificationError(
                    "Android Release mapping.txt body begins outside a class "
                    "mapping"
                )
            original_names.append(class_match.group(1))
            current_obfuscated_name = class_match.group(2)
            obfuscated_names.append(current_obfuscated_name)
            current_block = [raw_line]
        else:
            current_block.append(raw_line)
    if current_obfuscated_name is not None:
        mapping_blocks[current_obfuscated_name] = b"".join(current_block)
    if not original_names:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.txt must contain class mappings"
        )
    if (
        len(original_names) != len(set(original_names))
        or len(obfuscated_names) != len(set(obfuscated_names))
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.txt class identities must be unique"
        )

    partition_members = read_safe_zip_members(
        mapping_prt,
        "Android Release mapping.prt",
        maximum_members=ANDROID_RELEASE_R8_PRT_MAX_MEMBER_COUNT,
        maximum_member_bytes=ANDROID_RELEASE_R8_PRT_MAX_MEMBER_BYTES,
        maximum_total_uncompressed_bytes=(
            ANDROID_RELEASE_R8_PRT_MAX_TOTAL_UNCOMPRESSED_BYTES
        ),
    )
    if "METADATA" not in partition_members:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.prt must contain METADATA"
        )
    partition_class_names = set(partition_members) - {"METADATA"}
    obfuscated_name_set = set(obfuscated_names)
    if not partition_class_names:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.prt must contain class partitions"
        )
    unexpected_partitions = sorted(
        partition_class_names - obfuscated_name_set
    )
    missing_partitions = sorted(
        obfuscated_name_set - partition_class_names
    )
    if unexpected_partitions or set(missing_partitions) - {"$$compose"}:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.prt class partitions differ from "
            "mapping.txt; "
            f"missing={missing_partitions}, extra={unexpected_partitions}"
        )
    for partition_name in partition_class_names:
        partition_payload = partition_members[partition_name]
        mapping_block = mapping_blocks[partition_name]
        if partition_payload == mapping_block:
            continue
        if not partition_payload.endswith(mapping_block):
            raise ReleaseArchiveVerificationError(
                "Android Release mapping.prt partition payload differs from "
                f"mapping.txt: {partition_name}"
            )
        validate_android_r8_partition_source_prefix(
            partition_payload[: -len(mapping_block)],
            class_identity_pattern,
            partition_name,
        )

    metadata_header = bytearray(mapping[: header_match.end()])
    metadata_header[
        header_match.start(4) : header_match.end(4)
    ] = header_match.group(3)
    ordered_partition_names = [
        name for name in partition_members if name != "METADATA"
    ]
    validate_android_r8_prt_metadata(
        partition_members["METADATA"],
        ordered_partition_names,
        bytes(metadata_header),
        original_names,
    )
    if sha256(mapping) != ANDROID_RELEASE_R8_MAPPING_SHA256:
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.txt differs from the pinned V1 byte "
            "identity"
        )
    if (
        logical_member_digest(
            partition_members,
            b"AETHERLINK-R8-PRT-V1\0",
        )
        != ANDROID_RELEASE_R8_MAPPING_PRT_LOGICAL_SHA256
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release mapping.prt differs from the pinned V1 "
            "logical identity"
        )


def decode_android_sdk_dependency_digest(value: str, label: str) -> bytes:
    output = bytearray()
    cursor = 0
    simple_escapes = {
        "a": 7,
        "b": 8,
        "f": 12,
        "n": 10,
        "r": 13,
        "t": 9,
        "v": 11,
        "\\": 92,
        "'": 39,
        '"': 34,
    }
    while cursor < len(value):
        character = value[cursor]
        if character != "\\":
            code_point = ord(character)
            if code_point < 32 or code_point > 126:
                raise ReleaseArchiveVerificationError(
                    f"{label} contains a non-ASCII digest byte"
                )
            output.append(code_point)
            cursor += 1
            continue
        if cursor + 1 >= len(value):
            raise ReleaseArchiveVerificationError(
                f"{label} contains a truncated digest escape"
            )
        escape = value[cursor + 1]
        if escape in simple_escapes:
            output.append(simple_escapes[escape])
            cursor += 2
            continue
        octal = value[cursor + 1 : cursor + 4]
        if len(octal) != 3 or any(digit not in "01234567" for digit in octal):
            raise ReleaseArchiveVerificationError(
                f"{label} contains a noncanonical digest escape"
            )
        output.append(int(octal, 8))
        cursor += 4
    return bytes(output)


def parse_android_sdk_dependencies(
    data: bytes,
    root: Path,
) -> int:
    if (
        data.startswith(b"\xef\xbb\xbf")
        or b"\r" in data
        or b"\0" in data
        or not data.endswith(b"\n")
    ):
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency output must be BOM-free ASCII/LF text"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency output must contain only ASCII"
        ) from error
    header = (
        "# List of SDK dependencies of this app, this information is also "
        "included in an encrypted form in the APK.\n"
        "# For more information visit: "
        "https://d.android.com/r/tools/dependency-metadata\n\n"
    )
    if not text.startswith(header):
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency output header differs"
        )
    block_pattern = re.compile(
        r"(?ms)^(library|library_dependencies|module_dependencies|"
        r"repositories) \{\n.*?^\}\n"
    )
    matches = list(block_pattern.finditer(text, len(header)))
    cursor = len(header)
    coordinates: list[str] = []
    library_repository_indices: list[int] = []
    dependency_graph: dict[int, list[int]] = {}
    module_dependencies: list[int] | None = None
    repository_blocks: list[str] = []
    digest_count = 0
    observed_kinds: list[str] = []
    for index, match in enumerate(matches):
        if match.start() != cursor:
            raise ReleaseArchiveVerificationError(
                "Android SDK dependency output contains text outside "
                "recognized top-level blocks"
            )
        kind = match.group(1)
        observed_kinds.append(kind)
        block = match.group(0)
        cursor = match.end()
        if kind == "library":
            library_match = re.fullmatch(
                r"library \{\n"
                r"  maven_library \{\n"
                r'    groupId: "([A-Za-z0-9_.+\-]+)"\n'
                r'    artifactId: "([A-Za-z0-9_.+\-]+)"\n'
                r'    version: "([A-Za-z0-9_.+\-]+)"\n'
                r"  \}\n"
                r"(?:  digests \{\n"
                r'    sha256: "((?:\\[^\n]|[^"\\\n])+)"\n'
                r"  \}\n)?"
                r"  repo_index \{\n"
                r"(?:    value: ([01])\n)?"
                r"  \}\n"
                r"\}\n",
                block,
            )
            if library_match is None:
                raise ReleaseArchiveVerificationError(
                    f"Android SDK dependency block {index} has an invalid "
                    "library shape"
                )
            coordinates.append(":".join(library_match.group(1, 2, 3)))
            digest = library_match.group(4)
            if digest is not None:
                digest_bytes = decode_android_sdk_dependency_digest(
                    digest,
                    f"Android SDK dependency block {index}",
                )
                if len(digest_bytes) != 32:
                    raise ReleaseArchiveVerificationError(
                        f"Android SDK dependency block {index} digest must be "
                        "32 bytes"
                    )
                digest_count += 1
            repository_index = library_match.group(5)
            library_repository_indices.append(
                0 if repository_index is None else int(repository_index)
            )
            continue
        if kind == "library_dependencies":
            dependency_match = re.fullmatch(
                r"library_dependencies \{\n"
                r"(?:  library_index: ([1-9][0-9]*)\n)?"
                r"((?:  library_dep_index: (?:0|[1-9][0-9]*)\n)+)"
                r"\}\n",
                block,
            )
            if dependency_match is None:
                raise ReleaseArchiveVerificationError(
                    f"Android SDK dependency block {index} has an invalid "
                    "dependency shape"
                )
            owner = (
                0
                if dependency_match.group(1) is None
                else int(dependency_match.group(1))
            )
            if owner in dependency_graph:
                raise ReleaseArchiveVerificationError(
                    "Android SDK dependency owners must be unique"
                )
            dependency_graph[owner] = [
                int(value)
                for value in re.findall(
                    r"^  library_dep_index: (0|[1-9][0-9]*)$",
                    dependency_match.group(2),
                    re.MULTILINE,
                )
            ]
            continue
        if kind == "module_dependencies":
            module_match = re.fullmatch(
                r"module_dependencies \{\n"
                r'  module_name: "base"\n'
                r"((?:  dependency_index: (?:0|[1-9][0-9]*)\n)+)"
                r"\}\n",
                block,
            )
            if module_match is None or module_dependencies is not None:
                raise ReleaseArchiveVerificationError(
                    "Android SDK module dependency block differs"
                )
            module_dependencies = [
                int(value)
                for value in re.findall(
                    r"^  dependency_index: (0|[1-9][0-9]*)$",
                    module_match.group(1),
                    re.MULTILINE,
                )
            ]
            continue
        repository_blocks.append(block)
    kind_rank = {
        "library": 0,
        "library_dependencies": 1,
        "module_dependencies": 2,
        "repositories": 3,
    }
    if (
        cursor != len(text)
        or not coordinates
        or [kind_rank[kind] for kind in observed_kinds]
        != sorted(kind_rank[kind] for kind in observed_kinds)
        or module_dependencies is None
        or repository_blocks
        != [
            "repositories {\n"
            "  maven_repo {\n"
            '    url: "https://dl.google.com/dl/android/maven2/"\n'
            "  }\n"
            "}\n",
            "repositories {\n"
            "  maven_repo {\n"
            '    url: "https://repo.maven.apache.org/maven2/"\n'
            "  }\n"
            "}\n",
        ]
        or not digest_count
    ):
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency output top-level block shape differs"
        )
    if len(coordinates) != len(set(coordinates)):
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency identities must be unique"
        )
    library_count = len(coordinates)
    if any(
        repository_index >= len(repository_blocks)
        for repository_index in library_repository_indices
    ):
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency repository index is out of range"
        )
    for owner, dependencies in dependency_graph.items():
        if (
            owner >= library_count
            or any(dependency >= library_count for dependency in dependencies)
            or owner in dependencies
        ):
            raise ReleaseArchiveVerificationError(
                "Android SDK library dependency graph contains an invalid index"
            )
    if (
        not module_dependencies
        or len(module_dependencies) != len(set(module_dependencies))
        or any(dependency >= library_count for dependency in module_dependencies)
    ):
        raise ReleaseArchiveVerificationError(
            "Android SDK module dependency roots differ"
        )
    reachable = set(module_dependencies)
    pending = list(module_dependencies)
    while pending:
        owner = pending.pop()
        for dependency in dependency_graph.get(owner, []):
            if dependency not in reachable:
                reachable.add(dependency)
                pending.append(dependency)
    expected_indices = set(range(library_count))
    if reachable != expected_indices:
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency graph is not complete from the base "
            "module; "
            f"missing={sorted(expected_indices - reachable)}"
        )

    locked_modules: set[str] = set()
    release_runtime_locked_modules: set[str] = set()
    for relative in GRADLE_LOCK_PATHS:
        lock_data = read_stable_regular_file(
            root / relative,
            f"Gradle dependency lock {relative}",
            maximum_bytes=16_777_216,
        )
        parse_gradle_lockfile(lock_data, relative)
        for line in lock_data.decode("ascii").splitlines()[3:]:
            module, configurations = line.split("=", 1)
            if module != "empty":
                locked_modules.add(module)
                if (
                    relative == "apps/android/app/gradle.lockfile"
                    and "releaseRuntimeClasspath"
                    in configurations.split(",")
                ):
                    release_runtime_locked_modules.add(module)
    ignored = set(GRADLE_IGNORED_DEPENDENCIES)
    unlocked = [
        coordinate
        for coordinate in coordinates
        if coordinate not in locked_modules
        and ":".join(coordinate.split(":")[:2]) not in ignored
    ]
    if unlocked:
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency output contains unlocked modules: "
            f"{sorted(unlocked)}"
        )
    expected_coordinates = set(release_runtime_locked_modules)
    for ignored_coordinate, parent_coordinate in (
        GRADLE_IGNORED_DEPENDENCY_PARENT.items()
    ):
        parent_versions = {
            module.rsplit(":", 1)[1]
            for module in release_runtime_locked_modules
            if module.rsplit(":", 1)[0] == parent_coordinate
        }
        if not parent_versions:
            continue
        if len(parent_versions) != 1:
            raise ReleaseArchiveVerificationError(
                "Android Release runtime lock must contain one parent "
                f"version for ignored dependency {ignored_coordinate}"
            )
        expected_coordinates.add(
            f"{ignored_coordinate}:{next(iter(parent_versions))}"
        )
    observed_coordinates = set(coordinates)
    if observed_coordinates != expected_coordinates:
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency output differs from the exact Release "
            "runtime lock closure; "
            f"missing={sorted(expected_coordinates - observed_coordinates)}, "
            f"extra={sorted(observed_coordinates - expected_coordinates)}"
        )
    if sha256(data) != ANDROID_RELEASE_SDK_DEPENDENCIES_SHA256:
        raise ReleaseArchiveVerificationError(
            "Android SDK dependency output differs from the pinned V1 byte "
            "identity"
        )
    return len(coordinates)


def find_llvm_readelf(root: Path = ROOT) -> Path:
    sdk_root = android_sdk_root(root)
    candidates = sorted(
        sdk_root.glob(
            f"ndk/{ANDROID_NDK_VERSION}/toolchains/llvm/prebuilt/*/bin/"
            "llvm-readelf"
        ),
        key=lambda item: item.as_posix(),
    )
    candidates = [
        candidate
        for candidate in candidates
        if candidate.is_file() and os.access(candidate, os.X_OK)
    ]
    if len(candidates) != 1:
        raise ReleaseArchiveVerificationError(
            "expected exactly one llvm-readelf for pinned Android NDK "
            f"{ANDROID_NDK_VERSION} under {sdk_root}; found {candidates}"
        )
    return candidates[0]


def inspect_elf(
    path: Path,
    llvm_readelf: Path,
    root: Path = ROOT,
) -> tuple[str | None, bool]:
    notes = run_text([str(llvm_readelf), "-n", str(path)], root)
    build_id_match = re.search(r"Build ID:\s*([0-9a-fA-F]+)", notes)
    sections = run_text(
        [str(llvm_readelf), "-W", "-S", str(path)],
        root,
    )
    has_debug_metadata = (
        re.search(r"\.symtab(?:\s|$)", sections) is not None
        or re.search(r"\.debug_[A-Za-z0-9_.-]+", sections) is not None
    )
    return (
        build_id_match.group(1).lower() if build_id_match else None,
        has_debug_metadata,
    )


def inspect_elf_bytes(
    data: bytes,
    label: str,
    llvm_readelf: Path,
    root: Path = ROOT,
) -> tuple[str | None, bool]:
    if not data.startswith(b"\x7fELF"):
        raise ReleaseArchiveVerificationError(
            f"{label} is not an ELF file"
        )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="aetherlink-release-elf-readback-",
            suffix=".elf",
            delete=False,
        ) as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        return inspect_elf(temporary_path, llvm_readelf, root)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def read_safe_zip_members(
    data: bytes,
    label: str,
    *,
    maximum_members: int = 8_192,
    maximum_member_bytes: int = 268_435_456,
    maximum_total_uncompressed_bytes: int = 536_870_912,
) -> dict[str, bytes]:
    limits = {
        "member count": maximum_members,
        "member size": maximum_member_bytes,
        "total uncompressed size": maximum_total_uncompressed_bytes,
    }
    for kind, limit in limits.items():
        if type(limit) is not int or limit < 1:
            raise ReleaseArchiveVerificationError(
                f"{label} {kind} limit must be a positive integer"
            )
    members: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            if archive.comment:
                raise ReleaseArchiveVerificationError(
                    f"{label} must not contain a ZIP comment"
                )
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if not names or len(names) != len(set(names)):
                raise ReleaseArchiveVerificationError(
                    f"{label} must contain unique members"
                )
            if len(infos) > maximum_members:
                raise ReleaseArchiveVerificationError(
                    f"{label} exceeds the {maximum_members}-member limit"
                )
            total_uncompressed_bytes = 0
            for info in infos:
                validate_member_path(info.filename)
                if info.is_dir() or info.flag_bits & 0x1:
                    raise ReleaseArchiveVerificationError(
                        f"{label} contains a directory or encrypted member"
                    )
                if info.file_size < 1:
                    raise ReleaseArchiveVerificationError(
                        f"{label} contains an empty member: {info.filename}"
                    )
                if info.file_size > maximum_member_bytes:
                    raise ReleaseArchiveVerificationError(
                        f"{label} member exceeds the "
                        f"{maximum_member_bytes}-byte limit: {info.filename}"
                    )
                total_uncompressed_bytes += info.file_size
                if (
                    total_uncompressed_bytes
                    > maximum_total_uncompressed_bytes
                ):
                    raise ReleaseArchiveVerificationError(
                        f"{label} exceeds the "
                        f"{maximum_total_uncompressed_bytes}-byte total "
                        "uncompressed limit"
                    )
                member = archive.read(info)
                if len(member) != info.file_size:
                    raise ReleaseArchiveVerificationError(
                        f"{label} member size differs after readback: "
                        f"{info.filename}"
                    )
                members[info.filename] = member
    except ReleaseArchiveVerificationError:
        raise
    except (
        EOFError,
        OSError,
        KeyError,
        RuntimeError,
        zipfile.BadZipFile,
        zlib.error,
    ) as error:
        raise ReleaseArchiveVerificationError(
            f"{label} is not a readable ZIP: {error}"
        ) from error
    return members


def verify_android_release_build_outputs(
    root: Path = ROOT,
) -> dict[str, object]:
    try:
        current = load_release_version_ledger(
            root / "release/version-ledger.tsv"
        )[-1]
    except (IndexError, LedgerError) as error:
        raise ReleaseArchiveVerificationError(
            f"Android Release ledger readback failed: {error}"
        ) from error

    apk_path = root / ANDROID_RELEASE_APK_RELATIVE_PATH
    apk_metadata_path = (
        root / ANDROID_RELEASE_APK_METADATA_RELATIVE_PATH
    )
    aab_path = root / ANDROID_RELEASE_AAB_RELATIVE_PATH
    mapping_directory = root / ANDROID_RELEASE_MAPPING_RELATIVE_PATH
    sdk_dependencies_path = (
        root / ANDROID_RELEASE_SDK_DEPENDENCIES_RELATIVE_PATH
    )
    native_symbol_path = (
        root / ANDROID_RELEASE_NATIVE_SYMBOL_RELATIVE_PATH
    )

    require_directory_inventory(
        aab_path.parent,
        {aab_path.name},
        "Android Release AAB output directory",
    )
    require_directory_inventory(
        mapping_directory,
        set(ANDROID_RELEASE_MAPPING_FILES),
        "Android Release R8 output directory",
    )
    require_directory_inventory(
        sdk_dependencies_path.parent,
        {sdk_dependencies_path.name},
        "Android Release SDK dependency output directory",
    )
    apk_data = read_stable_regular_file(
        apk_path,
        "Android Release APK",
    )
    apk_members = read_safe_zip_members(
        apk_data,
        "Android Release APK",
        maximum_members=ANDROID_RELEASE_APK_MAX_MEMBER_COUNT,
        maximum_member_bytes=ANDROID_RELEASE_APK_MAX_MEMBER_BYTES,
        maximum_total_uncompressed_bytes=(
            ANDROID_RELEASE_APK_MAX_TOTAL_UNCOMPRESSED_BYTES
        ),
    )
    apk_native_members = {
        name: member
        for name, member in apk_members.items()
        if name.startswith("lib/") and name.endswith(".so")
    }
    if not apk_native_members:
        raise ReleaseArchiveVerificationError(
            "Android Release APK must contain JNI libraries"
        )
    if any(
        len(PurePosixPath(name).parts) != 3
        for name in apk_native_members
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release APK contains a noncanonical JNI path"
        )
    apk_native_abis = sorted(
        {PurePosixPath(name).parts[1] for name in apk_native_members}
    )
    if apk_native_abis != ["arm64-v8a"]:
        raise ReleaseArchiveVerificationError(
            "Android Release APK JNI ABI set must be arm64-v8a-only"
        )
    apk_metadata_data = read_stable_regular_file(
        apk_metadata_path,
        "Android Release APK output metadata",
        maximum_bytes=1_048_576,
    )
    aab_data = read_stable_regular_file(
        aab_path,
        "Android Release AAB",
    )
    aab_members = read_safe_zip_members(
        aab_data,
        "Android Release AAB",
        maximum_members=ANDROID_RELEASE_AAB_MAX_MEMBER_COUNT,
        maximum_member_bytes=ANDROID_RELEASE_AAB_MAX_MEMBER_BYTES,
        maximum_total_uncompressed_bytes=(
            ANDROID_RELEASE_AAB_MAX_TOTAL_UNCOMPRESSED_BYTES
        ),
    )
    apk_dex_members = {
        name: payload
        for name, payload in apk_members.items()
        if re.fullmatch(r"classes(?:[2-9][0-9]*)?\.dex", name)
    }
    aab_dex_members = {
        name.removeprefix("base/dex/"): payload
        for name, payload in aab_members.items()
        if name.startswith("base/dex/") and name.endswith(".dex")
    }
    if (
        set(apk_dex_members) != {"classes.dex"}
        or apk_dex_members != aab_dex_members
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release APK and AAB DEX members differ from the V1 "
            "single-DEX identity"
        )
    if sha256(apk_dex_members["classes.dex"]) != ANDROID_RELEASE_DEX_SHA256:
        raise ReleaseArchiveVerificationError(
            "Android Release DEX differs from the pinned V1 byte identity"
        )

    sdk_protobuf_prefix = (
        "BUNDLE-METADATA/com.android.tools.build.libraries/"
    )
    sdk_protobuf_names = {
        name for name in aab_members if name.startswith(sdk_protobuf_prefix)
    }
    sdk_protobuf_name = f"{sdk_protobuf_prefix}dependencies.pb"
    if sdk_protobuf_names != {sdk_protobuf_name}:
        raise ReleaseArchiveVerificationError(
            "Android Release AAB SDK dependency protobuf inventory differs"
        )
    if (
        sha256(aab_members[sdk_protobuf_name])
        != ANDROID_RELEASE_SDK_DEPENDENCIES_PROTOBUF_SHA256
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release AAB SDK dependency protobuf differs from the "
            "pinned V1 byte identity"
        )
    mapping_outputs = {
        name: read_stable_regular_file(
            mapping_directory / name,
            f"Android Release R8 {name}",
            maximum_bytes=ANDROID_RELEASE_MAPPING_MAX_BYTES[name],
        )
        for name in ANDROID_RELEASE_MAPPING_FILES
    }
    if sum(map(len, mapping_outputs.values())) > (
        ANDROID_RELEASE_MAPPING_MAX_TOTAL_BYTES
    ):
        raise ReleaseArchiveVerificationError(
            "Android Release R8 outputs exceed the cumulative read limit"
        )
    sdk_dependencies_data = read_stable_regular_file(
        sdk_dependencies_path,
        "Android Release SDK dependencies",
        maximum_bytes=16_777_216,
    )
    metadata_result = parse_android_release_output_metadata(
        apk_metadata_data,
        current,
        apk_path.parent,
        apk_members,
        aab_members,
    )
    validate_android_release_mapping_outputs(mapping_outputs)
    dependency_count = parse_android_sdk_dependencies(
        sdk_dependencies_data,
        root,
    )

    expected_badging = {
        "applicationId": "com.localagentbridge.android",
        "minSdk": 26,
        "nativeAbis": ["arm64-v8a"],
        "targetSdk": 36,
        "versionCode": current.build_number,
        "versionName": current.marketing_version,
    }
    apk_badging = inspect_apk_badging(apk_data, root)
    if apk_badging != expected_badging:
        raise ReleaseArchiveVerificationError(
            "Android Release APK badging differs from V1 and the ledger"
        )
    backup_policy_required = (
        current.build_number >= ANDROID_BACKUP_POLICY_BUILD
    )
    topology_required = (
        current.build_number >= ANDROID_ENTRY_POINT_TOPOLOGY_BUILD
    )
    shell_required = (
        current.build_number >= ANDROID_APPLICATION_SHELL_BUILD
    )
    apk_policy = inspect_apk_backup_policy(
        apk_data,
        root,
        entry_point_topology_required=topology_required,
        application_shell_required=shell_required,
    )
    expected_apk_policy: dict[str, object] = {
        "allowBackup": False,
        "dataExtractionRules": "@xml/data_extraction_rules",
        "fullBackupContent": "@xml/backup_rules",
    }
    if topology_required:
        expected_apk_policy["entryPointTopology"] = (
            verify_android_entry_point_topology_claim(
                apk_policy.get("entryPointTopology")
            )
        )
    if shell_required:
        expected_apk_policy["applicationShell"] = (
            verify_android_application_shell_claim(
                apk_policy.get("applicationShell")
            )
        )
    if apk_policy != expected_apk_policy:
        raise ReleaseArchiveVerificationError(
            "Android Release APK manifest differs from V1"
        )

    expected_aab_manifest: dict[str, object] = {
        **expected_badging,
    }
    expected_aab_manifest.pop("nativeAbis")
    if backup_policy_required:
        expected_aab_manifest.update(
            {
                "allowBackup": False,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
            }
        )
    if topology_required:
        expected_aab_manifest["entryPointTopology"] = (
            expected_apk_policy["entryPointTopology"]
        )
    if shell_required:
        expected_aab_manifest["applicationShell"] = (
            expected_apk_policy["applicationShell"]
        )
    aab_manifest = inspect_aab_manifest(
        aab_data,
        root,
        backup_policy_required=backup_policy_required,
        entry_point_topology_required=topology_required,
        application_shell_required=shell_required,
    )
    if aab_manifest != expected_aab_manifest:
        raise ReleaseArchiveVerificationError(
            "Android Release AAB manifest/config/resources differ from V1"
        )
    verified_bundletool_version = bundletool_version(root)

    mapping_member = (
        "BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map"
    )
    embedded_symbol_prefix = (
        "BUNDLE-METADATA/com.android.tools.build.debugsymbols/"
    )
    names = list(aab_members)
    if names.count(mapping_member) != 1:
        raise ReleaseArchiveVerificationError(
            "Android Release AAB must contain one R8 mapping"
        )
    if aab_members[mapping_member] != mapping_outputs["mapping.txt"]:
        raise ReleaseArchiveVerificationError(
            "Android Release AAB R8 mapping differs from mapping.txt"
        )
    native_names = sorted(
        name
        for name in names
        if name.startswith("base/lib/") and name.endswith(".so")
    )
    native_members = {name: aab_members[name] for name in native_names}
    embedded_symbols = {
        name.removeprefix(embedded_symbol_prefix): aab_members[name]
        for name in names
        if name.startswith(embedded_symbol_prefix)
    }
    if not native_names:
        raise ReleaseArchiveVerificationError(
            "Android Release AAB must contain JNI libraries"
        )
    if any(len(PurePosixPath(name).parts) != 4 for name in native_names):
        raise ReleaseArchiveVerificationError(
            "Android Release AAB contains a noncanonical JNI path"
        )
    native_abis = sorted(
        {PurePosixPath(name).parts[2] for name in native_names}
    )
    if native_abis != ["arm64-v8a"]:
        raise ReleaseArchiveVerificationError(
            "Android Release AAB JNI ABI set must be arm64-v8a-only"
        )
    aab_native_members_by_apk_path = {
        name.removeprefix("base/"): member
        for name, member in native_members.items()
    }
    if apk_native_members != aab_native_members_by_apk_path:
        missing = sorted(
            set(aab_native_members_by_apk_path) - set(apk_native_members)
        )
        extra = sorted(
            set(apk_native_members) - set(aab_native_members_by_apk_path)
        )
        byte_differences = sorted(
            name
            for name in (
                set(apk_native_members) & set(aab_native_members_by_apk_path)
            )
            if apk_native_members[name]
            != aab_native_members_by_apk_path[name]
        )
        raise ReleaseArchiveVerificationError(
            "Android Release APK and AAB JNI members differ; "
            f"missing={missing}, extra={extra}, "
            f"byteDifferences={byte_differences}"
        )

    llvm_readelf = find_llvm_readelf(root)
    any_merged_debug_metadata = False
    expected_symbol_build_ids: dict[str, str] = {}
    for name, member_data in native_members.items():
        _, _, abi, library_name = PurePosixPath(name).parts
        merged_path = (
            root
            / ANDROID_RELEASE_MERGED_NATIVE_RELATIVE_PATH
            / abi
            / library_name
        )
        stripped_path = (
            root
            / ANDROID_RELEASE_STRIPPED_NATIVE_RELATIVE_PATH
            / abi
            / library_name
        )
        merged_data = read_stable_regular_file(
            merged_path,
            f"Android Release merged JNI input {abi}/{library_name}",
            maximum_bytes=536_870_912,
        )
        stripped_data = read_stable_regular_file(
            stripped_path,
            f"Android Release stripped JNI output {abi}/{library_name}",
            maximum_bytes=536_870_912,
        )
        if stripped_data != member_data:
            raise ReleaseArchiveVerificationError(
                f"Android Release AAB JNI member differs from stripped "
                f"output: {name}"
            )
        build_id, has_debug_metadata = inspect_elf_bytes(
            merged_data,
            f"Android Release merged JNI input {abi}/{library_name}",
            llvm_readelf,
            root,
        )
        if build_id is None or re.fullmatch(
            r"[0-9a-f]{16,64}", build_id
        ) is None:
            raise ReleaseArchiveVerificationError(
                f"Android Release merged JNI input lacks a valid Build ID: "
                f"{name}"
            )
        if not has_debug_metadata and merged_data != stripped_data:
            raise ReleaseArchiveVerificationError(
                "Android Release pre-stripped JNI input differs without "
                f"debug metadata: {name}"
            )
        any_merged_debug_metadata |= has_debug_metadata
        expected_symbol_build_ids[f"{abi}/{library_name}.sym"] = build_id

    native_symbol_exists = (
        native_symbol_path.exists() or native_symbol_path.is_symlink()
    )
    native_symbol_directory = native_symbol_path.parent
    native_symbol_directory_exists = (
        native_symbol_directory.exists()
        or native_symbol_directory.is_symlink()
    )
    if native_symbol_directory_exists:
        require_directory_inventory(
            native_symbol_directory,
            {native_symbol_path.name} if native_symbol_exists else set(),
            "Android Release native-symbol output directory",
        )
    if native_symbol_exists:
        standalone_symbols = read_safe_zip_members(
            read_stable_regular_file(
                native_symbol_path,
                "Android Release native-symbol archive",
                maximum_bytes=1_073_741_824,
            ),
            "Android Release native-symbol archive",
        )
        if standalone_symbols != embedded_symbols:
            raise ReleaseArchiveVerificationError(
                "Android Release standalone and embedded native symbols differ"
            )
        if set(standalone_symbols) != set(expected_symbol_build_ids):
            raise ReleaseArchiveVerificationError(
                "Android Release native-symbol members differ from JNI "
                "libraries; "
                f"missing={sorted(set(expected_symbol_build_ids) - set(standalone_symbols))}, "
                f"extra={sorted(set(standalone_symbols) - set(expected_symbol_build_ids))}"
            )
        for symbol_name, symbol_data in standalone_symbols.items():
            symbol_build_id, symbol_has_debug_metadata = inspect_elf_bytes(
                symbol_data,
                f"Android Release native symbol {symbol_name}",
                llvm_readelf,
                root,
            )
            if symbol_build_id != expected_symbol_build_ids[symbol_name]:
                raise ReleaseArchiveVerificationError(
                    "Android Release native-symbol Build ID differs from "
                    f"its JNI input: {symbol_name}"
                )
            if not symbol_has_debug_metadata:
                raise ReleaseArchiveVerificationError(
                    "Android Release native symbol lacks debug metadata: "
                    f"{symbol_name}"
                )
        native_symbol_status = "available"
    else:
        if embedded_symbols:
            raise ReleaseArchiveVerificationError(
                "Android Release AAB embeds native symbols without the "
                "standalone archive"
            )
        if any_merged_debug_metadata:
            raise ReleaseArchiveVerificationError(
                "Android Release JNI inputs contain debug metadata but the "
                "native-symbol archive is missing"
            )
        native_symbol_status = "unavailable-upstream-prestripped"

    return {
        "aab": {
            "sha256": sha256(aab_data),
            "size": len(aab_data),
        },
        "apk": {
            "sha256": sha256(apk_data),
            "size": len(apk_data),
        },
        "applicationId": expected_badging["applicationId"],
        "baselineProfileCount": metadata_result["baselineProfileCount"],
        "bundletoolVersion": verified_bundletool_version,
        "mappingFileCount": len(mapping_outputs),
        "nativeLibraryCount": len(native_members),
        "nativeSymbolStatus": native_symbol_status,
        "sdkDependencyCount": dependency_count,
        "versionCode": current.build_number,
        "versionName": current.marketing_version,
    }


def verify_unsealed_macos_source_receipt(
    receipt_bytes: bytes,
    *,
    current: ReleaseVersion,
    current_source: dict[str, object],
) -> dict[str, object]:
    receipt = parse_canonical_json(
        receipt_bytes,
        "unsealed macOS source receipt",
    )
    require_exact_keys(
        receipt,
        {"build", "outputContract", "schemaVersion", "source"},
        "unsealed macOS source receipt",
    )
    if require_exact_int(
        receipt.get("schemaVersion"),
        "unsealed macOS source receipt.schemaVersion",
    ) != MACOS_UNSEALED_SOURCE_RECEIPT_SCHEMA_VERSION:
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt schemaVersion is unsupported"
        )
    if receipt.get("outputContract") != MACOS_UNSEALED_OUTPUT_CONTRACT:
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt output contract differs"
        )
    build = receipt.get("build")
    if type(build) is not dict:
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt build must be an object"
        )
    require_exact_keys(
        build,
        {"buildNumber", "configuration", "marketingVersion", "mode"},
        "unsealed macOS source receipt.build",
    )
    if (
        require_exact_int(
            build.get("buildNumber"),
            "unsealed macOS source receipt.buildNumber",
        )
        != current.build_number
        or build.get("marketingVersion") != current.marketing_version
        or build.get("configuration") != "release"
        or build.get("mode") != "unsealed-package-only"
    ):
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt build differs from the Release ledger"
        )
    source = receipt.get("source")
    if type(source) is not dict:
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt source must be an object"
        )
    require_exact_keys(
        source,
        {"algorithm", "fileCount", "sha256"},
        "unsealed macOS source receipt.source",
    )
    source_file_count = require_exact_int(
        source.get("fileCount"),
        "unsealed macOS source receipt.source.fileCount",
    )
    source_sha256 = require_string(
        source.get("sha256"),
        "unsealed macOS source receipt.source.sha256",
    )
    if re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt source SHA-256 is invalid"
        )
    expected_source = {
        "algorithm": current_source.get("algorithm"),
        "fileCount": require_exact_int(
            current_source.get("fileCount"),
            "current source fileCount",
        ),
        "sha256": require_string(
            current_source.get("sha256"),
            "current source sha256",
        ),
    }
    if (
        source.get("algorithm")
        != "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
        or source_file_count != expected_source["fileCount"]
        or source_sha256 != expected_source["sha256"]
        or source != expected_source
    ):
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt differs from current source"
        )
    return receipt


def parse_macos_dwarfdump_uuid_output(
    output: str,
    label: str,
) -> tuple[str, str]:
    matches = re.findall(
        r"^UUID:\s*([0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12})\s+"
        r"\(([^)]+)\)(?:\s+.*)?$",
        output,
        re.MULTILINE,
    )
    if len(matches) != 1:
        raise ReleaseArchiveVerificationError(
            f"expected one UUID for {label}, found {matches!r}"
        )
    return matches[0]


def verify_macos_release_build_outputs(
    root: Path = ROOT,
    *,
    output_root: Path | None = None,
) -> dict[str, object]:
    try:
        current = load_release_version_ledger(
            root / "release/version-ledger.tsv"
        )[-1]
    except (IndexError, LedgerError) as error:
        raise ReleaseArchiveVerificationError(
            f"macOS Release ledger readback failed: {error}"
        ) from error

    if output_root is None:
        output_root = root / MACOS_UNSEALED_OUTPUT_RELATIVE_PATH
    app = output_root / "AetherLink.app"
    dsym = output_root / "AetherLink.dSYM"
    source_receipt_path = output_root / MACOS_UNSEALED_SOURCE_RECEIPT_NAME
    require_directory_inventory(
        output_root,
        {app.name, dsym.name, source_receipt_path.name},
        "macOS unsealed Release output root",
    )
    source_receipt_bytes = read_stable_regular_file(
        source_receipt_path,
        "unsealed macOS source receipt",
        maximum_bytes=MACOS_UNSEALED_SOURCE_RECEIPT_MAX_BYTES,
    )
    try:
        source_receipt_mode = normalized_mode(
            source_receipt_path.lstat().st_mode
        )
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"unsealed macOS source receipt mode cannot be read: {error}"
        ) from error
    if source_receipt_mode != 0o644:
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source receipt mode must normalize to 0644"
        )
    current_source_before = current_source_snapshot_summary(root)
    source_receipt = verify_unsealed_macos_source_receipt(
        source_receipt_bytes,
        current=current,
        current_source=current_source_before,
    )
    app_files, app_modes, app_identity = read_exact_physical_tree(
        app,
        inventory=MACOS_UNSEALED_APP_INVENTORY,
        expected_files=MACOS_UNSEALED_APP_FILES,
        maximum_bytes=MACOS_UNSEALED_APP_MAX_BYTES,
        executable_files={"Contents/MacOS/AetherLink"},
        maximum_total_bytes=603_979_776,
        digest_domain=b"aetherlink-macos-unsealed-app-tree-v1\0",
        label="macOS unsealed Release app",
    )
    dsym_files, dsym_modes, dsym_identity = read_exact_physical_tree(
        dsym,
        inventory=MACOS_UNSEALED_DSYM_INVENTORY,
        expected_files=MACOS_UNSEALED_DSYM_FILES,
        maximum_bytes=MACOS_UNSEALED_DSYM_MAX_BYTES,
        executable_files=set(),
        maximum_total_bytes=1_342_177_280,
        digest_domain=b"aetherlink-macos-unsealed-dsym-tree-v1\0",
        label="macOS unsealed Release dSYM",
    )

    app_info = parse_exact_plist_dictionary(
        app_files["Contents/Info.plist"],
        expected_keys={
            "CFBundleDevelopmentRegion",
            "CFBundleExecutable",
            "CFBundleIconFile",
            "CFBundleIdentifier",
            "CFBundleLocalizations",
            "CFBundleName",
            "CFBundlePackageType",
            "CFBundleShortVersionString",
            "CFBundleVersion",
            "LSMinimumSystemVersion",
            "NSPrincipalClass",
        },
        label="macOS unsealed Release app Info.plist",
    )
    expected_app_info: dict[str, object] = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleExecutable": "AetherLink",
        "CFBundleIconFile": "AppIcon",
        "CFBundleIdentifier": "dev.aetherlink.companion",
        "CFBundleLocalizations": ["en", "ko", "ja", "zh-Hans", "fr"],
        "CFBundleName": "AetherLink",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": current.marketing_version,
        "CFBundleVersion": str(current.build_number),
        "LSMinimumSystemVersion": "14.0",
        "NSPrincipalClass": "NSApplication",
    }
    if app_info != expected_app_info:
        raise ReleaseArchiveVerificationError(
            "macOS unsealed Release app Info.plist differs from the V1 "
            "ledger and bundle contract"
        )

    resource_info_path = (
        "Contents/Resources/AetherLink_LocalAgentBridge.bundle/Info.plist"
    )
    resource_info = parse_exact_plist_dictionary(
        app_files[resource_info_path],
        expected_keys={"CFBundleDevelopmentRegion"},
        label="macOS unsealed Release resource Info.plist",
    )
    if resource_info != {"CFBundleDevelopmentRegion": "en"}:
        raise ReleaseArchiveVerificationError(
            "macOS unsealed Release resource bundle metadata differs"
        )

    dsym_info = parse_exact_plist_dictionary(
        dsym_files["Contents/Info.plist"],
        expected_keys={
            "CFBundleDevelopmentRegion",
            "CFBundleIdentifier",
            "CFBundleInfoDictionaryVersion",
            "CFBundlePackageType",
            "CFBundleShortVersionString",
            "CFBundleSignature",
            "CFBundleVersion",
        },
        label="macOS unsealed Release dSYM Info.plist",
    )
    if dsym_info != {
        "CFBundleDevelopmentRegion": "English",
        "CFBundleIdentifier": "com.apple.xcode.dsym.AetherLink",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundlePackageType": "dSYM",
        "CFBundleShortVersionString": "1.0",
        "CFBundleSignature": "????",
        "CFBundleVersion": "1",
    }:
        raise ReleaseArchiveVerificationError(
            "macOS unsealed Release dSYM metadata differs"
        )

    for locale in ("en", "fr", "ja", "ko", "zh-hans"):
        strings_path = (
            "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
            f"{locale}.lproj/Localizable.strings"
        )
        strings = app_files[strings_path]
        if b"\0" in strings or b"\r" in strings or not strings.endswith(b"\n"):
            raise ReleaseArchiveVerificationError(
                f"macOS unsealed Release locale {locale} is not LF text"
            )
        try:
            strings.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ReleaseArchiveVerificationError(
                f"macOS unsealed Release locale {locale} is not UTF-8"
            ) from error

    app_files_after, app_modes_after, app_identity_after = (
        read_exact_physical_tree(
            app,
            inventory=MACOS_UNSEALED_APP_INVENTORY,
            expected_files=MACOS_UNSEALED_APP_FILES,
            maximum_bytes=MACOS_UNSEALED_APP_MAX_BYTES,
            executable_files={"Contents/MacOS/AetherLink"},
            maximum_total_bytes=603_979_776,
            digest_domain=b"aetherlink-macos-unsealed-app-tree-v1\0",
            label="macOS unsealed Release app final read",
        )
    )
    dsym_files_after, dsym_modes_after, dsym_identity_after = (
        read_exact_physical_tree(
            dsym,
            inventory=MACOS_UNSEALED_DSYM_INVENTORY,
            expected_files=MACOS_UNSEALED_DSYM_FILES,
            maximum_bytes=MACOS_UNSEALED_DSYM_MAX_BYTES,
            executable_files=set(),
            maximum_total_bytes=1_342_177_280,
            digest_domain=b"aetherlink-macos-unsealed-dsym-tree-v1\0",
            label="macOS unsealed Release dSYM final read",
        )
    )
    if (
        app_files_after != app_files
        or app_modes_after != app_modes
        or app_identity_after != app_identity
        or dsym_files_after != dsym_files
        or dsym_modes_after != dsym_modes
        or dsym_identity_after != dsym_identity
    ):
        raise ReleaseArchiveVerificationError(
            "macOS unsealed Release output changed during readback"
        )

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-unsealed-readback-"
    ) as temporary:
        materialized_root = Path(temporary)
        materialized_app = materialized_root / "AetherLink.app"
        materialized_dsym = materialized_root / "AetherLink.dSYM"
        materialize_exact_tree(materialized_app, app_files, app_modes)
        materialize_exact_tree(materialized_dsym, dsym_files, dsym_modes)
        executable = materialized_app / "Contents/MacOS/AetherLink"
        dsym_dwarf = (
            materialized_dsym / "Contents/Resources/DWARF/AetherLink"
        )
        app_architectures = run_macos_readback_tool(
            ["/usr/bin/lipo", "-archs", str(executable)],
            materialized_root,
        ).split()
        dsym_architectures = run_macos_readback_tool(
            ["/usr/bin/lipo", "-archs", str(dsym_dwarf)],
            materialized_root,
        ).split()
        if app_architectures != ["arm64"] or dsym_architectures != ["arm64"]:
            raise ReleaseArchiveVerificationError(
                "macOS unsealed Release app and dSYM must both be thin arm64"
            )
        app_uuid, app_uuid_architecture = parse_macos_dwarfdump_uuid_output(
            run_macos_readback_tool(
                ["/usr/bin/dwarfdump", "--uuid", str(executable)],
                materialized_root,
            ),
            "materialized macOS app executable",
        )
        dsym_uuid, dsym_uuid_architecture = parse_macos_dwarfdump_uuid_output(
            run_macos_readback_tool(
                ["/usr/bin/dwarfdump", "--uuid", str(dsym_dwarf)],
                materialized_root,
            ),
            "materialized macOS dSYM DWARF",
        )
    if (
        (app_uuid, app_uuid_architecture)
        != (dsym_uuid, dsym_uuid_architecture)
        or app_uuid_architecture != "arm64"
    ):
        raise ReleaseArchiveVerificationError(
            "macOS unsealed Release app and dSYM UUID/architecture differ"
        )

    current_source_after = current_source_snapshot_summary(root)
    source_receipt_bytes_after = read_stable_regular_file(
        source_receipt_path,
        "unsealed macOS source receipt final read",
        maximum_bytes=MACOS_UNSEALED_SOURCE_RECEIPT_MAX_BYTES,
    )
    if (
        current_source_after != current_source_before
        or source_receipt_bytes_after != source_receipt_bytes
    ):
        raise ReleaseArchiveVerificationError(
            "unsealed macOS source or receipt changed during readback"
        )
    verify_unsealed_macos_source_receipt(
        source_receipt_bytes_after,
        current=current,
        current_source=current_source_after,
    )

    return {
        "app": app_identity,
        "architecture": "arm64",
        "buildNumber": current.build_number,
        "bundleId": expected_app_info["CFBundleIdentifier"],
        "dSYM": dsym_identity,
        "locales": ["en", "fr", "ja", "ko", "zh-hans"],
        "marketingVersion": current.marketing_version,
        "minimumSystemVersion": expected_app_info["LSMinimumSystemVersion"],
        "outerBundleSeal": "absent",
        "source": source_receipt["source"],
        "sourceReceipt": {
            "sha256": sha256(source_receipt_bytes),
            "size": len(source_receipt_bytes),
        },
        "uuid": app_uuid,
    }


def parse_dwarfdump_uuid(path: Path) -> tuple[str, str]:
    output = run_text(["/usr/bin/dwarfdump", "--uuid", str(path)], path.parent)
    matches = re.findall(
        r"^UUID:\s*([0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12})\s+"
        r"\(([^)]+)\)",
        output,
        re.MULTILINE,
    )
    if len(matches) != 1:
        raise ReleaseArchiveVerificationError(
            f"expected one UUID for {path}, found {matches!r}"
        )
    return matches[0]


def verify_canonical_container(
    archive_path: Path,
    external_manifest_path: Path,
) -> tuple[dict[str, object], dict[str, bytes], dict[str, int]]:
    try:
        external_manifest_bytes = external_manifest_path.read_bytes()
    except OSError as error:
        raise ReleaseArchiveVerificationError(
            f"cannot read external manifest: {error}"
        ) from error
    manifest = parse_canonical_json(
        external_manifest_bytes,
        external_manifest_path.name,
    )

    payload: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            if archive.comment:
                raise ReleaseArchiveVerificationError(
                    "release ZIP comment must be empty"
                )
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if not names or names[0] != "manifest.json":
                raise ReleaseArchiveVerificationError(
                    "manifest.json must be the first ZIP member"
                )
            if len(names) != len(set(names)):
                raise ReleaseArchiveVerificationError(
                    "release ZIP contains duplicate member paths"
                )
            for name in names:
                validate_member_path(name)
            expected_order = [
                "manifest.json",
                *sorted(names[1:], key=lambda item: item.encode("ascii")),
            ]
            if names != expected_order:
                raise ReleaseArchiveVerificationError(
                    "release ZIP member order is not canonical"
                )
            for info in infos:
                validate_member_path(info.filename)
                if info.is_dir():
                    raise ReleaseArchiveVerificationError(
                        f"directory ZIP member is not allowed: {info.filename}"
                    )
                if info.date_time != FIXED_ZIP_TIME:
                    raise ReleaseArchiveVerificationError(
                        f"ZIP timestamp is not canonical: {info.filename}"
                    )
                if info.compress_type != zipfile.ZIP_STORED:
                    raise ReleaseArchiveVerificationError(
                        f"ZIP member must use stored compression: {info.filename}"
                    )
                if info.create_system != 3 or info.extra or info.comment:
                    raise ReleaseArchiveVerificationError(
                        f"ZIP metadata is not canonical: {info.filename}"
                    )
                mode = (info.external_attr >> 16) & 0xFFFF
                if mode not in (0o644, 0o755):
                    raise ReleaseArchiveVerificationError(
                        f"ZIP mode is not canonical: {info.filename}={mode:o}"
                    )
                data = archive.read(info)
                if len(data) != info.file_size:
                    raise ReleaseArchiveVerificationError(
                        f"ZIP member size readback differs: {info.filename}"
                    )
                payload[info.filename] = data
                modes[info.filename] = mode
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseArchiveVerificationError(
            f"cannot read release ZIP: {error}"
        ) from error

    if payload["manifest.json"] != external_manifest_bytes:
        raise ReleaseArchiveVerificationError(
            "embedded and external manifests differ"
        )
    records = manifest.get("members")
    if type(records) is not list:
        raise ReleaseArchiveVerificationError("manifest members must be an array")
    expected_payload_names = set(payload) - {"manifest.json"}
    record_names: set[str] = set()
    ordered_record_names: list[str] = []
    for index, record in enumerate(records):
        if type(record) is not dict:
            raise ReleaseArchiveVerificationError(
                f"manifest member {index} must be an object"
            )
        require_exact_keys(
            record,
            {"mode", "path", "sha256", "size"},
            f"members[{index}]",
        )
        name = require_string(record.get("path"), f"members[{index}].path")
        validate_member_path(name)
        if name in record_names:
            raise ReleaseArchiveVerificationError(
                f"manifest repeats member {name!r}"
            )
        record_names.add(name)
        ordered_record_names.append(name)
        if name not in payload:
            raise ReleaseArchiveVerificationError(
                f"manifest member is absent from ZIP: {name}"
            )
        size = require_exact_int(record.get("size"), f"members[{index}].size")
        digest = require_string(
            record.get("sha256"),
            f"members[{index}].sha256",
        )
        mode_text = require_string(
            record.get("mode"),
            f"members[{index}].mode",
        )
        if re.fullmatch(r"0[67][0-7]{2}", mode_text) is None:
            raise ReleaseArchiveVerificationError(
                f"manifest mode is invalid for {name}: {mode_text!r}"
            )
        if size != len(payload[name]) or digest != sha256(payload[name]):
            raise ReleaseArchiveVerificationError(
                f"manifest byte identity differs for {name}"
            )
        if int(mode_text, 8) != modes[name]:
            raise ReleaseArchiveVerificationError(
                f"manifest mode differs from ZIP mode for {name}"
            )
    if record_names != expected_payload_names:
        missing = sorted(expected_payload_names - record_names)
        extra = sorted(record_names - expected_payload_names)
        raise ReleaseArchiveVerificationError(
            f"manifest/ZIP member set differs; missing={missing}, extra={extra}"
        )
    if ordered_record_names != sorted(
        ordered_record_names,
        key=lambda item: item.encode("ascii"),
    ):
        raise ReleaseArchiveVerificationError(
            "manifest members must be strictly ASCII-sorted"
        )
    return manifest, payload, modes


def collect_current_source_paths(root: Path = ROOT) -> tuple[str, ...]:
    candidates: set[Path] = set()
    for relative in SOURCE_REQUIRED_FILES:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ReleaseArchiveVerificationError(
                f"required current source input is missing: {relative}"
            )
        candidates.add(path)
    for relative in SOURCE_OPTIONAL_FILES:
        path = root / relative
        if path.is_symlink():
            raise ReleaseArchiveVerificationError(
                f"optional current source input is a symlink: {relative}"
            )
        if path.is_file():
            candidates.add(path)
    for relative in SOURCE_ROOTS:
        source_root = root / relative
        if source_root.is_symlink() or not source_root.is_dir():
            raise ReleaseArchiveVerificationError(
                f"required current source root is missing: {relative}"
            )
        for candidate in source_root.rglob("*"):
            if candidate.is_symlink():
                raise ReleaseArchiveVerificationError(
                    "current source root contains a symlink: "
                    f"{candidate.relative_to(root).as_posix()}"
                )
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise ReleaseArchiveVerificationError(
                    "current source root contains a special file: "
                    f"{candidate.relative_to(root).as_posix()}"
                )
            candidates.add(candidate)
    relative_paths = tuple(
        sorted(
            (
                candidate.relative_to(root).as_posix()
                for candidate in candidates
            ),
            key=lambda item: item.encode("ascii"),
        )
    )
    for relative in relative_paths:
        validate_member_path(relative)
    return relative_paths


def current_source_snapshot_summary(
    root: Path = ROOT,
) -> dict[str, object]:
    digest = hashlib.sha256()
    relative_paths = collect_current_source_paths(root)
    identity_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    for relative in relative_paths:
        path = root / relative
        try:
            before = path.lstat()
        except OSError as error:
            raise ReleaseArchiveVerificationError(
                f"current source input cannot be inspected: {relative}: {error}"
            ) from error
        data = read_stable_regular_file(
            path,
            f"current source input {relative}",
            allow_empty=True,
        )
        try:
            after = path.lstat()
        except OSError as error:
            raise ReleaseArchiveVerificationError(
                "current source input cannot be inspected after read: "
                f"{relative}: {error}"
            ) from error
        if tuple(getattr(before, field) for field in identity_fields) != tuple(
            getattr(after, field) for field in identity_fields
        ):
            raise ReleaseArchiveVerificationError(
                f"current source input changed during snapshot: {relative}"
            )
        mode = normalized_mode(after.st_mode)
        digest.update(
            relative.encode("ascii")
            + b"\0"
            + f"{mode:o}".encode("ascii")
            + b"\0"
            + str(len(data)).encode("ascii")
            + b"\0"
            + sha256(data).encode("ascii")
            + b"\n"
        )
    return {
        "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
        "fileCount": len(relative_paths),
        "sha256": digest.hexdigest(),
    }


def verify_source_snapshot(
    manifest: dict[str, object],
    payload: dict[str, bytes],
    root: Path,
    compare_current_source: bool,
) -> dict[str, tuple[int, str]]:
    source_summary = manifest.get("source")
    if type(source_summary) is not dict:
        raise ReleaseArchiveVerificationError("manifest source must be an object")
    require_exact_keys(
        source_summary,
        {
            "fileCount",
            "head",
            "member",
            "originMain",
            "snapshotAlgorithm",
            "snapshotSha256",
            "worktreeState",
        },
        "source",
    )
    source_member = require_string(
        source_summary.get("member"),
        "source.member",
    )
    if source_member != "source-files.json":
        raise ReleaseArchiveVerificationError(
            f"unexpected source manifest member: {source_member!r}"
        )
    if source_member not in payload:
        raise ReleaseArchiveVerificationError(
            f"source manifest member is absent from archive: {source_member}"
        )
    source_document = parse_canonical_json(
        payload[source_member],
        source_member,
    )
    if require_exact_int(
        source_document.get("schemaVersion"),
        "source-files.schemaVersion",
    ) != MEMBER_SCHEMA_VERSION:
        raise ReleaseArchiveVerificationError(
            "source-files schemaVersion is unsupported"
        )
    require_exact_keys(
        source_document,
        {"schemaVersion", "snapshot"},
        "source-files",
    )
    snapshot = source_document.get("snapshot")
    if type(snapshot) is not dict:
        raise ReleaseArchiveVerificationError(
            "source-files snapshot must be an object"
        )
    require_exact_keys(
        snapshot,
        {"algorithm", "fileCount", "files", "sha256"},
        "source-files.snapshot",
    )
    files = snapshot.get("files")
    if type(files) is not list or not files:
        raise ReleaseArchiveVerificationError(
            "source-files snapshot must list at least one file"
        )
    if require_exact_int(snapshot.get("fileCount"), "snapshot.fileCount") != len(
        files
    ):
        raise ReleaseArchiveVerificationError(
            "source-files fileCount does not match entries"
        )
    records = bytearray()
    archived_paths: list[str] = []
    source_identities: dict[str, tuple[int, str]] = {}
    previous_path: bytes | None = None
    for index, record in enumerate(files):
        if type(record) is not dict:
            raise ReleaseArchiveVerificationError(
                f"source file {index} must be an object"
            )
        require_exact_keys(
            record,
            {"mode", "path", "sha256", "size"},
            f"source[{index}]",
        )
        path = require_string(record.get("path"), f"source[{index}].path")
        validate_member_path(path)
        path_bytes = path.encode("ascii")
        if previous_path is not None and path_bytes <= previous_path:
            raise ReleaseArchiveVerificationError(
                "source file paths must be strictly ASCII-sorted"
            )
        previous_path = path_bytes
        archived_paths.append(path)
        mode = require_string(record.get("mode"), f"source[{index}].mode")
        size = require_exact_int(record.get("size"), f"source[{index}].size")
        digest = require_string(
            record.get("sha256"),
            f"source[{index}].sha256",
        )
        if mode not in ("0644", "0755") or re.fullmatch(
            r"[0-9a-f]{64}",
            digest,
        ) is None:
            raise ReleaseArchiveVerificationError(
                f"source file metadata is invalid for {path}"
            )
        source_identities[path] = (size, digest)
        records.extend(
            path_bytes
            + b"\0"
            + f"{int(mode, 8):o}".encode("ascii")
            + b"\0"
            + str(size).encode("ascii")
            + b"\0"
            + digest.encode("ascii")
            + b"\n"
        )
        if compare_current_source:
            current_path = root / path
            if current_path.is_symlink() or not current_path.is_file():
                raise ReleaseArchiveVerificationError(
                    f"current source input is missing or not regular: {path}"
                )
            current_data = current_path.read_bytes()
            current_mode = normalized_mode(current_path.stat().st_mode)
            if (
                len(current_data) != size
                or sha256(current_data) != digest
                or current_mode != int(mode, 8)
            ):
                raise ReleaseArchiveVerificationError(
                    f"current source input differs from archive: {path}"
                )
    if compare_current_source:
        current_paths = collect_current_source_paths(root)
        archived_path_tuple = tuple(archived_paths)
        if archived_path_tuple != current_paths:
            archived_path_set = set(archived_path_tuple)
            current_path_set = set(current_paths)
            raise ReleaseArchiveVerificationError(
                "current source path set differs from archive; "
                f"missing={sorted(archived_path_set - current_path_set)}, "
                f"extra={sorted(current_path_set - archived_path_set)}"
            )
    calculated = sha256(bytes(records))
    if snapshot.get("sha256") != calculated:
        raise ReleaseArchiveVerificationError(
            "source snapshot digest does not match source-files entries"
        )
    summary_file_count = require_exact_int(
        source_summary.get("fileCount"),
        "source.fileCount",
    )
    if (
        source_summary.get("snapshotSha256") != calculated
        or source_summary.get("snapshotAlgorithm")
        != "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
        or snapshot.get("algorithm")
        != "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
        or summary_file_count != len(files)
    ):
        raise ReleaseArchiveVerificationError(
            "manifest source summary differs from source-files snapshot"
        )
    for key in ("head", "originMain"):
        if re.fullmatch(
            r"[0-9a-f]{40}",
            require_string(source_summary.get(key), f"source.{key}"),
        ) is None:
            raise ReleaseArchiveVerificationError(
                f"manifest source {key} is not a Git object ID"
            )
    if source_summary.get("worktreeState") not in (
        "clean",
        "dirty-content-snapshot",
    ):
        raise ReleaseArchiveVerificationError(
            "manifest source worktreeState is unsupported"
        )
    return source_identities


def verify_android_relationships(
    manifest: dict[str, object],
    payload: dict[str, bytes],
) -> None:
    release = manifest.get("release")
    if type(release) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest release metadata is missing"
        )
    build_number = require_exact_int(
        release.get("buildNumber"),
        "release.buildNumber",
    )
    if build_number >= 4:
        validate_canonical_r8_configuration(
            payload["android/mapping/configuration.txt"],
            "android/mapping/configuration.txt",
        )
    mapping_prt_path = "android/mapping/mapping.prt"
    if (
        canonicalize_r8_mapping_prt(
            payload[mapping_prt_path],
            mapping_prt_path,
        )
        != payload[mapping_prt_path]
    ):
        raise ReleaseArchiveVerificationError(
            "archived R8 mapping partition ZIP is not canonical"
        )
    resources_path = "android/mapping/resources.txt"
    canonical_resources = (
        canonicalize_r8_line_artifact(
            payload[resources_path],
            resources_path,
        )
        if build_number <= 4
        else canonicalize_r8_resources(
            payload[resources_path],
            resources_path,
        )
    )
    if canonical_resources != payload[resources_path]:
        raise ReleaseArchiveVerificationError(
            f"archived R8 resource artifact is not canonical: {resources_path}"
        )
    seeds_path = "android/mapping/seeds.txt"
    if (
        canonicalize_r8_line_artifact(payload[seeds_path], seeds_path)
        != payload[seeds_path]
    ):
        raise ReleaseArchiveVerificationError(
            f"archived R8 line artifact is not canonical: {seeds_path}"
        )

    platforms = manifest.get("platforms")
    if type(platforms) is not dict or type(platforms.get("android")) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest Android metadata is missing"
        )
    require_exact_keys(platforms, {"android", "macos"}, "platforms")
    android = platforms["android"]
    assert isinstance(android, dict)
    release = manifest["release"]
    assert isinstance(release, dict)
    build_number = require_exact_int(
        release.get("buildNumber"),
        "release.buildNumber",
    )
    marketing_version = require_string(
        release.get("marketingVersion"),
        "release.marketingVersion",
    )
    require_exact_keys(
        android,
        expected_android_manifest_keys(build_number),
        "platforms.android",
    )
    verify_bundle_structure_validation_claim(android, build_number)
    if android.get("abis") != ["arm64-v8a"]:
        raise ReleaseArchiveVerificationError(
            "Android archived ABI set must be exactly arm64-v8a"
        )
    if android.get("applicationId") != "com.localagentbridge.android":
        raise ReleaseArchiveVerificationError(
            "Android archived application ID is unexpected"
        )
    if type(android.get("mappingEmbeddedByteIdentical")) is not bool or not android[
        "mappingEmbeddedByteIdentical"
    ]:
        raise ReleaseArchiveVerificationError(
            "Android mapping parity claim must be exactly true"
        )
    min_sdk = require_exact_int(android.get("minSdk"), "android.minSdk")
    target_sdk = require_exact_int(android.get("targetSdk"), "android.targetSdk")
    if (min_sdk, target_sdk) != (26, 36):
        raise ReleaseArchiveVerificationError(
            "Android archived SDK range differs from V1 contract"
        )
    android_version_code = require_exact_int(
        android.get("versionCode"),
        "platforms.android.versionCode",
    )
    if (
        android_version_code != build_number
        or android.get("versionName") != marketing_version
    ):
        raise ReleaseArchiveVerificationError(
            "Android archived version differs from release"
        )
    if android.get("signatureState") != "unsigned":
        raise ReleaseArchiveVerificationError(
            "local Android archive must remain explicitly unsigned"
        )
    bundle_manifest_readback = android.get("bundleManifestReadback")
    if type(bundle_manifest_readback) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android AAB manifest readback claim is missing"
        )
    require_exact_keys(
        bundle_manifest_readback,
        {"member", "tool", "verifiedFields"},
        "platforms.android.bundleManifestReadback",
    )
    backup_policy_required = (
        build_number >= ANDROID_BACKUP_POLICY_BUILD
    )
    entry_point_topology_required = (
        build_number >= ANDROID_ENTRY_POINT_TOPOLOGY_BUILD
    )
    application_shell_required = (
        build_number >= ANDROID_APPLICATION_SHELL_BUILD
    )
    entry_point_topology: dict[str, object] | None = None
    if entry_point_topology_required:
        entry_point_topology = (
            verify_android_entry_point_topology_claim(
                android.get("entryPointTopology")
            )
        )
    application_shell: dict[str, object] | None = None
    if application_shell_required:
        application_shell = verify_android_application_shell_claim(
            android.get("applicationShell")
        )
    expected_verified_fields = [
        *BASE_BUNDLE_MANIFEST_VERIFIED_FIELDS,
        *(
            BACKUP_POLICY_BUNDLE_MANIFEST_VERIFIED_FIELDS
            if backup_policy_required
            else ()
        ),
        *(
            ENTRY_POINT_TOPOLOGY_MANIFEST_VERIFIED_FIELDS
            if entry_point_topology_required
            else ()
        ),
        *(
            APPLICATION_SHELL_MANIFEST_VERIFIED_FIELDS
            if application_shell_required
            else ()
        ),
    ]
    if bundle_manifest_readback != {
        "member": "android/bundle/app-release.aab",
        "tool": (
            "bundletool dump manifest + resources + config + "
            "universal APK readback"
            if application_shell_required
            else "bundletool dump manifest"
        ),
        "verifiedFields": expected_verified_fields,
    }:
        raise ReleaseArchiveVerificationError(
            "Android AAB manifest readback claim is not canonical"
        )
    if backup_policy_required:
        apk_manifest_readback = android.get("apkManifestReadback")
        if type(apk_manifest_readback) is not dict:
            raise ReleaseArchiveVerificationError(
                "Android APK manifest readback claim is missing"
            )
        require_exact_keys(
            apk_manifest_readback,
            {"member", "tool", "verifiedFields"},
            "platforms.android.apkManifestReadback",
        )
        if apk_manifest_readback != {
            "member": "android/apk/app-release-unsigned.apk",
            "tool": (
                "aapt2 dump xmltree + resources"
                if application_shell_required
                else "aapt2 dump xmltree + resources --no-values"
            ),
            "verifiedFields": [
                *BACKUP_POLICY_APK_MANIFEST_VERIFIED_FIELDS,
                *(
                    ENTRY_POINT_TOPOLOGY_MANIFEST_VERIFIED_FIELDS
                    if entry_point_topology_required
                    else ()
                ),
                *(
                    APPLICATION_SHELL_MANIFEST_VERIFIED_FIELDS
                    if application_shell_required
                    else ()
                ),
            ],
        }:
            raise ReleaseArchiveVerificationError(
                "Android APK manifest readback claim is not canonical"
            )

    try:
        apk_metadata = json.loads(
            payload["android/apk/output-metadata.json"].decode("utf-8")
        )
        if type(apk_metadata) is not dict:
            raise TypeError("APK metadata root must be an object")
        elements = apk_metadata["elements"]
        if type(elements) is not list or len(elements) != 1:
            raise TypeError("APK metadata must contain exactly one element")
        apk_element = elements[0]
        if type(apk_element) is not dict:
            raise TypeError("APK metadata element must be an object")
    except (
        KeyError,
        IndexError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise ReleaseArchiveVerificationError(
            f"archived Android output metadata is invalid: {error}"
        ) from error
    if (
        apk_metadata.get("applicationId") != android["applicationId"]
        or apk_metadata.get("variantName") != "release"
    ):
        raise ReleaseArchiveVerificationError(
            "archived APK output metadata identity/shape differs"
        )
    if (
        type(apk_element.get("versionCode")) is not int
        or apk_element["versionCode"] != build_number
        or apk_element.get("versionName") != marketing_version
    ):
        raise ReleaseArchiveVerificationError(
            "archived APK metadata version differs from release"
        )
    apk_badging = inspect_apk_badging(
        payload["android/apk/app-release-unsigned.apk"]
    )
    if apk_badging != {
        "applicationId": android["applicationId"],
        "minSdk": min_sdk,
        "nativeAbis": android["abis"],
        "targetSdk": target_sdk,
        "versionCode": build_number,
        "versionName": marketing_version,
    }:
        raise ReleaseArchiveVerificationError(
            "independent archived APK badging differs from manifest"
        )
    if backup_policy_required:
        apk_backup_policy = inspect_apk_backup_policy(
            payload["android/apk/app-release-unsigned.apk"],
            entry_point_topology_required=(
                entry_point_topology_required
            ),
            application_shell_required=application_shell_required,
        )
        expected_apk_manifest: dict[str, object] = {
            "allowBackup": False,
            "dataExtractionRules": "@xml/data_extraction_rules",
            "fullBackupContent": "@xml/backup_rules",
        }
        if entry_point_topology_required:
            expected_apk_manifest["entryPointTopology"] = (
                entry_point_topology
            )
        if application_shell_required:
            expected_apk_manifest["applicationShell"] = application_shell
        if apk_backup_policy != expected_apk_manifest:
            raise ReleaseArchiveVerificationError(
                "independent archived APK manifest differs "
                "from the V1 contract"
            )

    mapping = payload["android/mapping/mapping.txt"]
    aab = payload["android/bundle/app-release.aab"]
    aab_manifest = inspect_aab_manifest(
        aab,
        backup_policy_required=backup_policy_required,
        entry_point_topology_required=entry_point_topology_required,
        application_shell_required=application_shell_required,
    )
    expected_aab_manifest = {
        "applicationId": android["applicationId"],
        "minSdk": min_sdk,
        "targetSdk": target_sdk,
        "versionCode": build_number,
        "versionName": marketing_version,
    }
    if backup_policy_required:
        expected_aab_manifest.update(
            {
                "allowBackup": False,
                "dataExtractionRules": "@xml/data_extraction_rules",
                "fullBackupContent": "@xml/backup_rules",
            }
        )
    if entry_point_topology_required:
        expected_aab_manifest["entryPointTopology"] = (
            entry_point_topology
        )
    if application_shell_required:
        expected_aab_manifest["applicationShell"] = application_shell
    if aab_manifest != expected_aab_manifest:
        raise ReleaseArchiveVerificationError(
            "independent archived AAB manifest differs from release metadata"
        )
    try:
        with zipfile.ZipFile(io.BytesIO(aab), "r") as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)):
                raise ReleaseArchiveVerificationError(
                    "archived AAB contains duplicate members"
                )
            if (
                bundle.read(
                    "BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map"
                )
                != mapping
            ):
                raise ReleaseArchiveVerificationError(
                    "archived AAB mapping differs from archived mapping.txt"
                )
            native_names = sorted(
                name
                for name in names
                if name.startswith("base/lib/") and name.endswith(".so")
            )
            native_data = {name: bundle.read(name) for name in native_names}
            embedded_symbol_names = [
                name
                for name in names
                if name.startswith(
                    "BUNDLE-METADATA/com.android.tools.build.debugsymbols/"
                )
            ]
    except (KeyError, zipfile.BadZipFile) as error:
        raise ReleaseArchiveVerificationError(
            f"archived AAB is invalid: {error}"
        ) from error
    if not native_names:
        raise ReleaseArchiveVerificationError("archived AAB has no JNI members")
    if any(len(PurePosixPath(name).parts) != 4 for name in native_names):
        raise ReleaseArchiveVerificationError(
            "archived AAB contains a noncanonical JNI member path"
        )
    if sorted({PurePosixPath(name).parts[2] for name in native_names}) != [
        "arm64-v8a"
    ]:
        raise ReleaseArchiveVerificationError(
            "archived AAB JNI ABI set is not arm64-v8a-only"
        )
    records = android.get("nativeLibraries")
    if type(records) is not list or len(records) != len(native_names):
        raise ReleaseArchiveVerificationError(
            "Android native-library manifest count differs from AAB"
        )
    record_map = {
        require_string(record.get("memberPath"), "native.memberPath"): record
        for record in records
        if type(record) is dict
    }
    if set(record_map) != set(native_names):
        raise ReleaseArchiveVerificationError(
            "Android native-library manifest paths differ from AAB"
        )
    for name in native_names:
        record = record_map[name]
        require_exact_keys(
            record,
            {
                "abi",
                "buildId",
                "memberPath",
                "mergedInputSha256",
                "name",
                "sha256",
                "size",
            },
            f"nativeLibraries[{name}]",
        )
        record_size = require_exact_int(
            record.get("size"),
            f"nativeLibraries[{name}].size",
        )
        if (
            record_size != len(native_data[name])
            or record.get("sha256") != sha256(native_data[name])
        ):
            raise ReleaseArchiveVerificationError(
                f"Android native-library identity differs for {name}"
            )
        _, _, abi, library_name = PurePosixPath(name).parts
        if record.get("abi") != abi or record.get("name") != library_name:
            raise ReleaseArchiveVerificationError(
                f"Android native-library metadata differs for {name}"
            )
        build_id = record.get("buildId")
        if type(build_id) is not str or re.fullmatch(
            r"[0-9a-f]{16,64}",
            build_id,
        ) is None:
            raise ReleaseArchiveVerificationError(
                f"Android native-library Build ID is invalid for {name}"
            )
        if re.fullmatch(
            r"[0-9a-f]{64}",
            require_string(
                record.get("mergedInputSha256"),
                f"nativeLibraries[{name}].mergedInputSha256",
            ),
        ) is None:
            raise ReleaseArchiveVerificationError(
                f"Android merged native-library digest is invalid for {name}"
            )
    native_symbols = android.get("nativeSymbols")
    if type(native_symbols) is not dict:
        raise ReleaseArchiveVerificationError(
            "Android native-symbol status is missing"
        )
    require_exact_keys(
        native_symbols,
        {"archiveMember", "requestedLevel", "status"},
        "platforms.android.nativeSymbols",
    )
    if native_symbols.get("requestedLevel") != "SYMBOL_TABLE":
        raise ReleaseArchiveVerificationError(
            "Android native-symbol requested level is unexpected"
        )
    status = native_symbols.get("status")
    if status == "unavailable-upstream-prestripped":
        if native_symbols.get("archiveMember") is not None or embedded_symbol_names:
            raise ReleaseArchiveVerificationError(
                "unavailable native-symbol status conflicts with archived symbols"
            )
    elif status == "available":
        member = native_symbols.get("archiveMember")
        if member not in payload or not embedded_symbol_names:
            raise ReleaseArchiveVerificationError(
                "available native-symbol status lacks both symbol payloads"
            )
    else:
        raise ReleaseArchiveVerificationError(
            f"unsupported Android native-symbol status: {status!r}"
        )
    status_document = parse_canonical_json(
        payload["android/native-symbol-status.json"],
        "android/native-symbol-status.json",
    )
    require_exact_keys(
        status_document,
        {"nativeLibraries", "nativeSymbols", "schemaVersion"},
        "android/native-symbol-status.json",
    )
    if require_exact_int(
        status_document.get("schemaVersion"),
        "android/native-symbol-status.schemaVersion",
    ) != MEMBER_SCHEMA_VERSION:
        raise ReleaseArchiveVerificationError(
            "Android native-symbol status schema is unsupported"
        )
    if (
        status_document.get("nativeLibraries") != records
        or status_document.get("nativeSymbols") != native_symbols
    ):
        raise ReleaseArchiveVerificationError(
            "native-symbol status member differs from main manifest"
        )


def extract_macos_payload(
    payload: dict[str, bytes],
    modes: dict[str, int],
    destination: Path,
) -> tuple[Path, Path]:
    prefixes = (
        "macos/AetherLink.app/",
        "macos/AetherLink.dSYM/",
    )
    for name, data in payload.items():
        if not name.startswith(prefixes):
            continue
        validate_member_path(name)
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(modes[name])
    return (
        destination / "macos/AetherLink.app",
        destination / "macos/AetherLink.dSYM",
    )


def verify_macos_relationships(
    manifest: dict[str, object],
    payload: dict[str, bytes],
    modes: dict[str, int],
) -> None:
    platforms = manifest["platforms"]
    assert isinstance(platforms, dict)
    macos = platforms.get("macos")
    if type(macos) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest macOS metadata is missing"
        )
    require_exact_keys(
        macos,
        {
            "architectures",
            "buildNumber",
            "bundleId",
            "dSYM",
            "locales",
            "marketingVersion",
            "minimumSystemVersion",
            "signatureState",
            "uuid",
        },
        "platforms.macos",
    )
    if type(macos.get("dSYM")) is not dict:
        raise ReleaseArchiveVerificationError("manifest macOS dSYM is missing")
    require_exact_keys(
        macos["dSYM"],
        {"architecture", "uuid"},
        "platforms.macos.dSYM",
    )
    release = manifest["release"]
    assert isinstance(release, dict)
    macos_build_number = require_exact_int(
        macos.get("buildNumber"),
        "platforms.macos.buildNumber",
    )
    if macos.get("architectures") != ["arm64"]:
        raise ReleaseArchiveVerificationError(
            "macOS archived architecture must be thin arm64"
        )
    if macos.get("bundleId") != "dev.aetherlink.companion":
        raise ReleaseArchiveVerificationError(
            "macOS archived bundle ID is unexpected"
        )
    if (
        macos.get("marketingVersion") != release.get("marketingVersion")
        or macos_build_number != release.get("buildNumber")
    ):
        raise ReleaseArchiveVerificationError(
            "macOS archived version differs from release"
        )
    if (
        macos.get("minimumSystemVersion") != "14.0"
        or macos.get("signatureState") != "ad-hoc-local"
        or macos.get("locales") != ["en", "fr", "ja", "ko", "zh-hans"]
    ):
        raise ReleaseArchiveVerificationError(
            "macOS archived minimum system, signature, or locale contract differs"
        )
    plist_member = "macos/AetherLink.app/Contents/Info.plist"
    try:
        info = plistlib.loads(payload[plist_member])
    except (KeyError, plistlib.InvalidFileException) as error:
        raise ReleaseArchiveVerificationError(
            f"archived macOS Info.plist is invalid: {error}"
        ) from error
    if (
        info.get("CFBundleIdentifier") != macos["bundleId"]
        or info.get("CFBundleShortVersionString")
        != macos["marketingVersion"]
        or info.get("CFBundleVersion") != str(macos_build_number)
        or info.get("LSMinimumSystemVersion") != macos["minimumSystemVersion"]
    ):
        raise ReleaseArchiveVerificationError(
            "archived macOS Info.plist differs from manifest"
        )

    with tempfile.TemporaryDirectory(prefix="aetherlink-release-readback-") as temp:
        app, dsym = extract_macos_payload(payload, modes, Path(temp))
        run_text(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
            Path(temp),
        )
        signature_details = run_text(
            ["/usr/bin/codesign", "-dv", "--verbose=4", str(app)],
            Path(temp),
        )
        if "Signature=adhoc" not in signature_details:
            raise ReleaseArchiveVerificationError(
                "extracted macOS app is not ad-hoc signed"
            )
        app_uuid, app_arch = parse_dwarfdump_uuid(
            app / "Contents/MacOS/AetherLink"
        )
        dsym_uuid, dsym_arch = parse_dwarfdump_uuid(dsym)
        if (app_uuid, app_arch) != (dsym_uuid, dsym_arch):
            raise ReleaseArchiveVerificationError(
                "extracted app and dSYM UUID/architecture differ"
            )
        if (
            app_uuid != macos.get("uuid")
            or app_arch != "arm64"
            or macos.get("dSYM")
            != {"architecture": dsym_arch, "uuid": dsym_uuid}
        ):
            raise ReleaseArchiveVerificationError(
                "extracted macOS UUID metadata differs from manifest"
            )


def expected_release_id() -> str:
    current = load_release_version_ledger()[-1]
    return (
        f"aetherlink-{current.marketing_version}+{current.build_number}-"
        "local-v1"
    )


def ledger_prefix_bytes_for_release(
    build_number: int,
    marketing_version: str,
    ledger_path: Path = ROOT / "release/version-ledger.tsv",
) -> tuple[bytes, bool]:
    try:
        entries = load_release_version_ledger(ledger_path)
        ledger_bytes = ledger_path.read_bytes()
    except (LedgerError, OSError) as error:
        raise ReleaseArchiveVerificationError(
            f"cannot read canonical release ledger: {error}"
        ) from error
    matching_indices = [
        index
        for index, entry in enumerate(entries)
        if (
            entry.build_number == build_number
            and entry.marketing_version == marketing_version
        )
    ]
    if len(matching_indices) != 1:
        raise ReleaseArchiveVerificationError(
            "release archive version is not an exact ledger entry"
        )
    lines = ledger_bytes.splitlines(keepends=True)
    if len(lines) != len(entries) + 1:
        raise ReleaseArchiveVerificationError(
            "canonical release ledger line count is inconsistent"
        )
    matching_index = matching_indices[0]
    prefix = b"".join(lines[: matching_index + 2])
    return prefix, matching_index == len(entries) - 1


def verify_release_mode(
    *,
    is_current_release: bool,
    require_current_release: bool,
) -> None:
    if is_current_release == require_current_release:
        return
    if require_current_release:
        raise ReleaseArchiveVerificationError(
            "release archive version differs from current ledger"
        )
    raise ReleaseArchiveVerificationError(
        "historical readback requires a non-current ledger entry"
    )


def verify_dependency_lock_source_identity(
    *,
    path: str,
    size: int,
    digest: str,
    source_identities: dict[str, tuple[int, str]],
) -> None:
    if source_identities.get(path) != (size, digest):
        raise ReleaseArchiveVerificationError(
            "manifest Gradle lock identity differs from archived source "
            f"snapshot: {path}"
        )


def manifest_contract_for_build(build_number: int) -> tuple[int, set[str]]:
    if type(build_number) is not int or build_number < 1:
        raise ReleaseArchiveVerificationError(
            "manifest build number is invalid for schema selection"
        )
    keys = {
        "archive",
        "channel",
        "dependencyLocking",
        "ledger",
        "members",
        "platforms",
        "product",
        "release",
        "schemaVersion",
        "source",
        "toolchains",
    }
    if build_number <= 6:
        return LEGACY_MANIFEST_SCHEMA_VERSION, keys
    return CURRENT_MANIFEST_SCHEMA_VERSION, keys | {"compliance"}


def verify_manifest_header(
    manifest: dict[str, object],
    payload: dict[str, bytes],
    archive_id: str,
    *,
    require_current_release: bool,
    source_identities: dict[str, tuple[int, str]],
) -> None:
    release_hint = manifest.get("release")
    if type(release_hint) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest release metadata must be an object"
        )
    build_number_hint = require_exact_int(
        release_hint.get("buildNumber"),
        "release.buildNumber",
    )
    expected_schema, expected_keys = manifest_contract_for_build(
        build_number_hint
    )
    require_exact_keys(
        manifest,
        expected_keys,
        "manifest",
    )
    if require_exact_int(
        manifest.get("schemaVersion"),
        "manifest.schemaVersion",
    ) != expected_schema:
        raise ReleaseArchiveVerificationError(
            "release archive schemaVersion differs from its build contract"
        )
    compliance_members = {
        name for name in payload if name.startswith("compliance/")
    }
    if build_number_hint <= 6 and compliance_members:
        raise ReleaseArchiveVerificationError(
            "historical schema-1 archive contains compliance members"
        )
    if manifest.get("product") != "AetherLink" or manifest.get("channel") != "local":
        raise ReleaseArchiveVerificationError(
            "release archive product/channel is unexpected"
        )
    dependency_locking = manifest.get("dependencyLocking")
    if type(dependency_locking) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest dependencyLocking must be an object"
        )
    require_exact_keys(
        dependency_locking,
        {"gradle", "swiftPackageManager"},
        "dependencyLocking",
    )
    gradle_locking = dependency_locking.get("gradle")
    if type(gradle_locking) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest Gradle locking metadata must be an object"
        )
    require_exact_keys(
        gradle_locking,
        {
            "ignoredDependencies",
            "lockFiles",
            "strictProperty",
            "verificationScope",
        },
        "dependencyLocking.gradle",
    )
    if gradle_locking.get("ignoredDependencies") != list(
        GRADLE_IGNORED_DEPENDENCIES
    ):
        raise ReleaseArchiveVerificationError(
            "manifest Gradle ignored-dependency inventory is unexpected"
        )
    lock_files = gradle_locking.get("lockFiles")
    if type(lock_files) is not list or len(lock_files) != len(
        GRADLE_LOCK_PATHS
    ):
        raise ReleaseArchiveVerificationError(
            "manifest Gradle lock-file inventory has an unexpected count"
        )
    for index, record in enumerate(lock_files):
        if type(record) is not dict:
            raise ReleaseArchiveVerificationError(
                f"manifest Gradle lock record {index} must be an object"
            )
        require_exact_keys(
            record,
            {
                "configurationCount",
                "emptyConfigurationCount",
                "moduleCount",
                "path",
                "sha256",
                "size",
            },
            f"dependencyLocking.gradle.lockFiles[{index}]",
        )
        for key in (
            "configurationCount",
            "emptyConfigurationCount",
            "moduleCount",
            "size",
        ):
            value = require_exact_int(
                record.get(key),
                f"dependencyLocking.gradle.lockFiles[{index}].{key}",
            )
            minimum = (
                0
                if key in ("emptyConfigurationCount", "moduleCount")
                else 1
            )
            if value < minimum:
                raise ReleaseArchiveVerificationError(
                    f"manifest Gradle lock record {key} is out of range"
                )
        if (
            record["emptyConfigurationCount"]
            > record["configurationCount"]
            or (
                record["moduleCount"] == 0
                and record["emptyConfigurationCount"] == 0
            )
        ):
            raise ReleaseArchiveVerificationError(
                "manifest Gradle lock record counts are inconsistent"
            )
        lock_path = require_string(
            record.get("path"),
            f"dependencyLocking.gradle.lockFiles[{index}].path",
        )
        lock_digest = require_string(
            record.get("sha256"),
            f"dependencyLocking.gradle.lockFiles[{index}].sha256",
        )
        lock_size = require_exact_int(
            record.get("size"),
            f"dependencyLocking.gradle.lockFiles[{index}].size",
        )
        if (
            lock_path != GRADLE_LOCK_PATHS[index]
            or re.fullmatch(r"[0-9a-f]{64}", lock_digest) is None
        ):
            raise ReleaseArchiveVerificationError(
                "manifest Gradle lock identity is invalid"
            )
        verify_dependency_lock_source_identity(
            path=lock_path,
            size=lock_size,
            digest=lock_digest,
            source_identities=source_identities,
        )
    swift_locking = dependency_locking.get("swiftPackageManager")
    if type(swift_locking) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest SwiftPM locking metadata must be an object"
        )
    require_exact_keys(
        swift_locking,
        {"externalDependencyCount", "packageResolved", "status"},
        "dependencyLocking.swiftPackageManager",
    )
    if (
        require_exact_int(
            swift_locking.get("externalDependencyCount"),
            "dependencyLocking.swiftPackageManager.externalDependencyCount",
        )
        != 0
        or swift_locking.get("packageResolved") is not None
        or swift_locking.get("status")
        != "not-applicable-no-external-dependencies"
    ):
        raise ReleaseArchiveVerificationError(
            "manifest SwiftPM zero-dependency state is unexpected"
        )
    if (
        require_current_release
        and dependency_locking != dependency_locking_metadata()
    ):
        raise ReleaseArchiveVerificationError(
            "manifest dependency-lock inventory differs from current readback"
        )
    release = manifest.get("release")
    if type(release) is not dict or release.get("releaseId") != archive_id:
        raise ReleaseArchiveVerificationError(
            "release archive ID differs from directory"
        )
    require_exact_keys(
        release,
        {"buildNumber", "marketingVersion", "releaseId"},
        "release",
    )
    build_number = require_exact_int(
        release.get("buildNumber"),
        "release.buildNumber",
    )
    marketing_version = require_string(
        release.get("marketingVersion"),
        "release.marketingVersion",
    )
    derived_archive_id = (
        f"aetherlink-{marketing_version}+{build_number}-local-v1"
    )
    if archive_id != derived_archive_id:
        raise ReleaseArchiveVerificationError(
            "release archive ID differs from its version fields"
        )
    ledger_prefix, is_current_release = ledger_prefix_bytes_for_release(
        build_number,
        marketing_version,
    )
    verify_release_mode(
        is_current_release=is_current_release,
        require_current_release=require_current_release,
    )

    archive = manifest.get("archive")
    if type(archive) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest archive metadata must be an object"
        )
    require_exact_keys(
        archive,
        {
            "artifactPathPolicy",
            "compression",
            "entryOrder",
            "entryTimestamp",
            "extendedAttributesIncluded",
            "memberCountExcludingManifest",
            "normalizations",
            "reproducibilityScope",
        },
        "archive",
    )
    member_count = require_exact_int(
        archive.get("memberCountExcludingManifest"),
        "archive.memberCountExcludingManifest",
    )
    expected_archive_metadata = {
        "artifactPathPolicy": (
            "raw-paths-with-declared-r8-byte-normalization"
        ),
        "compression": "stored",
        "entryOrder": "manifest-first-then-ascii-path",
        "entryTimestamp": "1980-01-01T00:00:00",
        "extendedAttributesIncluded": False,
        "normalizations": list(
            archive_normalizations_for_build(build_number)
        ),
        "reproducibilityScope": (
            "canonical-container-for-normalized-release-inputs"
        ),
    }
    for key, value in expected_archive_metadata.items():
        actual = archive.get(key)
        if type(actual) is not type(value) or actual != value:
            raise ReleaseArchiveVerificationError(
                f"manifest archive metadata differs for {key}"
            )
    if member_count != len(payload) - 1:
        raise ReleaseArchiveVerificationError(
            "manifest archive member count differs from ZIP"
        )

    ledger = manifest.get("ledger")
    if type(ledger) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest ledger metadata must be an object"
        )
    require_exact_keys(ledger, {"path", "sha256", "size"}, "ledger")
    if (
        ledger.get("path") != "release/version-ledger.tsv"
        or require_exact_int(ledger.get("size"), "ledger.size")
        != len(ledger_prefix)
        or ledger.get("sha256") != sha256(ledger_prefix)
    ):
        raise ReleaseArchiveVerificationError(
            "manifest ledger identity differs from its exact append-only prefix"
        )

    toolchains = manifest.get("toolchains")
    if type(toolchains) is not dict:
        raise ReleaseArchiveVerificationError(
            "manifest toolchains metadata must be an object"
        )
    expected_toolchain_keys = {
        "aapt2",
        "androidGradlePlugin",
        "bundletool",
        "gradleWrapper",
        "java",
        "kotlin",
        "swift",
        "swiftTools",
        "xcode",
    }
    if set(toolchains) != expected_toolchain_keys:
        raise ReleaseArchiveVerificationError(
            "manifest toolchain field set is not canonical"
        )
    for key in sorted(expected_toolchain_keys):
        if not require_string(toolchains[key], f"toolchains.{key}"):
            raise ReleaseArchiveVerificationError(
                f"manifest toolchain value is empty: {key}"
            )
    if toolchains["bundletool"] != bundletool_version():
        raise ReleaseArchiveVerificationError(
            "manifest bundletool version differs from independent readback"
        )


def verify_release_archive(
    archive_directory: Path,
    *,
    compare_current_source: bool = True,
    require_current_release: bool = True,
) -> dict[str, object]:
    archive_id = archive_directory.name
    if not require_current_release and compare_current_source:
        raise ReleaseArchiveVerificationError(
            "historical readback cannot compare against current source"
        )
    if require_current_release and archive_id != expected_release_id():
        raise ReleaseArchiveVerificationError(
            f"release archive directory name differs from ledger: {archive_id}"
        )
    archive_name = f"{archive_id}.zip"
    manifest_name = f"{archive_id}.manifest.json"
    checksum_name = f"{archive_id}.zip.sha256"
    expected_names = {archive_name, manifest_name, checksum_name}
    if archive_directory.is_symlink() or not archive_directory.is_dir():
        raise ReleaseArchiveVerificationError(
            f"release archive is not a real directory: {archive_directory}"
        )
    actual_names = {path.name for path in archive_directory.iterdir()}
    if actual_names != expected_names:
        raise ReleaseArchiveVerificationError(
            f"release archive sidecar set differs: {sorted(actual_names)}"
        )
    archive_path = archive_directory / archive_name
    manifest_path = archive_directory / manifest_name
    checksum_path = archive_directory / checksum_name
    for path in (archive_path, manifest_path, checksum_path):
        if path.is_symlink() or not path.is_file():
            raise ReleaseArchiveVerificationError(
                f"release archive sidecar is not a regular file: {path}"
            )
    archive_bytes = archive_path.read_bytes()
    checksum_bytes = checksum_path.read_bytes()
    expected_checksum = (
        f"{sha256(archive_bytes)}  {archive_name}\n".encode("ascii")
    )
    if checksum_bytes != expected_checksum:
        raise ReleaseArchiveVerificationError(
            "release archive SHA-256 sidecar differs"
        )

    manifest, payload, modes = verify_canonical_container(
        archive_path,
        manifest_path,
    )
    source_identities = verify_source_snapshot(
        manifest,
        payload,
        ROOT,
        compare_current_source,
    )
    verify_manifest_header(
        manifest,
        payload,
        archive_id,
        require_current_release=require_current_release,
        source_identities=source_identities,
    )
    release = manifest["release"]
    dependency_locking = manifest["dependencyLocking"]
    assert isinstance(release, dict)
    assert isinstance(dependency_locking, dict)
    gradle_locking = dependency_locking["gradle"]
    assert isinstance(gradle_locking, dict)
    build_number = require_exact_int(
        release.get("buildNumber"),
        "release.buildNumber",
    )
    if build_number >= 7:
        try:
            verify_release_compliance(
                compliance=manifest.get("compliance"),
                payload=payload,
                source_identities=source_identities,
                manifest_lock_files=gradle_locking["lockFiles"],
                marketing_version=require_string(
                    release.get("marketingVersion"),
                    "release.marketingVersion",
                ),
                build_number=build_number,
                source_snapshot_sha256=require_string(
                    manifest["source"].get("snapshotSha256"),
                    "source.snapshotSha256",
                ),
                root=ROOT,
                compare_current_source=compare_current_source,
            )
        except ComplianceVerificationError as error:
            raise ReleaseArchiveVerificationError(
                f"release compliance readback failed: {error}"
            ) from error
    verify_android_relationships(manifest, payload)
    verify_macos_relationships(manifest, payload, modes)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / expected_release_id(),
    )
    readback_mode = parser.add_mutually_exclusive_group()
    readback_mode.add_argument(
        "--android-build-outputs",
        action="store_true",
        help=(
            "independently verify current Gradle APK/AAB Release outputs "
            "without requiring a macOS archive"
        ),
    )
    readback_mode.add_argument(
        "--macos-build-outputs",
        action="store_true",
        help=(
            "independently verify current unsealed macOS Release app/dSYM "
            "outputs without creating an archive"
        ),
    )
    readback_mode.add_argument(
        "--no-current-source",
        action="store_true",
        help="skip comparison with current build-input bytes",
    )
    readback_mode.add_argument(
        "--historical",
        action="store_true",
        help=(
            "verify a preserved non-current archive against its exact "
            "append-only ledger prefix without comparing current source"
        ),
    )
    arguments = parser.parse_args()
    if arguments.android_build_outputs:
        if arguments.archive_dir != DEFAULT_OUTPUT_ROOT / expected_release_id():
            print(
                "Android Release build-output readback failed: "
                "--archive-dir is not valid with --android-build-outputs",
                file=os.sys.stderr,
            )
            return 1
        try:
            result = verify_android_release_build_outputs()
        except ReleaseArchiveVerificationError as error:
            print(
                f"Android Release build-output readback failed: {error}",
                file=os.sys.stderr,
            )
            return 1
        print(
            "Android Release build-output readback OK: "
            f"{result['applicationId']} "
            f"{result['versionName']}+{result['versionCode']}; "
            f"APK={result['apk']['sha256']}; "
            f"AAB={result['aab']['sha256']}; "
            f"JNI={result['nativeLibraryCount']}; "
            f"SDK dependencies={result['sdkDependencyCount']}; "
            f"native symbols={result['nativeSymbolStatus']}."
        )
        return 0
    if arguments.macos_build_outputs:
        if arguments.archive_dir != DEFAULT_OUTPUT_ROOT / expected_release_id():
            print(
                "macOS unsealed Release build-output readback failed: "
                "--archive-dir is not valid with --macos-build-outputs",
                file=os.sys.stderr,
            )
            return 1
        try:
            result = verify_macos_release_build_outputs()
        except ReleaseArchiveVerificationError as error:
            print(
                "macOS unsealed Release build-output readback failed: "
                f"{error}",
                file=os.sys.stderr,
            )
            return 1
        print(
            "macOS unsealed Release build-output readback OK: "
            f"{result['bundleId']} "
            f"{result['marketingVersion']}+{result['buildNumber']}; "
            f"app={result['app']['sha256']}; "
            f"dSYM={result['dSYM']['sha256']}; "
            f"UUID={result['uuid']}; "
            f"source={result['source']['sha256']}; "
            f"receipt={result['sourceReceipt']['sha256']}; "
            "outer bundle seal=absent."
        )
        return 0
    try:
        manifest = verify_release_archive(
            arguments.archive_dir,
            compare_current_source=not (
                arguments.no_current_source or arguments.historical
            ),
            require_current_release=not arguments.historical,
        )
    except ReleaseArchiveVerificationError as error:
        print(f"Release archive readback failed: {error}", file=os.sys.stderr)
        return 1
    release = manifest["release"]
    assert isinstance(release, dict)
    print(
        "Release archive readback OK: "
        f"{release['releaseId']}; "
        f"members={manifest['archive']['memberCountExcludingManifest']}; "
        "Android=unsigned arm64-v8a; macOS=ad-hoc arm64+dSYM."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
