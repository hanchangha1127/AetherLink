#!/usr/bin/env python3
"""Offline tests for the G2 Pion dependency wave-one acquisition runner."""

from __future__ import annotations

import ast
import base64
import copy
from email.message import Message
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import types
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = (
    "script/acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
)
RUNNER_PATH = ROOT / RUNNER_RELATIVE_PATH
RUNNER_BYTES = RUNNER_PATH.read_bytes()
RUNNER = types.ModuleType("g2_dependency_wave1_runner_under_test")
RUNNER.__dict__.update(
    {
        "__cached__": None,
        "__file__": str(RUNNER_PATH),
        "__loader__": None,
        "__package__": None,
    }
)
exec(
    compile(
        RUNNER_BYTES,
        RUNNER_RELATIVE_PATH,
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    ),
    RUNNER.__dict__,
    RUNNER.__dict__,
)

DECISION_PATH = (
    ROOT
    / "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
DECISION = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
DEFAULT_LIMITS = DECISION["resourceLimits"]


class FakeResponse:
    def __init__(
        self,
        payload: bytes,
        url: str,
        *,
        status: int = 200,
        content_type: str = "application/zip",
        content_length: str | None = None,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self._stream = io.BytesIO(payload)
        self._url = url
        self.status = status
        self.headers = Message()
        self.socket_timeouts: list[float] = []
        self.read1_count = 0
        self.headers.add_header("Content-Type", content_type)
        if content_length is not None:
            self.headers.add_header("Content-Length", content_length)
        for key, value in extra_headers or []:
            self.headers.add_header(key, value)

    def read(self, size: int = -1) -> bytes:
        raise AssertionError("bounded download must use read1")

    def read1(self, size: int = -1) -> bytes:
        self.read1_count += 1
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:
        self._stream.close()

    def settimeout(self, timeout: float) -> None:
        self.socket_timeouts.append(timeout)


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests: list[object] = []
        self.timeouts: list[float] = []

    def open(self, request, timeout: float):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response


def manual_h1(rows: list[tuple[str, bytes]]) -> str:
    aggregate = hashlib.sha256()
    for name, payload in sorted(rows, key=lambda row: row[0].encode("utf-8")):
        aggregate.update(hashlib.sha256(payload).hexdigest().encode("ascii"))
        aggregate.update(b"  ")
        aggregate.update(name.encode("utf-8"))
        aggregate.update(b"\n")
    return "h1:" + base64.b64encode(aggregate.digest()).decode("ascii")


def zip_bytes(
    module: str,
    version: str,
    files: list[tuple[str, bytes]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    archive_comment: bytes = b"",
    entry_extra: bytes = b"",
) -> bytes:
    prefix = f"{module}@{version}/"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.comment = archive_comment
        for name, payload in files:
            info = zipfile.ZipInfo(prefix + name)
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.extra = entry_extra
            archive.writestr(info, payload)
    return buffer.getvalue()


def item_for(
    module: str,
    version: str,
    raw: bytes,
    files: list[tuple[str, bytes]],
) -> dict:
    prefix = f"{module}@{version}/"
    rows = [(prefix + name, payload) for name, payload in files]
    go_mod = dict(files)["go.mod"]
    return {
        "order": 1,
        "tupleId": "wave1-test",
        "module": module,
        "version": version,
        "url": f"https://proxy.golang.org/{module}/@v/{version}.zip",
        "outputPath": "build/offline-source/test.zip",
        "moduleZipH1": manual_h1(rows),
        "goModH1": manual_h1([("go.mod", go_mod)]),
        "rawSha256": hashlib.sha256(raw).hexdigest(),
    }


def open_temp_payload(payload: bytes) -> tuple[tempfile.TemporaryDirectory, int, Path]:
    directory = tempfile.TemporaryDirectory()
    path = Path(directory.name) / "archive.zip"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, payload)
    os.fsync(fd)
    os.lseek(fd, 0, os.SEEK_SET)
    return directory, fd, path


class DependencyWaveOneRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = "example.com/mod"
        self.version = "v1.2.3"
        self.files = [
            ("go.mod", b"module example.com/mod\n\ngo 1.24.0\n"),
            ("source.go", b"package source\n"),
        ]
        self.raw = zip_bytes(self.module, self.version, self.files)
        self.item = item_for(self.module, self.version, self.raw, self.files)

    def inspect(
        self,
        raw: bytes | None = None,
        item: dict | None = None,
        limits: dict | None = None,
        *,
        aggregate_entries_before: int = 0,
        aggregate_uncompressed_before: int = 0,
    ) -> dict:
        directory, fd, _ = open_temp_payload(raw if raw is not None else self.raw)
        try:
            return RUNNER.inspect_module_zip(
                fd,
                item if item is not None else self.item,
                limits if limits is not None else DEFAULT_LIMITS,
                aggregate_entries_before=aggregate_entries_before,
                aggregate_uncompressed_before=aggregate_uncompressed_before,
            )
        finally:
            os.close(fd)
            directory.cleanup()

    def assert_failure(self, code: str, callback) -> None:
        with self.assertRaises(RUNNER.AcquisitionFailure) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_01_canonical_json_is_ascii_sorted_compact_and_lf_terminated(self) -> None:
        self.assertEqual(
            RUNNER.canonical_json_bytes({"z": "한", "a": 1}),
            b'{"a":1,"z":"\\ud55c"}\n',
        )

    def test_02_strict_json_rejects_duplicate_nonfinite_cr_and_missing_lf(self) -> None:
        for raw in (
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
        ):
            with self.subTest(raw=raw):
                self.assert_failure(
                    {
                        b'{"a":1,"a":2}\n': "E_JSON_DUPLICATE_KEY",
                        b'{"a":NaN}\n': "E_JSON_NONFINITE",
                        b'{"a":1}\r\n': "E_JSON_ENCODING",
                        b'{"a":1}': "E_JSON_ENCODING",
                    }[raw],
                    lambda raw=raw: RUNNER.strict_json(raw, "fixture"),
                )

    def test_03_relative_path_rejects_absolute_parent_backslash_and_nul(self) -> None:
        for path in ("/absolute", "../escape", "a/../b", "a\\b", "a\x00b"):
            with self.subTest(path=path):
                self.assert_failure(
                    "E_PATH",
                    lambda path=path: RUNNER.validate_relative_path(path),
                )

    def test_04_hash1_matches_independent_reference_algorithm(self) -> None:
        rows = [("b", b"two"), ("a", b"one")]
        runner_rows = [
            (name, hashlib.sha256(payload).hexdigest()) for name, payload in rows
        ]
        self.assertEqual(RUNNER.dirhash_h1(runner_rows), manual_h1(rows))

    def test_05_single_go_mod_hash_uses_only_go_mod_name(self) -> None:
        payload = b"module example.com/mod\n"
        self.assertEqual(
            RUNNER.single_go_mod_h1(payload),
            manual_h1([("go.mod", payload)]),
        )

    def test_06_valid_zip_is_read_without_extraction(self) -> None:
        result = self.inspect()
        self.assertEqual(result["moduleZipH1"], self.item["moduleZipH1"])
        self.assertEqual(result["goModH1"], self.item["goModH1"])
        self.assertEqual(result["entryCount"], 2)
        self.assertEqual(
            result["uncompressedByteCount"],
            sum(len(payload) for _, payload in self.files),
        )

    def test_07_wrong_module_h1_is_rejected(self) -> None:
        item = copy.deepcopy(self.item)
        item["moduleZipH1"] = "h1:" + "A" * 44
        self.assert_failure("E_MODULE_H1", lambda: self.inspect(item=item))

    def test_08_wrong_go_mod_h1_is_rejected(self) -> None:
        item = copy.deepcopy(self.item)
        item["goModH1"] = "h1:" + "A" * 44
        self.assert_failure("E_GO_MOD_H1", lambda: self.inspect(item=item))

    def test_09_missing_go_mod_is_rejected(self) -> None:
        files = [("source.go", b"package source\n")]
        raw = zip_bytes(self.module, self.version, files)
        item = copy.deepcopy(self.item)
        item["moduleZipH1"] = manual_h1(
            [(f"{self.module}@{self.version}/source.go", files[0][1])]
        )
        self.assert_failure(
            "E_GO_MOD_MISSING",
            lambda: self.inspect(raw=raw, item=item),
        )

    def test_10_wrong_module_directive_is_rejected(self) -> None:
        files = [
            ("go.mod", b"module example.com/other\n"),
            ("source.go", b"package source\n"),
        ]
        raw = zip_bytes(self.module, self.version, files)
        item = item_for(self.module, self.version, raw, files)
        self.assert_failure(
            "E_GO_MOD_MODULE",
            lambda: self.inspect(raw=raw, item=item),
        )

    def test_11_duplicate_zip_name_is_rejected(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            raw = zip_bytes(
                self.module,
                self.version,
                [self.files[0], self.files[1], self.files[1]],
            )
        self.assert_failure("E_ZIP_DUPLICATE", lambda: self.inspect(raw=raw))

    def test_12_explicit_directory_entry_is_rejected(self) -> None:
        raw = zip_bytes(
            self.module,
            self.version,
            [("go.mod", self.files[0][1]), ("folder/", b"")],
        )
        self.assert_failure("E_ZIP_PATH", lambda: self.inspect(raw=raw))

    def test_13_traversal_absolute_backslash_colon_and_newline_are_rejected(self) -> None:
        for name in ("../escape", "/absolute", "a\\b", "a:b", "a\nb"):
            raw = zip_bytes(
                self.module,
                self.version,
                [("go.mod", self.files[0][1]), (name, b"x")],
            )
            with self.subTest(name=name):
                self.assert_failure("E_ZIP_PATH", lambda raw=raw: self.inspect(raw=raw))

    def test_14_wrong_module_prefix_is_rejected(self) -> None:
        raw = zip_bytes("example.com/other", self.version, self.files)
        self.assert_failure("E_MODULE_PREFIX", lambda: self.inspect(raw=raw))

    def test_15_symlink_entry_is_rejected(self) -> None:
        prefix = f"{self.module}@{self.version}/"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(prefix + "go.mod", self.files[0][1])
            link = zipfile.ZipInfo(prefix + "link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, b"target")
        self.assert_failure(
            "E_ZIP_SPECIAL_FILE",
            lambda: self.inspect(raw=buffer.getvalue()),
        )

        unknown_buffer = io.BytesIO()
        with zipfile.ZipFile(unknown_buffer, "w") as archive:
            for name, payload in self.files:
                entry = zipfile.ZipInfo(prefix + name)
                entry.create_system = 42
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(entry, payload)
        self.assert_failure(
            "E_ZIP_CREATOR_SYSTEM",
            lambda: self.inspect(raw=unknown_buffer.getvalue()),
        )

    def test_16_unsupported_compression_is_rejected(self) -> None:
        raw = zip_bytes(
            self.module,
            self.version,
            self.files,
            compression=zipfile.ZIP_BZIP2,
        )
        self.assert_failure("E_ZIP_COMPRESSION", lambda: self.inspect(raw=raw))

        mismatched_method = bytearray(self.raw)
        with zipfile.ZipFile(io.BytesIO(self.raw), "r") as archive:
            first_offset = archive.infolist()[0].header_offset
        struct.pack_into("<H", mismatched_method, first_offset + 8, zipfile.ZIP_STORED)
        self.assert_failure(
            "E_ZIP_LOCAL_HEADER",
            lambda: self.inspect(raw=bytes(mismatched_method)),
        )

        ordinary_extra = struct.pack("<HH", 0xCAFE, 0)
        extra_zip = bytearray(
            zip_bytes(
                self.module,
                self.version,
                self.files,
                entry_extra=ordinary_extra,
            )
        )
        with zipfile.ZipFile(io.BytesIO(extra_zip), "r") as archive:
            first = archive.infolist()[0]
            first_offset = first.header_offset
        local_extra_offset = first_offset + RUNNER.ZIP_LOCAL_HEADER.size + len(
            first.filename.encode("ascii")
        )
        struct.pack_into("<H", extra_zip, local_extra_offset, 0x0001)
        self.assert_failure(
            "E_ZIP64",
            lambda: self.inspect(raw=bytes(extra_zip)),
        )

    def test_17_archive_comment_is_rejected_by_exact_eof_contract(self) -> None:
        raw = zip_bytes(
            self.module,
            self.version,
            self.files,
            archive_comment=b"comment",
        )
        self.assert_failure("E_ZIP_EOCD", lambda: self.inspect(raw=raw))

    def test_18_entry_comment_is_rejected(self) -> None:
        prefix = f"{self.module}@{self.version}/"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            first = zipfile.ZipInfo(prefix + "go.mod")
            first.comment = b"comment"
            archive.writestr(first, self.files[0][1])
            archive.writestr(prefix + "source.go", self.files[1][1])
        self.assert_failure(
            "E_ZIP_COMMENT",
            lambda: self.inspect(raw=buffer.getvalue()),
        )

    def test_19_non_nfc_name_is_rejected(self) -> None:
        raw = zip_bytes(
            self.module,
            self.version,
            [self.files[0], ("e\u0301.go", b"package source\n")],
        )
        self.assert_failure("E_ZIP_PATH", lambda: self.inspect(raw=raw))

    def test_20_casefold_collision_is_rejected(self) -> None:
        raw = zip_bytes(
            self.module,
            self.version,
            [self.files[0], ("A.go", b"x"), ("a.go", b"y")],
        )
        self.assert_failure("E_ZIP_CASE_COLLISION", lambda: self.inspect(raw=raw))

    def test_21_entry_count_limit_is_enforced(self) -> None:
        limits = copy.deepcopy(DEFAULT_LIMITS)
        limits["maximumEntriesPerArchive"] = 1
        self.assert_failure(
            "E_ZIP_ENTRY_COUNT",
            lambda: self.inspect(limits=limits),
        )

    def test_22_single_file_limit_is_enforced(self) -> None:
        limits = copy.deepcopy(DEFAULT_LIMITS)
        limits["maximumSingleFileBytes"] = 4
        self.assert_failure(
            "E_ZIP_FILE_SIZE",
            lambda: self.inspect(limits=limits),
        )

    def test_23_per_archive_uncompressed_limit_is_enforced(self) -> None:
        limits = copy.deepcopy(DEFAULT_LIMITS)
        limits["maximumUncompressedBytesPerArchive"] = 4
        self.assert_failure(
            "E_ZIP_UNCOMPRESSED",
            lambda: self.inspect(limits=limits),
        )

    def test_24_aggregate_entry_limit_is_enforced(self) -> None:
        limits = copy.deepcopy(DEFAULT_LIMITS)
        limits["maximumAggregateEntries"] = 2
        self.assert_failure(
            "E_AGGREGATE_ENTRY_COUNT",
            lambda: self.inspect(
                limits=limits,
                aggregate_entries_before=1,
            ),
        )

    def test_25_aggregate_uncompressed_limit_is_enforced(self) -> None:
        limits = copy.deepcopy(DEFAULT_LIMITS)
        limits["maximumAggregateUncompressedBytes"] = sum(
            len(payload) for _, payload in self.files
        )
        self.assert_failure(
            "E_AGGREGATE_UNCOMPRESSED",
            lambda: self.inspect(
                limits=limits,
                aggregate_uncompressed_before=1,
            ),
        )

    def test_26_response_header_contract_accepts_exact_zip_response(self) -> None:
        response = FakeResponse(
            self.raw,
            self.item["url"],
            content_length=str(len(self.raw)),
        )
        self.assertEqual(
            RUNNER.validate_response_headers(
                response,
                self.item["url"],
                len(self.raw),
            ),
            len(self.raw),
        )

    def test_27_response_url_change_is_rejected_as_redirect(self) -> None:
        response = FakeResponse(self.raw, self.item["url"] + "?changed")
        self.assert_failure(
            "E_REDIRECT",
            lambda: RUNNER.validate_response_headers(
                response,
                self.item["url"],
                len(self.raw) + 1,
            ),
        )

    def test_28_content_type_and_encoding_are_fail_closed(self) -> None:
        cases = [
            FakeResponse(self.raw, self.item["url"], content_type="text/plain"),
            FakeResponse(
                self.raw,
                self.item["url"],
                extra_headers=[("Content-Encoding", "gzip")],
            ),
        ]
        for response in cases:
            with self.subTest(headers=str(response.headers)):
                self.assert_failure(
                    "E_CONTENT_TYPE"
                    if response.headers["Content-Type"] == "text/plain"
                    else "E_CONTENT_ENCODING",
                    lambda response=response: RUNNER.validate_response_headers(
                        response,
                        self.item["url"],
                        len(self.raw) + 1,
                    ),
                )

    def test_29_auth_cookie_and_redirect_headers_are_rejected(self) -> None:
        for name in (
            "Location",
            "WWW-Authenticate",
            "Proxy-Authenticate",
            "Set-Cookie",
        ):
            response = FakeResponse(
                self.raw,
                self.item["url"],
                extra_headers=[(name, "redacted")],
            )
            with self.subTest(name=name):
                self.assert_failure(
                    "E_FORBIDDEN_RESPONSE_HEADER",
                    lambda response=response: RUNNER.validate_response_headers(
                        response,
                        self.item["url"],
                        len(self.raw) + 1,
                    ),
                )

    def test_30_duplicate_content_length_is_rejected(self) -> None:
        response = FakeResponse(
            self.raw,
            self.item["url"],
            content_length=str(len(self.raw)),
            extra_headers=[("Content-Length", str(len(self.raw)))],
        )
        self.assert_failure(
            "E_CONTENT_LENGTH",
            lambda: RUNNER.validate_response_headers(
                response,
                self.item["url"],
                len(self.raw) + 1,
            ),
        )

    def test_31_download_streams_exact_bytes_without_proxy_or_retry_surface(self) -> None:
        response = FakeResponse(
            self.raw,
            self.item["url"],
            content_length=str(len(self.raw)),
        )
        opener = FakeOpener(response)
        directory = tempfile.TemporaryDirectory()
        fd = os.open(
            Path(directory.name) / "out.zip",
            RUNNER.create_download_file_flags(),
            0o600,
        )
        try:
            self.assertEqual(
                RUNNER.create_download_file_flags() & os.O_ACCMODE,
                os.O_RDWR,
            )
            result = RUNNER.download_exact_once(
                opener,
                self.item,
                fd,
                maximum_bytes=len(self.raw),
                aggregate_before=0,
                maximum_aggregate_bytes=len(self.raw),
                per_request_timeout_seconds=30.0,
                wave_deadline=RUNNER.time.monotonic() + 60,
            )
            self.assertEqual(result["rawByteSize"], len(self.raw))
            self.assertEqual(result["rawSha256"], hashlib.sha256(self.raw).hexdigest())
            self.assertEqual(len(opener.requests), 1)
            request = opener.requests[0]
            self.assertEqual(request.full_url, self.item["url"])
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.get_header("Authorization"))
            self.assertIsNone(request.get_header("Cookie"))
            self.assertGreaterEqual(len(response.socket_timeouts), 1)
            self.assertGreaterEqual(response.read1_count, 1)
            self.assertTrue(
                all(
                    0 < timeout <= 30.0
                    for timeout in response.socket_timeouts
                )
            )
            inspected = RUNNER.inspect_module_zip(
                fd,
                self.item,
                DEFAULT_LIMITS,
                aggregate_entries_before=0,
                aggregate_uncompressed_before=0,
            )
            self.assertEqual(inspected["entryCount"], 2)
        finally:
            os.close(fd)
            directory.cleanup()

    def test_32_content_length_mismatch_is_rejected(self) -> None:
        response = FakeResponse(
            self.raw,
            self.item["url"],
            content_length=str(len(self.raw) + 1),
        )
        opener = FakeOpener(response)
        directory = tempfile.TemporaryDirectory()
        fd = os.open(Path(directory.name) / "out.zip", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            self.assert_failure(
                "E_CONTENT_LENGTH_MISMATCH",
                lambda: RUNNER.download_exact_once(
                    opener,
                    self.item,
                    fd,
                    maximum_bytes=len(self.raw) + 1,
                    aggregate_before=0,
                    maximum_aggregate_bytes=len(self.raw) + 1,
                    per_request_timeout_seconds=30.0,
                    wave_deadline=RUNNER.time.monotonic() + 60,
                ),
            )
        finally:
            os.close(fd)
            directory.cleanup()

        deadline_response = FakeResponse(self.raw, self.item["url"])
        deadline_opener = FakeOpener(deadline_response)
        deadline_directory = tempfile.TemporaryDirectory()
        deadline_fd = os.open(
            Path(deadline_directory.name) / "deadline.zip",
            os.O_RDWR | os.O_CREAT,
            0o600,
        )
        try:
            self.assert_failure(
                "E_REQUEST_DEADLINE",
                lambda: RUNNER.download_exact_once(
                    deadline_opener,
                    self.item,
                    deadline_fd,
                    maximum_bytes=len(self.raw),
                    aggregate_before=0,
                    maximum_aggregate_bytes=len(self.raw),
                    per_request_timeout_seconds=0.0,
                    wave_deadline=RUNNER.time.monotonic() + 60.0,
                ),
            )

            class SlowOpen:
                def open(self, _request, timeout: float):
                    self.timeout = timeout
                    RUNNER.time.sleep(1.0)
                    raise AssertionError("hard deadline failed")

            started = RUNNER.time.monotonic()
            self.assert_failure(
                "E_REQUEST_DEADLINE",
                lambda: RUNNER.download_exact_once(
                    SlowOpen(),
                    self.item,
                    deadline_fd,
                    maximum_bytes=len(self.raw),
                    aggregate_before=0,
                    maximum_aggregate_bytes=len(self.raw),
                    per_request_timeout_seconds=0.02,
                    wave_deadline=RUNNER.time.monotonic() + 1.0,
                ),
            )
            self.assertLess(RUNNER.time.monotonic() - started, 0.5)

            class SlowReadResponse(FakeResponse):
                def read1(self, size: int = -1) -> bytes:
                    RUNNER.time.sleep(1.0)
                    return super().read1(size)

            slow_response = SlowReadResponse(
                self.raw,
                self.item["url"],
                content_length=str(len(self.raw)),
            )
            started = RUNNER.time.monotonic()
            self.assert_failure(
                "E_WAVE_DEADLINE",
                lambda: RUNNER.download_exact_once(
                    FakeOpener(slow_response),
                    self.item,
                    deadline_fd,
                    maximum_bytes=len(self.raw),
                    aggregate_before=0,
                    maximum_aggregate_bytes=len(self.raw),
                    per_request_timeout_seconds=1.0,
                    wave_deadline=RUNNER.time.monotonic() + 0.02,
                ),
            )
            self.assertLess(RUNNER.time.monotonic() - started, 0.5)
            self.assertEqual(
                RUNNER.signal.getitimer(RUNNER.signal.ITIMER_REAL),
                (0.0, 0.0),
            )
            self.assertEqual(
                RUNNER.signal.getsignal(RUNNER.signal.SIGALRM),
                RUNNER.signal.SIG_DFL,
            )

            started = RUNNER.time.monotonic()
            with self.assertRaises(RUNNER.AcquisitionFailure) as caught:
                with RUNNER.hard_wall_clock_request_deadline(
                    request_deadline=started + 1.0,
                    wave_deadline=started + 0.02,
                    tuple_id="wave1-test",
                    phase="zip",
                ):
                    RUNNER.time.sleep(1.0)
            self.assertEqual(caught.exception.code, "E_WAVE_DEADLINE")
            self.assertEqual(caught.exception.phase, "zip")
            self.assertLess(RUNNER.time.monotonic() - started, 0.5)

            real_setitimer = RUNNER.signal.setitimer
            setup_calls: list[float] = []

            def fail_setup_then_disarm(which, seconds):
                setup_calls.append(seconds)
                if len(setup_calls) == 1:
                    raise OSError("setup failure")
                return real_setitimer(which, seconds)

            def run_setup_failure() -> None:
                with RUNNER.hard_wall_clock_request_deadline(
                    request_deadline=RUNNER.time.monotonic() + 1.0,
                    wave_deadline=RUNNER.time.monotonic() + 2.0,
                    tuple_id="wave1-test",
                ):
                    self.fail("setup failure must not enter the body")

            with mock.patch.object(
                RUNNER.signal,
                "setitimer",
                side_effect=fail_setup_then_disarm,
            ):
                self.assert_failure(
                    "E_DEADLINE_ENVIRONMENT",
                    run_setup_failure,
                )
            self.assertEqual(len(setup_calls), 2)
            self.assertGreater(setup_calls[0], 0)
            self.assertEqual(setup_calls[1], 0.0)
            self.assertEqual(
                RUNNER.signal.getsignal(RUNNER.signal.SIGALRM),
                RUNNER.signal.SIG_DFL,
            )

            cleanup_calls: list[float] = []
            cleanup_events: list[str] = []
            real_signal = RUNNER.signal.signal

            def fail_disarm_once(which, seconds):
                cleanup_calls.append(seconds)
                cleanup_events.append("disarm")
                if len(cleanup_calls) == 1:
                    raise OSError("disarm failure")
                return real_setitimer(which, seconds)

            def restore_signal(number, handler):
                cleanup_events.append("restore")
                return real_signal(number, handler)

            def bounded_test_alarm(_number, _frame):
                raise RUNNER.AcquisitionFailure(
                    "E_REQUEST_DEADLINE",
                    "download",
                    tuple_id="wave1-test",
                )

            real_signal(RUNNER.signal.SIGALRM, bounded_test_alarm)
            real_setitimer(RUNNER.signal.ITIMER_REAL, 0.5)
            try:
                with (
                    mock.patch.object(
                        RUNNER.signal,
                        "setitimer",
                        side_effect=fail_disarm_once,
                    ),
                    mock.patch.object(
                        RUNNER.signal,
                        "signal",
                        side_effect=restore_signal,
                    ) as restore_handler,
                ):
                    self.assert_failure(
                        "E_DEADLINE_ENVIRONMENT",
                        lambda: RUNNER.restore_hard_deadline_state(
                            RUNNER.signal.SIG_DFL,
                            tuple_id="wave1-test",
                        ),
                    )
            finally:
                real_setitimer(RUNNER.signal.ITIMER_REAL, 0.0)
                real_signal(RUNNER.signal.SIGALRM, RUNNER.signal.SIG_DFL)
            self.assertEqual(cleanup_calls, [0.0, 0.0])
            self.assertEqual(cleanup_events, ["disarm", "disarm", "restore"])
            restore_handler.assert_called_once_with(
                RUNNER.signal.SIGALRM,
                RUNNER.signal.SIG_DFL,
            )
            self.assertEqual(
                RUNNER.signal.getitimer(RUNNER.signal.ITIMER_REAL),
                (0.0, 0.0),
            )
            self.assertEqual(
                RUNNER.signal.getsignal(RUNNER.signal.SIGALRM),
                RUNNER.signal.SIG_DFL,
            )

            with (
                mock.patch.object(
                    RUNNER.signal,
                    "setitimer",
                    side_effect=OSError("permanent disarm failure"),
                ) as failed_disarm,
                mock.patch.object(RUNNER.signal, "signal") as unsafe_restore,
            ):
                self.assert_failure(
                    "E_DEADLINE_ENVIRONMENT",
                    lambda: RUNNER.restore_hard_deadline_state(
                        RUNNER.signal.SIG_DFL,
                        tuple_id="wave1-test",
                    ),
                )
            self.assertEqual(failed_disarm.call_count, 2)
            unsafe_restore.assert_not_called()
        finally:
            os.close(deadline_fd)
            deadline_directory.cleanup()

    def test_33_response_and_aggregate_byte_limits_are_enforced(self) -> None:
        for maximum, aggregate_before, aggregate_maximum, code in (
            (len(self.raw) - 1, 0, len(self.raw) * 2, "E_CONTENT_LENGTH"),
            (
                len(self.raw),
                1,
                len(self.raw),
                "E_AGGREGATE_RESPONSE_TOO_LARGE",
            ),
        ):
            response = FakeResponse(
                self.raw,
                self.item["url"],
                content_length=str(len(self.raw)),
            )
            opener = FakeOpener(response)
            directory = tempfile.TemporaryDirectory()
            fd = os.open(
                Path(directory.name) / "out.zip",
                os.O_RDWR | os.O_CREAT,
                0o600,
            )
            try:
                with self.subTest(code=code):
                    self.assert_failure(
                        code,
                        lambda: RUNNER.download_exact_once(
                            opener,
                            self.item,
                            fd,
                            maximum_bytes=maximum,
                            aggregate_before=aggregate_before,
                            maximum_aggregate_bytes=aggregate_maximum,
                            per_request_timeout_seconds=30.0,
                            wave_deadline=RUNNER.time.monotonic() + 60,
                        ),
                    )
            finally:
                os.close(fd)
                directory.cleanup()

    def test_34_failure_document_records_only_bounded_safe_fields(self) -> None:
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
        }
        failure = RUNNER.AcquisitionFailure(
            "E_TRANSPORT",
            "download",
            tuple_id="wave1-test",
            observations={
                "httpStatus": 503,
                "absolutePath": 1,
                "responseBody": 2,
            },
        )
        document = RUNNER.safe_failure_document(
            permit,
            failure,
            attempted_requests=1,
            completed_requests=0,
            claim_sha256="b" * 64,
            final_set_published=False,
        )
        rendered = json.dumps(document)
        self.assertIn('"httpStatus": 503', rendered)
        self.assertNotIn("absolutePath", rendered)
        self.assertNotIn("responseBody", rendered)
        self.assertFalse(document["externalAuthenticationRequired"])
        self.assertFalse(document["userActionRequired"])

    def test_35_ordered_source_set_digest_is_order_sensitive(self) -> None:
        first = [{"order": 1, "tupleId": "a"}, {"order": 2, "tupleId": "b"}]
        second = list(reversed(first))
        self.assertNotEqual(
            RUNNER.ordered_source_set_digest(first),
            RUNNER.ordered_source_set_digest(second),
        )

    def test_36_claim_is_owner_only_durable_and_not_reusable(self) -> None:
        directory = tempfile.TemporaryDirectory()
        parent_fd = os.open(directory.name, RUNNER.directory_open_flags())
        permit = {
            "permitId": "permit",
            "contentBinding": {"sha256": "a" * 64},
            "decisionBinding": {"contentSha256": "b" * 64},
        }
        try:
            _, digest = RUNNER.create_claim(parent_fd, permit)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            info = os.stat(RUNNER.CLAIM_NAME, dir_fd=parent_fd, follow_symlinks=False)
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
            self.assertEqual(info.st_nlink, 1)
            self.assert_failure(
                "E_OUTPUT_EXISTS",
                lambda: RUNNER.create_claim(parent_fd, permit),
            )
        finally:
            os.close(parent_fd)
            directory.cleanup()

    def test_37_temp_to_final_link_is_no_overwrite_and_single_link(self) -> None:
        directory = tempfile.TemporaryDirectory()
        staging_fd = os.open(directory.name, RUNNER.directory_open_flags())
        try:
            first = os.open(
                "temp",
                RUNNER.create_file_flags(),
                0o600,
                dir_fd=staging_fd,
            )
            os.write(first, b"payload")
            os.fsync(first)
            RUNNER.link_temp_to_final(staging_fd, "temp", "final", first)
            info = os.stat("final", dir_fd=staging_fd, follow_symlinks=False)
            self.assertEqual(info.st_nlink, 1)
            self.assertEqual(os.fstat(first).st_ino, info.st_ino)
            os.close(first)
            second = os.open(
                "temp2",
                RUNNER.create_file_flags(),
                0o600,
                dir_fd=staging_fd,
            )
            os.write(second, b"other")
            self.assert_failure(
                "E_OUTPUT_EXISTS",
                lambda: RUNNER.link_temp_to_final(
                    staging_fd,
                    "temp2",
                    "final",
                    second,
                ),
            )
            os.close(second)

            verified = os.open(
                "temp3",
                RUNNER.create_file_flags(),
                0o600,
                dir_fd=staging_fd,
            )
            os.write(verified, b"verified")
            replacement = os.open(
                "replacement",
                RUNNER.create_file_flags(),
                0o600,
                dir_fd=staging_fd,
            )
            os.write(replacement, b"replacement")
            os.close(replacement)
            real_link = os.link

            def swap_before_link(*args, **kwargs):
                os.replace(
                    "replacement",
                    "temp3",
                    src_dir_fd=staging_fd,
                    dst_dir_fd=staging_fd,
                )
                return real_link(*args, **kwargs)

            with mock.patch.object(RUNNER.os, "link", side_effect=swap_before_link):
                self.assert_failure(
                    "E_OUTPUT_IDENTITY",
                    lambda: RUNNER.link_temp_to_final(
                        staging_fd,
                        "temp3",
                        "final3",
                        verified,
                    ),
                )
            os.close(verified)
        finally:
            os.close(staging_fd)
            directory.cleanup()

        inventory_directory = tempfile.TemporaryDirectory()
        inventory_fd = os.open(
            inventory_directory.name,
            RUNNER.directory_open_flags(),
        )
        held_outputs: list[dict] = []
        try:
            for order in range(1, 20):
                name = f"file-{order:02d}.zip"
                payload = f"payload-{order:02d}".encode("ascii")
                fd = os.open(
                    name,
                    RUNNER.create_download_file_flags(),
                    0o600,
                    dir_fd=inventory_fd,
                )
                os.write(fd, payload)
                os.fsync(fd)
                held_outputs.append(
                    {
                        "fd": fd,
                        "name": name,
                        "rawByteSize": len(payload),
                        "rawSha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
            RUNNER.validate_held_output_inventory(inventory_fd, held_outputs)
            real_stable_hash = RUNNER.stable_open_file_sha256

            def mutate_first_after_last(fd: int, *, expected_size: int):
                result = real_stable_hash(fd, expected_size=expected_size)
                if fd == held_outputs[-1]["fd"]:
                    os.pwrite(held_outputs[0]["fd"], b"X", 0)
                    os.fsync(held_outputs[0]["fd"])
                return result

            with mock.patch.object(
                RUNNER,
                "stable_open_file_sha256",
                side_effect=mutate_first_after_last,
            ):
                self.assert_failure(
                    "E_OUTPUT_IDENTITY",
                    lambda: RUNNER.validate_held_output_inventory(
                        inventory_fd,
                        held_outputs,
                    ),
                )
        finally:
            for record in held_outputs:
                os.close(record["fd"])
            os.close(inventory_fd)
            inventory_directory.cleanup()

        rename_directory = tempfile.TemporaryDirectory()
        rename_root_fd = os.open(
            rename_directory.name,
            RUNNER.directory_open_flags(),
        )
        os.mkdir("source", 0o700, dir_fd=rename_root_fd)
        os.mkdir("destination", 0o700, dir_fd=rename_root_fd)
        source_parent_fd = os.open(
            "source",
            RUNNER.directory_open_flags(),
            dir_fd=rename_root_fd,
        )
        destination_parent_fd = os.open(
            "destination",
            RUNNER.directory_open_flags(),
            dir_fd=rename_root_fd,
        )
        try:
            os.mkdir("candidate", 0o700, dir_fd=source_parent_fd)
            RUNNER.exclusive_rename_directory(
                source_parent_fd,
                "candidate",
                destination_parent_fd,
                "accepted",
            )
            self.assertFalse(
                RUNNER.entry_exists(source_parent_fd, "candidate")
            )
            self.assertTrue(
                RUNNER.entry_exists(destination_parent_fd, "accepted")
            )
            os.mkdir("candidate2", 0o700, dir_fd=source_parent_fd)
            self.assert_failure(
                "E_OUTPUT_EXISTS",
                lambda: RUNNER.exclusive_rename_directory(
                    source_parent_fd,
                    "candidate2",
                    destination_parent_fd,
                    "accepted",
                ),
            )
        finally:
            os.close(destination_parent_fd)
            os.close(source_parent_fd)
            os.close(rename_root_fd)
            rename_directory.cleanup()

    def test_38_post_publish_failure_code_is_distinct_and_nonretryable(self) -> None:
        source = RUNNER_BYTES.decode("utf-8")
        self.assertIn('"E_POST_PUBLISH_UNCERTAIN"', source)
        self.assertIn("prepare_new_versioned_wave1_recovery_decision", source)
        self.assertNotIn("automaticRetryAllowed\": True", source)
        post_publish = RUNNER.normalize_execution_failure(
            OSError("secret absolute path"),
            final_set_published=True,
            completed_requests=19,
        )
        self.assertEqual(post_publish.code, "E_POST_PUBLISH_UNCERTAIN")
        self.assertEqual(post_publish.phase, "post_publish")
        self.assertEqual(
            post_publish.observations,
            {"completedRequests": 19},
        )
        internal = RUNNER.normalize_execution_failure(
            RuntimeError("secret"),
            final_set_published=False,
            completed_requests=0,
        )
        self.assertEqual(internal.code, "E_INTERNAL")

    def test_39_runner_has_no_override_cli_or_process_execution_import(self) -> None:
        tree = ast.parse(RUNNER_BYTES, filename=RUNNER_RELATIVE_PATH)
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        self.assertTrue({"ssl", "urllib", "zipfile"}.issubset(imports))
        self.assertTrue({"subprocess", "requests", "httpx"}.isdisjoint(imports))
        self.assertTrue(
            {
                "system",
                "popen",
                "spawnl",
                "spawnv",
                "fork",
                "execl",
                "execv",
            }.isdisjoint(calls)
        )
        source = RUNNER_BYTES.decode("utf-8")
        for forbidden_flag in (
            "--url",
            "--host",
            "--output",
            "--proxy",
            "--credential",
            "--token",
            "--retry",
        ):
            self.assertNotIn(forbidden_flag, source)

    def test_40_runner_pins_isolated_preflight_and_exact_checker_identity(self) -> None:
        RUNNER.require_isolated_interpreter()
        self.assertRegex(RUNNER.EXPECTED_CHECKER_RAW_SHA256, r"^[0-9a-f]{64}$")
        self.assertEqual(RUNNER.PERMIT_PATH.count("execution-permit-v1.json"), 1)
        self.assertEqual(
            RUNNER.EXPECTED_PERMIT_NEXT_ACTION,
            "execute_bound_dependency_source_wave1_once",
        )
        root_info = os.stat(ROOT, follow_symlinks=False)
        identity = {
            "device": root_info.st_dev,
            "inode": root_info.st_ino,
            "ownerUid": root_info.st_uid,
            "mode": stat.S_IMODE(root_info.st_mode),
        }
        root_fd = RUNNER.open_root_directory(identity)
        os.close(root_fd)
        wrong_identity = dict(identity)
        wrong_identity["inode"] += 1
        self.assert_failure(
            "E_FILESYSTEM_ROOT_IDENTITY",
            lambda: RUNNER.open_root_directory(wrong_identity),
        )
        with mock.patch.object(
            RUNNER.threading,
            "current_thread",
            return_value=object(),
        ):
            self.assert_failure(
                "E_DEADLINE_ENVIRONMENT",
                RUNNER.validate_hard_deadline_environment,
            )

    def test_41_preflight_never_builds_network_opener(self) -> None:
        def create_file(root: Path, relative: str) -> None:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"state\n")
            path.chmod(0o600)

        def materialize(root: Path, state: str) -> None:
            dependency_parent = root / str(RUNNER.DEPENDENCY_PARENT)
            if state in {"claim", "staging", "final", "complete"}:
                dependency_parent.mkdir(parents=True, exist_ok=True)
            if state in {"claim", "complete"}:
                create_file(
                    root,
                    f"{RUNNER.DEPENDENCY_PARENT}/{RUNNER.CLAIM_NAME}",
                )
            if state == "staging":
                (dependency_parent / f"{RUNNER.STAGING_PREFIX}fixture").mkdir()
            if state in {"final", "complete"}:
                (
                    dependency_parent
                    / RUNNER.WAVE_PARENT_NAME
                    / RUNNER.FINAL_DIRECTORY_NAME
                ).mkdir(parents=True)
            if state in {"success", "complete"}:
                create_file(root, RUNNER.SUCCESS_RECEIPT_PATH)
            if state == "failure":
                create_file(root, RUNNER.FAILURE_RECEIPT_PATH)
            if state in {"manifest", "complete"}:
                create_file(root, RUNNER.MANIFEST_PATH)

        for state in (
            "clean",
            "claim",
            "staging",
            "final",
            "success",
            "failure",
            "manifest",
            "complete",
        ):
            directory = tempfile.TemporaryDirectory()
            root = Path(directory.name)
            root.chmod(0o700)
            materialize(root, state)
            root_info = os.stat(root, follow_symlinks=False)
            fake = {
                "permit": {
                    "permitId": "permit",
                    "status": RUNNER.EXPECTED_PERMIT_STATUS,
                },
                "repositoryRootIdentity": {
                    "device": root_info.st_dev,
                    "inode": root_info.st_ino,
                    "ownerUid": root_info.st_uid,
                    "mode": stat.S_IMODE(root_info.st_mode),
                },
            }
            try:
                with (
                    self.subTest(state=state),
                    mock.patch.object(RUNNER, "ROOT", root),
                    mock.patch.object(
                        RUNNER,
                        "load_validated_authority",
                        return_value=(types.SimpleNamespace(), fake),
                    ),
                    mock.patch.object(
                        RUNNER,
                        "build_exact_opener",
                        side_effect=AssertionError(
                            "network opener must not be built"
                        ),
                    ),
                ):
                    result = RUNNER.preflight()
                self.assertEqual(result["networkOperationCount"], 0)
                self.assertEqual(result["fileWriteCount"], 0)
                self.assertFalse(result["externalAuthenticationRequired"])
                self.assertFalse(result["userActionRequired"])
                if state == "clean":
                    self.assertEqual(result["status"], "passed")
                    self.assertEqual(result["observedOneUseArtifactCount"], 0)
                    self.assertEqual(
                        result["nextAction"],
                        RUNNER.EXPECTED_PERMIT_NEXT_ACTION,
                    )
                elif state == "complete":
                    self.assertEqual(
                        result["status"],
                        "consumed_pending_independent_readback",
                    )
                    self.assertEqual(
                        result["nextAction"],
                        "run_separate_wave1_independent_readback",
                    )
                else:
                    self.assertEqual(
                        result["status"],
                        "blocked_one_use_state_present",
                    )
                    self.assertEqual(
                        result["nextAction"],
                        "prepare_new_versioned_wave1_recovery_decision",
                    )
            finally:
                directory.cleanup()

        with (
            mock.patch.object(
                RUNNER,
                "preflight",
                return_value={"status": "blocked_one_use_state_present"},
            ),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(RUNNER.main([]), 1)

        execute_directory = tempfile.TemporaryDirectory()
        execute_root = Path(execute_directory.name)
        execute_root.chmod(0o700)
        create_file(execute_root, RUNNER.SUCCESS_RECEIPT_PATH)
        execute_info = os.stat(execute_root, follow_symlinks=False)
        execute_authority = {
            "permit": {"permitId": "permit"},
            "decision": {"resourceLimits": {}},
            "repositoryRootIdentity": {
                "device": execute_info.st_dev,
                "inode": execute_info.st_ino,
                "ownerUid": execute_info.st_uid,
                "mode": stat.S_IMODE(execute_info.st_mode),
            },
        }
        try:
            with (
                mock.patch.object(RUNNER, "ROOT", execute_root),
                mock.patch.object(
                    RUNNER,
                    "load_validated_authority",
                    return_value=(types.SimpleNamespace(), execute_authority),
                ),
                mock.patch.object(
                    RUNNER,
                    "create_claim",
                    side_effect=AssertionError("claim must not be created"),
                ),
                mock.patch.object(
                    RUNNER,
                    "build_exact_opener",
                    side_effect=AssertionError("network must not be opened"),
                ),
            ):
                self.assert_failure(
                    "E_ONE_USE_STATE_PRESENT",
                    RUNNER._execute_once_with_umask,
                )
            self.assertFalse(
                (execute_root / str(RUNNER.DEPENDENCY_PARENT)).exists()
            )
        finally:
            execute_directory.cleanup()

    def test_42_main_redacts_exception_text_and_absolute_paths(self) -> None:
        failure = RUNNER.AcquisitionFailure(
            "E_TRANSPORT",
            "download",
            tuple_id="wave1-test",
        )
        with (
            mock.patch.object(RUNNER, "preflight", side_effect=failure),
            mock.patch("builtins.print") as output,
        ):
            self.assertEqual(RUNNER.main([]), 1)
        rendered = output.call_args.args[0]
        self.assertIn('"failureCode": "E_TRANSPORT"', rendered)
        self.assertNotIn(str(ROOT), rendered)
        self.assertNotIn("token", rendered.lower())
        with (
            mock.patch.object(
                RUNNER,
                "preflight",
                side_effect=RuntimeError(f"secret {ROOT} token"),
            ),
            mock.patch("builtins.print") as internal_output,
        ):
            self.assertEqual(RUNNER.main([]), 1)
        internal_rendered = internal_output.call_args.args[0]
        self.assertIn('"failureCode": "E_INTERNAL"', internal_rendered)
        self.assertNotIn(str(ROOT), internal_rendered)
        self.assertNotIn("token", internal_rendered.lower())

    def test_43_exact_public_proxy_opener_disables_ambient_proxy(self) -> None:
        opener = RUNNER.build_exact_opener()
        proxy_handlers = [
            handler
            for handler in opener.handlers
            if handler.__class__.__name__ == "ProxyHandler"
        ]
        redirect_handlers = [
            handler
            for handler in opener.handlers
            if isinstance(handler, RUNNER.RejectRedirects)
        ]
        self.assertEqual(proxy_handlers, [])
        self.assertIn("ProxyHandler({})", RUNNER_BYTES.decode("utf-8"))
        self.assertEqual(len(redirect_handlers), 1)

    def test_44_success_receipt_and_manifest_keep_readback_false(self) -> None:
        source = RUNNER_BYTES.decode("utf-8")
        self.assertGreaterEqual(source.count('"independentReadbackPassed": False'), 3)
        self.assertNotIn('"independentReadbackPassed": True', source)
        self.assertIn('"manifestWrittenLast": True', source)


if __name__ == "__main__":
    unittest.main()
