#!/usr/bin/env python3
"""Acquire the exact G2 Pion source ZIP once under the rung-two permit.

The safe default is a zero-write, zero-network preflight. The only networked
mode is the literal ``--execute-exact-once`` flag; the URL, hashes, destination,
request count, and security policy cannot be overridden from the command line.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import signal
import ssl
import stat
import struct
import sys
import time
from typing import Any, Iterator, Sequence
import unicodedata
import zlib
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPSHandler,
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_rung2_acquisition_authority.py"
CHECKER_SPEC = importlib.util.spec_from_file_location(
    "g2_pion_rung2_authority", CHECKER_PATH
)
if CHECKER_SPEC is None or CHECKER_SPEC.loader is None:
    raise RuntimeError("unable to load the G2 Pion rung-two authority checker")
AUTHORITY = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(AUTHORITY)

SOURCE_URL = AUTHORITY.SOURCE_URL
SOURCE_HOST = AUTHORITY.SOURCE_HOST
OUTPUT_PATH = AUTHORITY.OUTPUT_PATH
OUTPUT_PARENT = PurePosixPath(OUTPUT_PATH).parent
OUTPUT_NAME = PurePosixPath(OUTPUT_PATH).name
CLAIM_NAME = ".g2-pion-ice-v4.3.0-source-acquisition-v1.claim"
MODULE_PREFIX = "github.com/pion/ice/v4@v4.3.0/"
ROOT_GO_MOD_NAME = MODULE_PREFIX + "go.mod"

EXPECTED_CONTENT_LENGTH = 293023
MAXIMUM_RESPONSE_BYTES = 524288
TOTAL_DEADLINE_SECONDS = 30.0
EXPECTED_RAW_SHA256 = AUTHORITY.RAW_ARCHIVE_SHA256
EXPECTED_MODULE_H1 = AUTHORITY.MODULE_H1
EXPECTED_GO_MOD_H1 = AUTHORITY.GO_MOD_H1
EXPECTED_DECISION_SHA256 = AUTHORITY.EXPECTED_RAW_SHA256[AUTHORITY.DECISION_PATH]
EXPECTED_PROVENANCE_SHA256 = AUTHORITY.EXPECTED_RAW_SHA256[AUTHORITY.PROVENANCE_PATH]

MAX_ENTRY_COUNT = 4096
MAX_CENTRAL_DIRECTORY_BYTES = 4 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_GO_MOD_BYTES = 1024 * 1024
MAX_PATH_BYTES = 1024
MAX_COMPONENT_BYTES = 255
MAX_PATH_DEPTH = 32
MAX_COMPRESSION_RATIO = 200
STREAM_CHUNK_BYTES = 64 * 1024

ZIP_LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
ZIP_EOCD = struct.Struct("<4s4H2LH")
ZIP_DATA_DESCRIPTOR = struct.Struct("<III")
ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE = struct.Struct("<IIII")
ZIP_LOCAL_SIGNATURE = 0x04034B50
ZIP_DATA_DESCRIPTOR_SIGNATURE = 0x08074B50
ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
ZIP64_EXTRA_FIELD_ID = 0x0001
ALLOWED_ZIP_FLAGS = 0x0008 | 0x0800
ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class AcquisitionError(RuntimeError):
    """A fail-closed acquisition or archive-validation error."""


class PublishedArchiveStateError(AcquisitionError):
    """The archive was renamed into place but completion became uncertain."""

    def __init__(
        self,
        message: str,
        *,
        directory_fsync_completed: bool,
        request_count: int,
    ) -> None:
        super().__init__(message)
        self.archive_published = True
        self.directory_fsync_completed = directory_fsync_completed
        self.request_count = request_count


class RejectRedirects(HTTPRedirectHandler):
    """Ensure every 3xx response fails instead of generating another request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def write_all(file_descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(file_descriptor, payload[offset:])
        if written <= 0:
            raise AcquisitionError("short write while persisting the acquisition artifact")
        offset += written


def validate_directory_descriptor(file_descriptor: int, label: str) -> None:
    metadata = os.fstat(file_descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise AcquisitionError(f"{label} is not a directory")
    if metadata.st_uid != os.getuid():
        raise AcquisitionError(f"{label} is not owned by the current user")
    if metadata.st_mode & 0o022:
        raise AcquisitionError(f"{label} is group- or world-writable")


def directory_open_flags() -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return flags


def create_file_flags() -> int:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return flags


def open_secure_output_directory(*, create_missing: bool) -> int | None:
    """Open the output parent through owner-only, non-symlink dirfds."""

    current_fd = os.open(ROOT, directory_open_flags())
    try:
        validate_directory_descriptor(current_fd, "repository root")
        for segment in OUTPUT_PARENT.parts:
            created_segment = False
            try:
                next_fd = os.open(segment, directory_open_flags(), dir_fd=current_fd)
            except FileNotFoundError:
                if not create_missing:
                    return None
                try:
                    os.mkdir(segment, mode=0o700, dir_fd=current_fd)
                    created_segment = True
                except FileExistsError:
                    pass
                next_fd = os.open(segment, directory_open_flags(), dir_fd=current_fd)
            validate_directory_descriptor(next_fd, f"output ancestor {segment!r}")
            if created_segment:
                # Persist the empty child first, then the new name in its parent.
                # This occurs before the one-use claim or any network request.
                os.fsync(next_fd)
                os.fsync(current_fd)
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    except OSError as error:
        raise AcquisitionError(f"unable to open the secure output directory: {error}") from error
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def name_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise AcquisitionError(f"unable to inspect output name {name!r}: {error}") from error
    return True


def directory_entry_matches_open_file(
    directory_fd: int,
    name: str,
    open_file_fd: int,
) -> bool:
    """Return true only when name and the already-open file are one inode."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    named_fd = -1
    try:
        named_fd = os.open(name, flags, dir_fd=directory_fd)
    except FileNotFoundError:
        return False
    try:
        named = os.fstat(named_fd)
        opened = os.fstat(open_file_fd)
        return (
            stat.S_ISREG(named.st_mode)
            and stat.S_ISREG(opened.st_mode)
            and named.st_dev == opened.st_dev
            and named.st_ino == opened.st_ino
        )
    finally:
        if named_fd >= 0:
            try:
                os.close(named_fd)
            except OSError:
                pass


def create_atomic_claim(directory_fd: int) -> tuple[str, str]:
    if name_exists(directory_fd, OUTPUT_NAME):
        raise AcquisitionError("final source archive already exists; permit remains closed")
    if name_exists(directory_fd, CLAIM_NAME):
        raise AcquisitionError("one-use acquisition claim already exists; permit is not reusable")

    created_at = utc_now()
    claim_payload = (
        json.dumps(
            {
                "claimType": "aetherlink.g2-pion-source-acquisition-one-use-claim",
                "schemaVersion": "1.0",
                "decisionSha256": EXPECTED_DECISION_SHA256,
                "createdAt": created_at,
                "rule": "claim_persists_after_any_network_attempt_and_blocks_retry",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    claim_fd = -1
    claim_durable = False
    try:
        claim_fd = os.open(
            CLAIM_NAME,
            create_file_flags(),
            mode=0o600,
            dir_fd=directory_fd,
        )
        os.fchmod(claim_fd, 0o600)
        write_all(claim_fd, claim_payload)
        claim_stat = os.fstat(claim_fd)
        if (
            not stat.S_ISREG(claim_stat.st_mode)
            or claim_stat.st_uid != os.getuid()
            or claim_stat.st_nlink != 1
            or stat.S_IMODE(claim_stat.st_mode) != 0o600
        ):
            raise AcquisitionError("one-use claim file failed ownership or mode validation")
        os.fsync(claim_fd)
        os.fsync(directory_fd)
        claim_durable = True
        return created_at, hashlib.sha256(claim_payload).hexdigest()
    except FileExistsError as error:
        raise AcquisitionError("one-use acquisition claim was already consumed") from error
    except OSError as error:
        raise AcquisitionError(f"unable to persist one-use acquisition claim: {error}") from error
    finally:
        if claim_fd >= 0:
            os.close(claim_fd)
        if not claim_durable:
            try:
                os.unlink(CLAIM_NAME, dir_fd=directory_fd)
                os.fsync(directory_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass


def create_temporary_archive(directory_fd: int) -> tuple[int, str]:
    for _ in range(4):
        temporary_name = f".{OUTPUT_NAME}.tmp-{secrets.token_hex(16)}"
        try:
            temporary_fd = os.open(
                temporary_name,
                create_file_flags(),
                mode=0o600,
                dir_fd=directory_fd,
            )
        except FileExistsError:
            continue
        try:
            os.fchmod(temporary_fd, 0o600)
            metadata = os.fstat(temporary_fd)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) != 0o600
            ):
                raise AcquisitionError(
                    "temporary archive failed ownership or mode validation"
                )
            return temporary_fd, temporary_name
        except BaseException as error:
            os.close(temporary_fd)
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except OSError:
                pass
            if isinstance(error, AcquisitionError):
                raise
            raise AcquisitionError(
                f"temporary archive initialization failed: {error}"
            ) from error
    raise AcquisitionError("unable to create a unique temporary archive")


def unlink_exact(directory_fd: int, name: str | None) -> None:
    if name is None:
        return
    try:
        os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        return
    except OSError as error:
        raise AcquisitionError(f"unable to remove temporary archive {name!r}: {error}") from error


def rename_no_replace(
    directory_fd: int,
    temporary_name: str,
    final_name: str,
) -> None:
    """Publish with Darwin renameatx_np(RENAME_EXCL), never plain rename."""

    if sys.platform != "darwin":
        raise AcquisitionError("no-replace publication is implemented only for Darwin")
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameatx_np = libc.renameatx_np
    except AttributeError as error:
        raise AcquisitionError("Darwin renameatx_np is unavailable") from error
    renameatx_np.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameatx_np.restype = ctypes.c_int
    rename_exclusive = 0x00000004
    result = renameatx_np(
        directory_fd,
        temporary_name.encode("utf-8"),
        directory_fd,
        final_name.encode("utf-8"),
        rename_exclusive,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise AcquisitionError(
            f"exclusive archive publication failed: {os.strerror(error_number)}"
        )


class TotalDeadlineExpired(AcquisitionError):
    pass


@contextmanager
def wall_clock_deadline(seconds: float) -> Iterator[None]:
    if seconds <= 0:
        raise AcquisitionError("total deadline must be positive")
    if not hasattr(signal, "setitimer"):
        raise AcquisitionError("platform does not support a process wall-clock deadline")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)

    def handle_timeout(signum, frame):  # noqa: ANN001, ARG001
        raise TotalDeadlineExpired("30-second total acquisition deadline expired")

    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def build_exact_opener():
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return build_opener(
        ProxyHandler({}),
        RejectRedirects(),
        HTTPSHandler(context=context),
    )


def parse_exact_content_length(headers: Any) -> int:
    values = headers.get_all("Content-Length") or []
    if len(values) != 1 or re.fullmatch(r"[0-9]+", values[0]) is None:
        raise AcquisitionError("response must contain exactly one decimal Content-Length")
    length = int(values[0])
    if length != EXPECTED_CONTENT_LENGTH:
        raise AcquisitionError(
            f"response Content-Length drifted: expected {EXPECTED_CONTENT_LENGTH}, got {length}"
        )
    return length


def download_exact_once(temporary_fd: int) -> dict[str, Any]:
    request = Request(
        SOURCE_URL,
        method="GET",
        headers={
            "Accept": "application/zip",
            "Accept-Encoding": "identity",
            "Connection": "close",
            "User-Agent": "AetherLink-G2-Source-Intake/1.0",
        },
    )
    forbidden_request_headers = {
        "authorization", "cookie", "proxy-authorization", "range"
    }
    if any(name.lower() in forbidden_request_headers for name in request.headers):
        raise AcquisitionError("request unexpectedly contains a credential or replay header")

    opener = build_exact_opener()
    started_at = utc_now()
    started_monotonic = time.monotonic()
    raw_hasher = hashlib.sha256()
    retained = bytearray()
    response_etag: str | None = None
    try:
        with opener.open(request, timeout=TOTAL_DEADLINE_SECONDS) as response:
            status_code = getattr(response, "status", None)
            if type(status_code) is not int or status_code != 200:
                raise AcquisitionError(f"HTTP status must be exactly 200, got {status_code!r}")
            if response.geturl() != SOURCE_URL:
                raise AcquisitionError("final response URL differs from the exact permitted URL")
            parse_exact_content_length(response.headers)
            content_encoding = response.headers.get("Content-Encoding")
            if content_encoding not in (None, "identity"):
                raise AcquisitionError("encoded HTTP response bodies are forbidden")
            if response.headers.get("Transfer-Encoding") is not None:
                raise AcquisitionError("Transfer-Encoding is forbidden for this fixed archive")
            response_etag = response.headers.get("ETag")
            while True:
                chunk = response.read(STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                if len(retained) + len(chunk) > MAXIMUM_RESPONSE_BYTES:
                    raise AcquisitionError("response exceeded the exact maximum byte ceiling")
                retained.extend(chunk)
                raw_hasher.update(chunk)
                write_all(temporary_fd, chunk)
    except HTTPError as error:
        raise AcquisitionError(f"one permitted HTTP request failed with status {error.code}") from error
    except URLError as error:
        raise AcquisitionError(f"one permitted HTTPS request failed: {error.reason}") from error
    except (TimeoutError, ssl.SSLError, OSError) as error:
        raise AcquisitionError(f"one permitted HTTPS request failed: {error}") from error
    finally:
        opener.close()

    completed_at = utc_now()
    elapsed_milliseconds = int((time.monotonic() - started_monotonic) * 1000)
    if len(retained) != EXPECTED_CONTENT_LENGTH:
        raise AcquisitionError(
            f"received byte count drifted: expected {EXPECTED_CONTENT_LENGTH}, got {len(retained)}"
        )
    observed_raw_sha256 = raw_hasher.hexdigest()
    if observed_raw_sha256 != EXPECTED_RAW_SHA256:
        raise AcquisitionError(
            "decision-pinned raw archive SHA-256 mismatch: "
            f"expected {EXPECTED_RAW_SHA256}, got {observed_raw_sha256}"
        )
    return {
        "bytes": bytes(retained),
        "startedAt": started_at,
        "completedAt": completed_at,
        "elapsedMilliseconds": elapsed_milliseconds,
        "httpStatus": 200,
        "responseEtag": response_etag,
        "receivedBytes": len(retained),
        "rawSha256": observed_raw_sha256,
    }


def parse_extra_fields(extra: bytes, path: str) -> None:
    offset = 0
    while offset < len(extra):
        if len(extra) - offset < 4:
            raise AcquisitionError(f"{path} has a truncated ZIP extra-field header")
        field_id, field_length = struct.unpack_from("<HH", extra, offset)
        offset += 4
        if field_length > len(extra) - offset:
            raise AcquisitionError(f"{path} has a truncated ZIP extra-field payload")
        if field_id == ZIP64_EXTRA_FIELD_ID:
            raise AcquisitionError(f"{path} uses forbidden ZIP64 metadata")
        offset += field_length


def validate_archive_name(name: str, *, is_directory: bool) -> str:
    if not name or len(name.encode("utf-8")) > MAX_PATH_BYTES:
        raise AcquisitionError("ZIP entry path is empty or exceeds the path byte ceiling")
    if (
        "\\" in name
        or ":" in name
        or "\x00" in name
        or name.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        raise AcquisitionError(f"ZIP entry path is unsafe: {name!r}")
    if unicodedata.normalize("NFC", name) != name:
        raise AcquisitionError(f"ZIP entry path is not NFC-normalized: {name!r}")
    path_without_directory_suffix = name[:-1] if is_directory else name
    if is_directory != name.endswith("/"):
        raise AcquisitionError(f"ZIP directory suffix does not match entry type: {name!r}")
    components = path_without_directory_suffix.split("/")
    if (
        not components
        or len(components) > MAX_PATH_DEPTH
        or any(component in {"", ".", ".."} for component in components)
        or any(len(component.encode("utf-8")) > MAX_COMPONENT_BYTES for component in components)
    ):
        raise AcquisitionError(f"ZIP entry path is noncanonical or over-bounded: {name!r}")
    if not name.startswith(MODULE_PREFIX):
        raise AcquisitionError(f"ZIP entry is outside the exact module prefix: {name!r}")
    relative = path_without_directory_suffix[len(MODULE_PREFIX):]
    if not relative and not is_directory:
        raise AcquisitionError("ZIP contains a file at the module directory path")
    if relative:
        relative_path = PurePosixPath(relative)
        if str(relative_path) != relative:
            raise AcquisitionError(f"ZIP entry relative path is noncanonical: {name!r}")
    return path_without_directory_suffix


def decode_local_name(raw_name: bytes, flags: int, path: str) -> str:
    if not (flags & 0x0800) and any(byte >= 0x80 for byte in raw_name):
        raise AcquisitionError(
            f"{path} has a non-ASCII filename without the UTF-8 ZIP flag"
        )
    encoding = "utf-8" if flags & 0x0800 else "cp437"
    try:
        return raw_name.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        raise AcquisitionError(f"{path} has an invalid local filename encoding") from error


def parse_eocd(raw_archive: bytes) -> tuple[int, int, int]:
    if len(raw_archive) < ZIP_EOCD.size or not raw_archive.startswith(b"PK\x03\x04"):
        raise AcquisitionError("archive must start with a local ZIP header and contain an EOCD")
    if ZIP64_EOCD_SIGNATURE in raw_archive or ZIP64_LOCATOR_SIGNATURE in raw_archive:
        raise AcquisitionError("ZIP64 records are forbidden")
    eocd_offset = raw_archive.rfind(
        ZIP_EOCD_SIGNATURE,
        max(0, len(raw_archive) - ZIP_EOCD.size - 65535),
    )
    if eocd_offset < 0 or eocd_offset + ZIP_EOCD.size > len(raw_archive):
        raise AcquisitionError("archive has no complete end-of-central-directory record")
    (
        signature_value,
        disk_number,
        central_disk,
        disk_entries,
        total_entries,
        central_size,
        central_offset,
        comment_length,
    ) = ZIP_EOCD.unpack_from(raw_archive, eocd_offset)
    if signature_value != ZIP_EOCD_SIGNATURE:
        raise AcquisitionError("archive EOCD signature is invalid")
    if disk_number != 0 or central_disk != 0 or disk_entries != total_entries:
        raise AcquisitionError("multi-disk ZIP archives are forbidden")
    if 0xFFFF in (disk_entries, total_entries) or 0xFFFFFFFF in (central_size, central_offset):
        raise AcquisitionError("ZIP64 sentinel values are forbidden")
    if comment_length != 0 or eocd_offset + ZIP_EOCD.size != len(raw_archive):
        raise AcquisitionError("archive comments and trailing data are forbidden")
    if central_size > MAX_CENTRAL_DIRECTORY_BYTES:
        raise AcquisitionError("central directory exceeds its byte ceiling")
    if central_offset + central_size != eocd_offset:
        raise AcquisitionError("central directory does not end exactly at the EOCD")
    return total_entries, central_offset, central_size


def validate_local_headers(
    raw_archive: bytes,
    infos: Sequence[zipfile.ZipInfo],
    central_offset: int,
) -> dict[int, bytes]:
    ordered = sorted(infos, key=lambda item: item.header_offset)
    if not ordered or ordered[0].header_offset != 0:
        raise AcquisitionError("archive has a forbidden prefix before the first local header")
    seen_offsets: set[int] = set()
    compressed_payloads: dict[int, bytes] = {}
    for index, info in enumerate(ordered):
        offset = info.header_offset
        if offset in seen_offsets:
            raise AcquisitionError("multiple ZIP entries reference one local header")
        seen_offsets.add(offset)
        if offset < 0 or offset + ZIP_LOCAL_HEADER.size > central_offset:
            raise AcquisitionError(f"local header for {info.filename!r} is out of range")
        (
            signature_value,
            extract_version,
            local_flags,
            local_method,
            _mod_time,
            _mod_date,
            local_crc,
            local_compressed_size,
            local_uncompressed_size,
            name_length,
            extra_length,
        ) = ZIP_LOCAL_HEADER.unpack_from(raw_archive, offset)
        if signature_value != ZIP_LOCAL_SIGNATURE or extract_version >= 45:
            raise AcquisitionError(f"local header for {info.filename!r} is invalid or ZIP64")
        name_start = offset + ZIP_LOCAL_HEADER.size
        extra_start = name_start + name_length
        data_start = extra_start + extra_length
        if data_start > central_offset:
            raise AcquisitionError(f"local header for {info.filename!r} exceeds the data region")
        local_name = decode_local_name(
            raw_archive[name_start:extra_start], local_flags, info.filename
        )
        if local_name != info.filename:
            raise AcquisitionError(f"local and central filenames differ for {info.filename!r}")
        parse_extra_fields(raw_archive[extra_start:data_start], info.filename + " local")
        if local_flags != info.flag_bits or local_method != info.compress_type:
            raise AcquisitionError(f"local and central ZIP flags/method differ for {info.filename!r}")
        data_end = data_start + info.compress_size
        next_boundary = (
            ordered[index + 1].header_offset
            if index + 1 < len(ordered)
            else central_offset
        )
        if data_end > next_boundary:
            raise AcquisitionError(f"compressed data ranges overlap for {info.filename!r}")
        if local_flags & 0x0008:
            descriptor = raw_archive[data_end:next_boundary]
            if len(descriptor) == ZIP_DATA_DESCRIPTOR.size:
                descriptor_crc, descriptor_compressed, descriptor_uncompressed = (
                    ZIP_DATA_DESCRIPTOR.unpack(descriptor)
                )
            elif len(descriptor) == ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.size:
                (
                    descriptor_signature,
                    descriptor_crc,
                    descriptor_compressed,
                    descriptor_uncompressed,
                ) = ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.unpack(descriptor)
                if descriptor_signature != ZIP_DATA_DESCRIPTOR_SIGNATURE:
                    raise AcquisitionError(f"data descriptor signature is invalid for {info.filename!r}")
            else:
                raise AcquisitionError(f"data descriptor length is invalid for {info.filename!r}")
            if (
                descriptor_crc != info.CRC
                or descriptor_compressed != info.compress_size
                or descriptor_uncompressed != info.file_size
            ):
                raise AcquisitionError(f"data descriptor values differ for {info.filename!r}")
            if local_crc not in (0, info.CRC):
                raise AcquisitionError(f"local CRC differs for {info.filename!r}")
            if local_compressed_size not in (0, info.compress_size):
                raise AcquisitionError(f"local compressed size differs for {info.filename!r}")
            if local_uncompressed_size not in (0, info.file_size):
                raise AcquisitionError(f"local uncompressed size differs for {info.filename!r}")
        else:
            if data_end != next_boundary:
                raise AcquisitionError(f"unexpected padding follows {info.filename!r}")
            if (
                local_crc != info.CRC
                or local_compressed_size != info.compress_size
                or local_uncompressed_size != info.file_size
            ):
                raise AcquisitionError(f"local and central sizes/CRC differ for {info.filename!r}")
        compressed_payloads[offset] = raw_archive[data_start:data_end]
    return compressed_payloads


def decode_zip_entry_exact(info: zipfile.ZipInfo, compressed_payload: bytes) -> bytes:
    """Decode one bounded entry without trusting ZipExtFile's size truncation."""

    if len(compressed_payload) != info.compress_size:
        raise AcquisitionError(
            f"compressed payload size differs from metadata for {info.filename!r}"
        )
    if info.file_size > MAX_SINGLE_FILE_BYTES:
        raise AcquisitionError(
            f"ZIP entry exceeds the single-file ceiling: {info.filename!r}"
        )

    if info.compress_type == zipfile.ZIP_STORED:
        if info.compress_size != info.file_size:
            raise AcquisitionError(
                f"stored entry compressed/uncompressed sizes differ for {info.filename!r}"
            )
        decoded = compressed_payload
    elif info.compress_type == zipfile.ZIP_DEFLATED:
        decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
        try:
            decoded_buffer = bytearray(
                decompressor.decompress(compressed_payload, info.file_size + 1)
            )
            if len(decoded_buffer) > info.file_size or decompressor.unconsumed_tail:
                raise AcquisitionError(
                    f"deflate output exceeds declared size for {info.filename!r}"
                )
            decoded_buffer.extend(
                decompressor.flush(info.file_size - len(decoded_buffer) + 1)
            )
        except zlib.error as error:
            raise AcquisitionError(
                f"raw deflate validation failed for {info.filename!r}: {error}"
            ) from error
        if len(decoded_buffer) > info.file_size:
            raise AcquisitionError(
                f"deflate output exceeds declared size for {info.filename!r}"
            )
        if (
            not decompressor.eof
            or decompressor.unused_data
            or decompressor.unconsumed_tail
        ):
            raise AcquisitionError(
                f"deflate stream is incomplete or contains hidden data for {info.filename!r}"
            )
        decoded = bytes(decoded_buffer)
    else:
        raise AcquisitionError(
            f"unsupported compression method: {info.filename!r}"
        )

    if len(decoded) != info.file_size:
        raise AcquisitionError(f"decompressed size mismatch for {info.filename!r}")
    if zlib.crc32(decoded) & 0xFFFFFFFF != info.CRC:
        raise AcquisitionError(f"CRC mismatch for {info.filename!r}")
    return decoded


def dirhash_h1(file_hashes: Sequence[tuple[str, str]]) -> str:
    aggregate = hashlib.sha256()
    for name, content_sha256 in sorted(file_hashes, key=lambda item: item[0]):
        aggregate.update(f"{content_sha256}  {name}\n".encode("utf-8"))
    return "h1:" + base64.b64encode(aggregate.digest()).decode("ascii")


def inspect_module_zip(raw_archive: bytes) -> dict[str, Any]:
    if len(raw_archive) > MAXIMUM_RESPONSE_BYTES:
        raise AcquisitionError("archive exceeds the raw byte ceiling")
    total_entries, central_offset, central_size = parse_eocd(raw_archive)
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw_archive), mode="r")
    except (OSError, zipfile.BadZipFile) as error:
        raise AcquisitionError(f"archive cannot be parsed as ZIP: {error}") from error
    with archive:
        if archive.comment:
            raise AcquisitionError("ZIP archive comment is forbidden")
        infos = archive.infolist()
        if total_entries != len(infos) or not infos or len(infos) > MAX_ENTRY_COUNT:
            raise AcquisitionError("ZIP entry count is empty, inconsistent, or over-bounded")
        compressed_payloads = validate_local_headers(raw_archive, infos, central_offset)

        exact_names: set[str] = set()
        folded_names: set[str] = set()
        file_paths: set[str] = set()
        directory_paths: set[str] = set()
        folded_file_paths: set[str] = set()
        folded_directory_paths: set[str] = set()
        total_uncompressed = 0
        module_hash_entries: list[tuple[str, str]] = []
        file_count = 0
        go_mod_bytes: bytes | None = None
        for info in infos:
            if info.volume != 0:
                raise AcquisitionError(
                    f"multi-disk central-directory entry is forbidden: {info.filename!r}"
                )
            if info.flag_bits & ~ALLOWED_ZIP_FLAGS:
                raise AcquisitionError(f"ZIP entry uses forbidden flags: {info.filename!r}")
            if info.flag_bits & 0x0001:
                raise AcquisitionError(f"encrypted ZIP entry is forbidden: {info.filename!r}")
            if info.compress_type not in ALLOWED_COMPRESSION_METHODS:
                raise AcquisitionError(f"unsupported compression method: {info.filename!r}")
            if info.extract_version >= 45 or info.file_size > 0xFFFFFFFF or info.compress_size > 0xFFFFFFFF:
                raise AcquisitionError(f"ZIP64 entry is forbidden: {info.filename!r}")
            if info.comment:
                raise AcquisitionError(f"per-entry ZIP comments are forbidden: {info.filename!r}")
            parse_extra_fields(info.extra, info.filename + " central")

            unix_mode = (info.external_attr >> 16) & 0xFFFF
            unix_type = stat.S_IFMT(unix_mode)
            is_directory = info.is_dir()
            if unix_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise AcquisitionError(f"special or symlink ZIP entry is forbidden: {info.filename!r}")
            if unix_type == stat.S_IFDIR and not is_directory:
                raise AcquisitionError(f"directory mode/name mismatch: {info.filename!r}")
            if unix_type == stat.S_IFREG and is_directory:
                raise AcquisitionError(f"regular-file mode/name mismatch: {info.filename!r}")
            dos_directory = bool(info.external_attr & 0x10)
            if dos_directory != is_directory:
                raise AcquisitionError(f"DOS directory flag/name mismatch: {info.filename!r}")

            canonical_path = validate_archive_name(
                info.filename, is_directory=is_directory
            )
            collision_key = unicodedata.normalize("NFC", info.filename).casefold()
            if info.filename in exact_names or collision_key in folded_names:
                raise AcquisitionError(f"duplicate or case-fold-colliding ZIP path: {info.filename!r}")
            exact_names.add(info.filename)
            folded_names.add(collision_key)
            if is_directory:
                directory_paths.add(canonical_path)
                folded_directory_paths.add(canonical_path.casefold())
                if info.file_size != 0 or info.compress_size != 0 or info.CRC != 0:
                    raise AcquisitionError(f"directory entry contains data: {info.filename!r}")
                if decode_zip_entry_exact(
                    info, compressed_payloads[info.header_offset]
                ) != b"":
                    raise AcquisitionError(
                        f"directory entry yielded content: {info.filename!r}"
                    )
                module_hash_entries.append(
                    (info.filename, hashlib.sha256(b"").hexdigest())
                )
                continue

            file_paths.add(canonical_path)
            folded_file_paths.add(canonical_path.casefold())
            if info.file_size > MAX_SINGLE_FILE_BYTES:
                raise AcquisitionError(f"ZIP entry exceeds the single-file ceiling: {info.filename!r}")
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise AcquisitionError("ZIP exceeds the total uncompressed byte ceiling")
            if info.file_size and (
                info.compress_size == 0
                or info.file_size > info.compress_size * MAX_COMPRESSION_RATIO
            ):
                raise AcquisitionError(f"ZIP entry exceeds the compression-ratio ceiling: {info.filename!r}")

            decoded = decode_zip_entry_exact(
                info, compressed_payloads[info.header_offset]
            )
            digest = hashlib.sha256(decoded)
            file_count += 1
            module_hash_entries.append((info.filename, digest.hexdigest()))
            if info.filename == ROOT_GO_MOD_NAME:
                if go_mod_bytes is not None:
                    raise AcquisitionError("archive contains more than one root go.mod")
                if len(decoded) > MAX_GO_MOD_BYTES:
                    raise AcquisitionError("root go.mod exceeds its byte ceiling")
                go_mod_bytes = decoded

        if folded_file_paths & folded_directory_paths:
            raise AcquisitionError("ZIP contains the same path as both file and directory")
        for candidate_path in folded_file_paths | folded_directory_paths:
            parts = candidate_path.split("/")
            for index in range(1, len(parts)):
                if "/".join(parts[:index]) in folded_file_paths:
                    raise AcquisitionError("ZIP contains a file/directory prefix collision")
        if go_mod_bytes is None:
            raise AcquisitionError("archive does not contain the exact root go.mod")
        module_h1 = dirhash_h1(module_hash_entries)
        go_mod_content_sha = hashlib.sha256(go_mod_bytes).hexdigest()
        go_mod_h1 = dirhash_h1((("go.mod", go_mod_content_sha),))
        return {
            "entryCount": len(infos),
            "fileCount": file_count,
            "moduleHashEntryCount": len(module_hash_entries),
            "centralDirectoryBytes": central_size,
            "totalUncompressedBytes": total_uncompressed,
            "moduleH1": module_h1,
            "goModH1": go_mod_h1,
            "goModBytes": len(go_mod_bytes),
            "archiveExtracted": False,
        }


