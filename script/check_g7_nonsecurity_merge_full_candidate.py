#!/usr/bin/env python3
"""Independently verify one local non-security G7 Merge-full candidate.

This checker deliberately does not import its producer.  It closes the result
schema, re-reads every declared repository and artifact byte, validates the
zero-issue Android lint report, and (for the CLI) reruns existing readback-only
child checkers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Mapping, Sequence
import xml.etree.ElementTree as ET

if __package__:
    from script import check_product_ci as product_ci
else:
    import check_product_ci as product_ci


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-g7-nonsecurity-merge-full-local-candidate-v1"
SCHEMA_VERSION = 1
SOURCE_ALGORITHM = "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
RESULT_RELATIVE_PATH = Path(
    ".build/aetherlink-g7-nonsecurity-merge-full-candidate-v1/candidate.json"
)
RESULT_MAX_BYTES = 1 * 1024 * 1024
SOURCE_FILE_MAX_BYTES = 64 * 1024 * 1024
SOURCE_TOTAL_MAX_BYTES = 1024 * 1024 * 1024
ARTIFACT_MAX_BYTES = 768 * 1024 * 1024
LINT_XML_MAX_BYTES = 16 * 1024 * 1024
TEXT_MAX_LENGTH = 4096
COMMAND_STREAM_MAX_BYTES = 64 * 1024 * 1024
COMMAND_ARGUMENT_MAX_LENGTH = 128 * 1024
READBACK_STREAM_MAX_BYTES = 1 * 1024 * 1024
ANDROID_LINT_XML_PATH = Path(
    "apps/android/app/build/reports/lint-results-release.xml"
)

EXPECTED_IMPLEMENTATION_PATHS = (
    Path("script/check_g7_nonsecurity_merge_full_candidate.py"),
    Path("script/run_clean_release_reproducibility.py"),
    Path("script/run_g7_nonsecurity_merge_full_candidate.py"),
    Path("script/test_check_g7_nonsecurity_merge_full_candidate.py"),
    Path("script/test_run_g7_nonsecurity_merge_full_candidate.py"),
)

EXPECTED_ARTIFACT_PATHS = (
    Path(".build/aetherlink-current-unsealed-lifecycle-v1/repeatability.json"),
    Path(".build/aetherlink-current-unsealed-lifecycle-v1/result.json"),
    Path(".build/aetherlink-document-ingestion-asan-binding-v1.json"),
    Path(".build/aetherlink-document-ingestion-asan-console-v1.log"),
    Path(".build/aetherlink-document-ingestion-asan-run-marker-v1.json"),
    Path(".build/aetherlink-document-ingestion-mutation-binding-v1.json"),
    Path(".build/aetherlink-document-ingestion-mutation-console-v1.log"),
    Path(".build/aetherlink-document-ingestion-mutation-run-marker-v1.json"),
    Path(".build/aetherlink-product-ci-swift-focused-binding-v1.json"),
    Path(".build/aetherlink-product-ci-swift-focused-console-v1.log"),
    Path(".build/aetherlink-product-ci-swift-focused-run-marker-v1.json"),
    Path(".build/aetherlink-product-ci-swift-test-list-v1.txt"),
    Path(".build/aetherlink-release-diagnostics-v1/android.json"),
    Path(".build/aetherlink-release-diagnostics-v1/macos.json"),
    Path("apps/android/app/build/aetherlink-full-test-run-marker-v1.json"),
    Path("apps/android/app/build/outputs/apk/release/app-release-unsigned.apk"),
    Path("apps/android/app/build/outputs/bundle/release/app-release.aab"),
    Path("apps/android/app/build/outputs/mapping/release/mapping.txt"),
    ANDROID_LINT_XML_PATH,
    Path(
        "apps/android/app/build/test-results/testDebugUnitTest/"
        "aetherlink-full-test-result-binding-v1.json"
    ),
    Path("dist/unsealed-package-only/AetherLink.app/Contents/MacOS/AetherLink"),
    Path(
        "dist/unsealed-package-only/AetherLink.dSYM/Contents/Resources/"
        "DWARF/AetherLink"
    ),
    Path("dist/unsealed-package-only/source-receipt.json"),
)

# The producer must emit these command records in this exact order.  Keeping
# this as one small public constant makes coordinated producer changes explicit.
EXPECTED_COMMAND_IDS = (
    "product-ci-contract",
    "product-ci-contract-self-test",
    "nightly-contract",
    "nightly-contract-tests",
    "product-copy",
    "release-ledger",
    "app-icons",
    "license",
    "release-compliance-catalog",
    "release-compliance-tests",
    "tracked-document-contracts",
    "tracked-document-contract-tests",
    "macos-package-contract-tests",
    "macos-lifecycle-contract-tests",
    "release-diagnostics-contract-tests",
    "release-archive-contract-tests",
    "g7-candidate-contract-tests",
    "macos-debug-compile",
    "swift-test-list",
    "swift-selection-readback",
    "swift-focused-prepare",
    "swift-focused-run",
    "swift-focused-bind",
    "swift-focused-readback",
    "document-ingestion-asan-prepare",
    "document-ingestion-asan-run",
    "document-ingestion-asan-bind",
    "document-ingestion-asan-readback",
    "document-ingestion-mutation-prepare",
    "document-ingestion-mutation-run",
    "document-ingestion-mutation-bind",
    "document-ingestion-mutation-readback",
    "android-full-prepare",
    "android-full-run",
    "android-full-bind",
    "android-full-readback",
    "android-camera-lifecycle-readback",
    "android-camera-controller-readback",
    "android-font-scale-readback",
    "android-release-build",
    "android-release-readback",
    "android-diagnostics-produce",
    "android-diagnostics-readback",
    "macos-release-source-before",
    "macos-unsealed-package-produce",
    "macos-release-source-after",
    "macos-release-readback",
    "macos-diagnostics-produce",
    "macos-diagnostics-readback",
    "macos-lifecycle-produce",
    "macos-lifecycle-readback",
    "final-swift-focused-readback",
    "final-document-ingestion-asan-readback",
    "final-document-ingestion-mutation-readback",
    "final-android-full-readback",
    "final-android-release-readback",
    "final-macos-release-readback",
    "final-android-diagnostics-readback",
    "final-macos-diagnostics-readback",
    "final-macos-lifecycle-readback",
    "final-release-compliance-catalog",
    "final-tracked-document-contracts",
)

EXPECTED_COVERAGE = {
    "androidFullAppClasses": 19,
    "androidFullAppTests": 1226,
    "androidLintIssues": 0,
    "documentIngestionAsanTests": 57,
    "documentIngestionMutationCases": 96,
    "documentIngestionMutationXctestTests": 2,
    "releaseComplianceTests": 22,
    "swiftFocusedTests": 222,
}

EXPECTED_LIMITATIONS = {
    "canonicalG7ExitClaimed": False,
    "canonicalMergeFullClaimed": False,
    "completeSwiftSuiteClaimed": False,
    "deviceOrNetworkClaimed": False,
    "hostedCiClaimed": False,
    "securityAuthenticationCryptographyExecuted": False,
    "signedArtifactsClaimed": False,
    "v1Claimed": False,
}

READBACK_COMMANDS = (
    ("python3", "-B", "script/check_product_ci.py"),
    ("python3", "-B", "script/check_product_ci.py", "--swift-focused-test-results"),
    (
        "python3",
        "-B",
        "script/check_product_ci.py",
        "--document-ingestion-asan-results",
    ),
    (
        "python3",
        "-B",
        "script/check_product_ci.py",
        "--document-ingestion-mutation-results",
    ),
    ("python3", "-B", "script/check_product_ci.py", "--android-full-test-results"),
    (
        "python3",
        "-B",
        "script/check_release_artifact_archive.py",
        "--android-build-outputs",
    ),
    (
        "python3",
        "-B",
        "script/check_release_diagnostics_usability.py",
        "--platform",
        "android",
        ".build/aetherlink-release-diagnostics-v1/android.json",
    ),
    (
        "python3",
        "-B",
        "script/check_release_artifact_archive.py",
        "--macos-build-outputs",
    ),
    (
        "python3",
        "-B",
        "script/check_release_diagnostics_usability.py",
        "--platform",
        "macos",
        ".build/aetherlink-release-diagnostics-v1/macos.json",
    ),
    ("python3", "-B", "script/check_macos_current_unsealed_ci_lifecycle.py"),
)

ANDROID_FULL_COMMAND = (
    "./gradlew",
    "--offline",
    "--no-daemon",
    "--console=plain",
    "--rerun-tasks",
    "-Pkotlin.incremental=false",
    ":app:compileDebugKotlin",
    ":app:testDebugUnitTest",
    *tuple(
        argument
        for test_name in product_ci.ANDROID_MAIN_FULL_TESTS
        for argument in ("--tests", test_name)
    ),
)

ANDROID_RELEASE_COMMAND = (
    "./gradlew",
    "--offline",
    "--no-daemon",
    "--console=plain",
    "-PaetherlinkStrictReleaseDependencyLocks=true",
    "-Pkotlin.incremental=false",
    ":app:assembleRelease",
    ":app:bundleRelease",
    ":app:lintRelease",
)

# Commands that establish or consume the material child evidence are pinned
# independently here.  Supporting unit/static commands still receive a closed,
# bounded argv record and exact ordered identifier.
CRITICAL_COMMAND_ARGV = {
    "product-ci-contract": ("python3", "-B", "script/check_product_ci.py"),
    "release-compliance-tests": (
        "python3",
        "-B",
        "script/check_product_ci.py",
        "--run-release-compliance-tests",
    ),
    "g7-candidate-contract-tests": (
        "python3",
        "-B",
        "-m",
        "unittest",
        "script.test_run_g7_nonsecurity_merge_full_candidate",
        "script.test_check_g7_nonsecurity_merge_full_candidate",
    ),
    "swift-test-list": ("swift", "test", "list"),
    "swift-focused-run": (
        "python3",
        "-B",
        "script/check_product_ci.py",
        "--run-swift-focused-tests",
        "--swift-focused-filter",
        product_ci.SWIFT_FILTER,
    ),
    "android-full-run": ANDROID_FULL_COMMAND,
    "android-release-build": ANDROID_RELEASE_COMMAND,
    "android-release-readback": (
        "python3",
        "-B",
        "script/check_release_artifact_archive.py",
        "--android-build-outputs",
    ),
    "macos-release-source-before": (
        "python3",
        "-B",
        "script/package_release_artifacts.py",
        "source-digest",
    ),
    "macos-unsealed-package-produce": (
        "/usr/bin/env",
        (
            "AETHERLINK_REPRO_SWIFT_SCRATCH_PATH="
            "/private/tmp/aetherlink-g6-swift-scratch-v1"
        ),
        "./script/build_and_run.sh",
        "--unsealed-package-only",
    ),
    "macos-release-source-after": (
        "python3",
        "-B",
        "script/package_release_artifacts.py",
        "source-digest",
    ),
    "macos-release-readback": (
        "python3",
        "-B",
        "script/check_release_artifact_archive.py",
        "--macos-build-outputs",
    ),
    "macos-lifecycle-produce": (
        "python3",
        "-B",
        "script/run_macos_current_unsealed_install_recovery_smoke.py",
        "--result",
        ".build/aetherlink-current-unsealed-lifecycle-v1/result.json",
        "--repeatability-result",
        ".build/aetherlink-current-unsealed-lifecycle-v1/repeatability.json",
    ),
    "final-swift-focused-readback": READBACK_COMMANDS[1],
    "final-document-ingestion-asan-readback": READBACK_COMMANDS[2],
    "final-document-ingestion-mutation-readback": READBACK_COMMANDS[3],
    "final-android-full-readback": READBACK_COMMANDS[4],
    "final-android-release-readback": READBACK_COMMANDS[5],
    "final-android-diagnostics-readback": READBACK_COMMANDS[6],
    "final-macos-release-readback": READBACK_COMMANDS[7],
    "final-macos-diagnostics-readback": READBACK_COMMANDS[8],
    "final-macos-lifecycle-readback": READBACK_COMMANDS[9],
}


class CandidateError(RuntimeError):
    """Raised when candidate evidence fails its closed contract."""


class DuplicateKeyError(ValueError):
    """Raised for a duplicate JSON object name."""


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise CandidateError(f"{label} exact keys differ")
    return value


def require_exact_int(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if type(value) is not int or value < minimum:
        raise CandidateError(f"{label} must be an exact integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise CandidateError(f"{label} exceeds {maximum}")
    return value


def require_bool(value: object, expected: bool, label: str) -> None:
    if type(value) is not bool or value is not expected:
        raise CandidateError(f"{label} must be the exact boolean {expected}")


def require_text(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
    maximum: int = TEXT_MAX_LENGTH,
) -> str:
    if type(value) is not str or len(value) > maximum or (not allow_empty and not value):
        raise CandidateError(f"{label} must be bounded text")
    if "\x00" in value:
        raise CandidateError(f"{label} contains NUL")
    return value


def require_sha256(value: object, label: str) -> str:
    text = require_text(value, label, maximum=64)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CandidateError(f"{label} must be lowercase SHA-256")
    return text


def validate_relative_path(value: object, label: str) -> Path:
    text = require_text(value, label)
    path = Path(text)
    if (
        path.is_absolute()
        or path in (Path("."), Path(".."))
        or any(part in ("", ".", "..") for part in path.parts)
        or path.as_posix() != text
    ):
        raise CandidateError(f"{label} is not a canonical root-relative path")
    try:
        text.encode("ascii")
    except UnicodeEncodeError as error:
        raise CandidateError(f"{label} must be ASCII") from error
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in text):
        raise CandidateError(f"{label} contains a control character")
    return path


def _identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_uid,
        status.st_gid,
        status.st_nlink,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _require_physical_parents(root: Path, relative: Path) -> None:
    try:
        root_status = root.lstat()
    except OSError as error:
        raise CandidateError(f"repository root cannot be inspected: {error}") from error
    if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(root_status.st_mode):
        raise CandidateError("repository root must be a physical directory")
    current = root
    for component in relative.parts[:-1]:
        current = current / component
        try:
            status = current.lstat()
        except OSError as error:
            raise CandidateError(
                f"parent cannot be inspected for {relative.as_posix()}: {error}"
            ) from error
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
            raise CandidateError(
                f"parent must be a physical directory: {relative.as_posix()}"
            )


def read_stable_regular_file(
    root: Path,
    relative: Path,
    *,
    maximum_bytes: int,
) -> tuple[bytes, int]:
    validate_relative_path(relative.as_posix(), "file path")
    _require_physical_parents(root, relative)
    path = root / relative
    try:
        before = path.lstat()
    except OSError as error:
        raise CandidateError(f"file cannot be inspected: {relative}: {error}") from error
    mode = stat.S_IMODE(before.st_mode)
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
    ):
        raise CandidateError(
            f"file must be a physical single-link regular file: {relative}"
        )
    if before.st_size < 0 or before.st_size > maximum_bytes:
        raise CandidateError(f"file size is outside its bound: {relative}")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise CandidateError(f"file cannot be opened: {relative}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(before):
            raise CandidateError(f"file changed before read: {relative}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise CandidateError(f"file exceeds its byte bound: {relative}")
        final_descriptor = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = path.lstat()
    except OSError as error:
        raise CandidateError(f"file disappeared after read: {relative}: {error}") from error
    if _identity(before) != _identity(final_descriptor) or _identity(before) != _identity(after):
        raise CandidateError(f"file changed during read: {relative}")
    data = b"".join(chunks)
    if len(data) != before.st_size:
        raise CandidateError(f"file size changed during read: {relative}")
    return data, mode


def file_record(root: Path, relative: Path, *, maximum_bytes: int) -> dict[str, object]:
    data, mode = read_stable_regular_file(root, relative, maximum_bytes=maximum_bytes)
    return {
        "mode": mode,
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def collect_source_paths(root: Path) -> tuple[Path, ...]:
    command = (
        "git",
        "-C",
        str(root),
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise CandidateError(f"git source inventory failed: {error}") from error
    if completed.returncode != 0 or completed.stderr:
        detail = completed.stderr[:4096].decode("utf-8", errors="replace")
        raise CandidateError(f"git source inventory failed: {detail}")
    raw_paths = completed.stdout.split(b"\0")
    if raw_paths and raw_paths[-1] == b"":
        raw_paths.pop()
    paths: list[Path] = []
    for raw_path in raw_paths:
        try:
            text = raw_path.decode("ascii")
        except UnicodeDecodeError as error:
            raise CandidateError("git source path must be ASCII") from error
        relative = validate_relative_path(text, "git source path")
        if relative == Path("README.md") or relative.parts[0] == "docs":
            continue
        paths.append(relative)
    if len(paths) != len(set(paths)):
        raise CandidateError("git source inventory contains duplicate paths")
    return tuple(sorted(paths, key=lambda item: item.as_posix().encode("ascii")))


def source_snapshot(root: Path) -> dict[str, object]:
    paths = collect_source_paths(root)
    if not paths:
        raise CandidateError("source inventory must not be empty")
    digest = hashlib.sha256()
    total = 0
    for relative in paths:
        data, mode = read_stable_regular_file(
            root,
            relative,
            maximum_bytes=SOURCE_FILE_MAX_BYTES,
        )
        total += len(data)
        if total > SOURCE_TOTAL_MAX_BYTES:
            raise CandidateError("source inventory exceeds its total byte bound")
        file_digest = hashlib.sha256(data).hexdigest()
        digest.update(
            relative.as_posix().encode("ascii")
            + b"\0"
            + f"{mode:o}".encode("ascii")
            + b"\0"
            + str(len(data)).encode("ascii")
            + b"\0"
            + file_digest.encode("ascii")
            + b"\n"
        )
    return {
        "algorithm": SOURCE_ALGORITHM,
        "fileCount": len(paths),
        "sha256": digest.hexdigest(),
        "size": total,
    }


def validate_file_records(
    value: object,
    *,
    expected_paths: Sequence[Path],
    label: str,
    root: Path,
) -> None:
    if type(value) is not list or len(value) != len(expected_paths):
        raise CandidateError(f"{label} record count differs")
    actual_paths: list[str] = []
    for index, (record, expected_path) in enumerate(zip(value, expected_paths)):
        row = exact_mapping(record, {"mode", "path", "sha256", "size"}, f"{label}[{index}]")
        relative = validate_relative_path(row["path"], f"{label}[{index}].path")
        if relative != expected_path:
            raise CandidateError(f"{label} path sequence differs at index {index}")
        require_exact_int(row["mode"], f"{label}[{index}].mode", maximum=0o7777)
        require_exact_int(
            row["size"],
            f"{label}[{index}].size",
            maximum=ARTIFACT_MAX_BYTES,
        )
        require_sha256(row["sha256"], f"{label}[{index}].sha256")
        expected = file_record(root, relative, maximum_bytes=ARTIFACT_MAX_BYTES)
        if row != expected:
            raise CandidateError(f"{label} file identity differs: {relative}")
        actual_paths.append(relative.as_posix())
    if actual_paths != sorted(actual_paths, key=lambda item: item.encode("ascii")):
        raise CandidateError(f"{label} paths must be ASCII sorted")
    if len(actual_paths) != len(set(actual_paths)):
        raise CandidateError(f"{label} paths must be unique")


def validate_stream_record(value: object, label: str) -> None:
    row = exact_mapping(value, {"sha256", "size"}, label)
    require_exact_int(row["size"], f"{label}.size", maximum=COMMAND_STREAM_MAX_BYTES)
    require_sha256(row["sha256"], f"{label}.sha256")


def validate_commands(value: object) -> None:
    if type(value) is not list or len(value) != len(EXPECTED_COMMAND_IDS):
        raise CandidateError("commands record count differs")
    for index, (record, expected_id) in enumerate(zip(value, EXPECTED_COMMAND_IDS)):
        row = exact_mapping(
            record,
            {
                "argv",
                "cwd",
                "elapsedMilliseconds",
                "exitCode",
                "id",
                "stderr",
                "stdout",
                "timeoutSeconds",
            },
            f"commands[{index}]",
        )
        if row["id"] != expected_id:
            raise CandidateError(f"command id differs at index {index}")
        argv = row["argv"]
        if type(argv) is not list or not argv or len(argv) > 256:
            raise CandidateError(f"commands[{index}].argv must be a bounded list")
        for argument_index, argument in enumerate(argv):
            require_text(
                argument,
                f"commands[{index}].argv[{argument_index}]",
                maximum=COMMAND_ARGUMENT_MAX_LENGTH,
            )
        expected_argv = CRITICAL_COMMAND_ARGV.get(expected_id)
        if expected_argv is not None and tuple(argv) != expected_argv:
            raise CandidateError(f"commands[{index}].argv differs for {expected_id}")
        if row["cwd"] != ".":
            raise CandidateError(f"commands[{index}].cwd must be repository root '.'")
        timeout = require_exact_int(
            row["timeoutSeconds"],
            f"commands[{index}].timeoutSeconds",
            minimum=1,
            maximum=4 * 60 * 60,
        )
        require_exact_int(
            row["elapsedMilliseconds"],
            f"commands[{index}].elapsedMilliseconds",
            maximum=timeout * 1000 + 60_000,
        )
        if require_exact_int(row["exitCode"], f"commands[{index}].exitCode") != 0:
            raise CandidateError(f"commands[{index}] did not exit successfully")
        validate_stream_record(row["stdout"], f"commands[{index}].stdout")
        validate_stream_record(row["stderr"], f"commands[{index}].stderr")


def validate_android_lint(root: Path) -> None:
    data, _ = read_stable_regular_file(
        root,
        ANDROID_LINT_XML_PATH,
        maximum_bytes=LINT_XML_MAX_BYTES,
    )
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise CandidateError("Android lint XML must not contain a DTD or entity declaration")
    try:
        root_element = ET.fromstring(data)
    except ET.ParseError as error:
        raise CandidateError(f"Android lint XML cannot be parsed: {error}") from error
    if root_element.tag != "issues":
        raise CandidateError("Android lint XML root must be issues")
    issues = tuple(root_element.iter("issue"))
    if issues:
        raise CandidateError(f"Android lint XML contains {len(issues)} issue records")


def validate_pid_preservation(value: object) -> None:
    row = exact_mapping(
        value,
        {"after", "before", "pid", "preservedDuringRun", "requested"},
        "pidPreservation",
    )
    if type(row["requested"]) is not bool:
        raise CandidateError("pidPreservation.requested must be an exact boolean")
    if row["requested"] is False:
        expected = {
            "after": "",
            "before": "",
            "pid": 0,
            "preservedDuringRun": False,
            "requested": False,
        }
        if row != expected:
            raise CandidateError("unrequested PID preservation record differs")
        return
    require_exact_int(row["pid"], "pidPreservation.pid", minimum=1)
    before = require_text(row["before"], "pidPreservation.before", maximum=8192)
    after = require_text(row["after"], "pidPreservation.after", maximum=8192)
    require_bool(
        row["preservedDuringRun"],
        True,
        "pidPreservation.preservedDuringRun",
    )
    if before != after:
        raise CandidateError("PID identity changed during the candidate run")


def validate_document(
    document: object,
    *,
    root: Path = ROOT,
    run_readbacks: bool = False,
) -> None:
    row = exact_mapping(
        document,
        {
            "artifacts",
            "commands",
            "contract",
            "coverage",
            "implementation",
            "limitations",
            "pidPreservation",
            "result",
            "schemaVersion",
            "source",
        },
        "result",
    )
    if row["contract"] != CONTRACT:
        raise CandidateError("candidate contract differs")
    if require_exact_int(row["schemaVersion"], "schemaVersion", minimum=1) != SCHEMA_VERSION:
        raise CandidateError("candidate schema version differs")
    if row["result"] != "passed":
        raise CandidateError("candidate result must be passed")

    coverage = exact_mapping(row["coverage"], set(EXPECTED_COVERAGE), "coverage")
    for key, expected in EXPECTED_COVERAGE.items():
        if require_exact_int(coverage[key], f"coverage.{key}") != expected:
            raise CandidateError(f"coverage.{key} differs")

    limitations = exact_mapping(
        row["limitations"], set(EXPECTED_LIMITATIONS), "limitations"
    )
    for key, expected in EXPECTED_LIMITATIONS.items():
        require_bool(limitations[key], expected, f"limitations.{key}")

    recorded_source = exact_mapping(
        row["source"], {"algorithm", "fileCount", "sha256", "size"}, "source"
    )
    if recorded_source["algorithm"] != SOURCE_ALGORITHM:
        raise CandidateError("source algorithm differs")
    require_exact_int(recorded_source["fileCount"], "source.fileCount", minimum=1)
    require_exact_int(recorded_source["size"], "source.size", maximum=SOURCE_TOTAL_MAX_BYTES)
    require_sha256(recorded_source["sha256"], "source.sha256")
    if recorded_source != source_snapshot(root):
        raise CandidateError("source snapshot differs from current repository bytes")

    validate_file_records(
        row["artifacts"],
        expected_paths=EXPECTED_ARTIFACT_PATHS,
        label="artifacts",
        root=root,
    )
    validate_file_records(
        row["implementation"],
        expected_paths=EXPECTED_IMPLEMENTATION_PATHS,
        label="implementation",
        root=root,
    )
    validate_commands(row["commands"])
    validate_pid_preservation(row["pidPreservation"])
    validate_android_lint(root)
    if run_readbacks:
        run_child_readbacks(root)
    if recorded_source != source_snapshot(root):
        raise CandidateError("source snapshot changed during complete readback")
    validate_file_records(
        row["artifacts"],
        expected_paths=EXPECTED_ARTIFACT_PATHS,
        label="artifacts final readback",
        root=root,
    )


def load_result(path: Path, *, root: Path = ROOT) -> Mapping[str, object]:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise CandidateError("result path must be below the repository root") from error
    data, mode = read_stable_regular_file(root, relative, maximum_bytes=RESULT_MAX_BYTES)
    if mode != 0o600:
        raise CandidateError("result must be mode 0600")
    try:
        value = json.loads(data, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, DuplicateKeyError) as error:
        raise CandidateError(f"result JSON cannot be decoded: {error}") from error
    if type(value) is not dict or data != canonical_json_bytes(value):
        raise CandidateError("result must be canonical JSON with one trailing LF")
    return value


def run_child_readbacks(root: Path) -> None:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["PYTHONPATH"] = str(root)
    for command in READBACK_COMMANDS:
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                env=environment,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=180,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise CandidateError(
                f"child readback could not run: {' '.join(command)}: {error}"
            ) from error
        if (
            len(completed.stdout) > READBACK_STREAM_MAX_BYTES
            or len(completed.stderr) > READBACK_STREAM_MAX_BYTES
        ):
            raise CandidateError(f"child readback output exceeded its bound: {' '.join(command)}")
        if completed.returncode != 0:
            detail = completed.stderr[:4096].decode("utf-8", errors="replace")
            raise CandidateError(
                f"child readback failed: {' '.join(command)}: {detail}"
            )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", nargs="?", type=Path, default=ROOT / RESULT_RELATIVE_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    result_path = arguments.result
    if not result_path.is_absolute():
        result_path = ROOT / result_path
    try:
        document = load_result(result_path, root=ROOT)
        validate_document(document, root=ROOT, run_readbacks=True)
        if load_result(result_path, root=ROOT) != document:
            raise CandidateError("candidate result changed during complete readback")
    except (CandidateError, OSError, ValueError) as error:
        print(f"G7 non-security Merge-full candidate readback failed: {error}", file=sys.stderr)
        return 1
    print(
        "G7 non-security Merge-full local candidate readback passed; "
        "canonical Merge-full, G7 exit, and V1 remain unclaimed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
