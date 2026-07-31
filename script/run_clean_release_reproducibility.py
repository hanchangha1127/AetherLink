#!/usr/bin/env python3
"""Run two isolated same-host clean release builds and compare exact bytes."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterator
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import script.package_release_artifacts as archive_builder
import script.check_release_artifact_archive as archive_reader
from script.check_release_version_ledger import (
    LedgerError,
    load_release_version_ledger,
)


WORK_ROOT = Path("/private/tmp/aetherlink-g6-clean-release-repro-v1")
SWIFT_SCRATCH = Path("/private/tmp/aetherlink-g6-swift-scratch-v1")
LOCK_PATH = WORK_ROOT / ".runner.lock"
SWIFT_LEASE_PATH = WORK_ROOT / ".swift-scratch-lease.json"
RESULT_ROOT = ROOT / "dist/reproducibility"
LIFECYCLE_RESULT_ROOT = ROOT / "dist/lifecycle"
LANE_A_LOCAL_DMG_RUNNER = Path(
    "script/run_macos_local_dmg_install_smoke_v2.py"
)
LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER = Path(
    "script/run_macos_local_dmg_uninstall_reinstall_smoke.py"
)
LANE_A_LOCAL_DMG_STATE_RECOVERY_RUNNER = Path(
    "script/run_macos_local_dmg_uninstall_reinstall_state_recovery_smoke.py"
)
LANE_A_LOCAL_DMG_PHASE = "lane-a-local-dmg"
LANE_A_LOCAL_DMG_SCOPE = (
    "same-host-per-user-ephemeral-local-dmg-install-v2"
)
LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_SCOPE = (
    "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-v1"
)
LANE_A_LOCAL_DMG_STATE_RECOVERY_SCOPE = (
    "same-host-per-user-ephemeral-local-dmg-uninstall-reinstall-"
    "state-recovery-v1"
)
LANE_A_LOCAL_DMG_READBACK_MODE = "archive-only-no-current-source"
LANE_A_LOCAL_DMG_TIMEOUT_SECONDS = 720.0
LANE_A_LIFECYCLE_MAX_STDOUT_BYTES = 1024 * 1024
LANE_A_LIFECYCLE_MAX_STDERR_BYTES = 64 * 1024
LANE_A_LIFECYCLE_INTERRUPT_TIMEOUT_SECONDS = 5.0
LANE_A_LOCAL_DMG_INSTALL_FILENAME_TOKEN = "local-dmg-install-v2"
LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_FILENAME_TOKEN = (
    "local-dmg-uninstall-reinstall-v1"
)
LANE_A_LOCAL_DMG_STATE_RECOVERY_FILENAME_TOKEN = (
    "local-dmg-uninstall-reinstall-state-recovery-v1"
)
LANE_A_LOCAL_DMG_SUITE_LABEL_MAX_LENGTH = 80
LANE_A_LOCAL_DMG_EXERCISE_PROGRAM = """\
import sys
from pathlib import Path
from script import run_macos_local_dmg_install_smoke_v2 as smoke

