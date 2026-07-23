#!/usr/bin/env python3
"""Offline tests for the exact one-use G2 Pion source acquisition runner."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import time
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "script/acquire_p2p_nat_g2_pion_source_once.py"
SPEC = importlib.util.spec_from_file_location("g2_pion_source_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load G2 Pion source acquisition runner")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def make_zip(
    entries: list[tuple[str | zipfile.ZipInfo, bytes]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    comment: bytes = b"",
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.comment = comment
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, content in entries:
                archive.writestr(name, content)
    return output.getvalue()


def valid_entries() -> list[tuple[str, bytes]]:
    return [
        (RUNNER.MODULE_PREFIX + "go.mod", b"module github.com/pion/ice/v4\n"),
        (RUNNER.MODULE_PREFIX + "ice.go", b"package ice\n"),
    ]


def lower_declared_uncompressed_size(
    raw_archive: bytes,
    entry_name: str,
    declared_content: bytes,
) -> bytes:
    """Keep the full compressed span while shrinking central/local size and CRC."""

    mutated = bytearray(raw_archive)
    with zipfile.ZipFile(io.BytesIO(raw_archive), mode="r") as archive:
        target = archive.getinfo(entry_name)
    declared_crc = RUNNER.zlib.crc32(declared_content) & 0xFFFFFFFF
    struct.pack_into("<I", mutated, target.header_offset + 14, declared_crc)
    struct.pack_into("<I", mutated, target.header_offset + 22, len(declared_content))

    _, central_offset, central_size = RUNNER.parse_eocd(raw_archive)
    cursor = central_offset
    central_end = central_offset + central_size
    while cursor < central_end:
        if mutated[cursor : cursor + 4] != b"PK\x01\x02":
            raise AssertionError("invalid central directory in test fixture")
        flags = struct.unpack_from("<H", mutated, cursor + 8)[0]
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", mutated, cursor + 28
        )
        name_start = cursor + 46
        name_end = name_start + name_length
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        name = bytes(mutated[name_start:name_end]).decode(encoding)
        if name == entry_name:
            struct.pack_into("<I", mutated, cursor + 16, declared_crc)
            struct.pack_into("<I", mutated, cursor + 24, len(declared_content))
            return bytes(mutated)
        cursor = name_end + extra_length + comment_length
    raise AssertionError(f"test entry not found in central directory: {entry_name}")


class G2PionSourceAcquisitionRunnerTests(unittest.TestCase):
    def assert_archive_rejected(self, raw: bytes) -> None:
        with self.assertRaises(RUNNER.AcquisitionError):
            RUNNER.inspect_module_zip(raw)

    def test_01_fixed_authority_has_no_cli_override_surface(self) -> None:
        self.assertEqual(RUNNER.SOURCE_URL, RUNNER.AUTHORITY.SOURCE_URL)
        self.assertEqual(RUNNER.OUTPUT_PATH, RUNNER.AUTHORITY.OUTPUT_PATH)
        self.assertEqual(RUNNER.EXPECTED_RAW_SHA256, RUNNER.AUTHORITY.RAW_ARCHIVE_SHA256)
        self.assertEqual(RUNNER.EXPECTED_MODULE_H1, RUNNER.AUTHORITY.MODULE_H1)
        self.assertEqual(RUNNER.EXPECTED_GO_MOD_H1, RUNNER.AUTHORITY.GO_MOD_H1)

    def test_02_exact_opener_disables_proxy_and_redirects_and_requires_tls(self) -> None:
        opener = RUNNER.build_exact_opener()
        try:
            proxy_handlers = [
                handler
                for handler in opener.handlers
                if handler.__class__.__name__ == "ProxyHandler"
            ]
            # ProxyHandler({}) suppresses the default environment-derived proxy
            # handler and contributes no protocol method of its own.
            self.assertEqual(proxy_handlers, [])
            self.assertEqual(
                sum(isinstance(handler, RUNNER.RejectRedirects) for handler in opener.handlers),
                1,
            )
            https_handlers = [
                handler for handler in opener.handlers if isinstance(handler, RUNNER.HTTPSHandler)
            ]
            self.assertEqual(len(https_handlers), 1)
            context = https_handlers[0]._context
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, RUNNER.ssl.CERT_REQUIRED)
        finally:
            opener.close()

    def test_03_redirect_handler_never_constructs_a_followup_request(self) -> None:
        handler = RUNNER.RejectRedirects()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, "https://evil.invalid")
        )

    def test_04_content_length_requires_one_exact_decimal_value(self) -> None:
        from email.message import Message

        valid = Message()
        valid.add_header("Content-Length", str(RUNNER.EXPECTED_CONTENT_LENGTH))
        self.assertEqual(
            RUNNER.parse_exact_content_length(valid), RUNNER.EXPECTED_CONTENT_LENGTH
        )
        invalid_headers = []
        missing = Message()
        invalid_headers.append(missing)
        duplicate = Message()
        duplicate.add_header("Content-Length", str(RUNNER.EXPECTED_CONTENT_LENGTH))
        duplicate.add_header("Content-Length", str(RUNNER.EXPECTED_CONTENT_LENGTH))
        invalid_headers.append(duplicate)
        signed = Message()
        signed.add_header("Content-Length", "+293023")
        invalid_headers.append(signed)
        drifted = Message()
        drifted.add_header("Content-Length", "293024")
        invalid_headers.append(drifted)
        for headers in invalid_headers:
            with self.subTest(headers=headers.items()):
                with self.assertRaises(RUNNER.AcquisitionError):
                    RUNNER.parse_exact_content_length(headers)
        with self.assertRaises(RUNNER.TotalDeadlineExpired):
            with RUNNER.wall_clock_deadline(0.005):
                time.sleep(0.05)

    def test_05_valid_archive_is_verified_without_extraction(self) -> None:
        evidence = RUNNER.inspect_module_zip(make_zip(valid_entries()))
        self.assertEqual(evidence["entryCount"], 2)
        self.assertEqual(evidence["fileCount"], 2)
        self.assertEqual(evidence["totalUncompressedBytes"], 42)
        self.assertEqual(
            evidence["moduleH1"],
            "h1:YnVOXO1pf9iOLA4lcARCa+PZtVmcD5gcdrJXdznu5z4=",
        )
        self.assertEqual(
            evidence["goModH1"],
            "h1:M3BqvN+F59PAfhYHR7RZUVdsKaiJ1aZWzbXE3hfXmwk=",
        )
        self.assertFalse(evidence["archiveExtracted"])

        directory = zipfile.ZipInfo(RUNNER.MODULE_PREFIX + "sub/")
        directory.create_system = 3
        directory.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
        directory_archive = make_zip(
            [
                (RUNNER.ROOT_GO_MOD_NAME, b"module github.com/pion/ice/v4\n"),
                (directory, b""),
                (RUNNER.MODULE_PREFIX + "sub/file.go", b"package sub\n"),
            ]
        )
        directory_evidence = RUNNER.inspect_module_zip(directory_archive)
        expected_hash_entries = (
            (
                RUNNER.ROOT_GO_MOD_NAME,
                hashlib.sha256(b"module github.com/pion/ice/v4\n").hexdigest(),
            ),
            (RUNNER.MODULE_PREFIX + "sub/", hashlib.sha256(b"").hexdigest()),
            (
                RUNNER.MODULE_PREFIX + "sub/file.go",
                hashlib.sha256(b"package sub\n").hexdigest(),
            ),
        )
        self.assertEqual(
            directory_evidence["moduleH1"], RUNNER.dirhash_h1(expected_hash_entries)
        )
        self.assertEqual(directory_evidence["entryCount"], 3)
        self.assertEqual(directory_evidence["fileCount"], 2)
        self.assertEqual(directory_evidence["moduleHashEntryCount"], 3)

    def test_06_dirhash_uses_sorted_full_zip_names_and_virtual_go_mod_name(self) -> None:
        content = b"module example.invalid/test\n"
        content_digest = hashlib.sha256(content).hexdigest()
        expected = "h1:" + RUNNER.base64.b64encode(
            hashlib.sha256(f"{content_digest}  go.mod\n".encode()).digest()
        ).decode()
        self.assertEqual(RUNNER.dirhash_h1((("go.mod", content_digest),)), expected)
        full_name_hash = RUNNER.dirhash_h1(
            ((RUNNER.MODULE_PREFIX + "go.mod", content_digest),)
        )
        self.assertNotEqual(full_name_hash, expected)

    def test_07_missing_or_duplicate_root_go_mod_fails(self) -> None:
        self.assert_archive_rejected(
            make_zip([(RUNNER.MODULE_PREFIX + "ice.go", b"package ice\n")])
        )
        self.assert_archive_rejected(
            make_zip(
                [
                    (RUNNER.ROOT_GO_MOD_NAME, b"module first\n"),
                    (RUNNER.ROOT_GO_MOD_NAME, b"module second\n"),
                ]
            )
        )
        case_directory = zipfile.ZipInfo(RUNNER.MODULE_PREFIX + "foo/")
        case_directory.create_system = 3
        case_directory.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
        for extra_entries in (
            [
                (RUNNER.MODULE_PREFIX + "Foo", b"file"),
                (case_directory, b""),
            ],
            [
                (RUNNER.MODULE_PREFIX + "Foo", b"file"),
                (RUNNER.MODULE_PREFIX + "foo/child", b"child"),
            ],
        ):
            self.assert_archive_rejected(
                make_zip(
                    [(RUNNER.ROOT_GO_MOD_NAME, b"module good\n"), *extra_entries]
                )
            )

    def test_08_traversal_absolute_backslash_and_prefix_escape_fail(self) -> None:
        bad_names = (
            RUNNER.MODULE_PREFIX + "../evil",
            "/" + RUNNER.ROOT_GO_MOD_NAME,
            RUNNER.MODULE_PREFIX + "dir\\evil",
            RUNNER.MODULE_PREFIX + "stream:ads",
            RUNNER.MODULE_PREFIX + "control\x01name",
            "example.invalid/other@v1.0.0/go.mod",
        )
        for bad_name in bad_names:
            with self.subTest(name=bad_name):
                self.assert_archive_rejected(
                    make_zip(
                        [
                            (RUNNER.ROOT_GO_MOD_NAME, b"module good\n"),
                            (bad_name, b"bad\n"),
                        ]
                    )
                )
        with self.assertRaises(RUNNER.AcquisitionError):
            RUNNER.decode_local_name(b"name-\x82.go", 0, "non-utf8")
        self.assertEqual(
            RUNNER.decode_local_name("name-é.go".encode("utf-8"), 0x0800, "utf8"),
            "name-é.go",
        )

    def test_09_exact_duplicate_and_casefold_collision_fail(self) -> None:
        self.assert_archive_rejected(
            make_zip(
                [
                    (RUNNER.ROOT_GO_MOD_NAME, b"module good\n"),
                    (RUNNER.MODULE_PREFIX + "same.go", b"one"),
                    (RUNNER.MODULE_PREFIX + "same.go", b"two"),
                ]
            )
        )
        directory = zipfile.ZipInfo(RUNNER.MODULE_PREFIX + "conflict/")
        directory.create_system = 3
        directory.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
        self.assert_archive_rejected(
            make_zip(
                [
                    (RUNNER.ROOT_GO_MOD_NAME, b"module good\n"),
                    (directory, b""),
                    (RUNNER.MODULE_PREFIX + "conflict", b"file"),
                ]
            )
        )
        self.assert_archive_rejected(
            make_zip(
                [
                    (RUNNER.ROOT_GO_MOD_NAME, b"module good\n"),
                    (RUNNER.MODULE_PREFIX + "Name.go", b"one"),
                    (RUNNER.MODULE_PREFIX + "name.go", b"two"),
                ]
            )
        )

    def test_10_symlink_and_unsupported_compression_fail(self) -> None:
        symlink = zipfile.ZipInfo(RUNNER.MODULE_PREFIX + "link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.assert_archive_rejected(
            make_zip(
                [(RUNNER.ROOT_GO_MOD_NAME, b"module good\n"), (symlink, b"target")]
            )
        )
        self.assert_archive_rejected(
            make_zip(valid_entries(), compression=zipfile.ZIP_BZIP2)
        )

    def test_11_archive_comments_trailing_data_and_multidisk_fail(self) -> None:
        self.assert_archive_rejected(make_zip(valid_entries(), comment=b"forbidden"))
        self.assert_archive_rejected(make_zip(valid_entries()) + b"trailing")
        raw = bytearray(make_zip(valid_entries()))
        eocd_offset = raw.rfind(RUNNER.ZIP_EOCD_SIGNATURE)
        struct.pack_into("<H", raw, eocd_offset + 4, 1)
        self.assert_archive_rejected(bytes(raw))
        central_volume = bytearray(make_zip(valid_entries()))
        _, central_offset, _ = RUNNER.parse_eocd(central_volume)
        struct.pack_into("<H", central_volume, central_offset + 34, 1)
        self.assert_archive_rejected(bytes(central_volume))

    def test_12_local_central_header_drift_and_zip64_extra_fail(self) -> None:
        raw = bytearray(make_zip(valid_entries()))
        current_method = struct.unpack_from("<H", raw, 8)[0]
        struct.pack_into("<H", raw, 8, 0 if current_method != 0 else 8)
        self.assert_archive_rejected(bytes(raw))

        zip64 = zipfile.ZipInfo(RUNNER.ROOT_GO_MOD_NAME)
        zip64.compress_type = zipfile.ZIP_DEFLATED
        zip64.extra = struct.pack("<HHQ", RUNNER.ZIP64_EXTRA_FIELD_ID, 8, 1)
        self.assert_archive_rejected(make_zip([(zip64, b"module good\n")]))

    def test_13_high_compression_ratio_fails(self) -> None:
        self.assert_archive_rejected(
            make_zip(
                [
                    (RUNNER.ROOT_GO_MOD_NAME, b"module good\n"),
                    (RUNNER.MODULE_PREFIX + "zeros.bin", b"\x00" * 100_000),
                ]
            )
        )
        hidden_name = RUNNER.MODULE_PREFIX + "hidden-tail.bin"
        for compression in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            with self.subTest(compression=compression):
                archive = make_zip(
                    [
                        (RUNNER.ROOT_GO_MOD_NAME, b"module good\n"),
                        (hidden_name, b"A" * 10_000),
                    ],
                    compression=compression,
                )
                self.assert_archive_rejected(
                    lower_declared_uncompressed_size(archive, hidden_name, b"A")
                )

    def test_14_atomic_claim_is_owner_only_and_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with (
                mock.patch.object(RUNNER, "ROOT", Path(temporary_root)),
                mock.patch.object(
                    RUNNER,
                    "OUTPUT_PARENT",
                    RUNNER.PurePosixPath("durable-parent/durable-child"),
                ),
                mock.patch.object(RUNNER.os, "fsync", wraps=os.fsync) as fsync_mock,
            ):
                created_directory_fd = RUNNER.open_secure_output_directory(
                    create_missing=True
                )
                self.assertIsNotNone(created_directory_fd)
                assert created_directory_fd is not None
                os.close(created_directory_fd)
                self.assertGreaterEqual(fsync_mock.call_count, 4)
                for relative in ("durable-parent", "durable-parent/durable-child"):
                    metadata = (Path(temporary_root) / relative).stat()
                    self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o700)
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_fd = os.open(temporary_directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                created_at, claim_hash = RUNNER.create_atomic_claim(directory_fd)
                self.assertTrue(created_at.endswith("Z"))
                self.assertRegex(claim_hash, r"^[0-9a-f]{64}$")
                claim_path = Path(temporary_directory) / RUNNER.CLAIM_NAME
                metadata = claim_path.stat()
                self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
                self.assertEqual(metadata.st_nlink, 1)
                with self.assertRaises(RUNNER.AcquisitionError):
                    RUNNER.create_atomic_claim(directory_fd)
            finally:
                os.close(directory_fd)

    def test_15_temporary_archive_is_exclusive_owner_only_and_single_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_fd = os.open(temporary_directory, os.O_RDONLY | os.O_DIRECTORY)
            file_fd = -1
            temporary_name = None
            try:
                file_fd, temporary_name = RUNNER.create_temporary_archive(directory_fd)
                metadata = os.fstat(file_fd)
                self.assertTrue(stat.S_ISREG(metadata.st_mode))
                self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
                self.assertEqual(metadata.st_nlink, 1)
            finally:
                if file_fd >= 0:
                    os.close(file_fd)
                if temporary_name is not None:
                    RUNNER.unlink_exact(directory_fd, temporary_name)
                os.close(directory_fd)
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_fd = os.open(temporary_directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with mock.patch.object(
                    RUNNER.os, "fchmod", side_effect=OSError("forced fchmod failure")
                ):
                    with self.assertRaises(RUNNER.AcquisitionError):
                        RUNNER.create_temporary_archive(directory_fd)
                self.assertEqual(list(Path(temporary_directory).iterdir()), [])
            finally:
                os.close(directory_fd)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin renameatx_np is required")
    def test_16_exclusive_publish_never_replaces_an_existing_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_fd = os.open(temporary_directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                first_fd = os.open(
                    "first.tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                    dir_fd=directory_fd,
                )
                os.write(first_fd, b"first")
                os.close(first_fd)
                RUNNER.rename_no_replace(directory_fd, "first.tmp", "final.zip")

                second_fd = os.open(
                    "second.tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                    dir_fd=directory_fd,
                )
                os.write(second_fd, b"second")
                os.close(second_fd)
                with self.assertRaises(RUNNER.AcquisitionError):
                    RUNNER.rename_no_replace(directory_fd, "second.tmp", "final.zip")
                self.assertEqual(
                    (Path(temporary_directory) / "final.zip").read_bytes(), b"first"
                )

                publish_fd = os.open(
                    "publish.tmp", os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600,
                    dir_fd=directory_fd,
                )
                os.ftruncate(publish_fd, RUNNER.EXPECTED_CONTENT_LENGTH)
                publication_state = {
                    "archivePublished": False,
                    "directoryFsyncCompleted": False,
                }
                with (
                    mock.patch.object(
                        RUNNER,
                        "download_exact_once",
                        return_value={"bytes": b"synthetic"},
                    ),
                    mock.patch.object(
                        RUNNER,
                        "inspect_module_zip",
                        return_value={
                            "moduleH1": RUNNER.EXPECTED_MODULE_H1,
                            "goModH1": RUNNER.EXPECTED_GO_MOD_H1,
                        },
                    ),
                    mock.patch.object(
                        RUNNER.os,
                        "fsync",
                        side_effect=(None, OSError("forced directory fsync failure")),
                    ),
                ):
                    with self.assertRaises(OSError):
                        RUNNER.verify_and_publish_claimed_acquisition(
                            directory_fd,
                            publish_fd,
                            "publish.tmp",
                            publication_state,
                        )
                self.assertTrue(publication_state["archivePublished"])
                self.assertFalse(publication_state["directoryFsyncCompleted"])
                self.assertTrue(
                    (Path(temporary_directory) / RUNNER.OUTPUT_NAME).is_file()
                )
                publication_state["archivePublished"] = False
                self.assertTrue(
                    RUNNER.directory_entry_matches_open_file(
                        directory_fd,
                        RUNNER.OUTPUT_NAME,
                        publish_fd,
                    )
                )
                self.assertFalse(
                    RUNNER.directory_entry_matches_open_file(
                        directory_fd,
                        "final.zip",
                        publish_fd,
                    )
                )
                uncertain = RUNNER.PublishedArchiveStateError(
                    "synthetic uncertainty",
                    directory_fsync_completed=False,
                    request_count=1,
                )
                self.assertTrue(uncertain.archive_published)
                self.assertFalse(uncertain.directory_fsync_completed)
                self.assertEqual(uncertain.request_count, 1)
                os.close(publish_fd)
            finally:
                os.close(directory_fd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
