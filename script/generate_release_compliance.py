#!/usr/bin/env python3
"""Refresh and deterministically render the local release compliance inventory.

The release builder only uses the checked-in catalog and metadata. Network access
is isolated to the explicit ``refresh`` maintenance command.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "release/third-party-license-inventory-v1.json"
RELEASE_METADATA_PATH = ROOT / "release/release-compliance-metadata-v1.json"
CATALOG_SCHEMA_VERSION = 1
METADATA_SCHEMA_VERSION = 1
COMPLIANCE_SCHEMA_VERSION = 2
COMPLIANCE_PROFILE_V2 = "aetherlink-release-compliance-v2"
SPDX_VERSION = "SPDX-2.3"
SPDX_DATA_LICENSE = "CC0-1.0"
MAX_POM_BYTES = 4 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 30
SWIFT_PACKAGE_DUMP_TIMEOUT_SECONDS = 15
SWIFT_PACKAGE_DUMP_MAX_BYTES = 2 * 1024 * 1024
SWIFT_PACKAGE_PATH = Path("Package.swift")
SWIFT_PACKAGE_RESOLVED_PATH = Path("Package.resolved")
GRADLE_SETTINGS_PATH = Path("settings.gradle.kts")
GRADLE_SETTINGS_SIZE = 744
GRADLE_SETTINGS_SHA256 = (
    "c89fbc7a53aa4329fd3811a92b36e32f599cc90093125f64463e48986f8ecd44"
)
GRADLE_BUILD_PATHS = (
    "apps/android/app/build.gradle.kts",
    "apps/android/core/pairing/build.gradle.kts",
    "apps/android/core/protocol/build.gradle.kts",
    "apps/android/core/transport/build.gradle.kts",
    "build.gradle.kts",
)
GRADLE_INCLUDED_PROJECTS = (
    ":app",
    ":core:protocol",
    ":core:transport",
    ":core:pairing",
)
GRADLE_PROJECT_DIRECTORIES = (
    (":app", "apps/android/app"),
    (":core", "apps/android/core"),
    (":core:protocol", "apps/android/core/protocol"),
    (":core:transport", "apps/android/core/transport"),
    (":core:pairing", "apps/android/core/pairing"),
)
GRADLE_LOCK_PATHS = (
    "apps/android/app/gradle.lockfile",
    "apps/android/core/pairing/gradle.lockfile",
    "apps/android/core/protocol/gradle.lockfile",
    "apps/android/core/transport/gradle.lockfile",
    "buildscript-gradle.lockfile",
    "settings-gradle.lockfile",
)
KNOWN_CONFIGURATIONS = frozenset(
    {
        "androidLintTool",
        "classpath",
        "composeMappingProducerClasspath",
        "kotlinBuildToolsApiClasspath",
        "kotlin-extension",
        "kotlinCompilerPluginClasspathRelease",
        "releaseCompileClasspath",
        "releaseLintChecksClasspath",
        "releaseRuntimeClasspath",
    }
)
RUNTIME_CONFIGURATIONS = frozenset({"releaseRuntimeClasspath"})
BUILD_DEPENDENCY_CONFIGURATIONS = frozenset({"releaseCompileClasspath"})
BUILD_TOOL_CONFIGURATIONS = frozenset(
    KNOWN_CONFIGURATIONS
    - RUNTIME_CONFIGURATIONS
    - BUILD_DEPENDENCY_CONFIGURATIONS
)
MAVEN_REPOSITORIES = (
    (
        "google",
        "https://dl.google.com/dl/android/maven2",
    ),
    (
        "maven-central",
        "https://repo.maven.apache.org/maven2",
    ),
    (
        "gradle-plugin-portal",
        "https://plugins.gradle.org/m2",
    ),
)
STANDARD_LICENSE_NAMES = {
    "apache 2.0": "Apache-2.0",
    "apache license v2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache license v2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "the apache license, version 2.0": "Apache-2.0",
    "the apache software license, version 2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "mit license": "MIT",
    "the mit license": "MIT",
    "mpl 1.1": "MPL-1.1",
}
CATALOG_DOCUMENT_TYPE = "aetherlink.maven-pom-license-inventory"
NOTICE_MEMBER = "compliance/THIRD_PARTY_LICENSE_INVENTORY.txt"
CATALOG_MEMBER = "compliance/third-party-license-inventory-v1.json"
METADATA_MEMBER = "compliance/release-compliance-metadata-v1.json"
SPDX_MEMBER = "compliance/sbom.spdx.json"


class ComplianceError(ValueError):
    """Raised when release compliance inputs are incomplete or non-canonical."""


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
        raise ComplianceError(f"value is not canonical JSON: {error}") from error
    return encoded + b"\n"


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ComplianceError(f"JSON object contains duplicate key {key!r}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> object:
    raise ComplianceError(f"non-finite JSON constant is not allowed: {value}")


def parse_canonical_json(data: bytes, label: str) -> dict[str, object]:
    if (
        data.startswith(b"\xef\xbb\xbf")
        or b"\r" in data
        or not data.endswith(b"\n")
    ):
        raise ComplianceError(
            f"{label} must be BOM-free ASCII JSON with LF line endings"
        )
    try:
        text = data.decode("ascii")
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ComplianceError(f"{label} is invalid JSON: {error}") from error
    if type(value) is not dict:
        raise ComplianceError(f"{label} must contain one JSON object")
    if canonical_json_bytes(value) != data:
        raise ComplianceError(f"{label} is not canonical JSON")
    return value


def exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise ComplianceError(
            f"{label} field set differs; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def exact_int(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ComplianceError(f"{label} must be an integer >= {minimum}")
    return value


def nonempty_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ComplianceError(f"{label} must be a nonempty string")
    return value


def read_regular_file(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ComplianceError(f"{label} must be a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ComplianceError(f"cannot read {label}: {error}") from error


def validate_gradle_project_universe(root: Path = ROOT) -> None:
    ignored_segments = frozenset(
        {".build", ".git", ".gradle", ".idea", "build", "dist"}
    )
    expected_paths = frozenset(
        (GRADLE_SETTINGS_PATH.as_posix(), *GRADLE_BUILD_PATHS)
    )
    discovered_paths: set[str] = set()
    gradle_names = frozenset(
        {
            "settings.gradle.kts",
            "settings.gradle",
            "build.gradle.kts",
            "build.gradle",
        }
    )

    def walk_error(error: OSError) -> None:
        raise error

    try:
        for directory, child_directories, filenames in os.walk(
            root,
            topdown=True,
            onerror=walk_error,
            followlinks=False,
        ):
            retained_directories: list[str] = []
            for name in child_directories:
                if name in ignored_segments:
                    continue
                child = Path(directory) / name
                if child.is_symlink():
                    raise ComplianceError(
                        "Gradle project discovery encountered a symlink "
                        f"directory: {child.relative_to(root).as_posix()}"
                    )
                retained_directories.append(name)
            child_directories[:] = retained_directories
            for filename in filenames:
                if filename not in gradle_names:
                    continue
                path = Path(directory) / filename
                relative = path.relative_to(root)
                if path.is_symlink() or not path.is_file():
                    raise ComplianceError(
                        "Gradle project input must be a physical file: "
                        f"{relative.as_posix()}"
                    )
                discovered_paths.add(relative.as_posix())
    except OSError as error:
        raise ComplianceError(
            f"cannot discover Gradle project inputs: {error}"
        ) from error
    if frozenset(discovered_paths) != expected_paths:
        raise ComplianceError(
            "Gradle project-file universe differs; "
            f"missing={sorted(expected_paths - discovered_paths)}, "
            f"extra={sorted(discovered_paths - expected_paths)}"
        )

    settings_bytes = read_regular_file(
        root / GRADLE_SETTINGS_PATH,
        GRADLE_SETTINGS_PATH.as_posix(),
    )
    if (
        len(settings_bytes) != GRADLE_SETTINGS_SIZE
        or hashlib.sha256(settings_bytes).hexdigest()
        != GRADLE_SETTINGS_SHA256
    ):
        raise ComplianceError(
            "settings.gradle.kts bytes differ from the reviewed V1 profile"
        )
    try:
        settings = settings_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ComplianceError("settings.gradle.kts must be UTF-8") from error
    if "\r" in settings or not settings.endswith("\n"):
        raise ComplianceError("settings.gradle.kts must use LF line endings")
    if re.search(r"\bincludeBuild\s*\(", settings):
        raise ComplianceError("Gradle included builds are outside the V1 profile")

    included = tuple(
        re.findall(r'(?m)^include\("([^"\n]+)"\)\s*$', settings)
    )
    project_directories = tuple(
        re.findall(
            r'(?m)^project\("([^"\n]+)"\)\.projectDir = '
            r'file\("([^"\n]+)"\)\s*$',
            settings,
        )
    )
    if (
        included != GRADLE_INCLUDED_PROJECTS
        or settings.count("include(") != len(GRADLE_INCLUDED_PROJECTS)
    ):
        raise ComplianceError("Gradle included-project set differs")
    if (
        project_directories != GRADLE_PROJECT_DIRECTORIES
        or settings.count(".projectDir") != len(GRADLE_PROJECT_DIRECTORIES)
    ):
        raise ComplianceError("Gradle project-directory mapping differs")

    for _project, relative_text in GRADLE_PROJECT_DIRECTORIES:
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ComplianceError("Gradle project directory escapes the repository")
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ComplianceError(
                    "Gradle project directory has a symlink ancestor: "
                    f"{relative_text}"
                )
        if not current.is_dir():
            raise ComplianceError(
                f"Gradle project directory is missing: {relative_text}"
            )


def discovered_gradle_lock_paths(root: Path = ROOT) -> tuple[str, ...]:
    android_root = root / "apps/android"
    if android_root.is_symlink() or not android_root.is_dir():
        raise ComplianceError("apps/android must be a physical directory")
    ignored_segments = frozenset({".gradle", ".idea", "build"})
    candidates: set[str] = set()
    android_locks: list[Path] = []
    android_build_files: list[Path] = []

    def walk_error(error: OSError) -> None:
        raise error

    try:
        root_entries = tuple(root.iterdir())
        for directory, child_directories, filenames in os.walk(
            android_root,
            topdown=True,
            onerror=walk_error,
            followlinks=False,
        ):
            retained_directories: list[str] = []
            for name in child_directories:
                if name in ignored_segments:
                    continue
                child = Path(directory) / name
                if child.is_symlink():
                    raise ComplianceError(
                        "Gradle lock discovery encountered a symlink "
                        f"directory: {child.relative_to(root).as_posix()}"
                    )
                retained_directories.append(name)
            child_directories[:] = retained_directories
            for filename in filenames:
                path = Path(directory) / filename
                if filename == "gradle.lockfile":
                    android_locks.append(path)
                elif filename == "build.gradle.kts":
                    android_build_files.append(path)
    except OSError as error:
        raise ComplianceError(
            f"cannot discover Gradle dependency inputs: {error}"
        ) from error
    for path in root_entries:
        if path.name.endswith("gradle.lockfile"):
            if path.is_symlink() or not path.is_file():
                raise ComplianceError(
                    f"Gradle lock path must be a physical file: {path.name}"
                )
            candidates.add(path.name)
    for path in android_locks:
        relative = path.relative_to(root)
        if any(part in ignored_segments for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file():
            raise ComplianceError(
                "Gradle lock path must be a physical file: "
                f"{relative.as_posix()}"
            )
        candidates.add(relative.as_posix())
    for build_file in android_build_files:
        relative = build_file.relative_to(root)
        if any(part in ignored_segments for part in relative.parts):
            continue
        if build_file.is_symlink() or not build_file.is_file():
            raise ComplianceError(
                "Android module build path must be a physical file: "
                f"{relative.as_posix()}"
            )
        lock_path = build_file.parent / "gradle.lockfile"
        if lock_path.is_symlink() or not lock_path.is_file():
            raise ComplianceError(
                "Android module has no physical dependency lock: "
                f"{relative.as_posix()}"
            )
    return tuple(sorted(candidates, key=lambda value: value.encode("ascii")))


def validate_gradle_lock_path_universe(root: Path = ROOT) -> None:
    validate_gradle_project_universe(root)
    actual = discovered_gradle_lock_paths(root)
    if actual != GRADLE_LOCK_PATHS:
        expected = set(GRADLE_LOCK_PATHS)
        observed = set(actual)
        raise ComplianceError(
            "Gradle lock-file universe differs; "
            f"missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )


def swift_external_dependency_count(
    root: Path = ROOT,
    *,
    run: object = subprocess.run,
) -> int:
    package_path = root / SWIFT_PACKAGE_PATH
    read_regular_file(package_path, SWIFT_PACKAGE_PATH.as_posix())
    resolved_path = root / SWIFT_PACKAGE_RESOLVED_PATH
    if resolved_path.is_symlink() or resolved_path.exists():
        raise ComplianceError(
            "Package.resolved is incompatible with the declared zero Swift "
            "external dependency boundary"
        )
    try:
        completed = run(
            ["swift", "package", "dump-package"],
            cwd=root,
            capture_output=True,
            check=False,
            timeout=SWIFT_PACKAGE_DUMP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ComplianceError(
            f"cannot inspect Swift package dependency closure: {error}"
        ) from error
    stdout = getattr(completed, "stdout", None)
    stderr = getattr(completed, "stderr", None)
    returncode = getattr(completed, "returncode", None)
    if (
        type(returncode) is not int
        or returncode != 0
        or type(stdout) is not bytes
        or type(stderr) is not bytes
        or stderr
        or not stdout
        or len(stdout) > SWIFT_PACKAGE_DUMP_MAX_BYTES
    ):
        raise ComplianceError(
            "swift package dump-package did not produce one bounded "
            "successful JSON document"
        )
    try:
        package = json.loads(
            stdout.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ComplianceError(
            f"Swift package dependency closure is invalid JSON: {error}"
        ) from error
    if (
        type(package) is not dict
        or type(package.get("dependencies")) is not list
        or type(package.get("targets")) is not list
    ):
        raise ComplianceError(
            "Swift package dump lacks exact dependency and target arrays"
        )
    dependencies = package["dependencies"]
    if dependencies:
        raise ComplianceError(
            "Swift external dependencies are unsupported by the current "
            f"release compliance profile: count={len(dependencies)}"
        )
    for index, target in enumerate(package["targets"]):
        if type(target) is not dict:
            raise ComplianceError(
                f"Swift target {index} must be a JSON object"
            )
        if target.get("type") == "binary" or target.get("url") is not None:
            raise ComplianceError(
                "Swift binary target is outside the zero-external-dependency "
                f"profile: target {index}"
            )
    return 0


def validate_ascii_text_file(data: bytes, label: str) -> str:
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not data.endswith(b"\n"):
        raise ComplianceError(f"{label} must be BOM-free ASCII with LF endings")
    try:
        return data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ComplianceError(f"{label} must be ASCII") from error


def parse_maven_coordinate(coordinate: str, label: str) -> tuple[str, str, str]:
    parts = coordinate.split(":")
    if len(parts) != 3 or any(
        re.fullmatch(r"[A-Za-z0-9_.+-]+", part) is None for part in parts
    ):
        raise ComplianceError(f"{label} has an invalid Maven coordinate")
    return parts[0], parts[1], parts[2]


def maven_purl(group: str, artifact: str, version: str) -> str:
    return (
        "pkg:maven/"
        + urllib.parse.quote(group, safe=".-_")
        + "/"
        + urllib.parse.quote(artifact, safe=".-_")
        + "@"
        + urllib.parse.quote(version, safe=".-_")
    )


def lock_inventory(root: Path = ROOT) -> dict[str, dict[str, set[str]]]:
    validate_gradle_lock_path_universe(root)
    inventory: dict[str, dict[str, set[str]]] = {}
    for relative in GRADLE_LOCK_PATHS:
        data = read_regular_file(root / relative, relative)
        text = validate_ascii_text_file(data, relative)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line or line.startswith("#"):
                continue
            if line.count("=") != 1:
                raise ComplianceError(
                    f"{relative}:{line_number} must contain one '='"
                )
            coordinate, configuration_text = line.split("=", 1)
            if coordinate == "empty":
                if configuration_text and any(
                    re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", item) is None
                    for item in configuration_text.split(",")
                ):
                    raise ComplianceError(
                        f"{relative}:{line_number} has invalid empty configurations"
                    )
                continue
            configurations = configuration_text.split(",")
            if (
                not configurations
                or any(item not in KNOWN_CONFIGURATIONS for item in configurations)
            ):
                raise ComplianceError(
                    f"{relative}:{line_number} has unknown configurations"
                )
            parse_maven_coordinate(
                coordinate,
                f"{relative}:{line_number}",
            )
            record = inventory.setdefault(
                coordinate,
                {"configurations": set(), "lockFiles": set()},
            )
            record["configurations"].update(configurations)
            record["lockFiles"].add(relative)
    if not inventory:
        raise ComplianceError("Gradle lock inventory is empty")
    return inventory


def gradle_lock_file_records(root: Path = ROOT) -> list[dict[str, object]]:
    validate_gradle_lock_path_universe(root)
    records: list[dict[str, object]] = []
    for relative in GRADLE_LOCK_PATHS:
        data = read_regular_file(root / relative, relative)
        validate_ascii_text_file(data, relative)
        records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
    return records


def normalized_xml_text(value: str | None) -> str:
    return " ".join((value or "").split())


def xml_child_text(element: ET.Element, name: str) -> str:
    child = element.find(f"{{*}}{name}")
    return normalized_xml_text(None if child is None else child.text)


def xml_properties(project: ET.Element) -> dict[str, str]:
    properties: dict[str, str] = {}
    container = project.find("{*}properties")
    if container is None:
        return properties
    for child in list(container):
        key = child.tag.rsplit("}", 1)[-1]
        value = normalized_xml_text(child.text)
        if key and value:
            properties[key] = value
    return properties


def resolve_placeholders(
    value: str,
    context: Mapping[str, str],
    *,
    require_complete: bool = True,
) -> str:
    result = value
    for _ in range(12):
        changed = False

        def replacement(match: re.Match[str]) -> str:
            nonlocal changed
            key = match.group(1)
            if key not in context:
                return match.group(0)
            changed = True
            return context[key]

        updated = re.sub(r"\$\{([^{}]+)\}", replacement, result)
        result = updated
        if not changed:
            break
    if require_complete and "${" in result:
        raise ComplianceError(f"unresolved Maven property in {value!r}")
    return result


def pom_relative_path(group: str, artifact: str, version: str) -> str:
    return (
        group.replace(".", "/")
        + "/"
        + urllib.parse.quote(artifact, safe=".-_")
        + "/"
        + urllib.parse.quote(version, safe=".-_")
        + "/"
        + urllib.parse.quote(artifact, safe=".-_")
        + "-"
        + urllib.parse.quote(version, safe=".-_")
        + ".pom"
    )


def fetch_pom(
    coordinate: str,
    cache: dict[str, tuple[bytes, str, str]],
) -> tuple[bytes, str, str]:
    if coordinate in cache:
        return cache[coordinate]
    group, artifact, version = parse_maven_coordinate(
        coordinate,
        f"POM {coordinate}",
    )
    relative = pom_relative_path(group, artifact, version)
    failures: list[str] = []
    for repository_id, base_url in MAVEN_REPOSITORIES:
        url = f"{base_url}/{relative}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AetherLink-release-compliance-v2"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=FETCH_TIMEOUT_SECONDS,
            ) as response:
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > MAX_POM_BYTES:
                    raise ComplianceError(f"POM exceeds byte limit: {url}")
                data = response.read(MAX_POM_BYTES + 1)
        except (OSError, ValueError, urllib.error.URLError) as error:
            failures.append(f"{repository_id}: {error}")
            continue
        if len(data) > MAX_POM_BYTES or not data:
            failures.append(f"{repository_id}: invalid byte count {len(data)}")
            continue
        if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
            failures.append(f"{repository_id}: XML declarations are not allowed")
            continue
        cache[coordinate] = (data, url, repository_id)
        return cache[coordinate]
    raise ComplianceError(
        f"cannot fetch POM {coordinate}: {'; '.join(failures)}"
    )


def parse_pom_project(data: bytes, coordinate: str) -> ET.Element:
    try:
        project = ET.fromstring(data)
    except ET.ParseError as error:
        raise ComplianceError(f"POM {coordinate} is invalid XML: {error}") from error
    if project.tag.rsplit("}", 1)[-1] != "project":
        raise ComplianceError(f"POM {coordinate} does not contain a project root")
    return project


def declared_licenses(
    project: ET.Element,
    context: Mapping[str, str],
) -> list[dict[str, str]]:
    licenses = project.find("{*}licenses")
    if licenses is None:
        return []
    result: list[dict[str, str]] = []
    for license_element in licenses.findall("{*}license"):
        record = {
            "comments": resolve_placeholders(
                xml_child_text(license_element, "comments"),
                context,
                require_complete=False,
            ),
            "distribution": resolve_placeholders(
                xml_child_text(license_element, "distribution"),
                context,
                require_complete=False,
            ),
            "name": resolve_placeholders(
                xml_child_text(license_element, "name"),
                context,
                require_complete=False,
            ),
            "url": resolve_placeholders(
                xml_child_text(license_element, "url"),
                context,
                require_complete=False,
            ),
        }
        if any(record.values()):
            result.append(record)
    return result


def pom_context(
    project: ET.Element,
    requested: tuple[str, str, str],
) -> dict[str, str]:
    requested_group, requested_artifact, requested_version = requested
    parent = project.find("{*}parent")
    parent_group = "" if parent is None else xml_child_text(parent, "groupId")
    parent_version = "" if parent is None else xml_child_text(parent, "version")
    project_group = xml_child_text(project, "groupId") or parent_group or requested_group
    project_artifact = xml_child_text(project, "artifactId") or requested_artifact
    project_version = (
        xml_child_text(project, "version") or parent_version or requested_version
    )
    context = {
        **xml_properties(project),
        "groupId": project_group,
        "artifactId": project_artifact,
        "version": project_version,
        "project.groupId": project_group,
        "project.artifactId": project_artifact,
        "project.version": project_version,
        "pom.groupId": project_group,
        "pom.artifactId": project_artifact,
        "pom.version": project_version,
        "project.parent.groupId": parent_group,
        "project.parent.version": parent_version,
    }
    return context


def pom_parent_coordinate(
    project: ET.Element,
    context: Mapping[str, str],
) -> str | None:
    parent = project.find("{*}parent")
    if parent is None:
        return None
    group = resolve_placeholders(xml_child_text(parent, "groupId"), context)
    artifact = resolve_placeholders(xml_child_text(parent, "artifactId"), context)
    version = resolve_placeholders(xml_child_text(parent, "version"), context)
    coordinate = f"{group}:{artifact}:{version}"
    parse_maven_coordinate(coordinate, "Maven parent")
    return coordinate


def effective_pom_licenses(
    coordinate: str,
    fetch_cache: dict[str, tuple[bytes, str, str]],
    resolution_cache: dict[
        str,
        tuple[list[str], list[dict[str, str]], str],
    ],
    records: dict[str, dict[str, object]],
    *,
    stack: tuple[str, ...] = (),
) -> tuple[list[str], list[dict[str, str]], str]:
    if coordinate in resolution_cache:
        return resolution_cache[coordinate]
    if coordinate in stack or len(stack) >= 16:
        raise ComplianceError(f"Maven parent cycle or excessive depth: {coordinate}")
    data, url, repository_id = fetch_pom(coordinate, fetch_cache)
    project = parse_pom_project(data, coordinate)
    requested = parse_maven_coordinate(coordinate, f"POM {coordinate}")
    context = pom_context(project, requested)
    records[url] = {
        "coordinate": coordinate,
        "repository": repository_id,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "url": url,
    }
    licenses = declared_licenses(project, context)
    if licenses:
        result = ([url], licenses, url)
    else:
        parent = pom_parent_coordinate(project, context)
        if parent is None:
            raise ComplianceError(
                f"POM {coordinate} and its parent chain declare no licenses"
            )
        parent_chain, parent_licenses, source_url = effective_pom_licenses(
            parent,
            fetch_cache,
            resolution_cache,
            records,
            stack=(*stack, coordinate),
        )
        result = ([url, *parent_chain], parent_licenses, source_url)
    resolution_cache[coordinate] = result
    return result


def normalized_license_key(name: str) -> str:
    return " ".join(name.casefold().split())


def spdx_declared_expression(licenses: list[dict[str, str]]) -> str:
    mapped: set[str] = set()
    for license_record in licenses:
        name = license_record.get("name", "")
        identifier = STANDARD_LICENSE_NAMES.get(normalized_license_key(name))
        if identifier is None:
            return "NOASSERTION"
        mapped.add(identifier)
    if not mapped:
        return "NOASSERTION"
    return " OR ".join(sorted(mapped))


def refreshed_catalog(root: Path = ROOT) -> dict[str, object]:
    swift_dependency_count = swift_external_dependency_count(root)
    locked = lock_inventory(root)
    fetch_cache: dict[str, tuple[bytes, str, str]] = {}
    resolution_cache: dict[
        str,
        tuple[list[str], list[dict[str, str]], str],
    ] = {}
    pom_records: dict[str, dict[str, object]] = {}
    packages: list[dict[str, object]] = []
    for coordinate in sorted(locked, key=lambda item: item.encode("ascii")):
        group, artifact, version = parse_maven_coordinate(
            coordinate,
            f"locked package {coordinate}",
        )
        chain, licenses, source_url = effective_pom_licenses(
            coordinate,
            fetch_cache,
            resolution_cache,
            pom_records,
        )
        packages.append(
            {
                "artifact": artifact,
                "configurations": sorted(locked[coordinate]["configurations"]),
                "coordinate": coordinate,
                "group": group,
                "licenseEvidenceSource": source_url,
                "lockFiles": sorted(locked[coordinate]["lockFiles"]),
                "pomChain": chain,
                "pomDeclaredLicenses": licenses,
                "purl": maven_purl(group, artifact, version),
                "spdxLicenseDeclared": spdx_declared_expression(licenses),
                "version": version,
            }
        )
    return {
        "documentType": CATALOG_DOCUMENT_TYPE,
        "gradleLockFiles": gradle_lock_file_records(root),
        "gradleLockedPackageCount": len(packages),
        "packages": packages,
        "pomRecords": sorted(
            pom_records.values(),
            key=lambda item: str(item["url"]).encode("ascii"),
        ),
        "repositories": [
            {"baseUrl": base_url, "id": repository_id}
            for repository_id, base_url in MAVEN_REPOSITORIES
        ],
        "reviewBoundary": {
            "artifactFilesAnalyzed": False,
            "binaryArtifactChecksumsIncluded": False,
            "licenseCompatibilityConclusionIncluded": False,
            "licenseConcluded": "NOASSERTION",
            "networkRequiredForReleaseBuild": False,
            "source": "Maven POM license declarations with parent inheritance",
        },
        "schemaVersion": CATALOG_SCHEMA_VERSION,
        "swiftExternalDependencyCount": swift_dependency_count,
    }


def validate_license_record(value: object, label: str) -> dict[str, str]:
    if type(value) is not dict:
        raise ComplianceError(f"{label} must be an object")
    exact_keys(
        value,
        {"comments", "distribution", "name", "url"},
        label,
    )
    record: dict[str, str] = {}
    for key in ("comments", "distribution", "name", "url"):
        field = value.get(key)
        if type(field) is not str or "\r" in field or "\n" in field:
            raise ComplianceError(f"{label}.{key} must be a single-line string")
        record[key] = field
    if not any(record.values()):
        raise ComplianceError(f"{label} must contain a declared value")
    return record


def validate_catalog(
    catalog: dict[str, object],
    root: Path = ROOT,
) -> list[dict[str, object]]:
    exact_keys(
        catalog,
        {
            "documentType",
            "gradleLockFiles",
            "gradleLockedPackageCount",
            "packages",
            "pomRecords",
            "repositories",
            "reviewBoundary",
            "schemaVersion",
            "swiftExternalDependencyCount",
        },
        "catalog",
    )
    if (
        exact_int(catalog.get("schemaVersion"), "catalog.schemaVersion", minimum=1)
        != CATALOG_SCHEMA_VERSION
        or catalog.get("documentType") != CATALOG_DOCUMENT_TYPE
    ):
        raise ComplianceError("catalog identity is unsupported")
    lock_files = catalog.get("gradleLockFiles")
    expected_lock_files = gradle_lock_file_records(root)
    if lock_files != expected_lock_files:
        raise ComplianceError("catalog Gradle lock-file identities differ")
    repositories = catalog.get("repositories")
    expected_repositories = [
        {"baseUrl": base_url, "id": repository_id}
        for repository_id, base_url in MAVEN_REPOSITORIES
    ]
    if repositories != expected_repositories:
        raise ComplianceError("catalog repository set is not canonical")
    boundary = catalog.get("reviewBoundary")
    if type(boundary) is not dict:
        raise ComplianceError("catalog reviewBoundary must be an object")
    expected_boundary = {
        "artifactFilesAnalyzed": False,
        "binaryArtifactChecksumsIncluded": False,
        "licenseCompatibilityConclusionIncluded": False,
        "licenseConcluded": "NOASSERTION",
        "networkRequiredForReleaseBuild": False,
        "source": "Maven POM license declarations with parent inheritance",
    }
    if boundary != expected_boundary:
        raise ComplianceError("catalog review boundary differs")
    swift_dependency_count = swift_external_dependency_count(root)
    if exact_int(
        catalog.get("swiftExternalDependencyCount"),
        "catalog.swiftExternalDependencyCount",
    ) != swift_dependency_count:
        raise ComplianceError("catalog Swift external dependency count must be zero")

    records_value = catalog.get("pomRecords")
    if type(records_value) is not list or not records_value:
        raise ComplianceError("catalog pomRecords must be a nonempty array")
    records: dict[str, dict[str, object]] = {}
    previous_url: bytes | None = None
    repository_bases = {
        repository_id: base_url
        for repository_id, base_url in MAVEN_REPOSITORIES
    }
    for index, value in enumerate(records_value):
        if type(value) is not dict:
            raise ComplianceError(f"pomRecords[{index}] must be an object")
        exact_keys(
            value,
            {"coordinate", "repository", "sha256", "size", "url"},
            f"pomRecords[{index}]",
        )
        url = nonempty_string(value.get("url"), f"pomRecords[{index}].url")
        url_bytes = url.encode("ascii")
        if previous_url is not None and url_bytes <= previous_url:
            raise ComplianceError("POM record URLs must be strictly ASCII-sorted")
        previous_url = url_bytes
        coordinate = nonempty_string(
            value.get("coordinate"),
            f"pomRecords[{index}].coordinate",
        )
        group, artifact, version = parse_maven_coordinate(
            coordinate,
            f"pomRecords[{index}].coordinate",
        )
        repository = nonempty_string(
            value.get("repository"),
            f"pomRecords[{index}].repository",
        )
        digest = nonempty_string(
            value.get("sha256"),
            f"pomRecords[{index}].sha256",
        )
        size = exact_int(
            value.get("size"),
            f"pomRecords[{index}].size",
            minimum=1,
        )
        expected_url = (
            repository_bases.get(repository, "")
            + "/"
            + pom_relative_path(group, artifact, version)
        )
        if (
            repository not in repository_bases
            or url != expected_url
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or size > MAX_POM_BYTES
            or url in records
        ):
            raise ComplianceError(f"pomRecords[{index}] identity is invalid")
        records[url] = value

    locked = lock_inventory(root)
    packages_value = catalog.get("packages")
    if type(packages_value) is not list or not packages_value:
        raise ComplianceError("catalog packages must be a nonempty array")
    count = exact_int(
        catalog.get("gradleLockedPackageCount"),
        "catalog.gradleLockedPackageCount",
        minimum=1,
    )
    if count != len(packages_value) or count != len(locked):
        raise ComplianceError("catalog package count differs from Gradle locks")
    packages: list[dict[str, object]] = []
    previous_coordinate: bytes | None = None
    seen: set[str] = set()
    for index, value in enumerate(packages_value):
        if type(value) is not dict:
            raise ComplianceError(f"packages[{index}] must be an object")
        exact_keys(
            value,
            {
                "artifact",
                "configurations",
                "coordinate",
                "group",
                "licenseEvidenceSource",
                "lockFiles",
                "pomChain",
                "pomDeclaredLicenses",
                "purl",
                "spdxLicenseDeclared",
                "version",
            },
            f"packages[{index}]",
        )
        coordinate = nonempty_string(
            value.get("coordinate"),
            f"packages[{index}].coordinate",
        )
        coordinate_bytes = coordinate.encode("ascii")
        if (
            previous_coordinate is not None
            and coordinate_bytes <= previous_coordinate
        ):
            raise ComplianceError(
                "catalog packages must be strictly ASCII-coordinate-sorted"
            )
        previous_coordinate = coordinate_bytes
        if coordinate in seen or coordinate not in locked:
            raise ComplianceError(f"catalog package coordinate differs: {coordinate}")
        seen.add(coordinate)
        group, artifact, version = parse_maven_coordinate(
            coordinate,
            f"packages[{index}].coordinate",
        )
        configurations = value.get("configurations")
        lock_files = value.get("lockFiles")
        if (
            type(configurations) is not list
            or not configurations
            or configurations != sorted(set(configurations))
            or any(
                type(item) is not str or item not in KNOWN_CONFIGURATIONS
                for item in configurations
            )
            or type(lock_files) is not list
            or not lock_files
            or lock_files != sorted(set(lock_files))
            or any(item not in GRADLE_LOCK_PATHS for item in lock_files)
            or configurations != sorted(locked[coordinate]["configurations"])
            or lock_files != sorted(locked[coordinate]["lockFiles"])
        ):
            raise ComplianceError(
                f"catalog package lock coverage differs: {coordinate}"
            )
        if (
            value.get("group") != group
            or value.get("artifact") != artifact
            or value.get("version") != version
            or value.get("purl") != maven_purl(group, artifact, version)
        ):
            raise ComplianceError(f"catalog package identity differs: {coordinate}")
        chain = value.get("pomChain")
        if (
            type(chain) is not list
            or not chain
            or any(type(item) is not str or item not in records for item in chain)
            or len(set(chain)) != len(chain)
        ):
            raise ComplianceError(f"catalog POM chain is invalid: {coordinate}")
        direct_record = records[chain[0]]
        if direct_record.get("coordinate") != coordinate:
            raise ComplianceError(
                f"catalog direct POM differs from coordinate: {coordinate}"
            )
        source = value.get("licenseEvidenceSource")
        if source != chain[-1]:
            raise ComplianceError(
                f"catalog license evidence source differs: {coordinate}"
            )
        licenses_value = value.get("pomDeclaredLicenses")
        if type(licenses_value) is not list or not licenses_value:
            raise ComplianceError(
                f"catalog package lacks POM license declarations: {coordinate}"
            )
        licenses = [
            validate_license_record(
                item,
                f"packages[{index}].pomDeclaredLicenses[{license_index}]",
            )
            for license_index, item in enumerate(licenses_value)
        ]
        expression = spdx_declared_expression(licenses)
        if value.get("spdxLicenseDeclared") != expression:
            raise ComplianceError(
                f"catalog SPDX declaration differs from reviewed mapping: {coordinate}"
            )
        packages.append(value)
    if seen != set(locked):
        raise ComplianceError("catalog coordinate set differs from Gradle locks")
    return packages


def load_catalog(
    root: Path = ROOT,
) -> tuple[dict[str, object], bytes, list[dict[str, object]]]:
    path = root / CATALOG_PATH.relative_to(ROOT)
    data = read_regular_file(path, "release license catalog")
    catalog = parse_canonical_json(data, "release license catalog")
    packages = validate_catalog(catalog, root)
    return catalog, data, packages


def load_release_metadata(root: Path = ROOT) -> dict[str, object]:
    path = root / RELEASE_METADATA_PATH.relative_to(ROOT)
    data = read_regular_file(path, "release compliance metadata")
    metadata = parse_canonical_json(data, "release compliance metadata")
    exact_keys(
        metadata,
        {
            "creator",
            "spdxCreated",
            "schemaVersion",
        },
        "release compliance metadata",
    )
    if (
        exact_int(
            metadata.get("schemaVersion"),
            "release compliance metadata.schemaVersion",
            minimum=1,
        )
        != METADATA_SCHEMA_VERSION
    ):
        raise ComplianceError("release compliance metadata schema is unsupported")
    creator = nonempty_string(
        metadata.get("creator"),
        "release compliance metadata.creator",
    )
    if not creator.startswith(("Organization: ", "Person: ", "Tool: ")):
        raise ComplianceError("release compliance metadata creator is invalid")
    created = nonempty_string(
        metadata.get("spdxCreated"),
        "release compliance metadata.spdxCreated",
    )
    if re.fullmatch(
        r"[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])T"
        r"([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z",
        created,
    ) is None:
        raise ComplianceError("release compliance metadata timestamp is invalid")
    return metadata


def spdx_package_id(coordinate: str) -> str:
    digest = hashlib.sha256(coordinate.encode("ascii")).hexdigest()[:24]
    return f"SPDXRef-Maven-{digest}"


def dependency_relationship_types(configurations: list[str]) -> tuple[str, ...]:
    configuration_set = set(configurations)
    unknown = configuration_set - KNOWN_CONFIGURATIONS
    if not configuration_set or unknown:
        raise ComplianceError(
            "package contains unknown Gradle configurations: "
            f"{sorted(unknown) if unknown else configurations}"
        )
    relationship_types: set[str] = set()
    if configuration_set & RUNTIME_CONFIGURATIONS:
        relationship_types.add("RUNTIME_DEPENDENCY_OF")
    if configuration_set & BUILD_DEPENDENCY_CONFIGURATIONS:
        relationship_types.add("BUILD_DEPENDENCY_OF")
    if configuration_set & BUILD_TOOL_CONFIGURATIONS:
        relationship_types.add("BUILD_TOOL_OF")
    if not relationship_types:
        raise ComplianceError("package has no SPDX dependency relationship")
    return tuple(sorted(relationship_types))


def validate_source_snapshot_sha256(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ComplianceError(
            "source snapshot SHA-256 must be 64 lowercase hexadecimal characters"
        )
    return value


def document_namespace_v2(
    *,
    catalog_bytes: bytes,
    metadata: dict[str, object],
    marketing_version: str,
    build_number: int,
    source_snapshot_sha256: str,
    profile: str = COMPLIANCE_PROFILE_V2,
) -> str:
    source_digest = validate_source_snapshot_sha256(source_snapshot_sha256)
    if profile != COMPLIANCE_PROFILE_V2:
        raise ComplianceError(f"unsupported release compliance profile: {profile!r}")
    release_name = f"AetherLink-{marketing_version}+{build_number}-local-v1"
    generation_inputs = {
        "catalogSha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "metadataSha256": hashlib.sha256(
            canonical_json_bytes(metadata)
        ).hexdigest(),
        "profile": profile,
        "release": {
            "buildNumber": build_number,
            "marketingVersion": marketing_version,
            "releaseName": release_name,
        },
        "sourceSnapshotSha256": source_digest,
    }
    namespace_digest = hashlib.sha256(
        canonical_json_bytes(generation_inputs)
    ).hexdigest()
    return (
        "https://spdx.org/spdxdocs/"
        + release_name.lower()
        + "-"
        + namespace_digest
    )


def build_spdx_document(
    *,
    catalog_bytes: bytes,
    packages: list[dict[str, object]],
    metadata: dict[str, object],
    marketing_version: str,
    build_number: int,
    source_snapshot_sha256: str,
    profile: str = COMPLIANCE_PROFILE_V2,
) -> dict[str, object]:
    if (
        type(marketing_version) is not str
        or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", marketing_version) is None
        or type(build_number) is not int
        or build_number < 1
    ):
        raise ComplianceError("release version is invalid for SPDX generation")
    if build_number < 8:
        raise ComplianceError(
            "release compliance profile v2 starts at Build 8"
        )
    release_name = f"AetherLink-{marketing_version}+{build_number}-local-v1"
    namespace = document_namespace_v2(
        catalog_bytes=catalog_bytes,
        metadata=metadata,
        marketing_version=marketing_version,
        build_number=build_number,
        source_snapshot_sha256=source_snapshot_sha256,
        profile=profile,
    )
    spdx_packages: list[dict[str, object]] = [
        {
            "SPDXID": "SPDXRef-Package-AetherLink",
            "copyrightText": "NOASSERTION",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "Apache-2.0",
            "licenseDeclared": "Apache-2.0",
            "name": "AetherLink",
            "versionInfo": marketing_version,
        }
    ]
    relationships: list[dict[str, str]] = []
    for package in packages:
        coordinate = str(package["coordinate"])
        package_id = spdx_package_id(coordinate)
        spdx_packages.append(
            {
                "SPDXID": package_id,
                "copyrightText": "NOASSERTION",
                "downloadLocation": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceLocator": package["purl"],
                        "referenceType": "purl",
                    }
                ],
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": package["spdxLicenseDeclared"],
                "name": f"{package['group']}:{package['artifact']}",
                "versionInfo": package["version"],
            }
        )
        configurations = package["configurations"]
        assert isinstance(configurations, list)
        for relationship_type in dependency_relationship_types(configurations):
            relationships.append(
                {
                    "relatedSpdxElement": "SPDXRef-Package-AetherLink",
                    "relationshipType": relationship_type,
                    "spdxElementId": package_id,
                }
            )
    spdx_packages.sort(key=lambda item: str(item["SPDXID"]).encode("ascii"))
    relationships.sort(
        key=lambda item: (
            item["spdxElementId"].encode("ascii"),
            item["relationshipType"].encode("ascii"),
            item["relatedSpdxElement"].encode("ascii"),
        )
    )
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": metadata["spdxCreated"],
            "creators": [
                metadata["creator"],
                "Tool: AetherLink deterministic release compliance generator v2",
            ],
        },
        "dataLicense": SPDX_DATA_LICENSE,
        "documentDescribes": ["SPDXRef-Package-AetherLink"],
        "documentNamespace": namespace,
        "name": release_name,
        "packages": spdx_packages,
        "relationships": relationships,
        "spdxVersion": SPDX_VERSION,
    }


def notice_bytes(packages: list[dict[str, object]]) -> bytes:
    lines = [
        "AetherLink third-party license inventory",
        "",
        "Scope: exact Maven coordinates present in the checked-in Gradle lock files.",
        "Evidence: Maven POM license declarations, including parent inheritance.",
        "This inventory does not analyze binary artifacts or conclude license compatibility.",
        "Archived evidence stores POM URL, size, SHA-256, and parsed declarations; "
        "it does not store POM bodies or license/NOTICE texts.",
        "All package licenseConcluded values remain NOASSERTION in the SPDX document.",
        "",
    ]
    for package in packages:
        declarations = package["pomDeclaredLicenses"]
        assert isinstance(declarations, list)
        rendered = []
        for declaration in declarations:
            assert isinstance(declaration, dict)
            name = str(declaration["name"]) or "(unnamed)"
            url = str(declaration["url"]) or "(no URL)"
            rendered.append(f"{name} [{url}]")
        lines.extend(
            [
                str(package["coordinate"]),
                f"  SPDX licenseDeclared: {package['spdxLicenseDeclared']}",
                "  POM declarations: " + " OR ".join(rendered),
                f"  Evidence POM: {package['licenseEvidenceSource']}",
                "",
            ]
        )
    text = "\n".join(lines)
    if "\r" in text or "\t" in text:
        raise ComplianceError("rendered license inventory is non-canonical")
    return text.encode("utf-8")


def member_identity(path: str, data: bytes) -> dict[str, object]:
    if (
        PurePosixPath(path).is_absolute()
        or any(part in ("", ".", "..") for part in PurePosixPath(path).parts)
    ):
        raise ComplianceError(f"invalid compliance member path: {path!r}")
    return {
        "member": path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def build_release_compliance(
    *,
    marketing_version: str,
    build_number: int,
    source_snapshot_sha256: str,
    root: Path = ROOT,
) -> tuple[list[tuple[str, bytes]], dict[str, object]]:
    validate_source_snapshot_sha256(source_snapshot_sha256)
    if type(build_number) is not int or build_number < 8:
        raise ComplianceError(
            "release compliance profile v2 starts at Build 8"
        )
    _, catalog_bytes, packages = load_catalog(root)
    metadata_path = root / RELEASE_METADATA_PATH.relative_to(ROOT)
    metadata_bytes = read_regular_file(
        metadata_path,
        "release compliance metadata",
    )
    metadata = load_release_metadata(root)
    spdx_document = build_spdx_document(
        catalog_bytes=catalog_bytes,
        packages=packages,
        metadata=metadata,
        marketing_version=marketing_version,
        build_number=build_number,
        source_snapshot_sha256=source_snapshot_sha256,
    )
    spdx_bytes = canonical_json_bytes(spdx_document)
    inventory_bytes = notice_bytes(packages)
    members = [
        (CATALOG_MEMBER, catalog_bytes),
        (METADATA_MEMBER, metadata_bytes),
        (NOTICE_MEMBER, inventory_bytes),
        (SPDX_MEMBER, spdx_bytes),
    ]
    members.sort(key=lambda item: item[0].encode("ascii"))
    summary = {
        "artifactFilesAnalyzed": False,
        "catalog": member_identity(CATALOG_MEMBER, catalog_bytes),
        "gradleLockedPackageCount": len(packages),
        "licenseCompatibilityConclusionIncluded": False,
        "licenseConcluded": "NOASSERTION",
        "metadata": member_identity(METADATA_MEMBER, metadata_bytes),
        "networkRequiredForReleaseBuild": False,
        "notice": member_identity(NOTICE_MEMBER, inventory_bytes),
        "profile": COMPLIANCE_PROFILE_V2,
        "schemaVersion": COMPLIANCE_SCHEMA_VERSION,
        "spdx": {
            **member_identity(SPDX_MEMBER, spdx_bytes),
            "format": SPDX_VERSION,
            "packageCount": len(packages) + 1,
            "relationshipCount": len(spdx_document["relationships"]),
        },
        "swiftExternalDependencyCount": 0,
    }
    return members, summary


def open_physical_output_directory(
    directory: Path,
) -> tuple[int, Path]:
    absolute = Path(os.path.abspath(os.fspath(directory)))
    if not absolute.is_absolute() or not absolute.name:
        raise ComplianceError(f"invalid output directory: {directory}")
    required_flags = ("O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required_flags):
        raise ComplianceError("platform lacks required no-follow output flags")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_flags |= getattr(os, "O_CLOEXEC", 0)
    descriptor = -1
    try:
        descriptor = os.open(absolute.anchor, directory_flags)
        for part in absolute.parts[1:]:
            try:
                child_descriptor = os.open(
                    part,
                    directory_flags,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                os.mkdir(part, 0o755, dir_fd=descriptor)
                child_descriptor = os.open(
                    part,
                    directory_flags,
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = child_descriptor
        return descriptor, absolute
    except OSError as error:
        if descriptor >= 0:
            os.close(descriptor)
        raise ComplianceError(
            f"output directory must be a physical no-follow path: {directory}: "
            f"{error}"
        ) from error


def write_output_file_no_follow(
    output: Path,
    data: bytes,
    *,
    label: str,
) -> None:
    if type(data) is not bytes:
        raise ComplianceError(f"{label} output must be bytes")
    absolute = Path(os.path.abspath(os.fspath(output)))
    if absolute.name in ("", ".", ".."):
        raise ComplianceError(f"invalid {label} output path: {output}")
    parent_descriptor, _parent = open_physical_output_directory(absolute.parent)
    file_descriptor = -1
    try:
        try:
            existing = os.stat(
                absolute.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            existing = None
        if existing is not None and (
            not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1
        ):
            raise ComplianceError(
                f"{label} output must be a regular single-link file: {output}"
            )

        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
        flags |= getattr(os, "O_CLOEXEC", 0)
        file_descriptor = os.open(
            absolute.name,
            flags,
            0o644,
            dir_fd=parent_descriptor,
        )
        opened = os.fstat(file_descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ComplianceError(
                f"{label} output descriptor is not a regular single-link file"
            )
        os.ftruncate(file_descriptor, 0)
        remaining = memoryview(data)
        while remaining:
            written = os.write(file_descriptor, remaining)
            if written < 1:
                raise ComplianceError(f"{label} output write made no progress")
            remaining = remaining[written:]
        os.fsync(file_descriptor)
        after = os.fstat(file_descriptor)
        final = os.stat(
            absolute.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        opened_identity = (opened.st_dev, opened.st_ino)
        if (
            (after.st_dev, after.st_ino) != opened_identity
            or (final.st_dev, final.st_ino) != opened_identity
            or after.st_size != len(data)
            or final.st_size != len(data)
            or after.st_nlink != 1
            or final.st_nlink != 1
            or not stat.S_ISREG(final.st_mode)
        ):
            raise ComplianceError(f"{label} output identity changed during write")
    except OSError as error:
        raise ComplianceError(f"cannot write {label} output {output}: {error}") from error
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        os.close(parent_descriptor)


def write_release_compliance_members(
    output_directory: Path,
    members: list[tuple[str, bytes]],
) -> None:
    for member_path, data in members:
        relative = PurePosixPath(member_path)
        if (
            relative.is_absolute()
            or any(part in ("", ".", "..") for part in relative.parts)
            or relative.as_posix() != member_path
        ):
            raise ComplianceError(
                f"invalid release compliance member output path: {member_path}"
            )
        write_output_file_no_follow(
            output_directory.joinpath(*relative.parts),
            data,
            label=member_path,
        )


def refresh_catalog(output: Path, root: Path = ROOT) -> None:
    catalog = refreshed_catalog(root)
    data = canonical_json_bytes(catalog)
    write_output_file_no_follow(output, data, label="catalog")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="refresh checked-in POM license evidence from public Maven repositories",
    )
    refresh_parser.add_argument("--output", type=Path, default=CATALOG_PATH)
    subparsers.add_parser(
        "check",
        help="validate the checked-in catalog and fixed release metadata offline",
    )
    render_parser = subparsers.add_parser(
        "render",
        help="render deterministic SPDX and text inventory bytes for inspection",
    )
    render_parser.add_argument("--marketing-version", default="1.0.0")
    render_parser.add_argument("--build-number", type=int, required=True)
    render_parser.add_argument(
        "--source-snapshot-sha256",
        required=True,
        help="exact source snapshot digest recorded by the release manifest",
    )
    render_parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        if arguments.command == "refresh":
            refresh_catalog(arguments.output)
            print(f"Release compliance catalog refreshed: {arguments.output}")
            return 0
        if arguments.command == "check":
            _, _, packages = load_catalog()
            load_release_metadata()
            print(
                "Release compliance catalog OK: "
                f"Gradle packages={len(packages)}; Swift external packages=0."
            )
            return 0
        members, _ = build_release_compliance(
            marketing_version=arguments.marketing_version,
            build_number=arguments.build_number,
            source_snapshot_sha256=arguments.source_snapshot_sha256,
        )
        write_release_compliance_members(arguments.output_dir, members)
        print(f"Release compliance bytes rendered: {arguments.output_dir}")
        return 0
    except (ComplianceError, OSError) as error:
        print(f"Release compliance failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