def verify_and_publish_claimed_acquisition(
    directory_fd: int,
    temporary_fd: int,
    temporary_name: str,
    publication_state: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Download, verify, and publish inside the caller's one total deadline."""

    download = download_exact_once(temporary_fd)
    archive_evidence = inspect_module_zip(download["bytes"])
    if archive_evidence["moduleH1"] != EXPECTED_MODULE_H1:
        raise AcquisitionError(
            f"module h1 mismatch: expected {EXPECTED_MODULE_H1}, "
            f"got {archive_evidence['moduleH1']}"
        )
    if archive_evidence["goModH1"] != EXPECTED_GO_MOD_H1:
        raise AcquisitionError(
            f"go.mod h1 mismatch: expected {EXPECTED_GO_MOD_H1}, "
            f"got {archive_evidence['goModH1']}"
        )

    metadata = os.fstat(temporary_fd)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_size != EXPECTED_CONTENT_LENGTH
    ):
        raise AcquisitionError("temporary archive drifted before publication")
    os.fsync(temporary_fd)
    rename_no_replace(directory_fd, temporary_name, OUTPUT_NAME)
    publication_state["archivePublished"] = True
    os.fsync(directory_fd)
    publication_state["directoryFsyncCompleted"] = True
    return download, archive_evidence


