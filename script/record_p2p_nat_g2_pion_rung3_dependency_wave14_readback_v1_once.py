#!/usr/bin/env python3
"""Record one independent offline readback of the Wave14 v1 acquisition."""

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
    raise RuntimeError("Wave14 readback recorder requires `python3 -I -B -S`")

import argparse
import base64
import binascii
import ctypes
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import struct
import types
from typing import Any, Callable, Mapping, Sequence
import unicodedata
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", None)
if O_NOFOLLOW is None:
    raise RuntimeError("Wave14 readback recorder requires O_NOFOLLOW")
READBACK_CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave14_"
    "readback_execution_permit_v1.py"
)
EXPECTED_READBACK_CHECKER_RAW = "d7956fbef75adaa4e6609896d04f871668923392f26af2d33e54c113007d754b"
MAXIMUM_CHECKER_BYTES = 8 * 1024 * 1024
RENAME_EXCL = 0x00000004
ZIP_LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
ZIP_CENTRAL_HEADER = struct.Struct("<4s6H3L5H2L")
ZIP_EOCD = struct.Struct("<4s4H2LH")
ZIP_DATA_DESCRIPTOR = struct.Struct("<III")
ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE = struct.Struct("<IIII")
ZIP_LOCAL_SIGNATURE = 0x04034B50
ZIP_CENTRAL_SIGNATURE = b"PK\x01\x02"
ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
ZIP_DATA_DESCRIPTOR_SIGNATURE = 0x08074B50
ALLOWED_ZIP_FLAGS = 0x0008 | 0x0800
MAX_MOD_BYTES = 1 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_AGGREGATE_MOD_BYTES = 4 * 1024 * 1024
MAX_AGGREGATE_ZIP_BYTES = 64 * 1024 * 1024
MAX_AGGREGATE_BYTES = 68 * 1024 * 1024
MAX_ZIP_FILES = 20_000
MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP = 128 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL = 512 * 1024 * 1024
MAX_ZIP_FILES_ACROSS_ALL = 80_000
MAX_ZIP_FILE_BYTES = 128 * 1024 * 1024
MAX_ZIP_NAME_BYTES = 1_024
EXPECTED_PREFLIGHT_AUTHORITY = {
    "offlineReadbackAuthorizedOnce": True,
    "readbackClaimWriteAuthorized": True,
    "readbackReceiptWriteAuthorized": True,
    "readbackManifestWriteAuthorized": True,
    "sameDirectoryTemporaryPublicationAuthorized": True,
    "failedTemporaryCleanupAuthorized": True,
    "otherRepositoryWritesAuthorized": False,
    "frozenInputWritesAuthorized": False,
    "networkAuthorized": False,
    "dnsAuthorized": False,
    "socketAuthorized": False,
    "proxyAuthorized": False,
    "authenticationRequired": False,
    "credentialRequired": False,
    "externalAuthenticationRequired": False,
    "repositoryOwnerIdentityProofRequired": False,
    "accountRequired": False,
    "ownerRequired": False,
    "sshRequired": False,
    "gpgRequired": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "signatureRequired": False,
    "tokenRequired": False,
    "cookieRequired": False,
    "clientCertificateRequired": False,
    "sourceAcquisitionAuthorized": False,
    "source" "ExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "compileAuthorized": False,
    "packageManagerAuthorized": False,
    "sub" "processAuthorized": False,
    "gitOperationAuthorized": False,
    "deviceAuthorized": False,
    "deploymentAuthorized": False,
    "userActionRequired": False,
}


class ReadbackError(RuntimeError):
    def __init__(
        self,
        code: str,
        phase: str,
        *,
        consumed: bool = False,
        uncertain: bool = False,
    ) -> None:
        super().__init__(f"{code}:{phase}")
        self.code = code
        self.phase = phase
        self.consumed = consumed
        self.uncertain = uncertain


def require(value: bool, code: str, phase: str) -> None:
    if not value:
        raise ReadbackError(code, phase)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def has_portable_prefix(
    names: Sequence[str],
    prefixes: Sequence[str],
) -> bool:
    portable_prefixes = [portable_name(prefix) for prefix in prefixes]
    return any(
        portable_name(name).startswith(prefix)
        for name in names
        for prefix in portable_prefixes
    )


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    require("contentBinding" not in payload, "E_CONTENT", "json")
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def strict_json(raw: bytes, phase: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON", phase)
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(
                ReadbackError("E_JSON", phase)
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                ReadbackError("E_JSON", phase)
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReadbackError("E_JSON", phase) from error
    require(type(value) is dict and raw == canonical_bytes(value), "E_CANONICAL", phase)
    return value


def verify_content_binding(value: Mapping[str, Any], phase: str) -> None:
    binding = value.get("contentBinding")
    require(type(binding) is dict, "E_CONTENT", phase)
    unbound = dict(value)
    del unbound["contentBinding"]
    scope = {
        "decision": "decision_without_contentBinding",
        "permit": "permit_without_contentBinding",
    }.get(phase)
    require(
        binding
        == {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_ascii_escaped_sorted_keys_compact_single_lf"
            ),
            "scope": scope,
            "sha256": sha256(canonical_bytes(unbound)),
        }
        and scope is not None,
        "E_CONTENT",
        phase,
    )


def _stable_fields(info: os.stat_result) -> tuple[Any, ...]:
    return tuple(
        getattr(info, name)
        for name in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_gid",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
    )


def _read_fd(fd: int, size: int, phase: str) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.read(fd, min(65_536, remaining))
        require(bool(chunk), "E_READ", phase)
        chunks.append(chunk)
        remaining -= len(chunk)
    require(not os.read(fd, 1), "E_READ", phase)
    return b"".join(chunks)


def _open_to_owner(
    owner: list[int],
    opener: Callable[[], int],
    on_opened: Callable[[int], None] | None = None,
) -> int:
    """Defer SIGALRM/SIGINT only across local open-to-owner transfer."""
    previous_mask = signal.pthread_sigmask(
        signal.SIG_BLOCK,
        {signal.SIGALRM, signal.SIGINT},
    )
    fd = -1
    transferred = False
    primary_error: BaseException | None = None
    try:
        try:
            fd = opener()
            if on_opened is not None:
                on_opened(fd)
            owner.append(fd)
            transferred = True
        except BaseException as error:
            primary_error = error
        if fd >= 0 and not transferred:
            try:
                while fd in owner:
                    owner.remove(fd)
                os.close(fd)
            except BaseException as error:
                if primary_error is None:
                    primary_error = error
            fd = -1
    except BaseException as error:
        primary_error = error
    restore_error: BaseException | None = None
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    except BaseException as error:
        restore_error = error
    if primary_error is not None:
        if restore_error is not None:
            raise primary_error from restore_error
        raise primary_error
    if restore_error is not None:
        raise restore_error
    return fd


def _remove_owned_fd(owner: list[int], fd: int) -> None:
    while fd in owner:
        owner.remove(fd)


def _attempt_close_owned_fd(
    owner: list[int],
    fd: int,
) -> BaseException | None:
    """Retry only a reported close failure in this single-threaded recorder."""
    if fd not in owner:
        return None
    first_error: BaseException | None = None
    for _ in range(2):
        try:
            os.close(fd)
        except OSError as error:
            if error.errno == errno.EBADF:
                _remove_owned_fd(owner, fd)
                return None
            if first_error is None:
                first_error = error
        except BaseException as error:
            if first_error is None:
                first_error = error
        else:
            _remove_owned_fd(owner, fd)
            return None
        try:
            os.fstat(fd)
        except OSError as error:
            if error.errno == errno.EBADF:
                _remove_owned_fd(owner, fd)
                return None
            if first_error is None:
                first_error = error
        except BaseException as error:
            if first_error is None:
                first_error = error
        else:
            continue
    return first_error or OSError(
        errno.EIO,
        "file descriptor closure could not be verified",
    )


def _close_owned_members(owner: list[int], members: Sequence[int]) -> None:
    """Attempt each selected FD and retain any observably open ownership."""
    errors: list[BaseException] = []
    previous_mask: set[signal.Signals] | None = None
    try:
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGINT},
        )
    except BaseException as error:
        errors.append(error)
    seen: set[int] = set()
    for fd in members:
        if fd < 0 or fd in seen:
            continue
        seen.add(fd)
        error = _attempt_close_owned_fd(owner, fd)
        if error is not None:
            errors.append(error)
    if previous_mask is not None:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        except BaseException as error:
            errors.append(error)
    if errors:
        raise errors[0]


def _adopt_owned_fd(owner: list[int], fd: int) -> None:
    previous_mask = signal.pthread_sigmask(
        signal.SIG_BLOCK,
        {signal.SIGALRM, signal.SIGINT},
    )
    try:
        require(fd >= 0 and fd not in owner, "E_FD_OWNER", "ownership")
        owner.append(fd)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def _close_owned_fd(owner: list[int], fd: int) -> None:
    _close_owned_members(owner, (fd,))


def _close_owned_fds(owner: list[int]) -> None:
    """Attempt every registered FD before restoring the caller's mask."""
    _close_owned_members(owner, tuple(reversed(tuple(owner))))


class _RestrictedUmask:
    """Install and restore a process umask with an armed outer guard."""

    def __init__(self, value: int) -> None:
        self.value = value
        self.previous: int | None = None
        self.active = False

    def activate(self) -> None:
        require(not self.active, "E_UMASK", "umask")
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGINT},
        )
        try:
            self.previous = os.umask(self.value)
            self.active = True
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)

    def restore(self) -> None:
        if not self.active:
            return
        errors: list[BaseException] = []
        previous_mask: set[signal.Signals] | None = None
        try:
            previous_mask = signal.pthread_sigmask(
                signal.SIG_BLOCK,
                {signal.SIGALRM, signal.SIGINT},
            )
        except BaseException as error:
            errors.append(error)
        try:
            require(self.previous is not None, "E_UMASK", "umask")
            os.umask(self.previous)
            self.active = False
        except BaseException as error:
            errors.append(error)
        if previous_mask is not None:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            except BaseException as error:
                errors.append(error)
        if errors:
            raise errors[0]


def load_readback_checker() -> types.ModuleType:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= O_NOFOLLOW
    owned: list[int] = []
    fd = -1
    try:
        fd = _open_to_owner(
            owned,
            lambda: os.open(READBACK_CHECKER_PATH, flags),
        )
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_CHECKER_BYTES,
            "E_CHECKER",
            "bootstrap",
        )
        raw = _read_fd(fd, before.st_size, "bootstrap")
        require(
            _stable_fields(os.fstat(fd)) == _stable_fields(before)
            and sha256(raw) == EXPECTED_READBACK_CHECKER_RAW,
            "E_CHECKER",
            "bootstrap",
        )
    finally:
        _close_owned_fds(owned)
    module = types.ModuleType("wave14_acquisition_readback_permit_v1")
    module.__file__ = str(READBACK_CHECKER_PATH)
    module.__package__ = ""
    exec(compile(raw, str(READBACK_CHECKER_PATH), "exec"), module.__dict__)
    return module


PERMIT = load_readback_checker()


def _safe_relative(path: str, phase: str) -> list[str]:
    parts = path.split("/")
    require(
        type(path) is str
        and path
        and not path.startswith("/")
        and all(part not in {"", ".", ".."} for part in parts),
        "E_PATH",
        phase,
    )
    return parts


