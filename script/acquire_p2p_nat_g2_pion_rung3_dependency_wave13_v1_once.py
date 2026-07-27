#!/usr/bin/env python3
"""Consume the Wave13 v1 permit once and acquire 8 verified resources."""

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
    raise RuntimeError("Wave13 acquisition requires `python3 -I -B -S`")

import argparse
import ctypes
from dataclasses import dataclass, replace
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
import threading
import time
import types
from typing import Any, Callable, Mapping, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave13_acquisition_v1.py"
)
# Finalized reverse pin to the exact Wave13 acquisition checker bytes. The
# checker independently binds this runner through its normalized digest, so
# either side changing without a complete reseal fails closed.
EXPECTED_CHECKER_RAW = "0ea506ac073e854a04bfc22c6b3a4d25afd957d9c4043af1e55c6b876eb87612"
EXPECTED_WAVE13_IDENTITY = (
    (
        "golang.org/x/mod",
        "v0.26.0",
        "h1:/j6NAhSk8iQ723BGAUyoAcn7SlD7s15Dp9Nd/SfeaFQ=",
        "h1:EGMPT//Ezu+ylkCijjPc+f4Aih7sZvaAr+O3EHBxvZg=",
    ),
    (
        "golang.org/x/net",
        "v0.42.0",
        "h1:FF1RA5d3u7nAYA4z2TkclSCKh68eSXtiFwcWQpPXdt8=",
        "h1:jzkYrhi3YQWD6MLBJcsklgQsoAcw89EcZbJw8Z614hs=",
    ),
    (
        "golang.org/x/sys",
        "v0.34.0",
        "h1:BJP2sWEmIv4KK5OTEluFJCKSidICx8ciO85XgH3Ak8k=",
        "h1:H5Y5sJ2L2JRdyv7ROF1he/lPdvFsd0mJHFw2ThKHxLA=",
    ),
    (
        "golang.org/x/telemetry",
        "v0.0.0-20250710130107-8d8967aff50b",
        "h1:4ZwOYna0/zsOKwuR5X/m0QFOJpSZvAxFfkQT+Erd9D4=",
        "h1:DU+gwOBXU+6bO0sEyO7o/NeMlxZxCZEvI7v+J4a1zRQ=",
    ),
)
EXPECTED_WAVE13_RESOURCE_CONTRACT_SHA256 = (
    "cdb0c96d670feb69063b50709a342313501de575e4d8d692f943dffcab176f29"
)
EXPECTED_AUTHORITY = {
    "wave13PublicProxy8GetAcquisitionAuthorizedOnce": True,
    "dnsTcpTlsHttpsToExactProxyAuthorized": True,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "compileAuthorized": False,
    "packageManagerAuthorized": False,
    "subprocessAuthorized": False,
    "gitOperationAuthorized": False,
    "deviceAuthorized": False,
    "deploymentAuthorized": False,
    "productRuntimeNetworkAuthorized": False,
    "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized": False,
    "publicationAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "accountRequired": False,
    "ownerRequired": False,
    "sshRequired": False,
    "gpgRequired": False,
    "externalAuthenticationRequired": False,
    "authenticationRequired": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "signatureRequired": False,
    "tokenRequired": False,
    "cookieRequired": False,
    "clientCertificateRequired": False,
    "userActionRequired": False,
}
EXPECTED_FILESYSTEM_AUTHORITY = {
    "claimWriteAuthorized": True,
    "ownerOnlyStagingWriteAuthorized": True,
    "verifiedModAndZipWriteAuthorized": True,
    "receiptFailureAndManifestWriteAuthorized": True,
    "acquisitionArtifactPublicationAuthorized": True,
    "atomicNoReplacePublicationRequired": True,
    "manifestWrittenLast": True,
    "newFileMode": "0600",
    "newDirectoryMode": "0700",
    "sourceExtractionAuthorized": False,
    "otherRepositoryWritesAuthorized": False,
}
WAVE4_RUNNER_PATH = Path(__file__).with_name(
    "acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)
EXPECTED_WAVE4_RUNNER_RAW = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)
MAXIMUM_TOOL_BYTES = 8 * 1024 * 1024
CTL_KERN = 1
KERN_PROCARGS2 = 49
MAX_KERNEL_ARGV_BYTES = 1 * 1024 * 1024
MAX_KERNEL_ARGC = 64


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


def validate_argument_vector(argv: Sequence[str]) -> None:
    require(
        list(argv) == CHECK.EXACT_RUNNER_ARGV,
        "E_ARGUMENT",
        "cli",
    )