result = smoke.exercise(
    archive_dir=Path(sys.argv[1]),
    readiness_timeout_seconds=15.0,
    observation_seconds=5.0,
    termination_timeout_seconds=10.0,
)
sys.stdout.buffer.write(smoke.engine.canonical_json_bytes(result))
"""
LANE_A_LOCAL_DMG_LIMITATIONS = (
    "not-finder-ui-or-drag-and-drop-evidence",
    "not-general-ui-or-accessibility-evidence",
    "not-developer-id-notarized-or-stapled-distribution",
    "not-gatekeeper-quarantine-or-download-evidence",
    "not-clean-machine-account-or-system-applications",
    "not-tcc-keychain-provider-network-or-device-evidence",
    "not-arbitrary-history-crash-power-loss-or-concurrent-writer-evidence",
    "not-backup-restore-or-device-transfer-evidence",
    "not-upgrade-n-or-n-minus-one-rollback-production-or-security-evidence",
)
LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "same-created-dmg-image-remount-only",
    "application-support-retained-no-automatic-data-cleanup",
    "post-archive-harness-not-build-input-member",
    "not-finder-system-applications-quarantine-or-gatekeeper-evidence",
    "not-signed-notarized-stapled-or-distribution-evidence",
    (
        "not-clean-machine-upgrade-rollback-device-provider-network-ui-"
        "accessibility-production-or-security-evidence"
    ),
)
LANE_A_LOCAL_DMG_STATE_RECOVERY_LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "same-created-dmg-image-remount-only",
    "fixed-runtime-chat-legacy-canary-only",
    "legacy-fixture-removed-by-harness-before-reinstall-readback",
    "application-support-retained-no-automatic-data-cleanup",
    "post-archive-harness-not-build-input-member",
    "not-finder-system-applications-quarantine-or-gatekeeper-evidence",
    "not-signed-notarized-stapled-or-distribution-evidence",
    (
        "not-clean-machine-upgrade-rollback-device-provider-network-ui-"
        "accessibility-production-or-security-evidence"
    ),
)
LANE_A_LOCAL_DMG_CANARY = {
    "eventID": "packaged-state-recovery-canary-event-v1",
    "eventJsonSha256": (
        "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
    ),
    "eventJsonSize": 344,
    "legacyJsonlSha256": (
        "0e51fc924836465c4c0921eb3b3709b387f89787aabf2e100c7cff338f0aea2e"
    ),
    "legacyJsonlSize": 345,
    "model": "qa:packaged-state-recovery-canary-v1",
    "requestID": "packaged-state-recovery-canary-request-v1",
    "sessionID": "packaged-state-recovery-canary-session-v1",
}
LANE_A_LOCAL_DMG_MIGRATION_OBSERVATION = {
    "mode": "migration-read-v1",
    "sha256": (
        "558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9"
    ),
    "size": 70,
    "status": "passed",
}
LANE_A_LOCAL_DMG_SQLITE_READBACK_OBSERVATION = {
    "mode": "sqlite-readback-v1",
    "sha256": (
        "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07"
    ),
    "size": 71,
    "status": "passed",
}
RESULT_SCHEMA_VERSION = 4
RESULT_PATH_VERSION = 4
COMPARISON_ONLY_MODE = "comparison-only"
PUBLISH_QUALIFIED_MODE = "publish-qualified"
PREPUBLICATION_RESULT_SUFFIX = "-prepublication.json"
PREPUBLICATION_BINDING_POLICY = (
    "canonical-comparison-result-exact-source-builds-and-comparison-v1"
)
PROTECTED_RELEASE_POLICY = "previous-ledger-entry-archive-v1"
COMPARISON_ONLY_PUBLICATION_POLICY = "comparison-only-no-publication"
PUBLISH_QUALIFIED_PUBLICATION_POLICY = (
    "publish-qualified-build-a-after-exact-two-root-match"
)
SOURCE_ROOT_NAMES = ("lane-a", "lane-b-unequal")
SOURCE_ROOT_POLICY = "distinct-unequal-utf8-byte-length-v1"
SWIFT_REPRO_ARGUMENTS = (
    "--jobs",
    "1",
    "--scratch-path",
    str(SWIFT_SCRATCH),
    "-Xswiftc",
    "-num-threads",
    "-Xswiftc",
    "1",
    "-Xswiftc",
    "-file-prefix-map",
    "-Xswiftc",
    "<PHYSICAL_SOURCE_ROOT>=/aetherlink/source",
    "-Xswiftc",
    "-file-compilation-dir",
    "-Xswiftc",
    "/aetherlink/source",
    "-Xswiftc",
    "-prefix-serialized-debugging-options",
    "-Xcc",
    "-working-directory",
    "-Xcc",
    str(SWIFT_SCRATCH),
    "-Xcc",
    "-Xclang",
    "-Xcc",
    "-fdebug-compilation-dir=/aetherlink/source",
    "-Xcc",
    "-Xclang",
    "-Xcc",
    "-fdisable-module-hash",
    "-Xcc",
    "-Xclang",
    "-Xcc",
    "-fbuild-session-timestamp=0",
    "-Xcc",
    "-Xclang",
    "-Xcc",
    "-fno-pch-timestamp",
    "-Xlinker",
    "-reproducible",
)


class ReproducibilityError(RuntimeError):
    def __init__(self, exit_code: int, phase: str, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.phase = phase


@dataclass(frozen=True)
class ReleaseContext:
    release_id: str
    previous_release_relative: Path


@dataclass(frozen=True)
class LaneALocalDMGSuitePaths:
    install: Path
    uninstall_reinstall: Path
    state_recovery: Path

    def ordered(self) -> tuple[Path, Path, Path]:
        return (
            self.install,
            self.uninstall_reinstall,
            self.state_recovery,
        )


@dataclass(frozen=True)
class LaneALocalDMGSuiteEvidence:
    paths: LaneALocalDMGSuitePaths
    archive: ArchiveEvidence
    expected_release_id: str
    install: dict[str, object]
    uninstall_reinstall: dict[str, object]
    state_recovery: dict[str, object]


@dataclass(frozen=True)
class LaneALifecycleProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def resolve_release_context(
    root: Path = ROOT,
    *,
    phase: str = "invocation",
) -> ReleaseContext:
    try:
        entries = load_release_version_ledger(
            root / "release/version-ledger.tsv"
        )
    except LedgerError as error:
        raise ReproducibilityError(
            2,
            phase,
            f"cannot resolve the current and previous releases: {error}",
        ) from error
    if len(entries) < 2:
        raise ReproducibilityError(
            2,
            phase,
            "the release ledger has no previous entry to protect",
        )
    return ReleaseContext(
        release_id=archive_builder.release_id(entries[-1]),
        previous_release_relative=(
            Path("dist/releases")
            / archive_builder.release_id(entries[-2])
        ),
    )


def previous_release_relative(root: Path = ROOT) -> Path:
    return resolve_release_context(
        root,
        phase="protected-archive",
    ).previous_release_relative


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


@dataclass(frozen=True)
class OverlayRecord:
    path: str
    data: bytes
    mode: int


@dataclass(frozen=True)
class SourceOverlay:
    records: tuple[OverlayRecord, ...]
    tracked_deletions: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class GitRefs:
    head: str
    origin_main: str


@dataclass(frozen=True)
class ArchiveEvidence:
    archive_directory: Path
    archive_path: Path
    manifest_path: Path
    checksum_path: Path
    archive_identity: FileIdentity
    manifest_identity: FileIdentity
    checksum_identity: FileIdentity
    zip_entry_count: int
    payload_member_count: int
    normalizations: tuple[str, ...]
    source_sha256: str
    member_inventory: tuple[dict[str, object], ...]

    def result_record(self, build_id: str) -> dict[str, object]:
        return {
            "archive": {
                "checksumSha256": self.checksum_identity.sha256,
                "manifestSha256": self.manifest_identity.sha256,
                "payloadMemberCount": self.payload_member_count,
                "sha256": self.archive_identity.sha256,
                "size": self.archive_identity.size,
                "sourceSha256": self.source_sha256,
                "zipEntryCount": self.zip_entry_count,
                "members": [
                    dict(record) for record in self.member_inventory
                ],
            },
            "commandExitCode": 0,
            "id": build_id,
            "status": "passed",
        }


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )


def validate_source_root_length_evidence(
    evidence: object,
    roots: tuple[Path, ...],
) -> None:
    labels = ("build-a", "build-b")
    if len(roots) != len(labels) or roots[0] == roots[1]:
        raise ReproducibilityError(
            4,
            "source-materialization",
            "two distinct source roots are required",
        )
    if any(not root.is_absolute() for root in roots):
        raise ReproducibilityError(
            4,
            "source-materialization",
            "source roots must be absolute paths",
        )
    encoded_roots = tuple(os.fsencode(str(root)) for root in roots)
    if any(os.fsdecode(encoded) != str(root) for encoded, root in zip(encoded_roots, roots)):
        raise ReproducibilityError(
            4,
            "source-materialization",
            "source root does not round-trip through the filesystem encoding",
        )
    expected_lengths = {
        label: len(encoded)
        for label, encoded in zip(labels, encoded_roots)
    }
    if len(set(expected_lengths.values())) != len(labels):
        raise ReproducibilityError(
            4,
            "source-materialization",
            "two source roots must have different UTF-8 byte lengths",
        )
    if (
        type(evidence) is not dict
        or set(evidence)
        != {
            "policy",
            "sourceRootByteLengths",
            "sourceRootLengthsDiffer",
        }
        or evidence.get("policy") != SOURCE_ROOT_POLICY
        or type(evidence.get("sourceRootLengthsDiffer")) is not bool
        or evidence.get("sourceRootLengthsDiffer") is not True
    ):
        raise ReproducibilityError(
            4,
            "source-materialization",
            "source root length evidence shape is not canonical",
        )
    recorded_lengths = evidence.get("sourceRootByteLengths")
    if (
        type(recorded_lengths) is not dict
        or set(recorded_lengths) != set(labels)
        or any(type(value) is not int for value in recorded_lengths.values())
        or recorded_lengths != expected_lengths
    ):
        raise ReproducibilityError(
            4,
            "source-materialization",
            "source root byte-length evidence differs from the physical paths",
        )


def source_root_length_evidence(
    roots: tuple[Path, ...],
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "policy": SOURCE_ROOT_POLICY,
        "sourceRootByteLengths": {
            label: len(os.fsencode(str(root)))
            for label, root in zip(("build-a", "build-b"), roots)
        },
        "sourceRootLengthsDiffer": True,
    }
    validate_source_root_length_evidence(evidence, roots)
    return evidence


def normalized_mode(file_mode: int) -> int:
    return 0o755 if file_mode & 0o111 else 0o644


def stable_file_identity(path: Path) -> FileIdentity:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ReproducibilityError(
            2,
            "input",
            f"cannot open regular file {path}: {error}",
        ) from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ReproducibilityError(
                2,
                "input",
                f"path is not a regular file: {path}",
            )
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_fields = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_uid,
        before.st_gid,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_fields = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_uid,
        after.st_gid,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_fields != after_fields or total != before.st_size:
        raise ReproducibilityError(
            2,
            "input",
            f"file changed while being read: {path}",
        )
    return FileIdentity(
        device=before.st_dev,
        inode=before.st_ino,
        mode=stat.S_IMODE(before.st_mode),
        uid=before.st_uid,
        gid=before.st_gid,
        size=before.st_size,
        mtime_ns=before.st_mtime_ns,
        ctime_ns=before.st_ctime_ns,
        sha256=digest.hexdigest(),
    )


def stable_file_bytes(path: Path) -> tuple[bytes, int]:
    identity_before = stable_file_identity(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ReproducibilityError(
            4,
            "source-capture",
            f"cannot read source file {path}: {error}",
        ) from error
    identity_after = stable_file_identity(path)
    if identity_before != identity_after or len(data) != identity_before.size:
        raise ReproducibilityError(
            4,
            "source-capture",
            f"source file changed while being captured: {path}",
        )
    return data, normalized_mode(identity_before.mode)


def validate_relative_path(value: str) -> None:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ReproducibilityError(
            4,
            "source-capture",
            f"source path is not UTF-8: {value!r}",
        ) from error
    path = PurePosixPath(value)
    if (
        not encoded
        or value.startswith("/")
        or "//" in value
        or "\\" in value
        or "\0" in value
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise ReproducibilityError(
            4,
            "source-capture",
            f"invalid repository-relative path: {value!r}",
        )


def run_bytes(command: list[str], *, cwd: Path) -> bytes:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        raise ReproducibilityError(
            4,
            "source-capture",
            f"cannot execute {command[0]}: {error}",
        ) from error
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReproducibilityError(
            4,
            "source-capture",
            f"command failed ({result.returncode}): {' '.join(command)}: {stderr}",
        )
    return result.stdout


def nul_paths(data: bytes, label: str) -> tuple[str, ...]:
    if data and not data.endswith(b"\0"):
        raise ReproducibilityError(
            4,
            "source-capture",
            f"{label} output is not NUL-terminated",
        )
    values: list[str] = []
    for raw in data.split(b"\0")[:-1]:
        try:
            value = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ReproducibilityError(
                4,
                "source-capture",
                f"{label} contains a non-UTF-8 path",
            ) from error
        validate_relative_path(value)
        values.append(value)
    if len(values) != len(set(values)):
        raise ReproducibilityError(
            4,
            "source-capture",
            f"{label} contains duplicate paths",
        )
    return tuple(values)


def capture_source_overlay(root: Path = ROOT) -> SourceOverlay:
    conflicts = nul_paths(
        run_bytes(
            ["git", "diff", "--name-only", "--diff-filter=U", "-z"],
            cwd=root,
        ),
        "unmerged-path list",
    )
    if conflicts:
        raise ReproducibilityError(
            4,
            "source-capture",
            f"worktree contains unmerged paths: {list(conflicts)}",
        )
    tracked = nul_paths(
        run_bytes(["git", "ls-files", "-z", "--cached"], cwd=root),
        "tracked-path list",
    )
    untracked = nul_paths(
        run_bytes(
            ["git", "ls-files", "-z", "--others", "--exclude-standard"],
            cwd=root,
        ),
        "untracked-path list",
    )
    if set(tracked) & set(untracked):
        raise ReproducibilityError(
            4,
            "source-capture",
            "tracked and untracked path sets overlap",
        )

    records: list[OverlayRecord] = []
    tracked_deletions: list[str] = []
    digest = hashlib.sha256()
    for relative in sorted(set(tracked) | set(untracked), key=lambda item: item.encode()):
        path = root / relative
        if not os.path.lexists(path):
            if relative in tracked:
                tracked_deletions.append(relative)
                digest.update(relative.encode("utf-8") + b"\0deleted\n")
                continue
            raise ReproducibilityError(
                4,
                "source-capture",
                f"untracked source path disappeared: {relative}",
            )
        status = path.lstat()
        if not stat.S_ISREG(status.st_mode):
            raise ReproducibilityError(
                4,
                "source-capture",
                f"source overlay path is not a regular file: {relative}",
            )
        data, mode = stable_file_bytes(path)
        file_digest = hashlib.sha256(data).hexdigest()
        digest.update(
            relative.encode("utf-8")
            + b"\0"
            + f"{mode:o}".encode("ascii")
            + b"\0"
            + str(len(data)).encode("ascii")
            + b"\0"
            + file_digest.encode("ascii")
            + b"\n"
        )
        records.append(OverlayRecord(relative, data, mode))
    return SourceOverlay(
        records=tuple(records),
        tracked_deletions=tuple(tracked_deletions),
        sha256=digest.hexdigest(),
    )


def capture_git_refs(root: Path = ROOT) -> GitRefs:
    values: list[str] = []
    for revision in ("HEAD", "origin/main"):
        raw = run_bytes(["git", "rev-parse", revision], cwd=root)
        try:
            value = raw.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise ReproducibilityError(
                4,
                "source-capture",
                f"Git revision is not ASCII: {revision}",
            ) from error
        if (
            len(value) != 40
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ReproducibilityError(
                4,
                "source-capture",
                f"Git revision is not a full lowercase commit: {revision}",
            )
        values.append(value)
    return GitRefs(head=values[0], origin_main=values[1])


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    exit_code: int,
    phase: str,
) -> None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            check=False,
        )
    except OSError as error:
        raise ReproducibilityError(
            exit_code,
            phase,
            f"cannot execute {command[0]}: {error}",
        ) from error
    if result.returncode != 0:
        raise ReproducibilityError(
            exit_code,
            phase,
            f"command failed ({result.returncode}): {' '.join(command)}",
        )


def materialize_clone(
    destination: Path,
    overlay: SourceOverlay,
    git_refs: GitRefs,
    *,
    root: Path = ROOT,
) -> None:
    destination.parent.mkdir(parents=True, mode=0o700)
    run_checked(
        [
            "git",
            "clone",
            "--local",
            "--no-hardlinks",
            "--no-checkout",
            str(root),
            str(destination),
        ],
        cwd=destination.parent,
        exit_code=4,
        phase="source-materialization",
    )
    for record in overlay.records:
        target = destination / record.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            raise ReproducibilityError(
                4,
                "source-materialization",
                f"clone unexpectedly materialized overlay path: {record.path}",
            )
        target.write_bytes(record.data)
        target.chmod(record.mode)
    for relative in overlay.tracked_deletions:
        if os.path.lexists(destination / relative):
            raise ReproducibilityError(
                4,
                "source-materialization",
                f"tracked deletion exists in no-checkout clone: {relative}",
            )
    clone_head = run_bytes(["git", "rev-parse", "HEAD"], cwd=destination)
    if clone_head.decode("ascii").strip() != git_refs.head:
        raise ReproducibilityError(
            4,
            "source-materialization",
            "clone HEAD differs from the captured source HEAD",
        )
    run_checked(
        [
            "git",
            "update-ref",
            "refs/remotes/origin/main",
            git_refs.origin_main,
        ],
        cwd=destination,
        exit_code=4,
        phase="source-materialization",
    )
    clone_origin_main = run_bytes(
        ["git", "rev-parse", "origin/main"],
        cwd=destination,
    )
    if clone_origin_main.decode("ascii").strip() != git_refs.origin_main:
        raise ReproducibilityError(
            4,
            "source-materialization",
            "clone origin/main differs from the captured source reference",
        )


def validate_owned_directory(path: Path, *, phase: str) -> None:
    try:
        status = path.lstat()
        physical = path.resolve(strict=True)
    except OSError as error:
        raise ReproducibilityError(
            3,
            phase,
            f"cannot inspect directory {path}: {error}",
        ) from error
    if (
        stat.S_ISLNK(status.st_mode)
        or not stat.S_ISDIR(status.st_mode)
        or status.st_uid != os.getuid()
        or physical != path
        or stat.S_IMODE(status.st_mode) & 0o022
    ):
        raise ReproducibilityError(
            3,
            phase,
            f"directory is not a physical private owner-controlled path: {path}",
        )


def prepare_work_root() -> None:
    try:
        WORK_ROOT.mkdir(mode=0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise ReproducibilityError(
            3,
            "scratch-preflight",
            f"cannot create fixed work root: {error}",
        ) from error
    validate_owned_directory(WORK_ROOT, phase="scratch-preflight")


@contextmanager
def acquire_run_lock() -> Iterator[None]:
    prepare_work_root()
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(LOCK_PATH, flags, 0o600)
    except OSError as error:
        raise ReproducibilityError(
            3,
            "scratch-lock",
            f"cannot open runner lock: {error}",
        ) from error
    try:
        status = os.fstat(descriptor)
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_uid != os.getuid()
            or stat.S_IMODE(status.st_mode) & 0o077
        ):
            raise ReproducibilityError(
                3,
                "scratch-lock",
                "runner lock is not a private owner-controlled regular file",
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ReproducibilityError(
                3,
                "scratch-lock",
                "another reproducibility runner holds the fixed lock",
            ) from error
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return (
        first == second
        or first in second.parents
        or second in first.parents
    )


def validate_result_mode_path(
    result_path: Path,
    *,
    publish_qualified: bool,
    expected_release_id: str | None = None,
) -> str:
    if expected_release_id is None:
        try:
            current = load_release_version_ledger()[-1]
        except LedgerError as error:
            raise ReproducibilityError(
                2,
                "invocation",
                f"cannot resolve the current release ID: {error}",
            ) from error
        release_id = archive_builder.release_id(current)
    else:
        release_id = expected_release_id
    prefix = (
        f"{release_id}"
        f"-two-root-v{RESULT_PATH_VERSION}"
    )
    if publish_qualified:
        canonical_name = f"{prefix}.json"
        label_prefix = f"{prefix}-"
    else:
        canonical_name = f"{prefix}{PREPUBLICATION_RESULT_SUFFIX}"
        label_prefix = f"{prefix}-prepublication-"
    if result_path.name == canonical_name:
        valid = True
    elif not (
        result_path.name.startswith(label_prefix)
        and result_path.name.endswith(".json")
    ):
        valid = False
    else:
        label = result_path.name[len(label_prefix) : -len(".json")]
        valid = re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", label) is not None
        if publish_qualified and label.split("-", 1)[0] == "prepublication":
            valid = False
    if not valid:
        mode = (
            PUBLISH_QUALIFIED_MODE
            if publish_qualified
            else COMPARISON_ONLY_MODE
        )
        raise ReproducibilityError(
            2,
            "invocation",
            f"{mode} result basename violates the current release-qualified "
            "mode namespace",
        )
    return release_id


def preflight_fixed_paths(
    result_path: Path,
    *,
    publish_qualified: bool = True,
    expected_release_id: str | None = None,
    protected_release_relative: Path | None = None,
) -> str:
    if (expected_release_id is None) != (
        protected_release_relative is None
    ):
        raise ReproducibilityError(
            70,
            "internal",
            "release context must provide both current and previous releases",
        )
    release_context = (
        resolve_release_context()
        if expected_release_id is None
        else ReleaseContext(
            release_id=expected_release_id,
            previous_release_relative=protected_release_relative,
        )
    )
    release_id = validate_result_mode_path(
        result_path,
        publish_qualified=publish_qualified,
        expected_release_id=release_context.release_id,
    )
    allowed_result_root = RESULT_ROOT.resolve()
    if (
        result_path.parent != allowed_result_root
        or result_path.suffix != ".json"
        or result_path.name.startswith(".")
    ):
        raise ReproducibilityError(
            2,
            "invocation",
            f"result path must be a visible JSON file directly under "
            f"{allowed_result_root}",
        )
    if os.path.lexists(allowed_result_root):
        validate_owned_directory(
            allowed_result_root,
            phase="invocation",
        )
    else:
        result_parent = allowed_result_root.parent
        if result_parent.is_symlink() or not result_parent.is_dir():
            raise ReproducibilityError(
                2,
                "invocation",
                f"result root parent is not a real directory: {result_parent}",
            )
    if os.path.lexists(result_path):
        status = result_path.lstat()
        if (
            stat.S_ISLNK(status.st_mode)
            or not stat.S_ISREG(status.st_mode)
            or status.st_uid != os.getuid()
        ):
            raise ReproducibilityError(
                2,
                "invocation",
                f"existing result is not an owner-controlled regular file: "
                f"{result_path}",
            )
    for protected in (
        ROOT,
        ROOT / release_context.previous_release_relative,
        result_path.parent,
    ):
        if paths_overlap(SWIFT_SCRATCH, protected):
            raise ReproducibilityError(
                3,
                "scratch-preflight",
                f"fixed Swift scratch overlaps protected path: {protected}",
            )
    if os.path.lexists(SWIFT_SCRATCH):
        raise ReproducibilityError(
            3,
            "scratch-preflight",
            f"fixed Swift scratch already exists: {SWIFT_SCRATCH}",
        )
    if os.path.lexists(SWIFT_LEASE_PATH):
        raise ReproducibilityError(
            3,
            "scratch-preflight",
            f"fixed Swift scratch lease already exists: {SWIFT_LEASE_PATH}",
        )
    return release_id


def validate_lane_a_lifecycle_result_path(
    result_path: Path,
    *,
    expected_release_id: str,
    filename_token: str,
) -> Path:
    allowed_root = LIFECYCLE_RESULT_ROOT.resolve(strict=False)
    try:
        resolved = result_path.resolve(strict=False)
    except OSError as error:
        raise ReproducibilityError(
            2,
            "invocation",
            f"cannot resolve lane-A local DMG result path: {error}",
        ) from error
    prefix = f"macos-{expected_release_id}-two-root-lane-a-{filename_token}-"
    label = (
        result_path.name[len(prefix) : -len(".json")]
        if (
            result_path.name.startswith(prefix)
            and result_path.name.endswith(".json")
        )
        else ""
    )
    if (
        result_path != resolved
        or result_path.parent != allowed_root
        or result_path.suffix != ".json"
        or result_path.name.startswith(".")
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", label) is None
    ):
        raise ReproducibilityError(
            2,
            "invocation",
            "lane-A local DMG result must be a visible current-release "
            "qualified JSON file directly under dist/lifecycle",
        )

    if os.path.lexists(allowed_root):
        try:
            validate_owned_directory(allowed_root, phase="invocation")
        except ReproducibilityError as error:
            raise ReproducibilityError(
                2,
                "invocation",
                str(error),
            ) from error
    else:
        try:
            validate_owned_directory(
                allowed_root.parent,
                phase="invocation",
            )
        except ReproducibilityError as error:
            raise ReproducibilityError(
                2,
                "invocation",
                "lane-A local DMG result root has no owner-controlled "
                f"physical parent: {error}",
            ) from error

    if os.path.lexists(result_path):
        try:
            status = result_path.lstat()
        except OSError as error:
            raise ReproducibilityError(
                2,
                "invocation",
                f"cannot inspect lane-A local DMG result: {error}",
            ) from error
        if (
            stat.S_ISLNK(status.st_mode)
            or not stat.S_ISREG(status.st_mode)
            or status.st_uid != os.getuid()
            or stat.S_IMODE(status.st_mode) & 0o022
        ):
            raise ReproducibilityError(
                2,
                "invocation",
                "existing lane-A local DMG result is not an "
                "owner-controlled regular file",
            )
    return result_path


def validate_lane_a_local_dmg_result_path(
    result_path: Path,
    *,
    expected_release_id: str,
) -> Path:
    return validate_lane_a_lifecycle_result_path(
        result_path,
        expected_release_id=expected_release_id,
        filename_token=LANE_A_LOCAL_DMG_INSTALL_FILENAME_TOKEN,
    )


def validate_lane_a_local_dmg_suite_label(label: object) -> str:
    if (
        type(label) is not str
        or not 1 <= len(label) <= LANE_A_LOCAL_DMG_SUITE_LABEL_MAX_LENGTH
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", label) is None
    ):
        raise ReproducibilityError(
            2,
            "invocation",
            "lane-A local DMG suite label must be a lowercase slug of at "
            f"most {LANE_A_LOCAL_DMG_SUITE_LABEL_MAX_LENGTH} characters",
        )
    return label


def lane_a_local_dmg_suite_paths(
    label: object,
    *,
    expected_release_id: str,
) -> LaneALocalDMGSuitePaths:
    validated_label = validate_lane_a_local_dmg_suite_label(label)

    def result_path(filename_token: str) -> Path:
        return LIFECYCLE_RESULT_ROOT.resolve(strict=False) / (
            f"macos-{expected_release_id}-two-root-lane-a-"
            f"{filename_token}-{validated_label}.json"
        )

    paths = LaneALocalDMGSuitePaths(
        install=result_path(LANE_A_LOCAL_DMG_INSTALL_FILENAME_TOKEN),
        uninstall_reinstall=result_path(
            LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_FILENAME_TOKEN
        ),
        state_recovery=result_path(
            LANE_A_LOCAL_DMG_STATE_RECOVERY_FILENAME_TOKEN
        ),
    )
    specifications = (
        (
            paths.install,
            LANE_A_LOCAL_DMG_INSTALL_FILENAME_TOKEN,
        ),
        (
            paths.uninstall_reinstall,
            LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_FILENAME_TOKEN,
        ),
        (
            paths.state_recovery,
            LANE_A_LOCAL_DMG_STATE_RECOVERY_FILENAME_TOKEN,
        ),
    )
    for path, filename_token in specifications:
        validate_lane_a_lifecycle_result_path(
            path,
            expected_release_id=expected_release_id,
            filename_token=filename_token,
        )
    if len(set(paths.ordered())) != 3:
        raise ReproducibilityError(
            2,
            "invocation",
            "lane-A local DMG suite result paths are not distinct",
        )
    return paths


def create_swift_lease(run_id: str) -> None:
    lease = canonical_json_bytes(
        {
            "pid": os.getpid(),
            "runId": run_id,
            "schemaVersion": 1,
            "scratch": str(SWIFT_SCRATCH),
            "uid": os.getuid(),
        }
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(SWIFT_LEASE_PATH, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(lease)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        raise ReproducibilityError(
            3,
            "scratch-lease",
            f"cannot create fixed Swift scratch lease: {error}",
        ) from error


def read_swift_lease(run_id: str) -> None:
    identity = stable_file_identity(SWIFT_LEASE_PATH)
    if identity.uid != os.getuid() or identity.mode & 0o077:
        raise ReproducibilityError(
            3,
            "scratch-cleanup",
            "fixed Swift scratch lease ownership or mode changed",
        )
    try:
        value = json.loads(SWIFT_LEASE_PATH.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReproducibilityError(
            3,
            "scratch-cleanup",
            f"cannot read fixed Swift scratch lease: {error}",
        ) from error
    expected = {
        "pid": os.getpid(),
        "runId": run_id,
        "schemaVersion": 1,
        "scratch": str(SWIFT_SCRATCH),
        "uid": os.getuid(),
    }
    if value != expected:
        raise ReproducibilityError(
            3,
            "scratch-cleanup",
            "fixed Swift scratch lease differs from the active run",
        )


def cleanup_swift_scratch(run_id: str, *, remove_lease: bool) -> None:
    read_swift_lease(run_id)
    if os.path.lexists(SWIFT_SCRATCH):
        validate_owned_directory(
            SWIFT_SCRATCH,
            phase="scratch-cleanup",
        )
        try:
            shutil.rmtree(SWIFT_SCRATCH)
        except OSError as error:
            raise ReproducibilityError(
                3,
                "scratch-cleanup",
                f"cannot remove owned Swift scratch: {error}",
            ) from error
    if remove_lease:
        try:
            SWIFT_LEASE_PATH.unlink()
        except OSError as error:
            raise ReproducibilityError(
                3,
                "scratch-cleanup",
                f"cannot remove Swift scratch lease: {error}",
            ) from error


def tree_digest(root: Path) -> tuple[int, str]:
    if root.is_symlink() or not root.is_dir():
        raise ReproducibilityError(
            5,
            "gradle-cache",
            f"tree root is not a real directory: {root}",
        )
    digest = hashlib.sha256()
    count = 0
    for candidate in sorted(
        root.rglob("*"),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    ):
        if candidate.is_symlink():
            raise ReproducibilityError(
                5,
                "gradle-cache",
                f"tree contains a symlink: {candidate}",
            )
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ReproducibilityError(
                5,
                "gradle-cache",
                f"tree contains a special file: {candidate}",
            )
        relative = candidate.relative_to(root).as_posix()
        identity = stable_file_identity(candidate)
        digest.update(
            relative.encode("utf-8")
            + b"\0"
            + f"{normalized_mode(identity.mode):o}".encode("ascii")
            + b"\0"
            + str(identity.size).encode("ascii")
            + b"\0"
            + identity.sha256.encode("ascii")
            + b"\n"
        )
        count += 1
    return count, digest.hexdigest()


def clone_tree(source: Path, destination: Path) -> None:
    if os.path.lexists(destination):
        raise ReproducibilityError(
            5,
            "gradle-cache",
            f"cache destination already exists: {destination}",
        )
    run_checked(
        ["/bin/cp", "-cR", str(source), str(destination)],
        cwd=destination.parent,
        exit_code=5,
        phase="gradle-cache",
    )


def prepare_gradle_caches(
    run_root: Path,
    environment: dict[str, str],
) -> tuple[Path, Path, int, str]:
    configured = environment.get("GRADLE_USER_HOME")
    seed_source = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".gradle"
    ).resolve()
    if seed_source.is_symlink() or not seed_source.is_dir():
        raise ReproducibilityError(
            5,
            "gradle-cache",
            f"Gradle cache seed is not a real directory: {seed_source}",
        )
    for protected in (ROOT, SWIFT_SCRATCH, run_root):
        if paths_overlap(seed_source, protected):
            raise ReproducibilityError(
                5,
                "gradle-cache",
                f"Gradle cache seed overlaps protected path: {protected}",
            )
    seed = run_root / "gradle-seed"
    cache_a = run_root / "gradle-a"
    cache_b = run_root / "gradle-b"
    clone_tree(seed_source, seed)
    clone_tree(seed, cache_a)
    clone_tree(seed, cache_b)
    seed_count, seed_digest = tree_digest(seed)
    a_identity = tree_digest(cache_a)
    b_identity = tree_digest(cache_b)
    if a_identity != (seed_count, seed_digest) or b_identity != a_identity:
        raise ReproducibilityError(
            5,
            "gradle-cache",
            "paired Gradle cache clones differ from the stable seed snapshot",
        )
    return cache_a, cache_b, seed_count, seed_digest


def resolve_android_sdk(environment: dict[str, str]) -> Path:
    candidates = [
        environment.get("ANDROID_SDK_ROOT"),
        environment.get("ANDROID_HOME"),
    ]
    local_properties = ROOT / "local.properties"
    if local_properties.is_file() and not local_properties.is_symlink():
        for line in local_properties.read_text(encoding="utf-8").splitlines():
            if line.startswith("sdk.dir="):
                candidates.append(line.removeprefix("sdk.dir="))
                break
    for candidate in candidates:
        if not candidate:
            continue
        sdk = Path(candidate).expanduser().resolve()
        if sdk.is_dir() and not sdk.is_symlink():
            return sdk
    raise ReproducibilityError(
        2,
        "input",
        "Android SDK path is unavailable from the environment or local.properties",
    )


def capture_protected_archive(
    relative_path: Path,
    root: Path = ROOT,
) -> tuple[str, dict[str, FileIdentity]]:
    if (
        relative_path.is_absolute()
        or ".." in relative_path.parts
        or relative_path.parent != Path("dist/releases")
    ):
        raise ReproducibilityError(
            2,
            "protected-archive",
            f"protected release path is invalid: {relative_path}",
        )
    directory = root / relative_path
    if directory.is_symlink() or not directory.is_dir():
        raise ReproducibilityError(
            2,
            "protected-archive",
            f"previous release archive directory is unavailable: {directory}",
        )
    archive_id = directory.name
    expected = {
        f"{archive_id}.zip",
        f"{archive_id}.manifest.json",
        f"{archive_id}.zip.sha256",
    }
    actual = {path.name for path in directory.iterdir()}
    if actual != expected:
        raise ReproducibilityError(
            2,
            "protected-archive",
            f"previous release archive sidecar set differs: {sorted(actual)}",
        )
    identities = {
        name: stable_file_identity(directory / name)
        for name in sorted(expected)
    }
    digest = hashlib.sha256()
    directory_status = directory.lstat()
    digest.update(
        (
            f"directory\0{directory_status.st_dev}\0"
            f"{directory_status.st_ino}\0{stat.S_IMODE(directory_status.st_mode):o}"
            f"\0{directory_status.st_uid}\0{directory_status.st_gid}\n"
        ).encode("ascii")
    )
    for name, identity in identities.items():
        digest.update(
            (
                f"{name}\0{identity.device}\0{identity.inode}\0"
                f"{identity.mode:o}\0{identity.uid}\0{identity.gid}\0"
                f"{identity.size}\0{identity.mtime_ns}\0{identity.ctime_ns}\0"
                f"{identity.sha256}\n"
            ).encode("ascii")
        )
    return digest.hexdigest(), identities


def capture_archive(clone_root: Path, release_id: str) -> ArchiveEvidence:
    directory = clone_root / "dist/releases" / release_id
    archive_path = directory / f"{release_id}.zip"
    manifest_path = directory / f"{release_id}.manifest.json"
    checksum_path = directory / f"{release_id}.zip.sha256"
    archive_identity = stable_file_identity(archive_path)
    manifest_identity = stable_file_identity(manifest_path)
    checksum_identity = stable_file_identity(checksum_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if not names or names[0] != "manifest.json":
                raise ValueError("manifest.json is not the first ZIP entry")
            if archive.read("manifest.json") != manifest_path.read_bytes():
                raise ValueError("embedded and external manifests differ")
            member_inventory = tuple(
                {
                    "compressedSize": info.compress_size,
                    "compression": info.compress_type,
                    "crc32": f"{info.CRC:08x}",
                    "externalAttributes": info.external_attr,
                    "path": info.filename,
                    "sha256": hashlib.sha256(
                        archive.read(info.filename)
                    ).hexdigest(),
                    "size": info.file_size,
                    "timestamp": list(info.date_time),
                }
                for info in infos
            )
    except (OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile, ValueError) as error:
        raise ReproducibilityError(
            8,
            "archive-comparison",
            f"cannot inspect release archive {directory}: {error}",
        ) from error
    try:
        normalizations = tuple(manifest["archive"]["normalizations"])
        payload_member_count = manifest["archive"][
            "memberCountExcludingManifest"
        ]
        source_sha256 = str(manifest["source"]["snapshotSha256"])
    except (KeyError, TypeError, ValueError) as error:
        raise ReproducibilityError(
            8,
            "archive-comparison",
            f"release manifest comparison fields are invalid: {error}",
        ) from error
    if type(payload_member_count) is not int:
        raise ReproducibilityError(
            8,
            "archive-comparison",
            "release manifest member count is not an exact integer",
        )
    if payload_member_count != len(names) - 1:
        raise ReproducibilityError(
            8,
            "archive-comparison",
            "release manifest member count differs from ZIP entries",
        )
    return ArchiveEvidence(
        archive_directory=directory,
        archive_path=archive_path,
        manifest_path=manifest_path,
        checksum_path=checksum_path,
        archive_identity=archive_identity,
        manifest_identity=manifest_identity,
        checksum_identity=checksum_identity,
        zip_entry_count=len(names),
        payload_member_count=payload_member_count,
        normalizations=normalizations,
        source_sha256=source_sha256,
        member_inventory=member_inventory,
    )


def files_equal(first: Path, second: Path) -> bool:
    with first.open("rb") as left, second.open("rb") as right:
        while True:
            left_chunk = left.read(1024 * 1024)
            right_chunk = right.read(1024 * 1024)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def member_difference_diagnostic(
    first: ArchiveEvidence,
    second: ArchiveEvidence,
    path: str,
) -> dict[str, object]:
    with (
        zipfile.ZipFile(first.archive_path) as left_archive,
        zipfile.ZipFile(second.archive_path) as right_archive,
    ):
        left = left_archive.read(path)
        right = right_archive.read(path)
    shared_length = min(len(left), len(right))
    first_offset = next(
        (
            index
            for index in range(shared_length)
            if left[index] != right[index]
        ),
        shared_length if len(left) != len(right) else None,
    )
    diagnostic: dict[str, object] = {
        "firstDifferenceOffset": first_offset,
        "sizeA": len(left),
        "sizeB": len(right),
    }
    if path.endswith((".yml", ".yaml")):
        left_lines = left.splitlines()
        right_lines = right.splitlines()
        shared_lines = min(len(left_lines), len(right_lines))
        line_index = next(
            (
                index
                for index in range(shared_lines)
                if left_lines[index] != right_lines[index]
            ),
            shared_lines if len(left_lines) != len(right_lines) else None,
        )
        diagnostic["firstDifferingLineNumber"] = (
            None if line_index is None else line_index + 1
        )
        if line_index is not None:
            for label, lines in (("lineA", left_lines), ("lineB", right_lines)):
                value = b"" if line_index >= len(lines) else lines[line_index]
                diagnostic[label] = value[:512].decode(
                    "ascii",
                    errors="backslashreplace",
                )
    return diagnostic


def compare_archives(
    first: ArchiveEvidence,
    second: ArchiveEvidence,
) -> dict[str, object]:
    differences: list[str] = []
    for label, first_path, second_path in (
        ("zip", first.archive_path, second.archive_path),
        ("manifest", first.manifest_path, second.manifest_path),
        ("checksum", first.checksum_path, second.checksum_path),
    ):
        if not files_equal(first_path, second_path):
            differences.append(label)
    left_members = {
        str(record["path"]): record for record in first.member_inventory
    }
    right_members = {
        str(record["path"]): record for record in second.member_inventory
    }
    member_set_equal = list(left_members) == list(right_members)
    member_differences: list[dict[str, object]] = []
    metadata_fields = (
        "compressedSize",
        "compression",
        "crc32",
        "externalAttributes",
        "size",
        "timestamp",
    )
    for path in sorted(
        set(left_members) | set(right_members),
        key=lambda value: value.encode("ascii"),
    ):
        left = left_members.get(path)
        right = right_members.get(path)
        if left is None or right is None:
            member_differences.append(
                {
                    "bytesEqual": False,
                    "metadataEqual": False,
                    "path": path,
                    "presentInBuildA": left is not None,
                    "presentInBuildB": right is not None,
                }
            )
            continue
        bytes_equal = left["sha256"] == right["sha256"]
        record: dict[str, object] = {
            "bytesEqual": bytes_equal,
            "metadataEqual": all(
                left[field] == right[field]
                for field in metadata_fields
            ),
            "path": path,
            "presentInBuildA": True,
            "presentInBuildB": True,
        }
        if not bytes_equal:
            record["diagnostic"] = member_difference_diagnostic(
                first,
                second,
                path,
            )
        member_differences.append(record)
    member_differences = [
        record
        for record in member_differences
        if not record["bytesEqual"] or not record["metadataEqual"]
    ]
    member_metadata_equal = (
        member_set_equal
        and not any(
            not record["metadataEqual"]
            for record in member_differences
        )
    )
    member_bytes_equal = (
        member_set_equal
        and not any(
            not record["bytesEqual"]
            for record in member_differences
        )
    )
    if not member_set_equal:
        differences.append("member-set")
    if not member_metadata_equal:
        differences.append("member-metadata")
    if not member_bytes_equal:
        differences.append("member-bytes")
    archive_bytes_equal = "zip" not in differences
    return {
        "archiveBytesEqual": archive_bytes_equal,
        "differences": sorted(set(differences)),
        "memberBytesEqual": member_bytes_equal,
        "memberDifferences": member_differences,
        "memberMetadataEqual": member_metadata_equal,
        "memberSetEqual": member_set_equal,
        "normalizations": list(first.normalizations),
    }


def canonical_prepublication_result_path(release_id: str) -> Path:
    return RESULT_ROOT / (
        f"{release_id}-two-root-v{RESULT_PATH_VERSION}"
        f"{PREPUBLICATION_RESULT_SUFFIX}"
    )


def load_matching_prepublication_result(
    release_id: str,
    *,
    expected_source: object,
    expected_builds: object,
    expected_comparison: object,
    protected_release_relative: Path,
    protected_archive_identity_sha256: str,
) -> tuple[dict[str, object], Path, FileIdentity]:
    path = canonical_prepublication_result_path(release_id)
    try:
        identity_before = stable_file_identity(path)
        raw = path.read_bytes()
        identity_after = stable_file_identity(path)
    except (OSError, ReproducibilityError) as error:
        raise ReproducibilityError(
            8,
            "prepublication-binding",
            f"cannot read canonical comparison-only result: {error}",
        ) from error
    if (
        identity_before != identity_after
        or identity_before.uid != os.getuid()
        or len(raw) != identity_before.size
    ):
        raise ReproducibilityError(
            8,
            "prepublication-binding",
            "canonical comparison-only result changed while being read",
        )
    try:
        parsed = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReproducibilityError(
            8,
            "prepublication-binding",
            f"canonical comparison-only result is not ASCII JSON: {error}",
        ) from error
    if type(parsed) is not dict or canonical_json_bytes(parsed) != raw:
        raise ReproducibilityError(
            8,
            "prepublication-binding",
            "canonical comparison-only result is not canonical JSON",
        )
    expected_publication = empty_result(
        publish_qualified=False
    )["publication"]
    protected = parsed.get("protectedArchive")
    if (
        set(parsed) != set(empty_result(publish_qualified=False))
        or parsed.get("schemaVersion") != RESULT_SCHEMA_VERSION
        or parsed.get("executionMode") != COMPARISON_ONLY_MODE
        or parsed.get("releaseId") != release_id
        or parsed.get("status") != "passed"
        or parsed.get("failure") is not None
        or parsed.get("prepublicationBinding") is not None
        or parsed.get("publication") != expected_publication
        or parsed.get("source") != expected_source
        or parsed.get("builds") != expected_builds
        or parsed.get("comparison") != expected_comparison
        or type(protected) is not dict
        or protected.get("policy") != PROTECTED_RELEASE_POLICY
        or protected.get("relativePath")
        != protected_release_relative.as_posix()
        or protected.get("unchanged") is not True
        or protected.get("beforeIdentitySha256")
        != protected_archive_identity_sha256
        or protected.get("afterIdentitySha256")
        != protected_archive_identity_sha256
    ):
        raise ReproducibilityError(
            8,
            "prepublication-binding",
            "canonical comparison-only result does not exactly match the "
            "current source, builds, comparison, and previous archive",
        )
    return (
        {
            "matched": True,
            "path": path.relative_to(ROOT).as_posix(),
            "policy": PREPUBLICATION_BINDING_POLICY,
            "sha256": identity_before.sha256,
            "size": identity_before.size,
        },
        path,
        identity_before,
    )


def publish_qualified_archive(
    qualified: ArchiveEvidence,
    source_snapshot: dict[str, object],
    git_refs: GitRefs,
    protected_release_relative: Path,
    protected_archive: tuple[str, dict[str, FileIdentity]],
    *,
    publication: dict[str, object],
) -> dict[str, object]:
    publication.update(
        {
            "attempted": True,
            "independentReadback": False,
            "outcome": "checking-qualified-candidate",
            "qualifiedArchivePublished": False,
        }
    )
    already_matched: bool | None = None
    publication_call_active = False
    try:
        release_id = qualified.archive_directory.name
        current = load_release_version_ledger()[-1]
        if release_id != archive_builder.release_id(current):
            raise ReproducibilityError(
                8,
                "publication",
                "qualified archive release ID differs from the current ledger",
            )
        if capture_git_refs() != git_refs:
            raise ReproducibilityError(
                8,
                "publication",
                "Git references changed during the reproducibility run",
            )
        if archive_builder.source_snapshot(ROOT) != source_snapshot:
            raise ReproducibilityError(
                8,
                "publication",
                "build source inputs changed during the reproducibility run",
            )
        if (
            capture_protected_archive(protected_release_relative)
            != protected_archive
        ):
            raise ReproducibilityError(
                9,
                "protected-archive",
                "previous release archive changed before publication",
            )
        qualified_identities = {
            qualified.archive_path.name: (
                qualified.archive_identity.size,
                qualified.archive_identity.sha256,
            ),
            qualified.manifest_path.name: (
                qualified.manifest_identity.size,
                qualified.manifest_identity.sha256,
            ),
            qualified.checksum_path.name: (
                qualified.checksum_identity.size,
                qualified.checksum_identity.sha256,
            ),
        }
        for path, expected in (
            (qualified.archive_path, qualified.archive_identity),
            (qualified.manifest_path, qualified.manifest_identity),
            (qualified.checksum_path, qualified.checksum_identity),
        ):
            if stable_file_identity(path) != expected:
                raise ReproducibilityError(
                    8,
                    "publication",
                    f"qualified sidecar changed before publication: "
                    f"{path.name}",
                )
        try:
            archive_reader.verify_release_archive(
                qualified.archive_directory
            )
        except (
            OSError,
            archive_reader.ReleaseArchiveVerificationError,
        ) as error:
            raise ReproducibilityError(
                8,
                "publication",
                f"qualified archive publication/readback failed: {error}",
            ) from error

        publication_call_active = True
        publication.update(
            {
                "outcome": "archive-publication-call-in-progress",
                "qualifiedArchivePublished": None,
            }
        )
        try:
            published_directory, already_matched = (
                archive_builder.publish_archive_directory(
                    archive_builder.DEFAULT_OUTPUT_ROOT,
                    release_id,
                    qualified.archive_path,
                    qualified.manifest_path.read_bytes(),
                    expected_sidecars=qualified_identities,
                )
            )
        except (
            OSError,
            archive_builder.ReleaseArchiveError,
        ) as error:
            raise ReproducibilityError(
                8,
                "publication",
                f"qualified archive publication/readback failed: {error}",
            ) from error
        publication_call_active = False
        if type(already_matched) is not bool:
            publication.update(
                {
                    "outcome": "archive-publication-call-outcome-uncertain",
                    "qualifiedArchivePublished": None,
                }
            )
            raise ReproducibilityError(
                70,
                "internal",
                "archive publisher returned no exact already-matched boolean",
            )
        publication.update(
            {
                "outcome": (
                    "matched-existing-postcheck-incomplete"
                    if already_matched
                    else "published-postcheck-incomplete"
                ),
                "qualifiedArchivePublished": not already_matched,
            }
        )
        try:
            archive_reader.verify_release_archive(published_directory)
        except (
            OSError,
            archive_reader.ReleaseArchiveVerificationError,
        ) as error:
            raise ReproducibilityError(
                8,
                "publication",
                f"qualified archive publication/readback failed: {error}",
            ) from error
        if archive_builder.source_snapshot(ROOT) != source_snapshot:
            raise ReproducibilityError(
                8,
                "publication",
                "build source inputs changed during publication readback",
            )
        published = capture_archive(ROOT, release_id)
        comparison = compare_archives(qualified, published)
        if comparison["differences"]:
            raise ReproducibilityError(
                8,
                "publication",
                "published archive differs from qualified build A: "
                f"{comparison['differences']}",
            )
        publication.update(
            {
                "independentReadback": True,
                "outcome": (
                    "matched-existing-verified"
                    if already_matched
                    else "published-verified"
                ),
            }
        )
        return {
            "alreadyMatched": already_matched,
            "archiveDirectory": (
                published_directory.relative_to(ROOT).as_posix()
            ),
            "archiveSha256": published.archive_identity.sha256,
            "checksumSha256": published.checksum_identity.sha256,
            "manifestSha256": published.manifest_identity.sha256,
            "publishedBytesEqualLaneA": True,
            "sourceLane": "build-a",
            "sourceSnapshotUnchanged": True,
        }
    except BaseException:
        if publication_call_active:
            publication.update(
                {
                    "outcome": "archive-publication-call-outcome-uncertain",
                    "qualifiedArchivePublished": None,
                }
            )
        elif publication.get("qualifiedArchivePublished") is True:
            publication["outcome"] = "published-postcheck-failed"
        elif already_matched is True:
            publication["outcome"] = "matched-existing-postcheck-failed"
        elif publication.get("qualifiedArchivePublished") is None:
            publication["outcome"] = (
                "archive-publication-call-outcome-uncertain"
            )
        else:
            publication.update(
                {
                    "outcome": "failed-before-archive-mutation",
                    "qualifiedArchivePublished": False,
                }
            )
        publication["independentReadback"] = False
        raise


def source_release_id(
    source_root: Path,
    *,
    exit_code: int,
    phase: str,
) -> str:
    try:
        current = load_release_version_ledger(
            source_root / "release/version-ledger.tsv"
        )[-1]
    except LedgerError as error:
        raise ReproducibilityError(
            exit_code,
            phase,
            f"cannot resolve materialized release ID: {error}",
        ) from error
    return archive_builder.release_id(current)


def run_lane(
    clone_root: Path,
    gradle_home: Path,
    android_sdk: Path,
    *,
    lane_id: str,
) -> ArchiveEvidence:
    environment = os.environ.copy()
    environment.update(
        {
            "ANDROID_HOME": str(android_sdk),
            "ANDROID_SDK_ROOT": str(android_sdk),
            "AETHERLINK_REPRO_SWIFT_SCRATCH_PATH": str(SWIFT_SCRATCH),
            "GRADLE_USER_HOME": str(gradle_home),
            "LC_ALL": "C",
        }
    )
    exit_code = 6 if lane_id == "build-a" else 7
    run_checked(
        ["./script/build_release_artifacts.sh"],
        cwd=clone_root,
        environment=environment,
        exit_code=exit_code,
        phase=lane_id,
    )
    run_checked(
        ["python3", "script/check_release_artifact_archive.py"],
        cwd=clone_root,
        environment=environment,
        exit_code=exit_code,
        phase=f"{lane_id}-readback",
    )
    release_id = source_release_id(
        clone_root,
        exit_code=exit_code,
        phase=f"{lane_id}-readback",
    )
    return capture_archive(clone_root, release_id)


def lane_a_local_dmg_error(message: str) -> ReproducibilityError:
    return ReproducibilityError(
        10,
        LANE_A_LOCAL_DMG_PHASE,
        message,
    )


def require_closed_object(
    value: object,
    keys: set[str],
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise lane_a_local_dmg_error(
            f"{label} does not have the exact closed schema"
        )
    return value


def require_sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise lane_a_local_dmg_error(f"{label} is not a lowercase SHA-256")
    return value


def reject_duplicate_json_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON value: {value}")


def parse_lane_a_lifecycle_result_bytes(
    raw: bytes,
    *,
    label: str,
) -> dict[str, object]:
    if not raw or len(raw) > 1024 * 1024:
        raise lane_a_local_dmg_error(
            f"{label} size is outside the bounded contract"
        )
    try:
        decoded = raw.decode("ascii")
        parsed = json.loads(
            decoded,
            object_pairs_hook=reject_duplicate_json_pairs,
            parse_constant=reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise lane_a_local_dmg_error(
            f"{label} is not strict ASCII JSON: {error}"
        ) from error
    if type(parsed) is not dict or canonical_json_bytes(parsed) != raw:
        raise lane_a_local_dmg_error(f"{label} is not canonical JSON")
    return parsed


def validate_lane_a_archive_binding(
    result: dict[str, object],
    *,
    expected_release_id: str,
    evidence: ArchiveEvidence,
    label: str,
) -> None:
    release = require_closed_object(
        result["release"],
        {"archiveSha256", "manifestSha256", "releaseId"},
        label=f"{label} release",
    )
    if (
        release["releaseId"] != expected_release_id
        or release["archiveSha256"] != evidence.archive_identity.sha256
        or release["manifestSha256"] != evidence.manifest_identity.sha256
    ):
        raise lane_a_local_dmg_error(
            f"{label} release identity differs from build A"
        )

    archive_readback = require_closed_object(
        result["archiveReadback"],
        {
            "currentSourceCompared",
            "mode",
            "readbackAndExerciseSameSnapshot",
            "snapshotFiles",
            "snapshotFilesUnchangedAfterExercise",
            "status",
        },
        label=f"{label} archive readback",
    )
    if (
        archive_readback["currentSourceCompared"] is not False
        or archive_readback["mode"] != LANE_A_LOCAL_DMG_READBACK_MODE
        or archive_readback["readbackAndExerciseSameSnapshot"] is not True
        or archive_readback["snapshotFilesUnchangedAfterExercise"] is not True
        or archive_readback["status"] != "passed"
    ):
        raise lane_a_local_dmg_error(
            f"{label} archive readback contract is invalid"
        )
    expected_snapshot_files = {
        f"{expected_release_id}.manifest.json": evidence.manifest_identity,
        f"{expected_release_id}.zip": evidence.archive_identity,
        f"{expected_release_id}.zip.sha256": evidence.checksum_identity,
    }
    snapshot_files = require_closed_object(
        archive_readback["snapshotFiles"],
        set(expected_snapshot_files),
        label=f"{label} snapshot files",
    )
    for name, expected_identity in expected_snapshot_files.items():
        record = require_closed_object(
            snapshot_files[name],
            {"sha256", "size"},
            label=f"{label} snapshot file {name}",
        )
        if (
            record["sha256"] != expected_identity.sha256
            or type(record["size"]) is not int
            or record["size"] != expected_identity.size
        ):
            raise lane_a_local_dmg_error(
                f"{label} snapshot file differs from build A: {name}"
            )


def validate_lane_a_local_dmg_result_bytes(
    raw: bytes,
    *,
    expected_release_id: str,
    evidence: ArchiveEvidence,
) -> dict[str, object]:
    parsed = parse_lane_a_lifecycle_result_bytes(
        raw,
        label="lane-A local DMG result",
    )
    result = require_closed_object(
        parsed,
        {
            "archiveReadback",
            "image",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "mount",
            "release",
            "schemaVersion",
            "scope",
            "state",
            "status",
        },
        label="lane-A local DMG result",
    )
    if (
        type(result["schemaVersion"]) is not int
        or result["schemaVersion"] != 2
        or result["scope"] != LANE_A_LOCAL_DMG_SCOPE
        or result["status"] != "passed"
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG result identity or status is invalid"
        )

    release = require_closed_object(
        result["release"],
        {"archiveSha256", "manifestSha256", "releaseId"},
        label="lane-A local DMG release",
    )
    if (
        release["releaseId"] != expected_release_id
        or release["archiveSha256"] != evidence.archive_identity.sha256
        or release["manifestSha256"] != evidence.manifest_identity.sha256
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG release identity differs from build A"
        )

    archive_readback = require_closed_object(
        result["archiveReadback"],
        {
            "currentSourceCompared",
            "mode",
            "readbackAndExerciseSameSnapshot",
            "snapshotFiles",
            "snapshotFilesUnchangedAfterExercise",
            "status",
        },
        label="lane-A local DMG archive readback",
    )
    if (
        archive_readback["currentSourceCompared"] is not False
        or archive_readback["mode"] != LANE_A_LOCAL_DMG_READBACK_MODE
        or archive_readback["readbackAndExerciseSameSnapshot"] is not True
        or archive_readback["snapshotFilesUnchangedAfterExercise"] is not True
        or archive_readback["status"] != "passed"
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG archive readback contract is invalid"
        )
    expected_snapshot_files = {
        f"{expected_release_id}.manifest.json": (
            evidence.manifest_identity
        ),
        f"{expected_release_id}.zip": evidence.archive_identity,
        f"{expected_release_id}.zip.sha256": (
            evidence.checksum_identity
        ),
    }
    snapshot_files = require_closed_object(
        archive_readback["snapshotFiles"],
        set(expected_snapshot_files),
        label="lane-A local DMG snapshot files",
    )
    for name, expected_identity in expected_snapshot_files.items():
        record = require_closed_object(
            snapshot_files[name],
            {"sha256", "size"},
            label=f"lane-A local DMG snapshot file {name}",
        )
        if (
            record["sha256"] != expected_identity.sha256
            or type(record["size"]) is not int
            or record["size"] != expected_identity.size
        ):
            raise lane_a_local_dmg_error(
                f"lane-A local DMG snapshot file differs from build A: {name}"
            )

    image = require_closed_object(
        result["image"],
        {"ephemeral", "filesystem", "format", "retained", "verified"},
        label="lane-A local DMG image",
    )
    if (
        image["ephemeral"] is not True
        or image["filesystem"] != "HFS+"
        or image["format"] != "UDZO"
        or image["retained"] is not False
        or image["verified"] is not True
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG image contract is invalid"
        )

    installation = require_closed_object(
        result["installation"],
        {
            "adHocAppSealAndVersionVerified",
            "applicationsAliasPresent",
            "copyTool",
            "exactReleaseTreeCopied",
            "tree",
        },
        label="lane-A local DMG installation",
    )
    if (
        installation["adHocAppSealAndVersionVerified"] is not True
        or installation["applicationsAliasPresent"] is not True
        or installation["copyTool"] != "ditto"
        or installation["exactReleaseTreeCopied"] is not True
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG installation contract is invalid"
        )
    tree = require_closed_object(
        installation["tree"],
        {
            "digestAlgorithm",
            "regularFileCount",
            "sha256",
            "totalRegularFileBytes",
        },
        label="lane-A local DMG installed tree",
    )
    if (
        tree["digestAlgorithm"]
        != "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
        or type(tree["regularFileCount"]) is not int
        or tree["regularFileCount"] <= 0
        or type(tree["totalRegularFileBytes"]) is not int
        or tree["totalRegularFileBytes"] <= 0
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG installed tree contract is invalid"
        )
    require_sha256(tree["sha256"], label="lane-A local DMG installed tree")

    isolation = require_closed_object(
        result["isolation"],
        {
            "cleanHomeConfigured",
            "preexistingBundleApplicationsPreserved",
            "runtimeIdentityFileOverrideConfigured",
            "temporaryCFUserHomeConfigured",
        },
        label="lane-A local DMG isolation",
    )
    if any(value is not True for value in isolation.values()):
        raise lane_a_local_dmg_error(
            "lane-A local DMG isolation contract is invalid"
        )

    launch_services = require_closed_object(
        result["launchServices"],
        {
            "distinctProcessIdentifiers",
            "exactInstalledBundlePerCycle",
            "runs",
        },
        label="lane-A local DMG LaunchServices",
    )
    runs = launch_services["runs"]
    if (
        launch_services["distinctProcessIdentifiers"] is not True
        or launch_services["exactInstalledBundlePerCycle"] is not True
        or type(runs) is not list
        or len(runs) != 2
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG LaunchServices contract is invalid"
        )
    for ordinal, value in enumerate(runs, start=1):
        run = require_closed_object(
            value,
            {
                "activationPolicy",
                "finishedLaunching",
                "newProcessIdentifierDetected",
                "observationDeadlineReached",
                "ordinal",
                "terminationAccepted",
            },
            label=f"lane-A local DMG launch run {ordinal}",
        )
        if (
            type(run["activationPolicy"]) is not int
            or run["activationPolicy"] != 0
            or type(run["ordinal"]) is not int
            or run["ordinal"] != ordinal
            or any(
                run[key] is not True
                for key in (
                    "finishedLaunching",
                    "newProcessIdentifierDetected",
                    "observationDeadlineReached",
                    "terminationAccepted",
                )
            )
        ):
            raise lane_a_local_dmg_error(
                f"lane-A local DMG launch run {ordinal} is invalid"
            )

    if result["limitations"] != list(LANE_A_LOCAL_DMG_LIMITATIONS):
        raise lane_a_local_dmg_error(
            "lane-A local DMG limitations are not exact"
        )

    mount = require_closed_object(
        result["mount"],
        {
            "detachedBeforeLaunch",
            "exactFreshMountpoint",
            "nobrowse",
            "oneMountedEntity",
            "readOnly",
            "unmountedVerified",
        },
        label="lane-A local DMG mount",
    )
    if any(value is not True for value in mount.values()):
        raise lane_a_local_dmg_error(
            "lane-A local DMG mount contract is invalid"
        )

    state = require_closed_object(
        result["state"],
        {
            "databaseCount",
            "emptyRuntimeChatVerified",
            "integrityChecks",
            "regularFileBytesAndModesUnchangedAcrossRelaunch",
            "runtimeIdentityFilePresent",
            "sqlite",
            "stableAcrossRelaunch",
        },
        label="lane-A local DMG state",
    )
    if (
        type(state["databaseCount"]) is not int
        or state["databaseCount"] != 3
        or state["emptyRuntimeChatVerified"] is not True
        or state["integrityChecks"] != "passed"
        or state["regularFileBytesAndModesUnchangedAcrossRelaunch"] is not True
        or state["runtimeIdentityFilePresent"] is not True
        or state["stableAcrossRelaunch"] is not True
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG persisted-state contract is invalid"
        )
    sqlite = state["sqlite"]
    expected_sqlite = (
        ("runtime-chat-events.sqlite", True),
        ("runtime-document-index.sqlite", False),
        ("runtime-model-pull-approvals.sqlite", False),
    )
    if type(sqlite) is not list or len(sqlite) != len(expected_sqlite):
        raise lane_a_local_dmg_error(
            "lane-A local DMG SQLite inventory is invalid"
        )
    for record, (filename, has_count) in zip(sqlite, expected_sqlite):
        expected_keys = {"filename", "integrityCheck"}
        if has_count:
            expected_keys.add("totalEventCount")
        item = require_closed_object(
            record,
            expected_keys,
            label=f"lane-A local DMG SQLite record {filename}",
        )
        if (
            item["filename"] != filename
            or item["integrityCheck"] != "ok"
            or (
                has_count
                and (
                    type(item["totalEventCount"]) is not int
                    or item["totalEventCount"] != 0
                )
            )
        ):
            raise lane_a_local_dmg_error(
                f"lane-A local DMG SQLite record is invalid: {filename}"
            )
    return result


def validate_lane_a_installed_tree(
    value: object,
    *,
    expected_tree: dict[str, object],
    label: str,
) -> dict[str, object]:
    tree = require_closed_object(
        value,
        {
            "digestAlgorithm",
            "regularFileCount",
            "sha256",
            "totalRegularFileBytes",
        },
        label=label,
    )
    if (
        tree["digestAlgorithm"]
        != "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
        or type(tree["regularFileCount"]) is not int
        or tree["regularFileCount"] <= 0
        or type(tree["totalRegularFileBytes"]) is not int
        or tree["totalRegularFileBytes"] <= 0
    ):
        raise lane_a_local_dmg_error(f"{label} contract is invalid")
    require_sha256(tree["sha256"], label=label)
    if tree != expected_tree:
        raise lane_a_local_dmg_error(
            f"{label} differs from the validated install result"
        )
    return tree


def validate_lane_a_two_install_contract(
    result: dict[str, object],
    *,
    expected_tree: dict[str, object],
    label: str,
    state_present_before_reinstall: bool,
) -> None:
    image = require_closed_object(
        result["image"],
        {
            "ephemeral",
            "filesystem",
            "format",
            "retained",
            "sameImageBytesUsedForBothInstalls",
            "verified",
        },
        label=f"{label} image",
    )
    if (
        image["ephemeral"] is not True
        or image["filesystem"] != "HFS+"
        or image["format"] != "UDZO"
        or image["retained"] is not False
        or image["sameImageBytesUsedForBothInstalls"] is not True
        or image["verified"] is not True
    ):
        raise lane_a_local_dmg_error(f"{label} image contract is invalid")

    installation_keys = {
        "adHocAppSealAndVersionVerified",
        "applicationsAliasPresent",
        "copyTool",
        "exactReleaseTreeCopiedEachInstall",
        "installCount",
        "origin",
        "reinstallTreeMatchesInitial",
        "tree",
    }
    if state_present_before_reinstall:
        installation_keys.add("statePresentBeforeReinstall")
    installation = require_closed_object(
        result["installation"],
        installation_keys,
        label=f"{label} installation",
    )
    if (
        installation["adHocAppSealAndVersionVerified"] is not True
        or installation["applicationsAliasPresent"] is not True
        or installation["copyTool"] != "ditto"
        or installation["exactReleaseTreeCopiedEachInstall"] is not True
        or type(installation["installCount"]) is not int
        or installation["installCount"] != 2
        or installation["origin"] != "same-ephemeral-local-dmg"
        or installation["reinstallTreeMatchesInitial"] is not True
        or (
            state_present_before_reinstall
            and installation["statePresentBeforeReinstall"] is not True
        )
    ):
        raise lane_a_local_dmg_error(
            f"{label} installation contract is invalid"
        )
    validate_lane_a_installed_tree(
        installation["tree"],
        expected_tree=expected_tree,
        label=f"{label} installed tree",
    )

    isolation = require_closed_object(
        result["isolation"],
        {
            "cleanHomeConfigured",
            "preexistingBundleApplicationsPreserved",
            "runtimeIdentityFileOverrideConfigured",
            "temporaryCFUserHomeConfigured",
        },
        label=f"{label} isolation",
    )
    if any(value is not True for value in isolation.values()):
        raise lane_a_local_dmg_error(
            f"{label} isolation contract is invalid"
        )

    mount = require_closed_object(
        result["mount"],
        {
            "cycleCount",
            "detachedBeforeEachLaunch",
            "exactFreshMountpointPerInstall",
            "nobrowse",
            "oneMountedEntityPerInstall",
            "readOnly",
            "unmountedAfterEachCopy",
        },
        label=f"{label} mount",
    )
    if (
        type(mount["cycleCount"]) is not int
        or mount["cycleCount"] != 2
        or any(
            mount[key] is not True
            for key in set(mount) - {"cycleCount"}
        )
    ):
        raise lane_a_local_dmg_error(f"{label} mount contract is invalid")

    uninstall = require_closed_object(
        result["uninstall"],
        {
            "appAbsentAfterEachRemoval",
            "applicationSupportCleanupPerformed",
            "exactTemporaryAppPathOnly",
            "exactTemporaryAppStoppedBeforeEachRemoval",
            "removalCount",
            "removalMethod",
        },
        label=f"{label} uninstall",
    )
    if (
        uninstall["appAbsentAfterEachRemoval"] is not True
        or uninstall["applicationSupportCleanupPerformed"] is not False
        or uninstall["exactTemporaryAppPathOnly"] is not True
        or uninstall["exactTemporaryAppStoppedBeforeEachRemoval"] is not True
        or type(uninstall["removalCount"]) is not int
        or uninstall["removalCount"] != 2
        or uninstall["removalMethod"] != "python-shutil-rmtree"
    ):
        raise lane_a_local_dmg_error(
            f"{label} uninstall contract is invalid"
        )


def validate_lane_a_two_launches(
    value: object,
    *,
    label: str,
    includes_observation: bool,
) -> None:
    launch_keys = {
        "distinctProcessIdentifiers",
        "exactInstalledBundlePerCycle",
        "noExactTemporaryAppRemaining",
        "runs",
    }
    if includes_observation:
        launch_keys.add("commandPolicy")
    launch_services = require_closed_object(
        value,
        launch_keys,
        label=f"{label} LaunchServices",
    )
    if (
        launch_services["distinctProcessIdentifiers"] is not True
        or launch_services["exactInstalledBundlePerCycle"] is not True
        or launch_services["noExactTemporaryAppRemaining"] is not True
        or (
            includes_observation
            and launch_services["commandPolicy"]
            != "open-new-fresh-background-exact-app-path-captured-recovery-v1"
        )
    ):
        raise lane_a_local_dmg_error(
            f"{label} LaunchServices contract is invalid"
        )
    runs = launch_services["runs"]
    if type(runs) is not list or len(runs) != 2:
        raise lane_a_local_dmg_error(
            f"{label} LaunchServices run inventory is invalid"
        )
    base_keys = {
        "activationPolicy",
        "finishedLaunching",
        "newProcessIdentifierDetected",
        "observationDeadlineReached",
        "ordinal",
        "terminationAccepted",
    }
    if includes_observation:
        base_keys |= {"executablePathMatched", "minimumObservationSeconds"}
    for ordinal, value in enumerate(runs, start=1):
        run = require_closed_object(
            value,
            base_keys,
            label=f"{label} launch run {ordinal}",
        )
        if (
            type(run["activationPolicy"]) is not int
            or run["activationPolicy"] != 0
            or type(run["ordinal"]) is not int
            or run["ordinal"] != ordinal
            or any(
                run[key] is not True
                for key in (
                    "finishedLaunching",
                    "newProcessIdentifierDetected",
                    "observationDeadlineReached",
                    "terminationAccepted",
                )
            )
            or (
                includes_observation
                and (
                    run["executablePathMatched"] is not True
                    or type(run["minimumObservationSeconds"]) is not float
                    or run["minimumObservationSeconds"] != 5.0
                )
            )
        ):
            raise lane_a_local_dmg_error(
                f"{label} launch run {ordinal} is invalid"
            )


def validate_lane_a_empty_sqlite_inventory(
    value: object,
    *,
    label: str,
) -> None:
    expected = (
        ("runtime-chat-events.sqlite", True),
        ("runtime-document-index.sqlite", False),
        ("runtime-model-pull-approvals.sqlite", False),
    )
    if type(value) is not list or len(value) != len(expected):
        raise lane_a_local_dmg_error(f"{label} inventory is invalid")
    for record, (filename, has_count) in zip(value, expected):
        keys = {"filename", "integrityCheck"}
        if has_count:
            keys.add("totalEventCount")
        item = require_closed_object(
            record,
            keys,
            label=f"{label} record {filename}",
        )
        if (
            item["filename"] != filename
            or item["integrityCheck"] != "ok"
            or (
                has_count
                and (
                    type(item["totalEventCount"]) is not int
                    or item["totalEventCount"] != 0
                )
            )
        ):
            raise lane_a_local_dmg_error(
                f"{label} record is invalid: {filename}"
            )


def validate_lane_a_canary_sqlite(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    record = require_closed_object(
        value,
        {
            "eventJsonSha256",
            "eventJsonSize",
            "integrityCheck",
            "totalEventCount",
        },
        label=label,
    )
    if (
        record["eventJsonSha256"]
        != LANE_A_LOCAL_DMG_CANARY["eventJsonSha256"]
        or type(record["eventJsonSize"]) is not int
        or record["eventJsonSize"]
        != LANE_A_LOCAL_DMG_CANARY["eventJsonSize"]
        or record["integrityCheck"] != "ok"
        or type(record["totalEventCount"]) is not int
        or record["totalEventCount"] != 1
    ):
        raise lane_a_local_dmg_error(f"{label} is invalid")
    return record


def validate_lane_a_observation(
    value: object,
    *,
    expected: dict[str, object],
    label: str,
) -> None:
    observation = require_closed_object(
        value,
        {"mode", "sha256", "size", "status"},
        label=label,
    )
    if (
        observation["mode"] != expected["mode"]
        or observation["sha256"] != expected["sha256"]
        or type(observation["size"]) is not int
        or observation["size"] != expected["size"]
        or observation["status"] != "passed"
    ):
        raise lane_a_local_dmg_error(f"{label} is invalid")


def validate_lane_a_local_dmg_uninstall_reinstall_result_bytes(
    raw: bytes,
    *,
    expected_release_id: str,
    evidence: ArchiveEvidence,
    expected_tree: dict[str, object],
) -> dict[str, object]:
    label = "lane-A local DMG uninstall/reinstall result"
    parsed = parse_lane_a_lifecycle_result_bytes(raw, label=label)
    result = require_closed_object(
        parsed,
        {
            "archiveReadback",
            "image",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "mount",
            "release",
            "schemaVersion",
            "scope",
            "state",
            "status",
            "uninstall",
        },
        label=label,
    )
    if (
        type(result["schemaVersion"]) is not int
        or result["schemaVersion"] != 1
        or result["scope"] != LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_SCOPE
        or result["status"] != "passed"
    ):
        raise lane_a_local_dmg_error(f"{label} identity or status is invalid")
    validate_lane_a_archive_binding(
        result,
        expected_release_id=expected_release_id,
        evidence=evidence,
        label=label,
    )
    validate_lane_a_two_install_contract(
        result,
        expected_tree=expected_tree,
        label=label,
        state_present_before_reinstall=False,
    )
    validate_lane_a_two_launches(
        result["launchServices"],
        label=label,
        includes_observation=False,
    )
    if result["limitations"] != list(
        LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_LIMITATIONS
    ):
        raise lane_a_local_dmg_error(f"{label} limitations are not exact")
    state = require_closed_object(
        result["state"],
        {
            "applicationSupportPreservedAcrossRemovalAndReinstall",
            "databaseCount",
            "emptyRuntimeChatVerified",
            "integrityChecks",
            "regularFileBytesAndModesUnchanged",
            "runtimeIdentityFilePresent",
            "sqlite",
            "stableAcrossRemovalAndReinstall",
        },
        label=f"{label} state",
    )
    if (
        state["applicationSupportPreservedAcrossRemovalAndReinstall"]
        is not True
        or type(state["databaseCount"]) is not int
        or state["databaseCount"] != 3
        or state["emptyRuntimeChatVerified"] is not True
        or state["integrityChecks"] != "passed"
        or state["regularFileBytesAndModesUnchanged"] is not True
        or state["runtimeIdentityFilePresent"] is not True
        or state["stableAcrossRemovalAndReinstall"] is not True
    ):
        raise lane_a_local_dmg_error(f"{label} state contract is invalid")
    validate_lane_a_empty_sqlite_inventory(
        state["sqlite"],
        label=f"{label} SQLite",
    )
    return result


def validate_lane_a_local_dmg_state_recovery_result_bytes(
    raw: bytes,
    *,
    expected_release_id: str,
    evidence: ArchiveEvidence,
    expected_tree: dict[str, object],
) -> dict[str, object]:
    label = "lane-A local DMG state-recovery result"
    parsed = parse_lane_a_lifecycle_result_bytes(raw, label=label)
    result = require_closed_object(
        parsed,
        {
            "archiveReadback",
            "canary",
            "image",
            "installation",
            "isolation",
            "launchServices",
            "limitations",
            "mount",
            "release",
            "schemaVersion",
            "scope",
            "stateRecovery",
            "status",
            "uninstall",
        },
        label=label,
    )
    if (
        type(result["schemaVersion"]) is not int
        or result["schemaVersion"] != 1
        or result["scope"] != LANE_A_LOCAL_DMG_STATE_RECOVERY_SCOPE
        or result["status"] != "passed"
    ):
        raise lane_a_local_dmg_error(f"{label} identity or status is invalid")
    validate_lane_a_archive_binding(
        result,
        expected_release_id=expected_release_id,
        evidence=evidence,
        label=label,
    )
    canary = require_closed_object(
        result["canary"],
        set(LANE_A_LOCAL_DMG_CANARY),
        label=f"{label} canary",
    )
    for key, expected in LANE_A_LOCAL_DMG_CANARY.items():
        value = canary[key]
        if type(expected) is int:
            valid = type(value) is int and value == expected
        else:
            valid = value == expected
        if not valid:
            raise lane_a_local_dmg_error(
                f"{label} canary field is invalid: {key}"
            )
    validate_lane_a_two_install_contract(
        result,
        expected_tree=expected_tree,
        label=label,
        state_present_before_reinstall=True,
    )
    validate_lane_a_two_launches(
        result["launchServices"],
        label=label,
        includes_observation=True,
    )
    if result["limitations"] != list(
        LANE_A_LOCAL_DMG_STATE_RECOVERY_LIMITATIONS
    ):
        raise lane_a_local_dmg_error(f"{label} limitations are not exact")
    state = require_closed_object(
        result["stateRecovery"],
        {
            "applicationSupportPreservedAcrossRemovalAndReinstall",
            "auxiliarySQLite",
            "databaseCount",
            "installedStateBytesAndModesUnchangedAcrossRemovalAndReinstall",
            "legacyAbsentBeforeReinstallReadback",
            "legacyFixturePreservedUnchanged",
            "legacyRemovedByHarnessBeforeReinstall",
            "migrationObservation",
            "migrationSQLite",
            "runtimeIdentityFilePresent",
            "sqliteCanaryUnchangedAcrossRemovalAndReinstall",
            "sqliteReadbackObservation",
            "sqliteReadbackSQLite",
            "totalEventCount",
        },
        label=f"{label} state recovery",
    )
    if (
        state["applicationSupportPreservedAcrossRemovalAndReinstall"]
        is not True
        or type(state["databaseCount"]) is not int
        or state["databaseCount"] != 3
        or state[
            "installedStateBytesAndModesUnchangedAcrossRemovalAndReinstall"
        ]
        is not True
        or state["legacyAbsentBeforeReinstallReadback"] is not True
        or state["legacyFixturePreservedUnchanged"] is not True
        or state["legacyRemovedByHarnessBeforeReinstall"] is not True
        or state["runtimeIdentityFilePresent"] is not True
        or state["sqliteCanaryUnchangedAcrossRemovalAndReinstall"] is not True
        or type(state["totalEventCount"]) is not int
        or state["totalEventCount"] != 1
    ):
        raise lane_a_local_dmg_error(
            f"{label} state-recovery contract is invalid"
        )
    auxiliary = state["auxiliarySQLite"]
    expected_auxiliary = (
        "runtime-document-index.sqlite",
        "runtime-model-pull-approvals.sqlite",
    )
    if type(auxiliary) is not list or len(auxiliary) != 2:
        raise lane_a_local_dmg_error(
            f"{label} auxiliary SQLite inventory is invalid"
        )
    for value, filename in zip(auxiliary, expected_auxiliary):
        record = require_closed_object(
            value,
            {"filename", "integrityCheck"},
            label=f"{label} auxiliary SQLite {filename}",
        )
        if (
            record["filename"] != filename
            or record["integrityCheck"] != "ok"
        ):
            raise lane_a_local_dmg_error(
                f"{label} auxiliary SQLite record is invalid: {filename}"
            )
    validate_lane_a_observation(
        state["migrationObservation"],
        expected=LANE_A_LOCAL_DMG_MIGRATION_OBSERVATION,
        label=f"{label} migration observation",
    )
    validate_lane_a_observation(
        state["sqliteReadbackObservation"],
        expected=LANE_A_LOCAL_DMG_SQLITE_READBACK_OBSERVATION,
        label=f"{label} SQLite readback observation",
    )
    migration_sqlite = validate_lane_a_canary_sqlite(
        state["migrationSQLite"],
        label=f"{label} migration SQLite",
    )
    readback_sqlite = validate_lane_a_canary_sqlite(
        state["sqliteReadbackSQLite"],
        label=f"{label} readback SQLite",
    )
    if migration_sqlite != readback_sqlite:
        raise lane_a_local_dmg_error(
            f"{label} SQLite canary changed across reinstall"
        )
    return result


def lane_archive_identities(
    evidence: ArchiveEvidence,
) -> tuple[FileIdentity, FileIdentity, FileIdentity]:
    observed: list[FileIdentity] = []
    for path in (
        evidence.archive_path,
        evidence.manifest_path,
        evidence.checksum_path,
    ):
        try:
            observed.append(stable_file_identity(path))
        except ReproducibilityError as error:
            raise lane_a_local_dmg_error(
                f"cannot re-read lane-A archive input: {error}"
            ) from error
    identities = tuple(observed)
    expected = (
        evidence.archive_identity,
        evidence.manifest_identity,
        evidence.checksum_identity,
    )
    if identities != expected:
        raise lane_a_local_dmg_error(
            "lane-A archive inputs changed around local DMG exercise"
        )
    return identities


def stable_lane_a_local_dmg_result_bytes(
    path: Path,
) -> tuple[bytes, FileIdentity]:
    try:
        before = stable_file_identity(path)
        raw = path.read_bytes()
        after = stable_file_identity(path)
    except (OSError, ReproducibilityError) as error:
        raise lane_a_local_dmg_error(
            f"cannot read back lane-A local DMG result: {error}"
        ) from error
    if before != after or len(raw) != before.size:
        raise lane_a_local_dmg_error(
            "lane-A local DMG result changed while being read back"
        )
    return raw, after


def sync_lane_a_local_dmg_result_parent(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.parent, flags)
        try:
            status = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(status.st_mode)
                or status.st_uid != os.getuid()
                or stat.S_IMODE(status.st_mode) & 0o022
            ):
                raise OSError(
                    "result parent is not an owner-controlled directory"
                )
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise lane_a_local_dmg_error(
            f"cannot sync lane-A local DMG result directory: {error}"
        ) from error


def publish_lane_a_local_dmg_result(
    path: Path,
    result: dict[str, object],
    *,
    expected_release_id: str,
    filename_token: str = LANE_A_LOCAL_DMG_INSTALL_FILENAME_TOKEN,
) -> FileIdentity:
    payload = canonical_json_bytes(result)
    try:
        path.parent.mkdir(mode=0o700, exist_ok=True)
    except OSError as error:
        raise lane_a_local_dmg_error(
            f"cannot create lane-A local DMG result root: {error}"
        ) from error
    validate_lane_a_lifecycle_result_path(
        path,
        expected_release_id=expected_release_id,
        filename_token=filename_token,
    )
    if os.path.lexists(path):
        existing, identity = stable_lane_a_local_dmg_result_bytes(path)
        if existing != payload:
            raise lane_a_local_dmg_error(
                "refusing to replace a different lane-A local DMG result"
            )
        sync_lane_a_local_dmg_result_parent(path)
        return identity

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
    except OSError as error:
        raise lane_a_local_dmg_error(
            f"cannot create lane-A local DMG result temporary: {error}"
        ) from error
    temporary = Path(temporary_name)
    try:
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise lane_a_local_dmg_error(
                f"cannot write lane-A local DMG result temporary: {error}"
            ) from error
        try:
            os.link(temporary, path)
        except FileExistsError:
            existing, identity = stable_lane_a_local_dmg_result_bytes(path)
            if existing != payload:
                raise lane_a_local_dmg_error(
                    "concurrent lane-A local DMG result publication differed"
                )
            sync_lane_a_local_dmg_result_parent(path)
            return identity
        except OSError as error:
            raise lane_a_local_dmg_error(
                f"cannot publish lane-A local DMG result: {error}"
            ) from error
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

    sync_lane_a_local_dmg_result_parent(path)
    raw, identity = stable_lane_a_local_dmg_result_bytes(path)
    if raw != payload:
        raise lane_a_local_dmg_error(
            "published lane-A local DMG result bytes differ"
        )
    return identity


def run_lane_a_local_dmg_install(
    *,
    clone_root: Path,
    evidence: ArchiveEvidence,
    expected_release_id: str,
    result_path: Path,
) -> dict[str, object]:
    validate_lane_a_local_dmg_result_path(
        result_path,
        expected_release_id=expected_release_id,
    )
    lane_archive_identities(evidence)
    runner_path = clone_root / LANE_A_LOCAL_DMG_RUNNER
    try:
        runner_before = stable_file_identity(runner_path)
    except ReproducibilityError as error:
        raise lane_a_local_dmg_error(
            f"cannot bind materialized local DMG runner: {error}"
        ) from error
    environment = os.environ.copy()
    environment.update(
        {
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(clone_root),
        }
    )
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                LANE_A_LOCAL_DMG_EXERCISE_PROGRAM,
                str(evidence.archive_directory),
            ],
            cwd=clone_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=LANE_A_LOCAL_DMG_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise lane_a_local_dmg_error(
            f"lane-A local DMG exercise did not complete: {error}"
        ) from error
    if completed.returncode != 0:
        raise lane_a_local_dmg_error(
            "lane-A local DMG exercise returned a nonzero status "
            f"({completed.returncode})"
        )
    try:
        runner_after = stable_file_identity(runner_path)
    except ReproducibilityError as error:
        raise lane_a_local_dmg_error(
            f"cannot re-read materialized local DMG runner: {error}"
        ) from error
    if runner_before != runner_after:
        raise lane_a_local_dmg_error(
            "materialized local DMG runner changed during exercise"
        )
    lane_archive_identities(evidence)
    result = validate_lane_a_local_dmg_result_bytes(
        completed.stdout,
        expected_release_id=expected_release_id,
        evidence=evidence,
    )
    published_identity = publish_lane_a_local_dmg_result(
        result_path,
        result,
        expected_release_id=expected_release_id,
    )
    disk_raw, disk_identity = stable_lane_a_local_dmg_result_bytes(
        result_path
    )
    disk_result = validate_lane_a_local_dmg_result_bytes(
        disk_raw,
        expected_release_id=expected_release_id,
        evidence=evidence,
    )
    if (
        disk_result != result
        or disk_identity != published_identity
    ):
        raise lane_a_local_dmg_error(
            "lane-A local DMG disk readback differs from exercised result"
        )
    lane_archive_identities(evidence)
    return result


def require_lane_a_clone_source_snapshot(
    clone_root: Path,
    *,
    expected_source_snapshot: dict[str, object],
) -> None:
    try:
        observed = archive_builder.source_snapshot(clone_root)
    except Exception as error:
        raise lane_a_local_dmg_error(
            f"cannot re-read materialized lane-A source snapshot: {error}"
        ) from error
    if observed != expected_source_snapshot:
        raise lane_a_local_dmg_error(
            "materialized lane-A source snapshot changed around lifecycle "
            "exercise"
        )


def terminate_lane_a_lifecycle_process(
    process: subprocess.Popen[bytes],
) -> None:
    process_group = process.pid

    def group_exists() -> bool:
        try:
            os.killpg(process_group, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    try:
        os.killpg(process_group, signal.SIGINT)
    except OSError:
        try:
            process.terminate()
        except OSError:
            pass

    deadline = (
        time.monotonic() + LANE_A_LIFECYCLE_INTERRUPT_TIMEOUT_SECONDS
    )
    while group_exists():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if process.poll() is None:
            try:
                process.wait(timeout=min(0.05, remaining))
            except subprocess.TimeoutExpired:
                pass
        else:
            time.sleep(min(0.05, remaining))

    if group_exists():
        try:
            os.killpg(process_group, signal.SIGKILL)
        except OSError:
            pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=LANE_A_LIFECYCLE_INTERRUPT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=LANE_A_LIFECYCLE_INTERRUPT_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            pass
    group_deadline = (
        time.monotonic() + LANE_A_LIFECYCLE_INTERRUPT_TIMEOUT_SECONDS
    )
    while group_exists() and time.monotonic() < group_deadline:
        time.sleep(0.05)
    if group_exists():
        raise lane_a_local_dmg_error(
            "lane-A lifecycle process group remained after forced cleanup"
        )


def run_bounded_lane_a_lifecycle_command(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: float,
) -> LaneALifecycleProcessResult:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise lane_a_local_dmg_error(
            f"cannot start lane-A lifecycle exercise: {error}"
        ) from error
    if process.stdout is None or process.stderr is None:
        terminate_lane_a_lifecycle_process(process)
        raise lane_a_local_dmg_error(
            "lane-A lifecycle exercise has no bounded output pipes"
        )

    streams = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {
        "stdout": LANE_A_LIFECYCLE_MAX_STDOUT_BYTES,
        "stderr": LANE_A_LIFECYCLE_MAX_STDERR_BYTES,
    }
    deadline = time.monotonic() + timeout_seconds
    try:
        streams.register(process.stdout, selectors.EVENT_READ, "stdout")
        streams.register(process.stderr, selectors.EVENT_READ, "stderr")
        while streams.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise lane_a_local_dmg_error(
                    "lane-A lifecycle exercise timed out"
                )
            events = streams.select(remaining)
            if not events:
                raise lane_a_local_dmg_error(
                    "lane-A lifecycle exercise timed out"
                )
            for key, _ in events:
                output_name = key.data
                capacity = limits[output_name] - len(buffers[output_name])
                try:
                    chunk = os.read(
                        key.fileobj.fileno(),
                        min(65_536, capacity + 1),
                    )
                except OSError as error:
                    raise lane_a_local_dmg_error(
                        "cannot read bounded lane-A lifecycle output"
                    ) from error
                if not chunk:
                    streams.unregister(key.fileobj)
                    continue
                buffers[output_name].extend(chunk)
                if len(buffers[output_name]) > limits[output_name]:
                    raise lane_a_local_dmg_error(
                        f"lane-A lifecycle {output_name} exceeded its "
                        "hard byte limit"
                    )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise lane_a_local_dmg_error(
                "lane-A lifecycle exercise timed out"
            )
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise lane_a_local_dmg_error(
                "lane-A lifecycle exercise timed out"
            ) from error
    except BaseException:
        terminate_lane_a_lifecycle_process(process)
        raise
    finally:
        streams.close()
        process.stdout.close()
        process.stderr.close()
    return LaneALifecycleProcessResult(
        returncode=returncode,
        stdout=bytes(buffers["stdout"]),
        stderr=bytes(buffers["stderr"]),
    )


def run_lane_a_lifecycle_exercise(
    *,
    clone_root: Path,
    evidence: ArchiveEvidence,
    runner_relative: Path,
    module_name: str,
    expected_source_snapshot: dict[str, object],
    validator: Callable[[bytes], dict[str, object]],
) -> dict[str, object]:
    lane_archive_identities(evidence)
    require_lane_a_clone_source_snapshot(
        clone_root,
        expected_source_snapshot=expected_source_snapshot,
    )
    runner_path = clone_root / runner_relative
    try:
        runner_before = stable_file_identity(runner_path)
    except ReproducibilityError as error:
        raise lane_a_local_dmg_error(
            f"cannot bind materialized lifecycle runner: {error}"
        ) from error
    exercise_program = f"""\