RetainedComponent = tuple[str, int, os.stat_result, int, str]


def _directory_component_identity(info: os.stat_result) -> tuple[Any, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
    )


def _open_directory_beneath(
    root_fd: int,
    path: str,
    phase: str,
    owner: list[int],
    retained_components: list[RetainedComponent] | None = None,
) -> int:
    current = root_fd
    prefix: list[str] = []
    for component in _safe_relative(path, phase):
        prefix.append(component)
        parent = current
        following = _open_to_owner(
            owner,
            lambda component=component, parent=parent: os.open(
                component,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NONBLOCK
                | os.O_CLOEXEC
                | O_NOFOLLOW,
                dir_fd=parent,
            ),
        )
        try:
            info = os.fstat(following)
            require(
                stat.S_ISDIR(info.st_mode)
                and info.st_uid in {0, os.geteuid()}
                and stat.S_IMODE(info.st_mode) & 0o022 == 0,
                "E_PATH",
                phase,
            )
            if retained_components is not None:
                retained_components.append(
                    (
                        "/".join(prefix),
                        following,
                        info,
                        parent,
                        component,
                    )
                )
        except BaseException:
            _close_owned_fd(owner, following)
            raise
        current = following
    return current


def _open_file_beneath(
    root_fd: int,
    path: str,
    phase: str,
    owner: list[int],
    retained_components: list[RetainedComponent] | None = None,
) -> int:
    parts = _safe_relative(path, phase)
    parent = (
        _open_directory_beneath(
            root_fd,
            "/".join(parts[:-1]),
            phase,
            owner,
            retained_components,
        )
        if len(parts) > 1
        else root_fd
    )
    return _open_to_owner(
        owner,
        lambda: os.open(
            parts[-1],
            os.O_RDONLY
            | os.O_NONBLOCK
            | os.O_CLOEXEC
            | O_NOFOLLOW,
            dir_fd=parent,
        ),
    )


def _barrier_retained_components(
    root_fd: int,
    retained_components: Sequence[RetainedComponent],
    phase: str,
) -> None:
    for relative, fd, initial, parent, component in retained_components:
        current_owner: list[int] = []
        identity_error: ReadbackError | None = None
        cleanup_error: BaseException | None = None
        try:
            held = os.fstat(fd)
            named = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            current_fd = _open_directory_beneath(
                root_fd,
                relative,
                phase,
                current_owner,
            )
            current = os.fstat(current_fd)
            expected_identity = _directory_component_identity(initial)
            require(
                stat.S_ISDIR(held.st_mode)
                and stat.S_ISDIR(named.st_mode)
                and stat.S_ISDIR(current.st_mode)
                and stat.S_IMODE(held.st_mode) & 0o022 == 0
                and stat.S_IMODE(named.st_mode) & 0o022 == 0
                and stat.S_IMODE(current.st_mode) & 0o022 == 0
                and held.st_uid in {0, os.geteuid()}
                and named.st_uid in {0, os.geteuid()}
                and current.st_uid in {0, os.geteuid()}
                and _directory_component_identity(held)
                == expected_identity
                and _directory_component_identity(named)
                == expected_identity
                and _directory_component_identity(current)
                == expected_identity,
                "E_COMPONENT_IDENTITY",
                phase,
            )
        except BaseException as error:
            identity_error = ReadbackError(
                "E_COMPONENT_IDENTITY",
                phase,
            )
            identity_error.__cause__ = error
        finally:
            try:
                _close_owned_fds(current_owner)
            except BaseException as error:
                cleanup_error = error
        if identity_error is not None:
            if cleanup_error is not None:
                raise identity_error from cleanup_error
            raise identity_error
        if cleanup_error is not None:
            raise cleanup_error


def _lexists_beneath(
    root_fd: int,
    path: str,
    phase: str,
    owner: list[int],
) -> bool:
    parts = _safe_relative(path, phase)
    parent_path = "/".join(parts[:-1])
    parent = (
        _open_directory_beneath(root_fd, parent_path, phase, owner)
        if parent_path
        else root_fd
    )
    try:
        os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _open_root(
    root: Path,
    phase: str,
    owner: list[int],
) -> tuple[int, os.stat_result]:
    require(root.is_absolute(), "E_ROOT", phase)
    fd = _open_to_owner(
        owner,
        lambda: os.open(
            root,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NONBLOCK
            | os.O_CLOEXEC
            | O_NOFOLLOW,
        ),
    )
    info = os.fstat(fd)
    require(
        stat.S_ISDIR(info.st_mode)
        and info.st_uid in {0, os.geteuid()}
        and stat.S_IMODE(info.st_mode) & 0o022 == 0,
        "E_ROOT",
        phase,
    )
    return fd, info


def _root_barrier(
    root: Path,
    root_fd: int,
    before: os.stat_result,
    phase: str,
) -> None:
    held = os.fstat(root_fd)
    current_owner: list[int] = []
    try:
        _, current = _open_root(root, phase, current_owner)
        require(
            _stable_fields(held) == _stable_fields(before)
            and _stable_fields(current) == _stable_fields(before)
            and (current.st_dev, current.st_ino)
            == (before.st_dev, before.st_ino),
            "E_ROOT_IDENTITY",
            phase,
        )
    finally:
        _close_owned_fds(current_owner)


class HeldFile:
    def __init__(
        self,
        root_fd: int,
        expected: Mapping[str, Any],
        owner: list[int],
        existing_fd: int | None = None,
    ) -> None:
        self.root_fd = root_fd
        self.expected = expected
        self.owner = owner
        self.retained_components: list[RetainedComponent] = []
        if existing_fd is None:
            self.fd = _open_file_beneath(
                root_fd,
                expected["path"],
                "snapshot",
                owner,
                self.retained_components,
            )
        else:
            parts = _safe_relative(expected["path"], "snapshot")
            if len(parts) > 1:
                _open_directory_beneath(
                    root_fd,
                    "/".join(parts[:-1]),
                    "snapshot",
                    owner,
                    self.retained_components,
                )
            self.fd = existing_fd
        require(self.fd in owner, "E_FD_OWNER", "snapshot")
        self.before = os.fstat(self.fd)
        self._verify_shape(self.before)
        self.raw = _read_fd(self.fd, self.before.st_size, "snapshot")
        self._verify_bytes()
        self.barrier()

    def _verify_shape(self, info: os.stat_result) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_size == self.expected["bytes"]
            and stat.S_IMODE(info.st_mode) == int(self.expected["mode"], 8)
            and info.st_uid == self.expected["ownerUid"]
            and info.st_nlink == self.expected["linkCount"],
            "E_FROZEN",
            "snapshot",
        )

    def _verify_bytes(self) -> None:
        after = os.fstat(self.fd)
        self._verify_shape(after)
        require(
            _stable_fields(after) == _stable_fields(self.before)
            and len(self.raw) == self.expected["bytes"]
            and sha256(self.raw) == self.expected["rawSha256"],
            "E_FROZEN",
            "snapshot",
        )

    def refresh(self) -> None:
        self.barrier()
        self.raw = _read_fd(self.fd, self.before.st_size, "barrier")
        self._verify_bytes()
        self.barrier()

    def barrier(self) -> None:
        _barrier_retained_components(
            self.root_fd,
            self.retained_components,
            "barrier",
        )
        held = os.fstat(self.fd)
        self._verify_shape(held)
        current_owner: list[int] = []
        try:
            current_fd = _open_file_beneath(
                self.root_fd,
                self.expected["path"],
                "barrier",
                current_owner,
            )
            current = os.fstat(current_fd)
            self._verify_shape(current)
            current_raw = _read_fd(
                current_fd,
                self.expected["bytes"],
                "barrier",
            )
            require(
                _stable_fields(held) == _stable_fields(self.before)
                and _stable_fields(current) == _stable_fields(self.before)
                and (current.st_dev, current.st_ino)
                == (self.before.st_dev, self.before.st_ino)
                and current_raw == self.raw
                and sha256(current_raw) == self.expected["rawSha256"],
                "E_CURRENT_PATH_IDENTITY",
                "barrier",
            )
        finally:
            _close_owned_fds(current_owner)
        _barrier_retained_components(
            self.root_fd,
            self.retained_components,
            "barrier",
        )

    def close(self) -> None:
        if self.fd >= 0:
            _close_owned_fd(self.owner, self.fd)
            self.fd = -1


class HeldDirectory:
    def __init__(
        self,
        root_fd: int,
        expected: Mapping[str, Any],
        names: set[str],
        owner: list[int],
    ) -> None:
        self.root_fd = root_fd
        self.expected = expected
        self.names = names
        self.owner = owner
        self.retained_components: list[RetainedComponent] = []
        self.fd = _open_directory_beneath(
            root_fd,
            expected["path"],
            "snapshot",
            owner,
            self.retained_components,
        )
        self.before = os.fstat(self.fd)
        self.barrier()

    def barrier(self) -> None:
        _barrier_retained_components(
            self.root_fd,
            self.retained_components,
            "barrier",
        )
        held = os.fstat(self.fd)
        current_owner: list[int] = []
        try:
            current_fd = _open_directory_beneath(
                self.root_fd,
                self.expected["path"],
                "barrier",
                current_owner,
            )
            current = os.fstat(current_fd)
            require(
                stat.S_ISDIR(held.st_mode)
                and stat.S_ISDIR(current.st_mode)
                and stat.S_IMODE(held.st_mode)
                == stat.S_IMODE(current.st_mode)
                == int(self.expected["mode"], 8)
                and held.st_uid
                == current.st_uid
                == self.expected["ownerUid"]
                and held.st_nlink
                == current.st_nlink
                == self.expected["linkCount"]
                and _stable_fields(held) == _stable_fields(self.before)
                and _stable_fields(current) == _stable_fields(self.before)
                and (current.st_dev, current.st_ino)
                == (self.before.st_dev, self.before.st_ino)
                and set(os.listdir(self.fd)) == self.names
                and set(os.listdir(current_fd)) == self.names,
                "E_INVENTORY",
                "barrier",
            )
        finally:
            _close_owned_fds(current_owner)
        _barrier_retained_components(
            self.root_fd,
            self.retained_components,
            "barrier",
        )

    def close(self) -> None:
        if self.fd >= 0:
            _close_owned_fd(self.owner, self.fd)
            self.fd = -1