def _parse_kernel_procargs2(raw: bytes) -> tuple[str, list[str]]:
    integer_bytes = ctypes.sizeof(ctypes.c_int)
    require(
        type(raw) is bytes
        and integer_bytes < len(raw) <= MAX_KERNEL_ARGV_BYTES,
        "E_KERNEL_ARGV",
        "cli",
    )
    argc = int.from_bytes(
        raw[:integer_bytes],
        byteorder=sys.byteorder,
        signed=True,
    )
    require(
        0 < argc <= MAX_KERNEL_ARGC,
        "E_KERNEL_ARGV",
        "cli",
    )
    cursor = integer_bytes
    terminator = raw.find(b"\0", cursor)
    require(terminator > cursor, "E_KERNEL_ARGV", "cli")
    try:
        executable = raw[cursor:terminator].decode(
            "utf-8",
            errors="strict",
        )
    except UnicodeDecodeError as error:
        raise AcquisitionError("E_KERNEL_ARGV", "cli") from error
    cursor = terminator + 1
    while cursor < len(raw) and raw[cursor] == 0:
        cursor += 1
    argv: list[str] = []
    for _ in range(argc):
        terminator = raw.find(b"\0", cursor)
        require(terminator > cursor, "E_KERNEL_ARGV", "cli")
        try:
            value = raw[cursor:terminator].decode(
                "utf-8",
                errors="strict",
            )
        except UnicodeDecodeError as error:
            raise AcquisitionError("E_KERNEL_ARGV", "cli") from error
        argv.append(value)
        cursor = terminator + 1
    require(
        executable.startswith("/")
        and all("\0" not in value for value in [executable, *argv]),
        "E_KERNEL_ARGV",
        "cli",
    )
    return executable, argv


def _read_kernel_invocation() -> tuple[str, list[str]]:
    require(sys.platform == "darwin", "E_KERNEL_ARGV", "cli")
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        sysctl = libc.sysctl
        sysctl.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        sysctl.restype = ctypes.c_int
        mib = (ctypes.c_int * 3)(
            CTL_KERN,
            KERN_PROCARGS2,
            os.getpid(),
        )
        size = ctypes.c_size_t(0)
        ctypes.set_errno(0)
        if sysctl(
            mib,
            len(mib),
            None,
            ctypes.byref(size),
            None,
            0,
        ) != 0:
            error_number = ctypes.get_errno() or errno.EIO
            raise OSError(error_number, os.strerror(error_number))
        require(
            ctypes.sizeof(ctypes.c_int)
            < size.value <= MAX_KERNEL_ARGV_BYTES,
            "E_KERNEL_ARGV",
            "cli",
        )
        buffer = (ctypes.c_ubyte * size.value)()
        ctypes.set_errno(0)
        if sysctl(
            mib,
            len(mib),
            ctypes.byref(buffer),
            ctypes.byref(size),
            None,
            0,
        ) != 0:
            error_number = ctypes.get_errno() or errno.EIO
            raise OSError(error_number, os.strerror(error_number))
        require(
            ctypes.sizeof(ctypes.c_int)
            < size.value <= len(buffer),
            "E_KERNEL_ARGV",
            "cli",
        )
        return _parse_kernel_procargs2(bytes(buffer[:size.value]))
    except AcquisitionError:
        raise
    except (AttributeError, OSError, TypeError, ValueError) as error:
        raise AcquisitionError("E_KERNEL_ARGV", "cli") from error


def validate_production_invocation() -> None:
    kernel_executable, kernel_argv = _read_kernel_invocation()
    validate_argument_vector(sys.argv[1:])
    require(
        sys.executable == CHECK.INTERPRETER_PATH
        and Path.cwd() == ROOT
        and sys.argv
        == [CHECK.RUNNER_PATH, *CHECK.EXACT_RUNNER_ARGV]
        and __name__ == "__main__"
        and sys.modules.get("__main__") is sys.modules.get(__name__)
        and kernel_executable == CHECK.KERNEL_EXECUTABLE_PATH
        and kernel_argv == CHECK.EXACT_KERNEL_ARGV,
        "E_INVOCATION",
        "cli",
    )


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
    fd = -1
    try:
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGINT},
        )
        try:
            fd = os.open(path, flags)
        finally:
            signal.pthread_sigmask(
                signal.SIG_SETMASK,
                previous_mask,
            )
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
        if fd >= 0:
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
    "wave13_acquisition_permit_v1",
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
        and WAVE4.CHECK.MAX_AGGREGATE_BYTES >= CHECK.MAX_AGGREGATE_BYTES
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


@dataclass(frozen=True)
class ProcessOps:
    getsignal: Callable[[int], Any] = signal.getsignal
    getitimer: Callable[[int], tuple[float, float]] = signal.getitimer
    set_signal: Callable[[int, Any], Any] = signal.signal
    setitimer: Callable[..., tuple[float, float]] = signal.setitimer
    sigpending: Callable[[], set[signal.Signals]] = signal.sigpending
    sigwait: Callable[[set[signal.Signals]], int] = signal.sigwait
    pthread_sigmask: Callable[..., set[signal.Signals]] = (
        signal.pthread_sigmask
    )
    umask: Callable[[int], int] = os.umask
    monotonic: Callable[[], float] = time.monotonic


