#!/usr/bin/env python3
"""Consume the Wave5 v1 permit once and acquire 30 verified resources."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("Wave5 acquisition requires `python3 -I -B -S`")

import argparse
import ctypes
from dataclasses import dataclass
from enum import Enum, auto
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import time
import types
from typing import Any, Callable, Mapping, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave5_acquisition_v1.py"
)
EXPECTED_CHECKER_RAW = "0e004d35822f41a2ffa271c5175bdde5a51a786fb86965de320d23a2227f129f"
WAVE4_RUNNER_PATH = Path(__file__).with_name(
    "acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)
EXPECTED_WAVE4_RUNNER_RAW = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)
MAXIMUM_TOOL_BYTES = 8 * 1024 * 1024


class AcquisitionError(RuntimeError):
    def __init__(
        self,
        code: str,
        phase: str,
        *,
        consumed: bool = False,
    ) -> None:
        super().__init__(f"{code}:{phase}")
        self.code = code
        self.phase = phase
        self.consumed = consumed


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise AcquisitionError("E_ARGUMENT", "cli")


def require(value: bool, code: str, phase: str) -> None:
    if not value:
        raise AcquisitionError(code, phase)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode() + b"\n"


def _load_exact(
    path: Path,
    expected_sha256: str,
    module_name: str,
) -> tuple[types.ModuleType, bytes]:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_TOOL",
            "bootstrap",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_TOOL", "bootstrap")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_TOOL", "bootstrap")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        fields = (
            "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
            "st_size", "st_mtime_ns", "st_ctime_ns",
        )
        require(
            all(getattr(before, name) == getattr(after, name) for name in fields)
            and sha256(raw) == expected_sha256,
            "E_TOOL",
            "bootstrap",
        )
    finally:
        os.close(fd)
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = ""
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module, raw


CHECK, CHECKER_RAW = _load_exact(
    CHECKER_PATH,
    EXPECTED_CHECKER_RAW,
    "wave5_acquisition_permit_v1",
)
WAVE4, WAVE4_RUNNER_RAW = _load_exact(
    WAVE4_RUNNER_PATH,
    EXPECTED_WAVE4_RUNNER_RAW,
    "wave4_acquisition_primitives_v1",
)
VALIDATION = WAVE4.WAVE3
Fetch = Callable[[Mapping[str, Any], float], bytes]


def _assert_primitive_contract() -> None:
    require(
        sha256(WAVE4_RUNNER_RAW) == CHECK.EXPECTED_WAVE4_RUNNER_RAW
        and WAVE4.CHECK.PROXY_HOST == CHECK.PROXY_HOST
        and WAVE4.CHECK.MAX_MOD_BYTES == CHECK.MAX_MOD_BYTES
        and WAVE4.CHECK.MAX_ZIP_BYTES == CHECK.MAX_ZIP_BYTES
        and WAVE4.CHECK.MAX_AGGREGATE_BYTES == CHECK.MAX_AGGREGATE_BYTES
        and WAVE4.CHECK.MAX_HEADER_BYTES == CHECK.MAX_HEADER_BYTES
        and WAVE4.CHECK.PER_REQUEST_DEADLINE_MS
        == CHECK.PER_REQUEST_DEADLINE_MS
        and WAVE4.CHECK.WHOLE_ATTEMPT_DEADLINE_MS
        == CHECK.WHOLE_ATTEMPT_DEADLINE_MS
        and callable(WAVE4.direct_fetch)
        and callable(VALIDATION.validate_mod)
        and callable(VALIDATION.validate_zip)
        and callable(VALIDATION.decode_h1),
        "E_PRIMITIVE_BINDING",
        "bootstrap",
    )


_assert_primitive_contract()


def _primitive_call(function: Callable[..., Any], *args: Any) -> Any:
    try:
        return function(*args)
    except (WAVE4.AcquisitionError, VALIDATION.AcquisitionError) as error:
        raise AcquisitionError(error.code, error.phase) from error


def direct_fetch(resource: Mapping[str, Any], deadline: float) -> bytes:
    """Perform the exact direct HTTPS request through the pinned primitive."""
    return _primitive_call(WAVE4.direct_fetch, resource, deadline)


@dataclass(frozen=True)
class FileOps:
    fsync: Callable[[int], None] = os.fsync


REAL_OPS = FileOps()
RENAME_EXCL = 0x00000004


def _leaf_name(name: str, phase: str) -> str:
    require(
        type(name) is str
        and name not in {"", ".", ".."}
        and "/" not in name
        and "\x00" not in name,
        "E_PATH",
        phase,
    )
    return name


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _directory_anchor(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
    )


@dataclass
class HeldEntry:
    parent_fd: int
    name: str
    fd: int
    kind: str
    mode: int
    initial: os.stat_result
    raw_sha256: str | None = None
    byte_count: int | None = None

    def identity_barrier(self, phase: str) -> None:
        try:
            held = os.fstat(self.fd)
            named = os.stat(
                self.name,
                dir_fd=self.parent_fd,
                follow_symlinks=False,
            )
        except OSError as error:
            raise AcquisitionError("E_PERSISTED_IDENTITY", phase) from error
        if self.kind == "file":
            require(
                stat.S_ISREG(held.st_mode)
                and _identity(held) == _identity(self.initial)
                and _identity(named) == _identity(self.initial)
                and held.st_nlink == 1
                and stat.S_IMODE(held.st_mode) == self.mode
                and held.st_uid in {0, os.geteuid()},
                "E_PERSISTED_IDENTITY",
                phase,
            )
        else:
            require(
                stat.S_ISDIR(held.st_mode)
                and _directory_anchor(held) == _directory_anchor(self.initial)
                and _directory_anchor(named)
                == _directory_anchor(self.initial)
                and stat.S_IMODE(held.st_mode) == self.mode
                and held.st_uid in {0, os.geteuid()},
                "E_PERSISTED_IDENTITY",
                phase,
            )

    def verify_bytes(self, phase: str) -> bytes:
        require(
            self.kind == "file"
            and self.raw_sha256 is not None
            and self.byte_count is not None,
            "E_PERSISTED_IDENTITY",
            phase,
        )
        self.identity_barrier(phase)
        chunks: list[bytes] = []
        offset = 0
        while offset < self.byte_count:
            chunk = os.pread(
                self.fd,
                min(65_536, self.byte_count - offset),
                offset,
            )
            require(bool(chunk), "E_PERSISTED_IDENTITY", phase)
            chunks.append(chunk)
            offset += len(chunk)
        require(
            os.pread(self.fd, 1, offset) == b"",
            "E_PERSISTED_IDENTITY",
            phase,
        )
        raw = b"".join(chunks)
        self.identity_barrier(phase)
        require(
            len(raw) == self.byte_count
            and sha256(raw) == self.raw_sha256,
            "E_PERSISTED_IDENTITY",
            phase,
        )
        return raw

    def rebind_name(self, parent_fd: int, name: str, phase: str) -> None:
        self.parent_fd = parent_fd
        self.name = _leaf_name(name, phase)
        try:
            held = os.fstat(self.fd)
            named = os.stat(
                self.name,
                dir_fd=self.parent_fd,
                follow_symlinks=False,
            )
        except OSError as error:
            raise AcquisitionError("E_RENAME", phase) from error
        require(
            _directory_anchor(held) == _directory_anchor(named),
            "E_RENAME",
            phase,
        )
        self.initial = held

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _exclusive_file(
    parent_fd: int,
    name: str,
    raw: bytes,
    mode: int = 0o600,
    *,
    phase: str,
    ops: FileOps,
    exists_code: str = "E_WRITE",
    before_create_code: str = "E_WRITE",
    after_create_code: str = "E_WRITE",
) -> HeldEntry:
    name = _leaf_name(name, phase)
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    created = False
    fd = -1
    try:
        fd = os.open(name, flags, mode, dir_fd=parent_fd)
        created = True
        os.fchmod(fd, mode)
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            require(written > 0, after_create_code, phase)
            view = view[written:]
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) == mode
            and info.st_size == len(raw),
            after_create_code,
            phase,
        )
        ops.fsync(fd)
        ops.fsync(parent_fd)
        result = HeldEntry(
            parent_fd=parent_fd,
            name=name,
            fd=fd,
            kind="file",
            mode=mode,
            initial=os.fstat(fd),
            raw_sha256=sha256(raw),
            byte_count=len(raw),
        )
        result.verify_bytes(phase)
        fd = -1
        return result
    except FileExistsError as error:
        raise AcquisitionError(exists_code, phase) from error
    except AcquisitionError:
        raise
    except Exception as error:
        raise AcquisitionError(
            after_create_code if created else before_create_code,
            phase,
        ) from error
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def create_claim(
    parent_fd: int,
    name: str,
    payload: Mapping[str, Any],
    *,
    ops: FileOps,
) -> HeldEntry:
    return _exclusive_file(
        parent_fd,
        name,
        canonical_bytes(payload),
        0o600,
        phase="claim",
        ops=ops,
        exists_code="E_CONSUMED",
        before_create_code="E_CLAIM_NOT_CREATED",
        after_create_code="E_CLAIM_STATE_UNCERTAIN",
    )


def _fsync_directory(fd: int, *, ops: FileOps) -> None:
    try:
        ops.fsync(fd)
    except OSError as error:
        raise AcquisitionError("E_FSYNC", "filesystem") from error


def _create_directory(
    parent_fd: int,
    name: str,
    *,
    phase: str,
    ops: FileOps,
) -> HeldEntry:
    name = _leaf_name(name, phase)
    fd = -1
    created = False
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        created = True
        fd = os.open(
            name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
        os.fchmod(fd, 0o700)
        ops.fsync(parent_fd)
        result = HeldEntry(
            parent_fd=parent_fd,
            name=name,
            fd=fd,
            kind="directory",
            mode=0o700,
            initial=os.fstat(fd),
        )
        result.identity_barrier(phase)
        fd = -1
        return result
    except FileExistsError as error:
        raise AcquisitionError("E_NAMESPACE", phase) from error
    except AcquisitionError:
        raise
    except Exception as error:
        raise AcquisitionError(
            "E_DIRECTORY_STATE_UNCERTAIN" if created else "E_NAMESPACE",
            phase,
        ) from error
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def rename_exclusive(
    source_dir_fd: int,
    source_name: str,
    destination_dir_fd: int,
    destination_name: str,
    *,
    ops: FileOps,
) -> None:
    source_name = _leaf_name(source_name, "publish")
    destination_name = _leaf_name(destination_name, "publish")
    library = ctypes.CDLL(None, use_errno=True)
    renameatx_np = library.renameatx_np
    renameatx_np.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameatx_np.restype = ctypes.c_int
    result = renameatx_np(
        source_dir_fd,
        os.fsencode(source_name),
        destination_dir_fd,
        os.fsencode(destination_name),
        RENAME_EXCL,
    )
    if result != 0:
        value = ctypes.get_errno()
        code = (
            "E_FINAL_EXISTS"
            if value in {errno.EEXIST, errno.ENOTEMPTY}
            else "E_RENAME"
        )
        raise AcquisitionError(code, "publish")
    try:
        ops.fsync(source_dir_fd)
        if destination_dir_fd != source_dir_fd:
            ops.fsync(destination_dir_fd)
    except OSError as error:
        raise AcquisitionError("E_RENAME_STATE_UNCERTAIN", "publish") from error


def _remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    require(value > 0, "E_DEADLINE", phase)
    return value


def _portable(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


class ExecutionState(Enum):
    PRECLAIM = auto()
    CLAIMED = auto()
    STAGING = auto()
    READY_TO_PUBLISH = auto()
    PUBLISHED = auto()
    RECEIPT = auto()
    MANIFEST = auto()
    FAILURE = auto()


EventHook = Callable[[str, "ExecutionNamespace"], None]
Checkpoint = Callable[[str, ExecutionState], None]
RenameAt = Callable[..., None]


class ExecutionNamespace:
    """Own every mutable output FD and enforce the one-use state machine."""

    def __init__(
        self,
        root: Path,
        *,
        ops: FileOps = REAL_OPS,
        hook: EventHook | None = None,
        rename_at: RenameAt = rename_exclusive,
    ) -> None:
        self.root = root
        self.ops = ops
        self.hook = hook
        self.rename_at = rename_at
        self.dependency_fd = -1
        self.docs_fd = -1
        self.dependency_initial: os.stat_result | None = None
        self.docs_initial: os.stat_result | None = None
        self.claim: HeldEntry | None = None
        self.staging: HeldEntry | None = None
        self.accepted: HeldEntry | None = None
        self.resources: dict[str, HeldEntry] = {}
        self.evidence: HeldEntry | None = None
        self.receipt: HeldEntry | None = None
        self.manifest: HeldEntry | None = None
        self.failure: HeldEntry | None = None
        self.published = False

    @staticmethod
    def _open_directory(path: Path) -> tuple[int, os.stat_result]:
        fd = os.open(
            path,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
        )
        info = os.fstat(fd)
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_NAMESPACE",
            "preflight",
        )
        return fd, info

    def __enter__(self) -> "ExecutionNamespace":
        try:
            self.dependency_fd, self.dependency_initial = self._open_directory(
                self.root / CHECK.DEPENDENCY_ROOT
            )
            self.docs_fd, self.docs_initial = self._open_directory(
                self.root / CHECK.BASE
            )
            self.barrier(ExecutionState.PRECLAIM)
            return self
        except BaseException:
            self.close()
            raise

    def _stable(self, fd: int, initial: os.stat_result, path: Path) -> None:
        try:
            current = os.fstat(fd)
            named = os.stat(path, follow_symlinks=False)
        except OSError as error:
            raise AcquisitionError("E_NAMESPACE", "barrier") from error
        require(
            _directory_anchor(current)
            == _directory_anchor(initial)
            == _directory_anchor(named),
            "E_NAMESPACE",
            "barrier",
        )

    @staticmethod
    def _portable_names(fd: int, phase: str) -> dict[str, str]:
        try:
            raw_names = os.listdir(fd)
        except OSError as error:
            raise AcquisitionError("E_NAMESPACE", phase) from error
        names = {_portable(name): name for name in raw_names}
        require(len(names) == len(raw_names), "E_NAMESPACE", phase)
        return names

    def _fire(self, event: str) -> None:
        if self.hook is not None:
            self.hook(event, self)

    def create_claim(self, payload: Mapping[str, Any]) -> None:
        require(self.claim is None, "E_CONSUMED", "claim")
        self.claim = create_claim(
            self.dependency_fd,
            Path(CHECK.CLAIM_PATH).name,
            payload,
            ops=self.ops,
        )
        self._fire("after_claim_durable")

    def create_staging(self, attempt_id: str) -> None:
        require(
            self.claim is not None
            and self.staging is None
            and re.fullmatch(r"[0-9a-f]{32}", attempt_id) is not None,
            "E_NAMESPACE",
            "staging",
        )
        staging_name = f"{CHECK.STAGING_PREFIX}{attempt_id}"
        self.staging = _create_directory(
            self.dependency_fd,
            staging_name,
            phase="staging",
            ops=self.ops,
        )
        self.accepted = _create_directory(
            self.staging.fd,
            "accepted",
            phase="staging",
            ops=self.ops,
        )
        _fsync_directory(self.staging.fd, ops=self.ops)
        _fsync_directory(self.dependency_fd, ops=self.ops)
        self._fire("after_staging_created")

    def persist_resource(self, name: str, raw: bytes) -> HeldEntry:
        require(
            self.accepted is not None and name not in self.resources,
            "E_WRITE",
            "resource",
        )
        entry = _exclusive_file(
            self.accepted.fd,
            name,
            raw,
            0o600,
            phase="resource",
            ops=self.ops,
        )
        self.resources[name] = entry
        self._fire("after_resource_persisted")
        return entry

    def persist_evidence(self, raw: bytes) -> HeldEntry:
        require(
            self.staging is not None and self.evidence is None,
            "E_WRITE",
            "evidence",
        )
        self.evidence = _exclusive_file(
            self.staging.fd,
            "evidence.json",
            raw,
            0o600,
            phase="evidence",
            ops=self.ops,
        )
        self._fire("after_evidence_persisted")
        return self.evidence

    def sync_staging(self) -> None:
        require(
            self.staging is not None and self.accepted is not None,
            "E_FSYNC",
            "filesystem",
        )
        _fsync_directory(self.accepted.fd, ops=self.ops)
        _fsync_directory(self.staging.fd, ops=self.ops)
        _fsync_directory(self.dependency_fd, ops=self.ops)

    def verify_payloads(self, phase: str) -> None:
        for entry in self.resources.values():
            entry.verify_bytes(phase)
        require(self.evidence is not None, "E_CARDINALITY", phase)
        self.evidence.verify_bytes(phase)

    def publish(self) -> None:
        require(
            self.staging is not None
            and self.accepted is not None
            and not self.published,
            "E_RENAME",
            "publish",
        )
        old_name = self.staging.name
        final_name = Path(CHECK.FINAL_ROOT).name
        self._fire("before_publish")
        self.rename_at(
            self.dependency_fd,
            old_name,
            self.dependency_fd,
            final_name,
            ops=self.ops,
        )
        try:
            os.stat(
                old_name,
                dir_fd=self.dependency_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise AcquisitionError("E_RENAME", "publish")
        self.staging.rebind_name(
            self.dependency_fd,
            final_name,
            "publish",
        )
        self.published = True
        self._fire("after_publish")

    def persist_receipt(self, raw: bytes) -> HeldEntry:
        require(
            self.published and self.receipt is None,
            "E_WRITE",
            "receipt",
        )
        self.receipt = _exclusive_file(
            self.docs_fd,
            Path(CHECK.RECEIPT_PATH).name,
            raw,
            0o600,
            phase="receipt",
            ops=self.ops,
        )
        self._fire("after_receipt_persisted")
        return self.receipt

    def persist_manifest(self, raw: bytes) -> HeldEntry:
        require(
            self.receipt is not None and self.manifest is None,
            "E_WRITE",
            "manifest",
        )
        self.receipt.verify_bytes("manifest")
        self.manifest = _exclusive_file(
            self.docs_fd,
            Path(CHECK.MANIFEST_PATH).name,
            raw,
            0o600,
            phase="manifest",
            ops=self.ops,
        )
        self._fire("after_manifest_persisted")
        return self.manifest

    def persist_failure(self, raw: bytes) -> HeldEntry:
        require(
            not self.published
            and self.receipt is None
            and self.manifest is None
            and self.failure is None,
            "E_WRITE",
            "failure_terminal",
        )
        self.failure = _exclusive_file(
            self.docs_fd,
            Path(CHECK.FAILURE_PATH).name,
            raw,
            0o600,
            phase="failure_terminal",
            ops=self.ops,
        )
        self._fire("after_failure_persisted")
        return self.failure

    def barrier(self, state: ExecutionState) -> None:
        require(
            self.dependency_initial is not None
            and self.docs_initial is not None,
            "E_NAMESPACE",
            "barrier",
        )
        self._stable(
            self.dependency_fd,
            self.dependency_initial,
            self.root / CHECK.DEPENDENCY_ROOT,
        )
        self._stable(
            self.docs_fd,
            self.docs_initial,
            self.root / CHECK.BASE,
        )
        phase = state.name.lower()
        dependency_names = self._portable_names(
            self.dependency_fd,
            phase,
        )
        docs_names = self._portable_names(self.docs_fd, phase)
        claim = _portable(Path(CHECK.CLAIM_PATH).name)
        final = _portable(Path(CHECK.FINAL_ROOT).name)
        staging = _portable(CHECK.STAGING_PREFIX)
        staging_names = [
            name for name in dependency_names if name.startswith(staging)
        ]
        if state is ExecutionState.PRECLAIM:
            require(
                claim not in dependency_names
                and final not in dependency_names
                and not staging_names,
                "E_NAMESPACE",
                phase,
            )
        elif state is ExecutionState.CLAIMED:
            require(
                claim in dependency_names
                and final not in dependency_names
                and not staging_names,
                "E_NAMESPACE",
                phase,
            )
        elif state in {
            ExecutionState.STAGING,
            ExecutionState.READY_TO_PUBLISH,
            ExecutionState.FAILURE,
        }:
            expected_staging = (
                _portable(self.staging.name)
                if self.staging is not None
                else None
            )
            require(
                claim in dependency_names
                and final not in dependency_names
                and (
                    (expected_staging is None and not staging_names)
                    or staging_names == [expected_staging]
                ),
                "E_NAMESPACE",
                phase,
            )
        else:
            require(
                claim in dependency_names
                and final in dependency_names
                and not staging_names,
                "E_NAMESPACE",
                phase,
            )
        if self.claim is not None:
            self.claim.identity_barrier(phase)
        if self.staging is not None:
            self.staging.identity_barrier(phase)
        if self.accepted is not None:
            self.accepted.identity_barrier(phase)
            accepted_names = self._portable_names(self.accepted.fd, phase)
            require(
                set(accepted_names)
                == {_portable(name) for name in self.resources},
                "E_NAMESPACE",
                phase,
            )
            for entry in self.resources.values():
                entry.identity_barrier(phase)
            staging_names_exact = self._portable_names(
                self.staging.fd,
                phase,
            )
            expected_children = {_portable("accepted")}
            if self.evidence is not None:
                expected_children.add(_portable("evidence.json"))
                self.evidence.identity_barrier(phase)
            require(
                set(staging_names_exact) == expected_children,
                "E_NAMESPACE",
                phase,
            )
        if state in {
            ExecutionState.READY_TO_PUBLISH,
            ExecutionState.PUBLISHED,
            ExecutionState.RECEIPT,
            ExecutionState.MANIFEST,
        }:
            require(
                len(self.resources) == 30 and self.evidence is not None,
                "E_CARDINALITY",
                phase,
            )
        receipt = _portable(Path(CHECK.RECEIPT_PATH).name)
        failure = _portable(Path(CHECK.FAILURE_PATH).name)
        manifest = _portable(Path(CHECK.MANIFEST_PATH).name)
        readback = _portable(Path(CHECK.READBACK_PATH).name)
        readback_manifest = _portable(Path(CHECK.READBACK_MANIFEST_PATH).name)
        require(
            readback not in docs_names
            and readback_manifest not in docs_names,
            "E_NAMESPACE",
            phase,
        )
        if state in {
            ExecutionState.PRECLAIM,
            ExecutionState.CLAIMED,
            ExecutionState.STAGING,
            ExecutionState.READY_TO_PUBLISH,
            ExecutionState.PUBLISHED,
        }:
            require(
                receipt not in docs_names
                and failure not in docs_names
                and manifest not in docs_names,
                "E_NAMESPACE",
                phase,
            )
        elif state is ExecutionState.RECEIPT:
            require(
                receipt in docs_names
                and failure not in docs_names
                and manifest not in docs_names,
                "E_NAMESPACE",
                phase,
            )
            require(self.receipt is not None, "E_NAMESPACE", phase)
            self.receipt.identity_barrier(phase)
        elif state is ExecutionState.MANIFEST:
            require(
                receipt in docs_names
                and failure not in docs_names
                and manifest in docs_names,
                "E_NAMESPACE",
                phase,
            )
            require(
                self.receipt is not None and self.manifest is not None,
                "E_NAMESPACE",
                phase,
            )
            self.receipt.identity_barrier(phase)
            self.manifest.identity_barrier(phase)
        elif state is ExecutionState.FAILURE:
            require(
                receipt not in docs_names
                and failure in docs_names
                and manifest not in docs_names,
                "E_NAMESPACE",
                phase,
            )
            require(self.failure is not None, "E_NAMESPACE", phase)
            self.failure.identity_barrier(phase)

    def close(self) -> None:
        entries = [
            *self.resources.values(),
            self.evidence,
            self.receipt,
            self.manifest,
            self.failure,
            self.accepted,
            self.staging,
            self.claim,
        ]
        for entry in entries:
            if entry is not None:
                try:
                    entry.close()
                except OSError:
                    pass
        self.resources.clear()
        for fd in (self.dependency_fd, self.docs_fd):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self.dependency_fd = -1
        self.docs_fd = -1

    def __exit__(self, *_: object) -> None:
        self.close()


def _reject_consumed_claim(root: Path = ROOT) -> None:
    root_fd = -1
    current = -1
    opened: list[int] = []
    try:
        root_fd = os.open(
            root,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
        )
        current = os.dup(root_fd)
        opened.append(current)
        for component in CHECK.DEPENDENCY_ROOT.split("/"):
            current = os.open(
                component,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=current,
            )
            opened.append(current)
        raw_names = os.listdir(current)
        portable_names = {_portable(name): name for name in raw_names}
        require(
            len(portable_names) == len(raw_names),
            "E_NAMESPACE",
            "preflight",
        )
        claim_name = Path(CHECK.CLAIM_PATH).name
        if claim_name in raw_names:
            raise AcquisitionError("E_CONSUMED", "claim")
        require(
            _portable(claim_name) not in portable_names,
            "E_NAMESPACE",
            "preflight",
        )
    except AcquisitionError:
        raise
    except OSError as error:
        raise AcquisitionError("E_NAMESPACE", "preflight") from error
    finally:
        for fd in reversed(opened):
            try:
                os.close(fd)
            except OSError:
                pass
        if root_fd >= 0:
            try:
                os.close(root_fd)
            except OSError:
                pass


def preflight() -> tuple[dict[str, Any], dict[str, Any]]:
    _reject_consumed_claim()
    values, summary = CHECK.evaluate(True)
    permit = values["permit"]
    require(
        summary["validationPassed"] is True
        and summary["status"] == "authorized_not_consumed"
        and summary["requestCount"] == 30
        and summary["externalAuthenticationRequired"] is False
        and permit["status"] == "authorized_not_consumed"
        and permit["authority"]["wave5SourceAcquisitionAuthorizedOnce"]
        is True
        and permit["authority"]["externalAuthenticationRequired"] is False
        and permit["authority"]["repositoryOwnerIdentityProofRequired"]
        is False
        and permit["authority"]["sourceExtractionAuthorized"] is False
        and permit["oneUseContract"]["existingClaimState"]
        == "already_consumed"
        and permit["oneUseContract"]["claimAbsentAtPermitPublication"]
        is True,
        "E_PREFLIGHT",
        "preflight",
    )
    return values, summary


def _validate_resource_contract(
    rows: Sequence[Mapping[str, Any]],
    permit: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_keys = {
        "acceptedFileName",
        "expectedH1",
        "host",
        "kind",
        "maximumResponseBodyBytes",
        "method",
        "module",
        "path",
        "port",
        "requestOrdinal",
        "selectedByGraphAlgorithm",
        "tupleDigestSha256",
        "tupleId",
        "tupleOrder",
        "url",
        "version",
    }
    require(
        type(rows) is list
        and permit["requestContract"]["requestCount"] == 30
        and len(rows) == 30
        and sha256(canonical_bytes(rows))
        == permit["requestContract"]["resourcesCanonicalSha256"],
        "E_RESOURCES",
        "preflight",
    )
    result: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        require(
            type(source) is dict and set(source) == expected_keys,
            "E_RESOURCES",
            "preflight",
        )
        row = dict(source)
        ordinal = index + 1
        tuple_order = index // 2 + 1
        kind = "mod" if index % 2 == 0 else "zip"
        module = row["module"]
        version = row["version"]
        module_parts = module.split("/") if type(module) is str else []
        require(
            type(module) is str
            and type(version) is str
            and module.isascii()
            and version.isascii()
            and bool(module_parts)
            and all(
                part not in {"", ".", ".."}
                and re.fullmatch(r"[a-z0-9][a-z0-9._-]*", part) is not None
                for part in module_parts
            )
            and re.fullmatch(r"v[0-9][A-Za-z0-9.+_-]*", version) is not None,
            "E_RESOURCES",
            "preflight",
        )
        digest = sha256(f"{module}\n{version}\n".encode("utf-8"))
        path = f"/{module}/@v/{version}.{kind}"
        maximum = (
            CHECK.MAX_MOD_BYTES if kind == "mod" else CHECK.MAX_ZIP_BYTES
        )
        require(
            type(row["selectedByGraphAlgorithm"]) is bool
            and row["requestOrdinal"] == ordinal
            and row["tupleOrder"] == tuple_order
            and row["tupleDigestSha256"] == digest
            and row["tupleId"] == f"wave5-{tuple_order:03d}-{digest[:12]}"
            and row["kind"] == kind
            and row["method"] == "GET"
            and row["host"] == CHECK.PROXY_HOST
            and row["port"] == 443
            and row["path"] == path
            and row["url"] == f"https://{CHECK.PROXY_HOST}{path}"
            and row["maximumResponseBodyBytes"] == maximum
            and row["acceptedFileName"]
            == f"{tuple_order:03d}-{digest[:20]}.{kind}",
            "E_RESOURCES",
            "preflight",
        )
        _primitive_call(VALIDATION.decode_h1, row["expectedH1"], "preflight")
        result.append(row)
    for index in range(0, 30, 2):
        mod, archive = result[index:index + 2]
        require(
            mod["tupleOrder"] == archive["tupleOrder"]
            and mod["tupleId"] == archive["tupleId"]
            and mod["tupleDigestSha256"] == archive["tupleDigestSha256"]
            and mod["module"] == archive["module"]
            and mod["version"] == archive["version"]
            and mod["selectedByGraphAlgorithm"]
            == archive["selectedByGraphAlgorithm"],
            "E_RESOURCES",
            "preflight",
        )
    require(
        len({row["acceptedFileName"] for row in result}) == 30
        and len({row["url"] for row in result}) == 30
        and sum(
            row["selectedByGraphAlgorithm"] for row in result[::2]
        ) == 0,
        "E_RESOURCES",
        "preflight",
    )
    return result


def _attempt(
    fetch: Fetch,
    values: Mapping[str, Any],
    namespace: ExecutionNamespace,
    *,
    whole_timeout: float | None = None,
    checkpoint: Checkpoint | None = None,
) -> dict[str, Any]:
    permit = values["permit"]
    decision = values["decision"]
    source_rows = permit["requestContract"]["resources"]
    rows = _validate_resource_contract(source_rows, permit)
    expected_count = permit["requestContract"]["requestCount"]
    require(
        type(expected_count) is int
        and expected_count == 30
        and len(rows) == 30
        and sha256(canonical_bytes(rows))
        == permit["requestContract"]["resourcesCanonicalSha256"]
        and permit["authority"]["externalAuthenticationRequired"] is False
        and permit["authority"]["repositoryOwnerIdentityProofRequired"] is False
        and permit["authority"]["passwordRequired"] is False
        and permit["authority"]["privateKeyRequired"] is False
        and permit["authority"]["signatureRequired"] is False
        and permit["authority"]["tokenRequired"] is False
        and permit["authority"]["userActionRequired"] is False,
        "E_RESOURCES",
        "preflight",
    )

    def check(event: str, state: ExecutionState) -> None:
        if checkpoint is None:
            namespace.barrier(state)
        else:
            checkpoint(event, state)

    attempt_id = secrets.token_hex(16)
    claim = {
        "documentType": "aetherlink.wave5-source-acquisition-claim",
        "schemaVersion": "1.0",
        "attemptId": attempt_id,
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "checkerRawSha256": sha256(CHECKER_RAW),
        "requestCount": expected_count,
        "status": "consumed_active",
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }
    claim_raw = canonical_bytes(claim)
    evidence: list[dict[str, Any]] = []
    aggregate = 0
    aggregate_mod = 0
    aggregate_zip = 0
    all_zip_entries = 0
    all_zip_uncompressed = 0
    mod_by_tuple: dict[str, bytes] = {}
    publication_attempted = False
    receipt_attempted = False
    request_attempt_count = 0
    response_completed_count = 0
    response_completed_bytes = 0
    validated_count = 0
    persisted_count = 0
    claim_attempted = False
    claim_durable = False
    try:
        check("preclaim", ExecutionState.PRECLAIM)
        claim_attempted = True
        namespace.create_claim(claim)
        claim_durable = True
        check("claimed", ExecutionState.CLAIMED)
        namespace.create_staging(attempt_id)
        check("staging_created", ExecutionState.STAGING)
        deadline = time.monotonic() + (
            CHECK.WHOLE_ATTEMPT_DEADLINE_MS / 1000
            if whole_timeout is None
            else whole_timeout
        )
        for ordinal, resource in enumerate(rows, 1):
            require(
                resource["requestOrdinal"] == ordinal
                and resource["method"] == "GET"
                and resource["host"] == CHECK.PROXY_HOST
                and resource["port"] == 443
                and resource["url"]
                == f"https://{CHECK.PROXY_HOST}{resource['path']}"
                and resource["kind"]
                == ("mod" if ordinal % 2 else "zip")
                and _remaining(deadline, f"request_{ordinal:02d}") > 0,
                "E_RESOURCES",
                "request",
            )
            check(
                f"before_request_{ordinal:02d}",
                ExecutionState.STAGING,
            )
            request_attempt_count += 1
            raw = fetch(resource, deadline)
            response_completed_count += 1
            response_completed_bytes += len(raw)
            check(
                f"after_request_{ordinal:02d}",
                ExecutionState.STAGING,
            )
            aggregate += len(raw)
            if resource["kind"] == "mod":
                aggregate_mod += len(raw)
            else:
                aggregate_zip += len(raw)
            require(
                0 < len(raw) <= resource["maximumResponseBodyBytes"]
                and aggregate <= CHECK.MAX_AGGREGATE_BYTES
                and aggregate_mod <= CHECK.MAX_AGGREGATE_MOD_BYTES
                and aggregate_zip <= CHECK.MAX_AGGREGATE_ZIP_BYTES,
                "E_RESPONSE_SIZE",
                f"request_{ordinal:02d}",
            )
            if resource["kind"] == "mod":
                verified = _primitive_call(
                    VALIDATION.validate_mod,
                    raw,
                    resource["module"],
                )
                actual_h1 = verified["goModH1"]
                mod_by_tuple[resource["tupleId"]] = raw
            else:
                require(
                    resource["tupleId"] in mod_by_tuple,
                    "E_ORDER",
                    "zip",
                )
                verified = _primitive_call(
                    VALIDATION.validate_zip,
                    raw,
                    resource["module"],
                    resource["version"],
                    mod_by_tuple[resource["tupleId"]],
                )
                actual_h1 = verified["moduleZipH1"]
                all_zip_entries += verified["entryCount"]
                all_zip_uncompressed += verified["uncompressedBytes"]
                require(
                    all_zip_entries <= CHECK.MAX_ALL_ZIP_FILES
                    and all_zip_uncompressed
                    <= CHECK.MAX_ALL_ZIP_UNCOMPRESSED_BYTES,
                    "E_ZIP_AGGREGATE",
                    "zip",
                )
            _primitive_call(
                VALIDATION.decode_h1,
                resource["expectedH1"],
                "h1",
            )
            require(
                actual_h1 == resource["expectedH1"],
                "E_H1_MISMATCH",
                "verification",
            )
            validated_count += 1
            namespace.persist_resource(resource["acceptedFileName"], raw)
            persisted_count += 1
            check(
                f"resource_{ordinal:02d}_persisted",
                ExecutionState.STAGING,
            )
            evidence.append(
                {
                    "requestOrdinal": ordinal,
                    "tupleId": resource["tupleId"],
                    "kind": resource["kind"],
                    "url": resource["url"],
                    "byteCount": len(raw),
                    "rawSha256": sha256(raw),
                    "verifiedH1": actual_h1,
                    "acceptedFileName": resource["acceptedFileName"],
                    **{
                        key: value
                        for key, value in verified.items()
                        if key
                        not in {"rawSha256", "goModH1", "moduleZipH1"}
                    },
                }
            )
        require(
            len(evidence) == expected_count
            and len(mod_by_tuple) * 2 == expected_count,
            "E_CARDINALITY",
            "verification",
        )
        evidence_payload = {
            "documentType": "aetherlink.wave5-source-acquisition-evidence",
            "schemaVersion": "1.0",
            "attemptId": attempt_id,
            "requestCount": expected_count,
            "aggregateResponseBytes": aggregate,
            "aggregateModResponseBytes": aggregate_mod,
            "aggregateZipResponseBytes": aggregate_zip,
            "aggregateZipEntryCount": all_zip_entries,
            "aggregateZipUncompressedBytes": all_zip_uncompressed,
            "resources": evidence,
        }
        evidence_raw = canonical_bytes(evidence_payload)
        namespace.persist_evidence(evidence_raw)
        namespace.verify_payloads("ready_to_publish")
        namespace.sync_staging()
        check("ready_to_publish", ExecutionState.READY_TO_PUBLISH)
        publication_attempted = True
        namespace.publish()
        namespace.verify_payloads("published")
        check("published", ExecutionState.PUBLISHED)
        receipt = {
            "documentType": "aetherlink.wave5-source-acquisition-receipt",
            "schemaVersion": "1.0",
            "status": "consumed_success_pending_independent_readback",
            "attemptId": attempt_id,
            "decisionContentSha256": decision["contentBinding"]["sha256"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "checkerRawSha256": sha256(CHECKER_RAW),
            "runnerRawSha256": next(
                row["rawSha256"]
                for row in permit["toolBindings"]
                if row["path"] == CHECK.RUNNER_PATH
            ),
            "claimRawSha256": sha256(claim_raw),
            "acceptedEvidenceRawSha256": sha256(evidence_raw),
            "acceptedResourceHashSetCanonicalSha256": sha256(
                canonical_bytes(
                    [
                        {
                            "requestOrdinal": row["requestOrdinal"],
                            "acceptedFileName": row["acceptedFileName"],
                            "rawSha256": row["rawSha256"],
                            "verifiedH1": row["verifiedH1"],
                        }
                        for row in evidence
                    ]
                )
            ),
            "requestCount": expected_count,
            "modCount": expected_count // 2,
            "zipCount": expected_count // 2,
            "acceptedResourceCount": expected_count,
            "aggregateResponseBytes": aggregate,
            "aggregateModResponseBytes": aggregate_mod,
            "aggregateZipResponseBytes": aggregate_zip,
            "aggregateZipEntryCount": all_zip_entries,
            "aggregateZipUncompressedBytes": all_zip_uncompressed,
            "acceptedPath": CHECK.FINAL_ACCEPTED,
            "sourceAcquired": True,
            "sourceExtracted": False,
            "sourceLoadedOrExecuted": False,
            "compiled": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        receipt_raw = canonical_bytes(receipt)
        receipt_attempted = True
        namespace.persist_receipt(receipt_raw)
        require(namespace.receipt is not None, "E_WRITE", "receipt")
        namespace.receipt.verify_bytes("receipt")
        check("receipt", ExecutionState.RECEIPT)
        manifest = {
            "documentType": "aetherlink.wave5-source-acquisition-manifest",
            "schemaVersion": "1.0",
            "status": "consumed_success_pending_independent_readback",
            "attemptId": attempt_id,
            "receiptPath": CHECK.RECEIPT_PATH,
            "receiptRawSha256": sha256(receipt_raw),
            "manifestWrittenLast": True,
        }
        manifest_raw = canonical_bytes(manifest)
        namespace.persist_manifest(manifest_raw)
        require(namespace.manifest is not None, "E_WRITE", "manifest")
        namespace.manifest.verify_bytes("manifest")
        check("manifest", ExecutionState.MANIFEST)
        return receipt
    except Exception as error:
        claim_durable = claim_durable or namespace.claim is not None
        if not claim_durable:
            if not claim_attempted:
                if isinstance(error, AcquisitionError):
                    raise
                raise AcquisitionError("E_PREFLIGHT", "preclaim") from error
            if isinstance(error, AcquisitionError) and error.code in {
                "E_CONSUMED",
                "E_CLAIM_NOT_CREATED",
                "E_CLAIM_STATE_UNCERTAIN",
            }:
                raise
            raise AcquisitionError(
                "E_CLAIM_STATE_UNCERTAIN",
                "claim",
            ) from error
        if isinstance(error, AcquisitionError):
            code, phase = error.code, error.phase
        else:
            code, phase = "E_INTERNAL", "attempt"
        failure = {
            "documentType": "aetherlink.wave5-source-acquisition-failure",
            "schemaVersion": "1.0",
            "status": "consumed_failure_no_retry",
            "attemptId": attempt_id,
            "failureCode": code,
            "failurePhase": phase,
            "decisionContentSha256": decision["contentBinding"]["sha256"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "checkerRawSha256": sha256(CHECKER_RAW),
            "runnerRawSha256": next(
                row["rawSha256"]
                for row in permit["toolBindings"]
                if row["path"] == CHECK.RUNNER_PATH
            ),
            "claimRawSha256": sha256(claim_raw),
            "resourceSetCanonicalSha256": permit[
                "requestContract"
            ]["resourcesCanonicalSha256"],
            "requestAttemptCount": request_attempt_count,
            "responseCompletedCount": response_completed_count,
            "responseCompletedBytes": response_completed_bytes,
            "validatedResourceCount": validated_count,
            "persistedResourceCount": persisted_count,
            "sourceAcquired": response_completed_count > 0,
            "sourceExtracted": False,
            "retryResumeOrBackfillAllowed": False,
            "claimRetained": True,
            "stagingRetained": namespace.staging is not None,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        if publication_attempted or receipt_attempted or namespace.published:
            raise AcquisitionError(
                "E_POST_PUBLISH_UNCERTAIN",
                "terminal_state",
            ) from error
        try:
            namespace.persist_failure(canonical_bytes(failure))
            require(namespace.failure is not None, "E_WRITE", "failure_terminal")
            namespace.failure.verify_bytes("failure_terminal")
            check("failure", ExecutionState.FAILURE)
        except Exception as publication_error:
            raise AcquisitionError(
                "E_FAILURE_PUBLICATION_UNCERTAIN",
                "failure_terminal",
            ) from publication_error
        raise AcquisitionError(code, phase, consumed=True) from error


def execute(fetch: Fetch = direct_fetch) -> dict[str, Any]:
    values, _ = preflight()
    old_umask = os.umask(0o077)
    previous_handler = signal.getsignal(signal.SIGALRM)
    old_delay, old_interval = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()

    def alarm_handler(_signum: int, _frame: Any) -> None:
        raise AcquisitionError("E_DEADLINE", "whole_attempt")

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(
        signal.ITIMER_REAL,
        CHECK.WHOLE_ATTEMPT_DEADLINE_MS / 1000,
    )
    try:
        with CHECK.AuthorityFiles(ROOT, values["permit"]) as authority:
            with ExecutionNamespace(ROOT) as namespace:
                def checkpoint(
                    _event: str,
                    state: ExecutionState,
                ) -> None:
                    authority.barrier()
                    namespace.barrier(state)
                    authority.barrier()

                return _attempt(
                    fetch,
                    values,
                    namespace,
                    checkpoint=checkpoint,
                )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        elapsed = time.monotonic() - started
        if old_delay > 0:
            signal.setitimer(
                signal.ITIMER_REAL,
                max(0.000001, old_delay - elapsed),
                old_interval,
            )
        os.umask(old_umask)


def validate_execution_context() -> dict[str, Any]:
    values, summary = preflight()
    with CHECK.AuthorityFiles(ROOT, values["permit"]) as authority:
        with ExecutionNamespace(ROOT) as namespace:
            authority.barrier()
            namespace.barrier(ExecutionState.PRECLAIM)
            authority.barrier()
    return {
        "documentType":
            "aetherlink.wave5-source-acquisition-execution-context-check",
        "schemaVersion": "1.0",
        "status": summary["status"],
        "validationPassed": True,
        "requestCount": summary["requestCount"],
        "networkUsed": False,
        "fileWriteCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def error_document(error: AcquisitionError) -> dict[str, Any]:
    if error.code == "E_CONSUMED":
        status = "already_consumed"
    elif error.code in {
        "E_CLAIM_STATE_UNCERTAIN",
        "E_FAILURE_PUBLICATION_UNCERTAIN",
        "E_POST_PUBLISH_UNCERTAIN",
    }:
        status = "consumed_terminal_state_uncertain"
    elif error.consumed:
        status = "consumed_failure_no_retry"
    else:
        status = "failed_closed"
    return {
        "documentType": "aetherlink.wave5-source-acquisition-error",
        "schemaVersion": "1.0",
        "status": status,
        "failureCode": error.code,
        "failurePhase": error.phase,
        "retryAllowed": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False)
        parser.add_argument("--execute", action="store_true")
        args = parser.parse_args(argv)
        require(args.execute, "E_ARGUMENT", "cli")
        sys.stdout.buffer.write(canonical_bytes(execute()))
        return 0
    except AcquisitionError as error:
        sys.stdout.buffer.write(canonical_bytes(error_document(error)))
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                error_document(AcquisitionError("E_INTERNAL", "runner"))
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
