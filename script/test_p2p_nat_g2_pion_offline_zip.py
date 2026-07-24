#!/usr/bin/env python3
"""Synthetic, bytes-only tests for the G2 Pion offline ZIP validator."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import struct
from types import ModuleType
import unittest
import warnings
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
TARGET_RELATIVE_FILENAME = "script/p2p_nat_g2_pion_offline_zip.py"
TARGET_SOURCE = (ROOT / TARGET_RELATIVE_FILENAME).read_bytes()
TARGET = ModuleType("p2p_nat_g2_pion_offline_zip")
TARGET.__file__ = TARGET_RELATIVE_FILENAME
exec(
    compile(
        TARGET_SOURCE,
        TARGET_RELATIVE_FILENAME,
        "exec",
        dont_inherit=True,
        optimize=0,
    ),
    TARGET.__dict__,
)


MODULE_PREFIX = "github.com/pion/ice/v4@v4.3.0/"
GO_MOD = MODULE_PREFIX + "go.mod"
ICE_GO = MODULE_PREFIX + "ice.go"


def raw_deflate(content: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-zlib.MAX_WBITS)
    return compressor.compress(content) + compressor.flush()


def regular_info(
    name: str,
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    mode: int = 0o100644,
    dos_attributes: int = 0,
    creator: int = TARGET.UNIX_CREATOR,
) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.create_system = creator
    info.compress_type = compression
    info.external_attr = (mode << 16) | dos_attributes
    return info


def directory_info(name: str) -> zipfile.ZipInfo:
    if not name.endswith("/"):
        raise AssertionError("directory test fixture must end in '/'")
    return regular_info(
        name,
        compression=zipfile.ZIP_STORED,
        mode=0o040755,
        dos_attributes=TARGET.DOS_DIRECTORY,
    )


def make_zip(
    entries: list[tuple[str | zipfile.ZipInfo, bytes]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    comment: bytes = b"",
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=compression,
        allowZip64=False,
    ) as archive:
        archive.comment = comment
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, content in entries:
                archive.writestr(name, content)
    return output.getvalue()


def valid_entries() -> list[tuple[str | zipfile.ZipInfo, bytes]]:
    return [
        (regular_info(ICE_GO), b"package ice\n"),
        (regular_info(GO_MOD), b"module github.com/pion/ice/v4\n"),
    ]


def manual_zip(
    specs: list[dict[str, object]],
    *,
    descriptor_style: str | None = None,
    archive_comment: bytes = b"",
) -> bytes:
    """Build a small deterministic ZIP without any filesystem interaction."""

    local_region = bytearray()
    central_records: list[bytes] = []
    for spec in specs:
        name = str(spec["name"])
        content = bytes(spec.get("content", b""))
        raw_name = bytes(
            spec.get(
                "rawName",
                name.encode("utf-8"),
            )
        )
        method = int(spec.get("method", TARGET.DEFLATED_METHOD))
        flags = int(
            spec.get(
                "flags",
                TARGET.UTF8_FLAG if any(byte >= 0x80 for byte in raw_name) else 0,
            )
        )
        if descriptor_style is not None:
            flags |= TARGET.DATA_DESCRIPTOR_FLAG
        local_extra = bytes(spec.get("localExtra", b""))
        central_extra = bytes(spec.get("centralExtra", b""))
        central_comment = bytes(spec.get("centralComment", b""))
        version_needed = int(spec.get("versionNeeded", 20))
        creator = int(spec.get("creator", TARGET.UNIX_CREATOR))
        unix_mode = int(spec.get("mode", 0o100644))
        dos_attributes = int(spec.get("dosAttributes", 0))
        modified_time = int(spec.get("modifiedTime", 0))
        modified_date = int(spec.get("modifiedDate", 0x21))

        if method == TARGET.STORED_METHOD:
            compressed = content
        elif method == TARGET.DEFLATED_METHOD:
            compressed = raw_deflate(content)
        else:
            compressed = bytes(spec.get("compressed", content))
        compressed += bytes(spec.get("compressedSuffix", b""))
        crc32_value = zlib.crc32(content) & 0xFFFFFFFF
        declared_crc = int(spec.get("declaredCrc", crc32_value))
        declared_compressed = int(spec.get("declaredCompressedSize", len(compressed)))
        declared_uncompressed = int(spec.get("declaredSize", len(content)))
        local_header_offset = len(local_region)

        if descriptor_style is None:
            local_crc = declared_crc
            local_compressed = declared_compressed
            local_uncompressed = declared_uncompressed
        else:
            local_crc = int(spec.get("localCrc", 0))
            local_compressed = int(spec.get("localCompressedSize", 0))
            local_uncompressed = int(spec.get("localSize", 0))
        local_region.extend(
            TARGET.LOCAL_HEADER.pack(
                TARGET.LOCAL_SIGNATURE,
                version_needed,
                flags,
                method,
                modified_time,
                modified_date,
                local_crc,
                local_compressed,
                local_uncompressed,
                len(raw_name),
                len(local_extra),
            )
        )
        local_region.extend(raw_name)
        local_region.extend(local_extra)
        local_region.extend(compressed)
        if descriptor_style == "signed":
            local_region.extend(
                TARGET.SIGNED_DATA_DESCRIPTOR.pack(
                    TARGET.DATA_DESCRIPTOR_SIGNATURE,
                    declared_crc,
                    declared_compressed,
                    declared_uncompressed,
                )
            )
        elif descriptor_style == "unsigned":
            local_region.extend(
                TARGET.DATA_DESCRIPTOR.pack(
                    declared_crc,
                    declared_compressed,
                    declared_uncompressed,
                )
            )
        elif descriptor_style is not None:
            raise AssertionError("unknown descriptor style")

        version_made_by = (creator << 8) | 20
        external_attributes = (unix_mode << 16) | dos_attributes
        central_records.append(
            TARGET.CENTRAL_HEADER.pack(
                TARGET.CENTRAL_SIGNATURE,
                version_made_by,
                version_needed,
                flags,
                method,
                modified_time,
                modified_date,
                declared_crc,
                declared_compressed,
                declared_uncompressed,
                len(raw_name),
                len(central_extra),
                len(central_comment),
                int(spec.get("startingDisk", 0)),
                0,
                external_attributes,
                int(spec.get("localHeaderOffset", local_header_offset)),
            )
            + raw_name
            + central_extra
            + central_comment
        )

    central_offset = len(local_region)
    central = b"".join(central_records)
    eocd = TARGET.EOCD.pack(
        TARGET.EOCD_SIGNATURE,
        0,
        0,
        len(specs),
        len(specs),
        len(central),
        central_offset,
        len(archive_comment),
    )
    return bytes(local_region) + central + eocd + archive_comment


def eocd_offset(raw: bytes) -> int:
    return len(raw) - TARGET.EOCD.size


def central_offsets(raw: bytes) -> list[int]:
    fields = TARGET.EOCD.unpack_from(raw, eocd_offset(raw))
    count = fields[4]
    cursor = fields[6]
    offsets: list[int] = []
    for _ in range(count):
        if raw[cursor : cursor + 4] != TARGET.CENTRAL_SIGNATURE:
            raise AssertionError("invalid central directory test fixture")
        offsets.append(cursor)
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", raw, cursor + 28
        )
        cursor += (
            TARGET.CENTRAL_HEADER.size
            + name_length
            + extra_length
            + comment_length
        )
    return offsets


def central_offset_for_name(raw: bytes, name: str) -> int:
    for offset in central_offsets(raw):
        flags = struct.unpack_from("<H", raw, offset + 8)[0]
        name_length = struct.unpack_from("<H", raw, offset + 28)[0]
        raw_name = raw[
            offset + TARGET.CENTRAL_HEADER.size :
            offset + TARGET.CENTRAL_HEADER.size + name_length
        ]
        encoding = "utf-8" if flags & TARGET.UTF8_FLAG else "ascii"
        if raw_name.decode(encoding) == name:
            return offset
    raise AssertionError(f"missing central test entry: {name}")


def local_offset_for_name(raw: bytes, name: str) -> int:
    central_offset = central_offset_for_name(raw, name)
    return struct.unpack_from("<I", raw, central_offset + 42)[0]


class OfflinePionZipTests(unittest.TestCase):
    def inspect(
        self,
        raw: bytes,
        *,
        limits: dict[str, int] | None = None,
    ) -> dict[str, object]:
        return TARGET.inspect_module_zip(
            raw,
            module_prefix=MODULE_PREFIX,
            limits=limits,
        )

    def assert_rejected(
        self,
        raw: bytes,
        *,
        limits: dict[str, int] | None = None,
    ) -> None:
        with self.assertRaises(TARGET.OfflineZipValidationError):
            self.inspect(raw, limits=limits)

    def test_01_valid_archive_returns_deterministic_in_memory_entries(self) -> None:
        raw = make_zip(valid_entries())
        first = self.inspect(raw)
        second = self.inspect(raw)
        self.assertEqual(first, second)
        self.assertEqual(first["entryCount"], 2)
        self.assertEqual(first["fileCount"], 2)
        self.assertEqual(first["directoryCount"], 0)
        self.assertEqual(first["totalUncompressedBytes"], 42)
        self.assertEqual(first["archiveBytes"], len(raw))
        self.assertEqual(first["rawSha256"], hashlib.sha256(raw).hexdigest())
        self.assertFalse(first["archiveExtracted"])

        entries = first["entries"]
        self.assertIsInstance(entries, tuple)
        self.assertEqual(
            [entry["relativePath"] for entry in entries],
            ["go.mod", "ice.go"],
        )
        self.assertEqual(entries[0]["bytes"], b"module github.com/pion/ice/v4\n")
        self.assertEqual(entries[1]["bytes"], b"package ice\n")
        self.assertEqual(
            entries[1]["sha256"],
            hashlib.sha256(b"package ice\n").hexdigest(),
        )
        self.assertRegex(str(first["treeSha256"]), r"^[0-9a-f]{64}$")

    def test_02_directories_descriptors_and_accounted_extra_fields_pass(self) -> None:
        timestamp_extra = struct.pack("<HHBI", 0x5455, 5, 1, 1)
        specs = [
            {
                "name": GO_MOD,
                "content": b"module github.com/pion/ice/v4\n",
                "localExtra": timestamp_extra,
                "centralExtra": timestamp_extra,
            },
            {
                "name": MODULE_PREFIX + "sub/",
                "content": b"",
                "method": TARGET.STORED_METHOD,
                "mode": 0o040755,
                "dosAttributes": TARGET.DOS_DIRECTORY,
                "localExtra": timestamp_extra,
                "centralExtra": timestamp_extra,
            },
            {
                "name": MODULE_PREFIX + "sub/file.go",
                "content": b"package sub\n",
            },
        ]
        for descriptor_style in ("signed", "unsigned"):
            with self.subTest(descriptor_style=descriptor_style):
                result = self.inspect(
                    manual_zip(specs, descriptor_style=descriptor_style)
                )
                self.assertEqual(result["entryCount"], 3)
                self.assertEqual(result["directoryCount"], 1)
                directory = next(
                    entry for entry in result["entries"] if entry["isDirectory"]
                )
                self.assertEqual(directory["bytes"], b"")
                self.assertEqual(
                    directory["localExtraFields"][0]["id"],
                    0x5455,
                )

    def test_03_limits_are_tightening_only_and_input_must_be_bytes(self) -> None:
        raw = make_zip(valid_entries())
        self.assert_rejected(raw, limits={"archiveBytes": len(raw) - 1})
        self.assert_rejected(raw, limits={"entryCount": 1})
        self.assert_rejected(raw, limits={"singleFileBytes": 20})
        self.assert_rejected(raw, limits={"totalUncompressedBytes": 41})
        central_size = TARGET.EOCD.unpack_from(raw, eocd_offset(raw))[5]
        self.assert_rejected(
            raw,
            limits={"centralDirectoryBytes": central_size - 1},
        )
        with self.assertRaises(TARGET.OfflineZipValidationError):
            TARGET.inspect_module_zip(
                bytearray(raw),  # type: ignore[arg-type]
                module_prefix=MODULE_PREFIX,
            )
        for invalid_limits in (
            {"unknown": 1},
            {"entryCount": True},
            {"entryCount": 0},
            {"entryCount": TARGET.DEFAULT_LIMITS["entryCount"] + 1},
        ):
            with self.subTest(limits=invalid_limits):
                with self.assertRaises(TARGET.OfflineZipValidationError):
                    self.inspect(raw, limits=invalid_limits)

    def test_04_module_prefix_is_closed_and_root_go_mod_is_required(self) -> None:
        raw = make_zip(valid_entries())
        for prefix in (
            "",
            "github.com/pion/ice/v4@v4.3.0",
            "/github.com/pion/ice/v4@v4.3.0/",
            "github.com/pion/../ice/",
        ):
            with self.subTest(prefix=prefix):
                with self.assertRaises(TARGET.OfflineZipValidationError):
                    TARGET.inspect_module_zip(raw, module_prefix=prefix)
        self.assert_rejected(
            make_zip([(regular_info(ICE_GO), b"package ice\n")])
        )
        self.assert_rejected(
            make_zip(
                [
                    (regular_info(GO_MOD + "/child"), b"bad"),
                    (regular_info(ICE_GO), b"package ice\n"),
                ]
            )
        )

    def test_05_unsafe_noncanonical_and_overbounded_paths_fail(self) -> None:
        bad_names = (
            MODULE_PREFIX + "../evil.go",
            "/" + GO_MOD,
            MODULE_PREFIX + "dir\\evil.go",
            MODULE_PREFIX + "stream:ads",
            MODULE_PREFIX + "control\x01.go",
            MODULE_PREFIX + "./dot.go",
            MODULE_PREFIX + "double//slash.go",
            "example.invalid/other@v1.0.0/file.go",
            MODULE_PREFIX + "x" * 256,
            MODULE_PREFIX + "/".join(["d"] * 29) + "/file.go",
        )
        for bad_name in bad_names:
            with self.subTest(name=bad_name):
                self.assert_rejected(
                    make_zip(
                        [
                            (regular_info(GO_MOD), b"module good\n"),
                            (regular_info(bad_name), b"bad\n"),
                        ]
                    )
                )

    def test_06_nfc_and_filename_encodings_are_strict(self) -> None:
        decomposed = MODULE_PREFIX + "cafe\u0301.go"
        self.assert_rejected(
            make_zip(
                [
                    (regular_info(GO_MOD), b"module good\n"),
                    (regular_info(decomposed), b"bad\n"),
                ]
            )
        )
        bad_raw_name = MODULE_PREFIX.encode("ascii") + b"bad-\x82.go"
        self.assert_rejected(
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {
                        "name": MODULE_PREFIX + "placeholder",
                        "rawName": bad_raw_name,
                        "content": b"bad\n",
                        "flags": 0,
                    },
                ]
            )
        )
        invalid_utf8 = MODULE_PREFIX.encode("ascii") + b"bad-\xff.go"
        self.assert_rejected(
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {
                        "name": MODULE_PREFIX + "placeholder",
                        "rawName": invalid_utf8,
                        "content": b"bad\n",
                        "flags": TARGET.UTF8_FLAG,
                    },
                ]
            )
        )

    def test_07_duplicate_casefold_and_directory_spelling_collisions_fail(self) -> None:
        collision_sets = (
            [
                (regular_info(GO_MOD), b"module good\n"),
                (regular_info(ICE_GO), b"one"),
                (regular_info(ICE_GO), b"two"),
            ],
            [
                (regular_info(GO_MOD), b"module good\n"),
                (regular_info(MODULE_PREFIX + "Name.go"), b"one"),
                (regular_info(MODULE_PREFIX + "name.go"), b"two"),
            ],
            [
                (regular_info(GO_MOD), b"module good\n"),
                (regular_info(MODULE_PREFIX + "Straße.go"), b"one"),
                (regular_info(MODULE_PREFIX + "STRASSE.go"), b"two"),
            ],
            [
                (regular_info(GO_MOD), b"module good\n"),
                (regular_info(MODULE_PREFIX + "Foo/a.go"), b"one"),
                (regular_info(MODULE_PREFIX + "foo/b.go"), b"two"),
            ],
        )
        for entries in collision_sets:
            with self.subTest(names=[str(item[0]) for item in entries]):
                self.assert_rejected(make_zip(entries))

    def test_08_file_directory_and_file_prefix_collisions_fail(self) -> None:
        cases = (
            [
                (regular_info(GO_MOD), b"module good\n"),
                (directory_info(MODULE_PREFIX + "conflict/"), b""),
                (regular_info(MODULE_PREFIX + "conflict"), b"file"),
            ],
            [
                (regular_info(GO_MOD), b"module good\n"),
                (regular_info(MODULE_PREFIX + "parent"), b"file"),
                (regular_info(MODULE_PREFIX + "parent/child.go"), b"child"),
            ],
            [
                (regular_info(GO_MOD), b"module good\n"),
                (directory_info(MODULE_PREFIX + "Case/"), b""),
                (regular_info(MODULE_PREFIX + "case/child.go"), b"child"),
            ],
        )
        for entries in cases:
            with self.subTest(names=[str(item[0]) for item in entries]):
                self.assert_rejected(make_zip(entries))

    def test_09_nonregular_executable_and_hidden_metadata_fail(self) -> None:
        bad_specs = (
            {"name": ICE_GO, "content": b"x", "mode": 0o120777},
            {"name": ICE_GO, "content": b"x", "mode": 0o010644},
            {"name": ICE_GO, "content": b"x", "mode": 0o100755},
            {"name": ICE_GO, "content": b"x", "mode": 0o104644},
            {
                "name": ICE_GO,
                "content": b"x",
                "mode": 0o100644,
                "dosAttributes": TARGET.DOS_HIDDEN,
            },
            {"name": ICE_GO, "content": b"x", "creator": 0},
        )
        for bad_spec in bad_specs:
            with self.subTest(spec=bad_spec):
                self.assert_rejected(
                    manual_zip(
                        [
                            {"name": GO_MOD, "content": b"module good\n"},
                            bad_spec,
                        ]
                    )
                )

    def test_10_encryption_unknown_flags_methods_and_zip64_versions_fail(self) -> None:
        bad_specs = (
            {
                "name": ICE_GO,
                "content": b"x",
                "flags": TARGET.ENCRYPTED_FLAG,
            },
            {"name": ICE_GO, "content": b"x", "flags": 0x0020},
            {"name": ICE_GO, "content": b"x", "method": 12},
            {"name": ICE_GO, "content": b"x", "versionNeeded": 45},
        )
        for bad_spec in bad_specs:
            with self.subTest(spec=bad_spec):
                self.assert_rejected(
                    manual_zip(
                        [
                            {"name": GO_MOD, "content": b"module good\n"},
                            bad_spec,
                        ]
                    )
                )

    def test_11_eocd_comments_trailing_prefix_multidisk_and_zip64_fail(self) -> None:
        raw = manual_zip(
            [
                {"name": GO_MOD, "content": b"module good\n"},
                {"name": ICE_GO, "content": b"package ice\n"},
            ]
        )
        candidates = [
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {"name": ICE_GO, "content": b"package ice\n"},
                ],
                archive_comment=b"comment",
            ),
            raw + b"trailing",
            b"prefix" + raw,
        ]
        multidisk = bytearray(raw)
        struct.pack_into("<H", multidisk, eocd_offset(raw) + 4, 1)
        candidates.append(bytes(multidisk))
        unequal_disk_counts = bytearray(raw)
        count = struct.unpack_from("<H", unequal_disk_counts, eocd_offset(raw) + 10)[0]
        struct.pack_into("<H", unequal_disk_counts, eocd_offset(raw) + 8, count - 1)
        candidates.append(bytes(unequal_disk_counts))
        zip64 = bytearray(raw)
        struct.pack_into("<H", zip64, eocd_offset(raw) + 10, 0xFFFF)
        candidates.append(bytes(zip64))
        central_drift = bytearray(raw)
        central_size = struct.unpack_from("<I", central_drift, eocd_offset(raw) + 12)[0]
        struct.pack_into("<I", central_drift, eocd_offset(raw) + 12, central_size - 1)
        candidates.append(bytes(central_drift))
        for index, candidate in enumerate(candidates):
            with self.subTest(index=index):
                self.assert_rejected(candidate)

    def test_12_central_comments_hidden_data_and_forbidden_extras_fail(self) -> None:
        forbidden_extras = (
            struct.pack("<HHQ", TARGET.ZIP64_EXTRA_FIELD_ID, 8, 1),
            struct.pack("<HHB", TARGET.UNICODE_PATH_EXTRA_FIELD_ID, 1, 1),
            struct.pack("<HH", 0x5455, 0) + struct.pack("<HH", 0x5455, 0),
            struct.pack("<HH", 0x5455, 3) + b"x",
        )
        for extra in forbidden_extras:
            with self.subTest(extra=extra):
                self.assert_rejected(
                    manual_zip(
                        [
                            {"name": GO_MOD, "content": b"module good\n"},
                            {
                                "name": ICE_GO,
                                "content": b"package ice\n",
                                "centralExtra": extra,
                            },
                        ]
                    )
                )
        self.assert_rejected(
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {
                        "name": ICE_GO,
                        "content": b"package ice\n",
                        "centralComment": b"forbidden",
                    },
                ]
            )
        )

        raw = manual_zip(
            [
                {"name": GO_MOD, "content": b"module good\n"},
                {"name": ICE_GO, "content": b"package ice\n"},
            ]
        )
        old_eocd = eocd_offset(raw)
        mutated = bytearray(raw[:old_eocd] + b"X" + raw[old_eocd:])
        new_eocd = old_eocd + 1
        central_size = struct.unpack_from("<I", mutated, new_eocd + 12)[0]
        struct.pack_into("<I", mutated, new_eocd + 12, central_size + 1)
        self.assert_rejected(bytes(mutated))

    def test_13_local_and_central_header_drift_fails_closed(self) -> None:
        raw = manual_zip(
            [
                {"name": GO_MOD, "content": b"module good\n"},
                {"name": ICE_GO, "content": b"package ice\n"},
            ]
        )
        ice_local = local_offset_for_name(raw, ICE_GO)
        mutations: list[bytes] = []
        for field_offset, field_format, value in (
            (ice_local + 4, "<H", 19),
            (ice_local + 6, "<H", TARGET.UTF8_FLAG),
            (ice_local + 8, "<H", TARGET.STORED_METHOD),
            (ice_local + 10, "<H", 1),
            (ice_local + 14, "<I", 1),
            (ice_local + 18, "<I", 1),
            (ice_local + 22, "<I", 1),
        ):
            mutated = bytearray(raw)
            struct.pack_into(field_format, mutated, field_offset, value)
            mutations.append(bytes(mutated))

        name_mutation = bytearray(raw)
        name_start = ice_local + TARGET.LOCAL_HEADER.size
        name_mutation[name_start + len(ICE_GO) - 1] ^= 1
        mutations.append(bytes(name_mutation))
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.assert_rejected(mutation)

        local_zip64_extra = struct.pack(
            "<HHQ", TARGET.ZIP64_EXTRA_FIELD_ID, 8, 1
        )
        self.assert_rejected(
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {
                        "name": ICE_GO,
                        "content": b"package ice\n",
                        "localExtra": local_zip64_extra,
                    },
                ]
            )
        )

    def test_14_local_layout_gaps_overlaps_and_duplicate_offsets_fail(self) -> None:
        raw = manual_zip(
            [
                {"name": GO_MOD, "content": b"module good\n"},
                {"name": ICE_GO, "content": b"package ice\n"},
            ]
        )
        offsets = central_offsets(raw)
        duplicate = bytearray(raw)
        first_local = struct.unpack_from("<I", duplicate, offsets[0] + 42)[0]
        struct.pack_into("<I", duplicate, offsets[1] + 42, first_local)
        self.assert_rejected(bytes(duplicate))

        ice_local = local_offset_for_name(raw, ICE_GO)
        ice_central = central_offset_for_name(raw, ICE_GO)
        overlap = bytearray(raw)
        compressed_size = struct.unpack_from("<I", overlap, ice_central + 20)[0]
        struct.pack_into("<I", overlap, ice_central + 20, compressed_size + 1)
        struct.pack_into("<I", overlap, ice_local + 18, compressed_size + 1)
        self.assert_rejected(bytes(overlap))

        old_eocd = eocd_offset(raw)
        central_offset = struct.unpack_from("<I", raw, old_eocd + 16)[0]
        gap = bytearray(raw[:central_offset] + b"X" + raw[central_offset:])
        new_eocd = old_eocd + 1
        struct.pack_into("<I", gap, new_eocd + 16, central_offset + 1)
        self.assert_rejected(bytes(gap))

    def test_15_crc_size_ratio_and_hidden_deflate_data_fail(self) -> None:
        bad_specs = (
            {
                "name": ICE_GO,
                "content": b"package ice\n",
                "declaredCrc": 1,
            },
            {
                "name": ICE_GO,
                "content": b"package ice\n",
                "declaredSize": 1,
            },
            {
                "name": ICE_GO,
                "content": b"package ice\n",
                "compressedSuffix": b"hidden",
            },
            {
                "name": ICE_GO,
                "content": b"package ice\n",
                "method": TARGET.STORED_METHOD,
                "declaredSize": 1,
            },
            {
                "name": MODULE_PREFIX + "zeros.bin",
                "content": b"\x00" * 100_000,
            },
        )
        for bad_spec in bad_specs:
            with self.subTest(spec=bad_spec):
                self.assert_rejected(
                    manual_zip(
                        [
                            {"name": GO_MOD, "content": b"module good\n"},
                            bad_spec,
                        ]
                    )
                )

        stored = bytearray(
            manual_zip(
                [
                    {
                        "name": GO_MOD,
                        "content": b"module good\n",
                        "method": TARGET.STORED_METHOD,
                    },
                    {
                        "name": ICE_GO,
                        "content": b"package ice\n",
                        "method": TARGET.STORED_METHOD,
                    },
                ]
            )
        )
        ice_local = local_offset_for_name(bytes(stored), ICE_GO)
        name_length, extra_length = struct.unpack_from("<HH", stored, ice_local + 26)
        data_start = ice_local + TARGET.LOCAL_HEADER.size + name_length + extra_length
        stored[data_start] ^= 1
        self.assert_rejected(bytes(stored))

    def test_16_descriptor_values_and_boundaries_are_exact(self) -> None:
        specs = [
            {"name": GO_MOD, "content": b"module good\n"},
            {"name": ICE_GO, "content": b"package ice\n"},
        ]
        raw = bytearray(manual_zip(specs, descriptor_style="signed"))
        ice_local = local_offset_for_name(bytes(raw), ICE_GO)
        name_length, extra_length = struct.unpack_from("<HH", raw, ice_local + 26)
        ice_central = central_offset_for_name(bytes(raw), ICE_GO)
        compressed_size = struct.unpack_from("<I", raw, ice_central + 20)[0]
        descriptor_offset = (
            ice_local + TARGET.LOCAL_HEADER.size + name_length + extra_length + compressed_size
        )
        struct.pack_into("<I", raw, descriptor_offset + 4, 1)
        self.assert_rejected(bytes(raw))

        unsigned = manual_zip(specs, descriptor_style="unsigned")
        old_eocd = eocd_offset(unsigned)
        central_offset = struct.unpack_from("<I", unsigned, old_eocd + 16)[0]
        gap = bytearray(unsigned[:central_offset] + b"X" + unsigned[central_offset:])
        new_eocd = old_eocd + 1
        struct.pack_into("<I", gap, new_eocd + 16, central_offset + 1)
        self.assert_rejected(bytes(gap))

    def test_17_directory_payload_and_type_metadata_are_exact(self) -> None:
        self.assert_rejected(
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {
                        "name": MODULE_PREFIX + "bad/",
                        "content": b"hidden",
                        "method": TARGET.STORED_METHOD,
                        "mode": 0o040755,
                        "dosAttributes": TARGET.DOS_DIRECTORY,
                    },
                ]
            )
        )
        self.assert_rejected(
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {
                        "name": MODULE_PREFIX + "bad/",
                        "content": b"",
                        "method": TARGET.STORED_METHOD,
                        "mode": 0o100644,
                        "dosAttributes": TARGET.DOS_DIRECTORY,
                    },
                ]
            )
        )
        self.assert_rejected(
            manual_zip(
                [
                    {"name": GO_MOD, "content": b"module good\n"},
                    {
                        "name": ICE_GO,
                        "content": b"package ice\n",
                        "mode": 0o100644,
                        "dosAttributes": TARGET.DOS_DIRECTORY,
                    },
                ]
            )
        )

    def test_18_archive_and_entries_are_immutable_bytes_only_inputs(self) -> None:
        raw = make_zip(valid_entries())
        result = self.inspect(raw)
        for entry in result["entries"]:
            self.assertIs(type(entry["bytes"]), bytes)
            self.assertNotIn("text", entry)
            self.assertNotIn("source", entry)
        with self.assertRaises(TARGET.OfflineZipValidationError):
            TARGET.inspect_module_zip(
                memoryview(raw),  # type: ignore[arg-type]
                module_prefix=MODULE_PREFIX,
            )

    def test_19_every_single_bit_fixture_mutation_fails_cleanly_or_revalidates(self) -> None:
        raw = make_zip(valid_entries())
        rejected = 0
        for index in range(len(raw)):
            mutated = bytearray(raw)
            mutated[index] ^= 1
            try:
                self.inspect(bytes(mutated))
            except TARGET.OfflineZipValidationError:
                rejected += 1
        self.assertGreater(rejected, len(raw) * 9 // 10)


if __name__ == "__main__":
    unittest.main()