REAL_PROCESS_OPS = ProcessOps()
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

    def __del__(self) -> None:
        if getattr(self, "fd", -1) >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
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
    exists_observed = False
    fd = -1
    try:
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGINT},
        )
        try:
            try:
                fd = os.open(name, flags, mode, dir_fd=parent_fd)
                created = True
            except FileExistsError:
                exists_observed = True
                raise
        finally:
            signal.pthread_sigmask(
                signal.SIG_SETMASK,
                previous_mask,
            )
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
    except AcquisitionError as error:
        if exists_observed:
            raise AcquisitionError(exists_code, phase) from error
        raise
    except BaseException as error:
        if exists_observed:
            raise AcquisitionError(exists_code, phase) from error
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
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGINT},
        )
        try:
            fd = os.open(
                name,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        finally:
            signal.pthread_sigmask(
                signal.SIG_SETMASK,
                previous_mask,
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


def _open_owned_directory(
    owner: list[int],
    path: str | os.PathLike[str],
    *,
    dir_fd: int | None = None,
) -> int:
    """Defer termination only across local open-to-ownership transfer."""
    previous_mask = signal.pthread_sigmask(
        signal.SIG_BLOCK,
        {signal.SIGALRM, signal.SIGINT},
    )
    fd = -1
    transferred = False
    try:
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC
        )
        if dir_fd is None:
            fd = os.open(path, flags)
        else:
            fd = os.open(path, flags, dir_fd=dir_fd)
        try:
            owner.append(fd)
            transferred = True
        except BaseException:
            try:
                os.close(fd)
            finally:
                fd = -1
            raise
        return fd
    finally:
        if fd >= 0 and not transferred:
            try:
                os.close(fd)
            except OSError:
                pass
        signal.pthread_sigmask(
            signal.SIG_SETMASK,
            previous_mask,
        )


@dataclass(frozen=True)
class ImmutablePhaseLedger:
    """Single-assignment snapshots of committed lower bounds and in-flight work."""

    dispatch_boundary_count: int = 0
    response_committed_count: int = 0
    response_committed_bytes: int = 0
    validation_committed_count: int = 0
    persistence_committed_count: int = 0
    current_resource_ordinal: int | None = None
    current_operation_phase: str | None = None
    additional_completion_uncertain: bool = False

    def _require_idle(self, ordinal: int, expected: int) -> None:
        require(
            type(ordinal) is int
            and ordinal == expected
            and self.current_resource_ordinal is None
            and self.current_operation_phase is None
            and self.additional_completion_uncertain is False
            and 0
            <= self.persistence_committed_count
            <= self.validation_committed_count
            <= self.response_committed_count
            <= self.dispatch_boundary_count,
            "E_LEDGER",
            "operation_ledger",
        )

    def begin_fetch(self, ordinal: int) -> "ImmutablePhaseLedger":
        self._require_idle(ordinal, self.dispatch_boundary_count + 1)
        return replace(
            self,
            dispatch_boundary_count=self.dispatch_boundary_count + 1,
            current_resource_ordinal=ordinal,
            current_operation_phase="fetch_may_have_completed",
            additional_completion_uncertain=True,
        )

    def commit_response(self, raw: bytes) -> "ImmutablePhaseLedger":
        require(
            type(raw) is bytes
            and self.current_resource_ordinal
            == self.response_committed_count + 1
            and self.current_operation_phase == "fetch_may_have_completed"
            and self.additional_completion_uncertain is True,
            "E_LEDGER",
            "response_commit",
        )
        return replace(
            self,
            response_committed_count=self.response_committed_count + 1,
            response_committed_bytes=self.response_committed_bytes + len(raw),
            current_resource_ordinal=None,
            current_operation_phase=None,
            additional_completion_uncertain=False,
        )

    def begin_validation(self, ordinal: int) -> "ImmutablePhaseLedger":
        self._require_idle(ordinal, self.validation_committed_count + 1)
        require(
            self.response_committed_count == ordinal,
            "E_LEDGER",
            "validation_begin",
        )
        return replace(
            self,
            current_resource_ordinal=ordinal,
            current_operation_phase="validation_may_have_completed",
            additional_completion_uncertain=True,
        )

    def commit_validation(self) -> "ImmutablePhaseLedger":
        require(
            self.current_resource_ordinal
            == self.validation_committed_count + 1
            and self.current_operation_phase
            == "validation_may_have_completed"
            and self.additional_completion_uncertain is True,
            "E_LEDGER",
            "validation_commit",
        )
        return replace(
            self,
            validation_committed_count=self.validation_committed_count + 1,
            current_resource_ordinal=None,
            current_operation_phase=None,
            additional_completion_uncertain=False,
        )

    def begin_persistence(self, ordinal: int) -> "ImmutablePhaseLedger":
        self._require_idle(ordinal, self.persistence_committed_count + 1)
        require(
            self.validation_committed_count == ordinal,
            "E_LEDGER",
            "persistence_begin",
        )
        return replace(
            self,
            current_resource_ordinal=ordinal,
            current_operation_phase="persist_may_have_completed",
            additional_completion_uncertain=True,
        )

    def commit_persistence(self) -> "ImmutablePhaseLedger":
        require(
            self.current_resource_ordinal
            == self.persistence_committed_count + 1
            and self.current_operation_phase == "persist_may_have_completed"
            and self.additional_completion_uncertain is True,
            "E_LEDGER",
            "persistence_commit",
        )
        return replace(
            self,
            persistence_committed_count=self.persistence_committed_count + 1,
            current_resource_ordinal=None,
            current_operation_phase=None,
            additional_completion_uncertain=False,
        )

    def committed_fields(self) -> dict[str, int]:
        return {
            "dispatchBoundaryCount": self.dispatch_boundary_count,
            "responseCommittedCount": self.response_committed_count,
            "responseCommittedBytes": self.response_committed_bytes,
            "validationCommittedCount": self.validation_committed_count,
            "persistenceCommittedCount": self.persistence_committed_count,
        }

    def source_acquisition_state(self) -> str:
        if (
            self.response_committed_count == 0
            and self.current_operation_phase == "fetch_may_have_completed"
        ):
            return "unknown_after_dispatch"
        if self.response_committed_count == 0:
            return "none_committed"
        if self.additional_completion_uncertain:
            return "partial_committed_with_additional_completion_uncertain"
        if self.response_committed_count == 8:
            return "all_responses_committed"
        return "partial_committed"

    def failure_fields(self) -> dict[str, Any]:
        return {
            **self.committed_fields(),
            "operationCountSemantics": "committed_lower_bounds",
            "currentResourceOrdinal": self.current_resource_ordinal,
            "currentOperationPhase": self.current_operation_phase,
            "additionalCompletionUncertain":
                self.additional_completion_uncertain,
            "sourceAcquisitionState": self.source_acquisition_state(),
        }

    def success_fields(self, expected_count: int) -> dict[str, Any]:
        require(
            type(expected_count) is int
            and expected_count == 8
            and self.dispatch_boundary_count == expected_count
            and self.response_committed_count == expected_count
            and self.validation_committed_count == expected_count
            and self.persistence_committed_count == expected_count
            and self.current_resource_ordinal is None
            and self.current_operation_phase is None
            and self.additional_completion_uncertain is False,
            "E_LEDGER",
            "success",
        )
        return {
            **self.committed_fields(),
            "operationCountSemantics": "exact_terminal_success",
            "currentResourceOrdinal": None,
            "currentOperationPhase": None,
            "additionalCompletionUncertain": False,
            "sourceAcquisitionState": "all_responses_committed",
        }


class ProcessStateGuard:
    """Install and independently restore process-global deadline state."""

    def __init__(
        self,
        ops: ProcessOps,
        previous_mask: set[signal.Signals],
    ) -> None:
        self.ops = ops
        self.previous_mask = set(previous_mask)
        self.started = ops.monotonic()
        self.previous_handler: Any = None
        self.previous_timer: tuple[float, float] | None = None
        self.previous_umask: int | None = None
        self.handler_mutation_attempted = False
        self.timer_mutation_attempted = False
        self.umask_changed = False
        self.restore_attempted = False
        self.restoring = False
        self.alarm_observed_during_restore = False
        self.restore_errors: tuple[tuple[str, BaseException], ...] = ()

    def observe_alarm_during_restore(self) -> bool:
        if not self.restoring:
            return False
        self.alarm_observed_during_restore = True
        return True

    def install(self, handler: Callable[[int, Any], None]) -> None:
        try:
            self.ops.pthread_sigmask(
                signal.SIG_BLOCK,
                {signal.SIGALRM, signal.SIGINT},
            )
            self.previous_handler = self.ops.getsignal(signal.SIGALRM)
            self.previous_timer = self.ops.getitimer(signal.ITIMER_REAL)
            self.handler_mutation_attempted = True
            self.ops.set_signal(signal.SIGALRM, handler)
            self.timer_mutation_attempted = True
            self.ops.setitimer(
                signal.ITIMER_REAL,
                CHECK.WHOLE_ATTEMPT_DEADLINE_MS / 1000,
            )
            self.previous_umask = self.ops.umask(0o077)
            self.umask_changed = True
            self.ops.pthread_sigmask(
                signal.SIG_SETMASK,
                self.previous_mask,
            )
        except BaseException as error:
            cleanup_errors = self.restore()
            if cleanup_errors:
                raise AcquisitionError(
                    "E_PROCESS_STATE_RESTORE_UNCERTAIN",
                    "setup_restore",
                ) from error
            raise

    def restore(self) -> tuple[tuple[str, BaseException], ...]:
        if self.restore_attempted:
            return self.restore_errors
        self.restore_attempted = True
        self.restoring = True
        errors: list[tuple[str, BaseException]] = []

        def attempt(name: str, operation: Callable[[], Any]) -> bool:
            try:
                operation()
                return True
            except BaseException as error:
                errors.append((name, error))
                return False

        mask_blocked = attempt(
            "mask_for_restore",
            lambda: self.ops.pthread_sigmask(
                signal.SIG_BLOCK,
                {signal.SIGALRM, signal.SIGINT},
            ),
        )
        if not mask_blocked:
            mask_blocked = attempt(
                "mask_for_restore_retry",
                lambda: self.ops.pthread_sigmask(
                    signal.SIG_BLOCK,
                    {signal.SIGALRM, signal.SIGINT},
                ),
            )

        timer_cancelled = not self.timer_mutation_attempted
        if self.timer_mutation_attempted:
            timer_cancelled = attempt(
                "cancel_installed_timer",
                lambda: self.ops.setitimer(signal.ITIMER_REAL, 0),
            )
            if not timer_cancelled:
                timer_cancelled = attempt(
                    "cancel_installed_timer_retry",
                    lambda: self.ops.setitimer(signal.ITIMER_REAL, 0),
                )

        alarm_state_mutated = (
            self.handler_mutation_attempted
            or self.timer_mutation_attempted
        )
        pending_drained = not alarm_state_mutated
        if mask_blocked and timer_cancelled and alarm_state_mutated:
            try:
                while signal.SIGALRM in self.ops.sigpending():
                    waited = self.ops.sigwait({signal.SIGALRM})
                    if waited != signal.SIGALRM:
                        raise AcquisitionError(
                            "E_SIGNAL_MASK",
                            "process_state_restore",
                        )
                    self.alarm_observed_during_restore = True
                pending_drained = True
            except BaseException as error:
                errors.append(("drain_pending_alarm", error))
                pending_drained = False

        safe_alarm_restore = (
            mask_blocked
            and timer_cancelled
            and pending_drained
        )
        prior_handler_restored = not self.handler_mutation_attempted
        if (
            safe_alarm_restore
            and self.handler_mutation_attempted
            and self.previous_handler is not None
        ):
            prior_handler_restored = attempt(
                "restore_handler",
                lambda: self.ops.set_signal(
                    signal.SIGALRM,
                    self.previous_handler,
                )
            )

        prior_timer_restored = not self.timer_mutation_attempted
        if (
            safe_alarm_restore
            and prior_handler_restored
            and self.timer_mutation_attempted
            and self.previous_timer is not None
        ):
            def restore_previous_timer() -> None:
                old_delay, old_interval = self.previous_timer or (0, 0)
                elapsed = self.ops.monotonic() - self.started
                restored_delay = (
                    max(0.000001, old_delay - elapsed)
                    if old_delay > 0
                    else 0
                )
                self.ops.setitimer(
                    signal.ITIMER_REAL,
                    restored_delay,
                    old_interval,
                )

            prior_timer_restored = attempt(
                "restore_previous_timer",
                restore_previous_timer,
            )
        if self.umask_changed and self.previous_umask is not None:
            attempt(
                "restore_umask",
                lambda: self.ops.umask(self.previous_umask),
            )
        if safe_alarm_restore and prior_handler_restored:
            attempt(
                "restore_signal_mask",
                lambda: self.ops.pthread_sigmask(
                    signal.SIG_SETMASK,
                    self.previous_mask,
                ),
            )
        else:
            errors.append(
                (
                    "alarm_state_contained",
                    AcquisitionError(
                        "E_PROCESS_STATE_RESTORE_UNCERTAIN",
                        "process_state_restore",
                    ),
                )
            )
            attempt(
                "contain_signal_mask",
                lambda: self.ops.pthread_sigmask(
                    signal.SIG_BLOCK,
                    {signal.SIGALRM},
                ),
            )
        if not prior_timer_restored:
            errors.append(
                (
                    "prior_timer_not_restored",
                    AcquisitionError(
                        "E_PROCESS_STATE_RESTORE_UNCERTAIN",
                        "process_state_restore",
                    ),
                )
            )
        if self.alarm_observed_during_restore:
            errors.append(
                (
                    "alarm_during_restore",
                    AcquisitionError(
                        "E_DEADLINE",
                        "process_state_restore",
                    ),
                )
            )
        self.restoring = False
        self.restore_errors = tuple(errors)
        return self.restore_errors


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
        self.owned_directory_fds: list[int] = []
        self.root_fd = -1
        self.root_initial: os.stat_result | None = None
        self.directory_steps: list[
            tuple[int, os.stat_result, int, str]
        ] = []
        self.dependency_fd = -1
        self.docs_fd = -1
        self.dependency_initial: os.stat_result | None = None
        self.docs_initial: os.stat_result | None = None
        self.claim: HeldEntry | None = None
        self.claim_creation_attempted = False
        self.claim_creation_may_have_consumed = False
        self.claim_known_consumed = False
        self.staging: HeldEntry | None = None
        self.accepted: HeldEntry | None = None
        self.resources: dict[str, HeldEntry] = {}
        self.evidence: HeldEntry | None = None
        self.receipt: HeldEntry | None = None
        self.manifest: HeldEntry | None = None
        self.failure: HeldEntry | None = None
        self.published = False

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_NAMESPACE",
            "preflight",
        )

    def _open_relative_directory(self, relative: str) -> int:
        require(
            self.root_fd >= 0
            and type(relative) is str
            and not relative.startswith("/"),
            "E_NAMESPACE",
            "preflight",
        )
        current = self.root_fd
        try:
            for component in relative.split("/"):
                _leaf_name(component, "preflight")
                child = _open_owned_directory(
                    self.owned_directory_fds,
                    component,
                    dir_fd=current,
                )
                info = os.fstat(child)
                self._validate_directory(info)
                self.directory_steps.append(
                    (child, info, current, component)
                )
                current = child
            return current
        except AcquisitionError:
            raise
        except OSError as error:
            raise AcquisitionError(
                "E_NAMESPACE",
                "preflight",
            ) from error

    def __enter__(self) -> "ExecutionNamespace":
        try:
            self.root_fd = _open_owned_directory(
                self.owned_directory_fds,
                self.root,
            )
            self.root_initial = os.fstat(self.root_fd)
            self._validate_directory(self.root_initial)
            self.dependency_fd = self._open_relative_directory(
                CHECK.DEPENDENCY_ROOT
            )
            self.dependency_initial = os.fstat(self.dependency_fd)
            self.docs_fd = self._open_relative_directory(
                CHECK.BASE
            )
            self.docs_initial = os.fstat(self.docs_fd)
            self.barrier(ExecutionState.PRECLAIM)
            return self
        except OSError as error:
            self.close()
            raise AcquisitionError(
                "E_NAMESPACE",
                "preflight",
            ) from error
        except BaseException:
            self.close()
            raise

    def _namespace_barrier(self) -> None:
        require(
            self.root_fd >= 0 and self.root_initial is not None,
            "E_NAMESPACE",
            "barrier",
        )
        try:
            current_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root, follow_symlinks=False)
            require(
                _directory_anchor(current_root)
                == _directory_anchor(self.root_initial)
                == _directory_anchor(named_root),
                "E_NAMESPACE",
                "barrier",
            )
            for fd, initial, parent_fd, name in self.directory_steps:
                held = os.fstat(fd)
                named = os.stat(
                    name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                require(
                    _directory_anchor(held)
                    == _directory_anchor(initial)
                    == _directory_anchor(named),
                    "E_NAMESPACE",
                    "barrier",
                )
        except OSError as error:
            raise AcquisitionError("E_NAMESPACE", "barrier") from error

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
        self.claim_creation_attempted = True
        self.claim_creation_may_have_consumed = True
        try:
            created_claim = create_claim(
                self.dependency_fd,
                Path(CHECK.CLAIM_PATH).name,
                payload,
                ops=self.ops,
            )
        except AcquisitionError as error:
            if error.code in {"E_CLAIM_NOT_CREATED", "E_CONSUMED"}:
                self.claim_creation_may_have_consumed = False
            if error.code == "E_CONSUMED":
                self.claim_known_consumed = True
            raise
        try:
            self._fire("after_claim_create_returned_before_assignment")
        except BaseException:
            try:
                created_claim.close()
            except BaseException as close_error:
                raise AcquisitionError(
                    "E_CLAIM_STATE_UNCERTAIN",
                    "claim",
                ) from close_error
            raise
        self.claim = created_claim
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
        self._namespace_barrier()
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
                len(self.resources) == 8 and self.evidence is not None,
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
        errors: list[BaseException] = []
        previous_mask: set[signal.Signals] | None = None
        try:
            previous_mask = signal.pthread_sigmask(
                signal.SIG_BLOCK,
                {signal.SIGALRM, signal.SIGINT},
            )
        except BaseException as error:
            errors.append(error)

        def close_fd(fd: int, mark_closed: Callable[[], None]) -> None:
            if fd < 0:
                return
            try:
                os.close(fd)
                mark_closed()
                return
            except OSError as error:
                if error.errno == errno.EBADF:
                    mark_closed()
                    return
                errors.append(error)
            except BaseException as error:
                errors.append(error)
            try:
                os.fstat(fd)
            except OSError as error:
                if error.errno == errno.EBADF:
                    mark_closed()
                    return
                errors.append(error)
            except BaseException as error:
                errors.append(error)
            try:
                os.close(fd)
                mark_closed()
            except OSError as error:
                if error.errno == errno.EBADF:
                    mark_closed()
                else:
                    errors.append(error)
            except BaseException as error:
                errors.append(error)

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
                close_fd(
                    entry.fd,
                    lambda entry=entry: setattr(entry, "fd", -1),
                )
        self.resources.clear()
        seen: set[int] = set()
        for fd in reversed(self.owned_directory_fds):
            if fd < 0 or fd in seen:
                continue
            seen.add(fd)
            close_fd(fd, lambda: None)
        self.owned_directory_fds.clear()
        self.directory_steps.clear()
        self.root_fd = -1
        self.root_initial = None
        self.dependency_fd = -1
        self.docs_fd = -1
        if previous_mask is not None:
            try:
                signal.pthread_sigmask(
                    signal.SIG_SETMASK,
                    previous_mask,
                )
            except BaseException as error:
                errors.append(error)
        if errors:
            raise errors[0]

    def __exit__(self, *_: object) -> None:
        self.close()


def _reject_consumed_claim(root: Path = ROOT) -> None:
    current = -1
    opened: list[int] = []
    try:
        current = _open_owned_directory(
            opened,
            root,
        )
        for component in CHECK.DEPENDENCY_ROOT.split("/"):
            current = _open_owned_directory(
                opened,
                component,
                dir_fd=current,
            )
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


def _authority_contract_is_exact(permit: Mapping[str, Any]) -> bool:
    authority = permit.get("authority")
    filesystem = permit.get("filesystemAuthority")

    def exact(
        actual: object,
        expected: Mapping[str, object],
    ) -> bool:
        return (
            type(actual) is dict
            and set(actual) == set(expected)
            and all(
                (
                    actual[key] is expected_value
                    if type(expected_value) is bool
                    else type(actual[key]) is type(expected_value)
                    and actual[key] == expected_value
                )
                for key, expected_value in expected.items()
            )
        )

    return (
        exact(authority, EXPECTED_AUTHORITY)
        and exact(filesystem, EXPECTED_FILESYSTEM_AUTHORITY)
    )


def preflight() -> tuple[dict[str, Any], dict[str, Any]]:
    _reject_consumed_claim()
    values, summary = CHECK.evaluate(True)
    permit = values["permit"]
    require(
        summary["validationPassed"] is True
        and summary["status"] == "authorized_not_consumed"
        and summary["requestCount"] == 8
        and summary["claimExists"] is False
        and summary["permitConsumed"] is False
        and summary["runnerInvoked"] is False
        and summary["networkUsed"] is False
        and summary["fileWriteCount"] == 0
        and summary["externalAuthenticationRequired"] is False
        and permit["status"] == "authorized_not_consumed"
        and permit["structurePreparationOnly"] is False
        and permit["executionReady"] is True
        and _authority_contract_is_exact(permit)
        and permit["requestContract"]["resourcesCanonicalSha256"]
        == EXPECTED_WAVE13_RESOURCE_CONTRACT_SHA256
        and permit["authority"][
            "wave13PublicProxy8GetAcquisitionAuthorizedOnce"
        ]
        is True
        and permit["authority"][
            "dnsTcpTlsHttpsToExactProxyAuthorized"
        ]
        is True
        and permit["authority"][
            "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized"
        ]
        is False
        and permit["authority"]["externalAuthenticationRequired"] is False
        and permit["authority"]["repositoryOwnerIdentityProofRequired"]
        is False
        and permit["authority"]["sourceExtractionAuthorized"] is False
        and permit["authority"]["publicationAuthorized"] is False
        and permit["filesystemAuthority"][
            "acquisitionArtifactPublicationAuthorized"
        ]
        is True
        and permit["filesystemAuthority"][
            "otherRepositoryWritesAuthorized"
        ]
        is False
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
        and type(permit["requestContract"]["requestCount"]) is int
        and permit["requestContract"]["requestCount"] == 8
        and len(rows) == 8
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
            and re.fullmatch(r"v[0-9][a-z0-9.+_-]*", version) is not None,
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
            and type(row["requestOrdinal"]) is int
            and row["requestOrdinal"] == ordinal
            and type(row["tupleOrder"]) is int
            and row["tupleOrder"] == tuple_order
            and row["tupleDigestSha256"] == digest
            and row["tupleId"] == f"wave13-{tuple_order:03d}-{digest[:12]}"
            and row["kind"] == kind
            and row["method"] == "GET"
            and row["host"] == CHECK.PROXY_HOST
            and type(row["port"]) is int
            and row["port"] == 443
            and row["path"] == path
            and row["url"] == f"https://{CHECK.PROXY_HOST}{path}"
            and type(row["maximumResponseBodyBytes"]) is int
            and row["maximumResponseBodyBytes"] == maximum
            and row["acceptedFileName"]
            == f"{tuple_order:03d}-{digest[:20]}.{kind}",
            "E_RESOURCES",
            "preflight",
        )
        _primitive_call(VALIDATION.decode_h1, row["expectedH1"], "preflight")
        result.append(row)
    for index in range(0, 8, 2):
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
        len({row["acceptedFileName"] for row in result}) == 8
        and len({row["url"] for row in result}) == 8
        and all(
            row["selectedByGraphAlgorithm"] is False
            for row in result
        ),
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
        and expected_count == 8
        and len(rows) == 8
        and sha256(canonical_bytes(rows))
        == permit["requestContract"]["resourcesCanonicalSha256"]
        and permit["structurePreparationOnly"] is False
        and permit["executionReady"] is True
        and _authority_contract_is_exact(permit)
        and permit["authority"][
            "wave13PublicProxy8GetAcquisitionAuthorizedOnce"
        ]
        is True
        and permit["authority"][
            "dnsTcpTlsHttpsToExactProxyAuthorized"
        ]
        is True
        and permit["authority"][
            "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized"
        ]
        is False
        and permit["authority"]["publicationAuthorized"] is False
        and permit["authority"]["externalAuthenticationRequired"] is False
        and permit["authority"]["repositoryOwnerIdentityProofRequired"] is False
        and permit["authority"]["accountRequired"] is False
        and permit["authority"]["ownerRequired"] is False
        and permit["authority"]["sshRequired"] is False
        and permit["authority"]["gpgRequired"] is False
        and permit["authority"]["authenticationRequired"] is False
        and permit["authority"]["passwordRequired"] is False
        and permit["authority"]["privateKeyRequired"] is False
        and permit["authority"]["signatureRequired"] is False
        and permit["authority"]["tokenRequired"] is False
        and permit["authority"]["cookieRequired"] is False
        and permit["authority"]["clientCertificateRequired"] is False
        and permit["authority"]["userActionRequired"] is False
        and permit["filesystemAuthority"][
            "acquisitionArtifactPublicationAuthorized"
        ]
        is True
        and permit["filesystemAuthority"][
            "otherRepositoryWritesAuthorized"
        ]
        is False,
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
        "documentType": "aetherlink.wave13-source-acquisition-claim",
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
    ledger = ImmutablePhaseLedger()
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
            request_deadline = min(
                deadline,
                time.monotonic()
                + CHECK.PER_REQUEST_DEADLINE_MS / 1000,
            )
            ledger = ledger.begin_fetch(ordinal)
            raw = fetch(resource, request_deadline)
            ledger = ledger.commit_response(raw)
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
                type(raw) is bytes
                and 0 < len(raw) <= resource["maximumResponseBodyBytes"],
                "E_RESPONSE_SIZE",
                f"request_{ordinal:02d}",
            )
            require(
                aggregate_mod <= CHECK.MAX_AGGREGATE_MOD_BYTES,
                "E_RESPONSE_SIZE",
                "aggregate_mod",
            )
            require(
                aggregate_zip <= CHECK.MAX_AGGREGATE_ZIP_BYTES,
                "E_RESPONSE_SIZE",
                "aggregate_zip",
            )
            require(
                aggregate <= CHECK.MAX_AGGREGATE_BYTES,
                "E_RESPONSE_SIZE",
                "aggregate_total",
            )
            ledger = ledger.begin_validation(ordinal)
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
            ledger = ledger.commit_validation()
            ledger = ledger.begin_persistence(ordinal)
            namespace.persist_resource(
                resource["acceptedFileName"],
                raw,
            )
            ledger = ledger.commit_persistence()
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
        success_operation_fields = ledger.success_fields(expected_count)
        evidence_payload = {
            "documentType": "aetherlink.wave13-source-acquisition-evidence",
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
            "documentType": "aetherlink.wave13-source-acquisition-receipt",
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
            **success_operation_fields,
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
            "documentType": "aetherlink.wave13-source-acquisition-manifest",
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
            "documentType": "aetherlink.wave13-source-acquisition-failure",
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
            **ledger.failure_fields(),
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


def execute(
    fetch: Fetch = direct_fetch,
    *,
    process_ops: ProcessOps = REAL_PROCESS_OPS,
) -> dict[str, Any]:
    validate_production_invocation()
    require(
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "pthread_sigmask"),
        "E_SIGNAL_THREAD",
        "setup",
    )
    try:
        previous_mask = process_ops.pthread_sigmask(
            signal.SIG_BLOCK,
            set(),
        )
    except OSError as error:
        raise AcquisitionError(
            "E_SIGNAL_MASK",
            "caller_mask",
        ) from error
    require(
        signal.SIGALRM not in previous_mask,
        "E_SIGNAL_MASK",
        "caller_mask",
    )
    values, _ = preflight()

    def alarm_handler(_signum: int, _frame: Any) -> None:
        if guard.observe_alarm_during_restore():
            return
        raise AcquisitionError("E_DEADLINE", "whole_attempt")

    guard = ProcessStateGuard(process_ops, previous_mask)
    guard.install(alarm_handler)
    result_marker = object()
    result: object = result_marker
    body_error: BaseException | None = None
    namespace_object: ExecutionNamespace | None = None
    try:
        with CHECK.AuthorityFiles(ROOT, values["permit"]) as authority:
            namespace_object = ExecutionNamespace(ROOT)
            with namespace_object as namespace:
                def checkpoint(
                    _event: str,
                    state: ExecutionState,
                ) -> None:
                    authority.barrier()
                    namespace.barrier(state)
                    authority.barrier()

                result = _attempt(
                    fetch,
                    values,
                    namespace,
                    checkpoint=checkpoint,
                )
    except BaseException as error:
        body_error = error

    consumed_possible = (
        result is not result_marker
        or (
            namespace_object is not None
            and (
                namespace_object.claim is not None
                or (
                    namespace_object.claim_creation_attempted
                    and namespace_object.claim_creation_may_have_consumed
                )
                or namespace_object.published
                or namespace_object.receipt is not None
                or namespace_object.manifest is not None
                or namespace_object.failure is not None
            )
        )
        or (
            isinstance(body_error, AcquisitionError)
            and (
                body_error.consumed
                or body_error.code in {
                    "E_CLAIM_STATE_UNCERTAIN",
                    "E_FAILURE_PUBLICATION_UNCERTAIN",
                    "E_POST_PUBLISH_UNCERTAIN",
                }
            )
        )
    )
    known_consumed = (
        namespace_object is not None
        and namespace_object.claim_known_consumed
    )
    body_is_known_consumed = (
        isinstance(body_error, AcquisitionError)
        and body_error.code == "E_CONSUMED"
    )
    cleanup_errors = guard.restore()
    cleanup_consumed = (
        consumed_possible
        or known_consumed
        or body_is_known_consumed
    )
    if cleanup_errors:
        cause = body_error or cleanup_errors[0][1]
        raise AcquisitionError(
            "E_PROCESS_STATE_RESTORE_UNCERTAIN",
            "process_state_restore",
            consumed=cleanup_consumed,
        ) from cause
    if body_error is not None:
        if (
            (
                consumed_possible
                or (known_consumed and not body_is_known_consumed)
            )
            and not (
                isinstance(body_error, AcquisitionError)
                and body_error.consumed
            )
        ):
            raise AcquisitionError(
                "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
                "terminal_teardown",
                consumed=True,
            ) from body_error
        raise body_error
    require(
        result is not result_marker and type(result) is dict,
        "E_INTERNAL",
        "runner",
    )
    return result


