#!/usr/bin/env python3
"""Consume the Wave3 v1 permit once and acquire 32 verified proxy resources."""

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
    raise RuntimeError("Wave3 acquisition requires `python3 -I -B -S`")

import argparse
import base64
import binascii
import ctypes
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import secrets
import signal
import ssl
import stat
import struct
import time
import types
from typing import Any, Callable, Mapping, Sequence
import unicodedata
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition_v1.py"
)
EXPECTED_CHECKER_RAW = "ca1cb2a766c4fcb4c6d1cec036352ff0529400554006e8129af4f9eb30f1be2a"
RENAME_EXCL = 0x00000004
MAXIMUM_TOOL_BYTES = 8 * 1024 * 1024
ZIP_LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
ZIP_CENTRAL_HEADER = struct.Struct("<4s6H3L5H2L")
ZIP_EOCD = struct.Struct("<4s4H2LH")
ZIP_DATA_DESCRIPTOR = struct.Struct("<III")
ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE = struct.Struct("<IIII")
ZIP_LOCAL_SIGNATURE = 0x04034B50
ZIP_CENTRAL_SIGNATURE = b"PK\x01\x02"
ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
ZIP_DATA_DESCRIPTOR_SIGNATURE = 0x08074B50
ALLOWED_ZIP_FLAGS = 0x0008 | 0x0800


class AcquisitionError(RuntimeError):
    def __init__(self, code: str, phase: str) -> None:
        super().__init__(f"{code}:{phase}")
        self.code = code
        self.phase = phase


def require(value: bool, code: str, phase: str) -> None:
    if not value:
        raise AcquisitionError(code, phase)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode() + b"\n"


def load_checker() -> tuple[types.ModuleType, bytes]:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(CHECKER_PATH, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_CHECKER",
            "bootstrap",
        )
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_CHECKER", "bootstrap")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(fd, 1), "E_CHECKER", "bootstrap")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        stable_fields = (
            "st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid",
            "st_size", "st_mtime_ns", "st_ctime_ns",
        )
        require(
            all(getattr(before, field) == getattr(after, field) for field in stable_fields)
            and sha256(raw) == EXPECTED_CHECKER_RAW,
            "E_CHECKER",
            "bootstrap",
        )
    finally:
        os.close(fd)
    module = types.ModuleType("wave3_acquisition_permit_v1")
    module.__file__ = str(CHECKER_PATH)
    module.__package__ = ""
    exec(compile(raw, str(CHECKER_PATH), "exec"), module.__dict__)
    return module, raw


CHECK, CHECKER_RAW = load_checker()
Fetch = Callable[[Mapping[str, Any], float], bytes]


def decode_h1(value: str, phase: str) -> bytes:
    require(type(value) is str and value.startswith("h1:"), "E_H1", phase)
    try:
        raw = base64.b64decode(value[3:], validate=True)
    except (binascii.Error, ValueError) as error:
        raise AcquisitionError("E_H1", phase) from error
    require(
        len(raw) == 32
        and base64.b64encode(raw).decode("ascii") == value[3:],
        "E_H1",
        phase,
    )
    return raw


def dirhash_h1(rows: Sequence[tuple[str, str]]) -> str:
    require(bool(rows), "E_H1", "hash")
    seen: set[str] = set()
    lines = []
    for name, digest in rows:
        require(
            type(name) is str
            and name not in seen
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            "E_H1",
            "hash",
        )
        seen.add(name)
        lines.append((name.encode("utf-8"), f"{digest}  {name}\n".encode("utf-8")))
    aggregate = hashlib.sha256(b"".join(line for _, line in sorted(lines))).digest()
    return "h1:" + base64.b64encode(aggregate).decode("ascii")


def go_mod_h1(raw: bytes) -> str:
    return dirhash_h1([("go.mod", sha256(raw))])


