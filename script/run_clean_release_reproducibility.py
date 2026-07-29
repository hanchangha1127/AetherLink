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
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Iterator
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
PROTECTED_RELEASE_RELATIVE = Path(
    "dist/releases/aetherlink-1.0.0+3-local-v1"
)
RESULT_ROOT = ROOT / "dist/reproducibility"
RESULT_SCHEMA_VERSION = 2
SOURCE_ROOT_NAMES = ("lane-a", "lane-b-unequal")
SOURCE_ROOT_POLICY = "distinct-unequal-utf8-byte-length-v1"
SWIFT_REPRO_ARGUMENTS = (
    "--jobs",
    "1",
    "--scratch-path",
    str(SWIFT_SCRATCH),
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


def preflight_fixed_paths(result_path: Path) -> None:
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
    for protected in (ROOT, ROOT / PROTECTED_RELEASE_RELATIVE, result_path.parent):
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
    root: Path = ROOT,
) -> tuple[str, dict[str, FileIdentity]]:
    directory = root / PROTECTED_RELEASE_RELATIVE
    if directory.is_symlink() or not directory.is_dir():
        raise ReproducibilityError(
            2,
            "protected-archive",
            f"protected build3 archive directory is unavailable: {directory}",
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
            f"protected build3 sidecar set differs: {sorted(actual)}",
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


def publish_qualified_archive(
    qualified: ArchiveEvidence,
    source_snapshot: dict[str, object],
    git_refs: GitRefs,
    protected_archive: tuple[str, dict[str, FileIdentity]],
) -> dict[str, object]:
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
    if capture_protected_archive() != protected_archive:
        raise ReproducibilityError(
            9,
            "protected-archive",
            "protected build3 archive changed before publication",
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
                f"qualified sidecar changed before publication: {path.name}",
            )
    try:
        archive_reader.verify_release_archive(qualified.archive_directory)
        published_directory, already_matched = (
            archive_builder.publish_archive_directory(
                archive_builder.DEFAULT_OUTPUT_ROOT,
                release_id,
                qualified.archive_path,
                qualified.manifest_path.read_bytes(),
                expected_sidecars=qualified_identities,
            )
        )
        archive_reader.verify_release_archive(published_directory)
    except (
        OSError,
        archive_builder.ReleaseArchiveError,
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
    return {
        "alreadyMatched": already_matched,
        "archiveDirectory": published_directory.relative_to(ROOT).as_posix(),
        "archiveSha256": published.archive_identity.sha256,
        "checksumSha256": published.checksum_identity.sha256,
        "independentReadback": True,
        "manifestSha256": published.manifest_identity.sha256,
        "publishedBytesEqualLaneA": True,
        "sourceLane": "build-a",
        "sourceSnapshotUnchanged": True,
    }


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
    current = load_release_version_ledger()[-1]
    release_id = archive_builder.release_id(current)
    return capture_archive(clone_root, release_id)


def empty_result() -> dict[str, object]:
    return {
        "builds": [],
        "comparison": None,
        "failure": None,
        "gradleCache": None,
        "publication": None,
        "protectedArchive": {
            "afterIdentitySha256": None,
            "beforeIdentitySha256": None,
            "relativePath": PROTECTED_RELEASE_RELATIVE.as_posix(),
            "unchanged": False,
        },
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


def execute(result_path: Path) -> tuple[int, dict[str, object]]:
    result = empty_result()
    exit_code = 70
    error: ReproducibilityError | None = None
    sentinel_before: tuple[str, dict[str, FileIdentity]] | None = None
    run_root: Path | None = None
    run_id: str | None = None
    lease_created = False
    result_path_validated = False
    lock_manager = acquire_run_lock()
    lock_acquired = False
    try:
        sentinel_before = capture_protected_archive()
        result["protectedArchive"]["beforeIdentitySha256"] = sentinel_before[0]
        lock_manager.__enter__()
        lock_acquired = True
        preflight_fixed_paths(result_path)
        result_path_validated = True
        run_id = uuid.uuid4().hex
        run_root = WORK_ROOT / f"run-{run_id}"
        run_root.mkdir(mode=0o700)
        create_swift_lease(run_id)
        lease_created = True

        print("Capturing one immutable dirty-worktree overlay...", flush=True)
        git_refs = capture_git_refs()
        overlay = capture_source_overlay()
        source_snapshot = archive_builder.source_snapshot(ROOT)
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
                raise ReproducibilityError(
                    4,
                    "source-materialization",
                    f"materialized source snapshot differs: {clone_root}",
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
        print("Publishing and reading back qualified build A...", flush=True)
        result["publication"] = publish_qualified_archive(
            build_a,
            source_snapshot,
            git_refs,
            sentinel_before,
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

        if sentinel_before is not None:
            try:
                sentinel_after = capture_protected_archive()
                unchanged = sentinel_after == sentinel_before
                result["protectedArchive"]["afterIdentitySha256"] = (
                    sentinel_after[0]
                )
                result["protectedArchive"]["unchanged"] = unchanged
                if not unchanged:
                    error = ReproducibilityError(
                        9,
                        "protected-archive",
                        "protected build3 archive identity changed",
                    )
                    exit_code = 9
            except ReproducibilityError as caught:
                error = ReproducibilityError(
                    9,
                    "protected-archive",
                    str(caught),
                )
                exit_code = 9

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
        f"{archive_builder.release_id(current)}-two-root-v2.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result",
        type=Path,
        default=None,
        help=(
            "atomic canonical JSON result path outside the fixed scratch; "
            "defaults to a release-ID-qualified file under dist/reproducibility"
        ),
    )
    arguments = parser.parse_args()
    try:
        result_path = (
            default_result_path()
            if arguments.result is None
            else arguments.result.resolve()
        )
    except (LedgerError, OSError) as error:
        print(
            f"Clean release reproducibility failed: invocation: {error}",
            file=os.sys.stderr,
            flush=True,
        )
        return 2
    exit_code, result = execute(result_path.resolve())
    if exit_code == 0:
        comparison = result["comparison"]
        archive_sha = result["builds"][0]["archive"]["sha256"]
        print(
            "Clean release reproducibility passed: "
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
