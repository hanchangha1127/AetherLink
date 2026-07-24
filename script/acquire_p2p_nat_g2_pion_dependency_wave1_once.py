#!/usr/bin/env python3
"""Acquire the exact G2 Pion dependency wave-one ZIP set once.

The default mode is a read-only preflight. ``--execute`` is intentionally
available only under the separately versioned permit validated by the pinned
checker. The runner never invokes Go, Git, a shell, a package manager, a
compiler, or dependency source code.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import closing, contextmanager
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import signal
import ssl
import stat
import struct
import sys
import threading
import time
import types
from typing import Any, BinaryIO, Mapping, Sequence
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-execution-permit-v1.json"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v1.py"
)
EXPECTED_CHECKER_RAW_SHA256 = "014eaf714c41753e328679f1cc4f2ff0fe644039dbc1156406ad547a9f22bbe5"
MAXIMUM_CHECKER_BYTES = 2 * 1024 * 1024

EXPECTED_PERMIT_STATUS = (
    "wave1_dependency_source_acquisition_authorized_not_consumed"
)
EXPECTED_PERMIT_RESULT = (
    "exact_19_public_proxy_zip_requests_authorized_once_not_executed"
)
EXPECTED_PERMIT_NEXT_ACTION = (
    "execute_bound_dependency_source_wave1_once"
)

CLAIM_NAME = ".wave-1-v1.claim"
STAGING_PREFIX = ".wave-1-v1-staging-"
DEPENDENCY_PARENT = PurePosixPath(
    "build/offline-source/pion-ice-v4.3.0/dependencies"
)
WAVE_PARENT_NAME = "wave-1"
FINAL_DIRECTORY_NAME = "accepted"
SUCCESS_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-receipt-v1.json"
)
FAILURE_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave1-manifest-v1.json"
)

STREAM_CHUNK_BYTES = 64 * 1024
RENAME_EXCL = 0x00000004
ZIP_EOCD = struct.Struct("<4s4H2LH")
ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
ZIP_LOCAL_HEADER = struct.Struct("<4s5H3L2H")
ZIP_LOCAL_HEADER_SIGNATURE = b"PK\x03\x04"
ZIP_DATA_DESCRIPTOR = struct.Struct("<3L")
ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE = struct.Struct("<4s3L")
ZIP_DATA_DESCRIPTOR_SIGNATURE = b"PK\x07\x08"
ZIP64_EXTRA_FIELD_ID = 0x0001
ALLOWED_ZIP_FLAGS = 0x0008 | 0x0800
ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
UNIX_TYPE_MASK = 0o170000
UNIX_REGULAR = 0o100000
UNIX_SPECIAL_PERMISSION_BITS = 0o7000
DOS_DIRECTORY = 0x10


class AcquisitionFailure(RuntimeError):
    """A bounded failure safe to map to a persisted reason code."""

    def __init__(
        self,
        code: str,
        phase: str,
        *,
        tuple_id: str | None = None,
        observations: Mapping[str, int] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase
        self.tuple_id = tuple_id
        self.observations = dict(observations or {})


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AcquisitionFailure("E_REDIRECT", "response")


def require(condition: bool, code: str, phase: str) -> None:
    if not condition:
        raise AcquisitionFailure(code, phase)


def require_isolated_interpreter() -> None:
    require(sys.flags.isolated == 1, "E_INTERPRETER", "preflight")
    require(sys.dont_write_bytecode, "E_INTERPRETER", "preflight")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def strict_json(raw: bytes, label: str) -> Any:
    if not raw.endswith(b"\n") or raw.endswith(b"\r\n") or b"\r" in raw:
        raise AcquisitionFailure("E_JSON_ENCODING", "preflight")

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise AcquisitionFailure("E_JSON_DUPLICATE_KEY", "preflight")
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        raise AcquisitionFailure("E_JSON_NONFINITE", "preflight")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except AcquisitionFailure:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionFailure("E_JSON_PARSE", "preflight") from error


def directory_open_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def file_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def create_file_flags() -> int:
    return (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )


def create_download_file_flags() -> int:
    return (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )


def validate_regular_descriptor(
    fd: int,
    label: str,
    *,
    owner_only: bool | None = None,
) -> os.stat_result:
    info = os.fstat(fd)
    require(stat.S_ISREG(info.st_mode), "E_FILESYSTEM_TYPE", "filesystem")
    require(info.st_uid == os.getuid(), "E_FILESYSTEM_OWNER", "filesystem")
    require(info.st_nlink == 1, "E_FILESYSTEM_LINK", "filesystem")
    require(
        stat.S_IMODE(info.st_mode) & 0o022 == 0,
        "E_FILESYSTEM_MODE",
        "filesystem",
    )
    if owner_only is True:
        require(
            stat.S_IMODE(info.st_mode) == 0o600,
            "E_FILESYSTEM_MODE",
            "filesystem",
        )
    return info


def validate_directory_descriptor(
    fd: int,
    label: str,
    *,
    owner_only: bool = False,
) -> os.stat_result:
    info = os.fstat(fd)
    require(stat.S_ISDIR(info.st_mode), "E_FILESYSTEM_TYPE", "filesystem")
    require(info.st_uid == os.getuid(), "E_FILESYSTEM_OWNER", "filesystem")
    require(
        stat.S_IMODE(info.st_mode) & 0o022 == 0,
        "E_FILESYSTEM_MODE",
        "filesystem",
    )
    if owner_only:
        require(
            stat.S_IMODE(info.st_mode) == 0o700,
            "E_FILESYSTEM_MODE",
            "filesystem",
        )
    return info


def read_all_fd(fd: int, maximum_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(STREAM_CHUNK_BYTES, maximum_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > maximum_bytes:
            raise AcquisitionFailure("E_FILE_TOO_LARGE", "preflight")
        chunks.append(chunk)
    return b"".join(chunks)


def read_stable_regular_file(path: Path, maximum_bytes: int) -> bytes:
    try:
        fd = os.open(path, file_open_flags())
    except OSError as error:
        raise AcquisitionFailure("E_TRUST_ROOT_READ", "preflight") from error
    try:
        before = validate_regular_descriptor(fd, str(path))
        require(before.st_size <= maximum_bytes, "E_FILE_TOO_LARGE", "preflight")
        raw = read_all_fd(fd, maximum_bytes)
        after = validate_regular_descriptor(fd, str(path))
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "E_TOCTOU",
            "preflight",
        )
        require(len(raw) == before.st_size, "E_TOCTOU", "preflight")
        return raw
    finally:
        os.close(fd)


def load_validated_authority() -> tuple[types.ModuleType, dict[str, Any]]:
    require_isolated_interpreter()
    checker_path = ROOT / CHECKER_PATH
    raw = read_stable_regular_file(checker_path, MAXIMUM_CHECKER_BYTES)
    require(
        sha256_bytes(raw) == EXPECTED_CHECKER_RAW_SHA256,
        "E_CHECKER_IDENTITY",
        "preflight",
    )
    module = types.ModuleType("g2_dependency_wave1_permit_checker_trust_root")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(checker_path),
            "__loader__": None,
            "__package__": None,
        }
    )
    try:
        exec(
            compile(
                raw,
                CHECKER_PATH,
                "exec",
                flags=0,
                dont_inherit=True,
                optimize=0,
            ),
            module.__dict__,
            module.__dict__,
        )
        result = module.validate_repository(ROOT)
    except AcquisitionFailure:
        raise
    except Exception as error:
        raise AcquisitionFailure("E_PERMIT_VALIDATION", "preflight") from error
    require(isinstance(result, dict), "E_PERMIT_VALIDATION", "preflight")
    permit = result.get("permit")
    require(isinstance(permit, dict), "E_PERMIT_VALIDATION", "preflight")
    require(
        permit.get("status") == EXPECTED_PERMIT_STATUS,
        "E_PERMIT_STATE",
        "preflight",
    )
    require(
        permit.get("result") == EXPECTED_PERMIT_RESULT,
        "E_PERMIT_STATE",
        "preflight",
    )
    require(
        permit.get("nextAction") == EXPECTED_PERMIT_NEXT_ACTION,
        "E_PERMIT_STATE",
        "preflight",
    )
    return module, result


def open_root_directory(expected_identity: Any) -> int:
    require(
        isinstance(expected_identity, Mapping)
        and set(expected_identity) == {"device", "inode", "ownerUid", "mode"},
        "E_FILESYSTEM_ROOT_IDENTITY",
        "filesystem",
    )
    require(
        all(type(expected_identity[key]) is int for key in expected_identity),
        "E_FILESYSTEM_ROOT_IDENTITY",
        "filesystem",
    )
    require(
        expected_identity["device"] >= 0
        and expected_identity["inode"] > 0
        and expected_identity["ownerUid"] == os.getuid()
        and expected_identity["mode"] & 0o022 == 0,
        "E_FILESYSTEM_ROOT_IDENTITY",
        "filesystem",
    )
    try:
        fd = os.open(ROOT, directory_open_flags())
    except OSError as error:
        raise AcquisitionFailure("E_FILESYSTEM_ROOT", "filesystem") from error
    try:
        info = validate_directory_descriptor(fd, "repository root")
        observed_identity = {
            "device": info.st_dev,
            "inode": info.st_ino,
            "ownerUid": info.st_uid,
            "mode": stat.S_IMODE(info.st_mode),
        }
        require(
            observed_identity == dict(expected_identity),
            "E_FILESYSTEM_ROOT_IDENTITY",
            "filesystem",
        )
        return fd
    except Exception:
        os.close(fd)
        raise


def validate_relative_path(path: str) -> tuple[str, ...]:
    require(isinstance(path, str), "E_PATH", "filesystem")
    pure = PurePosixPath(path)
    require(not pure.is_absolute(), "E_PATH", "filesystem")
    require("\\" not in path and "\x00" not in path, "E_PATH", "filesystem")
    parts = pure.parts
    require(bool(parts), "E_PATH", "filesystem")
    require(all(part not in {"", ".", ".."} for part in parts), "E_PATH", "filesystem")
    return parts


def open_directory_chain(
    root_fd: int,
    parts: Sequence[str],
    *,
    create: bool,
    owner_only_from: int | None = None,
) -> int:
    current = os.dup(root_fd)
    try:
        for index, part in enumerate(parts):
            try:
                child = os.open(part, directory_open_flags(), dir_fd=current)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError:
                    pass
                os.fsync(current)
                child = os.open(part, directory_open_flags(), dir_fd=current)
            validate_directory_descriptor(
                child,
                part,
                owner_only=owner_only_from is not None and index >= owner_only_from,
            )
            os.close(current)
            current = child
        return current
    except Exception:
        os.close(current)
        raise


def entry_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False
    except OSError as error:
        raise AcquisitionFailure("E_FILESYSTEM_STAT", "filesystem") from error


def list_names(directory_fd: int) -> list[str]:
    try:
        return sorted(os.listdir(directory_fd))
    except OSError as error:
        raise AcquisitionFailure("E_FILESYSTEM_LIST", "filesystem") from error


def write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise AcquisitionFailure("E_FILESYSTEM_WRITE", "filesystem")
        view = view[written:]


def close_quietly(fd: int) -> None:
    if fd < 0:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def create_exclusive_file(
    directory_fd: int,
    name: str,
    payload: bytes,
    *,
    maximum_bytes: int,
) -> str:
    require(len(payload) <= maximum_bytes, "E_RECEIPT_TOO_LARGE", "publication")
    try:
        fd = os.open(name, create_file_flags(), 0o600, dir_fd=directory_fd)
    except FileExistsError as error:
        raise AcquisitionFailure("E_OUTPUT_EXISTS", "publication") from error
    except OSError as error:
        raise AcquisitionFailure("E_FILESYSTEM_CREATE", "publication") from error
    try:
        os.fchmod(fd, 0o600)
        write_all(fd, payload)
        os.fsync(fd)
        info = validate_regular_descriptor(fd, name, owner_only=True)
        require(info.st_size == len(payload), "E_FILESYSTEM_WRITE", "publication")
    finally:
        os.close(fd)
    os.fsync(directory_fd)
    return sha256_bytes(payload)


def create_claim(
    parent_fd: int,
    permit: Mapping[str, Any],
) -> tuple[str, str]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = canonical_json_bytes(
        {
            "claimType": "aetherlink.g2-pion-dependency-wave1-one-use-claim",
            "schemaVersion": "1.0",
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "decisionContentSha256": permit["decisionBinding"]["contentSha256"],
            "createdAt": now,
            "rule": "claim_persists_after_any_network_attempt_and_blocks_retry",
        }
    )
    digest = create_exclusive_file(
        parent_fd,
        CLAIM_NAME,
        payload,
        maximum_bytes=64 * 1024,
    )
    return now, digest


def create_staging_directory(parent_fd: int) -> str:
    for _ in range(8):
        name = STAGING_PREFIX + secrets.token_hex(12)
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            fd = os.open(name, directory_open_flags(), dir_fd=parent_fd)
            try:
                validate_directory_descriptor(fd, name, owner_only=True)
            finally:
                os.close(fd)
            return name
        except FileExistsError:
            continue
        except OSError as error:
            raise AcquisitionFailure("E_STAGING_CREATE", "filesystem") from error
    raise AcquisitionFailure("E_STAGING_COLLISION", "filesystem")


def build_exact_opener():
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return build_opener(
        ProxyHandler({}),
        RejectRedirects(),
        HTTPSHandler(context=context),
    )


def exact_header_values(headers: Any, name: str) -> list[str]:
    values = headers.get_all(name)
    if values is None:
        return []
    return [str(value).strip() for value in values]


def validate_response_headers(
    response: Any,
    expected_url: str,
    maximum_bytes: int,
) -> int | None:
    require(getattr(response, "status", None) == 200, "E_HTTP_STATUS", "response")
    require(response.geturl() == expected_url, "E_REDIRECT", "response")
    headers = response.headers
    for forbidden in (
        "Location",
        "WWW-Authenticate",
        "Proxy-Authenticate",
        "Set-Cookie",
    ):
        require(
            not exact_header_values(headers, forbidden),
            "E_FORBIDDEN_RESPONSE_HEADER",
            "response",
        )
    encodings = exact_header_values(headers, "Content-Encoding")
    require(
        len(encodings) <= 1
        and (not encodings or encodings[0].lower() == "identity"),
        "E_CONTENT_ENCODING",
        "response",
    )
    content_types = exact_header_values(headers, "Content-Type")
    require(len(content_types) == 1, "E_CONTENT_TYPE", "response")
    media_type = content_types[0].split(";", 1)[0].strip().lower()
    require(
        media_type in {"application/zip", "application/octet-stream"},
        "E_CONTENT_TYPE",
        "response",
    )
    lengths = exact_header_values(headers, "Content-Length")
    require(len(lengths) <= 1, "E_CONTENT_LENGTH", "response")
    if not lengths:
        return None
    require(lengths[0].isdigit(), "E_CONTENT_LENGTH", "response")
    length = int(lengths[0])
    require(0 < length <= maximum_bytes, "E_CONTENT_LENGTH", "response")
    return length


def set_response_io_timeout(response: Any, timeout_seconds: float) -> None:
    require(timeout_seconds > 0, "E_REQUEST_DEADLINE", "download")
    attribute_paths = (
        (),
        ("fp",),
        ("fp", "raw"),
        ("fp", "raw", "_sock"),
    )
    for attributes in attribute_paths:
        target = response
        for attribute in attributes:
            target = getattr(target, attribute, None)
            if target is None:
                break
        if target is None:
            continue
        setter = getattr(target, "settimeout", None)
        if callable(setter):
            try:
                setter(timeout_seconds)
            except (OSError, ValueError) as error:
                raise AcquisitionFailure(
                    "E_TRANSPORT",
                    "download",
                ) from error
            return
    raise AcquisitionFailure("E_TRANSPORT", "download")


def validate_hard_deadline_environment() -> None:
    require(
        hasattr(signal, "SIGALRM")
        and hasattr(signal, "ITIMER_REAL")
        and hasattr(signal, "getitimer")
        and hasattr(signal, "setitimer"),
        "E_DEADLINE_ENVIRONMENT",
        "download",
    )
    require(
        threading.current_thread() is threading.main_thread(),
        "E_DEADLINE_ENVIRONMENT",
        "download",
    )
    try:
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        previous_handler = signal.getsignal(signal.SIGALRM)
    except (OSError, ValueError) as error:
        raise AcquisitionFailure(
            "E_DEADLINE_ENVIRONMENT",
            "download",
        ) from error
    require(
        previous_timer == (0.0, 0.0) and previous_handler == signal.SIG_DFL,
        "E_DEADLINE_ENVIRONMENT",
        "download",
    )


def restore_hard_deadline_state(
    previous_handler: Any,
    *,
    tuple_id: str | None,
    phase: str = "download",
) -> None:
    cleanup_error: Exception | None = None
    disarmed = False
    for _attempt in range(2):
        try:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            disarmed = True
            break
        except (OSError, ValueError) as error:
            if cleanup_error is None:
                cleanup_error = error
    if disarmed:
        try:
            signal.signal(signal.SIGALRM, previous_handler)
        except (OSError, ValueError) as error:
            if cleanup_error is None:
                cleanup_error = error
    if cleanup_error is not None:
        raise AcquisitionFailure(
            "E_DEADLINE_ENVIRONMENT",
            phase,
            tuple_id=tuple_id,
        ) from cleanup_error


@contextmanager
def hard_wall_clock_request_deadline(
    *,
    request_deadline: float,
    wave_deadline: float,
    tuple_id: str | None,
    phase: str = "download",
):
    validate_hard_deadline_environment()
    now = time.monotonic()
    if now >= wave_deadline:
        raise AcquisitionFailure(
            "E_WAVE_DEADLINE",
            phase,
            tuple_id=tuple_id,
        )
    if now >= request_deadline:
        raise AcquisitionFailure(
            "E_REQUEST_DEADLINE",
            phase,
            tuple_id=tuple_id,
        )
    deadline = min(request_deadline, wave_deadline)
    failure_code = (
        "E_WAVE_DEADLINE"
        if wave_deadline <= request_deadline
        else "E_REQUEST_DEADLINE"
    )

    def expire_request(_signal_number, _frame) -> None:
        raise AcquisitionFailure(
            failure_code,
            phase,
            tuple_id=tuple_id,
        )

    previous_handler = signal.getsignal(signal.SIGALRM)
    installed = False
    try:
        signal.signal(signal.SIGALRM, expire_request)
        installed = True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AcquisitionFailure(
                failure_code,
                phase,
                tuple_id=tuple_id,
            )
        signal.setitimer(signal.ITIMER_REAL, remaining)
    except AcquisitionFailure:
        if installed:
            restore_hard_deadline_state(
                previous_handler,
                tuple_id=tuple_id,
                phase=phase,
            )
        raise
    except (OSError, ValueError) as error:
        if installed:
            restore_hard_deadline_state(
                previous_handler,
                tuple_id=tuple_id,
                phase=phase,
            )
        raise AcquisitionFailure(
            "E_DEADLINE_ENVIRONMENT",
            phase,
            tuple_id=tuple_id,
        ) from error
    try:
        yield
    finally:
        restore_hard_deadline_state(
            previous_handler,
            tuple_id=tuple_id,
            phase=phase,
        )


def download_exact_once(
    opener: Any,
    item: Mapping[str, Any],
    output_fd: int,
    *,
    maximum_bytes: int,
    aggregate_before: int,
    maximum_aggregate_bytes: int,
    per_request_timeout_seconds: float,
    wave_deadline: float,
) -> dict[str, Any]:
    tuple_id = str(item["tupleId"])
    url = str(item["url"])
    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/zip",
            "Accept-Encoding": "identity",
            "User-Agent": "AetherLink-G2-Dependency-Source-Intake/1",
        },
    )
    digest = hashlib.sha256()
    total = 0
    request_deadline = time.monotonic() + per_request_timeout_seconds
    try:
        with hard_wall_clock_request_deadline(
            request_deadline=request_deadline,
            wave_deadline=wave_deadline,
            tuple_id=tuple_id,
        ):
            open_timeout = min(request_deadline, wave_deadline) - time.monotonic()
            require(open_timeout > 0, "E_REQUEST_DEADLINE", "download")
            with closing(opener.open(request, timeout=open_timeout)) as response:
                declared = validate_response_headers(response, url, maximum_bytes)
                read_one = getattr(response, "read1", None)
                require(callable(read_one), "E_TRANSPORT", "download")
                while True:
                    now = time.monotonic()
                    if now >= wave_deadline:
                        raise AcquisitionFailure(
                            "E_WAVE_DEADLINE",
                            "download",
                            tuple_id=tuple_id,
                        )
                    if now >= request_deadline:
                        raise AcquisitionFailure(
                            "E_REQUEST_DEADLINE",
                            "download",
                            tuple_id=tuple_id,
                        )
                    set_response_io_timeout(
                        response,
                        min(wave_deadline, request_deadline) - now,
                    )
                    chunk = read_one(
                        min(STREAM_CHUNK_BYTES, maximum_bytes + 1 - total)
                    )
                    now = time.monotonic()
                    if now >= wave_deadline:
                        raise AcquisitionFailure(
                            "E_WAVE_DEADLINE",
                            "download",
                            tuple_id=tuple_id,
                        )
                    if now >= request_deadline:
                        raise AcquisitionFailure(
                            "E_REQUEST_DEADLINE",
                            "download",
                            tuple_id=tuple_id,
                        )
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > maximum_bytes:
                        raise AcquisitionFailure(
                            "E_RESPONSE_TOO_LARGE",
                            "download",
                            tuple_id=tuple_id,
                            observations={"responseBytes": total},
                        )
                    if aggregate_before + total > maximum_aggregate_bytes:
                        raise AcquisitionFailure(
                            "E_AGGREGATE_RESPONSE_TOO_LARGE",
                            "download",
                            tuple_id=tuple_id,
                            observations={
                                "aggregateBytes": aggregate_before + total
                            },
                        )
                    write_all(output_fd, chunk)
                    digest.update(chunk)
                if declared is not None and declared != total:
                    raise AcquisitionFailure(
                        "E_CONTENT_LENGTH_MISMATCH",
                        "download",
                        tuple_id=tuple_id,
                        observations={"responseBytes": total},
                    )
    except AcquisitionFailure:
        raise
    except HTTPError as error:
        raise AcquisitionFailure(
            "E_HTTP_STATUS",
            "download",
            tuple_id=tuple_id,
            observations={"httpStatus": int(error.code)},
        ) from error
    except (URLError, TimeoutError, ssl.SSLError, OSError) as error:
        raise AcquisitionFailure(
            "E_TRANSPORT",
            "download",
            tuple_id=tuple_id,
        ) from error
    require(total > 0, "E_EMPTY_RESPONSE", "download")
    os.fsync(output_fd)
    info = validate_regular_descriptor(output_fd, tuple_id, owner_only=True)
    require(info.st_size == total, "E_FILESYSTEM_WRITE", "download")
    return {"rawByteSize": total, "rawSha256": digest.hexdigest()}


def validate_zip_name(
    name: str,
    *,
    expected_prefix: str,
    limits: Mapping[str, Any],
) -> tuple[str, ...]:
    require(name != "", "E_ZIP_PATH", "zip")
    require("\x00" not in name and "\n" not in name and "\r" not in name, "E_ZIP_PATH", "zip")
    require("\\" not in name and ":" not in name, "E_ZIP_PATH", "zip")
    require(not name.startswith("/") and not name.endswith("/"), "E_ZIP_PATH", "zip")
    require(unicodedata.normalize("NFC", name) == name, "E_ZIP_PATH", "zip")
    encoded = name.encode("utf-8")
    require(len(encoded) <= limits["maximumPathBytes"], "E_ZIP_PATH", "zip")
    parts = tuple(name.split("/"))
    require(
        1 <= len(parts) <= limits["maximumPathComponents"],
        "E_ZIP_PATH",
        "zip",
    )
    require(all(part not in {"", ".", ".."} for part in parts), "E_ZIP_PATH", "zip")
    require(
        all(len(part.encode("utf-8")) <= limits["maximumComponentBytes"] for part in parts),
        "E_ZIP_PATH",
        "zip",
    )
    require(name.startswith(expected_prefix), "E_MODULE_PREFIX", "zip")
    return parts


def parse_extra_fields(extra: bytes) -> None:
    cursor = 0
    while cursor < len(extra):
        require(cursor + 4 <= len(extra), "E_ZIP_EXTRA", "zip")
        field_id, size = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        require(cursor + size <= len(extra), "E_ZIP_EXTRA", "zip")
        require(field_id != ZIP64_EXTRA_FIELD_ID, "E_ZIP64", "zip")
        cursor += size


def validate_eocd(
    fd: int,
    size: int,
    expected_entries: int,
    maximum_cd: int,
) -> int:
    require(size >= ZIP_EOCD.size, "E_ZIP_EOCD", "zip")
    raw = os.pread(fd, ZIP_EOCD.size, size - ZIP_EOCD.size)
    require(len(raw) == ZIP_EOCD.size, "E_ZIP_EOCD", "zip")
    (
        signature,
        disk_number,
        cd_disk,
        entries_on_disk,
        entries_total,
        cd_size,
        cd_offset,
        comment_length,
    ) = ZIP_EOCD.unpack(raw)
    require(signature == ZIP_EOCD_SIGNATURE, "E_ZIP_EOCD", "zip")
    require(disk_number == 0 and cd_disk == 0, "E_ZIP_MULTIDISK", "zip")
    require(entries_on_disk == entries_total == expected_entries, "E_ZIP_EOCD", "zip")
    require(comment_length == 0, "E_ZIP_COMMENT", "zip")
    require(cd_size <= maximum_cd, "E_ZIP_CENTRAL_DIRECTORY", "zip")
    require(cd_offset + cd_size == size - ZIP_EOCD.size, "E_ZIP_TRAILING", "zip")
    return cd_offset


def validate_local_header(
    fd: int,
    entry: zipfile.ZipInfo,
    *,
    next_offset: int,
) -> None:
    offset = entry.header_offset
    require(
        type(offset) is int
        and 0 <= offset
        and offset + ZIP_LOCAL_HEADER.size <= next_offset,
        "E_ZIP_LOCAL_HEADER",
        "zip",
    )
    raw = os.pread(fd, ZIP_LOCAL_HEADER.size, offset)
    require(
        len(raw) == ZIP_LOCAL_HEADER.size,
        "E_ZIP_LOCAL_HEADER",
        "zip",
    )
    (
        signature,
        extract_version,
        flags,
        compression,
        modified_time,
        modified_date,
        crc,
        compressed_size,
        uncompressed_size,
        name_length,
        extra_length,
    ) = ZIP_LOCAL_HEADER.unpack(raw)
    require(signature == ZIP_LOCAL_HEADER_SIGNATURE, "E_ZIP_LOCAL_HEADER", "zip")
    require(
        extract_version == entry.extract_version,
        "E_ZIP_LOCAL_HEADER",
        "zip",
    )
    require(flags == entry.flag_bits, "E_ZIP_LOCAL_HEADER", "zip")
    require(compression == entry.compress_type, "E_ZIP_LOCAL_HEADER", "zip")
    require(
        modified_time == getattr(entry, "_raw_time", -1),
        "E_ZIP_LOCAL_HEADER",
        "zip",
    )
    year, month, day, hour, minute, second = entry.date_time
    expected_date = ((year - 1980) << 9) | (month << 5) | day
    expected_time = (hour << 11) | (minute << 5) | (second // 2)
    require(
        modified_date == expected_date and modified_time == expected_time,
        "E_ZIP_LOCAL_HEADER",
        "zip",
    )
    variable_size = name_length + extra_length
    variable = os.pread(fd, variable_size, offset + ZIP_LOCAL_HEADER.size)
    require(len(variable) == variable_size, "E_ZIP_LOCAL_HEADER", "zip")
    local_name = variable[:name_length]
    local_extra = variable[name_length:]
    expected_name = entry.filename.encode(
        "utf-8" if entry.flag_bits & 0x0800 else "ascii"
    )
    require(local_name == expected_name, "E_ZIP_LOCAL_HEADER", "zip")
    parse_extra_fields(local_extra)

    data_offset = offset + ZIP_LOCAL_HEADER.size + variable_size
    data_end = data_offset + entry.compress_size
    require(data_end <= next_offset, "E_ZIP_LOCAL_HEADER", "zip")
    expected_sizes = (entry.CRC, entry.compress_size, entry.file_size)
    local_sizes = (crc, compressed_size, uncompressed_size)
    if entry.flag_bits & 0x0008:
        require(
            local_sizes in {(0, 0, 0), expected_sizes},
            "E_ZIP_LOCAL_HEADER",
            "zip",
        )
        descriptor_size = next_offset - data_end
        require(
            descriptor_size
            in {
                ZIP_DATA_DESCRIPTOR.size,
                ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.size,
            },
            "E_ZIP_DATA_DESCRIPTOR",
            "zip",
        )
        descriptor = os.pread(fd, descriptor_size, data_end)
        require(
            len(descriptor) == descriptor_size,
            "E_ZIP_DATA_DESCRIPTOR",
            "zip",
        )
        if descriptor_size == ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.size:
            descriptor_signature, *descriptor_values = (
                ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.unpack(descriptor)
            )
            require(
                descriptor_signature == ZIP_DATA_DESCRIPTOR_SIGNATURE,
                "E_ZIP_DATA_DESCRIPTOR",
                "zip",
            )
            observed_descriptor = tuple(descriptor_values)
        else:
            observed_descriptor = ZIP_DATA_DESCRIPTOR.unpack(descriptor)
        require(
            observed_descriptor == expected_sizes,
            "E_ZIP_DATA_DESCRIPTOR",
            "zip",
        )
    else:
        require(local_sizes == expected_sizes, "E_ZIP_LOCAL_HEADER", "zip")
        require(data_end == next_offset, "E_ZIP_LOCAL_HEADER", "zip")


def dirhash_h1(rows: Sequence[tuple[str, str]]) -> str:
    aggregate = hashlib.sha256()
    for name, file_digest in sorted(rows, key=lambda row: row[0].encode("utf-8")):
        aggregate.update(file_digest.encode("ascii"))
        aggregate.update(b"  ")
        aggregate.update(name.encode("utf-8"))
        aggregate.update(b"\n")
    return "h1:" + base64.b64encode(aggregate.digest()).decode("ascii")


def single_go_mod_h1(payload: bytes) -> str:
    file_digest = hashlib.sha256(payload).hexdigest()
    return dirhash_h1([("go.mod", file_digest)])


def parse_module_directive(go_mod: bytes) -> str:
    try:
        text = go_mod.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AcquisitionFailure("E_GO_MOD_ENCODING", "zip") from error
    found: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "module" or line.startswith("module "):
            value = line[len("module") :].strip()
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            found.append(value)
    require(len(found) == 1 and found[0] != "", "E_GO_MOD_MODULE", "zip")
    return found[0]


def inspect_module_zip(
    fd: int,
    item: Mapping[str, Any],
    limits: Mapping[str, Any],
    *,
    aggregate_entries_before: int,
    aggregate_uncompressed_before: int,
) -> dict[str, Any]:
    tuple_id = str(item["tupleId"])
    info = validate_regular_descriptor(fd, tuple_id, owner_only=True)
    os.lseek(fd, 0, os.SEEK_SET)
    expected_prefix = f"{item['module']}@{item['version']}/"
    rows: list[tuple[str, str]] = []
    names: set[str] = set()
    folded: set[str] = set()
    go_mod: bytes | None = None
    total_uncompressed = 0
    try:
        with os.fdopen(os.dup(fd), "rb") as archive_file:
            archive = zipfile.ZipFile(archive_file, "r")
            try:
                infos = archive.infolist()
                require(
                    0 < len(infos) <= limits["maximumEntriesPerArchive"],
                    "E_ZIP_ENTRY_COUNT",
                    "zip",
                )
                require(
                    aggregate_entries_before + len(infos)
                    <= limits["maximumAggregateEntries"],
                    "E_AGGREGATE_ENTRY_COUNT",
                    "zip",
                )
                central_directory_offset = validate_eocd(
                    fd,
                    info.st_size,
                    len(infos),
                    limits["maximumCentralDirectoryBytesPerArchive"],
                )
                entries_by_offset = sorted(infos, key=lambda value: value.header_offset)
                offsets = [entry.header_offset for entry in entries_by_offset]
                require(
                    len(set(offsets)) == len(offsets)
                    and all(
                        type(offset) is int
                        and 0 <= offset < central_directory_offset
                        for offset in offsets
                    ),
                    "E_ZIP_LOCAL_HEADER",
                    "zip",
                )
                next_offset_by_header = {
                    entry.header_offset: (
                        entries_by_offset[index + 1].header_offset
                        if index + 1 < len(entries_by_offset)
                        else central_directory_offset
                    )
                    for index, entry in enumerate(entries_by_offset)
                }
                for entry in infos:
                    name = entry.filename
                    validate_zip_name(
                        name,
                        expected_prefix=expected_prefix,
                        limits=limits,
                    )
                    require(name not in names, "E_ZIP_DUPLICATE", "zip")
                    names.add(name)
                    folded_name = unicodedata.normalize("NFC", name).casefold()
                    require(folded_name not in folded, "E_ZIP_CASE_COLLISION", "zip")
                    folded.add(folded_name)
                    require(not entry.is_dir(), "E_ZIP_DIRECTORY_ENTRY", "zip")
                    require(entry.flag_bits & 0x1 == 0, "E_ZIP_ENCRYPTED", "zip")
                    require(
                        entry.flag_bits & ~ALLOWED_ZIP_FLAGS == 0,
                        "E_ZIP_FLAGS",
                        "zip",
                    )
                    if not (entry.flag_bits & 0x0800):
                        require(name.isascii(), "E_ZIP_NAME_ENCODING", "zip")
                    require(
                        entry.compress_type in ALLOWED_COMPRESSION_METHODS,
                        "E_ZIP_COMPRESSION",
                        "zip",
                    )
                    require(
                        entry.create_system in {0, 3},
                        "E_ZIP_CREATOR_SYSTEM",
                        "zip",
                    )
                    parse_extra_fields(entry.extra)
                    validate_local_header(
                        fd,
                        entry,
                        next_offset=next_offset_by_header[entry.header_offset],
                    )
                    require(not entry.comment, "E_ZIP_COMMENT", "zip")
                    require(
                        0 <= entry.file_size <= limits["maximumSingleFileBytes"],
                        "E_ZIP_FILE_SIZE",
                        "zip",
                    )
                    if entry.file_size:
                        require(
                            entry.compress_size > 0
                            and entry.file_size
                            <= entry.compress_size * limits["maximumCompressionRatio"],
                            "E_ZIP_RATIO",
                            "zip",
                        )
                    mode = (entry.external_attr >> 16) & 0xFFFF
                    if entry.create_system == 3 and mode:
                        file_type = mode & UNIX_TYPE_MASK
                        require(
                            file_type in {0, UNIX_REGULAR},
                            "E_ZIP_SPECIAL_FILE",
                            "zip",
                        )
                        require(
                            mode & UNIX_SPECIAL_PERMISSION_BITS == 0,
                            "E_ZIP_SPECIAL_MODE",
                            "zip",
                        )
                    elif entry.create_system == 0:
                        require(
                            entry.external_attr & DOS_DIRECTORY == 0,
                            "E_ZIP_SPECIAL_FILE",
                            "zip",
                        )
                    digest = hashlib.sha256()
                    chunks: list[bytes] | None = (
                        [] if name == expected_prefix + "go.mod" else None
                    )
                    observed = 0
                    try:
                        with archive.open(entry, "r") as source:
                            while True:
                                chunk = source.read(
                                    min(
                                        STREAM_CHUNK_BYTES,
                                        limits["maximumSingleFileBytes"]
                                        + 1
                                        - observed,
                                    )
                                )
                                if not chunk:
                                    break
                                observed += len(chunk)
                                require(
                                    observed <= limits["maximumSingleFileBytes"],
                                    "E_ZIP_FILE_SIZE",
                                    "zip",
                                )
                                total_uncompressed += len(chunk)
                                require(
                                    total_uncompressed
                                    <= limits["maximumUncompressedBytesPerArchive"],
                                    "E_ZIP_UNCOMPRESSED",
                                    "zip",
                                )
                                require(
                                    aggregate_uncompressed_before
                                    + total_uncompressed
                                    <= limits["maximumAggregateUncompressedBytes"],
                                    "E_AGGREGATE_UNCOMPRESSED",
                                    "zip",
                                )
                                digest.update(chunk)
                                if chunks is not None:
                                    chunks.append(chunk)
                    except AcquisitionFailure:
                        raise
                    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                        raise AcquisitionFailure(
                            "E_ZIP_READ",
                            "zip",
                            tuple_id=tuple_id,
                        ) from error
                    require(observed == entry.file_size, "E_ZIP_FILE_SIZE", "zip")
                    rows.append((name, digest.hexdigest()))
                    if chunks is not None:
                        require(go_mod is None, "E_GO_MOD_DUPLICATE", "zip")
                        go_mod = b"".join(chunks)
            finally:
                archive.close()
    except AcquisitionFailure:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise AcquisitionFailure(
            "E_ZIP_FORMAT",
            "zip",
            tuple_id=tuple_id,
        ) from error
    require(go_mod is not None, "E_GO_MOD_MISSING", "zip")
    require(parse_module_directive(go_mod) == item["module"], "E_GO_MOD_MODULE", "zip")
    module_h1 = dirhash_h1(rows)
    go_mod_h1 = single_go_mod_h1(go_mod)
    require(module_h1 == item["moduleZipH1"], "E_MODULE_H1", "zip")
    require(go_mod_h1 == item["goModH1"], "E_GO_MOD_H1", "zip")
    return {
        "moduleZipH1": module_h1,
        "goModH1": go_mod_h1,
        "entryCount": len(rows),
        "uncompressedByteCount": total_uncompressed,
        "modulePrefix": expected_prefix,
    }


def link_temp_to_final(
    staging_fd: int,
    temporary_name: str,
    final_name: str,
    verified_fd: int,
) -> None:
    require(
        validate_relative_path(temporary_name) == (temporary_name,)
        and validate_relative_path(final_name) == (final_name,),
        "E_PATH",
        "filesystem",
    )
    named_entry_matches_open_file(
        staging_fd,
        temporary_name,
        verified_fd,
        expected_link_count=1,
    )
    try:
        os.link(
            temporary_name,
            final_name,
            src_dir_fd=staging_fd,
            dst_dir_fd=staging_fd,
            follow_symlinks=False,
        )
        named_entry_matches_open_file(
            staging_fd,
            temporary_name,
            verified_fd,
            expected_link_count=2,
        )
        named_entry_matches_open_file(
            staging_fd,
            final_name,
            verified_fd,
            expected_link_count=2,
        )
        os.unlink(temporary_name, dir_fd=staging_fd)
        os.fsync(staging_fd)
        named_entry_matches_open_file(
            staging_fd,
            final_name,
            verified_fd,
            expected_link_count=1,
        )
    except FileExistsError as error:
        raise AcquisitionFailure("E_OUTPUT_EXISTS", "filesystem") from error
    except OSError as error:
        raise AcquisitionFailure("E_OUTPUT_PUBLISH", "filesystem") from error


def named_entry_matches_open_file(
    directory_fd: int,
    name: str,
    open_fd: int,
    *,
    expected_link_count: int,
) -> os.stat_result:
    try:
        held = os.fstat(open_fd)
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as error:
        raise AcquisitionFailure("E_OUTPUT_IDENTITY", "filesystem") from error
    for info in (held, named):
        require(stat.S_ISREG(info.st_mode), "E_OUTPUT_IDENTITY", "filesystem")
        require(info.st_uid == os.getuid(), "E_OUTPUT_IDENTITY", "filesystem")
        require(
            stat.S_IMODE(info.st_mode) == 0o600,
            "E_OUTPUT_IDENTITY",
            "filesystem",
        )
        require(
            info.st_nlink == expected_link_count,
            "E_OUTPUT_IDENTITY",
            "filesystem",
        )
    require(
        (
            held.st_dev,
            held.st_ino,
            held.st_uid,
            stat.S_IFMT(held.st_mode),
            stat.S_IMODE(held.st_mode),
            held.st_size,
            held.st_mtime_ns,
        )
        == (
            named.st_dev,
            named.st_ino,
            named.st_uid,
            stat.S_IFMT(named.st_mode),
            stat.S_IMODE(named.st_mode),
            named.st_size,
            named.st_mtime_ns,
        ),
        "E_OUTPUT_IDENTITY",
        "filesystem",
    )
    return held


def regular_file_content_state(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def stable_open_file_sha256(
    fd: int,
    *,
    expected_size: int,
) -> tuple[str, tuple[int, ...]]:
    require(
        type(expected_size) is int and expected_size > 0,
        "E_OUTPUT_IDENTITY",
        "publication",
    )
    before = validate_regular_descriptor(fd, "held output", owner_only=True)
    require(
        before.st_size == expected_size,
        "E_OUTPUT_IDENTITY",
        "publication",
    )
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while total <= expected_size:
        chunk = os.read(
            fd,
            min(STREAM_CHUNK_BYTES, expected_size + 1 - total),
        )
        if not chunk:
            break
        total += len(chunk)
        digest.update(chunk)
    after = validate_regular_descriptor(fd, "held output", owner_only=True)
    require(
        total == expected_size
        and regular_file_content_state(before) == regular_file_content_state(after),
        "E_OUTPUT_IDENTITY",
        "publication",
    )
    return digest.hexdigest(), regular_file_content_state(after)


def validate_held_output_inventory(
    directory_fd: int,
    held_outputs: Sequence[Mapping[str, Any]],
) -> None:
    require(
        len(held_outputs) == 19,
        "E_OUTPUT_INVENTORY",
        "publication",
    )
    names = [record.get("name") for record in held_outputs]
    require(
        all(isinstance(name, str) for name in names)
        and len(set(names)) == len(names)
        and list_names(directory_fd) == sorted(names),
        "E_OUTPUT_INVENTORY",
        "publication",
    )
    snapshots: list[tuple[int, str, tuple[int, ...]]] = []
    for record in held_outputs:
        fd = record.get("fd")
        name = record.get("name")
        expected_size = record.get("rawByteSize")
        expected_sha256 = record.get("rawSha256")
        require(
            type(fd) is int
            and fd >= 0
            and isinstance(name, str)
            and type(expected_size) is int
            and expected_size > 0
            and isinstance(expected_sha256, str)
            and len(expected_sha256) == 64
            and all(character in "0123456789abcdef" for character in expected_sha256),
            "E_OUTPUT_INVENTORY",
            "publication",
        )
        named_entry_matches_open_file(
            directory_fd,
            name,
            fd,
            expected_link_count=1,
        )
        observed_sha256, state = stable_open_file_sha256(
            fd,
            expected_size=expected_size,
        )
        require(
            observed_sha256 == expected_sha256,
            "E_OUTPUT_IDENTITY",
            "publication",
        )
        named_entry_matches_open_file(
            directory_fd,
            name,
            fd,
            expected_link_count=1,
        )
        snapshots.append((fd, name, state))
    for fd, name, expected_state in snapshots:
        require(
            regular_file_content_state(os.fstat(fd)) == expected_state,
            "E_OUTPUT_IDENTITY",
            "publication",
        )
        named_entry_matches_open_file(
            directory_fd,
            name,
            fd,
            expected_link_count=1,
        )


def ordered_source_set_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "schema": "aetherlink.g2-pion-dependency-source-set-digest.v1",
                "sources": list(rows),
            }
        )
    )


def exclusive_rename_directory(
    source_parent_fd: int,
    source_name: str,
    destination_parent_fd: int,
    destination_name: str,
) -> None:
    require(
        validate_relative_path(source_name) == (source_name,)
        and validate_relative_path(destination_name) == (destination_name,),
        "E_PATH",
        "publication",
    )
    libc = ctypes.CDLL(None, use_errno=True)
    renameatx = getattr(libc, "renameatx_np", None)
    require(renameatx is not None, "E_RENAME_EXCL_UNAVAILABLE", "publication")
    renameatx.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameatx.restype = ctypes.c_int
    result = renameatx(
        source_parent_fd,
        os.fsencode(source_name),
        destination_parent_fd,
        os.fsencode(destination_name),
        RENAME_EXCL,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise AcquisitionFailure("E_OUTPUT_EXISTS", "publication")
        raise AcquisitionFailure("E_OUTPUT_PUBLISH", "publication")


def write_repo_relative_artifact(
    root_fd: int,
    relative_path: str,
    payload: bytes,
    maximum_bytes: int,
) -> str:
    parts = validate_relative_path(relative_path)
    parent_fd = open_directory_chain(root_fd, parts[:-1], create=False)
    try:
        return create_exclusive_file(
            parent_fd,
            parts[-1],
            payload,
            maximum_bytes=maximum_bytes,
        )
    finally:
        os.close(parent_fd)


def remove_staging(parent_fd: int, staging_name: str) -> None:
    try:
        staging_fd = os.open(staging_name, directory_open_flags(), dir_fd=parent_fd)
    except FileNotFoundError:
        return
    try:
        validate_directory_descriptor(staging_fd, staging_name, owner_only=True)
        for name in list_names(staging_fd):
            try:
                child = os.open(name, file_open_flags(), dir_fd=staging_fd)
            except OSError:
                continue
            try:
                validate_regular_descriptor(child, name, owner_only=True)
            finally:
                os.close(child)
            os.unlink(name, dir_fd=staging_fd)
        os.fsync(staging_fd)
    finally:
        os.close(staging_fd)
    os.rmdir(staging_name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def safe_failure_document(
    permit: Mapping[str, Any],
    failure: AcquisitionFailure,
    *,
    attempted_requests: int,
    completed_requests: int,
    claim_sha256: str | None,
    final_set_published: bool,
) -> dict[str, Any]:
    allowed_observation_keys = {
        "httpStatus",
        "responseBytes",
        "aggregateBytes",
        "completedRequests",
    }
    observations = {
        key: value
        for key, value in failure.observations.items()
        if key in allowed_observation_keys
        and type(value) is int
        and 0 <= value <= (1 << 63) - 1
    }
    return {
        "documentType": "aetherlink.g2-pion-dependency-wave1-acquisition-failure",
        "schemaVersion": "1.0",
        "status": "wave1_acquisition_failed_permit_consumed",
        "result": "no_dependency_source_set_accepted",
        "permitId": permit["permitId"],
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "failureCode": failure.code,
        "phase": failure.phase,
        "failedTupleId": failure.tuple_id,
        "safeNumericObservations": observations,
        "attemptedRequestCount": attempted_requests,
        "completedRequestCount": completed_requests,
        "acceptedArtifactCount": 0,
        "claimRetained": claim_sha256 is not None,
        "claimSha256": claim_sha256,
        "finalSetPublished": final_set_published,
        "automaticRetryAllowed": False,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": "prepare_new_versioned_wave1_recovery_decision",
    }


def normalize_execution_failure(
    error: Exception,
    *,
    final_set_published: bool,
    completed_requests: int,
) -> AcquisitionFailure:
    if final_set_published:
        return AcquisitionFailure(
            "E_POST_PUBLISH_UNCERTAIN",
            "post_publish",
            observations={"completedRequests": completed_requests},
        )
    if isinstance(error, AcquisitionFailure):
        return error
    return AcquisitionFailure("E_INTERNAL", "execution")


def repo_relative_entry_exists(root_fd: int, relative_path: str) -> bool:
    parts = validate_relative_path(relative_path)
    try:
        parent_fd = open_directory_chain(root_fd, parts[:-1], create=False)
    except FileNotFoundError:
        return False
    try:
        return entry_exists(parent_fd, parts[-1])
    finally:
        os.close(parent_fd)


def inspect_one_use_state(root_fd: int) -> dict[str, Any]:
    state: dict[str, Any] = {
        "claimPresent": False,
        "stagingEntryCount": 0,
        "finalDirectoryPresent": False,
        "successReceiptPresent": repo_relative_entry_exists(
            root_fd,
            SUCCESS_RECEIPT_PATH,
        ),
        "failureReceiptPresent": repo_relative_entry_exists(
            root_fd,
            FAILURE_RECEIPT_PATH,
        ),
        "manifestPresent": repo_relative_entry_exists(root_fd, MANIFEST_PATH),
        "dependencyParentInvalid": False,
        "waveParentInvalid": False,
    }
    parent_fd = -1
    wave_parent_fd = -1
    parent_parts = validate_relative_path(str(DEPENDENCY_PARENT))
    try:
        try:
            parent_fd = open_directory_chain(root_fd, parent_parts, create=False)
        except FileNotFoundError:
            return state
        except (OSError, AcquisitionFailure):
            state["dependencyParentInvalid"] = True
            return state
        state["claimPresent"] = entry_exists(parent_fd, CLAIM_NAME)
        state["stagingEntryCount"] = sum(
            name.startswith(STAGING_PREFIX) for name in list_names(parent_fd)
        )
        if not entry_exists(parent_fd, WAVE_PARENT_NAME):
            return state
        try:
            wave_parent_fd = os.open(
                WAVE_PARENT_NAME,
                directory_open_flags(),
                dir_fd=parent_fd,
            )
            validate_directory_descriptor(wave_parent_fd, WAVE_PARENT_NAME)
        except (OSError, AcquisitionFailure):
            state["waveParentInvalid"] = True
            return state
        state["finalDirectoryPresent"] = entry_exists(
            wave_parent_fd,
            FINAL_DIRECTORY_NAME,
        )
        return state
    finally:
        close_quietly(wave_parent_fd)
        close_quietly(parent_fd)


def one_use_artifact_count(one_use_state: Mapping[str, Any]) -> int:
    return (
        int(one_use_state["claimPresent"])
        + one_use_state["stagingEntryCount"]
        + int(one_use_state["finalDirectoryPresent"])
        + int(one_use_state["successReceiptPresent"])
        + int(one_use_state["failureReceiptPresent"])
        + int(one_use_state["manifestPresent"])
        + int(one_use_state["dependencyParentInvalid"])
        + int(one_use_state["waveParentInvalid"])
    )


def preflight() -> dict[str, Any]:
    _, result = load_validated_authority()
    permit = result["permit"]
    validate_hard_deadline_environment()
    root_fd = open_root_directory(result.get("repositoryRootIdentity"))
    try:
        one_use_state = inspect_one_use_state(root_fd)
    finally:
        os.close(root_fd)
    observed_count = one_use_artifact_count(one_use_state)
    clean = observed_count == 0
    complete_publication = (
        one_use_state["claimPresent"]
        and one_use_state["finalDirectoryPresent"]
        and one_use_state["successReceiptPresent"]
        and one_use_state["manifestPresent"]
        and not one_use_state["failureReceiptPresent"]
        and one_use_state["stagingEntryCount"] == 0
        and not one_use_state["dependencyParentInvalid"]
        and not one_use_state["waveParentInvalid"]
    )
    if clean:
        status = "passed"
        consumption_state = "authorized_not_consumed"
        next_action = EXPECTED_PERMIT_NEXT_ACTION
    elif complete_publication:
        status = "consumed_pending_independent_readback"
        consumption_state = "consumed_pending_independent_readback"
        next_action = "run_separate_wave1_independent_readback"
    else:
        status = "blocked_one_use_state_present"
        consumption_state = "state_present_recovery_required"
        next_action = "prepare_new_versioned_wave1_recovery_decision"
    return {
        "documentType": "aetherlink.g2-pion-dependency-wave1-runner-preflight",
        "schemaVersion": "1.0",
        "status": status,
        "permitId": permit["permitId"],
        "permitStatus": permit["status"],
        "requestCount": 0,
        "fileWriteCount": 0,
        "networkOperationCount": 0,
        "claimCreated": one_use_state["claimPresent"],
        "observedOneUseArtifactCount": observed_count,
        "permitConsumptionState": consumption_state,
        "oneUseState": one_use_state,
        "repositoryOwnerIdentityProofRequired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
        "nextAction": next_action,
    }


def _execute_once_with_umask() -> dict[str, Any]:
    _, authority = load_validated_authority()
    permit = authority["permit"]
    decision = authority["decision"]
    limits = decision["resourceLimits"]
    validate_hard_deadline_environment()
    root_fd = open_root_directory(authority.get("repositoryRootIdentity"))
    parent_fd = -1
    wave_parent_fd = -1
    staging_fd = -1
    staging_name: str | None = None
    claim_sha256: str | None = None
    completed_requests = 0
    attempted_requests = 0
    final_set_published = False
    success_receipt_published = False
    held_outputs: list[dict[str, Any]] = []
    try:
        require(
            one_use_artifact_count(inspect_one_use_state(root_fd)) == 0,
            "E_ONE_USE_STATE_PRESENT",
            "preflight",
        )
        parent_parts = validate_relative_path(str(DEPENDENCY_PARENT))
        parent_fd = open_directory_chain(
            root_fd,
            parent_parts,
            create=True,
            owner_only_from=len(parent_parts) - 1,
        )
        wave_parent_fd = open_directory_chain(
            parent_fd,
            (WAVE_PARENT_NAME,),
            create=True,
            owner_only_from=0,
        )
        require(not entry_exists(parent_fd, CLAIM_NAME), "E_CLAIM_EXISTS", "filesystem")
        require(
            not entry_exists(wave_parent_fd, FINAL_DIRECTORY_NAME),
            "E_OUTPUT_EXISTS",
            "filesystem",
        )
        require(
            not any(name.startswith(STAGING_PREFIX) for name in list_names(parent_fd)),
            "E_STAGING_EXISTS",
            "filesystem",
        )
        require(
            one_use_artifact_count(inspect_one_use_state(root_fd)) == 0,
            "E_ONE_USE_STATE_PRESENT",
            "preflight",
        )
        _, claim_sha256 = create_claim(parent_fd, permit)
        staging_name = create_staging_directory(parent_fd)
        staging_fd = os.open(staging_name, directory_open_flags(), dir_fd=parent_fd)
        validate_directory_descriptor(staging_fd, staging_name, owner_only=True)
        require(
            not entry_exists(wave_parent_fd, FINAL_DIRECTORY_NAME),
            "E_OUTPUT_EXISTS",
            "filesystem",
        )
        require(
            [
                name
                for name in list_names(parent_fd)
                if name.startswith(STAGING_PREFIX)
            ]
            == [staging_name],
            "E_STAGING_EXISTS",
            "filesystem",
        )
        opener = build_exact_opener()
        wave_deadline = time.monotonic() + limits["wholeWaveDeadlineMilliseconds"] / 1000
        per_request_timeout = limits["perRequestDeadlineMilliseconds"] / 1000
        aggregate_bytes = 0
        aggregate_entries = 0
        aggregate_uncompressed = 0
        rows: list[dict[str, Any]] = []
        tuples = decision["wave"]["tuples"]
        require(len(tuples) == 19, "E_WAVE_TUPLES", "execution")
        for item in tuples:
            tuple_id = item["tupleId"]
            temporary_name = f".{item['order']:03d}.download"
            final_name = PurePosixPath(item["outputPath"]).name
            try:
                output_fd = os.open(
                    temporary_name,
                    create_download_file_flags(),
                    0o600,
                    dir_fd=staging_fd,
                )
            except OSError as error:
                raise AcquisitionFailure(
                    "E_FILESYSTEM_CREATE",
                    "download",
                    tuple_id=tuple_id,
                ) from error
            keep_output_fd = False
            try:
                os.fchmod(output_fd, 0o600)
                attempted_requests += 1
                download = download_exact_once(
                    opener,
                    item,
                    output_fd,
                    maximum_bytes=limits["maximumResponseBytesPerArchive"],
                    aggregate_before=aggregate_bytes,
                    maximum_aggregate_bytes=limits["maximumAggregateResponseBytes"],
                    per_request_timeout_seconds=per_request_timeout,
                    wave_deadline=wave_deadline,
                )
                with hard_wall_clock_request_deadline(
                    request_deadline=wave_deadline,
                    wave_deadline=wave_deadline,
                    tuple_id=tuple_id,
                    phase="zip",
                ):
                    archive = inspect_module_zip(
                        output_fd,
                        item,
                        limits,
                        aggregate_entries_before=aggregate_entries,
                        aggregate_uncompressed_before=aggregate_uncompressed,
                    )
                link_temp_to_final(
                    staging_fd,
                    temporary_name,
                    final_name,
                    output_fd,
                )
                held_outputs.append(
                    {
                        "fd": output_fd,
                        "name": final_name,
                        "rawByteSize": download["rawByteSize"],
                        "rawSha256": download["rawSha256"],
                    }
                )
                keep_output_fd = True
            finally:
                if not keep_output_fd:
                    os.close(output_fd)
            completed_requests += 1
            aggregate_bytes += download["rawByteSize"]
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
            row = {
                "order": item["order"],
                "tupleId": tuple_id,
                "module": item["module"],
                "version": item["version"],
                "url": item["url"],
                "outputPath": item["outputPath"],
                "rawByteSize": download["rawByteSize"],
                "rawSha256": download["rawSha256"],
                "moduleZipH1": archive["moduleZipH1"],
                "goModH1": archive["goModH1"],
                "entryCount": archive["entryCount"],
                "uncompressedByteCount": archive["uncompressedByteCount"],
                "modulePrefix": archive["modulePrefix"],
                "mode": "0600",
                "linkCount": 1,
            }
            rows.append(row)
        require(completed_requests == 19, "E_REQUEST_COUNT", "execution")
        require(len(rows) == 19, "E_ACCEPTED_COUNT", "execution")
        source_set_sha256 = ordered_source_set_digest(rows)
        with hard_wall_clock_request_deadline(
            request_deadline=wave_deadline,
            wave_deadline=wave_deadline,
            tuple_id=None,
            phase="publication",
        ):
            validate_held_output_inventory(staging_fd, held_outputs)
            os.fsync(staging_fd)
        if time.monotonic() >= wave_deadline:
            raise AcquisitionFailure(
                "E_WAVE_DEADLINE",
                "publication",
            )
        exclusive_rename_directory(
            parent_fd,
            staging_name,
            wave_parent_fd,
            FINAL_DIRECTORY_NAME,
        )
        final_set_published = True
        published_fd = os.open(
            FINAL_DIRECTORY_NAME,
            directory_open_flags(),
            dir_fd=wave_parent_fd,
        )
        try:
            validate_directory_descriptor(
                published_fd,
                FINAL_DIRECTORY_NAME,
                owner_only=True,
            )
            validate_held_output_inventory(published_fd, held_outputs)
        finally:
            os.close(published_fd)
        for record in held_outputs:
            close_quietly(record["fd"])
        held_outputs.clear()
        os.close(staging_fd)
        staging_fd = -1
        os.fsync(parent_fd)
        os.fsync(wave_parent_fd)

        receipt = {
            "documentType": "aetherlink.g2-pion-dependency-wave1-acquisition-receipt",
            "schemaVersion": "1.0",
            "status": "acquired_pending_independent_readback",
            "result": "exact_19_dependency_module_zip_set_acquired_and_hash_verified",
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "decisionId": decision["decisionId"],
            "decisionContentSha256": decision["contentBinding"]["sha256"],
            "claimSha256": claim_sha256,
            "requestCount": completed_requests,
            "acceptedArtifactCount": len(rows),
            "aggregateRawByteSize": aggregate_bytes,
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedByteCount": aggregate_uncompressed,
            "orderedSourceSetSha256": source_set_sha256,
            "sources": rows,
            "independentReadbackPassed": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_independent_readback",
        }
        receipt_raw = canonical_json_bytes(receipt)
        receipt_sha256 = write_repo_relative_artifact(
            root_fd,
            SUCCESS_RECEIPT_PATH,
            receipt_raw,
            limits["maximumJsonReceiptOrFailureBytes"],
        )
        success_receipt_published = True
        manifest = {
            "documentType": "aetherlink.g2-pion-dependency-wave1-acquisition-manifest",
            "schemaVersion": "1.0",
            "status": "wave1_acquisition_publication_complete_pending_independent_readback",
            "result": "receipt_and_exact_19_zip_final_set_published_manifest_written_last",
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "successReceiptPath": SUCCESS_RECEIPT_PATH,
            "successReceiptRawSha256": receipt_sha256,
            "finalDirectoryPath": decision["plannedAcquisitionContract"][
                "finalDirectoryPath"
            ],
            "acceptedArtifactCount": 19,
            "orderedSourceSetSha256": source_set_sha256,
            "manifestWrittenLast": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_independent_readback",
        }
        manifest_raw = canonical_json_bytes(manifest)
        manifest_sha256 = write_repo_relative_artifact(
            root_fd,
            MANIFEST_PATH,
            manifest_raw,
            limits["maximumJsonReceiptOrFailureBytes"],
        )
        return {
            "documentType": "aetherlink.g2-pion-dependency-wave1-runner-result",
            "schemaVersion": "1.0",
            "status": "acquired_pending_independent_readback",
            "requestCount": completed_requests,
            "acceptedArtifactCount": 19,
            "orderedSourceSetSha256": source_set_sha256,
            "successReceiptRawSha256": receipt_sha256,
            "manifestRawSha256": manifest_sha256,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_independent_readback",
        }
    except Exception as error:
        failure = normalize_execution_failure(
            error,
            final_set_published=final_set_published,
            completed_requests=completed_requests,
        )
        if staging_fd >= 0:
            close_quietly(staging_fd)
            staging_fd = -1
        for record in held_outputs:
            close_quietly(record["fd"])
        held_outputs.clear()
        if staging_name is not None and not final_set_published and parent_fd >= 0:
            try:
                remove_staging(parent_fd, staging_name)
            except Exception:
                pass
        if not final_set_published and claim_sha256 is not None and not success_receipt_published:
            failure_document = safe_failure_document(
                permit,
                failure,
                attempted_requests=attempted_requests,
                completed_requests=completed_requests,
                claim_sha256=claim_sha256,
                final_set_published=final_set_published,
            )
            try:
                write_repo_relative_artifact(
                    root_fd,
                    FAILURE_RECEIPT_PATH,
                    canonical_json_bytes(failure_document),
                    decision["resourceLimits"]["maximumJsonReceiptOrFailureBytes"],
                )
            except Exception:
                pass
        raise failure from None
    finally:
        for record in held_outputs:
            close_quietly(record["fd"])
        close_quietly(staging_fd)
        close_quietly(wave_parent_fd)
        close_quietly(parent_fd)
        close_quietly(root_fd)


def execute_once() -> dict[str, Any]:
    previous_umask = os.umask(0o077)
    try:
        return _execute_once_with_umask()
    finally:
        os.umask(previous_umask)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = execute_once() if args.execute else preflight()
    except AcquisitionFailure as failure:
        safe = {
            "documentType": "aetherlink.g2-pion-dependency-wave1-runner-error",
            "schemaVersion": "1.0",
            "status": "failed",
            "failureCode": failure.code,
            "phase": failure.phase,
            "failedTupleId": failure.tuple_id,
            "safeNumericObservations": failure.observations,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        print(json.dumps(safe, ensure_ascii=True, sort_keys=True))
        return 1
    except Exception:
        safe = {
            "documentType": "aetherlink.g2-pion-dependency-wave1-runner-error",
            "schemaVersion": "1.0",
            "status": "failed",
            "failureCode": "E_INTERNAL",
            "phase": "runner",
            "failedTupleId": None,
            "safeNumericObservations": {},
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        print(json.dumps(safe, ensure_ascii=True, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    if not args.execute and result.get("status") != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
