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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from script.check_release_version_ledger import (
    LedgerError,
    load_release_version_ledger,
)


DEFAULT_OUTPUT_ROOT = ROOT / "dist/releases"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
SCHEMA_VERSION = 1
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
    "release/version-ledger.tsv",
    "script/build_and_run.sh",
    "script/build_release_artifacts.sh",
    "script/check_release_version_ledger.py",
    "script/package_release_artifacts.py",
    "script/check_release_artifact_archive.py",
    "script/run_clean_release_reproducibility.py",
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
    "apps/macos/LocalAgentBridgeApp/Sources",
)


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
    entries: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as source:
            if source.comment:
                raise ReleaseArchiveVerificationError(
                    f"{label} must not contain a ZIP comment"
                )
            names = [info.filename for info in source.infolist()]
            if not names or len(names) != len(set(names)):
                raise ReleaseArchiveVerificationError(
                    f"{label} must contain unique ZIP members"
                )
            for info in source.infolist():
                validate_member_path(info.filename)
                if info.is_dir() or info.flag_bits & 0x1:
                    raise ReleaseArchiveVerificationError(
                        f"{label} contains a directory or encrypted member"
                    )
                entries.append((info.filename, source.read(info)))
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ReleaseArchiveVerificationError(
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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseArchiveVerificationError(
            f"bundletool readback command failed: {error}"
        ) from error
    if result.stderr.strip():
        raise ReleaseArchiveVerificationError(
            "bundletool emitted unexpected standard-error output"
        )
    return result.stdout.strip()


def parse_bundletool_manifest(output: str) -> dict[str, object]:
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
    android_attribute = f"{{{ANDROID_XML_NAMESPACE}}}"
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
    assert isinstance(version_code_text, str)
    assert isinstance(min_sdk_text, str)
    assert isinstance(target_sdk_text, str)
    return {
        "applicationId": application_id,
        "minSdk": int(min_sdk_text),
        "targetSdk": int(target_sdk_text),
        "versionCode": int(version_code_text),
        "versionName": version_name,
    }


def inspect_aab_manifest(
    aab_data: bytes,
    root: Path = ROOT,
) -> dict[str, object]:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="aetherlink-release-readback-bundle-",
        suffix=".aab",
    )
    try:
        with os.fdopen(file_descriptor, "wb") as output:
            output.write(aab_data)
        manifest = run_bundletool(
            [
                "dump",
                "manifest",
                f"--bundle={temporary_name}",
                "--module=base",
            ],
            root=root,
        )
        return parse_bundletool_manifest(manifest)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


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
        raise ReleaseArchiveVerificationError(
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
    ) != SCHEMA_VERSION:
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
    require_exact_keys(
        android,
        {
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
        },
        "platforms.android",
    )
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
    if bundle_manifest_readback != {
        "member": "android/bundle/app-release.aab",
        "tool": "bundletool dump manifest",
        "verifiedFields": [
            "applicationId",
            "minSdk",
            "targetSdk",
            "versionCode",
            "versionName",
        ],
    }:
        raise ReleaseArchiveVerificationError(
            "Android AAB manifest readback claim is not canonical"
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

    mapping = payload["android/mapping/mapping.txt"]
    aab = payload["android/bundle/app-release.aab"]
    aab_manifest = inspect_aab_manifest(aab)
    if aab_manifest != {
        "applicationId": android["applicationId"],
        "minSdk": min_sdk,
        "targetSdk": target_sdk,
        "versionCode": build_number,
        "versionName": marketing_version,
    }:
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
    ) != SCHEMA_VERSION:
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


def verify_manifest_header(
    manifest: dict[str, object],
    payload: dict[str, bytes],
    archive_id: str,
    *,
    require_current_release: bool,
    source_identities: dict[str, tuple[int, str]],
) -> None:
    require_exact_keys(
        manifest,
        {
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
        },
        "manifest",
    )
    if require_exact_int(
        manifest.get("schemaVersion"),
        "manifest.schemaVersion",
    ) != SCHEMA_VERSION:
        raise ReleaseArchiveVerificationError(
            "release archive schemaVersion is unsupported"
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