def preflight() -> dict[str, Any]:
    AUTHORITY.validate_repository()
    directory_fd = open_secure_output_directory(create_missing=False)
    output_exists = False
    claim_exists = False
    if directory_fd is not None:
        try:
            output_exists = name_exists(directory_fd, OUTPUT_NAME)
            claim_exists = name_exists(directory_fd, CLAIM_NAME)
        finally:
            os.close(directory_fd)
    if output_exists or claim_exists:
        raise AcquisitionError(
            "one-use acquisition is no longer fresh: output or claim already exists"
        )
    return {
        "status": "preflight_passed_zero_write_zero_network",
        "decisionSha256": EXPECTED_DECISION_SHA256,
        "provenanceSha256": EXPECTED_PROVENANCE_SHA256,
        "url": SOURCE_URL,
        "outputPath": OUTPUT_PATH,
        "outputDirectoryExists": directory_fd is not None,
        "outputExists": False,
        "claimExists": False,
        "requestCount": 0,
        "externalIdentityProofRequired": False,
        "userActionRequired": False,
    }


def execute_exact_once() -> dict[str, Any]:
    AUTHORITY.validate_repository()
    directory_fd = open_secure_output_directory(create_missing=True)
    if directory_fd is None:
        raise AcquisitionError("secure output directory was not created")
    temporary_fd = -1
    temporary_name: str | None = None
    publication_state = {
        "archivePublished": False,
        "directoryFsyncCompleted": False,
    }
    request_count = 0
    try:
        claim_created_at, claim_sha256 = create_atomic_claim(directory_fd)
        total_started_monotonic = time.monotonic()
        with wall_clock_deadline(TOTAL_DEADLINE_SECONDS):
            temporary_fd, temporary_name = create_temporary_archive(directory_fd)
            request_count = 1
            download, archive_evidence = verify_and_publish_claimed_acquisition(
                directory_fd,
                temporary_fd,
                temporary_name,
                publication_state,
            )
        total_elapsed_milliseconds = int(
            (time.monotonic() - total_started_monotonic) * 1000
        )
        if (
            request_count != 1
            or not publication_state["archivePublished"]
            or not publication_state["directoryFsyncCompleted"]
        ):
            raise AcquisitionError(
                "successful acquisition reached an impossible publication state"
            )
        temporary_name = None

        return {
            "documentType": "aetherlink.g2-pion-source-acquisition-run-result",
            "schemaVersion": "1.0",
            "status": "success_archive_retained_not_extracted",
            "totalElapsedMilliseconds": total_elapsed_milliseconds,
            "decisionSha256": EXPECTED_DECISION_SHA256,
            "provenanceSha256": EXPECTED_PROVENANCE_SHA256,
            "claim": {
                "path": (OUTPUT_PARENT / CLAIM_NAME).as_posix(),
                "createdAt": claim_created_at,
                "sha256": claim_sha256,
                "retained": True,
            },
            "request": {
                "requestCount": request_count,
                "method": "GET",
                "url": SOURCE_URL,
                "finalUrl": SOURCE_URL,
                "startedAt": download["startedAt"],
                "completedAt": download["completedAt"],
                "elapsedMilliseconds": download["elapsedMilliseconds"],
                "httpStatus": download["httpStatus"],
                "redirectCount": 0,
                "ambientProxyUsed": False,
                "credentialsUsed": False,
                "responseEtag": download["responseEtag"],
                "receivedBytes": download["receivedBytes"],
            },
            "verification": {
                "rawSha256": download["rawSha256"],
                "rawSha256Matches": True,
                "rawSha256TrustRole": "decision_pinned_reproducibility_check_not_independent_upstream_authentication",
                "moduleH1": archive_evidence["moduleH1"],
                "moduleH1Matches": True,
                "goModH1": archive_evidence["goModH1"],
                "goModH1Matches": True,
                "sumdbSignatureVerifiedByPreflight": True,
                "sumdbInclusionProofVerifiedByPreflight": True,
                "zipStructureAndCrcVerified": True,
                "allRequiredChecksPassed": True,
            },
            "archive": {
                "outputPath": OUTPUT_PATH,
                "mode": "0600",
                "bytes": EXPECTED_CONTENT_LENGTH,
                **archive_evidence,
                "retained": True,
                "publishedWithoutReplacement": True,
                "directoryFsyncCompleted": True,
            },
            "executionBoundary": {
                "candidateSelected": False,
                "librarySelected": False,
                "archiveExtracted": False,
                "sourceExecuted": False,
                "dependencyInstallationAllowed": False,
                "compilerInvocationAllowed": False,
                "codeLoadingAllowed": False,
                "socketCreationAllowed": False,
                "runtimeNetworkIoAllowed": False,
                "deviceExecutionAllowed": False,
                "productionDeploymentAllowed": False,
                "gitOperationAllowed": False,
                "externalIdentityProofRequired": False,
                "userActionRequired": False,
                "repositoryOwnerAuthenticationRequired": False,
            },
        }
    except BaseException as error:
        publication_inspection_error: OSError | None = None
        if temporary_fd >= 0 and not publication_state["archivePublished"]:
            try:
                publication_state["archivePublished"] = (
                    directory_entry_matches_open_file(
                        directory_fd,
                        OUTPUT_NAME,
                        temporary_fd,
                    )
                )
            except OSError as inspection_error:
                publication_inspection_error = inspection_error
        if publication_state["archivePublished"]:
            raise PublishedArchiveStateError(
                "archive was atomically published but acquisition completion became "
                f"uncertain: {error}",
                directory_fsync_completed=publication_state[
                    "directoryFsyncCompleted"
                ],
                request_count=request_count,
            ) from error
        cleanup_error: Exception | None = None
        if temporary_name is not None:
            try:
                unlink_exact(directory_fd, temporary_name)
                try:
                    os.fsync(directory_fd)
                except OSError as sync_error:
                    cleanup_error = sync_error
            except Exception as unlink_error:
                cleanup_error = unlink_error
        if publication_inspection_error is not None:
            raise AcquisitionError(
                "acquisition failed and final publication state could not be inspected; "
                "the retained claim blocks retry and manual output inspection is required: "
                f"{publication_inspection_error}"
            ) from error
        cleanup_suffix = (
            f"; temporary cleanup also failed: {cleanup_error}"
            if cleanup_error is not None
            else ""
        )
        if isinstance(error, AcquisitionError):
            if cleanup_suffix:
                raise AcquisitionError(f"{error}{cleanup_suffix}") from error
            raise
        if isinstance(error, AUTHORITY.RungTwoValidationError):
            raise AcquisitionError(
                f"rung-two authority validation failed: {error}{cleanup_suffix}"
            ) from error
        if isinstance(error, OSError):
            raise AcquisitionError(
                f"filesystem acquisition phase failed: {error}{cleanup_suffix}"
            ) from error
        raise AcquisitionError(
            f"acquisition interrupted by {type(error).__name__}: {error}{cleanup_suffix}"
        ) from error
    finally:
        if temporary_fd >= 0:
            try:
                os.close(temporary_fd)
            except OSError:
                pass
        try:
            os.close(directory_fd)
        except OSError:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute-exact-once", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = execute_exact_once() if args.execute_exact_once else preflight()
    except (AcquisitionError, AUTHORITY.RungTwoValidationError) as error:
        failure: dict[str, Any] = {
            "documentType": "aetherlink.g2-pion-source-acquisition-run-result",
            "schemaVersion": "1.0",
            "status": "failed_closed",
            "reason": str(error),
            "automaticRetryAllowed": False,
            "externalIdentityProofRequired": False,
            "userActionRequired": False,
        }
        if isinstance(error, PublishedArchiveStateError):
            failure.update(
                {
                    "status": "failed_closed_archive_published_completion_uncertain",
                    "archivePublished": True,
                    "directoryFsyncCompleted": error.directory_fsync_completed,
                    "requestCount": error.request_count,
                    "outputPath": OUTPUT_PATH,
                    "claimRetained": True,
                    "manualByteInspectionRequiredBeforeAnyNewDecision": True,
                }
            )
        print(
            json.dumps(failure, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