def _module_directive_operand(line: str) -> str | None:
    match = re.fullmatch(r"[ \t]*module(?:[ \t]+(.*))?", line)
    if match is None:
        return None
    remainder = match.group(1)
    require(remainder is not None, "E_MOD", "mod")
    remainder = remainder.rstrip(" \t")
    if remainder.startswith('"'):
        require(
            len(remainder) >= 2,
            "E_MOD",
            "mod",
        )
        closing = remainder.find('"', 1)
        require(closing > 1, "E_MOD", "mod")
        value = remainder[1:closing]
        tail = remainder[closing + 1:].lstrip(" \t")
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
    require(0 < len(raw) <= CHECK.MAX_MOD_BYTES and b"\x00" not in raw, "E_MOD", "mod")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise AcquisitionError("E_MOD", "mod") from error
    directives = []
    for line in text.splitlines():
        if re.match(r"^[ \t]*module(?:[ \t]|$)", line):
            operand = _module_directive_operand(line)
            require(operand is not None, "E_MOD", "mod")
            directives.append(operand)
    require(directives == [module], "E_MOD", "mod")
    return {"rawSha256": sha256(raw), "goModH1": go_mod_h1(raw)}


def _safe_zip_name(name: str, prefix: str) -> str:
    require(
        type(name) is str
        and name.startswith(prefix)
        and len(name.encode("utf-8")) <= CHECK.MAX_ZIP_NAME_BYTES
        and name == unicodedata.normalize("NFC", name)
        and not any(character in name for character in ("\x00", "\r", "\n", "\\", ":")),
        "E_ZIP_NAME",
        "zip",
    )
    require(
        not any(ord(character) < 32 or 0x7F <= ord(character) <= 0x9F for character in name),
        "E_ZIP_NAME",
        "zip",
    )
    relative = name[len(prefix):]
    components = relative.split("/")
    require(
        bool(relative)
        and not relative.startswith("/")
        and not relative.endswith("/")
        and len(components) <= 64
        and all(
            component not in {"", ".", ".."}
            and len(component.encode("utf-8")) <= 255
            for component in components
        ),
        "E_ZIP_NAME",
        "zip",
    )
    return relative


def _zip_structure(raw: bytes) -> tuple[int, int, int]:
    require(
        len(raw) >= ZIP_EOCD.size and raw.startswith(b"PK\x03\x04"),
        "E_ZIP_STRUCTURE",
        "zip",
    )
    offset = raw.rfind(
        ZIP_EOCD_SIGNATURE, max(0, len(raw) - ZIP_EOCD.size - 65_535)
    )
    require(offset >= 0 and offset + ZIP_EOCD.size <= len(raw), "E_ZIP_STRUCTURE", "zip")
    (
        signature_value, disk, central_disk, disk_entries, total_entries,
        central_size, central_offset, comment_length,
    ) = ZIP_EOCD.unpack_from(raw, offset)
    require(
        signature_value == ZIP_EOCD_SIGNATURE
        and disk == central_disk == 0
        and disk_entries == total_entries
        and 0 < total_entries <= CHECK.MAX_ZIP_FILES
        and total_entries != 0xFFFF
        and central_size != 0xFFFFFFFF
        and central_offset != 0xFFFFFFFF
        and central_size <= 8 * 1024 * 1024
        and central_offset + central_size == offset
        and comment_length == 0
        and offset + ZIP_EOCD.size == len(raw),
        "E_ZIP_STRUCTURE",
        "zip",
    )
    return total_entries, central_offset, offset


def _parse_extra(extra: bytes) -> None:
    cursor = 0
    while cursor < len(extra):
        require(len(extra) - cursor >= 4, "E_ZIP_EXTRA", "zip")
        field_id, length = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        require(length <= len(extra) - cursor and field_id != 0x0001, "E_ZIP64", "zip")
        cursor += length