def validate_execution_context() -> dict[str, Any]:
    values, summary = preflight()
    with CHECK.AuthorityFiles(ROOT, values["permit"]) as authority:
        with ExecutionNamespace(ROOT) as namespace:
            authority.barrier()
            namespace.barrier(ExecutionState.PRECLAIM)
            authority.barrier()
    return {
        "documentType":
            "aetherlink.wave13-source-acquisition-execution-context-check",
        "schemaVersion": "1.0",
        "status": summary["status"],
        "validationPassed": True,
        "requestCount": summary["requestCount"],
        "claimExists": False,
        "permitConsumed": False,
        "runnerInvoked": False,
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
        "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
        "E_FAILURE_PUBLICATION_UNCERTAIN",
        "E_POST_PUBLISH_UNCERTAIN",
    }:
        status = "consumed_terminal_state_uncertain"
    elif (
        error.code == "E_PROCESS_STATE_RESTORE_UNCERTAIN"
        and error.consumed
    ):
        status = "consumed_terminal_state_uncertain"
    elif error.consumed:
        status = "consumed_failure_no_retry"
    else:
        status = "failed_closed"
    return {
        "documentType": "aetherlink.wave13-source-acquisition-error",
        "schemaVersion": "1.0",
        "status": status,
        "failureCode": error.code,
        "failurePhase": error.phase,
        "processStateRestorationUncertain":
            error.code == "E_PROCESS_STATE_RESTORE_UNCERTAIN",
        "retryAllowed": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main() -> int:
    try:
        arguments = list(sys.argv[1:])
        validate_argument_vector(arguments)
        validate_production_invocation()
        parser = Parser(add_help=False, allow_abbrev=False)
        parser.add_argument("--execute", action="store_true")
        args = parser.parse_args(arguments)
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