import sys
from pathlib import Path
from script import {module_name} as smoke

result = smoke.exercise(
    archive_dir=Path(sys.argv[1]),
    readiness_timeout_seconds=15.0,
    observation_seconds=5.0,
    termination_timeout_seconds=10.0,
)
sys.stdout.buffer.write(smoke.engine.canonical_json_bytes(result))
"""
    environment = os.environ.copy()
    environment.update(
        {
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(clone_root),
        }
    )
    completed = run_bounded_lane_a_lifecycle_command(
        [
            sys.executable,
            "-B",
            "-c",
            exercise_program,
            str(evidence.archive_directory),
        ],
        cwd=clone_root,
        environment=environment,
        timeout_seconds=LANE_A_LOCAL_DMG_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise lane_a_local_dmg_error(
            "lane-A lifecycle exercise returned a nonzero status "
            f"({completed.returncode})"
        )
    try:
        runner_after = stable_file_identity(runner_path)
    except ReproducibilityError as error:
        raise lane_a_local_dmg_error(
            f"cannot re-read materialized lifecycle runner: {error}"
        ) from error
    if runner_before != runner_after:
        raise lane_a_local_dmg_error(
            "materialized lifecycle runner changed during exercise"
        )
    lane_archive_identities(evidence)
    require_lane_a_clone_source_snapshot(
        clone_root,
        expected_source_snapshot=expected_source_snapshot,
    )
    return validator(completed.stdout)


def run_lane_a_local_dmg_suite(
    *,
    clone_root: Path,
    evidence: ArchiveEvidence,
    expected_release_id: str,
    expected_source_snapshot: dict[str, object],
    label: str,
) -> LaneALocalDMGSuiteEvidence:
    paths = lane_a_local_dmg_suite_paths(
        label,
        expected_release_id=expected_release_id,
    )
    install = run_lane_a_lifecycle_exercise(
        clone_root=clone_root,
        evidence=evidence,
        runner_relative=LANE_A_LOCAL_DMG_RUNNER,
        module_name="run_macos_local_dmg_install_smoke_v2",
        expected_source_snapshot=expected_source_snapshot,
        validator=lambda raw: validate_lane_a_local_dmg_result_bytes(
            raw,
            expected_release_id=expected_release_id,
            evidence=evidence,
        ),
    )
    installation = require_closed_object(
        install["installation"],
        {
            "adHocAppSealAndVersionVerified",
            "applicationsAliasPresent",
            "copyTool",
            "exactReleaseTreeCopied",
            "tree",
        },
        label="validated lane-A local DMG installation",
    )
    expected_tree = require_closed_object(
        installation["tree"],
        {
            "digestAlgorithm",
            "regularFileCount",
            "sha256",
            "totalRegularFileBytes",
        },
        label="validated lane-A local DMG installed tree",
    )

    uninstall_reinstall = run_lane_a_lifecycle_exercise(
        clone_root=clone_root,
        evidence=evidence,
        runner_relative=LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER,
        module_name="run_macos_local_dmg_uninstall_reinstall_smoke",
        expected_source_snapshot=expected_source_snapshot,
        validator=lambda raw: (
            validate_lane_a_local_dmg_uninstall_reinstall_result_bytes(
                raw,
                expected_release_id=expected_release_id,
                evidence=evidence,
                expected_tree=expected_tree,
            )
        ),
    )
    state_recovery = run_lane_a_lifecycle_exercise(
        clone_root=clone_root,
        evidence=evidence,
        runner_relative=LANE_A_LOCAL_DMG_STATE_RECOVERY_RUNNER,
        module_name=(
            "run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke"
        ),
        expected_source_snapshot=expected_source_snapshot,
        validator=lambda raw: validate_lane_a_local_dmg_state_recovery_result_bytes(
            raw,
            expected_release_id=expected_release_id,
            evidence=evidence,
            expected_tree=expected_tree,
        ),
    )
    lane_archive_identities(evidence)
    require_lane_a_clone_source_snapshot(
        clone_root,
        expected_source_snapshot=expected_source_snapshot,
    )
    return LaneALocalDMGSuiteEvidence(
        paths=paths,
        archive=evidence,
        expected_release_id=expected_release_id,
        install=install,
        uninstall_reinstall=uninstall_reinstall,
        state_recovery=state_recovery,
    )


def publish_lane_a_local_dmg_suite(
    suite: LaneALocalDMGSuiteEvidence,
) -> None:
    install_tree = require_closed_object(
        require_closed_object(
            suite.install["installation"],
            {
                "adHocAppSealAndVersionVerified",
                "applicationsAliasPresent",
                "copyTool",
                "exactReleaseTreeCopied",
                "tree",
            },
            label="validated lane-A local DMG installation",
        )["tree"],
        {
            "digestAlgorithm",
            "regularFileCount",
            "sha256",
            "totalRegularFileBytes",
        },
        label="validated lane-A local DMG installed tree",
    )
    items: tuple[
        tuple[
            Path,
            str,
            dict[str, object],
            Callable[[bytes], dict[str, object]],
        ],
        ...,
    ] = (
        (
            suite.paths.install,
            LANE_A_LOCAL_DMG_INSTALL_FILENAME_TOKEN,
            suite.install,
            lambda raw: validate_lane_a_local_dmg_result_bytes(
                raw,
                expected_release_id=suite.expected_release_id,
                evidence=suite.archive,
            ),
        ),
        (
            suite.paths.uninstall_reinstall,
            LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_FILENAME_TOKEN,
            suite.uninstall_reinstall,
            lambda raw: (
                validate_lane_a_local_dmg_uninstall_reinstall_result_bytes(
                    raw,
                    expected_release_id=suite.expected_release_id,
                    evidence=suite.archive,
                    expected_tree=install_tree,
                )
            ),
        ),
        (
            suite.paths.state_recovery,
            LANE_A_LOCAL_DMG_STATE_RECOVERY_FILENAME_TOKEN,
            suite.state_recovery,
            lambda raw: validate_lane_a_local_dmg_state_recovery_result_bytes(
                raw,
                expected_release_id=suite.expected_release_id,
                evidence=suite.archive,
                expected_tree=install_tree,
            ),
        ),
    )
    try:
        suite.paths.install.parent.mkdir(mode=0o700, exist_ok=True)
    except OSError as error:
        raise lane_a_local_dmg_error(
            f"cannot create lane-A local DMG suite result root: {error}"
        ) from error

    payloads: list[bytes] = []
    for path, filename_token, result, validator in items:
        validate_lane_a_lifecycle_result_path(
            path,
            expected_release_id=suite.expected_release_id,
            filename_token=filename_token,
        )
        payload = canonical_json_bytes(result)
        validator(payload)
        payloads.append(payload)
        if os.path.lexists(path):
            existing, _ = stable_lane_a_local_dmg_result_bytes(path)
            if existing != payload:
                raise lane_a_local_dmg_error(
                    "refusing to replace a different lane-A local DMG "
                    f"suite result: {path.name}"
                )

    staged: list[tuple[Path, int]] = []
    identities: list[FileIdentity | None] = [None] * len(items)
    try:
        for index, ((path, _, _, _), payload) in enumerate(
            zip(items, payloads)
        ):
            if os.path.lexists(path):
                continue
            descriptor: int | None = None
            try:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{path.name}.",
                    dir=path.parent,
                )
                temporary = Path(temporary_name)
                staged.append((temporary, index))
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = None
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as error:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                raise lane_a_local_dmg_error(
                    f"cannot stage lane-A local DMG suite result: {error}"
                ) from error

        for temporary, index in staged:
            path = items[index][0]
            try:
                os.link(temporary, path)
            except FileExistsError:
                existing, identity = stable_lane_a_local_dmg_result_bytes(
                    path
                )
                if existing != payloads[index]:
                    raise lane_a_local_dmg_error(
                        "concurrent lane-A local DMG suite publication "
                        f"differed: {path.name}"
                    )
                identities[index] = identity
            except OSError as error:
                raise lane_a_local_dmg_error(
                    f"cannot publish lane-A local DMG suite result: {error}"
                ) from error
    finally:
        for temporary, _ in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    sync_lane_a_local_dmg_result_parent(suite.paths.install)
    for index, ((path, _, _, validator), payload) in enumerate(
        zip(items, payloads)
    ):
        raw, identity = stable_lane_a_local_dmg_result_bytes(path)
        observed = validator(raw)
        if raw != payload or observed != items[index][2]:
            raise lane_a_local_dmg_error(
                "lane-A local DMG suite disk readback differs from "
                f"exercised result: {path.name}"
            )
        if identities[index] is not None and identities[index] != identity:
            raise lane_a_local_dmg_error(
                "lane-A local DMG suite result identity changed during "
                f"readback: {path.name}"
            )


def empty_result(
    *,
    publish_qualified: bool = True,
) -> dict[str, object]:
    if publish_qualified:
        execution_mode = PUBLISH_QUALIFIED_MODE
        publication = {
            "attempted": False,
            "independentReadback": False,
            "outcome": "not-reached",
            "policy": PUBLISH_QUALIFIED_PUBLICATION_POLICY,
            "qualifiedArchivePublished": False,
        }
    else:
        execution_mode = COMPARISON_ONLY_MODE
        publication = {
            "attempted": False,
            "independentReadback": False,
            "outcome": "disabled-comparison-only",
            "policy": COMPARISON_ONLY_PUBLICATION_POLICY,
            "qualifiedArchivePublished": False,
        }
    return {
        "builds": [],
        "comparison": None,
        "executionMode": execution_mode,
        "failure": None,
        "gradleCache": None,
        "prepublicationBinding": None,
        "publication": publication,
        "protectedArchive": {
            "afterIdentitySha256": None,
            "beforeIdentitySha256": None,
            "policy": PROTECTED_RELEASE_POLICY,
            "relativePath": None,
            "unchanged": False,
        },
        "releaseId": None,
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "scratch": {
            "fixedSwiftPath": str(SWIFT_SCRATCH),
            "policy": "fixed-owned-flocked-fresh-per-lane-v1",
            "sourceRoots": None,
        },
        "source": None,
        "status": "failed",
        "toolchainPolicy": {
            "scope": "same-host-fixed-toolchain-cache-snapshot",
            "swiftArguments": list(SWIFT_REPRO_ARGUMENTS),
        },
    }


def publish_and_record(
    result: dict[str, object],
    qualified: ArchiveEvidence,
    source_snapshot: dict[str, object],
    git_refs: GitRefs,
    protected_release_relative: Path,
    protected_archive: tuple[str, dict[str, FileIdentity]],
) -> None:
    publication = result.get("publication")
    if (
        result.get("executionMode") != PUBLISH_QUALIFIED_MODE
        or not isinstance(publication, dict)
    ):
        raise ReproducibilityError(
            70,
            "internal",
            "publication state is not initialized for publish-qualified mode",
        )
    publication.update(
        {
            "attempted": True,
            "independentReadback": None,
            "outcome": "publication-or-readback-incomplete",
            "qualifiedArchivePublished": None,
        }
    )
    details = publish_qualified_archive(
        qualified,
        source_snapshot,
        git_refs,
        protected_release_relative,
        protected_archive,
        publication=publication,
    )
    already_matched = details.get("alreadyMatched")
    if type(already_matched) is not bool:
        raise ReproducibilityError(
            70,
            "internal",
            "publication result has no exact alreadyMatched boolean",
        )
    publication.update(details)
    publication.update(
        {
            "attempted": True,
            "independentReadback": True,
            "outcome": (
                "matched-existing-verified"
                if already_matched
                else "published-verified"
            ),
            "policy": PUBLISH_QUALIFIED_PUBLICATION_POLICY,
            "qualifiedArchivePublished": not already_matched,
        }
    )


def write_result(path: Path, result: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(result))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def execute(
    result_path: Path,
    *,
    publish_qualified: bool = True,
    lane_a_local_dmg_result_path: Path | None = None,
    lane_a_local_dmg_suite_label: str | None = None,
) -> tuple[int, dict[str, object]]:
    result = empty_result(publish_qualified=publish_qualified)
    exit_code = 70
    error: ReproducibilityError | None = None
    protected_release_relative: Path | None = None
    sentinel_before: tuple[str, dict[str, FileIdentity]] | None = None
    run_root: Path | None = None
    run_id: str | None = None
    lease_created = False
    result_path_validated = False
    pending_lane_a_local_dmg_suite: LaneALocalDMGSuiteEvidence | None = None
    lock_manager = acquire_run_lock()
    lock_acquired = False
    try:
        lock_manager.__enter__()
        lock_acquired = True
        release_context = resolve_release_context()
        protected_release_relative = (
            release_context.previous_release_relative
        )
        if (
            lane_a_local_dmg_result_path is not None
            and lane_a_local_dmg_suite_label is not None
        ):
            raise ReproducibilityError(
                2,
                "invocation",
                "lane-A local DMG install-only and suite modes are mutually "
                "exclusive",
            )
        if publish_qualified and (
            lane_a_local_dmg_result_path is not None
            or lane_a_local_dmg_suite_label is not None
        ):
            raise ReproducibilityError(
                2,
                "invocation",
                "lane-A local DMG exercise is comparison-only",
            )
        result["protectedArchive"]["relativePath"] = (
            protected_release_relative.as_posix()
        )
        expected_release_id = preflight_fixed_paths(
            result_path,
            publish_qualified=publish_qualified,
            expected_release_id=release_context.release_id,
            protected_release_relative=protected_release_relative,
        )
        if lane_a_local_dmg_result_path is not None:
            validate_lane_a_local_dmg_result_path(
                lane_a_local_dmg_result_path,
                expected_release_id=expected_release_id,
            )
        if lane_a_local_dmg_suite_label is not None:
            lane_a_local_dmg_suite_paths(
                lane_a_local_dmg_suite_label,
                expected_release_id=expected_release_id,
            )
        result["releaseId"] = expected_release_id
        result_path_validated = True
        sentinel_before = capture_protected_archive(
            protected_release_relative
        )
        result["protectedArchive"]["beforeIdentitySha256"] = sentinel_before[0]
        run_id = uuid.uuid4().hex
        run_root = WORK_ROOT / f"run-{run_id}"
        run_root.mkdir(mode=0o700)
        create_swift_lease(run_id)
        lease_created = True

        print("Capturing one immutable dirty-worktree overlay...", flush=True)
        git_refs = capture_git_refs()
        overlay = capture_source_overlay()
        source_snapshot = archive_builder.source_snapshot(ROOT)
        try:
            captured_release_id = source_release_id(
                ROOT,
                exit_code=4,
                phase="source-capture",
            )
        except ReproducibilityError:
            result_path_validated = False
            raise
        if captured_release_id != expected_release_id:
            result_path_validated = False
            raise ReproducibilityError(
                4,
                "source-capture",
                "captured source release ID differs from the result basename",
            )
        result["source"] = {
            "algorithm": source_snapshot["algorithm"],
            "fileCount": source_snapshot["fileCount"],
            "overlaySha256": overlay.sha256,
            "sha256": source_snapshot["sha256"],
        }

        roots = tuple(
            run_root / name / "project" for name in SOURCE_ROOT_NAMES
        )
        result["scratch"]["sourceRoots"] = source_root_length_evidence(roots)
        print("Materializing two independent local Git containers...", flush=True)
        for clone_root in roots:
            materialize_clone(clone_root, overlay, git_refs)
            clone_snapshot = archive_builder.source_snapshot(clone_root)
            if clone_snapshot != source_snapshot:
                result_path_validated = False
                raise ReproducibilityError(
                    4,
                    "source-materialization",
                    f"materialized source snapshot differs: {clone_root}",
                )
            try:
                clone_release_id = source_release_id(
                    clone_root,
                    exit_code=4,
                    phase="source-materialization",
                )
            except ReproducibilityError:
                result_path_validated = False
                raise
            if clone_release_id != expected_release_id:
                result_path_validated = False
                raise ReproducibilityError(
                    4,
                    "source-materialization",
                    "materialized release ID differs from the result basename",
                )

        print("Cloning one Gradle cache seed into isolated A/B homes...", flush=True)
        environment = os.environ.copy()
        cache_a, cache_b, cache_count, cache_digest = prepare_gradle_caches(
            run_root,
            environment,
        )
        result["gradleCache"] = {
            "fileCount": cache_count,
            "pairInitiallyEqual": True,
            "policy": "paired-clones-from-one-stable-seed-v1",
            "seedSnapshotSha256": cache_digest,
        }
        android_sdk = resolve_android_sdk(environment)

        print("Running clean release build A...", flush=True)
        build_a = run_lane(
            roots[0],
            cache_a,
            android_sdk,
            lane_id="build-a",
        )
        result["builds"].append(build_a.result_record("build-a"))
        cleanup_swift_scratch(run_id, remove_lease=False)

        print("Running clean release build B...", flush=True)
        build_b = run_lane(
            roots[1],
            cache_b,
            android_sdk,
            lane_id="build-b",
        )
        result["builds"].append(build_b.result_record("build-b"))
        cleanup_swift_scratch(run_id, remove_lease=False)

        if (
            build_a.archive_directory.name != expected_release_id
            or build_b.archive_directory.name != expected_release_id
        ):
            result_path_validated = False
            raise ReproducibilityError(
                8,
                "archive-comparison",
                "built archive release ID differs from the result basename",
            )
        if (
            build_a.source_sha256 != source_snapshot["sha256"]
            or build_b.source_sha256 != source_snapshot["sha256"]
        ):
            raise ReproducibilityError(
                8,
                "archive-comparison",
                "archive source snapshot differs from materialized source",
            )
        print("Comparing sidecars and every ZIP member...", flush=True)
        result["comparison"] = compare_archives(build_a, build_b)
        if result["comparison"]["differences"]:
            raise ReproducibilityError(
                8,
                "archive-comparison",
                "release archives differ: "
                f"{result['comparison']['differences']}",
            )
        if lane_a_local_dmg_result_path is not None:
            print(
                "Exercising exact build A through local DMG install twice...",
                flush=True,
            )
            run_lane_a_local_dmg_install(
                clone_root=roots[0],
                evidence=build_a,
                expected_release_id=expected_release_id,
                result_path=lane_a_local_dmg_result_path,
            )
        elif lane_a_local_dmg_suite_label is not None:
            print(
                "Exercising exact build A through the complete local DMG "
                "lifecycle suite...",
                flush=True,
            )
            pending_lane_a_local_dmg_suite = run_lane_a_local_dmg_suite(
                clone_root=roots[0],
                evidence=build_a,
                expected_release_id=expected_release_id,
                expected_source_snapshot=source_snapshot,
                label=lane_a_local_dmg_suite_label,
            )
        if publish_qualified:
            (
                prepublication_binding,
                prepublication_path,
                prepublication_identity,
            ) = load_matching_prepublication_result(
                expected_release_id,
                expected_source=result["source"],
                expected_builds=result["builds"],
                expected_comparison=result["comparison"],
                protected_release_relative=protected_release_relative,
                protected_archive_identity_sha256=sentinel_before[0],
            )
            result["prepublicationBinding"] = prepublication_binding
            print("Publishing and reading back qualified build A...", flush=True)
            publish_and_record(
                result,
                build_a,
                source_snapshot,
                git_refs,
                protected_release_relative,
                sentinel_before,
            )
            if (
                stable_file_identity(prepublication_path)
                != prepublication_identity
            ):
                raise ReproducibilityError(
                    8,
                    "prepublication-binding",
                    "canonical comparison-only result changed during publication",
                )
        else:
            print(
                "Comparison-only match passed; publication is disabled.",
                flush=True,
            )
        result["status"] = "passed"
        exit_code = 0
    except ReproducibilityError as caught:
        error = caught
        exit_code = caught.exit_code
    except KeyboardInterrupt:
        error = ReproducibilityError(
            130,
            "interrupted",
            "reproducibility run interrupted",
        )
        exit_code = error.exit_code
    except Exception as caught:  # pragma: no cover - final fail-closed boundary
        error = ReproducibilityError(70, "internal", str(caught))
        exit_code = 70
    finally:
        cleanup_error: ReproducibilityError | None = None
        if lease_created and run_id is not None:
            try:
                cleanup_swift_scratch(run_id, remove_lease=True)
            except ReproducibilityError as caught:
                cleanup_error = caught
        if run_root is not None and os.path.lexists(run_root):
            try:
                if (
                    run_root.parent != WORK_ROOT
                    or not run_root.name.startswith("run-")
                    or run_root.is_symlink()
                ):
                    raise OSError("run root identity is unsafe")
                shutil.rmtree(run_root)
            except OSError as caught:
                cleanup_error = ReproducibilityError(
                    70,
                    "cleanup",
                    f"cannot remove owned run root: {caught}",
                )
        if cleanup_error is not None and error is None:
            error = cleanup_error
            exit_code = cleanup_error.exit_code

        if (
            sentinel_before is not None
            and protected_release_relative is not None
        ):
            try:
                sentinel_after = capture_protected_archive(
                    protected_release_relative
                )
                unchanged = sentinel_after == sentinel_before
                result["protectedArchive"]["afterIdentitySha256"] = (
                    sentinel_after[0]
                )
                result["protectedArchive"]["unchanged"] = unchanged
                if not unchanged:
                    error = ReproducibilityError(
                        9,
                        "protected-archive",
                        "previous release archive identity changed",
                    )
                    exit_code = 9
            except ReproducibilityError as caught:
                error = ReproducibilityError(
                    9,
                    "protected-archive",
                    str(caught),
                )
                exit_code = 9

        if (
            pending_lane_a_local_dmg_suite is not None
            and error is None
            and exit_code == 0
        ):
            try:
                publish_lane_a_local_dmg_suite(
                    pending_lane_a_local_dmg_suite
                )
            except ReproducibilityError as caught:
                error = caught
                exit_code = caught.exit_code
            except Exception as caught:
                error = lane_a_local_dmg_error(
                    f"cannot publish lane-A local DMG suite: {caught}"
                )
                exit_code = error.exit_code

        if error is not None:
            result["status"] = "failed"
            result["failure"] = {
                "code": error.exit_code,
                "message": str(error),
                "phase": error.phase,
            }
        elif exit_code == 0:
            result["failure"] = None
        try:
            if result_path_validated:
                write_result(result_path, result)
        except Exception as caught:  # result path failures must not traceback
            if exit_code != 9:
                error = ReproducibilityError(
                    70,
                    "result-write",
                    f"cannot write canonical result: {caught}",
                )
                exit_code = 70
                result["status"] = "failed"
                result["failure"] = {
                    "code": error.exit_code,
                    "message": str(error),
                    "phase": error.phase,
                }
        finally:
            if lock_acquired:
                lock_manager.__exit__(None, None, None)
                lock_acquired = False
    return exit_code, result


def default_result_path() -> Path:
    current = load_release_version_ledger()[-1]
    return RESULT_ROOT / (
        f"{archive_builder.release_id(current)}"
        f"-two-root-v{RESULT_PATH_VERSION}.json"
    )


def default_comparison_result_path() -> Path:
    current = load_release_version_ledger()[-1]
    return canonical_prepublication_result_path(
        archive_builder.release_id(current)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result",
        type=Path,
        default=None,
        help=(
            "atomic canonical JSON result path under dist/reproducibility; "
            "the basename must use the current release ID and the selected "
            "publish or prepublication namespace"
        ),
    )
    parser.add_argument(
        "--comparison-only",
        action="store_true",
        help=(
            "compare two complete isolated builds but never publish an "
            "archive into the source workspace"
        ),
    )
    parser.add_argument(
        "--lane-a-local-dmg-result",
        type=Path,
        default=None,
        help=(
            "comparison-only opt-in: exercise the exact matching build-A "
            "archive through the local DMG v2 lifecycle and publish its "
            "separate canonical JSON result under dist/lifecycle"
        ),
    )
    parser.add_argument(
        "--lane-a-local-dmg-suite-label",
        default=None,
        help=(
            "comparison-only opt-in: derive and publish the install, "
            "same-DMG uninstall/reinstall, and persisted-state recovery "
            "results under dist/lifecycle from one lowercase slug"
        ),
    )
    arguments = parser.parse_args()
    publish_qualified = not arguments.comparison_only
    lane_a_local_dmg_result_path: Path | None = None
    try:
        result_path = (
            (
                default_comparison_result_path()
                if arguments.comparison_only
                else default_result_path()
            )
            if arguments.result is None
            else arguments.result.resolve()
        ).resolve()
        release_id = validate_result_mode_path(
            result_path,
            publish_qualified=publish_qualified,
        )
        if arguments.lane_a_local_dmg_result is not None:
            if publish_qualified:
                raise ReproducibilityError(
                    2,
                    "invocation",
                    "--lane-a-local-dmg-result requires --comparison-only",
                )
            lane_a_local_dmg_result_path = Path(
                os.path.abspath(arguments.lane_a_local_dmg_result)
            )
            validate_lane_a_local_dmg_result_path(
                lane_a_local_dmg_result_path,
                expected_release_id=release_id,
            )
        if arguments.lane_a_local_dmg_suite_label is not None:
            if publish_qualified:
                raise ReproducibilityError(
                    2,
                    "invocation",
                    "--lane-a-local-dmg-suite-label requires "
                    "--comparison-only",
                )
            if lane_a_local_dmg_result_path is not None:
                raise ReproducibilityError(
                    2,
                    "invocation",
                    "--lane-a-local-dmg-result and "
                    "--lane-a-local-dmg-suite-label are mutually exclusive",
                )
            validate_lane_a_local_dmg_suite_label(
                arguments.lane_a_local_dmg_suite_label
            )
            lane_a_local_dmg_suite_paths(
                arguments.lane_a_local_dmg_suite_label,
                expected_release_id=release_id,
            )
    except (LedgerError, OSError, ReproducibilityError) as error:
        print(
            f"Clean release reproducibility failed: invocation: {error}",
            file=os.sys.stderr,
            flush=True,
        )
        return 2
    if (
        lane_a_local_dmg_result_path is None
        and arguments.lane_a_local_dmg_suite_label is None
    ):
        exit_code, result = execute(
            result_path,
            publish_qualified=publish_qualified,
        )
    elif lane_a_local_dmg_result_path is not None:
        exit_code, result = execute(
            result_path,
            publish_qualified=publish_qualified,
            lane_a_local_dmg_result_path=lane_a_local_dmg_result_path,
        )
    else:
        exit_code, result = execute(
            result_path,
            publish_qualified=publish_qualified,
            lane_a_local_dmg_suite_label=(
                arguments.lane_a_local_dmg_suite_label
            ),
        )
    if exit_code == 0:
        comparison = result["comparison"]
        archive_sha = result["builds"][0]["archive"]["sha256"]
        mode = (
            "comparison-only"
            if arguments.comparison_only
            else "reproducibility"
        )
        print(
            f"Clean release {mode} passed: "
            f"archiveSha256={archive_sha}; "
            f"memberBytesEqual={comparison['memberBytesEqual']}",
            flush=True,
        )
    else:
        failure = result["failure"]
        print(
            f"Clean release reproducibility failed: "
            f"{failure['phase']}: {failure['message']}",
            file=os.sys.stderr,
            flush=True,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