def _central_records(
    raw: bytes,
    expected_count: int,
    central_offset: int,
    central_end: int,
) -> dict[int, dict[str, Any]]:
    records = {}
    cursor = central_offset
    while cursor < central_end:
        require(
            cursor + ZIP_CENTRAL_HEADER.size <= central_end,
            "E_ZIP_CENTRAL",
            "zip",
        )
        (
            signature_value, made_version, extract_version, flags, method,
            modified_time, modified_date, crc, compressed_size, file_size,
            name_length, extra_length, comment_length, volume, internal_attr,
            external_attr, local_offset,
        ) = ZIP_CENTRAL_HEADER.unpack_from(raw, cursor)
        require(
            signature_value == ZIP_CENTRAL_SIGNATURE
            and extract_version < 45
            and flags & ~ALLOWED_ZIP_FLAGS == 0
            and compressed_size != 0xFFFFFFFF
            and file_size != 0xFFFFFFFF
            and local_offset != 0xFFFFFFFF
            and volume == 0
            and comment_length == 0
            and local_offset not in records,
            "E_ZIP_CENTRAL",
            "zip",
        )
        name_start = cursor + ZIP_CENTRAL_HEADER.size
        extra_start = name_start + name_length
        comment_start = extra_start + extra_length
        next_cursor = comment_start + comment_length
        require(next_cursor <= central_end, "E_ZIP_CENTRAL", "zip")
        name = raw[name_start:extra_start]
        extra = raw[extra_start:comment_start]
        _parse_extra(extra)
        require(not extra, "E_ZIP_EXTRA", "zip")
        records[local_offset] = {
            "madeVersion": made_version,
            "extractVersion": extract_version,
            "flags": flags,
            "method": method,
            "modifiedTime": modified_time,
            "modifiedDate": modified_date,
            "crc": crc,
            "compressedSize": compressed_size,
            "fileSize": file_size,
            "name": name,
            "extra": extra,
            "internalAttr": internal_attr,
            "externalAttr": external_attr,
            "volume": volume,
        }
        cursor = next_cursor
    require(
        cursor == central_end and len(records) == expected_count,
        "E_ZIP_CENTRAL",
        "zip",
    )
    return records