class FrozenSnapshot:
    """Open authority first, then hold every frozen acquisition input."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root.absolute()
        self.owned_fds: list[int] = []
        self.root_fd = -1
        self.root_before: os.stat_result | None = None
        self.files: dict[str, HeldFile] = {}
        self.directories: list[HeldDirectory] = []
        self.closed = False
        try:
            self.root_fd, self.root_before = _open_root(
                self.root,
                "snapshot",
                self.owned_fds,
            )
            for expected in PERMIT.ACQUISITION_AUTHORITY:
                self._hold(expected)
            self._hold(PERMIT.ACQUISITION_CLAIM)
            self.directories.append(
                HeldDirectory(
                    self.root_fd,
                    PERMIT.FINAL_DIRECTORY,
                    set(PERMIT.FINAL_DIRECTORY["exactEntries"]),
                    self.owned_fds,
                )
            )
            self._hold(PERMIT.EVIDENCE_FILE)
            accepted_names = {
                Path(row["path"]).name for row in PERMIT.ACCEPTED_FILES
            }
            self.directories.append(
                HeldDirectory(
                    self.root_fd,
                    PERMIT.ACCEPTED_DIRECTORY,
                    accepted_names,
                    self.owned_fds,
                )
            )
            for expected in PERMIT.ACCEPTED_FILES:
                self._hold(expected)
            self._hold(PERMIT.ACQUISITION_RECEIPT)
            self._hold(PERMIT.ACQUISITION_MANIFEST)
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def _hold(self, expected: Mapping[str, Any]) -> None:
        item = HeldFile(
            self.root_fd,
            expected,
            self.owned_fds,
        )
        require(expected["path"] not in self.files, "E_DUPLICATE", "snapshot")
        self.files[expected["path"]] = item

    def raw(self, path: str) -> bytes:
        require(path in self.files, "E_PATH", "snapshot")
        return self.files[path].raw

    def refresh(self) -> None:
        _root_barrier(
            self.root,
            self.root_fd,
            self.root_before,
            "barrier",
        )
        for item in self.files.values():
            item.refresh()
        self.final_barrier()

    def final_barrier(self) -> None:
        _root_barrier(
            self.root,
            self.root_fd,
            self.root_before,
            "barrier",
        )
        for item in self.files.values():
            item.barrier()
        for directory in self.directories:
            directory.barrier()
        ephemeral: list[int] = []
        try:
            require(
                not _lexists_beneath(
                    self.root_fd,
                    PERMIT.ACQUISITION_FAILURE_PATH,
                    "barrier",
                    ephemeral,
                ),
                "E_TERMINAL",
                "barrier",
            )
            dependency_fd = _open_directory_beneath(
                self.root_fd,
                PERMIT.DEPENDENCY_ROOT,
                "barrier",
                ephemeral,
            )
            require(
                not has_portable_prefix(
                    os.listdir(dependency_fd),
                    [PERMIT.STAGING_PREFIX],
                ),
                "E_TERMINAL",
                "barrier",
            )
        finally:
            _close_owned_fds(ephemeral)
        _root_barrier(
            self.root,
            self.root_fd,
            self.root_before,
            "barrier",
        )

    def close(self) -> None:
        if self.closed:
            return
        _close_owned_fds(self.owned_fds)
        self.root_fd = -1
        self.closed = True


class ReadbackNamespace:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root.absolute()
        self.owned_fds: list[int] = []
        self.root_fd = -1
        self.root_before: os.stat_result | None = None
        self.closed = False
        self.claim: HeldFile | None = None
        self.receipt: HeldFile | None = None
        self.manifest: HeldFile | None = None
        try:
            self.root_fd, self.root_before = _open_root(
                self.root,
                "readback_namespace",
                self.owned_fds,
            )
        except BaseException:
            try:
                _close_owned_fds(self.owned_fds)
            except BaseException:
                pass
            raise

    def _root_barrier(self) -> None:
        _root_barrier(
            self.root,
            self.root_fd,
            self.root_before,
            "readback_namespace",
        )

    def _temporary_names_absent(self) -> None:
        ephemeral: list[int] = []
        terminal_error: ReadbackError | None = None
        cleanup_error: BaseException | None = None
        try:
            parent = _open_directory_beneath(
                self.root_fd,
                PERMIT.BASE,
                "readback_namespace",
                ephemeral,
            )
            if has_portable_prefix(
                os.listdir(parent),
                PERMIT.READBACK_TEMP_PREFIXES,
            ):
                terminal_error = ReadbackError(
                    "E_STALE_TEMP_NAMESPACE",
                    "readback_namespace",
                    consumed=True,
                    uncertain=True,
                )
        finally:
            try:
                _close_owned_fds(ephemeral)
            except BaseException as error:
                cleanup_error = error
        if terminal_error is not None:
            if cleanup_error is not None:
                raise terminal_error from cleanup_error
            raise terminal_error
        if cleanup_error is not None:
            raise cleanup_error

    def namespace_state(self) -> str:
        ephemeral: list[int] = []
        observed_state: str | None = None
        cleanup_error: BaseException | None = None
        try:
            claim = _lexists_beneath(
                self.root_fd,
                PERMIT.READBACK_CLAIM_PATH,
                "readback_namespace",
                ephemeral,
            )
            receipt = _lexists_beneath(
                self.root_fd,
                PERMIT.READBACK_RECEIPT_PATH,
                "readback_namespace",
                ephemeral,
            )
            manifest = _lexists_beneath(
                self.root_fd,
                PERMIT.READBACK_MANIFEST_PATH,
                "readback_namespace",
                ephemeral,
            )
            parent = _open_directory_beneath(
                self.root_fd,
                PERMIT.BASE,
                "readback_namespace",
                ephemeral,
            )
            stale = has_portable_prefix(
                os.listdir(parent),
                PERMIT.READBACK_TEMP_PREFIXES,
            )
            if stale:
                observed_state = "stale_temporary_namespace"
            elif not claim and not receipt and not manifest:
                observed_state = "absent"
            elif claim and not receipt and not manifest:
                observed_state = "claim_only"
            elif claim and receipt and not manifest:
                observed_state = "receipt_only"
            elif claim and receipt and manifest:
                observed_state = "complete"
            else:
                observed_state = "inconsistent"
        finally:
            try:
                _close_owned_fds(ephemeral)
            except BaseException as error:
                cleanup_error = error
        if cleanup_error is not None:
            if observed_state in {"claim_only", "complete"}:
                raise ReadbackError(
                    "E_CONSUMED",
                    observed_state,
                    consumed=True,
                    uncertain=False,
                ) from cleanup_error
            if observed_state == "receipt_only":
                raise ReadbackError(
                    "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
                    observed_state,
                    consumed=True,
                    uncertain=True,
                ) from cleanup_error
            if observed_state == "stale_temporary_namespace":
                raise ReadbackError(
                    "E_STALE_TEMP_NAMESPACE",
                    observed_state,
                    consumed=True,
                    uncertain=True,
                ) from cleanup_error
            if observed_state == "inconsistent":
                raise ReadbackError(
                    "E_NAMESPACE_STATE_UNCERTAIN",
                    observed_state,
                    consumed=True,
                    uncertain=True,
                ) from cleanup_error
            raise cleanup_error
        require(
            observed_state is not None,
            "E_NAMESPACE_STATE_UNCERTAIN",
            "readback_namespace",
        )
        return observed_state

    def preclaim_barrier(self) -> None:
        self._root_barrier()
        state = self.namespace_state()
        self._root_barrier()
        if state == "absent":
            return
        if state in {"claim_only", "complete"}:
            raise ReadbackError(
                "E_CONSUMED",
                state,
                consumed=True,
                uncertain=False,
            )
        if state == "receipt_only":
            raise ReadbackError(
                "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
                state,
                consumed=True,
                uncertain=True,
            )
        if state == "stale_temporary_namespace":
            raise ReadbackError(
                "E_STALE_TEMP_NAMESPACE",
                state,
                consumed=True,
                uncertain=True,
            )
        raise ReadbackError(
            "E_NAMESPACE_STATE_UNCERTAIN",
            state,
            consumed=True,
            uncertain=True,
        )

    @staticmethod
    def _claim_identity_uncertain(error: BaseException) -> ReadbackError:
        return ReadbackError(
            "E_CLAIM_STATE_UNCERTAIN",
            "claim_identity",
            consumed=True,
            uncertain=True,
        )

    def _claim_barrier(self) -> None:
        require(self.claim is not None, "E_CLAIM", "readback_namespace")
        try:
            self.claim.barrier()
        except BaseException as error:
            raise self._claim_identity_uncertain(error) from error

    def hold_claim(
        self,
        expected: Mapping[str, Any],
        creation_fd: int,
    ) -> None:
        require(
            self.claim is None,
            "E_DUPLICATE",
            "readback_namespace",
        )
        try:
            self.claim = HeldFile(
                self.root_fd,
                expected,
                self.owned_fds,
                existing_fd=creation_fd,
            )
        except BaseException as error:
            if creation_fd in self.owned_fds:
                try:
                    _close_owned_fd(self.owned_fds, creation_fd)
                except BaseException:
                    pass
            raise self._claim_identity_uncertain(error) from error
        self._claim_barrier()

    def install_published(
        self,
        slot: str,
        expected: Mapping[str, Any],
        source_identity: tuple[int, int],
    ) -> None:
        self._root_barrier()
        require(
            slot in {"receipt", "manifest"}
            and getattr(self, slot) is None,
            "E_DUPLICATE",
            "publication",
        )
        held = HeldFile(
            self.root_fd,
            expected,
            self.owned_fds,
        )
        try:
            require(
                (held.before.st_dev, held.before.st_ino) == source_identity,
                "E_CURRENT_PATH_IDENTITY",
                "publication",
            )
            held.barrier()
        except BaseException:
            held.close()
            raise
        setattr(self, slot, held)
        self._root_barrier()

    def publication_barrier(self, *, receipt_required: bool) -> None:
        self._root_barrier()
        self._claim_barrier()
        ephemeral: list[int] = []
        terminal_error: ReadbackError | None = None
        cleanup_error: BaseException | None = None
        try:
            receipt_exists = _lexists_beneath(
                self.root_fd,
                PERMIT.READBACK_RECEIPT_PATH,
                "readback_namespace",
                ephemeral,
            )
            manifest_exists = _lexists_beneath(
                self.root_fd,
                PERMIT.READBACK_MANIFEST_PATH,
                "readback_namespace",
                ephemeral,
            )
            if receipt_exists is not receipt_required or manifest_exists:
                terminal_error = ReadbackError(
                    "E_OUTPUT_STATE",
                    "readback_namespace",
                    consumed=True,
                    uncertain=True,
                )
        finally:
            try:
                _close_owned_fds(ephemeral)
            except BaseException as error:
                cleanup_error = error
        if terminal_error is not None:
            if cleanup_error is not None:
                raise terminal_error from cleanup_error
            raise terminal_error
        if cleanup_error is not None:
            raise cleanup_error
        if receipt_required:
            if self.receipt is None:
                raise ReadbackError(
                    "E_OUTPUT_STATE",
                    "readback_namespace",
                    consumed=True,
                    uncertain=True,
                )
            self.receipt.barrier()
        else:
            if self.receipt is not None:
                raise ReadbackError(
                    "E_OUTPUT_STATE",
                    "readback_namespace",
                    consumed=True,
                    uncertain=True,
                )
        if self.manifest is not None or manifest_exists:
            raise ReadbackError(
                "E_OUTPUT_STATE",
                "readback_namespace",
                consumed=True,
                uncertain=True,
            )
        self._temporary_names_absent()
        self._root_barrier()

    def close(self) -> None:
        if self.closed:
            return
        _close_owned_fds(self.owned_fds)
        self.root_fd = -1
        self.closed = True


def decode_h1(value: str, phase: str) -> bytes:
    require(type(value) is str and value.startswith("h1:"), "E_H1", phase)
    try:
        raw = base64.b64decode(value[3:], validate=True)
    except (binascii.Error, ValueError) as error:
        raise ReadbackError("E_H1", phase) from error
    require(
        len(raw) == 32
        and base64.b64encode(raw).decode("ascii") == value[3:],
        "E_H1",
        phase,
    )
    return raw


def dirhash_h1(rows: Sequence[tuple[str, str]]) -> str:
    require(bool(rows), "E_H1", "hash")
    names: set[str] = set()
    lines: list[tuple[bytes, bytes]] = []
    for name, digest in rows:
        require(
            name not in names
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            "E_H1",
            "hash",
        )
        names.add(name)
        lines.append((name.encode(), f"{digest}  {name}\n".encode()))
    aggregate = hashlib.sha256(b"".join(line for _, line in sorted(lines))).digest()
    return "h1:" + base64.b64encode(aggregate).decode()


def _module_operand(line: str) -> str | None:
    match = re.fullmatch(r"[ \t]*module(?:[ \t]+(.*))?", line)
    if match is None:
        return None
    remainder = match.group(1)
    require(remainder is not None, "E_MOD", "mod")
    remainder = remainder.rstrip(" \t")
    if remainder.startswith('"'):
        closing = remainder.find('"', 1)
        require(closing > 1, "E_MOD", "mod")
        value = remainder[1:closing]
        tail = remainder[closing + 1 :].lstrip(" \t")
        require(
            '"' not in value
            and "\\" not in value
            and value.isascii()
            and all(0x21 <= ord(character) <= 0x7E for character in value)
            and (not tail or tail.startswith("//")),
            "E_MOD",
            "mod",
        )
        return value
    token, separator, tail = remainder.partition(" ")
    if not separator:
        token, separator, tail = remainder.partition("\t")
    tail = tail.lstrip(" \t")
    require(
        bool(token)
        and token.isascii()
        and all(0x21 <= ord(character) <= 0x7E for character in token)
        and (not separator or not tail or tail.startswith("//")),
        "E_MOD",
        "mod",
    )
    return token


def validate_mod(raw: bytes, module: str) -> dict[str, Any]:
    require(0 < len(raw) <= MAX_MOD_BYTES and b"\x00" not in raw, "E_MOD", "mod")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReadbackError("E_MOD", "mod") from error
    directives = [
        _module_operand(line)
        for line in text.splitlines()
        if re.match(r"^[ \t]*module(?:[ \t]|$)", line)
    ]
    require(directives == [module], "E_MOD", "mod")
    return {
        "rawSha256": sha256(raw),
        "goModH1": dirhash_h1([("go.mod", sha256(raw))]),
    }


def _zip_name(name: str, prefix: str) -> str:
    require(
        type(name) is str
        and name.startswith(prefix)
        and name == unicodedata.normalize("NFC", name)
        and len(name.encode()) <= MAX_ZIP_NAME_BYTES
        and not any(character in name for character in ("\x00", "\r", "\n", "\\", ":"))
        and not any(
            ord(character) < 32 or 0x7F <= ord(character) <= 0x9F
            for character in name
        ),
        "E_ZIP_NAME",
        "zip",
    )
    relative = name[len(prefix) :]
    parts = relative.split("/")
    require(
        bool(relative)
        and not relative.startswith("/")
        and not relative.endswith("/")
        and len(parts) <= 64
        and all(
            part not in {"", ".", ".."} and len(part.encode()) <= 255
            for part in parts
        ),
        "E_ZIP_NAME",
        "zip",
    )
    return relative


def _zip_layout(raw: bytes) -> tuple[int, int, int]:
    require(
        len(raw) >= ZIP_EOCD.size and raw.startswith(b"PK\x03\x04"),
        "E_ZIP_STRUCTURE",
        "zip",
    )
    eocd = raw.rfind(
        ZIP_EOCD_SIGNATURE,
        max(0, len(raw) - ZIP_EOCD.size - 65_535),
    )
    require(eocd >= 0 and eocd + ZIP_EOCD.size <= len(raw), "E_ZIP_STRUCTURE", "zip")
    (
        signature,
        disk,
        central_disk,
        disk_entries,
        total_entries,
        central_size,
        central_offset,
        comment_length,
    ) = ZIP_EOCD.unpack_from(raw, eocd)
    require(
        signature == ZIP_EOCD_SIGNATURE
        and disk == central_disk == 0
        and disk_entries == total_entries
        and 0 < total_entries <= MAX_ZIP_FILES
        and total_entries != 0xFFFF
        and central_size != 0xFFFFFFFF
        and central_offset != 0xFFFFFFFF
        and central_size <= 8 * 1024 * 1024
        and central_offset + central_size == eocd
        and comment_length == 0
        and eocd + ZIP_EOCD.size == len(raw),
        "E_ZIP_STRUCTURE",
        "zip",
    )
    return total_entries, central_offset, eocd


def _parse_extra(extra: bytes) -> None:
    cursor = 0
    while cursor < len(extra):
        require(len(extra) - cursor >= 4, "E_ZIP_EXTRA", "zip")
        field_id, size = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        require(
            field_id != 0x0001 and size <= len(extra) - cursor,
            "E_ZIP64",
            "zip",
        )
        cursor += size


def _central_directory(
    raw: bytes,
    count: int,
    start: int,
    end: int,
) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    cursor = start
    while cursor < end:
        require(cursor + ZIP_CENTRAL_HEADER.size <= end, "E_ZIP_CENTRAL", "zip")
        values = ZIP_CENTRAL_HEADER.unpack_from(raw, cursor)
        (
            signature,
            made,
            needed,
            flags,
            method,
            modified_time,
            modified_date,
            crc,
            compressed_size,
            file_size,
            name_size,
            extra_size,
            comment_size,
            volume,
            internal_attr,
            external_attr,
            local_offset,
        ) = values
        require(
            signature == ZIP_CENTRAL_SIGNATURE
            and needed < 45
            and flags & ~ALLOWED_ZIP_FLAGS == 0
            and compressed_size != 0xFFFFFFFF
            and file_size != 0xFFFFFFFF
            and local_offset != 0xFFFFFFFF
            and volume == 0
            and comment_size == 0
            and local_offset not in records,
            "E_ZIP_CENTRAL",
            "zip",
        )
        name_start = cursor + ZIP_CENTRAL_HEADER.size
        extra_start = name_start + name_size
        comment_start = extra_start + extra_size
        following = comment_start + comment_size
        require(following <= end, "E_ZIP_CENTRAL", "zip")
        extra = raw[extra_start:comment_start]
        _parse_extra(extra)
        require(not extra, "E_ZIP_EXTRA", "zip")
        records[local_offset] = {
            "made": made,
            "needed": needed,
            "flags": flags,
            "method": method,
            "modifiedTime": modified_time,
            "modifiedDate": modified_date,
            "crc": crc,
            "compressedSize": compressed_size,
            "fileSize": file_size,
            "name": raw[name_start:extra_start],
            "extra": extra,
            "internalAttr": internal_attr,
            "externalAttr": external_attr,
            "volume": volume,
        }
        cursor = following
    require(cursor == end and len(records) == count, "E_ZIP_CENTRAL", "zip")
    return records


def _compressed_spans(
    raw: bytes,
    infos: Sequence[zipfile.ZipInfo],
    central_offset: int,
    central: Mapping[int, Mapping[str, Any]],
) -> dict[int, bytes]:
    ordered = sorted(infos, key=lambda item: item.header_offset)
    require(ordered and ordered[0].header_offset == 0, "E_ZIP_PREFIX", "zip")
    payloads: dict[int, bytes] = {}
    for index, info in enumerate(ordered):
        offset = info.header_offset
        require(
            offset in central
            and 0 <= offset
            and offset + ZIP_LOCAL_HEADER.size <= central_offset,
            "E_ZIP_STRUCTURE",
            "zip",
        )
        record = central[offset]
        (
            signature,
            needed,
            flags,
            method,
            modified_time,
            modified_date,
            crc,
            compressed_size,
            file_size,
            name_size,
            extra_size,
        ) = ZIP_LOCAL_HEADER.unpack_from(raw, offset)
        require(
            signature == ZIP_LOCAL_SIGNATURE
            and (needed, flags, method, modified_time, modified_date)
            == (
                record["needed"],
                record["flags"],
                record["method"],
                record["modifiedTime"],
                record["modifiedDate"],
            )
            and (
                info.extract_version,
                info.flag_bits,
                info.compress_type,
                info.CRC,
                info.compress_size,
                info.file_size,
            )
            == (
                record["needed"],
                record["flags"],
                record["method"],
                record["crc"],
                record["compressedSize"],
                record["fileSize"],
            )
            and info.create_version + (info.create_system << 8) == record["made"]
            and info.internal_attr == record["internalAttr"]
            and info.external_attr == record["externalAttr"]
            and info.volume == record["volume"],
            "E_ZIP_STRUCTURE",
            "zip",
        )
        name_start = offset + ZIP_LOCAL_HEADER.size
        extra_start = name_start + name_size
        data_start = extra_start + extra_size
        require(data_start <= central_offset, "E_ZIP_STRUCTURE", "zip")
        raw_name = raw[name_start:extra_start]
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        try:
            local_name = raw_name.decode(encoding, errors="strict")
        except UnicodeDecodeError as error:
            raise ReadbackError("E_ZIP_NAME", "zip") from error
        local_extra = raw[extra_start:data_start]
        require(
            raw_name == record["name"]
            and local_name == info.filename
            and (flags & 0x0800 != 0 or not any(byte >= 0x80 for byte in raw_name))
            and local_extra == record["extra"]
            and not local_extra,
            "E_ZIP_STRUCTURE",
            "zip",
        )
        data_end = data_start + info.compress_size
        boundary = (
            ordered[index + 1].header_offset
            if index + 1 < len(ordered)
            else central_offset
        )
        require(data_end <= boundary, "E_ZIP_OVERLAP", "zip")
        if flags & 0x0008:
            require(
                (crc, compressed_size, file_size)
                in {
                    (0, 0, 0),
                    (info.CRC, info.compress_size, info.file_size),
                },
                "E_ZIP_DESCRIPTOR",
                "zip",
            )
            descriptor = raw[data_end:boundary]
            if len(descriptor) == ZIP_DATA_DESCRIPTOR.size:
                descriptor_values = ZIP_DATA_DESCRIPTOR.unpack(descriptor)
            elif len(descriptor) == ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.size:
                marker, *descriptor_values = ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.unpack(
                    descriptor
                )
                require(
                    marker == ZIP_DATA_DESCRIPTOR_SIGNATURE,
                    "E_ZIP_DESCRIPTOR",
                    "zip",
                )
            else:
                raise ReadbackError("E_ZIP_DESCRIPTOR", "zip")
            require(
                tuple(descriptor_values)
                == (info.CRC, info.compress_size, info.file_size),
                "E_ZIP_DESCRIPTOR",
                "zip",
            )
        else:
            require(
                data_end == boundary
                and (crc, compressed_size, file_size)
                == (info.CRC, info.compress_size, info.file_size),
                "E_ZIP_STRUCTURE",
                "zip",
            )
        payloads[offset] = raw[data_start:data_end]
    return payloads


def _inflate(info: zipfile.ZipInfo, compressed: bytes) -> bytes:
    require(len(compressed) == info.compress_size, "E_ZIP_SIZE", "zip")
    if info.compress_type == zipfile.ZIP_STORED:
        require(info.compress_size == info.file_size, "E_ZIP_SIZE", "zip")
        decoded = compressed
    else:
        decoder = zlib.decompressobj(-zlib.MAX_WBITS)
        try:
            decoded = decoder.decompress(compressed, info.file_size + 1)
            decoded += decoder.flush(info.file_size - len(decoded) + 1)
        except (ValueError, zlib.error) as error:
            raise ReadbackError("E_ZIP_DEFLATE", "zip") from error
        require(
            decoder.eof
            and not decoder.unused_data
            and not decoder.unconsumed_tail,
            "E_ZIP_DEFLATE",
            "zip",
        )
    require(
        len(decoded) == info.file_size
        and len(decoded) <= MAX_ZIP_FILE_BYTES
        and zlib.crc32(decoded) & 0xFFFFFFFF == info.CRC,
        "E_ZIP_CRC",
        "zip",
    )
    return decoded


def validate_zip(
    raw: bytes,
    module: str,
    version: str,
    mod_raw: bytes | None,
) -> dict[str, Any]:
    require(0 < len(raw) <= MAX_ZIP_BYTES, "E_ZIP_SIZE", "zip")
    prefix = f"{module}@{version}/"
    rows: list[tuple[str, str]] = []
    names: set[str] = set()
    folded: set[str] = set()
    relative_names: set[str] = set()
    total = 0
    root_mod: bytes | None = None
    archive: zipfile.ZipFile | None = None
    try:
        count, central_offset, central_end = _zip_layout(raw)
        central = _central_directory(raw, count, central_offset, central_end)
        archive = zipfile.ZipFile(io.BytesIO(raw), "r")
        infos = archive.infolist()
        require(
            not archive.comment
            and 0 < len(infos) == count <= MAX_ZIP_FILES,
            "E_ZIP_SHAPE",
            "zip",
        )
        payloads = _compressed_spans(raw, infos, central_offset, central)
        require(
            {info.header_offset for info in infos} == set(central),
            "E_ZIP_CENTRAL",
            "zip",
        )
        for info in infos:
            relative = _zip_name(info.filename, prefix)
            folded_name = info.filename.casefold()
            require(
                info.filename not in names
                and folded_name not in folded
                and relative not in relative_names,
                "E_ZIP_DUPLICATE",
                "zip",
            )
            names.add(info.filename)
            folded.add(folded_name)
            relative_names.add(relative)
            require(
                info.flag_bits & 0x1 == 0
                and info.flag_bits & ~ALLOWED_ZIP_FLAGS == 0
                and info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                and info.create_system in {0, 3}
                and info.extract_version < 45
                and info.volume == 0
                and not info.is_dir()
                and not info.extra
                and not info.comment
                and 0 <= info.file_size <= MAX_ZIP_FILE_BYTES
                and 0 <= info.compress_size <= MAX_ZIP_BYTES,
                "E_ZIP_SHAPE",
                "zip",
            )
            mode = (info.external_attr >> 16) & 0xFFFF
            if info.create_system == 3 and mode:
                require(
                    stat.S_ISREG(mode)
                    and mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX) == 0,
                    "E_ZIP_MODE",
                    "zip",
                )
            if info.create_system == 0:
                require(info.external_attr & 0x1F == 0, "E_ZIP_MODE", "zip")
            total += info.file_size
            require(
                total <= MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP,
                "E_ZIP_SIZE",
                "zip",
            )
            decoded = _inflate(info, payloads[info.header_offset])
            if relative == "go.mod":
                root_mod = decoded
            rows.append((info.filename, sha256(decoded)))
        folded_relative = {name.casefold() for name in relative_names}
        for relative in relative_names:
            parts = relative.split("/")
            for index in range(1, len(parts)):
                ancestor = "/".join(parts[:index])
                require(
                    ancestor not in relative_names
                    and ancestor.casefold() not in folded_relative,
                    "E_ZIP_COLLISION",
                    "zip",
                )
    except (zipfile.BadZipFile, RuntimeError, ValueError, OSError) as error:
        if isinstance(error, ReadbackError):
            raise
        raise ReadbackError("E_ZIP_SHAPE", "zip") from error
    finally:
        if archive is not None:
            archive.close()
    if root_mod is not None and mod_raw is not None:
        require(root_mod == mod_raw, "E_MOD_PARITY", "zip")
    return {
        "rawSha256": sha256(raw),
        "moduleZipH1": dirhash_h1(rows),
        "entryCount": len(rows),
        "uncompressedBytes": total,
        "rootGoModPresent": root_mod is not None,
    }


def _bound_json(raw: bytes, phase: str) -> dict[str, Any]:
    value = strict_json(raw, phase)
    verify_content_binding(value, phase)
    return value


def validate_resource_selection(
    resources: Sequence[Mapping[str, Any]],
    phase: str,
) -> tuple[list[int], set[str]]:
    require(
        type(resources) is list
        and len(resources) == 8
        and all(
            type(row) is dict
            and type(row.get("selectedByGraphAlgorithm")) is bool
            for row in resources
        ),
        "E_RESOURCES",
        phase,
    )
    selected_request_ordinals = [
        row["requestOrdinal"]
        for row in resources
        if row["selectedByGraphAlgorithm"]
    ]
    selected_tuple_ids = {
        row["tupleId"]
        for row in resources
        if row["selectedByGraphAlgorithm"]
    }
    require(
        selected_request_ordinals == []
        and selected_tuple_ids == set()
        and all(
            row["selectedByGraphAlgorithm"] is False
            for row in resources
        ),
        "E_RESOURCES",
        phase,
    )
    return selected_request_ordinals, selected_tuple_ids


def verify_snapshot(snapshot: FrozenSnapshot) -> dict[str, Any]:
    phase = "verification"
    authority = {row["path"]: row for row in PERMIT.ACQUISITION_AUTHORITY}
    decision_path = (
        PERMIT.BASE
        + "/bounded-dependency-source-identity-and-acquisition-"
        "decision-wave14-v1.json"
    )
    permit_path = (
        PERMIT.BASE
        + "/bounded-dependency-source-acquisition-wave14-execution-permit-v1.json"
    )
    decision = _bound_json(snapshot.raw(decision_path), "decision")
    acquisition_permit = _bound_json(snapshot.raw(permit_path), "permit")
    require(
        decision["contentBinding"]["sha256"] == PERMIT.EXPECTED_DECISION_CONTENT
        and acquisition_permit["contentBinding"]["sha256"]
        == PERMIT.EXPECTED_ACQUISITION_PERMIT_CONTENT
        and acquisition_permit["decisionBinding"]["rawSha256"]
        == authority[decision_path]["rawSha256"]
        and acquisition_permit["decisionBinding"]["contentSha256"]
        == decision["contentBinding"]["sha256"],
        "E_AUTHORITY",
        phase,
    )
    authority_hashes = {row["path"]: row["rawSha256"] for row in PERMIT.ACQUISITION_AUTHORITY}
    require(
        set(acquisition_permit["predecessorBindings"])
        == {"combinedFixedPointV12"},
        "E_AUTHORITY",
        phase,
    )
    v12 = acquisition_permit["predecessorBindings"]["combinedFixedPointV12"]
    predecessor_authority_rows = [
        {
            "path": v12["checkerPath"],
            "rawSha256": v12["checkerRawSha256"],
        },
        {
            "path": v12["testsPath"],
            "rawSha256": v12["testsRawSha256"],
        },
    ]
    bound_authority_rows = [
        *acquisition_permit["decisionBinding"]["files"],
        *predecessor_authority_rows,
        v12["wave13NamespaceAnchor"],
        acquisition_permit["readerDocumentBinding"],
        *acquisition_permit["toolBindings"],
        *acquisition_permit["primitiveBindings"],
    ]
    require(
        len(authority_hashes) == 15
        and len(bound_authority_rows) == 14
        and set(authority_hashes)
        == {permit_path, *(row["path"] for row in bound_authority_rows)},
        "E_AUTHORITY",
        phase,
    )
    for row in bound_authority_rows:
        require(
            authority_hashes.get(row["path"]) == row["rawSha256"],
            "E_AUTHORITY",
            phase,
        )
    require(
        acquisition_permit["requestContract"][
            "sourceRequestSetCanonicalSha256"
        ]
        == PERMIT.EXPECTED_SOURCE_REQUEST_SET_CANONICAL
        and acquisition_permit["requestContract"]["tupleCount"] == 4
        and acquisition_permit["requestContract"]["requestCount"] == 8
        and acquisition_permit["requestContract"][
            "resourcesCanonicalSha256"
        ]
        == PERMIT.EXPECTED_RESOURCES_CANONICAL
        and v12
        == {
            "checkerPath": (
                "script/check_p2p_nat_g2_pion_combined_fixed_point_v12.py"
            ),
            "checkerRawSha256": authority_hashes[
                "script/check_p2p_nat_g2_pion_combined_fixed_point_v12.py"
            ],
            "checkerNormalizedSha256": (
                PERMIT.EXPECTED_V12_CHECKER_NORMALIZED
            ),
            "testsPath": (
                "script/test_p2p_nat_g2_pion_combined_fixed_point_v12.py"
            ),
            "testsRawSha256": authority_hashes[
                "script/test_p2p_nat_g2_pion_combined_fixed_point_v12.py"
            ],
            "contentSha256": PERMIT.EXPECTED_V12_CONTENT,
            "combinedInputSetSha256": PERMIT.EXPECTED_V12_INPUT_SET,
            "graphSha256": PERMIT.EXPECTED_V12_GRAPH,
            "frontierSha256": PERMIT.EXPECTED_V12_FRONTIER,
            "sourceBindingsSha256": (
                PERMIT.EXPECTED_HELD_SOURCE_BINDINGS
            ),
            "v11TestsBindingScope":
                "historical_metadata_only_not_live_held",
            "v11TestsLiveHeld": False,
            "wave13NamespaceAnchor": {
                "path": (
                    "build/offline-source/pion-ice-v4.3.0/"
                    "dependencies/.wave-13-v1.claim"
                ),
                "rawSha256": authority_hashes[
                    "build/offline-source/pion-ice-v4.3.0/"
                    "dependencies/.wave-13-v1.claim"
                ],
            },
        }
        and acquisition_permit["identityBinding"]
        == {
            "blockedTupleCount": 0,
            "compactIdentitySha256": PERMIT.EXPECTED_COMPACT_IDENTITY,
            "completeTupleCount": 4,
            "fullWitnessSha256": PERMIT.EXPECTED_FULL_WITNESS,
            "heldSourceBindingsSha256": (
                PERMIT.EXPECTED_HELD_SOURCE_BINDINGS
            ),
        }
        and acquisition_permit["authority"][
            "externalAuthenticationRequired"
        ]
        is False
        and acquisition_permit["authority"][
            "repositoryOwnerIdentityProofRequired"
        ]
        is False
        and acquisition_permit["authority"]["accountRequired"] is False
        and acquisition_permit["authority"]["ownerRequired"] is False
        and acquisition_permit["authority"]["sshRequired"] is False
        and acquisition_permit["authority"]["gpgRequired"] is False
        and acquisition_permit["authority"]["authenticationRequired"] is False
        and acquisition_permit["authority"]["passwordRequired"] is False
        and acquisition_permit["authority"]["privateKeyRequired"] is False
        and acquisition_permit["authority"]["signatureRequired"] is False
        and acquisition_permit["authority"]["tokenRequired"] is False
        and acquisition_permit["authority"]["cookieRequired"] is False
        and acquisition_permit["authority"][
            "clientCertificateRequired"
        ]
        is False
        and acquisition_permit["authority"]["userActionRequired"] is False,
        "E_AUTHORITY",
        phase,
    )
    claim_expected = {
        "documentType": "aetherlink.wave14-source-acquisition-claim",
        "schemaVersion": "1.0",
        "attemptId": PERMIT.ATTEMPT_ID,
        "permitContentSha256": acquisition_permit["contentBinding"]["sha256"],
        "checkerRawSha256": authority_hashes[
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave14_acquisition_v1.py"
        ],
        "requestCount": 8,
        "status": "consumed_active",
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }
    claim_raw = snapshot.raw(PERMIT.ACQUISITION_CLAIM_PATH)
    require(
        strict_json(claim_raw, "claim") == claim_expected
        and claim_raw == canonical_bytes(claim_expected),
        "E_CLAIM",
        phase,
    )
    resources = acquisition_permit["requestContract"]["resources"]
    require(
        sha256(canonical_bytes(resources))
        == PERMIT.EXPECTED_RESOURCES_CANONICAL,
        "E_RESOURCES",
        phase,
    )
    expected_accepted_names = [
        Path(row["path"]).name for row in PERMIT.ACCEPTED_FILES
    ]
    require(
        len(resources) == 8
        and [row["requestOrdinal"] for row in resources] == list(range(1, 9))
        and [row["kind"] for row in resources] == ["mod", "zip"] * 4
        and [row["acceptedFileName"] for row in resources]
        == expected_accepted_names,
        "E_RESOURCES",
        phase,
    )
    selected_request_ordinals, selected_tuple_ids = (
        validate_resource_selection(resources, phase)
    )
    accepted_specs = {
        Path(row["path"]).name: row for row in PERMIT.ACCEPTED_FILES
    }
    evidence_rows: list[dict[str, Any]] = []
    mod_by_tuple: dict[str, bytes] = {}
    aggregate_mod = 0
    aggregate_zip = 0
    aggregate_zip_entries = 0
    aggregate_zip_uncompressed = 0
    for ordinal, resource in enumerate(resources, 1):
        name = resource["acceptedFileName"]
        require(
            ordinal == resource["requestOrdinal"] and name in accepted_specs,
            "E_ORDER",
            phase,
        )
        raw = snapshot.raw(accepted_specs[name]["path"])
        require(
            0 < len(raw) <= resource["maximumResponseBodyBytes"],
            "E_SIZE",
            phase,
        )
        if resource["kind"] == "mod":
            verified = validate_mod(raw, resource["module"])
            actual_h1 = verified["goModH1"]
            mod_by_tuple[resource["tupleId"]] = raw
            aggregate_mod += len(raw)
        else:
            require(resource["tupleId"] in mod_by_tuple, "E_ORDER", phase)
            verified = validate_zip(
                raw,
                resource["module"],
                resource["version"],
                mod_by_tuple[resource["tupleId"]],
            )
            actual_h1 = verified["moduleZipH1"]
            aggregate_zip += len(raw)
            aggregate_zip_entries += verified["entryCount"]
            aggregate_zip_uncompressed += verified["uncompressedBytes"]
        decode_h1(resource["expectedH1"], phase)
        require(
            actual_h1 == resource["expectedH1"]
            and verified["rawSha256"] == accepted_specs[name]["rawSha256"],
            "E_H1",
            phase,
        )
        evidence_rows.append(
            {
                "requestOrdinal": ordinal,
                "tupleId": resource["tupleId"],
                "kind": resource["kind"],
                "url": resource["url"],
                "byteCount": len(raw),
                "rawSha256": sha256(raw),
                "verifiedH1": actual_h1,
                "acceptedFileName": name,
                **{
                    key: value
                    for key, value in verified.items()
                    if key not in {"rawSha256", "goModH1", "moduleZipH1"}
                },
            }
        )
    aggregate = aggregate_mod + aggregate_zip
    require(
        len(mod_by_tuple) == 4
        and aggregate_mod == 753
        and aggregate_zip == 15_050_695
        and aggregate == 15_051_448
        and aggregate_zip_entries == 2_571
        and aggregate_zip_uncompressed == 55_954_414
        and aggregate_zip_entries <= MAX_ZIP_FILES_ACROSS_ALL
        and aggregate_zip_uncompressed
        <= MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL
        and aggregate_mod <= MAX_AGGREGATE_MOD_BYTES
        and aggregate_zip <= MAX_AGGREGATE_ZIP_BYTES
        and aggregate <= MAX_AGGREGATE_BYTES,
        "E_AGGREGATE",
        phase,
    )
    evidence_expected = {
        "documentType": "aetherlink.wave14-source-acquisition-evidence",
        "schemaVersion": "1.0",
        "attemptId": PERMIT.ATTEMPT_ID,
        "requestCount": 8,
        "aggregateResponseBytes": aggregate,
        "aggregateModResponseBytes": aggregate_mod,
        "aggregateZipResponseBytes": aggregate_zip,
        "aggregateZipEntryCount": aggregate_zip_entries,
        "aggregateZipUncompressedBytes": aggregate_zip_uncompressed,
        "resources": evidence_rows,
    }
    evidence_raw = snapshot.raw(PERMIT.EVIDENCE_PATH)
    require(
        strict_json(evidence_raw, "evidence") == evidence_expected
        and evidence_raw == canonical_bytes(evidence_expected),
        "E_EVIDENCE",
        phase,
    )
    accepted_hash_set = sha256(
        canonical_bytes(
            [
                {
                    "requestOrdinal": row["requestOrdinal"],
                    "acceptedFileName": row["acceptedFileName"],
                    "rawSha256": row["rawSha256"],
                    "verifiedH1": row["verifiedH1"],
                }
                for row in evidence_rows
            ]
        )
    )
    require(
        accepted_hash_set == PERMIT.EXPECTED_ACCEPTED_RESOURCE_HASH_SET,
        "E_HASH_SET",
        phase,
    )
    acquisition_runner_hash = authority_hashes[
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave14_v1_once.py"
    ]
    receipt_expected = {
        "documentType": "aetherlink.wave14-source-acquisition-receipt",
        "schemaVersion": "1.0",
        "status": "consumed_success_pending_independent_readback",
        "attemptId": PERMIT.ATTEMPT_ID,
        "decisionContentSha256": decision["contentBinding"]["sha256"],
        "permitContentSha256": acquisition_permit["contentBinding"]["sha256"],
        "checkerRawSha256": claim_expected["checkerRawSha256"],
        "runnerRawSha256": acquisition_runner_hash,
        "claimRawSha256": sha256(claim_raw),
        "acceptedEvidenceRawSha256": sha256(evidence_raw),
        "acceptedResourceHashSetCanonicalSha256": accepted_hash_set,
        "requestCount": 8,
        "modCount": 4,
        "zipCount": 4,
        "acceptedResourceCount": 8,
        "aggregateResponseBytes": aggregate,
        "aggregateModResponseBytes": aggregate_mod,
        "aggregateZipResponseBytes": aggregate_zip,
        "aggregateZipEntryCount": aggregate_zip_entries,
        "aggregateZipUncompressedBytes": aggregate_zip_uncompressed,
        "dispatchBoundaryCount": 8,
        "responseCommittedCount": 8,
        "responseCommittedBytes": aggregate,
        "validationCommittedCount": 8,
        "persistenceCommittedCount": 8,
        "currentResourceOrdinal": None,
        "currentOperationPhase": None,
        "additionalCompletionUncertain": False,
        "operationCountSemantics": "exact_terminal_success",
        "sourceAcquisitionState": "all_responses_committed",
        "acceptedPath": PERMIT.ACCEPTED_ROOT,
        "sourceAcquired": True,
        "sourceExtracted": False,
        "sourceLoadedOrExecuted": False,
        "compiled": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }
    receipt_raw = snapshot.raw(PERMIT.ACQUISITION_RECEIPT_PATH)
    require(
        strict_json(receipt_raw, "receipt") == receipt_expected
        and receipt_raw == canonical_bytes(receipt_expected),
        "E_RECEIPT",
        phase,
    )
    manifest_expected = {
        "documentType": "aetherlink.wave14-source-acquisition-manifest",
        "schemaVersion": "1.0",
        "status": "consumed_success_pending_independent_readback",
        "attemptId": PERMIT.ATTEMPT_ID,
        "receiptPath": PERMIT.ACQUISITION_RECEIPT_PATH,
        "receiptRawSha256": sha256(receipt_raw),
        "manifestWrittenLast": True,
    }
    manifest_raw = snapshot.raw(PERMIT.ACQUISITION_MANIFEST_PATH)
    require(
        strict_json(manifest_raw, "manifest") == manifest_expected
        and manifest_raw == canonical_bytes(manifest_expected),
        "E_MANIFEST",
        phase,
    )
    snapshot.final_barrier()
    return {
        "status": (
            "wave14_acquisition_retained_snapshot_independently_verified"
        ),
        "acquisitionAttemptId": PERMIT.ATTEMPT_ID,
        "authorityFileCount": 15,
        "acceptedResourceCount": 8,
        "selectedTupleCount": len(selected_tuple_ids),
        "selectedRequestOrdinals": selected_request_ordinals,
        "modCount": 4,
        "zipCount": 4,
        "aggregateModBytes": aggregate_mod,
        "aggregateZipBytes": aggregate_zip,
        "aggregateAcceptedBytes": aggregate,
        "aggregateZipEntryCount": aggregate_zip_entries,
        "aggregateZipUncompressedBytes": aggregate_zip_uncompressed,
        "decisionContentSha256": decision["contentBinding"]["sha256"],
        "permitContentSha256": (
            acquisition_permit["contentBinding"]["sha256"]
        ),
        "sourceRequestSetCanonicalSha256": (
            PERMIT.EXPECTED_SOURCE_REQUEST_SET_CANONICAL
        ),
        "resourcesCanonicalSha256": PERMIT.EXPECTED_RESOURCES_CANONICAL,
        "combinedFixedPointV12ContentSha256": PERMIT.EXPECTED_V12_CONTENT,
        "compactIdentitySha256": PERMIT.EXPECTED_COMPACT_IDENTITY,
        "fullWitnessSha256": PERMIT.EXPECTED_FULL_WITNESS,
        "heldSourceBindingsSha256": PERMIT.EXPECTED_HELD_SOURCE_BINDINGS,
        "acquisitionClaimRawSha256": sha256(claim_raw),
        "evidenceRawSha256": sha256(evidence_raw),
        "acceptedResourceHashSetCanonicalSha256": accepted_hash_set,
        "acquisitionReceiptRawSha256": sha256(receipt_raw),
        "acquisitionManifestRawSha256": sha256(manifest_raw),
        "resources": evidence_rows,
        "failureAbsent": True,
        "stagingAbsent": True,
        "sourceExtracted": False,
        "sourceLoadedOrExecuted": False,
        "compiled": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def preflight() -> dict[str, Any]:
    try:
        value = PERMIT.package_preflight_for_recorder()
    except PERMIT.PermitError as error:
        state = getattr(error, "state", None) or "permit_preflight"
        if error.code == "E_CONSUMED":
            if state in {"claim_only", "complete"}:
                raise ReadbackError(
                    "E_CONSUMED",
                    state,
                    consumed=True,
                    uncertain=False,
                ) from error
            if state == "receipt_only":
                raise ReadbackError(
                    "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
                    state,
                    consumed=True,
                    uncertain=True,
                ) from error
            if state == "stale_temporary_namespace":
                raise ReadbackError(
                    "E_STALE_TEMP_NAMESPACE",
                    state,
                    consumed=True,
                    uncertain=True,
                ) from error
            raise ReadbackError(
                "E_NAMESPACE_STATE_UNCERTAIN",
                state,
                consumed=True,
                uncertain=True,
            ) from error
        raise ReadbackError(error.code, "permit_preflight") from error
    require(type(value) is dict, "E_PREFLIGHT", "preflight")
    permit = value.get("permit")
    authority = permit.get("authority") if type(permit) is dict else None
    require(
        type(permit) is dict
        and permit.get("status") == "authorized_not_consumed"
        and type(authority) is dict
        and canonical_bytes(authority)
        == canonical_bytes(EXPECTED_PREFLIGHT_AUTHORITY)
        and value.get("frozenAcquisitionInputOpened") is False,
        "E_PREFLIGHT",
        "preflight",
    )
    return {
        **value,
        "authorityBinding": {
            "permit": {
                "path": PERMIT.PERMIT_PATH,
                "rawSha256": value["permitRawSha256"],
                "contentSha256": value["permitContentSha256"],
            },
            "checker": {
                "path": PERMIT.THIS_CHECKER_PATH,
                "rawSha256": value["checkerRawSha256"],
            },
            "recorder": {
                "path": PERMIT.RECORDER_PATH,
                "rawSha256": value["recorderRawSha256"],
            },
        },
    }


def _write_all(fd: int, raw: bytes, phase: str) -> None:
    view = memoryview(raw)
    while view:
        written = os.write(fd, view)
        require(written > 0, "E_WRITE", phase)
        view = view[written:]


def create_readback_claim(
    root: Path,
    readback_attempt_id: str,
    authority_binding: Mapping[str, Any],
    retained_root_fd: int | None = None,
    fd_owner: list[int] | None = None,
) -> tuple[dict[str, Any], int]:
    traversal_owner: list[int] = []
    claim = content_bound(
        {
            "documentType": "aetherlink.wave14-acquisition-readback-one-use-claim",
            "schemaVersion": "1.0",
            "status": "consumed_active",
            "readbackAttemptId": readback_attempt_id,
            "acquisitionAttemptId": PERMIT.ATTEMPT_ID,
            "authorityBinding": authority_binding,
            "claimPersistsAfterSuccessFailureOrUncertainty": True,
            "retryAllowed": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    )
    raw = canonical_bytes(claim)
    created = False
    existing_claim_observed = False
    fd = -1
    claim_owner = [] if fd_owner is None else fd_owner
    success: tuple[dict[str, Any], int] | None = None

    def mark_created(opened_fd: int) -> None:
        nonlocal created, fd
        created = True
        fd = opened_fd

    try:
        if retained_root_fd is None:
            root_fd, _ = _open_root(
                root.absolute(),
                "claim",
                traversal_owner,
            )
        else:
            root_fd = retained_root_fd
        target_parts = _safe_relative(PERMIT.READBACK_CLAIM_PATH, "claim")
        parent = _open_directory_beneath(
            root_fd,
            "/".join(target_parts[:-1]),
            "claim",
            traversal_owner,
        )
        opened_fd = _open_to_owner(
            claim_owner,
            lambda: os.open(
                target_parts[-1],
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            ),
            mark_created,
        )
        require(opened_fd == fd and created, "E_FD_OWNER", "claim")
        os.fchmod(opened_fd, 0o600)
        _write_all(opened_fd, raw, "claim")
        info = os.fstat(opened_fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == len(raw),
            "E_CLAIM",
            "claim",
        )
        os.fsync(opened_fd)
        os.fsync(parent)
        result = {
            "path": PERMIT.READBACK_CLAIM_PATH,
            "rawSha256": sha256(raw),
            "bytes": len(raw),
            "mode": "0600",
            "ownerUid": info.st_uid,
            "linkCount": info.st_nlink,
            "contentSha256": claim["contentBinding"]["sha256"],
        }
        success = (result, opened_fd)
    except FileExistsError as error:
        existing_claim_observed = True
        raise ReadbackError(
            "E_CONSUMED",
            "claim",
            consumed=True,
        ) from error
    except BaseException as error:
        if isinstance(error, ReadbackError):
            cause = error
        else:
            cause = ReadbackError("E_CLAIM", "claim")
        raise ReadbackError(
            "E_CLAIM_STATE_UNCERTAIN" if created else "E_CLAIM_NOT_CREATED",
            "claim",
            consumed=created,
            uncertain=created,
        ) from cause
    finally:
        cleanup_errors: list[BaseException] = []
        try:
            _close_owned_fds(traversal_owner)
        except BaseException as error:
            cleanup_errors.append(error)
        if (success is None or cleanup_errors) and fd >= 0:
            try:
                if fd in claim_owner:
                    _close_owned_fd(claim_owner, fd)
                else:
                    orphaned_owner = [fd]
                    _close_owned_fds(orphaned_owner)
            except BaseException as error:
                cleanup_errors.append(error)
        if cleanup_errors:
            if existing_claim_observed:
                raise ReadbackError(
                    "E_CONSUMED",
                    "claim_cleanup",
                    consumed=True,
                    uncertain=False,
                ) from cleanup_errors[0]
            raise ReadbackError(
                (
                    "E_CLAIM_STATE_UNCERTAIN"
                    if created
                    else "E_CLAIM_NOT_CREATED"
                ),
                "claim",
                consumed=created,
                uncertain=created,
            ) from cleanup_errors[0]
    require(success is not None, "E_CLAIM", "claim")
    return success


def rename_no_replace(
    source_parent_fd: int,
    source_name: str,
    target_parent_fd: int,
    target_name: str,
) -> None:
    require(sys.platform == "darwin", "E_RENAME", "publication")
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameatx_np", None)
    require(rename is not None, "E_RENAME", "publication")
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    result = rename(
        source_parent_fd,
        source_name.encode(),
        target_parent_fd,
        target_name.encode(),
        RENAME_EXCL,
    )
    if result != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise ReadbackError("E_OUTPUT_EXISTS", "publication")
        raise ReadbackError("E_RENAME", "publication")


def atomic_publish(
    root: Path,
    path: str,
    payload: Mapping[str, Any],
    rename_fn: Callable[[int, str, int, str], None] = rename_no_replace,
    *,
    namespace: ReadbackNamespace | None = None,
    slot: str | None = None,
) -> dict[str, Any]:
    require(
        (namespace is None and slot is None)
        or (namespace is not None and slot in {"receipt", "manifest"}),
        "E_PUBLICATION_BINDING",
        "publication",
    )
    root_path = root.absolute()
    owned: list[int] = []
    root_fd = -1
    parent = -1
    target = ""
    temporary = ""
    raw = canonical_bytes(payload)
    temporary_created = False
    published = False
    fd = -1
    local_hold: HeldFile | None = None

    def mark_temporary_created(opened_fd: int) -> None:
        nonlocal fd, temporary_created
        fd = opened_fd
        temporary_created = True

    try:
        root_fd, root_before = _open_root(
            root_path,
            "publication",
            owned,
        )
        parts = _safe_relative(path, "publication")
        parent = _open_directory_beneath(
            root_fd,
            "/".join(parts[:-1]),
            "publication",
            owned,
        )
        target = parts[-1]
        temporary = f".{target}.tmp-{secrets.token_hex(16)}"
        _root_barrier(root_path, root_fd, root_before, "publication")
        try:
            os.stat(target, dir_fd=parent, follow_symlinks=False)
            raise ReadbackError("E_OUTPUT_EXISTS", "publication")
        except FileNotFoundError:
            pass
        opened_fd = _open_to_owner(
            owned,
            lambda: os.open(
                temporary,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            ),
            mark_temporary_created,
        )
        require(
            opened_fd == fd and temporary_created,
            "E_FD_OWNER",
            "publication",
        )
        os.fchmod(opened_fd, 0o600)
        _write_all(opened_fd, raw, "publication")
        info = os.fstat(opened_fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == len(raw),
            "E_WRITE",
            "publication",
        )
        require(
            _read_fd(opened_fd, len(raw), "publication") == raw,
            "E_WRITE",
            "publication",
        )
        os.fsync(opened_fd)
        _root_barrier(root_path, root_fd, root_before, "publication")
        rename_fn(parent, temporary, parent, target)
        temporary_created = False
        published = True
        result = {
            "path": path,
            "rawSha256": sha256(raw),
            "bytes": len(raw),
            "mode": "0600",
            "ownerUid": info.st_uid,
            "linkCount": info.st_nlink,
            **(
                {"contentSha256": payload["contentBinding"]["sha256"]}
                if "contentBinding" in payload
                else {}
            ),
        }
        source_identity = (info.st_dev, info.st_ino)
        os.fsync(parent)
        if namespace is not None:
            namespace.install_published(slot or "", result, source_identity)
        else:
            _root_barrier(root_path, root_fd, root_before, "publication")
            local_hold = HeldFile(
                root_fd,
                result,
                owned,
            )
            require(
                (local_hold.before.st_dev, local_hold.before.st_ino)
                == source_identity,
                "E_CURRENT_PATH_IDENTITY",
                "publication",
            )
            local_hold.barrier()
        return result
    except BaseException as error:
        if published:
            raise ReadbackError(
                "E_PUBLICATION_DURABILITY_UNCERTAIN",
                "publication",
                consumed=True,
                uncertain=True,
            ) from error
        raise
    finally:
        cleanup_errors: list[BaseException] = []
        if local_hold is not None:
            try:
                local_hold.close()
            except BaseException as error:
                cleanup_errors.append(error)
        if temporary_created and parent >= 0 and temporary:
            try:
                os.unlink(temporary, dir_fd=parent)
                os.fsync(parent)
            except BaseException as error:
                cleanup_errors.append(error)
        if fd >= 0 and fd not in owned:
            try:
                orphaned_owner = [fd]
                _close_owned_fds(orphaned_owner)
            except BaseException as error:
                cleanup_errors.append(error)
        try:
            _close_owned_fds(owned)
        except BaseException as error:
            cleanup_errors.append(error)
        if cleanup_errors:
            raise cleanup_errors[0]


def complete_pre_manifest_barrier(
    snapshot: FrozenSnapshot,
    namespace: ReadbackNamespace,
    name: str,
    *,
    receipt_required: bool,
) -> None:
    require(
        name
        in {
            "complete_snapshot_and_claim_immediately_before_receipt",
            "complete_snapshot_claim_and_receipt_after_receipt",
            (
                "complete_snapshot_claim_and_receipt_"
                "immediately_before_manifest_publication"
            ),
        },
        "E_BARRIER",
        "publication_barrier",
    )
    snapshot.final_barrier()
    namespace.publication_barrier(receipt_required=receipt_required)


def execute(
    root: Path = ROOT,
    snapshot_factory: Callable[[Path], FrozenSnapshot] = FrozenSnapshot,
    namespace_factory: Callable[[Path], ReadbackNamespace] = ReadbackNamespace,
) -> dict[str, Any]:
    umask_guard = _RestrictedUmask(0o077)
    claim_attempted = False
    claim_durable = False
    publication_attempted = False
    receipt_published = False
    snapshot: FrozenSnapshot | None = None
    namespace: ReadbackNamespace | None = None
    claim_creation_fd = -1
    pending_error: ReadbackError | None = None
    try:
        umask_guard.activate()
        try:
            package = preflight()
            readback_attempt_id = secrets.token_hex(16)
            namespace = namespace_factory(root)
            namespace.preclaim_barrier()
            claim_attempted = True
            claim, claim_creation_fd = create_readback_claim(
                root,
                readback_attempt_id,
                package["authorityBinding"],
                namespace.root_fd,
                namespace.owned_fds,
            )
            claim_durable = True
            try:
                namespace.hold_claim(claim, claim_creation_fd)
            finally:
                claim_creation_fd = -1
            snapshot = snapshot_factory(root)
            first = verify_snapshot(snapshot)
            snapshot.refresh()
            second = verify_snapshot(snapshot)
            require(first == second, "E_PASS_DRIFT", "verification")
            barrier_names = list(
                package["permit"]["verificationContract"][
                    "retainedFdPreManifestBarriers"
                ]
            )
            require(
                barrier_names
                == [
                    (
                        "complete_snapshot_and_claim_"
                        "immediately_before_receipt"
                    ),
                    (
                        "complete_snapshot_claim_and_receipt_"
                        "after_receipt"
                    ),
                    (
                        "complete_snapshot_claim_and_receipt_"
                        "immediately_before_manifest_publication"
                    ),
                ],
                "E_BARRIER",
                "publication_barrier",
            )
            complete_pre_manifest_barrier(
                snapshot,
                namespace,
                barrier_names[0],
                receipt_required=False,
            )
            receipt = content_bound(
                {
                    "documentType": "aetherlink.wave14-source-acquisition-readback",
                    "schemaVersion": "1.0",
                    "status": (
                        "wave14_acquisition_retained_snapshot_"
                        "independently_read_back"
                    ),
                    "readbackAttemptId": readback_attempt_id,
                    "acquisitionAttemptId": PERMIT.ATTEMPT_ID,
                    "authorityBinding": package["authorityBinding"],
                    "readbackClaim": claim,
                    "verificationPassCount": 2,
                    "requiredRetainedFdPreManifestBarrierCount": 3,
                    "completedRetainedFdPreManifestBarrierCountAtReceipt": 1,
                    "remainingRetainedFdPreManifestBarrierCount": 2,
                    "retainedFdPreManifestBarriers": barrier_names,
                    "allRequiredPreManifestBarriersRequired": True,
                    "allRequiredPreManifestBarriersCompleteAtReceipt": False,
                    "currentPathIdentityGuaranteedThroughManifestPublication": False,
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
                    "completionAppliesToRetainedSnapshot": True,
                    "verified": second,
                    "offline": True,
                    "networkRequestAttemptCount": 0,
                    "sourceAcquisitionCount": 0,
                    "sourceExtracted": False,
                    "sourceLoadedOrExecuted": False,
                    "compiled": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
            publication_attempted = True
            receipt_result = atomic_publish(
                root,
                PERMIT.READBACK_RECEIPT_PATH,
                receipt,
                namespace=namespace,
                slot="receipt",
            )
            receipt_published = True
            complete_pre_manifest_barrier(
                snapshot,
                namespace,
                barrier_names[1],
                receipt_required=True,
            )
            manifest = content_bound(
                {
                    "documentType": (
                        "aetherlink.wave14-source-acquisition-readback-manifest"
                    ),
                    "schemaVersion": "1.0",
                    "status": (
                        "wave14_acquisition_retained_snapshot_"
                        "readback_publication_complete"
                    ),
                    "readbackAttemptId": readback_attempt_id,
                    "acquisitionAttemptId": PERMIT.ATTEMPT_ID,
                    "authorityBinding": package["authorityBinding"],
                    "receipt": receipt_result,
                    "completedPreManifestCurrentPathIdentityBarrierCount": 3,
                    "retainedFdPreManifestBarriers": barrier_names,
                    "allRequiredPreManifestBarriersCompleted": True,
                    "lastCurrentPathIdentityBarrierTiming": (
                        "immediately_before_manifest_publication"
                    ),
                    "currentPathIdentityGuaranteedThroughManifestPublication": False,
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
                    "completionAppliesToRetainedSnapshot": True,
                    "manifestWrittenLast": True,
                    "offline": True,
                    "networkRequestAttemptCount": 0,
                    "sourceAcquisitionCount": 0,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
            success_result = {
                "status": (
                    "wave14_acquisition_retained_snapshot_"
                    "readback_publication_complete"
                ),
                "readbackAttemptId": readback_attempt_id,
                "acquisitionAttemptId": PERMIT.ATTEMPT_ID,
                "lastCurrentPathIdentityBarrierTiming": (
                    "immediately_before_manifest_publication"
                ),
                "currentPathIdentityGuaranteedThroughManifestPublication": False,
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
                "completionAppliesToRetainedSnapshot": True,
                "networkRequestAttemptCount": 0,
                "sourceAcquisitionCount": 0,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            }
            complete_pre_manifest_barrier(
                snapshot,
                namespace,
                barrier_names[2],
                receipt_required=True,
            )
            publication_attempted = True
            atomic_publish(
                root,
                PERMIT.READBACK_MANIFEST_PATH,
                manifest,
                namespace=namespace,
                slot="manifest",
            )
            return success_result
        except BaseException as error:
            if isinstance(error, ReadbackError):
                original = error
            else:
                original = ReadbackError("E_INTERNAL", "readback")
            if original.code == "E_CONSUMED":
                pending_error = original
                raise
            if publication_attempted or receipt_published:
                pending_error = ReadbackError(
                    "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
                    "terminal_state",
                    consumed=True,
                    uncertain=True,
                )
            elif claim_attempted and not claim_durable:
                if original.code == "E_CLAIM_NOT_CREATED":
                    pending_error = original
                    raise
                pending_error = ReadbackError(
                    "E_CLAIM_STATE_UNCERTAIN",
                    "claim",
                    consumed=True,
                    uncertain=True,
                )
            elif original.uncertain:
                pending_error = ReadbackError(
                    "E_CONSUMED_STATE_UNCERTAIN",
                    original.phase,
                    consumed=True,
                    uncertain=True,
                )
            else:
                pending_error = ReadbackError(
                    original.code,
                    original.phase,
                    consumed=claim_durable or original.consumed,
                    uncertain=original.uncertain,
                )
            raise pending_error from error
        finally:
            cleanup_errors: list[BaseException] = []
            if claim_creation_fd >= 0:
                try:
                    if (
                        namespace is not None
                        and claim_creation_fd in namespace.owned_fds
                    ):
                        _close_owned_fd(
                            namespace.owned_fds,
                            claim_creation_fd,
                        )
                    else:
                        temporary_owner = [claim_creation_fd]
                        _close_owned_fds(temporary_owner)
                except BaseException as error:
                    cleanup_errors.append(error)
            if snapshot is not None:
                try:
                    snapshot.close()
                except BaseException as error:
                    cleanup_errors.append(error)
            if namespace is not None:
                try:
                    namespace.close()
                except BaseException as error:
                    cleanup_errors.append(error)
            try:
                umask_guard.restore()
            except BaseException as error:
                cleanup_errors.append(error)
            if cleanup_errors:
                terminal_uncertain = (
                    publication_attempted
                    or receipt_published
                    or (claim_attempted and not claim_durable)
                    or (
                        pending_error.uncertain
                        if pending_error is not None
                        else False
                    )
                )
                pending_error = ReadbackError(
                    "E_CLEANUP_STATE_UNCERTAIN",
                    "cleanup",
                    consumed=(
                        claim_attempted
                        or claim_durable
                        or (
                            pending_error.consumed
                            if pending_error is not None
                            else False
                        )
                    ),
                    uncertain=terminal_uncertain,
                )
                raise pending_error from cleanup_errors[0]
    finally:
        if umask_guard.active:
            try:
                umask_guard.restore()
            except BaseException as error:
                raise ReadbackError(
                    "E_CLEANUP_STATE_UNCERTAIN",
                    "cleanup",
                    consumed=(
                        pending_error.consumed
                        if pending_error is not None
                        else False
                    ),
                    uncertain=(
                        pending_error.uncertain
                        if pending_error is not None
                        else False
                    ),
                ) from error


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise ReadbackError("E_ARGUMENT", "cli")


def _post_success_reporting_failure() -> dict[str, Any]:
    return {
        "documentType": "aetherlink.wave14-acquisition-readback-error",
        "schemaVersion": "1.0",
        "status": "consumed_success_reporting_failed",
        "failureCode": "E_POST_SUCCESS_REPORTING",
        "failurePhase": "reporting",
        "retryAllowed": False,
        "readbackPublicationComplete": True,
        "completionAppliesToRetainedSnapshot": True,
        "networkAuthorized": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    execute_success_recorded = False
    try:
        parser = Parser(add_help=False)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--preflight", action="store_true")
        group.add_argument("--execute", action="store_true")
        args = parser.parse_args(argv)
        if args.preflight:
            preflight()
            result = {
                "documentType": "aetherlink.wave14-acquisition-readback-preflight",
                "schemaVersion": "1.0",
                "status": "authorized_not_consumed",
                "acquisitionAttemptId": PERMIT.ATTEMPT_ID,
                "frozenAcquisitionInputOpened": False,
                "networkRequestAttemptCount": 0,
                "fileWriteCount": 0,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            }
        else:
            result = execute()
            execute_success_recorded = True
        sys.stdout.buffer.write(canonical_bytes(result))
        return 0
    except ReadbackError as error:
        if execute_success_recorded:
            sys.stdout.buffer.write(
                canonical_bytes(_post_success_reporting_failure())
            )
            return 1
        if error.code == "E_CONSUMED":
            status = "already_consumed"
        elif error.uncertain:
            status = "consumed_terminal_state_uncertain"
        elif error.consumed:
            status = "consumed_failure_no_retry"
        else:
            status = "failed_closed_not_consumed"
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": "aetherlink.wave14-acquisition-readback-error",
                    "schemaVersion": "1.0",
                    "status": status,
                    "failureCode": error.code,
                    "failurePhase": error.phase,
                    "retryAllowed": False,
                    "networkAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        if execute_success_recorded:
            sys.stdout.buffer.write(
                canonical_bytes(_post_success_reporting_failure())
            )
            return 1
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": "aetherlink.wave14-acquisition-readback-error",
                    "schemaVersion": "1.0",
                    "status": "failed_closed_not_consumed",
                    "failureCode": "E_INTERNAL",
                    "failurePhase": "internal",
                    "retryAllowed": False,
                    "networkAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
