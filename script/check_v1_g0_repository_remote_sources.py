#!/usr/bin/env python3
"""Mechanically verify two source observations required by V1 G0 V3.

The returned identities are deliberately *not* independent trust-adapter
results.  They are opaque, source-specific, non-authorizing observations that
can become inputs to a future reviewed all-seven coordinator only after owner,
registry, revocation, and verifier trust are implemented.  This module has no
context, acceptance, activation, G0-exit, or G1a API.

The default checker performs local, read-only Git object inspection only.  This
module contains no socket client; its remote matcher accepts supplied bytes as
unauthenticated candidate material and performs no network I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import time
import weakref

try:
    from script import check_v1_g0_decision as decision
    from script import check_v1_g0_receipt_bundle as receipt
except ModuleNotFoundError:
    import check_v1_g0_decision as decision
    import check_v1_g0_receipt_bundle as receipt


ROOT = Path(__file__).resolve().parents[1]
GIT_EXECUTABLE = Path("/usr/bin/git")

MAX_GIT_COMMIT_BYTES = 1_048_576
MAX_GIT_METADATA_BYTES = 262_144
MAX_GIT_STDERR_BYTES = 65_536
GIT_COMMAND_TIMEOUT_SECONDS = 20

REMOTE_HOST = "raw.githubusercontent.com"
REMOTE_PORT = 443
REMOTE_METHOD = "GET"
REMOTE_OWNER = "hanchangha1127"
REMOTE_REPOSITORY = "AetherLink"
REMOTE_REF = "refs/heads/main"
REMOTE_PATH = (
    f"/{REMOTE_OWNER}/{REMOTE_REPOSITORY}/"
    f"{receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID}/"
    f"{receipt.V3_CHECKPOINT_PATH}"
)
REMOTE_URL = f"https://{REMOTE_HOST}{REMOTE_PATH}"

EXPECTED_BASE_COMMIT_OBJECT_ID = "929fda5f2c01cd7d53325a036071b6a684ecaa1f"
EXPECTED_BASE_TREE_OBJECT_ID = "63bb7d2644321b5bfd006a7ebd82ddee1765e89d"
EXPECTED_PUBLICATION_TREE_OBJECT_ID = "fcdf392d47ab5591e6c1085dcc4e71935f115704"
EXPECTED_REVIEWED_SCOPE_ENTRY_COUNT = 18
EXPECTED_REVIEWED_SCOPE_ENTRIES_SHA256 = (
    "8e04479d4ab4941976061e066ff4a43e25b09111111c8ed96643a5ec3ee53138"
)
EXPECTED_CHECKPOINT_BLOB_OBJECT_ID = "c91cd84cfe2ba5fa69221b5643b5810a36ec7316"

REPOSITORY_VERIFIER_ID = "reviewed-repository-target-mechanical-source-v1"
REMOTE_VERIFIER_ID = "independent-remote-checkpoint-mechanical-source-v1"
SOURCE_OBSERVATION_DORMANT_MESSAGE = (
    "G0 V3 repository/remote source observations are mechanical_candidate_only; "
    "they are not authenticated trust adapters and cannot activate receipts, "
    "close G0, or authorize G1a"
)

_GIT_OBJECT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_DIFF_METADATA_PATTERN = re.compile(
    rb"^:([0-7]{6}) ([0-7]{6}) ([0-9a-f]{40}) ([0-9a-f]{40}) ([A-Z])$"
)
_TREE_ENTRY_PATTERN = re.compile(
    rb"^([0-7]{6}) ([a-z]+) ([0-9a-f]{40})\t([^\x00]+)\x00$"
)


class _SourceObservationError(ValueError):
    """Raised when a source cannot be mechanically and exactly observed."""

    def __init__(self, failures: tuple[str, ...]):
        super().__init__("; ".join(failures))
        self.failures = failures


class _RepositorySourceObservation:
    """Opaque identity for exact local Git object material."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_: object, **__: object) -> _RepositorySourceObservation:
        raise TypeError("repository source observations are verifier-only")

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("repository source observations are immutable")

    def __copy__(self) -> object:
        raise TypeError("repository source observations cannot be copied")

    def __deepcopy__(self, _: object) -> object:
        raise TypeError("repository source observations cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("repository source observations cannot be serialized")


class _RemoteCheckpointSourceObservation:
    """Opaque identity for one exact fixed-origin HTTPS body observation."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *_: object, **__: object) -> _RemoteCheckpointSourceObservation:
        raise TypeError("remote checkpoint source observations are verifier-only")

    def __setattr__(self, _: str, __: object) -> None:
        raise AttributeError("remote checkpoint source observations are immutable")

    def __copy__(self) -> object:
        raise TypeError("remote checkpoint source observations cannot be copied")

    def __deepcopy__(self, _: object) -> object:
        raise TypeError("remote checkpoint source observations cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("remote checkpoint source observations cannot be serialized")


def _make_observation_store() -> tuple[object, object, object, object]:
    repository_payloads: weakref.WeakKeyDictionary[
        _RepositorySourceObservation,
        tuple[
            tuple[str, str, str, str, str, str],
            str,
            str,
            bytes,
            tuple[bytes, ...],
            str,
        ],
    ] = weakref.WeakKeyDictionary()
    remote_payloads: weakref.WeakKeyDictionary[
        _RemoteCheckpointSourceObservation,
        tuple[
            _RepositorySourceObservation,
            tuple[str, str, str, str, str, str],
            str,
            str,
            str,
            int,
            bytes,
            bytes,
        ],
    ] = weakref.WeakKeyDictionary()

    def new_repository(
        payload: tuple[
            tuple[str, str, str, str, str, str],
            str,
            str,
            bytes,
            tuple[bytes, ...],
            str,
        ],
    ) -> _RepositorySourceObservation:
        value = object.__new__(_RepositorySourceObservation)
        repository_payloads[value] = payload
        return value

    def repository_payload(value: object) -> object:
        if type(value) is not _RepositorySourceObservation:
            return None
        return repository_payloads.get(value)

    def new_remote(
        payload: tuple[
            _RepositorySourceObservation,
            tuple[str, str, str, str, str, str],
            str,
            str,
            str,
            int,
            bytes,
            bytes,
        ],
    ) -> _RemoteCheckpointSourceObservation:
        value = object.__new__(_RemoteCheckpointSourceObservation)
        remote_payloads[value] = payload
        return value

    def remote_payload(value: object) -> object:
        if type(value) is not _RemoteCheckpointSourceObservation:
            return None
        return remote_payloads.get(value)

    return new_repository, repository_payload, new_remote, remote_payload


(
    _new_repository_identity,
    _repository_payload,
    _new_remote_identity,
    _remote_payload,
) = _make_observation_store()
del _make_observation_store


def _raise(message: str) -> None:
    raise _SourceObservationError((message,))


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (MemoryError, TypeError, ValueError, UnicodeEncodeError, RecursionError):
        _raise("source observation is not bounded canonical JSON data")


def _ordered_compact_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (MemoryError, TypeError, ValueError, UnicodeEncodeError, RecursionError):
        _raise("source observation is not bounded ordered JSON data")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_utc(value: object, label: str) -> datetime:
    failures: list[str] = []
    parsed = receipt._parse_canonical_utc(value, label, failures)
    if parsed is None or failures:
        raise _SourceObservationError(tuple(failures or (f"{label} is invalid",)))
    return parsed


def _target_binding() -> tuple[str, str, str, str, str, str]:
    return (
        receipt.EXPECTED_RECORDED_REPOSITORY_REF,
        receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
        receipt.V3_CHECKPOINT_PATH,
        receipt.LINEAGE_RAW_SHA256[-1],
        receipt.EXPECTED_EFFECTIVE_V3_SHA256,
        receipt.EXPECTED_CLOSURE_V3_SHA256,
    )


def _target_object(
    binding: tuple[str, str, str, str, str, str],
) -> dict[str, str]:
    return {
        "repositoryRef": binding[0],
        "commitObjectId": binding[1],
        "checkpointPath": binding[2],
        "checkpointRawSha256": binding[3],
        "effectiveAssuranceCanonicalSha256": binding[4],
        "effectiveClosureCanonicalSha256": binding[5],
    }


def _path_identity(path: Path, *, directory: bool, current_owner: bool) -> tuple[int, int, int, int]:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise _SourceObservationError((f"cannot inspect {path.name}: {error}",)) from error
    expected = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if not expected or stat.S_ISLNK(metadata.st_mode):
        _raise(f"{path.name} must be a regular {'directory' if directory else 'file'}")
    if current_owner and metadata.st_uid != os.geteuid():
        _raise(f"{path.name} is not owned by the current user")
    if metadata.st_mode & stat.S_IWOTH:
        _raise(f"{path.name} must not be world-writable")
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_uid)


def _git_environment() -> dict[str, str]:
    return {
        "LC_ALL": "C",
        "LANG": "C",
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "never",
    }


def _run_git(
    root: Path,
    arguments: tuple[str, ...],
    *,
    maximum_stdout_bytes: int = MAX_GIT_METADATA_BYTES,
    allowed_returncodes: tuple[int, ...] = (0,),
) -> bytes:
    command = (
        str(GIT_EXECUTABLE),
        "-C",
        str(root),
        "--no-replace-objects",
        "--literal-pathspecs",
        *arguments,
    )
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_git_environment(),
        )
    except OSError as error:
        raise _SourceObservationError(("bounded Git object inspection failed",)) from error
    assert process.stdout is not None
    assert process.stderr is not None
    streams = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {
        "stdout": maximum_stdout_bytes,
        "stderr": MAX_GIT_STDERR_BYTES,
    }
    deadline = time.monotonic() + GIT_COMMAND_TIMEOUT_SECONDS
    try:
        streams.register(process.stdout, selectors.EVENT_READ, "stdout")
        streams.register(process.stderr, selectors.EVENT_READ, "stderr")
        while streams.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _raise("bounded Git object inspection timed out")
            events = streams.select(remaining)
            if not events:
                _raise("bounded Git object inspection timed out")
            for key, _ in events:
                label = key.data
                chunk = os.read(key.fileobj.fileno(), 65_536)
                if not chunk:
                    streams.unregister(key.fileobj)
                    continue
                buffers[label].extend(chunk)
                if len(buffers[label]) > limits[label]:
                    _raise(f"Git object inspection exceeded its {label} bound")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _raise("bounded Git object inspection timed out")
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as error:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise _SourceObservationError(("bounded Git object inspection timed out",)) from error
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        streams.close()
        process.stdout.close()
        process.stderr.close()
    stdout = bytes(buffers["stdout"])
    stderr = bytes(buffers["stderr"])
    if returncode not in allowed_returncodes:
        _raise("Git object inspection returned a nonzero status")
    if stderr:
        _raise("Git object inspection emitted unexpected diagnostics")
    return stdout


def _decode_single_line(raw: bytes, label: str) -> str:
    try:
        value = raw.decode("ascii")
    except UnicodeDecodeError:
        _raise(f"{label} is not ASCII")
    if not value.endswith("\n") or "\n" in value[:-1] or "\r" in value:
        _raise(f"{label} is not one canonical line")
    return value[:-1]


def _git_object_id(kind: str, raw: bytes) -> str:
    header = f"{kind} {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _read_git_object(
    root: Path,
    object_id: str,
    expected_type: str,
    maximum_bytes: int,
    cache: dict[tuple[str, str], bytes],
) -> bytes:
    if _GIT_OBJECT_PATTERN.fullmatch(object_id) is None:
        _raise("Git object ID is not exact full lowercase SHA-1")
    cache_key = (expected_type, object_id)
    cached = cache.get(cache_key)
    if cached is not None:
        if len(cached) > maximum_bytes:
            _raise("cached Git object exceeds the requested bound")
        return cached
    actual_type = _decode_single_line(
        _run_git(root, ("cat-file", "-t", object_id), maximum_stdout_bytes=64),
        "Git object type",
    )
    if actual_type != expected_type:
        _raise(f"Git object type is not exact {expected_type}")
    size_text = _decode_single_line(
        _run_git(root, ("cat-file", "-s", object_id), maximum_stdout_bytes=64),
        "Git object size",
    )
    if not size_text.isascii() or not size_text.isdigit() or size_text.startswith("0"):
        _raise("Git object size is not a canonical positive integer")
    size = int(size_text)
    if size > maximum_bytes:
        _raise("Git object exceeds its source-specific byte bound")
    raw = _run_git(
        root,
        ("cat-file", expected_type, object_id),
        maximum_stdout_bytes=maximum_bytes,
    )
    if len(raw) != size:
        _raise("Git object bytes do not match the announced size")
    if _git_object_id(expected_type, raw) != object_id:
        _raise("Git object bytes do not reproduce the exact object ID")
    cache[cache_key] = raw
    return raw


def _parse_commit(raw: bytes) -> tuple[str, tuple[str, ...]]:
    header, separator, _ = raw.partition(b"\n\n")
    if not separator:
        _raise("Git commit object has no header terminator")
    trees: list[str] = []
    parents: list[str] = []
    for line in header.splitlines():
        if line.startswith(b"tree "):
            value = line[5:]
            try:
                trees.append(value.decode("ascii"))
            except UnicodeDecodeError:
                _raise("Git commit tree header is invalid")
        elif line.startswith(b"parent "):
            value = line[7:]
            try:
                parents.append(value.decode("ascii"))
            except UnicodeDecodeError:
                _raise("Git commit parent header is invalid")
    if len(trees) != 1 or _GIT_OBJECT_PATTERN.fullmatch(trees[0]) is None:
        _raise("Git commit must contain one exact tree object ID")
    if not parents or any(_GIT_OBJECT_PATTERN.fullmatch(value) is None for value in parents):
        _raise("Git commit parent coverage is invalid")
    return trees[0], tuple(parents)


def _parse_diff_entries(raw: bytes) -> tuple[dict[str, str], ...]:
    if not raw or not raw.endswith(b"\0"):
        _raise("Git diff-tree output is not NUL-terminated")
    fields = raw[:-1].split(b"\0")
    if len(fields) % 2:
        _raise("Git diff-tree output does not contain metadata/path pairs")
    entries: list[dict[str, str]] = []
    for index in range(0, len(fields), 2):
        match = _DIFF_METADATA_PATTERN.fullmatch(fields[index])
        if match is None:
            _raise("Git diff-tree metadata is malformed")
        try:
            path = fields[index + 1].decode("utf-8")
            old_mode, new_mode, old_id, new_id, status_code = (
                value.decode("ascii") for value in match.groups()
            )
        except UnicodeDecodeError:
            _raise("Git diff-tree path or metadata is not canonical text")
        if status_code not in ("A", "M"):
            _raise("Git diff-tree contains a non A/M change")
        entries.append(
            {
                "path": path,
                "changeType": "added" if status_code == "A" else "modified",
                "oldMode": old_mode,
                "fileMode": new_mode,
                "oldBlobObjectId": old_id,
                "blobObjectId": new_id,
            }
        )
    paths = tuple(entry["path"] for entry in entries)
    if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
        _raise("Git diff-tree paths are not unique canonical order")
    return tuple(entries)


def _parse_tree_entry(raw: bytes, expected_path: str) -> tuple[str, str, str]:
    match = _TREE_ENTRY_PATTERN.fullmatch(raw)
    if match is None:
        _raise("Git ls-tree output is not one exact NUL-terminated entry")
    try:
        mode, kind, object_id, path = (
            value.decode("utf-8") for value in match.groups()
        )
    except UnicodeDecodeError:
        _raise("Git ls-tree output is not canonical UTF-8")
    if path != expected_path:
        _raise("Git ls-tree path does not match the exact requested path")
    if mode != "100644" or kind != "blob":
        _raise("Git ls-tree entry is not an exact 100644 blob")
    return mode, kind, object_id


def _repository_policy_state(
    root: Path,
    git_dir: Path,
    objects_dir: Path,
) -> tuple[tuple[str, ...], tuple[str, ...], bytes, bytes]:
    unsafe_labels: list[str] = []
    for unsafe_path, label in (
        (objects_dir / "info" / "alternates", "Git object alternates"),
        (objects_dir / "info" / "http-alternates", "Git HTTP object alternates"),
        (git_dir / "info" / "grafts", "Git grafts"),
        (git_dir / "shallow", "shallow repository state"),
        (git_dir / "commondir", "linked-worktree common directory"),
    ):
        try:
            unsafe_path.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise _SourceObservationError((f"cannot inspect {label}: {error}",)) from error
        unsafe_labels.append(label)
    promisor_packs: list[str] = []
    try:
        with os.scandir(objects_dir / "pack") as entries:
            promisor_packs = sorted(
                entry.name for entry in entries if entry.name.endswith(".promisor")
            )
    except FileNotFoundError:
        pass
    except OSError as error:
        raise _SourceObservationError((f"cannot inspect Git packfiles: {error}",)) from error
    replace_refs = _run_git(
        root,
        ("for-each-ref", "--count=1", "--format=%(refname)", "refs/replace/"),
    )
    promisor_config = _run_git(
        root,
        (
            "config",
            "--get-regexp",
            r"^(remote\..*\.promisor|extensions\.partialClone)$",
        ),
        allowed_returncodes=(0, 1),
    )
    return (
        tuple(unsafe_labels),
        tuple(promisor_packs),
        replace_refs,
        promisor_config,
    )


def _require_safe_repository_policy(
    state: tuple[tuple[str, ...], tuple[str, ...], bytes, bytes],
) -> None:
    unsafe_labels, promisor_packs, replace_refs, promisor_config = state
    if unsafe_labels:
        _raise(f"{unsafe_labels[0]} is not allowed")
    if promisor_packs:
        _raise("promisor packfiles are not allowed")
    if replace_refs:
        _raise("Git replace refs are not allowed")
    if promisor_config:
        _raise("promisor or partial-clone lazy fetch configuration is not allowed")


def _verify_local_repository_source(
    root: Path = ROOT,
) -> _RepositorySourceObservation:
    """Verify exact pinned Git material; never consult HEAD, index, or worktree blobs."""

    if not isinstance(root, Path):
        _raise("repository root must be an exact Path")
    input_root_identity = _path_identity(root, directory=True, current_owner=True)
    try:
        canonical_root = root.resolve(strict=True)
    except OSError as error:
        raise _SourceObservationError(("repository root cannot be resolved",)) from error
    if canonical_root != root.absolute():
        _raise("repository root must not contain symlink indirection")
    root_identity = _path_identity(canonical_root, directory=True, current_owner=True)
    if root_identity != input_root_identity:
        _raise("repository root identity changed during resolution")

    git_identity = _path_identity(GIT_EXECUTABLE, directory=False, current_owner=False)
    git_dir = canonical_root / ".git"
    git_dir_identity = _path_identity(git_dir, directory=True, current_owner=True)
    objects_dir = git_dir / "objects"
    objects_identity = _path_identity(objects_dir, directory=True, current_owner=True)

    resolved_git_dir = Path(
        _decode_single_line(
            _run_git(canonical_root, ("rev-parse", "--absolute-git-dir")),
            "absolute Git directory",
        )
    )
    try:
        resolved_git_dir = resolved_git_dir.resolve(strict=True)
    except OSError as error:
        raise _SourceObservationError(("resolved Git directory is unavailable",)) from error
    if resolved_git_dir != git_dir:
        _raise("resolved Git directory is not the exact normal worktree .git directory")
    if _decode_single_line(
        _run_git(canonical_root, ("rev-parse", "--is-bare-repository")),
        "bare repository state",
    ) != "false":
        _raise("repository must be a non-bare worktree")
    if _decode_single_line(
        _run_git(canonical_root, ("rev-parse", "--show-object-format")),
        "Git object format",
    ) != "sha1":
        _raise("repository Git object format must be exact sha1")
    initial_policy_state = _repository_policy_state(
        canonical_root,
        git_dir,
        objects_dir,
    )
    _require_safe_repository_policy(initial_policy_state)

    base_commit = EXPECTED_BASE_COMMIT_OBJECT_ID
    base_tree = EXPECTED_BASE_TREE_OBJECT_ID
    publication_tree = EXPECTED_PUBLICATION_TREE_OBJECT_ID

    cache: dict[tuple[str, str], bytes] = {}
    target_commit = receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID
    commit_raw = _read_git_object(
        canonical_root,
        target_commit,
        "commit",
        MAX_GIT_COMMIT_BYTES,
        cache,
    )
    commit_tree, commit_parents = _parse_commit(commit_raw)
    if commit_tree != publication_tree or commit_parents != (base_commit,):
        _raise("target commit tree or exact parent binding changed")
    parent_raw = _read_git_object(
        canonical_root,
        base_commit,
        "commit",
        MAX_GIT_COMMIT_BYTES,
        cache,
    )
    parent_tree, _ = _parse_commit(parent_raw)
    if parent_tree != base_tree:
        _raise("base commit tree binding changed")

    raw_diff = _run_git(
        canonical_root,
        (
            "diff-tree",
            "--no-commit-id",
            "--raw",
            "-r",
            "--abbrev=40",
            "--no-renames",
            "-z",
            base_commit,
            target_commit,
        ),
    )
    diff_entries = _parse_diff_entries(raw_diff)
    if len(diff_entries) != EXPECTED_REVIEWED_SCOPE_ENTRY_COUNT:
        _raise("target commit diff does not contain the exact reviewed scope count")
    scope_entries: list[dict[str, object]] = []
    for index, actual in enumerate(diff_entries):
        path = actual["path"]
        change_type = actual["changeType"]
        file_mode = actual["fileMode"]
        expected_blob = actual["blobObjectId"]
        if not receipt._safe_artifact_path(path):
            _raise(f"target commit reviewed scope entry {index}.path is invalid")
        if file_mode not in ("100644", "100755"):
            _raise(f"target commit reviewed scope entry {index}.fileMode is invalid")
        if change_type == "added":
            if actual["oldMode"] != "000000" or actual["oldBlobObjectId"] != "0" * 40:
                _raise(f"target commit reviewed scope entry {index} add binding is invalid")
        elif actual["oldMode"] == "000000" or actual["oldBlobObjectId"] == "0" * 40:
            _raise(f"target commit reviewed scope entry {index} modify binding is invalid")
        blob = _read_git_object(
            canonical_root,
            expected_blob,
            "blob",
            receipt.MAX_REFERENCED_ARTIFACT_BYTES,
            cache,
        )
        scope_entries.append(
            {
                "path": path,
                "changeType": change_type,
                "fileMode": file_mode,
                "blobObjectId": expected_blob,
                "byteLength": len(blob),
                "rawSha256": hashlib.sha256(blob).hexdigest(),
            }
        )
    scope_digest = hashlib.sha256(_ordered_compact_bytes(scope_entries)).hexdigest()
    if scope_digest != EXPECTED_REVIEWED_SCOPE_ENTRIES_SHA256:
        _raise("target commit reviewed scope canonical digest changed")

    lineage_blobs: list[bytes] = []
    lineage_entries: list[dict[str, object]] = []
    for role, path, maximum, raw_sha256, canonical_sha256 in zip(
        receipt.LINEAGE_ROLES,
        receipt.LINEAGE_PATHS,
        receipt.LINEAGE_MAXIMUM_BYTES,
        receipt.LINEAGE_RAW_SHA256,
        receipt.LINEAGE_CANONICAL_SHA256,
    ):
        tree_raw = _run_git(
            canonical_root,
            (
                "ls-tree",
                "--full-tree",
                "--full-name",
                "-z",
                target_commit,
                "--",
                path,
            ),
            maximum_stdout_bytes=MAX_GIT_METADATA_BYTES,
        )
        mode, kind, blob_id = _parse_tree_entry(tree_raw, path)
        if mode != "100644" or kind != "blob":
            _raise(f"lineage {role} is not an exact 100644 blob")
        blob = _read_git_object(canonical_root, blob_id, "blob", maximum, cache)
        if hashlib.sha256(blob).hexdigest() != raw_sha256:
            _raise(f"lineage {role} raw SHA-256 changed")
        parse_failures: list[str] = []
        parsed = receipt._parse_object(blob, f"repository-source lineage {role}", parse_failures)
        if parsed is None or parse_failures:
            raise _SourceObservationError(tuple(parse_failures))
        if decision.canonical_json_sha256(parsed) != canonical_sha256:
            _raise(f"lineage {role} canonical SHA-256 changed")
        lineage_blobs.append(blob)
        lineage_entries.append(
            {
                "role": role,
                "path": path,
                "mode": mode,
                "objectType": kind,
                "blobObjectId": blob_id,
                "byteLength": len(blob),
                "rawSha256": raw_sha256,
                "canonicalSha256": canonical_sha256,
            }
        )
    lineage_failures: list[str] = []
    immutable_lineage = receipt._snapshot_validated_v3_lineage(
        tuple(lineage_blobs),
        label="repository-source exact commit lineage",
        failures=lineage_failures,
    )
    if immutable_lineage is None or lineage_failures:
        raise _SourceObservationError(tuple(lineage_failures))
    if _git_object_id("blob", immutable_lineage[-1]) != EXPECTED_CHECKPOINT_BLOB_OBJECT_ID:
        _raise("V3 checkpoint Git blob object ID changed")

    final_policy_state = _repository_policy_state(
        canonical_root,
        git_dir,
        objects_dir,
    )
    _require_safe_repository_policy(final_policy_state)
    if final_policy_state != initial_policy_state:
        _raise("repository replacement/alternate/promisor policy changed during inspection")

    if (
        _path_identity(canonical_root, directory=True, current_owner=True) != root_identity
        or _path_identity(git_dir, directory=True, current_owner=True) != git_dir_identity
        or _path_identity(objects_dir, directory=True, current_owner=True) != objects_identity
        or _path_identity(GIT_EXECUTABLE, directory=False, current_owner=False) != git_identity
    ):
        _raise("repository, object database, or Git executable identity changed")

    observed_at = _utc_now()
    _parse_utc(observed_at, "repository source observation time")
    binding = _target_binding()
    receipt_core = {
        "documentType": "aetherlink.v1-g0-repository-source-observation",
        "schemaVersion": 1,
        "status": "mechanically_verified_candidate_non_authorizing",
        "verifierId": REPOSITORY_VERIFIER_ID,
        "targetBinding": _target_object(binding),
        "gitObjectFormat": "sha1",
        "repositoryLayout": "normal_non_bare_no_alternates_no_replace_no_promisor",
        "commitObject": {
            "objectId": target_commit,
            "objectType": "commit",
            "byteLength": len(commit_raw),
            "rawSha256": hashlib.sha256(commit_raw).hexdigest(),
            "treeObjectId": commit_tree,
            "parentObjectIds": list(commit_parents),
        },
        "scopeProfileBinding": {
            "baseCommitObjectId": base_commit,
            "baseTreeObjectId": base_tree,
            "publicationTreeObjectId": publication_tree,
            "entryCount": len(scope_entries),
            "entriesCanonicalSha256": scope_digest,
        },
        "lineageEntries": lineage_entries,
        "lineageEntriesCanonicalSha256": hashlib.sha256(
            _canonical_bytes(lineage_entries)
        ).hexdigest(),
        "observedAt": observed_at,
    }
    core_bytes = _canonical_bytes(receipt_core)
    observation_ref = (
        "repository-source-observation:sha256:"
        + hashlib.sha256(core_bytes).hexdigest()
    )
    receipt_bytes = _canonical_bytes(
        {**receipt_core, "observationRef": observation_ref}
    )
    return _new_repository_identity(
        (
            binding,
            observed_at,
            observation_ref,
            receipt_bytes,
            immutable_lineage,
            EXPECTED_CHECKPOINT_BLOB_OBJECT_ID,
        )
    )


def _observation_receipt_matches(
    raw: object,
    observation_ref: object,
    *,
    prefix: str,
    status: str,
    verifier_id: str,
    binding: tuple[str, str, str, str, str, str],
    observed_at_field: str,
    observed_at: object,
) -> bool:
    if type(raw) is not bytes or not isinstance(observation_ref, str):
        return False
    failures: list[str] = []
    document = receipt._parse_object(raw, "source observation receipt", failures)
    if document is None or failures:
        return False
    try:
        if _canonical_bytes(document) != raw:
            return False
        embedded_ref = document.pop("observationRef", None)
        expected_ref = prefix + hashlib.sha256(_canonical_bytes(document)).hexdigest()
    except _SourceObservationError:
        return False
    if embedded_ref != observation_ref or observation_ref != expected_ref:
        return False
    time_failures: list[str] = []
    if receipt._parse_canonical_utc(
        observed_at,
        "source observation time",
        time_failures,
    ) is None or time_failures:
        return False
    return (
        document.get("status") == status
        and document.get("verifierId") == verifier_id
        and document.get("targetBinding") == _target_object(binding)
        and document.get(observed_at_field) == observed_at
    )


def _factory_owned_repository_source(value: object) -> bool:
    payload = _repository_payload(value)
    if not isinstance(payload, tuple) or len(payload) != 6:
        return False
    binding, observed_at, observation_ref, receipt_bytes, lineage, checkpoint_blob = payload
    lineage_is_exact = (
        isinstance(lineage, tuple)
        and len(lineage) == len(receipt.LINEAGE_PATHS)
        and all(type(raw) is bytes for raw in lineage)
        and tuple(hashlib.sha256(raw).hexdigest() for raw in lineage)
        == receipt.LINEAGE_RAW_SHA256
    )
    return (
        binding == _target_binding()
        and isinstance(observed_at, str)
        and isinstance(observation_ref, str)
        and lineage_is_exact
        and checkpoint_blob == EXPECTED_CHECKPOINT_BLOB_OBJECT_ID
        and _observation_receipt_matches(
            receipt_bytes,
            observation_ref,
            prefix="repository-source-observation:sha256:",
            status="mechanically_verified_candidate_non_authorizing",
            verifier_id=REPOSITORY_VERIFIER_ID,
            binding=binding,
            observed_at_field="observedAt",
            observed_at=observed_at,
        )
    )


def _single_header(
    headers: tuple[tuple[str, str], ...],
    name: str,
) -> str | None:
    values = tuple(value for key, value in headers if key == name)
    if len(values) > 1:
        _raise(f"HTTPS response contains duplicate {name} headers")
    return values[0] if values else None


def _verify_supplied_remote_checkpoint_source(
    repository_source: _RepositorySourceObservation,
    *,
    status: object,
    headers: object,
    body: object,
    started_at: object,
    completed_at: object,
    duration_millis: object,
) -> _RemoteCheckpointSourceObservation:
    """Match supplied transport material; perform no socket or network I/O."""

    if not _factory_owned_repository_source(repository_source):
        _raise("remote material requires a factory-owned repository source")
    repository_payload = _repository_payload(repository_source)
    assert isinstance(repository_payload, tuple) and len(repository_payload) == 6
    binding, repository_observed_at, repository_ref, _, lineage, checkpoint_blob = (
        repository_payload
    )
    started_time = _parse_utc(started_at, "remote source start time")
    repository_time = _parse_utc(
        repository_observed_at,
        "repository source observation time",
    )
    if started_time < repository_time:
        _raise("remote source acquisition predates its repository source")
    completed_time = _parse_utc(completed_at, "remote source completion time")
    if completed_time < started_time:
        _raise("remote source observation clock order is invalid")
    assert isinstance(started_at, str)
    assert isinstance(completed_at, str)
    if type(duration_millis) is not int or not 0 <= duration_millis <= 3_600_000:
        _raise("remote source duration is invalid")
    if type(status) is not int or status != 200:
        _raise("fixed HTTPS checkpoint endpoint did not return status 200")
    if type(headers) is not tuple or any(
        type(entry) is not tuple
        or len(entry) != 2
        or not all(type(value) is str for value in entry)
        for entry in headers
    ):
        _raise("HTTPS response headers are not an immutable normalized tuple")
    if (
        len(headers) > 128
        or any(
            name not in {"content-length", "content-encoding"}
            or not value
            or any(ord(character) < 0x20 or ord(character) > 0x7E for character in value)
            for name, value in headers
        )
        or sum(len(name) + len(value) for name, value in headers) > MAX_GIT_STDERR_BYTES
    ):
        _raise("HTTPS response headers exceed canonical bounds")
    body_failures: list[str] = []
    immutable_body = receipt._bounded_snapshot(
        body,
        "HTTPS checkpoint body",
        receipt.MAX_V3_CHECKPOINT_BYTES,
        body_failures,
    )
    if immutable_body is None or body_failures:
        raise _SourceObservationError(tuple(body_failures))
    encoding = _single_header(headers, "content-encoding")
    if encoding is not None and encoding.lower() != "identity":
        _raise("HTTPS checkpoint response uses a non-identity content encoding")
    content_length = _single_header(headers, "content-length")
    if content_length is not None:
        if (
            len(content_length) > 10
            or not content_length.isascii()
            or not content_length.isdigit()
        ):
            _raise("HTTPS checkpoint content-length is invalid")
        if int(content_length) != len(immutable_body):
            _raise("HTTPS checkpoint content-length does not match the body")
    expected_checkpoint = lineage[-1]
    if immutable_body != expected_checkpoint:
        _raise("HTTPS checkpoint bytes do not equal the exact commit blob")
    if hashlib.sha256(immutable_body).hexdigest() != receipt.LINEAGE_RAW_SHA256[-1]:
        _raise("HTTPS checkpoint raw SHA-256 changed")
    parse_failures: list[str] = []
    parsed = receipt._parse_object(
        immutable_body,
        "remote source V3 checkpoint",
        parse_failures,
    )
    if parsed is None or parse_failures:
        raise _SourceObservationError(tuple(parse_failures))
    if decision.canonical_json_sha256(parsed) != receipt.LINEAGE_CANONICAL_SHA256[-1]:
        _raise("HTTPS checkpoint canonical SHA-256 changed")
    if _git_object_id("blob", immutable_body) != checkpoint_blob:
        _raise("HTTPS checkpoint bytes do not reproduce the exact Git blob ID")

    receipt_core = {
        "documentType": "aetherlink.v1-g0-remote-checkpoint-source-observation",
        "schemaVersion": 1,
        "status": "supplied_bytes_matched_candidate_non_authorizing",
        "verifierId": REMOTE_VERIFIER_ID,
        "repositoryObservationRef": repository_ref,
        "targetBinding": _target_object(binding),
        "expectedRequest": {
            "scheme": "https",
            "host": REMOTE_HOST,
            "port": REMOTE_PORT,
            "method": REMOTE_METHOD,
            "path": REMOTE_PATH,
            "url": REMOTE_URL,
            "logicalRemoteRef": REMOTE_REF,
            "redirectCount": 0,
        },
        "suppliedResponse": {
            "httpStatus": status,
            "contentEncoding": "identity" if encoding is None else encoding.lower(),
            "bodyByteLength": len(immutable_body),
            "bodyRawSha256": hashlib.sha256(immutable_body).hexdigest(),
            "bodyCanonicalSha256": decision.canonical_json_sha256(parsed),
            "checkpointBlobObjectId": checkpoint_blob,
        },
        "provenanceBoundary": {
            "networkPerformedByThisModule": False,
            "collectorAuthenticated": False,
            "tlsPeerAuthenticatedByThisModule": False,
            "remoteRefReachabilityVerified": False,
        },
        "startedAt": started_at,
        "completedAt": completed_at,
        "durationMillis": duration_millis,
    }
    core_bytes = _canonical_bytes(receipt_core)
    observation_ref = (
        "remote-checkpoint-source-observation:sha256:"
        + hashlib.sha256(core_bytes).hexdigest()
    )
    receipt_bytes = _canonical_bytes(
        {**receipt_core, "observationRef": observation_ref}
    )
    return _new_remote_identity(
        (
            repository_source,
            binding,
            completed_at,
            observation_ref,
            repository_ref,
            duration_millis,
            receipt_bytes,
            immutable_body,
        )
    )


def _factory_owned_remote_source(value: object) -> bool:
    payload = _remote_payload(value)
    if not isinstance(payload, tuple) or len(payload) != 8:
        return False
    repository_source, binding, completed_at, observation_ref, repository_ref, duration, receipt_bytes, body = payload
    repository_payload = _repository_payload(repository_source)
    return (
        _factory_owned_repository_source(repository_source)
        and binding == _target_binding()
        and isinstance(completed_at, str)
        and isinstance(repository_ref, str)
        and isinstance(repository_payload, tuple)
        and len(repository_payload) == 6
        and repository_ref == repository_payload[2]
        and type(duration) is int
        and 0 <= duration <= 3_600_000
        and type(body) is bytes
        and body == repository_payload[4][-1]
        and hashlib.sha256(body).hexdigest() == receipt.LINEAGE_RAW_SHA256[-1]
        and _observation_receipt_matches(
            receipt_bytes,
            observation_ref,
            prefix="remote-checkpoint-source-observation:sha256:",
            status="supplied_bytes_matched_candidate_non_authorizing",
            verifier_id=REMOTE_VERIFIER_ID,
            binding=binding,
            observed_at_field="completedAt",
            observed_at=completed_at,
        )
    )


def _collect_worktree_contract_failures(root: Path = ROOT) -> tuple[str, ...]:
    """Verify the local source only; this module has no socket client."""

    try:
        local_source = _verify_local_repository_source(root)
    except _SourceObservationError as error:
        return error.failures
    if not _factory_owned_repository_source(local_source):
        return ("repository source observation is not factory-owned",)
    forbidden_names = {
        "accept",
        "activate",
        "authorize",
        "build_context",
        "close_g0",
        "derive_g1a",
    }
    if forbidden_names.intersection(globals()):
        return ("repository/remote source module exposes an authority operation",)
    return ()


def main() -> int:
    failures = _collect_worktree_contract_failures()
    if failures:
        for failure in failures:
            print(
                f"V1 G0 repository/remote source check failed: {failure}",
                file=sys.stderr,
            )
        return 1
    print(
        "V1 G0 exact local commit/tree/scope/lineage source verified read-only. "
        "No worktree document or network socket was read, no remote source was "
        "instantiated, no trust adapter or partial context was created, and "
        "G0/G1a remain closed."
    )
    return 0


__all__: tuple[str, ...] = ()


if __name__ == "__main__":
    raise SystemExit(main())