def _compressed_payloads(
    raw: bytes,
    infos: Sequence[zipfile.ZipInfo],
    central_offset: int,
    central: Mapping[int, Mapping[str, Any]],
) -> dict[int, bytes]:
    ordered = sorted(infos, key=lambda item: item.header_offset)
    require(ordered and ordered[0].header_offset == 0, "E_ZIP_PREFIX", "zip")
    result = {}
    seen = set()
    for index, info in enumerate(ordered):
        offset = info.header_offset
        require(
            offset not in seen
            and 0 <= offset
            and offset + ZIP_LOCAL_HEADER.size <= central_offset,
            "E_ZIP_STRUCTURE",
            "zip",
        )
        seen.add(offset)
        require(offset in central, "E_ZIP_CENTRAL", "zip")
        record = central[offset]
        (
            signature_value, extract_version, flags, method, modified_time, modified_date,
            crc, compressed_size, file_size, name_length, extra_length,
        ) = ZIP_LOCAL_HEADER.unpack_from(raw, offset)
        require(
            signature_value == ZIP_LOCAL_SIGNATURE
            and (
                extract_version, flags, method, modified_time, modified_date,
            )
            == (
                record["extractVersion"], record["flags"], record["method"],
                record["modifiedTime"], record["modifiedDate"],
            )
            and (
                info.extract_version, info.flag_bits, info.compress_type,
                info.CRC, info.compress_size, info.file_size,
            )
            == (
                record["extractVersion"], record["flags"], record["method"],
                record["crc"], record["compressedSize"], record["fileSize"],
            )
            and info.create_version + (info.create_system << 8)
            == record["madeVersion"]
            and info.internal_attr == record["internalAttr"]
            and info.external_attr == record["externalAttr"]
            and info.volume == record["volume"],
            "E_ZIP_STRUCTURE",
            "zip",
        )
        name_start = offset + ZIP_LOCAL_HEADER.size
        extra_start = name_start + name_length
        data_start = extra_start + extra_length
        require(data_start <= central_offset, "E_ZIP_STRUCTURE", "zip")
        raw_name = raw[name_start:extra_start]
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        try:
            local_name = raw_name.decode(encoding, errors="strict")
        except UnicodeDecodeError as error:
            raise AcquisitionError("E_ZIP_NAME", "zip") from error
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
                    (
                        record["crc"],
                        record["compressedSize"],
                        record["fileSize"],
                    ),
                },
                "E_ZIP_DESCRIPTOR",
                "zip",
            )
            descriptor = raw[data_end:boundary]
            if len(descriptor) == ZIP_DATA_DESCRIPTOR.size:
                values = ZIP_DATA_DESCRIPTOR.unpack(descriptor)
            elif len(descriptor) == ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.size:
                signature, *values = ZIP_DATA_DESCRIPTOR_WITH_SIGNATURE.unpack(descriptor)
                require(signature == ZIP_DATA_DESCRIPTOR_SIGNATURE, "E_ZIP_DESCRIPTOR", "zip")
            else:
                raise AcquisitionError("E_ZIP_DESCRIPTOR", "zip")
            require(
                tuple(values) == (info.CRC, info.compress_size, info.file_size)
                and (
                    crc, compressed_size, file_size
                ) in {
                    (0, 0, 0),
                    (info.CRC, info.compress_size, info.file_size),
                },
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
        result[offset] = raw[data_start:data_end]
    return result


def _decode_entry(info: zipfile.ZipInfo, compressed: bytes) -> bytes:
    require(len(compressed) == info.compress_size, "E_ZIP_SIZE", "zip")
    if info.compress_type == zipfile.ZIP_STORED:
        require(info.compress_size == info.file_size, "E_ZIP_SIZE", "zip")
        decoded = compressed
    else:
        decoder = zlib.decompressobj(-zlib.MAX_WBITS)
        try:
            decoded = decoder.decompress(compressed, info.file_size + 1)
            decoded += decoder.flush(info.file_size - len(decoded) + 1)
        except zlib.error as error:
            raise AcquisitionError("E_ZIP_DEFLATE", "zip") from error
        require(
            decoder.eof
            and not decoder.unused_data
            and not decoder.unconsumed_tail,
            "E_ZIP_DEFLATE",
            "zip",
        )
    require(
        len(decoded) == info.file_size
        and len(decoded) <= CHECK.MAX_ZIP_FILE_BYTES
        and zlib.crc32(decoded) & 0xFFFFFFFF == info.CRC,
        "E_ZIP_CRC",
        "zip",
    )
    return decoded


def validate_zip(
    raw: bytes,
    module: str,
    version: str,
    mod_raw: bytes | None = None,
) -> dict[str, Any]:
    require(0 < len(raw) <= CHECK.MAX_ZIP_BYTES, "E_ZIP_SIZE", "zip")
    prefix = f"{module}@{version}/"
    rows: list[tuple[str, str]] = []
    names: set[str] = set()
    folded: set[str] = set()
    relative_files: set[str] = set()
    total = 0
    root_mod: bytes | None = None
    try:
        structural_count, central_offset, central_end = _zip_structure(raw)
        central = _central_records(raw, structural_count, central_offset, central_end)
        archive = zipfile.ZipFile(io.BytesIO(raw), "r")
        require(not archive.comment, "E_ZIP_SHAPE", "zip")
        infos = archive.infolist()
        require(
            0 < len(infos) == structural_count <= CHECK.MAX_ZIP_FILES,
            "E_ZIP_SIZE",
            "zip",
        )
        payloads = _compressed_payloads(raw, infos, central_offset, central)
        require(
            {info.header_offset for info in infos} == set(central),
            "E_ZIP_CENTRAL",
            "zip",
        )
        for info in infos:
            relative = _safe_zip_name(info.filename, prefix)
            folded_name = info.filename.casefold()
            require(
                info.filename not in names
                and folded_name not in folded
                and relative not in relative_files,
                "E_ZIP_DUPLICATE",
                "zip",
            )
            names.add(info.filename)
            folded.add(folded_name)
            relative_files.add(relative)
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
                and 0 <= info.file_size <= CHECK.MAX_ZIP_FILE_BYTES
                and 0 <= info.compress_size <= CHECK.MAX_ZIP_BYTES,
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
                require(
                    info.external_attr & 0x1F == 0,
                    "E_ZIP_MODE",
                    "zip",
                )
            total += info.file_size
            require(total <= CHECK.MAX_ZIP_UNCOMPRESSED_BYTES, "E_ZIP_SIZE", "zip")
            decoded = _decode_entry(info, payloads[info.header_offset])
            if relative == "go.mod":
                root_mod = decoded
            rows.append((info.filename, sha256(decoded)))
        folded_relative_files = {name.casefold() for name in relative_files}
        for relative in relative_files:
            components = relative.split("/")
            require(
                all(
                    "/".join(components[:index]) not in relative_files
                    and "/".join(components[:index]).casefold()
                    not in folded_relative_files
                    for index in range(1, len(components))
                ),
                "E_ZIP_COLLISION",
                "zip",
            )
    except (zipfile.BadZipFile, RuntimeError, ValueError, OSError) as error:
        if isinstance(error, AcquisitionError):
            raise
        raise AcquisitionError("E_ZIP_SHAPE", "zip") from error
    finally:
        try:
            archive.close()
        except (UnboundLocalError, Exception):
            pass
    if root_mod is not None and mod_raw is not None:
        require(root_mod == mod_raw, "E_MOD_PARITY", "zip")
    return {
        "rawSha256": sha256(raw),
        "moduleZipH1": dirhash_h1(rows),
        "entryCount": len(rows),
        "uncompressedBytes": total,
        "rootGoModPresent": root_mod is not None,
    }


def module_zip_h1(raw: bytes, module: str, version: str) -> str:
    return validate_zip(raw, module, version)["moduleZipH1"]


def _remaining(deadline: float, phase: str) -> float:
    value = deadline - time.monotonic()
    require(value > 0, "E_DEADLINE", phase)
    return value


def direct_fetch(
    resource: Mapping[str, Any],
    whole_deadline: float,
    connection_factory: Callable[..., Any] = http.client.HTTPSConnection,
) -> bytes:
    phase = f"request_{resource['requestOrdinal']:02d}"
    require(
        resource["method"] == "GET"
        and resource["host"] == CHECK.PROXY_HOST
        and resource["url"] == f"https://{CHECK.PROXY_HOST}{resource['path']}"
        and resource["path"].startswith("/")
        and "?" not in resource["path"]
        and "#" not in resource["path"],
        "E_REQUEST",
        phase,
    )
    request_deadline = min(
        whole_deadline, time.monotonic() + CHECK.PER_REQUEST_DEADLINE_MS / 1000
    )
    previous_handler = signal.getsignal(signal.SIGALRM)
    old_delay, old_interval = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()

    def alarm_handler(_signum: int, _frame: Any) -> None:
        raise AcquisitionError("E_DEADLINE", phase)

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, _remaining(request_deadline, phase))
    connection = None
    try:
        context = ssl.create_default_context()
        require(
            context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname is True,
            "E_TLS",
            phase,
        )
        connection = connection_factory(
            CHECK.PROXY_HOST,
            443,
            timeout=_remaining(request_deadline, phase),
            context=context,
        )
        connection.request(
            "GET",
            resource["path"],
            body=None,
            headers={
                "Accept": "text/plain" if resource["kind"] == "mod" else "application/zip",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "AetherLink-Wave3-Source-Acquirer/1",
            },
            encode_chunked=False,
        )
        response = connection.getresponse()
        headers = response.getheaders()
        require(
            response.status == 200
            and sum(len(str(k)) + len(str(v)) + 4 for k, v in headers)
            <= CHECK.MAX_HEADER_BYTES
            and response.getheader("Content-Encoding") in {None, "identity"},
            "E_RESPONSE",
            phase,
        )
        lengths = response.getheaders().get_all("Content-Length") if hasattr(response.getheaders(), "get_all") else None
        if lengths is None:
            lengths = [value for key, value in headers if key.lower() == "content-length"]
        require(len(lengths) <= 1, "E_RESPONSE", phase)
        limit = int(resource["maximumResponseBodyBytes"])
        if lengths:
            require(
                re.fullmatch(r"0|[1-9][0-9]*", lengths[0]) is not None
                and 0 < int(lengths[0]) <= limit,
                "E_RESPONSE",
                phase,
            )
        body = bytearray()
        while True:
            chunk = response.read(min(65_536, limit + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            require(len(body) <= limit, "E_RESPONSE_SIZE", phase)
            _remaining(request_deadline, phase)
        require(
            bool(body) and (not lengths or len(body) == int(lengths[0])),
            "E_RESPONSE",
            phase,
        )
        return bytes(body)
    except (OSError, http.client.HTTPException, ssl.SSLError) as error:
        if isinstance(error, AcquisitionError):
            raise
        raise AcquisitionError("E_NETWORK", phase) from error
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        elapsed = time.monotonic() - started
        if old_delay > 0:
            signal.setitimer(signal.ITIMER_REAL, max(0.000001, old_delay - elapsed), old_interval)


def _exclusive_file(path: Path, raw: bytes, mode: int = 0o600) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    try:
        os.fchmod(fd, mode)
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            require(written > 0, "E_WRITE", "filesystem")
            view = view[written:]
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == mode
            and info.st_size == len(raw),
            "E_WRITE",
            "filesystem",
        )
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def create_claim(path: Path, payload: Mapping[str, Any]) -> None:
    raw = canonical_bytes(payload)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    created = False
    fd = -1
    try:
        fd = os.open(path, flags, 0o600)
        created = True
        os.fchmod(fd, 0o600)
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            require(written > 0, "E_CLAIM_STATE_UNCERTAIN", "claim")
            view = view[written:]
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == len(raw),
            "E_CLAIM_STATE_UNCERTAIN",
            "claim",
        )
        os.fsync(fd)
        closing_fd = fd
        fd = -1
        os.close(closing_fd)
        _fsync_directory(path.parent)
    except FileExistsError as error:
        raise AcquisitionError("E_CONSUMED", "claim") from error
    except Exception as error:
        code = "E_CLAIM_STATE_UNCERTAIN" if created else "E_CLAIM_NOT_CREATED"
        raise AcquisitionError(code, "claim") from error
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def rename_exclusive(source: Path, destination: Path) -> None:
    require(not destination.exists(), "E_FINAL_EXISTS", "publish")
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
        -2,
        os.fsencode(source),
        -2,
        os.fsencode(destination),
        RENAME_EXCL,
    )
    if result != 0:
        raise AcquisitionError("E_RENAME", "publish")
    _fsync_directory(destination.parent)


