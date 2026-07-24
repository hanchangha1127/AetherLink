#!/usr/bin/env python3
"""Pure, bytes-only validation for the bounded G2 Pion module ZIP.

This module deliberately has no filesystem, process, network, dynamic-import,
or device API.  A caller must first read and authenticate the retained archive
through its separately permitted single file descriptor, then pass the exact
retained bytes to :func:`inspect_module_zip`.

Decoded source bytes are returned only as in-memory ``bytes`` values.  They are
not included in any JSON helper or written anywhere by this module.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import struct
from typing import Any
import unicodedata
import zlib


class OfflineZipValidationError(RuntimeError):
    """A fail-closed structural or content-validation failure."""


DEFAULT_LIMITS: Mapping[str, int] = {
    "archiveBytes": 512 * 1024,
    "entryCount": 4096,
    "centralDirectoryBytes": 4 * 1024 * 1024,
    "pathBytes": 1024,
    "pathComponents": 32,
    "componentBytes": 255,
    "singleFileBytes": 4 * 1024 * 1024,
    "totalUncompressedBytes": 64 * 1024 * 1024,
    "compressionRatio": 200,
}

LOCAL_HEADER = struct.Struct("<4s5H3I2H")
CENTRAL_HEADER = struct.Struct("<4s6H3I5H2I")
EOCD = struct.Struct("<4s4H2IH")
DATA_DESCRIPTOR = struct.Struct("<3I")
SIGNED_DATA_DESCRIPTOR = struct.Struct("<4I")

LOCAL_SIGNATURE = b"PK\x03\x04"
CENTRAL_SIGNATURE = b"PK\x01\x02"
EOCD_SIGNATURE = b"PK\x05\x06"
DATA_DESCRIPTOR_SIGNATURE = 0x08074B50

ZIP64_EXTRA_FIELD_ID = 0x0001
UNICODE_PATH_EXTRA_FIELD_ID = 0x7075
UNICODE_COMMENT_EXTRA_FIELD_ID = 0x6375
STRONG_ENCRYPTION_EXTRA_FIELD_ID = 0x0017
AES_EXTRA_FIELD_ID = 0x9901
FORBIDDEN_EXTRA_FIELD_IDS = {
    ZIP64_EXTRA_FIELD_ID,
    UNICODE_PATH_EXTRA_FIELD_ID,
    UNICODE_COMMENT_EXTRA_FIELD_ID,
    STRONG_ENCRYPTION_EXTRA_FIELD_ID,
    AES_EXTRA_FIELD_ID,
}

UTF8_FLAG = 0x0800
DATA_DESCRIPTOR_FLAG = 0x0008
ENCRYPTED_FLAG = 0x0001
ALLOWED_FLAGS = UTF8_FLAG | DATA_DESCRIPTOR_FLAG

STORED_METHOD = 0
DEFLATED_METHOD = 8
ALLOWED_METHODS = {STORED_METHOD, DEFLATED_METHOD}

UNIX_CREATOR = 3
UNIX_TYPE_MASK = 0o170000
UNIX_REGULAR = 0o100000
UNIX_DIRECTORY = 0o040000
UNIX_SPECIAL_PERMISSION_BITS = 0o7000
UNIX_EXECUTABLE_BITS = 0o111

DOS_HIDDEN = 0x02
DOS_SYSTEM = 0x04
DOS_VOLUME_LABEL = 0x08
DOS_DIRECTORY = 0x10
FORBIDDEN_DOS_ATTRIBUTES = DOS_HIDDEN | DOS_SYSTEM | DOS_VOLUME_LABEL

ZIP64_VERSION = 45


def _fail(message: str) -> None:
    raise OfflineZipValidationError(message)


def _resolve_limits(limits: Mapping[str, int] | None) -> dict[str, int]:
    resolved = dict(DEFAULT_LIMITS)
    if limits is None:
        return resolved
    if not isinstance(limits, Mapping):
        _fail("limits must be a mapping")
    unknown = set(limits) - set(DEFAULT_LIMITS)
    if unknown:
        _fail(f"unknown limit keys: {sorted(unknown)!r}")
    for key, value in limits.items():
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(f"limit {key!r} must be an integer")
        if value < 1 or value > DEFAULT_LIMITS[key]:
            _fail(
                f"limit {key!r} must be positive and may only tighten its hard ceiling"
            )
        resolved[key] = value
    return resolved


def _utf8(value: str, label: str) -> bytes:
    try:
        return value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise OfflineZipValidationError(
            f"{label} is not valid Unicode for UTF-8"
        ) from error


def _validate_module_prefix(module_prefix: str, limits: Mapping[str, int]) -> None:
    if not isinstance(module_prefix, str) or not module_prefix.endswith("/"):
        _fail("module_prefix must be a non-empty string ending in '/'")
    _validate_path(
        module_prefix,
        is_directory=True,
        module_prefix=None,
        limits=limits,
    )


def _decode_name(raw_name: bytes, flags: int, label: str) -> str:
    if not raw_name:
        _fail(f"{label} has an empty filename")
    if flags & UTF8_FLAG:
        encoding = "utf-8"
    else:
        if any(byte >= 0x80 for byte in raw_name):
            _fail(f"{label} has a non-ASCII filename without the UTF-8 flag")
        encoding = "ascii"
    try:
        return raw_name.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        raise OfflineZipValidationError(
            f"{label} has an invalid filename encoding"
        ) from error


def _validate_path(
    name: str,
    *,
    is_directory: bool,
    module_prefix: str | None,
    limits: Mapping[str, int],
) -> tuple[str, str]:
    raw_name = _utf8(name, "ZIP entry path")
    if not raw_name or len(raw_name) > limits["pathBytes"]:
        _fail("ZIP entry path is empty or exceeds the path byte ceiling")
    if (
        name.startswith("/")
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        _fail(f"ZIP entry path is unsafe: {name!r}")
    if unicodedata.normalize("NFC", name) != name:
        _fail(f"ZIP entry path is not NFC-normalized: {name!r}")
    if name.endswith("/") != is_directory:
        _fail(f"ZIP directory suffix does not match entry type: {name!r}")

    canonical = name[:-1] if is_directory else name
    components = canonical.split("/")
    if (
        not canonical
        or not components
        or len(components) > limits["pathComponents"]
        or any(component in {"", ".", ".."} for component in components)
    ):
        _fail(f"ZIP entry path is noncanonical or over-bounded: {name!r}")
    for component in components:
        if len(_utf8(component, "ZIP path component")) > limits["componentBytes"]:
            _fail(f"ZIP path component exceeds its byte ceiling: {name!r}")

    if module_prefix is None:
        return canonical, ""
    if not name.startswith(module_prefix):
        _fail(f"ZIP entry is outside the exact module prefix: {name!r}")
    relative = name[len(module_prefix) :]
    if not relative and not is_directory:
        _fail("ZIP contains a file at the module directory path")
    return canonical, relative


def _parse_extra_fields(extra: bytes, label: str) -> tuple[dict[str, Any], ...]:
    offset = 0
    seen_ids: set[int] = set()
    metadata: list[dict[str, Any]] = []
    while offset < len(extra):
        if len(extra) - offset < 4:
            _fail(f"{label} has a truncated extra-field header")
        field_id, field_length = struct.unpack_from("<HH", extra, offset)
        offset += 4
        if field_length > len(extra) - offset:
            _fail(f"{label} has a truncated extra-field payload")
        if field_id in seen_ids:
            _fail(f"{label} repeats extra-field ID 0x{field_id:04x}")
        if field_id in FORBIDDEN_EXTRA_FIELD_IDS:
            _fail(f"{label} uses forbidden extra-field ID 0x{field_id:04x}")
        payload = extra[offset : offset + field_length]
        metadata.append(
            {
                "id": field_id,
                "size": field_length,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        seen_ids.add(field_id)
        offset += field_length
    return tuple(metadata)


def _parse_eocd(
    raw_archive: bytes, limits: Mapping[str, int]
) -> tuple[int, int, int]:
    if len(raw_archive) < LOCAL_HEADER.size + EOCD.size:
        _fail("archive is too small to contain one local entry and an EOCD")
    if len(raw_archive) > limits["archiveBytes"]:
        _fail("archive exceeds the raw byte ceiling")
    if not raw_archive.startswith(LOCAL_SIGNATURE):
        _fail("archive has a forbidden prefix before its first local header")

    eocd_offset = len(raw_archive) - EOCD.size
    (
        signature,
        disk_number,
        central_disk,
        disk_entries,
        total_entries,
        central_size,
        central_offset,
        comment_length,
    ) = EOCD.unpack_from(raw_archive, eocd_offset)
    if signature != EOCD_SIGNATURE:
        _fail("archive has no exact terminal EOCD record")
    if comment_length != 0:
        _fail("archive comments and trailing data are forbidden")
    if disk_number != 0 or central_disk != 0 or disk_entries != total_entries:
        _fail("multi-disk ZIP archives are forbidden")
    if (
        disk_entries == 0xFFFF
        or total_entries == 0xFFFF
        or central_size == 0xFFFFFFFF
        or central_offset == 0xFFFFFFFF
    ):
        _fail("ZIP64 EOCD sentinel values are forbidden")
    if total_entries < 1 or total_entries > limits["entryCount"]:
        _fail("ZIP entry count is empty or exceeds its ceiling")
    if central_size > limits["centralDirectoryBytes"]:
        _fail("central directory exceeds its byte ceiling")
    if central_offset + central_size != eocd_offset:
        _fail("central directory does not end exactly at the EOCD")
    if central_offset < LOCAL_HEADER.size:
        _fail("central directory overlaps or precedes local entry data")
    return total_entries, central_offset, central_size


def _validate_entry_mode(
    *,
    path: str,
    version_made_by: int,
    external_attributes: int,
    is_directory: bool,
) -> int:
    creator = (version_made_by >> 8) & 0xFF
    if creator != UNIX_CREATOR:
        _fail(f"ZIP entry lacks auditable Unix mode metadata: {path!r}")
    dos_attributes = external_attributes & 0xFF
    if dos_attributes & FORBIDDEN_DOS_ATTRIBUTES:
        _fail(f"ZIP entry uses hidden, system, or volume attributes: {path!r}")
    if bool(dos_attributes & DOS_DIRECTORY) != is_directory:
        _fail(f"DOS directory attribute differs from the path type: {path!r}")

    unix_mode = (external_attributes >> 16) & 0xFFFF
    unix_type = unix_mode & UNIX_TYPE_MASK
    permitted_types = {0, UNIX_DIRECTORY if is_directory else UNIX_REGULAR}
    if unix_type not in permitted_types:
        _fail(f"symlink, hardlink-like, or special ZIP entry is forbidden: {path!r}")
    if unix_mode & UNIX_SPECIAL_PERMISSION_BITS:
        _fail(f"ZIP entry uses special permission bits: {path!r}")
    if not is_directory and unix_mode & UNIX_EXECUTABLE_BITS:
        _fail(f"executable ZIP entry is forbidden: {path!r}")
    return unix_mode


def _parse_central_directory(
    raw_archive: bytes,
    *,
    entry_count: int,
    central_offset: int,
    central_size: int,
    module_prefix: str,
    limits: Mapping[str, int],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    cursor = central_offset
    central_end = central_offset + central_size
    for central_index in range(entry_count):
        if cursor + CENTRAL_HEADER.size > central_end:
            _fail("central directory header is truncated")
        (
            signature,
            version_made_by,
            version_needed,
            flags,
            compression_method,
            modified_time,
            modified_date,
            crc32_value,
            compressed_size,
            uncompressed_size,
            name_length,
            extra_length,
            comment_length,
            starting_disk,
            internal_attributes,
            external_attributes,
            local_header_offset,
        ) = CENTRAL_HEADER.unpack_from(raw_archive, cursor)
        if signature != CENTRAL_SIGNATURE:
            _fail("central directory contains hidden or non-entry data")
        if version_needed >= ZIP64_VERSION:
            _fail("ZIP64-capable entry versions are forbidden")
        if flags & ENCRYPTED_FLAG or flags & ~ALLOWED_FLAGS:
            _fail("encrypted or unsupported ZIP flags are forbidden")
        if compression_method not in ALLOWED_METHODS:
            _fail("unsupported ZIP compression method")
        if starting_disk != 0:
            _fail("multi-disk central-directory entries are forbidden")
        if (
            compressed_size == 0xFFFFFFFF
            or uncompressed_size == 0xFFFFFFFF
            or local_header_offset == 0xFFFFFFFF
        ):
            _fail("ZIP64 central-directory sentinel values are forbidden")
        if comment_length != 0:
            _fail("per-entry ZIP comments are forbidden")

        name_start = cursor + CENTRAL_HEADER.size
        extra_start = name_start + name_length
        comment_start = extra_start + extra_length
        next_cursor = comment_start + comment_length
        if next_cursor > central_end:
            _fail("central directory variable-length fields are truncated")
        raw_name = raw_archive[name_start:extra_start]
        name = _decode_name(raw_name, flags, "central directory entry")
        is_directory = name.endswith("/")
        canonical, relative = _validate_path(
            name,
            is_directory=is_directory,
            module_prefix=module_prefix,
            limits=limits,
        )
        extra_fields = _parse_extra_fields(
            raw_archive[extra_start:comment_start],
            f"{name!r} central metadata",
        )
        unix_mode = _validate_entry_mode(
            path=name,
            version_made_by=version_made_by,
            external_attributes=external_attributes,
            is_directory=is_directory,
        )
        if is_directory and (
            crc32_value != 0 or compressed_size != 0 or uncompressed_size != 0
        ):
            _fail(f"directory entry contains declared data: {name!r}")
        if uncompressed_size > limits["singleFileBytes"]:
            _fail(f"ZIP entry exceeds the single-file ceiling: {name!r}")

        entries.append(
            {
                "_centralIndex": central_index,
                "_rawName": raw_name,
                "_versionNeeded": version_needed,
                "_flags": flags,
                "_method": compression_method,
                "_modifiedTime": modified_time,
                "_modifiedDate": modified_date,
                "_crc32": crc32_value,
                "_compressedSize": compressed_size,
                "_uncompressedSize": uncompressed_size,
                "_localHeaderOffset": local_header_offset,
                "_centralExtraFields": extra_fields,
                "_internalAttributes": internal_attributes,
                "_externalAttributes": external_attributes,
                "_unixMode": unix_mode,
                "path": name,
                "relativePath": relative,
                "isDirectory": is_directory,
                "_canonical": canonical,
            }
        )
        cursor = next_cursor
    if cursor != central_end:
        _fail("central directory contains trailing, hidden, or duplicate data")
    return entries


def _validate_path_collisions(entries: list[dict[str, Any]]) -> None:
    exact_names: set[str] = set()
    full_spelling_by_folded: dict[str, str] = {}
    directory_spelling_by_folded: dict[str, str] = {}
    file_keys: set[str] = set()
    directory_keys: set[str] = set()

    for entry in entries:
        name = entry["path"]
        canonical = entry["_canonical"]
        is_directory = entry["isDirectory"]
        if name in exact_names:
            _fail(f"duplicate ZIP path is forbidden: {name!r}")
        exact_names.add(name)

        folded = unicodedata.normalize("NFC", canonical.casefold())
        previous = full_spelling_by_folded.get(folded)
        if previous is not None:
            _fail(
                "case-fold or file/directory path collision: "
                f"{previous!r} versus {canonical!r}"
            )
        full_spelling_by_folded[folded] = canonical
        if is_directory:
            directory_keys.add(folded)
        else:
            file_keys.add(folded)

        components = canonical.split("/")
        parent_count = len(components) if is_directory else len(components) - 1
        for component_count in range(1, parent_count + 1):
            parent = "/".join(components[:component_count])
            parent_folded = unicodedata.normalize("NFC", parent.casefold())
            previous_parent = directory_spelling_by_folded.get(parent_folded)
            if previous_parent is not None and previous_parent != parent:
                _fail(
                    "case-fold-colliding directory spelling is forbidden: "
                    f"{previous_parent!r} versus {parent!r}"
                )
            directory_spelling_by_folded[parent_folded] = parent

    implied_directory_keys = set(directory_spelling_by_folded)
    collision = file_keys & (directory_keys | implied_directory_keys)
    if collision:
        _fail("ZIP contains a file/directory or file-prefix collision")


def _validate_local_headers(
    raw_archive: bytes,
    *,
    entries: list[dict[str, Any]],
    central_offset: int,
) -> dict[int, bytes]:
    ordered = sorted(entries, key=lambda entry: entry["_localHeaderOffset"])
    if ordered[0]["_localHeaderOffset"] != 0:
        _fail("archive has a forbidden prefix before the first local header")

    payloads: dict[int, bytes] = {}
    seen_offsets: set[int] = set()
    cursor = 0
    for index, entry in enumerate(ordered):
        offset = entry["_localHeaderOffset"]
        path = entry["path"]
        if offset in seen_offsets:
            _fail("multiple central entries reference one local header")
        seen_offsets.add(offset)
        if offset != cursor:
            _fail(f"local entry layout has a gap, overlap, or hidden data: {path!r}")
        if offset + LOCAL_HEADER.size > central_offset:
            _fail(f"local header is truncated or out of range: {path!r}")

        (
            signature,
            version_needed,
            flags,
            compression_method,
            modified_time,
            modified_date,
            crc32_value,
            compressed_size,
            uncompressed_size,
            name_length,
            extra_length,
        ) = LOCAL_HEADER.unpack_from(raw_archive, offset)
        if signature != LOCAL_SIGNATURE:
            _fail(f"local header signature is invalid: {path!r}")
        if version_needed >= ZIP64_VERSION:
            _fail(f"local header uses a ZIP64-capable version: {path!r}")
        if (
            version_needed != entry["_versionNeeded"]
            or flags != entry["_flags"]
            or compression_method != entry["_method"]
            or modified_time != entry["_modifiedTime"]
            or modified_date != entry["_modifiedDate"]
        ):
            _fail(f"local and central header metadata differ: {path!r}")

        name_start = offset + LOCAL_HEADER.size
        extra_start = name_start + name_length
        data_start = extra_start + extra_length
        if data_start > central_offset:
            _fail(f"local filename or extra fields exceed the data region: {path!r}")
        raw_name = raw_archive[name_start:extra_start]
        local_name = _decode_name(raw_name, flags, f"{path!r} local header")
        if raw_name != entry["_rawName"] or local_name != path:
            _fail(f"local and central filenames differ: {path!r}")
        local_extra_fields = _parse_extra_fields(
            raw_archive[extra_start:data_start],
            f"{path!r} local metadata",
        )

        data_end = data_start + entry["_compressedSize"]
        next_boundary = (
            ordered[index + 1]["_localHeaderOffset"]
            if index + 1 < len(ordered)
            else central_offset
        )
        if data_end > next_boundary:
            _fail(f"compressed data ranges overlap: {path!r}")

        if flags & DATA_DESCRIPTOR_FLAG:
            descriptor = raw_archive[data_end:next_boundary]
            if len(descriptor) == DATA_DESCRIPTOR.size:
                descriptor_crc, descriptor_compressed, descriptor_uncompressed = (
                    DATA_DESCRIPTOR.unpack(descriptor)
                )
            elif len(descriptor) == SIGNED_DATA_DESCRIPTOR.size:
                (
                    descriptor_signature,
                    descriptor_crc,
                    descriptor_compressed,
                    descriptor_uncompressed,
                ) = SIGNED_DATA_DESCRIPTOR.unpack(descriptor)
                if descriptor_signature != DATA_DESCRIPTOR_SIGNATURE:
                    _fail(f"data descriptor signature is invalid: {path!r}")
            else:
                _fail(f"data descriptor length is invalid: {path!r}")
            if (
                descriptor_crc != entry["_crc32"]
                or descriptor_compressed != entry["_compressedSize"]
                or descriptor_uncompressed != entry["_uncompressedSize"]
            ):
                _fail(f"data descriptor differs from central metadata: {path!r}")
            if crc32_value not in (0, entry["_crc32"]):
                _fail(f"local CRC differs from central metadata: {path!r}")
            if compressed_size not in (0, entry["_compressedSize"]):
                _fail(f"local compressed size differs from central metadata: {path!r}")
            if uncompressed_size not in (0, entry["_uncompressedSize"]):
                _fail(
                    f"local uncompressed size differs from central metadata: {path!r}"
                )
        else:
            if data_end != next_boundary:
                _fail(f"unexpected data follows the local payload: {path!r}")
            if (
                crc32_value != entry["_crc32"]
                or compressed_size != entry["_compressedSize"]
                or uncompressed_size != entry["_uncompressedSize"]
            ):
                _fail(f"local and central CRC or sizes differ: {path!r}")

        payloads[offset] = raw_archive[data_start:data_end]
        entry["_localExtraFields"] = local_extra_fields
        entry["_dataOffset"] = data_start
        cursor = next_boundary
    if cursor != central_offset:
        _fail("local entry region contains trailing or hidden data")
    return payloads


def _decode_exact(entry: Mapping[str, Any], compressed_payload: bytes) -> bytes:
    path = entry["path"]
    expected_compressed = entry["_compressedSize"]
    expected_uncompressed = entry["_uncompressedSize"]
    if len(compressed_payload) != expected_compressed:
        _fail(f"compressed payload size differs from metadata: {path!r}")

    if entry["_method"] == STORED_METHOD:
        if expected_compressed != expected_uncompressed:
            _fail(f"stored entry size metadata differs: {path!r}")
        decoded = compressed_payload
    elif entry["_method"] == DEFLATED_METHOD:
        decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
        try:
            decoded_buffer = bytearray(
                decompressor.decompress(
                    compressed_payload,
                    expected_uncompressed + 1,
                )
            )
            if (
                len(decoded_buffer) > expected_uncompressed
                or decompressor.unconsumed_tail
            ):
                _fail(f"deflate output exceeds its declared size: {path!r}")
            decoded_buffer.extend(
                decompressor.flush(expected_uncompressed - len(decoded_buffer) + 1)
            )
        except zlib.error as error:
            raise OfflineZipValidationError(
                f"raw deflate validation failed for {path!r}: {error}"
            ) from error
        if len(decoded_buffer) > expected_uncompressed:
            _fail(f"deflate output exceeds its declared size: {path!r}")
        if (
            not decompressor.eof
            or decompressor.unused_data
            or decompressor.unconsumed_tail
        ):
            _fail(f"deflate stream is incomplete or contains hidden data: {path!r}")
        decoded = bytes(decoded_buffer)
    else:
        _fail(f"unsupported compression method: {path!r}")

    if len(decoded) != expected_uncompressed:
        _fail(f"decompressed size mismatch: {path!r}")
    if zlib.crc32(decoded) & 0xFFFFFFFF != entry["_crc32"]:
        _fail(f"CRC mismatch: {path!r}")
    return decoded


def _public_entry(entry: Mapping[str, Any], decoded: bytes) -> dict[str, Any]:
    """Return deterministic metadata while retaining source only as bytes."""

    return {
        "path": entry["path"],
        "relativePath": entry["relativePath"],
        "isDirectory": entry["isDirectory"],
        "bytes": decoded,
        "size": len(decoded),
        "compressedSize": entry["_compressedSize"],
        "compressionMethod": entry["_method"],
        "crc32": f"{entry['_crc32']:08x}",
        "sha256": hashlib.sha256(decoded).hexdigest(),
        "unixMode": f"{entry['_unixMode']:06o}",
        "localHeaderOffset": entry["_localHeaderOffset"],
        "dataOffset": entry["_dataOffset"],
        "centralDirectoryIndex": entry["_centralIndex"],
        "localExtraFields": entry["_localExtraFields"],
        "centralExtraFields": entry["_centralExtraFields"],
    }


def _tree_sha256(entries: tuple[dict[str, Any], ...]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        path_bytes = entry["path"].encode("utf-8")
        digest.update(b"D" if entry["isDirectory"] else b"F")
        digest.update(len(path_bytes).to_bytes(4, "big"))
        digest.update(path_bytes)
        digest.update(entry["size"].to_bytes(8, "big"))
        digest.update(bytes.fromhex(entry["sha256"]))
    return digest.hexdigest()


def inspect_module_zip(
    raw_archive: bytes,
    *,
    module_prefix: str,
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Validate one complete module ZIP and return bounded in-memory entries.

    ``limits`` may tighten, but can never relax, the module's hard ceilings.
    The returned ``entries`` tuple is sorted by UTF-8 archive path bytes.  Each
    entry contains decoded source under the ``bytes`` key; callers must exclude
    that key from serialized evidence and reports.
    """

    if not isinstance(raw_archive, bytes):
        _fail("raw_archive must be an immutable bytes value")
    resolved_limits = _resolve_limits(limits)
    _validate_module_prefix(module_prefix, resolved_limits)
    entry_count, central_offset, central_size = _parse_eocd(
        raw_archive, resolved_limits
    )
    entries = _parse_central_directory(
        raw_archive,
        entry_count=entry_count,
        central_offset=central_offset,
        central_size=central_size,
        module_prefix=module_prefix,
        limits=resolved_limits,
    )
    _validate_path_collisions(entries)
    payloads = _validate_local_headers(
        raw_archive,
        entries=entries,
        central_offset=central_offset,
    )

    total_uncompressed = 0
    public_entries: list[dict[str, Any]] = []
    root_go_mod_count = 0
    for entry in entries:
        if entry["_uncompressedSize"] > resolved_limits["singleFileBytes"]:
            _fail(f"ZIP entry exceeds the single-file ceiling: {entry['path']!r}")
        total_uncompressed += entry["_uncompressedSize"]
        if total_uncompressed > resolved_limits["totalUncompressedBytes"]:
            _fail("ZIP exceeds the total uncompressed byte ceiling")
        if (
            entry["_uncompressedSize"] > 0
            and (
                entry["_compressedSize"] == 0
                or entry["_uncompressedSize"]
                > entry["_compressedSize"] * resolved_limits["compressionRatio"]
            )
        ):
            _fail(f"ZIP entry exceeds the compression-ratio ceiling: {entry['path']!r}")

        decoded = _decode_exact(
            entry,
            payloads[entry["_localHeaderOffset"]],
        )
        if entry["isDirectory"] and decoded:
            _fail(f"directory entry yielded content: {entry['path']!r}")
        if not entry["isDirectory"] and entry["relativePath"] == "go.mod":
            root_go_mod_count += 1
        public_entries.append(_public_entry(entry, decoded))

    if root_go_mod_count != 1:
        _fail("archive must contain exactly one regular root go.mod")

    deterministic_entries = tuple(
        sorted(public_entries, key=lambda entry: entry["path"].encode("utf-8"))
    )
    file_count = sum(not entry["isDirectory"] for entry in deterministic_entries)
    if file_count < 1:
        _fail("archive contains no regular source files")
    return {
        "rawSha256": hashlib.sha256(raw_archive).hexdigest(),
        "archiveBytes": len(raw_archive),
        "entryCount": len(deterministic_entries),
        "fileCount": file_count,
        "directoryCount": len(deterministic_entries) - file_count,
        "centralDirectoryOffset": central_offset,
        "centralDirectoryBytes": central_size,
        "totalCompressedBytes": sum(
            entry["compressedSize"] for entry in deterministic_entries
        ),
        "totalUncompressedBytes": total_uncompressed,
        "treeSha256": _tree_sha256(deterministic_entries),
        "archiveExtracted": False,
        "entries": deterministic_entries,
    }
