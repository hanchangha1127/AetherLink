#!/usr/bin/env python3
"""Independently validate archived release license inventory and SPDX bytes."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.parse


CATALOG_SCHEMA_VERSION = 1
METADATA_SCHEMA_VERSION = 1
COMPLIANCE_SCHEMA_VERSION_V2 = 2
COMPLIANCE_PROFILE_V1 = "aetherlink-release-compliance-v1"
COMPLIANCE_PROFILE_V2 = "aetherlink-release-compliance-v2"
CATALOG_DOCUMENT_TYPE = "aetherlink.maven-pom-license-inventory"
SPDX_VERSION = "SPDX-2.3"
SPDX_DATA_LICENSE = "CC0-1.0"
MAX_POM_BYTES = 4 * 1024 * 1024
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
CATALOG_SOURCE = "release/third-party-license-inventory-v1.json"
METADATA_SOURCE = "release/release-compliance-metadata-v1.json"
CATALOG_MEMBER = "compliance/third-party-license-inventory-v1.json"
METADATA_MEMBER = "compliance/release-compliance-metadata-v1.json"
NOTICE_MEMBER = "compliance/THIRD_PARTY_LICENSE_INVENTORY.txt"
SPDX_MEMBER = "compliance/sbom.spdx.json"
GRADLE_LOCK_PATHS = (
    "apps/android/app/gradle.lockfile",
    "apps/android/core/pairing/gradle.lockfile",
    "apps/android/core/protocol/gradle.lockfile",
    "apps/android/core/transport/gradle.lockfile",
    "buildscript-gradle.lockfile",
    "settings-gradle.lockfile",
)
V1_KNOWN_CONFIGURATIONS = frozenset(
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
V2_KNOWN_CONFIGURATIONS = frozenset(
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
V2_RUNTIME_CONFIGURATIONS = frozenset({"releaseRuntimeClasspath"})
V2_BUILD_DEPENDENCY_CONFIGURATIONS = frozenset(
    {"releaseCompileClasspath"}
)
V2_BUILD_TOOL_CONFIGURATIONS = frozenset(
    V2_KNOWN_CONFIGURATIONS
    - V2_RUNTIME_CONFIGURATIONS
    - V2_BUILD_DEPENDENCY_CONFIGURATIONS
)
V1_MAVEN_REPOSITORIES = (
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
V2_MAVEN_REPOSITORIES = (
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
V1_STANDARD_LICENSE_NAMES = {
    "apache 2.0": "Apache-2.0",
    "apache license v2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "the apache license, version 2.0": "Apache-2.0",
    "the apache software license, version 2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "mit license": "MIT",
    "the mit license": "MIT",
    "mpl 1.1": "MPL-1.1",
}
V2_STANDARD_LICENSE_NAMES = {
    "apache 2.0": "Apache-2.0",
    "apache license v2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "the apache license, version 2.0": "Apache-2.0",
    "the apache software license, version 2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "mit license": "MIT",
    "the mit license": "MIT",
    "mpl 1.1": "MPL-1.1",
}
V1_REVIEW_BOUNDARY = {
    "artifactFilesAnalyzed": False,
    "binaryArtifactChecksumsIncluded": False,
    "licenseCompatibilityConclusionIncluded": False,
    "licenseConcluded": "NOASSERTION",
    "networkRequiredForReleaseBuild": False,
    "source": "Maven POM license declarations with parent inheritance",
}
V2_REVIEW_BOUNDARY = {
    "artifactFilesAnalyzed": False,
    "binaryArtifactChecksumsIncluded": False,
    "licenseCompatibilityConclusionIncluded": False,
    "licenseConcluded": "NOASSERTION",
    "networkRequiredForReleaseBuild": False,
    "source": "Maven POM license declarations with parent inheritance",
}

# Backward-compatible public aliases describe the current profile only.
KNOWN_CONFIGURATIONS = V2_KNOWN_CONFIGURATIONS
MAVEN_REPOSITORIES = V2_MAVEN_REPOSITORIES
STANDARD_LICENSE_NAMES = V2_STANDARD_LICENSE_NAMES


class ComplianceVerificationError(ValueError):
    """Raised when archived compliance bytes fail independent readback."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
        raise ComplianceVerificationError(
            f"value is not canonical JSON: {error}"
        ) from error


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ComplianceVerificationError(
                f"JSON object contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def reject_json_constant(value: str) -> object:
    raise ComplianceVerificationError(
        f"non-finite JSON constant is not allowed: {value}"
    )


def parse_canonical_json(data: bytes, label: str) -> dict[str, object]:
    if (
        data.startswith(b"\xef\xbb\xbf")
        or b"\r" in data
        or not data.endswith(b"\n")
    ):
        raise ComplianceVerificationError(
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
        raise ComplianceVerificationError(
            f"{label} is invalid JSON: {error}"
        ) from error
    if type(value) is not dict:
        raise ComplianceVerificationError(f"{label} must be a JSON object")
    if canonical_json_bytes(value) != data:
        raise ComplianceVerificationError(f"{label} is not canonical JSON")
    return value


def exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise ComplianceVerificationError(
            f"{label} field set differs; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def exact_int(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ComplianceVerificationError(
            f"{label} must be an integer >= {minimum}"
        )
    return value


def nonempty_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ComplianceVerificationError(f"{label} must be a nonempty string")
    return value


def parse_coordinate(coordinate: str, label: str) -> tuple[str, str, str]:
    parts = coordinate.split(":")
    if len(parts) != 3 or any(
        re.fullmatch(r"[A-Za-z0-9_.+-]+", part) is None for part in parts
    ):
        raise ComplianceVerificationError(
            f"{label} has an invalid Maven coordinate"
        )
    return parts[0], parts[1], parts[2]


def purl(group: str, artifact: str, version: str) -> str:
    return (
        "pkg:maven/"
        + urllib.parse.quote(group, safe=".-_")
        + "/"
        + urllib.parse.quote(artifact, safe=".-_")
        + "@"
        + urllib.parse.quote(version, safe=".-_")
    )


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


def profile_contract(
    profile: str,
) -> tuple[
    frozenset[str],
    tuple[tuple[str, str], ...],
    dict[str, str],
    dict[str, object],
]:
    if profile == COMPLIANCE_PROFILE_V1:
        return (
            V1_KNOWN_CONFIGURATIONS,
            V1_MAVEN_REPOSITORIES,
            V1_STANDARD_LICENSE_NAMES,
            V1_REVIEW_BOUNDARY,
        )
    if profile == COMPLIANCE_PROFILE_V2:
        return (
            V2_KNOWN_CONFIGURATIONS,
            V2_MAVEN_REPOSITORIES,
            V2_STANDARD_LICENSE_NAMES,
            V2_REVIEW_BOUNDARY,
        )
    raise ComplianceVerificationError(
        f"unsupported release compliance profile: {profile!r}"
    )


def parse_current_locks(
    root: Path,
    *,
    profile: str = COMPLIANCE_PROFILE_V2,
) -> dict[str, dict[str, set[str]]]:
    validate_gradle_lock_path_universe(root)
    known_configurations, _, _, _ = profile_contract(profile)
    inventory: dict[str, dict[str, set[str]]] = {}
    for relative in GRADLE_LOCK_PATHS:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ComplianceVerificationError(
                f"current Gradle lock is missing: {relative}"
            )
        data = path.read_bytes()
        if (
            data.startswith(b"\xef\xbb\xbf")
            or b"\r" in data
            or not data.endswith(b"\n")
        ):
            raise ComplianceVerificationError(
                f"current Gradle lock is non-canonical: {relative}"
            )
        try:
            text = data.decode("ascii")
        except UnicodeDecodeError as error:
            raise ComplianceVerificationError(
                f"current Gradle lock is not ASCII: {relative}"
            ) from error
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line or line.startswith("#"):
                continue
            if line.count("=") != 1:
                raise ComplianceVerificationError(
                    f"{relative}:{line_number} must contain one '='"
                )
            coordinate, configurations_text = line.split("=", 1)
            if coordinate == "empty":
                if configurations_text and any(
                    re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", item) is None
                    for item in configurations_text.split(",")
                ):
                    raise ComplianceVerificationError(
                        f"{relative}:{line_number} has invalid empty configurations"
                    )
                continue
            group, artifact, version = parse_coordinate(
                coordinate,
                f"{relative}:{line_number}",
            )
            del group, artifact, version
            configurations = configurations_text.split(",")
            if (
                not configurations
                or any(item not in known_configurations for item in configurations)
            ):
                raise ComplianceVerificationError(
                    f"{relative}:{line_number} has unknown configurations"
                )
            record = inventory.setdefault(
                coordinate,
                {"configurations": set(), "lockFiles": set()},
            )
            record["configurations"].update(configurations)
            record["lockFiles"].add(relative)
    if not inventory:
        raise ComplianceVerificationError("current Gradle lock inventory is empty")
    return inventory


def validate_gradle_project_universe(root: Path) -> None:
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
                    raise ComplianceVerificationError(
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
                    raise ComplianceVerificationError(
                        "Gradle project input must be a physical file: "
                        f"{relative.as_posix()}"
                    )
                discovered_paths.add(relative.as_posix())
    except OSError as error:
        raise ComplianceVerificationError(
            f"cannot discover Gradle project inputs: {error}"
        ) from error
    if frozenset(discovered_paths) != expected_paths:
        raise ComplianceVerificationError(
            "Gradle project-file universe differs; "
            f"missing={sorted(expected_paths - discovered_paths)}, "
            f"extra={sorted(discovered_paths - expected_paths)}"
        )

    settings_path = root / GRADLE_SETTINGS_PATH
    if settings_path.is_symlink() or not settings_path.is_file():
        raise ComplianceVerificationError(
            "settings.gradle.kts must be a physical file"
        )
    try:
        settings_bytes = settings_path.read_bytes()
        settings = settings_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ComplianceVerificationError(
            f"cannot read UTF-8 settings.gradle.kts: {error}"
        ) from error
    if (
        len(settings_bytes) != GRADLE_SETTINGS_SIZE
        or hashlib.sha256(settings_bytes).hexdigest()
        != GRADLE_SETTINGS_SHA256
    ):
        raise ComplianceVerificationError(
            "settings.gradle.kts bytes differ from the reviewed V1 profile"
        )
    if "\r" in settings or not settings.endswith("\n"):
        raise ComplianceVerificationError(
            "settings.gradle.kts must use LF line endings"
        )
    if re.search(r"\bincludeBuild\s*\(", settings):
        raise ComplianceVerificationError(
            "Gradle included builds are outside the V1 profile"
        )

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
        raise ComplianceVerificationError("Gradle included-project set differs")
    if (
        project_directories != GRADLE_PROJECT_DIRECTORIES
        or settings.count(".projectDir") != len(GRADLE_PROJECT_DIRECTORIES)
    ):
        raise ComplianceVerificationError(
            "Gradle project-directory mapping differs"
        )

    for _project, relative_text in GRADLE_PROJECT_DIRECTORIES:
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ComplianceVerificationError(
                "Gradle project directory escapes the repository"
            )
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ComplianceVerificationError(
                    "Gradle project directory has a symlink ancestor: "
                    f"{relative_text}"
                )
        if not current.is_dir():
            raise ComplianceVerificationError(
                f"Gradle project directory is missing: {relative_text}"
            )


def discovered_gradle_lock_paths(root: Path) -> tuple[str, ...]:
    android_root = root / "apps/android"
    if android_root.is_symlink() or not android_root.is_dir():
        raise ComplianceVerificationError(
            "apps/android must be a physical directory"
        )
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
                    raise ComplianceVerificationError(
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
        raise ComplianceVerificationError(
            f"cannot discover Gradle dependency inputs: {error}"
        ) from error
    for path in root_entries:
        if path.name.endswith("gradle.lockfile"):
            if path.is_symlink() or not path.is_file():
                raise ComplianceVerificationError(
                    f"Gradle lock path must be a physical file: {path.name}"
                )
            candidates.add(path.name)
    for path in android_locks:
        relative = path.relative_to(root)
        if any(part in ignored_segments for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file():
            raise ComplianceVerificationError(
                "Gradle lock path must be a physical file: "
                f"{relative.as_posix()}"
            )
        candidates.add(relative.as_posix())
    for build_file in android_build_files:
        relative = build_file.relative_to(root)
        if any(part in ignored_segments for part in relative.parts):
            continue
        if build_file.is_symlink() or not build_file.is_file():
            raise ComplianceVerificationError(
                "Android module build path must be a physical file: "
                f"{relative.as_posix()}"
            )
        lock_path = build_file.parent / "gradle.lockfile"
        if lock_path.is_symlink() or not lock_path.is_file():
            raise ComplianceVerificationError(
                "Android module has no physical dependency lock: "
                f"{relative.as_posix()}"
            )
    return tuple(sorted(candidates, key=lambda value: value.encode("ascii")))


def validate_gradle_lock_path_universe(root: Path) -> None:
    validate_gradle_project_universe(root)
    actual = discovered_gradle_lock_paths(root)
    if actual != GRADLE_LOCK_PATHS:
        expected = set(GRADLE_LOCK_PATHS)
        observed = set(actual)
        raise ComplianceVerificationError(
            "Gradle lock-file universe differs; "
            f"missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )


def swift_external_dependency_count(
    root: Path,
    *,
    run: object = subprocess.run,
) -> int:
    package_path = root / SWIFT_PACKAGE_PATH
    if package_path.is_symlink() or not package_path.is_file():
        raise ComplianceVerificationError(
            "Package.swift must be a physical file"
        )
    resolved_path = root / SWIFT_PACKAGE_RESOLVED_PATH
    if resolved_path.is_symlink() or resolved_path.exists():
        raise ComplianceVerificationError(
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
        raise ComplianceVerificationError(
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
        raise ComplianceVerificationError(
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
        raise ComplianceVerificationError(
            f"Swift package dependency closure is invalid JSON: {error}"
        ) from error
    if (
        type(package) is not dict
        or type(package.get("dependencies")) is not list
        or type(package.get("targets")) is not list
    ):
        raise ComplianceVerificationError(
            "Swift package dump lacks exact dependency and target arrays"
        )
    dependencies = package["dependencies"]
    if dependencies:
        raise ComplianceVerificationError(
            "Swift external dependencies are unsupported by the current "
            f"release compliance profile: count={len(dependencies)}"
        )
    for index, target in enumerate(package["targets"]):
        if type(target) is not dict:
            raise ComplianceVerificationError(
                f"Swift target {index} must be a JSON object"
            )
        if target.get("type") == "binary" or target.get("url") is not None:
            raise ComplianceVerificationError(
                "Swift binary target is outside the zero-external-dependency "
                f"profile: target {index}"
            )
    return 0


def normalized_license_key(name: str) -> str:
    return " ".join(name.casefold().split())


def expected_spdx_expression_for_profile(
    licenses: list[dict[str, str]],
    *,
    profile: str,
) -> str:
    _, _, standard_license_names, _ = profile_contract(profile)
    identifiers: set[str] = set()
    for license_record in licenses:
        identifier = standard_license_names.get(
            normalized_license_key(license_record["name"])
        )
        if identifier is None:
            return "NOASSERTION"
        identifiers.add(identifier)
    if not identifiers:
        return "NOASSERTION"
    return " OR ".join(sorted(identifiers))


def expected_spdx_expression(licenses: list[dict[str, str]]) -> str:
    return expected_spdx_expression_for_profile(
        licenses,
        profile=COMPLIANCE_PROFILE_V2,
    )


def validate_license_record(value: object, label: str) -> dict[str, str]:
    if type(value) is not dict:
        raise ComplianceVerificationError(f"{label} must be an object")
    exact_keys(
        value,
        {"comments", "distribution", "name", "url"},
        label,
    )
    record: dict[str, str] = {}
    for key in ("comments", "distribution", "name", "url"):
        field = value.get(key)
        if type(field) is not str or "\r" in field or "\n" in field:
            raise ComplianceVerificationError(
                f"{label}.{key} must be a single-line string"
            )
        record[key] = field
    if not any(record.values()):
        raise ComplianceVerificationError(
            f"{label} must contain a declared value"
        )
    return record


def validate_catalog(
    catalog: dict[str, object],
    *,
    manifest_lock_files: list[dict[str, object]],
    current_locks: dict[str, dict[str, set[str]]] | None,
    profile: str = COMPLIANCE_PROFILE_V2,
) -> list[dict[str, object]]:
    (
        known_configurations,
        maven_repositories,
        _,
        expected_boundary,
    ) = profile_contract(profile)
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
        exact_int(
            catalog.get("schemaVersion"),
            "catalog.schemaVersion",
            minimum=1,
        )
        != CATALOG_SCHEMA_VERSION
        or catalog.get("documentType") != CATALOG_DOCUMENT_TYPE
    ):
        raise ComplianceVerificationError("catalog identity is unsupported")
    expected_repositories = [
        {"baseUrl": base_url, "id": repository_id}
        for repository_id, base_url in maven_repositories
    ]
    if catalog.get("repositories") != expected_repositories:
        raise ComplianceVerificationError(
            "catalog repository list is not canonical"
        )
    if catalog.get("reviewBoundary") != expected_boundary:
        raise ComplianceVerificationError("catalog review boundary differs")
    if (
        exact_int(
            catalog.get("swiftExternalDependencyCount"),
            "catalog.swiftExternalDependencyCount",
        )
        != 0
    ):
        raise ComplianceVerificationError(
            "catalog Swift external dependency count must be zero"
        )

    catalog_lock_files = catalog.get("gradleLockFiles")
    if type(catalog_lock_files) is not list:
        raise ComplianceVerificationError(
            "catalog gradleLockFiles must be an array"
        )
    expected_lock_identities: list[dict[str, object]] = []
    for index, record in enumerate(manifest_lock_files):
        if type(record) is not dict:
            raise ComplianceVerificationError(
                f"manifest lock record {index} must be an object"
            )
        expected_lock_identities.append(
            {
                "path": record.get("path"),
                "sha256": record.get("sha256"),
                "size": record.get("size"),
            }
        )
    if catalog_lock_files != expected_lock_identities:
        raise ComplianceVerificationError(
            "catalog Gradle lock identities differ from the manifest"
        )

    records_value = catalog.get("pomRecords")
    if type(records_value) is not list or not records_value:
        raise ComplianceVerificationError(
            "catalog pomRecords must be a nonempty array"
        )
    records: dict[str, dict[str, object]] = {}
    repository_bases = {
        repository_id: base_url
        for repository_id, base_url in maven_repositories
    }
    previous_url: bytes | None = None
    for index, value in enumerate(records_value):
        if type(value) is not dict:
            raise ComplianceVerificationError(
                f"pomRecords[{index}] must be an object"
            )
        exact_keys(
            value,
            {"coordinate", "repository", "sha256", "size", "url"},
            f"pomRecords[{index}]",
        )
        coordinate = nonempty_string(
            value.get("coordinate"),
            f"pomRecords[{index}].coordinate",
        )
        group, artifact, version = parse_coordinate(
            coordinate,
            f"pomRecords[{index}].coordinate",
        )
        repository = nonempty_string(
            value.get("repository"),
            f"pomRecords[{index}].repository",
        )
        if repository not in repository_bases:
            raise ComplianceVerificationError(
                f"pomRecords[{index}] repository is unknown"
            )
        url = nonempty_string(value.get("url"), f"pomRecords[{index}].url")
        expected_url = (
            repository_bases[repository]
            + "/"
            + pom_relative_path(group, artifact, version)
        )
        try:
            url_bytes = url.encode("ascii")
        except UnicodeEncodeError as error:
            raise ComplianceVerificationError(
                f"pomRecords[{index}].url must be ASCII"
            ) from error
        if (
            url != expected_url
            or url in records
            or (previous_url is not None and url_bytes <= previous_url)
        ):
            raise ComplianceVerificationError(
                "POM record URLs must be unique and strictly sorted"
            )
        previous_url = url_bytes
        digest = nonempty_string(
            value.get("sha256"),
            f"pomRecords[{index}].sha256",
        )
        size = exact_int(
            value.get("size"),
            f"pomRecords[{index}].size",
            minimum=1,
        )
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None or size > MAX_POM_BYTES:
            raise ComplianceVerificationError(
                f"pomRecords[{index}] byte identity is invalid"
            )
        records[url] = value

    packages_value = catalog.get("packages")
    if type(packages_value) is not list or not packages_value:
        raise ComplianceVerificationError(
            "catalog packages must be a nonempty array"
        )
    package_count = exact_int(
        catalog.get("gradleLockedPackageCount"),
        "catalog.gradleLockedPackageCount",
        minimum=1,
    )
    if package_count != len(packages_value):
        raise ComplianceVerificationError(
            "catalog Gradle package count differs from its array"
        )
    packages: list[dict[str, object]] = []
    previous_coordinate: bytes | None = None
    seen: set[str] = set()
    for index, value in enumerate(packages_value):
        if type(value) is not dict:
            raise ComplianceVerificationError(
                f"packages[{index}] must be an object"
            )
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
        try:
            coordinate_bytes = coordinate.encode("ascii")
        except UnicodeEncodeError as error:
            raise ComplianceVerificationError(
                f"packages[{index}].coordinate must be ASCII"
            ) from error
        if (
            coordinate in seen
            or (
                previous_coordinate is not None
                and coordinate_bytes <= previous_coordinate
            )
        ):
            raise ComplianceVerificationError(
                "catalog package coordinates must be unique and strictly sorted"
            )
        seen.add(coordinate)
        previous_coordinate = coordinate_bytes
        group, artifact, version = parse_coordinate(
            coordinate,
            f"packages[{index}].coordinate",
        )
        if (
            value.get("group") != group
            or value.get("artifact") != artifact
            or value.get("version") != version
            or value.get("purl") != purl(group, artifact, version)
        ):
            raise ComplianceVerificationError(
                f"catalog package identity differs: {coordinate}"
            )
        configurations = value.get("configurations")
        lock_files = value.get("lockFiles")
        if (
            type(configurations) is not list
            or not configurations
            or configurations != sorted(set(configurations))
            or any(
                type(item) is not str or item not in known_configurations
                for item in configurations
            )
            or type(lock_files) is not list
            or not lock_files
            or lock_files != sorted(set(lock_files))
            or any(item not in GRADLE_LOCK_PATHS for item in lock_files)
        ):
            raise ComplianceVerificationError(
                f"catalog package lock coverage is invalid: {coordinate}"
            )
        if current_locks is not None:
            if coordinate not in current_locks:
                raise ComplianceVerificationError(
                    f"catalog package is absent from current locks: {coordinate}"
                )
            if (
                configurations
                != sorted(current_locks[coordinate]["configurations"])
                or lock_files != sorted(current_locks[coordinate]["lockFiles"])
            ):
                raise ComplianceVerificationError(
                    f"catalog package differs from current locks: {coordinate}"
                )
        chain = value.get("pomChain")
        if (
            type(chain) is not list
            or not chain
            or len(set(chain)) != len(chain)
            or any(type(item) is not str or item not in records for item in chain)
        ):
            raise ComplianceVerificationError(
                f"catalog package POM chain is invalid: {coordinate}"
            )
        if records[chain[0]].get("coordinate") != coordinate:
            raise ComplianceVerificationError(
                f"catalog direct POM differs: {coordinate}"
            )
        if value.get("licenseEvidenceSource") != chain[-1]:
            raise ComplianceVerificationError(
                f"catalog license evidence source differs: {coordinate}"
            )
        licenses_value = value.get("pomDeclaredLicenses")
        if type(licenses_value) is not list or not licenses_value:
            raise ComplianceVerificationError(
                f"catalog package lacks license evidence: {coordinate}"
            )
        licenses = [
            validate_license_record(
                license_record,
                f"packages[{index}].pomDeclaredLicenses[{license_index}]",
            )
            for license_index, license_record in enumerate(licenses_value)
        ]
        if value.get(
            "spdxLicenseDeclared"
        ) != expected_spdx_expression_for_profile(
            licenses,
            profile=profile,
        ):
            raise ComplianceVerificationError(
                f"catalog SPDX declaration differs: {coordinate}"
            )
        packages.append(value)
    if current_locks is not None and seen != set(current_locks):
        raise ComplianceVerificationError(
            "catalog coordinate set differs from current Gradle locks"
        )
    return packages


def validate_metadata_v1(metadata: dict[str, object]) -> None:
    """Validate the exact metadata contract archived by Build 7."""
    exact_keys(
        metadata,
        {"creator", "schemaVersion", "spdxCreated"},
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
        raise ComplianceVerificationError(
            "release compliance metadata schema is unsupported"
        )
    if metadata.get("creator") != "Organization: AetherLink":
        raise ComplianceVerificationError(
            "Build 7 release compliance metadata creator differs"
        )
    if metadata.get("spdxCreated") != "2026-07-29T00:00:00Z":
        raise ComplianceVerificationError(
            "Build 7 release compliance metadata timestamp differs"
        )


def validate_metadata_v2(metadata: dict[str, object]) -> None:
    exact_keys(
        metadata,
        {"creator", "schemaVersion", "spdxCreated"},
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
        raise ComplianceVerificationError(
            "release compliance metadata schema is unsupported"
        )
    creator = nonempty_string(
        metadata.get("creator"),
        "release compliance metadata.creator",
    )
    if not creator.startswith(("Organization: ", "Person: ", "Tool: ")):
        raise ComplianceVerificationError(
            "release compliance metadata creator is invalid"
        )
    created = nonempty_string(
        metadata.get("spdxCreated"),
        "release compliance metadata.spdxCreated",
    )
    if re.fullmatch(
        r"[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])T"
        r"([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z",
        created,
    ) is None:
        raise ComplianceVerificationError(
            "release compliance metadata timestamp is invalid"
        )


def package_id(coordinate: str) -> str:
    return (
        "SPDXRef-Maven-"
        + hashlib.sha256(coordinate.encode("ascii")).hexdigest()[:24]
    )


def relationship_type_v1(configurations: list[str]) -> str:
    """Frozen Build 7 precedence-compressed relationship mapping."""
    if "releaseRuntimeClasspath" in configurations:
        return "RUNTIME_DEPENDENCY_OF"
    if "releaseCompileClasspath" in configurations:
        return "DEPENDENCY_OF"
    return "BUILD_DEPENDENCY_OF"


def relationship_types_v2(configurations: list[str]) -> tuple[str, ...]:
    configuration_set = set(configurations)
    unknown = configuration_set - V2_KNOWN_CONFIGURATIONS
    if not configuration_set or unknown:
        raise ComplianceVerificationError(
            "package contains unknown Gradle configurations: "
            f"{sorted(unknown) if unknown else configurations}"
        )
    relationship_types: set[str] = set()
    if configuration_set & V2_RUNTIME_CONFIGURATIONS:
        relationship_types.add("RUNTIME_DEPENDENCY_OF")
    if configuration_set & V2_BUILD_DEPENDENCY_CONFIGURATIONS:
        relationship_types.add("BUILD_DEPENDENCY_OF")
    if configuration_set & V2_BUILD_TOOL_CONFIGURATIONS:
        relationship_types.add("BUILD_TOOL_OF")
    if not relationship_types:
        raise ComplianceVerificationError(
            "package has no SPDX dependency relationship"
        )
    return tuple(sorted(relationship_types))


def spdx_packages_and_relationships(
    packages: list[dict[str, object]],
    *,
    profile: str,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    if profile not in (COMPLIANCE_PROFILE_V1, COMPLIANCE_PROFILE_V2):
        raise ComplianceVerificationError(
            f"unsupported release compliance profile: {profile!r}"
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
            "versionInfo": "",
        }
    ]
    relationships: list[dict[str, str]] = []
    for package in packages:
        coordinate = str(package["coordinate"])
        spdx_id = package_id(coordinate)
        spdx_packages.append(
            {
                "SPDXID": spdx_id,
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
        relationship_types = (
            (relationship_type_v1(configurations),)
            if profile == COMPLIANCE_PROFILE_V1
            else relationship_types_v2(configurations)
        )
        for relationship_type in relationship_types:
            relationships.append(
                {
                    "relatedSpdxElement": "SPDXRef-Package-AetherLink",
                    "relationshipType": relationship_type,
                    "spdxElementId": spdx_id,
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
    return spdx_packages, relationships


def expected_spdx_v1(
    *,
    catalog_bytes: bytes,
    packages: list[dict[str, object]],
    metadata: dict[str, object],
    marketing_version: str,
    build_number: int,
) -> dict[str, object]:
    """Reconstruct the immutable, profile-less Build 7 SPDX document."""
    if type(build_number) is not int or build_number != 7:
        raise ComplianceVerificationError(
            "release compliance profile v1 is restricted to Build 7"
        )
    release_name = f"AetherLink-{marketing_version}+{build_number}-local-v1"
    spdx_packages, relationships = spdx_packages_and_relationships(
        packages,
        profile=COMPLIANCE_PROFILE_V1,
    )
    for package in spdx_packages:
        if package["SPDXID"] == "SPDXRef-Package-AetherLink":
            package["versionInfo"] = marketing_version
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": metadata["spdxCreated"],
            "creators": [
                metadata["creator"],
                "Tool: AetherLink deterministic release compliance generator v1",
            ],
        },
        "dataLicense": SPDX_DATA_LICENSE,
        "documentDescribes": ["SPDXRef-Package-AetherLink"],
        "documentNamespace": (
            "https://spdx.org/spdxdocs/"
            + release_name.lower()
            + "-"
            + sha256(catalog_bytes)
        ),
        "name": release_name,
        "packages": spdx_packages,
        "relationships": relationships,
        "spdxVersion": SPDX_VERSION,
    }


def validate_source_snapshot_sha256(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ComplianceVerificationError(
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
        raise ComplianceVerificationError(
            f"unsupported release compliance profile: {profile!r}"
        )
    release_name = f"AetherLink-{marketing_version}+{build_number}-local-v1"
    generation_inputs = {
        "catalogSha256": sha256(catalog_bytes),
        "metadataSha256": sha256(canonical_json_bytes(metadata)),
        "profile": profile,
        "release": {
            "buildNumber": build_number,
            "marketingVersion": marketing_version,
            "releaseName": release_name,
        },
        "sourceSnapshotSha256": source_digest,
    }
    namespace_digest = sha256(canonical_json_bytes(generation_inputs))
    return (
        "https://spdx.org/spdxdocs/"
        + release_name.lower()
        + "-"
        + namespace_digest
    )


def expected_spdx_v2(
    *,
    catalog_bytes: bytes,
    packages: list[dict[str, object]],
    metadata: dict[str, object],
    marketing_version: str,
    build_number: int,
    source_snapshot_sha256: str,
) -> dict[str, object]:
    if type(build_number) is not int or build_number < 8:
        raise ComplianceVerificationError(
            "release compliance profile v2 starts at Build 8"
        )
    release_name = f"AetherLink-{marketing_version}+{build_number}-local-v1"
    spdx_packages, relationships = spdx_packages_and_relationships(
        packages,
        profile=COMPLIANCE_PROFILE_V2,
    )
    for package in spdx_packages:
        if package["SPDXID"] == "SPDXRef-Package-AetherLink":
            package["versionInfo"] = marketing_version
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
        "documentNamespace": document_namespace_v2(
            catalog_bytes=catalog_bytes,
            metadata=metadata,
            marketing_version=marketing_version,
            build_number=build_number,
            source_snapshot_sha256=source_snapshot_sha256,
        ),
        "name": release_name,
        "packages": spdx_packages,
        "relationships": relationships,
        "spdxVersion": SPDX_VERSION,
    }


def expected_notice_v1(packages: list[dict[str, object]]) -> bytes:
    """Reconstruct the immutable Build 7 text inventory."""
    lines = [
        "AetherLink third-party license inventory",
        "",
        "Scope: exact Maven coordinates present in the checked-in Gradle lock files.",
        "Evidence: Maven POM license declarations, including parent inheritance.",
        "This inventory does not analyze binary artifacts or conclude license compatibility.",
        "All package licenseConcluded values remain NOASSERTION in the SPDX document.",
        "",
    ]
    for package in packages:
        declarations = package["pomDeclaredLicenses"]
        assert isinstance(declarations, list)
        rendered: list[str] = []
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
        raise ComplianceVerificationError(
            "expected text inventory is non-canonical"
        )
    return text.encode("utf-8")


def expected_notice_v2(packages: list[dict[str, object]]) -> bytes:
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
        rendered: list[str] = []
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
        raise ComplianceVerificationError(
            "expected text inventory is non-canonical"
        )
    return text.encode("utf-8")


def identity(member: str, data: bytes) -> dict[str, object]:
    return {
        "member": member,
        "sha256": sha256(data),
        "size": len(data),
    }


def verify_source_member_identity(
    *,
    source_path: str,
    data: bytes,
    source_identities: dict[str, tuple[int, str]],
) -> None:
    if source_identities.get(source_path) != (len(data), sha256(data)):
        raise ComplianceVerificationError(
            f"archived compliance source identity differs: {source_path}"
        )


def verify_release_compliance(
    *,
    compliance: object,
    payload: dict[str, bytes],
    source_identities: dict[str, tuple[int, str]],
    manifest_lock_files: list[dict[str, object]],
    marketing_version: str,
    build_number: int,
    source_snapshot_sha256: str,
    root: Path,
    compare_current_source: bool,
) -> None:
    if type(compliance) is not dict:
        raise ComplianceVerificationError(
            "manifest compliance must be an object"
        )
    validate_source_snapshot_sha256(source_snapshot_sha256)
    if type(build_number) is not int:
        raise ComplianceVerificationError(
            "release compliance build number must be an integer"
        )
    if build_number == 7:
        profile = COMPLIANCE_PROFILE_V1
    elif build_number >= 8:
        profile = COMPLIANCE_PROFILE_V2
    else:
        raise ComplianceVerificationError(
            "release compliance starts at Build 7"
        )
    expected_members = {
        CATALOG_MEMBER,
        METADATA_MEMBER,
        NOTICE_MEMBER,
        SPDX_MEMBER,
    }
    actual_members = {
        name for name in payload if name.startswith("compliance/")
    }
    if actual_members != expected_members:
        raise ComplianceVerificationError(
            "release compliance member set differs; "
            f"missing={sorted(expected_members - actual_members)}, "
            f"extra={sorted(actual_members - expected_members)}"
        )
    catalog_bytes = payload[CATALOG_MEMBER]
    metadata_bytes = payload[METADATA_MEMBER]
    notice_bytes = payload[NOTICE_MEMBER]
    spdx_bytes = payload[SPDX_MEMBER]
    verify_source_member_identity(
        source_path=CATALOG_SOURCE,
        data=catalog_bytes,
        source_identities=source_identities,
    )
    verify_source_member_identity(
        source_path=METADATA_SOURCE,
        data=metadata_bytes,
        source_identities=source_identities,
    )
    catalog = parse_canonical_json(catalog_bytes, CATALOG_MEMBER)
    metadata = parse_canonical_json(metadata_bytes, METADATA_MEMBER)
    if profile == COMPLIANCE_PROFILE_V1:
        validate_metadata_v1(metadata)
    else:
        validate_metadata_v2(metadata)
    if compare_current_source:
        swift_external_dependency_count(root)
        current_locks = parse_current_locks(root, profile=profile)
    else:
        current_locks = None
    packages = validate_catalog(
        catalog,
        manifest_lock_files=manifest_lock_files,
        current_locks=current_locks,
        profile=profile,
    )
    expected_spdx_document = (
        expected_spdx_v1(
            catalog_bytes=catalog_bytes,
            packages=packages,
            metadata=metadata,
            marketing_version=marketing_version,
            build_number=build_number,
        )
        if profile == COMPLIANCE_PROFILE_V1
        else expected_spdx_v2(
            catalog_bytes=catalog_bytes,
            packages=packages,
            metadata=metadata,
            marketing_version=marketing_version,
            build_number=build_number,
            source_snapshot_sha256=source_snapshot_sha256,
        )
    )
    expected_spdx_bytes = canonical_json_bytes(
        expected_spdx_document
    )
    if spdx_bytes != expected_spdx_bytes:
        raise ComplianceVerificationError(
            "archived SPDX bytes differ from independent rendering"
        )
    expected_notice_bytes = (
        expected_notice_v1(packages)
        if profile == COMPLIANCE_PROFILE_V1
        else expected_notice_v2(packages)
    )
    if notice_bytes != expected_notice_bytes:
        raise ComplianceVerificationError(
            "archived text license inventory differs from independent rendering"
        )
    expected_summary: dict[str, object] = {
        "artifactFilesAnalyzed": False,
        "catalog": identity(CATALOG_MEMBER, catalog_bytes),
        "gradleLockedPackageCount": len(packages),
        "licenseCompatibilityConclusionIncluded": False,
        "licenseConcluded": "NOASSERTION",
        "metadata": identity(METADATA_MEMBER, metadata_bytes),
        "networkRequiredForReleaseBuild": False,
        "notice": identity(NOTICE_MEMBER, notice_bytes),
        "spdx": {
            **identity(SPDX_MEMBER, spdx_bytes),
            "format": SPDX_VERSION,
            "packageCount": len(packages) + 1,
            "relationshipCount": len(expected_spdx_document["relationships"]),
        },
        "swiftExternalDependencyCount": 0,
    }
    if profile == COMPLIANCE_PROFILE_V2:
        expected_summary["profile"] = COMPLIANCE_PROFILE_V2
        expected_summary["schemaVersion"] = COMPLIANCE_SCHEMA_VERSION_V2
    if compliance != expected_summary:
        raise ComplianceVerificationError(
            "manifest compliance summary differs from archived bytes"
        )