def preflight() -> tuple[dict[str, Any], dict[str, Any]]:
    values, summary = CHECK.evaluate(True)
    permit = values["permit"]
    require(
        summary["validationPassed"] is True
        and summary["status"] == "authorized_not_consumed"
        and summary["requestCount"] == 32
        and permit["status"] == "authorized_not_consumed"
        and permit["authority"]["wave3SourceAcquisitionAuthorizedOnce"] is True
        and permit["authority"]["externalAuthenticationRequired"] is False
        and permit["authority"]["sourceExtractionAuthorized"] is False,
        "E_PREFLIGHT",
        "preflight",
    )
    return values, summary


def _attempt(
    fetch: Fetch,
    values: Mapping[str, Any],
    claim_path: Path,
    dependency_root: Path,
    staging_prefix: str,
    final_root: Path,
    receipt_path: Path,
    failure_path: Path,
    manifest_path: Path,
    publish: Callable[[Path, Path], None],
    resources: Sequence[Mapping[str, Any]] | None = None,
    whole_timeout: float | None = None,
) -> dict[str, Any]:
    permit = values["permit"]
    decision = values["decision"]
    rows = list(resources if resources is not None else permit["requestContract"]["resources"])
    require(len(rows) == 32, "E_RESOURCES", "preflight")
    attempt_id = secrets.token_hex(16)
    claim = {
        "documentType": "aetherlink.wave3-source-acquisition-claim",
        "schemaVersion": "1.0",
        "attemptId": attempt_id,
        "permitContentSha256": permit["contentBinding"]["sha256"],
        "checkerRawSha256": sha256(CHECKER_RAW),
        "requestCount": 32,
        "status": "consumed_active",
    }
    claim_raw = canonical_bytes(claim)
    staging = dependency_root / f"{staging_prefix}{attempt_id}"
    accepted = staging / "accepted"
    evidence = []
    aggregate = 0
    aggregate_mod = 0
    aggregate_zip = 0
    mod_by_tuple: dict[str, bytes] = {}
    publication_attempted = False
    receipt_attempted = False
    request_attempt_count = 0
    response_completed_count = 0
    response_completed_bytes = 0
    validated_count = 0
    persisted_count = 0
    claim_durable = False
    try:
        create_claim(claim_path, claim)
        claim_durable = True
        os.mkdir(staging, 0o700)
        os.mkdir(accepted, 0o700)
        _fsync_directory(dependency_root)
        deadline = time.monotonic() + (
            CHECK.WHOLE_ATTEMPT_DEADLINE_MS / 1000 if whole_timeout is None else whole_timeout
        )
        for ordinal, resource in enumerate(rows, 1):
            require(
                resource["requestOrdinal"] == ordinal
                and _remaining(deadline, f"request_{ordinal:02d}") > 0,
                "E_RESOURCES",
                "request",
            )
            request_attempt_count += 1
            raw = fetch(resource, deadline)
            response_completed_count += 1
            response_completed_bytes += len(raw)
            aggregate += len(raw)
            if resource["kind"] == "mod":
                aggregate_mod += len(raw)
            else:
                aggregate_zip += len(raw)
            require(
                0 < len(raw) <= resource["maximumResponseBodyBytes"]
                and aggregate <= CHECK.MAX_AGGREGATE_BYTES,
                "E_RESPONSE_SIZE",
                f"request_{ordinal:02d}",
            )
            require(
                aggregate_mod <= CHECK.MAX_AGGREGATE_MOD_BYTES
                and aggregate_zip <= CHECK.MAX_AGGREGATE_ZIP_BYTES,
                "E_RESPONSE_SIZE",
                f"request_{ordinal:02d}",
            )
            if resource["kind"] == "mod":
                verified = validate_mod(raw, resource["module"])
                actual_h1 = verified["goModH1"]
                mod_by_tuple[resource["tupleId"]] = raw
            else:
                require(resource["tupleId"] in mod_by_tuple, "E_ORDER", "zip")
                verified = validate_zip(
                    raw,
                    resource["module"],
                    resource["version"],
                    mod_by_tuple[resource["tupleId"]],
                )
                actual_h1 = verified["moduleZipH1"]
            decode_h1(resource["expectedH1"], "h1")
            require(actual_h1 == resource["expectedH1"], "E_H1_MISMATCH", "verification")
            validated_count += 1
            destination = accepted / resource["acceptedFileName"]
            _exclusive_file(destination, raw, 0o600)
            persisted_count += 1
            evidence.append({
                "requestOrdinal": ordinal,
                "tupleId": resource["tupleId"],
                "kind": resource["kind"],
                "url": resource["url"],
                "byteCount": len(raw),
                "rawSha256": sha256(raw),
                "verifiedH1": actual_h1,
                "acceptedFileName": resource["acceptedFileName"],
                **{key: value for key, value in verified.items() if key not in {"rawSha256", "goModH1", "moduleZipH1"}},
            })
        require(
            len(evidence) == 32
            and len(mod_by_tuple) == 16
            and aggregate <= CHECK.MAX_AGGREGATE_BYTES,
            "E_CARDINALITY",
            "verification",
        )
        evidence_payload = {
            "documentType": "aetherlink.wave3-source-acquisition-evidence",
            "schemaVersion": "1.0",
            "attemptId": attempt_id,
            "requestCount": 32,
            "aggregateResponseBytes": aggregate,
            "aggregateModResponseBytes": aggregate_mod,
            "aggregateZipResponseBytes": aggregate_zip,
            "resources": evidence,
        }
        evidence_raw = canonical_bytes(evidence_payload)
        _exclusive_file(staging / "evidence.json", evidence_raw, 0o600)
        _fsync_directory(accepted)
        _fsync_directory(staging)
        publication_attempted = True
        publish(staging, final_root)
        receipt = {
            "documentType": "aetherlink.wave3-source-acquisition-receipt",
            "schemaVersion": "1.0",
            "status": "consumed_success_pending_readback",
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
            "acceptedResourceHashSetCanonicalSha256": sha256(canonical_bytes([
                {
                    "requestOrdinal": row["requestOrdinal"],
                    "acceptedFileName": row["acceptedFileName"],
                    "rawSha256": row["rawSha256"],
                    "verifiedH1": row["verifiedH1"],
                }
                for row in evidence
            ])),
            "requestCount": 32,
            "modCount": 16,
            "zipCount": 16,
            "acceptedResourceCount": 32,
            "aggregateResponseBytes": aggregate,
            "aggregateModResponseBytes": aggregate_mod,
            "aggregateZipResponseBytes": aggregate_zip,
            "acceptedPath": CHECK.FINAL_ACCEPTED,
            "sourceAcquired": True,
            "sourceExtracted": False,
            "sourceLoadedOrExecuted": False,
            "compiled": False,
        }
        receipt_raw = canonical_bytes(receipt)
        receipt_attempted = True
        _exclusive_file(receipt_path, receipt_raw, 0o600)
        _fsync_directory(receipt_path.parent)
        manifest = {
            "documentType": "aetherlink.wave3-source-acquisition-manifest",
            "schemaVersion": "1.0",
            "status": "consumed_success_pending_readback",
            "attemptId": attempt_id,
            "receiptPath": CHECK.RECEIPT_PATH,
            "receiptRawSha256": sha256(receipt_raw),
            "manifestWrittenLast": True,
        }
        _exclusive_file(manifest_path, canonical_bytes(manifest), 0o600)
        _fsync_directory(manifest_path.parent)
        return receipt
    except Exception as error:
        if not claim_durable:
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
            "documentType": "aetherlink.wave3-source-acquisition-failure",
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
            "resourceSetCanonicalSha256": permit["requestContract"]["resourcesCanonicalSha256"],
            "requestAttemptCount": request_attempt_count,
            "responseCompletedCount": response_completed_count,
            "responseCompletedBytes": response_completed_bytes,
            "validatedResourceCount": validated_count,
            "persistedResourceCount": persisted_count,
            "sourceAcquired": response_completed_count > 0,
            "sourceExtracted": False,
            "retryResumeOrBackfillAllowed": False,
            "claimRetained": True,
            "stagingRetained": staging.exists(),
        }
        if publication_attempted or receipt_attempted:
            raise AcquisitionError("E_POST_PUBLISH_UNCERTAIN", "terminal_state") from error
        else:
            try:
                _exclusive_file(failure_path, canonical_bytes(failure), 0o600)
                _fsync_directory(failure_path.parent)
            except Exception as publication_error:
                raise AcquisitionError(
                    "E_FAILURE_PUBLICATION_UNCERTAIN",
                    "failure_terminal",
                ) from publication_error
        raise AcquisitionError(code, phase) from error


