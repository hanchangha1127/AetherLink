#!/usr/bin/env python3
"""Offline synthetic tests for the one-use Wave3 source acquirer."""

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
    raise RuntimeError("tests require `python3 -I -B -S`")

import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest import mock
import warnings
import zipfile


PATH = Path(__file__).with_name(
    "acquire_p2p_nat_g2_pion_rung3_dependency_wave3_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location("wave3_source_acquirer_v1", PATH)
assert SPEC and SPEC.loader
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


def manual_h1(rows):
    body = b"".join(
        f"{digest}  {name}\n".encode()
        for name, digest in sorted(rows, key=lambda row: row[0].encode())
    )
    return "h1:" + base64.b64encode(hashlib.sha256(body).digest()).decode()


def make_zip(module: str, version: str, files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    prefix = f"{module}@{version}/"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            info = zipfile.ZipInfo(prefix + name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return output.getvalue()


def synthetic_rows():
    rows = []
    bodies = {}
    for index in range(1, 17):
        module = f"example.test/dependency{index}"
        version = f"v1.0.{index}"
        tuple_id = f"tuple-{index:02d}"
        mod = f"module {module}\n\ngo 1.23\n".encode()
        archive = make_zip(
            module,
            version,
            {"go.mod": mod, "source/file.go": f"package dep{index}\n".encode()},
        )
        for kind, body, maximum in (
            ("mod", mod, R.CHECK.MAX_MOD_BYTES),
            ("zip", archive, R.CHECK.MAX_ZIP_BYTES),
        ):
            ordinal = len(rows) + 1
            expected = (
                R.go_mod_h1(body)
                if kind == "mod"
                else R.module_zip_h1(body, module, version)
            )
            row = {
                "requestOrdinal": ordinal,
                "tupleOrder": index,
                "tupleId": tuple_id,
                "module": module,
                "version": version,
                "kind": kind,
                "method": "GET",
                "host": R.CHECK.PROXY_HOST,
                "path": f"/{module}/@v/{version}.{kind}",
                "url": f"https://{R.CHECK.PROXY_HOST}/{module}/@v/{version}.{kind}",
                "expectedH1": expected,
                "maximumResponseBodyBytes": maximum,
                "acceptedFileName": f"{index:03d}-synthetic.{kind}",
            }
            rows.append(row)
            bodies[ordinal] = body
    return rows, bodies


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, delay: float = 0.0):
        self.body = body
        self.status = status
        self.delay = delay
        self.offset = 0
        self.headers = [
            ("Content-Length", str(len(body))),
            ("Content-Encoding", "identity"),
        ]

    def getheaders(self):
        return list(self.headers)

    def getheader(self, name):
        for key, value in self.headers:
            if key.lower() == name.lower():
                return value
        return None

    def read(self, count):
        if self.delay:
            time.sleep(self.delay)
        if self.offset >= len(self.body):
            return b""
        result = self.body[self.offset:self.offset + min(count, 1)]
        self.offset += len(result)
        return result


class FakeConnection:
    response = FakeResponse(b"x")
    seen = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def request(self, *args, **kwargs):
        type(self).seen.append((args, kwargs))

    def getresponse(self):
        return type(self).response

    def close(self):
        pass


class Wave3AcquirerTests(unittest.TestCase):
    def test_01_go_mod_h1_matches_independent_dirhash(self):
        raw = b"module example.test/a\n\ngo 1.23\n"
        self.assertEqual(
            R.go_mod_h1(raw),
            manual_h1([("go.mod", hashlib.sha256(raw).hexdigest())]),
        )
        self.assertEqual(R.validate_mod(raw, "example.test/a")["goModH1"], R.go_mod_h1(raw))
        with self.assertRaises(R.AcquisitionError):
            R.validate_mod(raw.replace(b"example.test/a", b"example.test/b"), "example.test/a")

    def test_01b_quoted_module_directives_and_fail_closed_forms(self):
        module = "example.test/a"
        for raw in (
            b"module example.test/a\n",
            b'module "example.test/a"\n',
            b'module "example.test/a" // exact quoted form\n',
        ):
            self.assertEqual(R.validate_mod(raw, module)["goModH1"], R.go_mod_h1(raw))
        invalid = (
            b'module "example.test/a\n',
            b'module "example.test\\x2fa"\n',
            b'module "example.test/a\\""\n',
            b"module example.test/a extra\n",
            b"module example.test/a\nmodule example.test/a\n",
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(R.AcquisitionError):
                R.validate_mod(raw, module)

    def test_01c_retained_quoted_module_fixtures_pass_read_only(self):
        fixtures = [
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v3/accepted/"
                "012-2055c3218667fc22d930.mod",
                "e3d5d46d2f6ac94a666a54b5e867ec16bf199d9f4b700827cd731607efdd109a",
                "github.com/kr/pretty",
                "h1:dAy3ld7l9f0ibDNOQOHHMYYIIbhfbHSm3C4ZsoJORNo=",
            ),
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v3/accepted/"
                "019-495087f35325ae50e341.mod",
                "21579860a20306fcf43b1bd234d1fba319499c77611b71c05f9bf3ba90dab939",
                "gopkg.in/yaml.v3",
                "h1:K4uyk7z7BCEPqu6E+C64Yfv1cQ7kz7rIZviUmN+EgEM=",
            ),
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v3/accepted/"
                "001-21ba4abc86961659f24e.mod",
                "2fba9529e5c13dde62f371ef7383baf04d7132501dac6aa08e910f9ec0bf85c5",
                "github.com/kr/text",
                "h1:4Jbv+DJW3UT/LiOwJeYQe1efqtUx/iVham/4vfdArNI=",
            ),
        ]
        root = PATH.parents[1]
        for relative, expected_raw, module, expected_h1 in fixtures:
            with self.subTest(module=module):
                raw = (root / relative).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_raw)
                self.assertEqual(R.validate_mod(raw, module)["goModH1"], expected_h1)

    def test_02_zip_h1_uses_full_names_and_mod_parity(self):
        module, version = "example.test/a", "v1.2.3"
        mod = b"module example.test/a\n"
        files = {"go.mod": mod, "a.txt": b"alpha", "dir/b.txt": b"beta"}
        raw = make_zip(module, version, files)
        expected_rows = [
            (f"{module}@{version}/{name}", hashlib.sha256(body).hexdigest())
            for name, body in files.items()
        ]
        result = R.validate_zip(raw, module, version, mod)
        self.assertEqual(result["moduleZipH1"], manual_h1(expected_rows))
        self.assertEqual(result["entryCount"], 3)
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(raw, module, version, mod + b"x")

    def test_03_zip_path_mode_duplicate_and_size_mutations_fail(self):
        module, version = "example.test/a", "v1.0.0"
        mutations = [
            {"../evil": b"x"},
            {"a\\b": b"x"},
            {"a:b": b"x"},
        ]
        for files in mutations:
            with self.subTest(files=files), self.assertRaises(R.AcquisitionError):
                R.validate_zip(make_zip(module, version, files), module, version)
        output = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr(f"{module}@{version}/same", b"a")
                archive.writestr(f"{module}@{version}/same", b"b")
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(output.getvalue(), module, version)
        raw = make_zip(module, version, {"big": b"x" * 64})
        with mock.patch.object(R.CHECK, "MAX_ZIP_FILE_BYTES", 32):
            with self.assertRaises(R.AcquisitionError):
                R.validate_zip(raw, module, version)

    def test_03b_zip_container_structure_mutations_fail(self):
        module, version = "example.test/a", "v1.0.0"
        raw = make_zip(module, version, {"a.txt": b"alpha"})
        mutations = []
        mutations.append(raw + b"x")
        zip64 = bytearray(raw)
        zip64[10:14] = R.ZIP64_EOCD_SIGNATURE
        mutations.append(bytes(zip64))
        multidisk = bytearray(raw)
        eocd = multidisk.rfind(R.ZIP_EOCD_SIGNATURE)
        multidisk[eocd + 4:eocd + 6] = (1).to_bytes(2, "little")
        mutations.append(bytes(multidisk))
        local_drift = bytearray(raw)
        local_drift[8:10] = (zipfile.ZIP_STORED).to_bytes(2, "little")
        mutations.append(bytes(local_drift))
        for mutated in mutations:
            with self.subTest(length=len(mutated)), self.assertRaises(R.AcquisitionError):
                R.validate_zip(mutated, module, version)
        symlink = io.BytesIO()
        with zipfile.ZipFile(symlink, "w") as archive:
            info = zipfile.ZipInfo(f"{module}@{version}/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(symlink.getvalue(), module, version)

    def test_03c_local_central_parity_and_payload_signature_regressions(self):
        module, version = "example.test/a", "v1.0.0"
        payload = R.ZIP64_EOCD_SIGNATURE + R.ZIP64_LOCATOR_SIGNATURE
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
            info = zipfile.ZipInfo(f"{module}@{version}/signature.bin")
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, payload)
        valid = output.getvalue()
        self.assertIn(payload, valid)
        self.assertEqual(R.validate_zip(valid, module, version)["entryCount"], 1)

        for offset in (4, 10, 12):
            mutated = bytearray(make_zip(module, version, {"a.txt": b"alpha"}))
            mutated[offset:offset + 2] = (
                int.from_bytes(mutated[offset:offset + 2], "little") ^ 1
            ).to_bytes(2, "little")
            with self.subTest(local_field_offset=offset), self.assertRaises(R.AcquisitionError):
                R.validate_zip(bytes(mutated), module, version)

        local_extra = bytearray(make_zip(module, version, {"a.txt": b"alpha"}))
        name_length = int.from_bytes(local_extra[26:28], "little")
        data_start = R.ZIP_LOCAL_HEADER.size + name_length
        local_extra[28:30] = (4).to_bytes(2, "little")
        local_extra[data_start:data_start] = b"\xfe\xca\x00\x00"
        eocd = local_extra.rfind(R.ZIP_EOCD_SIGNATURE)
        central_offset_field = eocd + 16
        old_central = int.from_bytes(
            local_extra[central_offset_field:central_offset_field + 4], "little"
        )
        local_extra[central_offset_field:central_offset_field + 4] = (
            old_central + 4
        ).to_bytes(4, "little")
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(bytes(local_extra), module, version)

    def test_03d_ancestor_collision_uses_precomputed_sets(self):
        source = PATH.read_text()
        self.assertIn(
            "folded_relative_files = {name.casefold() for name in relative_files}",
            source,
        )
        self.assertNotIn(
            "not in {name.casefold() for name in relative_files}",
            source,
        )

    def test_03e_control_encoding_dos_and_central_trailing_records_fail(self):
        module, version = "example.test/a", "v1.0.0"
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(
                make_zip(module, version, {"tab\tname": b"x"}),
                module,
                version,
            )

        non_utf8 = bytearray(make_zip(module, version, {"ascii.txt": b"x"}))
        eocd = non_utf8.rfind(R.ZIP_EOCD_SIGNATURE)
        central = int.from_bytes(non_utf8[eocd + 16:eocd + 20], "little")
        non_utf8[R.ZIP_LOCAL_HEADER.size] = 0x80
        non_utf8[central + R.ZIP_CENTRAL_HEADER.size] = 0x80
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(bytes(non_utf8), module, version)

        dos_special = bytearray(make_zip(module, version, {"a.txt": b"x"}))
        eocd = dos_special.rfind(R.ZIP_EOCD_SIGNATURE)
        central = int.from_bytes(dos_special[eocd + 16:eocd + 20], "little")
        dos_special[central + 5] = 0
        external = int.from_bytes(dos_special[central + 38:central + 42], "little")
        dos_special[central + 38:central + 42] = (external | 0x08).to_bytes(4, "little")
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(bytes(dos_special), module, version)

        digital = bytearray(make_zip(module, version, {"a.txt": b"x"}))
        eocd = digital.rfind(R.ZIP_EOCD_SIGNATURE)
        digital[eocd:eocd] = b"PK\x05\x05\x00\x00"
        eocd += 6
        central_size = int.from_bytes(digital[eocd + 12:eocd + 16], "little")
        digital[eocd + 12:eocd + 16] = (central_size + 6).to_bytes(4, "little")
        with self.assertRaises(R.AcquisitionError):
            R.validate_zip(bytes(digital), module, version)

    def test_03f_retained_proxy_data_descriptor_archives_pass_read_only(self):
        fixtures = [
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v3/accepted/"
                "001-c7683a099605cf146d8d.zip",
                "d0f02f377217f42702e259684e06441edbf5140dddcc34ba9bea56038b38a6ed",
                "github.com/google/uuid",
                "v1.6.0",
                "h1:NIvaJDMOsjHA8n1jAhLSgzrAzy1Hgr+hNrb57e+94F0=",
            ),
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/wave-2-v3/accepted/"
                "001-21ba4abc86961659f24e.zip",
                "9363a4c8f1f3387a36014de51b477b831a13981fc59a5665f9d21609bea9e77c",
                "github.com/kr/text",
                "v0.1.0",
                "h1:45sCR5RtlFHMR4UwH9sdQ5TC8v0qDQCHnXt+kaKSTVE=",
            ),
        ]
        root = PATH.parents[1]
        for relative, expected_raw, module, version, expected_h1 in fixtures:
            with self.subTest(module=module):
                raw = (root / relative).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_raw)
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    self.assertTrue(all(info.flag_bits & 0x0008 for info in archive.infolist()))
                self.assertEqual(
                    R.validate_zip(raw, module, version)["moduleZipH1"],
                    expected_h1,
                )

    def test_04_bound_resources_are_exact_order_and_paths(self):
        values, _ = R.CHECK.evaluate(True)
        rows = values["permit"]["requestContract"]["resources"]
        self.assertEqual(len(rows), 32)
        self.assertEqual([row["requestOrdinal"] for row in rows], list(range(1, 33)))
        self.assertEqual([row["kind"] for row in rows], ["mod", "zip"] * 16)
        self.assertTrue(all(row["url"] == "https://proxy.golang.org" + row["path"] for row in rows))
        self.assertEqual(rows[0]["path"], "/github.com/kr/pty/@v/v1.1.1.mod")
        self.assertEqual(rows[-1]["path"], "/golang.org/x/tools/@v/v0.41.0.zip")

    def test_05_direct_fetch_has_exact_request_and_no_retry(self):
        values, _ = R.CHECK.evaluate(True)
        resource = values["permit"]["requestContract"]["resources"][0]
        FakeConnection.seen = []
        FakeConnection.response = FakeResponse(b"module github.com/kr/pty\n")
        body = R.direct_fetch(resource, time.monotonic() + 2, FakeConnection)
        self.assertEqual(body, FakeConnection.response.body)
        self.assertEqual(len(FakeConnection.seen), 1)
        args, kwargs = FakeConnection.seen[0]
        self.assertEqual(args, ("GET", resource["path"]))
        self.assertIsNone(kwargs["body"])
        self.assertFalse(kwargs["encode_chunked"])
        self.assertNotIn("Authorization", kwargs["headers"])
        bad = dict(resource, host="other.invalid")
        with self.assertRaises(R.AcquisitionError):
            R.direct_fetch(bad, time.monotonic() + 2, FakeConnection)
        self.assertEqual(len(FakeConnection.seen), 1)

    def test_06_slow_drip_hits_absolute_request_deadline(self):
        values, _ = R.CHECK.evaluate(True)
        resource = values["permit"]["requestContract"]["resources"][0]
        FakeConnection.response = FakeResponse(b"abcdef", delay=0.02)
        with mock.patch.object(R.CHECK, "PER_REQUEST_DEADLINE_MS", 35):
            with self.assertRaises(R.AcquisitionError) as caught:
                R.direct_fetch(resource, time.monotonic() + 2, FakeConnection)
        self.assertEqual(caught.exception.code, "E_DEADLINE")

    def test_07_synthetic_e2e_claim_precedes_fetch_and_manifest_is_last(self):
        values, _ = R.CHECK.evaluate(True)
        rows, bodies = synthetic_rows()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            dependencies = base / "dependencies"
            terminals = base / "terminals"
            dependencies.mkdir(mode=0o700)
            terminals.mkdir(mode=0o700)
            claim = dependencies / ".wave-3-v1.claim"
            receipt = terminals / "receipt.json"
            failure = terminals / "failure.json"
            manifest = terminals / "manifest.json"
            calls = []

            def fetch(resource, _deadline):
                self.assertTrue(claim.exists())
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            receipt_value = R._attempt(
                fetch, values, claim, dependencies, ".stage-", dependencies / "wave-3-v1",
                receipt, failure, manifest, lambda source, destination: os.rename(source, destination),
                rows, 10,
            )
            self.assertEqual(calls, list(range(1, 33)))
            self.assertEqual(receipt_value["status"], "consumed_success_pending_readback")
            accepted = dependencies / "wave-3-v1" / "accepted"
            self.assertEqual(len(list(accepted.iterdir())), 32)
            self.assertTrue(claim.exists() and receipt.exists() and manifest.exists())
            self.assertFalse(failure.exists())
            self.assertGreaterEqual(manifest.stat().st_mtime_ns, receipt.stat().st_mtime_ns)
            self.assertEqual(stat.S_IMODE(claim.stat().st_mode), 0o600)
            self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in accepted.iterdir()))

    def test_08_h1_failure_is_permanent_and_retains_staging(self):
        values, _ = R.CHECK.evaluate(True)
        rows, bodies = synthetic_rows()
        rows = copy.deepcopy(rows)
        rows[3]["expectedH1"] = "h1:" + base64.b64encode(b"\0" * 32).decode()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            dependencies = base / "dependencies"
            terminals = base / "terminals"
            dependencies.mkdir()
            terminals.mkdir()
            claim = dependencies / ".wave-3-v1.claim"
            failure = terminals / "failure.json"
            calls = []

            def fetch(resource, _deadline):
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            with self.assertRaises(R.AcquisitionError):
                R._attempt(
                    fetch, values, claim, dependencies, ".stage-", dependencies / "wave-3-v1",
                    terminals / "receipt.json", failure, terminals / "manifest.json",
                    lambda source, destination: os.rename(source, destination), rows, 10,
                )
            self.assertEqual(calls, [1, 2, 3, 4])
            self.assertTrue(claim.exists() and failure.exists())
            self.assertFalse((dependencies / "wave-3-v1").exists())
            self.assertEqual(len(list(dependencies.glob(".stage-*"))), 1)
            terminal = json.loads(failure.read_text())
            self.assertEqual(terminal["failureCode"], "E_H1_MISMATCH")
            self.assertEqual(terminal["requestAttemptCount"], 4)
            self.assertEqual(terminal["responseCompletedCount"], 4)
            self.assertEqual(terminal["validatedResourceCount"], 3)
            self.assertEqual(terminal["persistedResourceCount"], 3)
            self.assertTrue(terminal["sourceAcquired"])
            for key in (
                "decisionContentSha256", "permitContentSha256", "checkerRawSha256",
                "runnerRawSha256", "claimRawSha256", "resourceSetCanonicalSha256",
            ):
                self.assertRegex(terminal[key], r"^[0-9a-f]{64}$")
            with self.assertRaises(R.AcquisitionError) as consumed:
                R.create_claim(claim, {"second": True})
            self.assertEqual(consumed.exception.code, "E_CONSUMED")
            self.assertEqual(calls, [1, 2, 3, 4])

    def test_09_expired_deadline_fails_after_claim_without_fetch(self):
        values, _ = R.CHECK.evaluate(True)
        rows, _ = synthetic_rows()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            dependencies = base / "dependencies"
            terminals = base / "terminals"
            dependencies.mkdir()
            terminals.mkdir()
            calls = []
            with self.assertRaises(R.AcquisitionError) as caught:
                R._attempt(
                    lambda resource, deadline: calls.append(resource), values,
                    dependencies / ".claim", dependencies, ".stage-", dependencies / "final",
                    terminals / "receipt", terminals / "failure", terminals / "manifest",
                    lambda source, destination: os.rename(source, destination), rows, -1,
                )
            self.assertEqual(caught.exception.code, "E_DEADLINE")
            self.assertEqual(calls, [])
            self.assertTrue((dependencies / ".claim").exists())
            self.assertTrue((terminals / "failure").exists())

    def test_09b_claim_write_and_fsync_uncertainty_never_fetches(self):
        values, _ = R.CHECK.evaluate(True)
        rows, _ = synthetic_rows()
        for failure_kind in ("write_after_exclusive", "file_fsync", "parent_fsync"):
            with self.subTest(failure_kind=failure_kind), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                dependencies = base / "dependencies"
                terminals = base / "terminals"
                dependencies.mkdir()
                terminals.mkdir()
                claim = dependencies / ".claim"
                fetches = []
                real_write = R.os.write
                real_fsync = R.os.fsync
                write_calls = 0
                fsync_calls = 0

                def controlled_write(fd, raw):
                    nonlocal write_calls
                    write_calls += 1
                    if failure_kind == "write_after_exclusive" and write_calls == 1:
                        real_write(fd, b"{")
                        raise OSError("synthetic claim write uncertainty")
                    return real_write(fd, raw)

                def controlled_fsync(fd):
                    nonlocal fsync_calls
                    fsync_calls += 1
                    if (
                        failure_kind == "file_fsync" and fsync_calls == 1
                    ) or (
                        failure_kind == "parent_fsync" and fsync_calls == 2
                    ):
                        raise OSError("synthetic claim fsync uncertainty")
                    return real_fsync(fd)

                with mock.patch.object(R.os, "write", controlled_write), mock.patch.object(
                    R.os, "fsync", controlled_fsync
                ):
                    with self.assertRaises(R.AcquisitionError) as caught:
                        R._attempt(
                            lambda resource, deadline: fetches.append(resource),
                            values, claim, dependencies, ".stage-", dependencies / "final",
                            terminals / "receipt", terminals / "failure",
                            terminals / "manifest",
                            lambda source, destination: os.rename(source, destination),
                            rows, 10,
                        )
                self.assertEqual(caught.exception.code, "E_CLAIM_STATE_UNCERTAIN")
                self.assertEqual(caught.exception.phase, "claim")
                self.assertEqual(fetches, [])
                self.assertTrue(claim.exists())
                self.assertFalse((terminals / "failure").exists())
                self.assertFalse((dependencies / "final").exists())

    def test_09c_failure_publication_uncertainty_is_explicit(self):
        values, _ = R.CHECK.evaluate(True)
        original_rows, bodies = synthetic_rows()
        for failure_kind in ("partial_write", "file_fsync", "parent_fsync"):
            with self.subTest(failure_kind=failure_kind), tempfile.TemporaryDirectory() as directory:
                rows = copy.deepcopy(original_rows)
                rows[0]["expectedH1"] = "h1:" + base64.b64encode(b"\0" * 32).decode()
                base = Path(directory)
                dependencies = base / "dependencies"
                terminals = base / "terminals"
                dependencies.mkdir()
                terminals.mkdir()
                claim = dependencies / ".claim"
                failure = terminals / "failure"
                real_write = R.os.write
                real_fsync = R.os.fsync
                write_calls = 0
                fsync_calls = 0

                def controlled_write(fd, raw):
                    nonlocal write_calls
                    write_calls += 1
                    if failure_kind == "partial_write" and write_calls == 2:
                        real_write(fd, b"{")
                        raise OSError("synthetic failure write uncertainty")
                    return real_write(fd, raw)

                def controlled_fsync(fd):
                    nonlocal fsync_calls
                    fsync_calls += 1
                    target = 4 if failure_kind == "file_fsync" else 5
                    if failure_kind != "partial_write" and fsync_calls == target:
                        raise OSError("synthetic failure fsync uncertainty")
                    return real_fsync(fd)

                with mock.patch.object(R.os, "write", controlled_write), mock.patch.object(
                    R.os, "fsync", controlled_fsync
                ):
                    with self.assertRaises(R.AcquisitionError) as caught:
                        R._attempt(
                            lambda resource, deadline: bodies[resource["requestOrdinal"]],
                            values, claim, dependencies, ".stage-", dependencies / "final",
                            terminals / "receipt", failure, terminals / "manifest",
                            lambda source, destination: os.rename(source, destination),
                            rows, 10,
                        )
                self.assertEqual(
                    caught.exception.code,
                    "E_FAILURE_PUBLICATION_UNCERTAIN",
                )
                self.assertEqual(caught.exception.phase, "failure_terminal")
                self.assertTrue(claim.exists())
                self.assertTrue(failure.exists())
                self.assertFalse((dependencies / "final").exists())

    def test_09d_exception_immediately_after_claim_is_consumed_uncertainty(self):
        values, _ = R.CHECK.evaluate(True)
        rows, _ = synthetic_rows()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            dependencies = base / "dependencies"
            terminals = base / "terminals"
            dependencies.mkdir()
            terminals.mkdir()
            claim = dependencies / ".claim"
            fetches = []
            real_create = R.create_claim

            def create_then_interrupt(path, payload):
                real_create(path, payload)
                raise RuntimeError("synthetic post-claim/pre-flag interruption")

            with mock.patch.object(R, "create_claim", create_then_interrupt):
                with self.assertRaises(R.AcquisitionError) as caught:
                    R._attempt(
                        lambda resource, deadline: fetches.append(resource),
                        values, claim, dependencies, ".stage-", dependencies / "final",
                        terminals / "receipt", terminals / "failure",
                        terminals / "manifest",
                        lambda source, destination: os.rename(source, destination),
                        rows, 10,
                    )
            self.assertEqual(caught.exception.code, "E_CLAIM_STATE_UNCERTAIN")
            self.assertEqual(fetches, [])
            self.assertTrue(claim.exists())
            self.assertFalse((terminals / "failure").exists())
            self.assertFalse(any(dependencies.glob(".stage-*")))

    def test_10_post_publication_terminal_uncertainty_never_writes_failure(self):
        values, _ = R.CHECK.evaluate(True)
        rows, bodies = synthetic_rows()
        for failed_name in ("receipt", "manifest"):
            with self.subTest(failed_name=failed_name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                dependencies = base / "dependencies"
                terminals = base / "terminals"
                dependencies.mkdir()
                terminals.mkdir()
                receipt = terminals / "receipt"
                manifest = terminals / "manifest"
                failure = terminals / "failure"
                real_write = R._exclusive_file

                def controlled_write(path, raw, mode=0o600):
                    if path == (receipt if failed_name == "receipt" else manifest):
                        raise R.AcquisitionError("E_SYNTHETIC_TERMINAL", failed_name)
                    return real_write(path, raw, mode)

                with mock.patch.object(R, "_exclusive_file", controlled_write):
                    with self.assertRaises(R.AcquisitionError) as caught:
                        R._attempt(
                            lambda resource, deadline: bodies[resource["requestOrdinal"]],
                            values, dependencies / ".claim", dependencies, ".stage-",
                            dependencies / "wave-3-v1", receipt, failure, manifest,
                            lambda source, destination: os.rename(source, destination),
                            rows, 10,
                        )
                self.assertEqual(caught.exception.code, "E_POST_PUBLISH_UNCERTAIN")
                self.assertEqual(caught.exception.phase, "terminal_state")
                self.assertTrue((dependencies / ".claim").exists())
                self.assertTrue((dependencies / "wave-3-v1" / "accepted").is_dir())
                self.assertFalse(failure.exists())
                self.assertEqual(receipt.exists(), failed_name == "manifest")
                self.assertFalse(manifest.exists())

    def test_11_execute_restores_preexisting_real_timer(self):
        original_handler = R.signal.getsignal(R.signal.SIGALRM)
        original_timer = R.signal.getitimer(R.signal.ITIMER_REAL)

        def previous_handler(_signum, _frame):
            pass

        R.signal.signal(R.signal.SIGALRM, previous_handler)
        R.signal.setitimer(R.signal.ITIMER_REAL, 5.0, 0.25)
        started = time.monotonic()
        try:
            with mock.patch.object(R, "preflight", return_value=({}, {})), mock.patch.object(
                R, "_attempt", return_value={"synthetic": True}
            ):
                self.assertEqual(R.execute(lambda resource, deadline: b""), {"synthetic": True})
            delay, interval = R.signal.getitimer(R.signal.ITIMER_REAL)
            elapsed = time.monotonic() - started
            self.assertGreater(delay, max(0.1, 5.0 - elapsed - 0.2))
            self.assertLessEqual(delay, 5.0)
            self.assertAlmostEqual(interval, 0.25, places=2)
            self.assertIs(R.signal.getsignal(R.signal.SIGALRM), previous_handler)
        finally:
            R.signal.setitimer(R.signal.ITIMER_REAL, 0)
            R.signal.signal(R.signal.SIGALRM, original_handler)
            if original_timer[0] > 0:
                R.signal.setitimer(
                    R.signal.ITIMER_REAL,
                    max(0.000001, original_timer[0] - (time.monotonic() - started)),
                    original_timer[1],
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