def execute(fetch: Fetch = direct_fetch) -> dict[str, Any]:
    values, _ = preflight()
    old_umask = os.umask(0o077)
    previous_handler = signal.getsignal(signal.SIGALRM)
    old_delay, old_interval = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()

    def alarm_handler(_signum: int, _frame: Any) -> None:
        raise AcquisitionError("E_DEADLINE", "whole_attempt")

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, CHECK.WHOLE_ATTEMPT_DEADLINE_MS / 1000)
    try:
        return _attempt(
            fetch,
            values,
            ROOT / CHECK.CLAIM_PATH,
            ROOT / CHECK.DEPENDENCY_ROOT,
            CHECK.STAGING_PREFIX,
            ROOT / CHECK.FINAL_ROOT,
            ROOT / CHECK.RECEIPT_PATH,
            ROOT / CHECK.FAILURE_PATH,
            ROOT / CHECK.MANIFEST_PATH,
            rename_exclusive,
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


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise AcquisitionError("E_ARGUMENT", "cli")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False)
        parser.add_argument("--execute", action="store_true")
        args = parser.parse_args(argv)
        require(args.execute, "E_ARGUMENT", "cli")
        result = execute()
        sys.stdout.buffer.write(canonical_bytes(result))
        return 0
    except AcquisitionError as error:
        if error.code == "E_CONSUMED":
            status = "already_consumed"
        elif error.code in {
            "E_CLAIM_STATE_UNCERTAIN",
            "E_FAILURE_PUBLICATION_UNCERTAIN",
            "E_POST_PUBLISH_UNCERTAIN",
        }:
            status = "consumed_terminal_state_uncertain"
        else:
            status = "failed_closed"
        sys.stdout.buffer.write(canonical_bytes({
            "documentType": "aetherlink.wave3-source-acquisition-error",
            "schemaVersion": "1.0",
            "status": status,
            "failureCode": error.code,
            "failurePhase": error.phase,
            "retryAllowed": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }))
        return 1
    except Exception:
        sys.stdout.buffer.write(canonical_bytes({
            "documentType": "aetherlink.wave3-source-acquisition-error",
            "schemaVersion": "1.0",
            "status": "failed_closed",
            "failureCode": "E_INTERNAL",
            "failurePhase": "runner",
            "retryAllowed": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
