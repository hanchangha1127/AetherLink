#!/usr/bin/env python3
"""Offline tests for the G2 Pion dependency wave-one v3 runner."""

from __future__ import annotations

import base64
from contextlib import nullcontext
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPT_DIR / "acquire_p2p_nat_g2_pion_dependency_wave1_v3_once.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("wave1_v3_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("cannot load v3 runner")
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)

LEGACY_PATH = SCRIPT_DIR / "acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
LEGACY_SPEC = importlib.util.spec_from_file_location(
    "wave1_v1_legacy_for_v3_tests",
    LEGACY_PATH,
)
if LEGACY_SPEC is None or LEGACY_SPEC.loader is None:
    raise RuntimeError("cannot load v1 runner")
legacy = importlib.util.module_from_spec(LEGACY_SPEC)
LEGACY_SPEC.loader.exec_module(legacy)
runner.configure_legacy(legacy)


def single_go_mod_h1(payload: bytes) -> str:
    file_digest = hashlib.sha256(payload).hexdigest()
    aggregate = hashlib.sha256()
    aggregate.update(file_digest.encode("ascii"))
    aggregate.update(b"  go.mod\n")
    return "h1:" + base64.b64encode(aggregate.digest()).decode("ascii")


class Headers:
    def __init__(self, values: dict[str, list[str]] | None = None) -> None:
        self.values = {
            key.lower(): list(items) for key, items in (values or {}).items()
        }

    def get_all(self, name: str, default: list[str]) -> list[str]:
        return list(self.values.get(name.lower(), default))


class Response:
    def __init__(
        self,
        url: str,
        content_type: str,
        *,
        status: int = 200,
        extra: dict[str, list[str]] | None = None,
    ) -> None:
        values = {"Content-Type": [content_type]}
        values.update(extra or {})
        self.status = status
        self.headers = Headers(values)
        self.url = url

    def geturl(self) -> str:
        return self.url


class BodyResponse(Response):
    def __init__(
        self,
        url: str,
        content_type: str,
        body: bytes,
        *,
        declared_length: int | None = None,
    ) -> None:
        extra = (
            {}
            if declared_length is None
            else {"Content-Length": [str(declared_length)]}
        )
        super().__init__(url, content_type, extra=extra)
        self.body = body
        self.offset = 0

    def read1(self, amount: int) -> bytes:
        chunk = self.body[self.offset : self.offset + amount]
        self.offset += len(chunk)
        return chunk

    def close(self) -> None:
        pass


class CapturingOpener:
    def __init__(self, response: BodyResponse) -> None:
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request: object, *, timeout: float) -> BodyResponse:
        self.request = request
        self.timeout = timeout
        return self.response


class DependencyWaveOneV3RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.module = "example.com/aetherlink-test"
        self.version = "v1.0.0"
        self.mod = f"module {self.module}\n\ngo 1.22\n".encode()
        self.item: dict[str, object] = {
            "order": 1,
            "tupleId": "wave1-001-" + ("a" * 12),
            "tupleSha256": "a" * 64,
            "module": self.module,
            "version": self.version,
            "url": (
                "https://proxy.golang.org/"
                "example.com/aetherlink-test/@v/v1.0.0.zip"
            ),
            "moduleZipH1": "h1:" + ("A" * 43) + "=",
            "goModH1": single_go_mod_h1(self.mod),
        }
        self.limits = {
            "maximumEntriesPerArchive": 16_384,
            "maximumAggregateEntries": 131_072,
            "maximumCentralDirectoryBytesPerArchive": 8 * 1024 * 1024,
            "maximumSingleFileBytes": 16 * 1024 * 1024,
            "maximumUncompressedBytesPerArchive": 256 * 1024 * 1024,
            "maximumAggregateUncompressedBytes": 1024 * 1024 * 1024,
            "maximumPathBytes": 1024,
            "maximumPathComponents": 64,
            "maximumComponentBytes": 255,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_zip(
        self,
        *,
        embedded_mod: bytes | None,
        h1_override: str | None = None,
    ) -> tuple[int, dict[str, object]]:
        path = self.root / "module.zip"
        prefix = f"{self.module}@{self.version}/"
        entries = [("payload.txt", b"payload")]
        if embedded_mod is not None:
            entries.insert(0, ("go.mod", embedded_mod))
        rows: list[tuple[str, str]] = []
        with zipfile.ZipFile(
            path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative, payload in entries:
                name = prefix + relative
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = 0o100600 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, payload)
                rows.append((name, hashlib.sha256(payload).hexdigest()))
        os.chmod(path, 0o600)
        item = dict(self.item)
        item["moduleZipH1"] = h1_override or legacy.dirhash_h1(rows)
        return os.open(path, os.O_RDWR), item

    def inspect_zip(
        self,
        fd: int,
        item: dict[str, object],
        external_mod: bytes | None = None,
    ) -> dict[str, object]:
        return runner.inspect_module_zip_v3(
            legacy,
            fd,
            item,
            self.limits,
            aggregate_entries_before=0,
            aggregate_uncompressed_before=0,
            external_go_mod=self.mod if external_mod is None else external_mod,
        )

    def state(self, **overrides: object) -> dict[str, object]:
        result: dict[str, object] = {
            "dependencyParentInvalid": False,
            "waveParentInvalid": False,
            "claimPresent": False,
            "stagingEntryCount": 0,
            "finalDirectoryPresent": False,
            "successReceiptPresent": False,
            "failureReceiptPresent": False,
            "manifestPresent": False,
        }
        result.update(overrides)
        return result

    def failure(self, **overrides: object) -> runner.RunnerFailure:
        values: dict[str, object] = {
            "code": "E_GO_MOD_H1",
            "phase": "mod",
            "tuple_id": str(self.item["tupleId"]),
            "tuple_order": 1,
            "resource_kind": "mod",
            "observations": {"responseBytes": 12},
        }
        values.update(overrides)
        return runner.RunnerFailure(**values)

    def download_legacy(self) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            hard_wall_clock_request_deadline=lambda **_kwargs: nullcontext(),
            set_response_io_timeout=lambda *_args: None,
            write_all=lambda fd, payload: os.write(fd, payload),
            validate_regular_descriptor=lambda fd, *_args, **_kwargs: os.fstat(fd),
        )

    def test_01_mod_url_is_derived_from_exact_zip_suffix(self) -> None:
        self.assertEqual(
            runner.derive_mod_url(self.item),
            str(self.item["url"])[:-4] + ".mod",
        )

    def test_02_mod_url_rejects_plain_http(self) -> None:
        item = dict(self.item, url=str(self.item["url"]).replace("https:", "http:"))
        with self.assertRaises(runner.RunnerFailure):
            runner.derive_mod_url(item)

    def test_03_mod_url_rejects_query(self) -> None:
        item = dict(self.item, url=str(self.item["url"]) + "?token=no")
        with self.assertRaises(runner.RunnerFailure):
            runner.derive_mod_url(item)

    def test_04_mod_url_rejects_userinfo(self) -> None:
        item = dict(
            self.item,
            url=str(self.item["url"]).replace(
                "proxy.golang.org", "user@proxy.golang.org"
            ),
        )
        with self.assertRaises(runner.RunnerFailure):
            runner.derive_mod_url(item)

    def test_05_output_names_are_bound_to_order_and_tuple_digest(self) -> None:
        self.assertEqual(
            runner.output_names(self.item),
            ("001-" + ("a" * 20) + ".mod", "001-" + ("a" * 20) + ".zip"),
        )

    def test_06_output_names_reject_boolean_order(self) -> None:
        with self.assertRaises(runner.RunnerFailure):
            runner.output_names(dict(self.item, order=True))

    def test_07_external_mod_exact_bytes_pass(self) -> None:
        result = runner.validate_mod_bytes(self.mod, self.item)
        self.assertEqual(result["goModH1"], self.item["goModH1"])
        self.assertEqual(result["module"], self.module)

    def test_08_external_mod_quoted_module_passes(self) -> None:
        payload = f'module "{self.module}"\n'.encode()
        item = dict(self.item, goModH1=single_go_mod_h1(payload))
        self.assertEqual(
            runner.validate_mod_bytes(payload, item)["module"], self.module
        )

    def test_09_external_mod_missing_directive_is_rejected(self) -> None:
        payload = b"go 1.22\n"
        item = dict(self.item, goModH1=single_go_mod_h1(payload))
        with self.assertRaises(runner.RunnerFailure) as caught:
            runner.validate_mod_bytes(payload, item)
        self.assertEqual(caught.exception.code, "E_GO_MOD_MODULE")

    def test_10_external_mod_wrong_module_is_rejected(self) -> None:
        payload = b"module example.com/wrong\n"
        item = dict(self.item, goModH1=single_go_mod_h1(payload))
        with self.assertRaises(runner.RunnerFailure) as caught:
            runner.validate_mod_bytes(payload, item)
        self.assertEqual(caught.exception.code, "E_GO_MOD_MODULE")

    def test_11_external_mod_duplicate_directive_is_rejected(self) -> None:
        payload = self.mod + f"module {self.module}\n".encode()
        item = dict(self.item, goModH1=single_go_mod_h1(payload))
        with self.assertRaises(runner.RunnerFailure):
            runner.validate_mod_bytes(payload, item)

    def test_12_external_mod_nul_is_rejected(self) -> None:
        payload = self.mod + b"\0"
        item = dict(self.item, goModH1=single_go_mod_h1(payload))
        with self.assertRaises(runner.RunnerFailure) as caught:
            runner.validate_mod_bytes(payload, item)
        self.assertEqual(caught.exception.code, "E_GO_MOD_ENCODING")

    def test_13_external_mod_invalid_utf8_is_rejected(self) -> None:
        payload = self.mod + b"\xff"
        item = dict(self.item, goModH1=single_go_mod_h1(payload))
        with self.assertRaises(runner.RunnerFailure):
            runner.validate_mod_bytes(payload, item)

    def test_14_external_mod_h1_mismatch_is_rejected(self) -> None:
        with self.assertRaises(runner.RunnerFailure) as caught:
            runner.validate_mod_bytes(self.mod, dict(self.item, goModH1="h1:bad"))
        self.assertEqual(caught.exception.code, "E_GO_MOD_H1")

    def test_15_success_counters_are_accepted(self) -> None:
        counters = {
            "networkRequestAttemptCount": 38,
            "responseBodyCompletedCount": 38,
            "validatedAndStagedResourceCount": 38,
            "validatedModResourceCount": 19,
            "validatedZipResourceCount": 19,
            "validatedAndStagedTupleCount": 19,
        }
        runner.validate_counters(counters)

    def test_16_mod_before_zip_counter_state_is_accepted(self) -> None:
        counters = {
            "networkRequestAttemptCount": 1,
            "responseBodyCompletedCount": 1,
            "validatedAndStagedResourceCount": 1,
            "validatedModResourceCount": 1,
            "validatedZipResourceCount": 0,
            "validatedAndStagedTupleCount": 0,
        }
        runner.validate_counters(counters)

    def test_17_boolean_counter_is_rejected(self) -> None:
        counters = runner.zero_counters()
        counters["networkRequestAttemptCount"] = True
        with self.assertRaises(runner.RunnerFailure):
            runner.validate_counters(counters)

    def test_18_zip_cannot_advance_before_mod(self) -> None:
        counters = runner.zero_counters()
        counters.update(
            {
                "networkRequestAttemptCount": 1,
                "responseBodyCompletedCount": 1,
                "validatedAndStagedResourceCount": 1,
                "validatedZipResourceCount": 1,
                "validatedAndStagedTupleCount": 1,
            }
        )
        with self.assertRaises(runner.RunnerFailure):
            runner.validate_counters(counters)

    def test_19_attempt_counter_increments_before_delegate_open(self) -> None:
        counters = runner.zero_counters()
        delegate = mock.Mock()
        delegate.open.side_effect = OSError("offline")
        opener = runner.AttemptCountingOpener(delegate, counters)
        with self.assertRaises(OSError):
            opener.open(object(), timeout=1.0)
        self.assertEqual(counters["networkRequestAttemptCount"], 1)

    def test_20_mod_response_headers_pass(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = Response(url, "text/plain; charset=utf-8")
        self.assertIsNone(
            runner.validate_response_headers_v3(
                response,
                expected_url=url,
                resource_kind="mod",
                maximum_bytes=1024,
                tuple_id=str(self.item["tupleId"]),
                tuple_order=1,
            )
        )

    def test_21_zip_response_headers_pass(self) -> None:
        url = str(self.item["url"])
        response = Response(
            url, "application/zip", extra={"Content-Length": ["123"]}
        )
        self.assertEqual(
            runner.validate_response_headers_v3(
                response,
                expected_url=url,
                resource_kind="zip",
                maximum_bytes=1024,
                tuple_id=str(self.item["tupleId"]),
                tuple_order=1,
            ),
            123,
        )

    def test_22_wrong_content_type_is_rejected(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = Response(url, "text/html")
        with self.assertRaises(runner.RunnerFailure) as caught:
            runner.validate_response_headers_v3(
                response,
                expected_url=url,
                resource_kind="mod",
                maximum_bytes=1024,
                tuple_id=str(self.item["tupleId"]),
                tuple_order=1,
            )
        self.assertEqual(caught.exception.code, "E_CONTENT_TYPE")

    def test_23_redirected_response_url_is_rejected(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = Response(url + ".mirror", "text/plain")
        with self.assertRaises(runner.RunnerFailure) as caught:
            runner.validate_response_headers_v3(
                response,
                expected_url=url,
                resource_kind="mod",
                maximum_bytes=1024,
                tuple_id=str(self.item["tupleId"]),
                tuple_order=1,
            )
        self.assertEqual(caught.exception.code, "E_REDIRECT")

    def test_24_authentication_challenge_header_is_rejected(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = Response(
            url,
            "text/plain",
            extra={"WWW-Authenticate": ['Basic realm="no"']},
        )
        with self.assertRaises(runner.RunnerFailure):
            runner.validate_response_headers_v3(
                response,
                expected_url=url,
                resource_kind="mod",
                maximum_bytes=1024,
                tuple_id=str(self.item["tupleId"]),
                tuple_order=1,
            )

    def test_25_nonidentity_content_encoding_is_rejected(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = Response(
            url, "text/plain", extra={"Content-Encoding": ["gzip"]}
        )
        with self.assertRaises(runner.RunnerFailure):
            runner.validate_response_headers_v3(
                response,
                expected_url=url,
                resource_kind="mod",
                maximum_bytes=1024,
                tuple_id=str(self.item["tupleId"]),
                tuple_order=1,
            )

    def test_26_zero_content_length_is_rejected(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = Response(
            url, "text/plain", extra={"Content-Length": ["0"]}
        )
        with self.assertRaises(runner.RunnerFailure):
            runner.validate_response_headers_v3(
                response,
                expected_url=url,
                resource_kind="mod",
                maximum_bytes=1024,
                tuple_id=str(self.item["tupleId"]),
                tuple_order=1,
            )

    def test_27_safe_failure_schema_keeps_resource_context(self) -> None:
        counters = {
            "networkRequestAttemptCount": 1,
            "responseBodyCompletedCount": 1,
            "validatedAndStagedResourceCount": 0,
            "validatedModResourceCount": 0,
            "validatedZipResourceCount": 0,
            "validatedAndStagedTupleCount": 0,
        }
        permit = {
            "permitId": "permit-v3",
            "contentBinding": {"sha256": "b" * 64},
        }
        document = runner.safe_failure_document_v3(
            permit,
            self.failure(),
            counters,
            claim_sha256="c" * 64,
        )
        self.assertEqual(document["failedResourceKind"], "mod")
        self.assertEqual(document["failedTupleOrder"], 1)
        self.assertFalse(document["automaticRetryAllowed"])

    def test_28_failure_without_tuple_context_is_rejected(self) -> None:
        permit = {
            "permitId": "permit-v3",
            "contentBinding": {"sha256": "b" * 64},
        }
        with self.assertRaises(runner.RunnerFailure):
            runner.safe_failure_document_v3(
                permit,
                self.failure(tuple_id=None),
                runner.zero_counters(),
                claim_sha256="c" * 64,
            )

    def test_29_clean_state_classifies_clean(self) -> None:
        self.assertEqual(runner.classify_preflight_state(self.state()), "clean")

    def test_30_success_state_requires_all_success_artifacts(self) -> None:
        state = self.state(
            claimPresent=True,
            finalDirectoryPresent=True,
            successReceiptPresent=True,
            manifestPresent=True,
        )
        self.assertEqual(runner.classify_preflight_state(state), "success")

    def test_31_failure_state_requires_claim_and_failure_only(self) -> None:
        state = self.state(claimPresent=True, failureReceiptPresent=True)
        self.assertEqual(runner.classify_preflight_state(state), "failure")

    def test_32_partial_publication_state_is_blocked(self) -> None:
        state = self.state(claimPresent=True, finalDirectoryPresent=True)
        self.assertEqual(runner.classify_preflight_state(state), "blocked")

    def test_33_post_publish_error_is_terminal_and_nonretryable(self) -> None:
        result = runner.runner_error_document(
            runner.RunnerFailure("E_POST_PUBLISH_UNCERTAIN", "post_publish")
        )
        self.assertEqual(result["status"], "consumed_terminal_state_uncertain")
        self.assertFalse(result["automaticRetryAllowed"])

    def test_34_ordered_source_digest_changes_with_resource_order(self) -> None:
        rows = [{"resourceKind": "mod"}, {"resourceKind": "zip"}]
        digest = runner.ordered_source_set_digest_v3(rows)
        self.assertNotEqual(
            digest, runner.ordered_source_set_digest_v3(list(reversed(rows)))
        )

    def test_35_zip_without_embedded_go_mod_passes(self) -> None:
        fd, item = self.make_zip(embedded_mod=None)
        try:
            result = self.inspect_zip(fd, item)
        finally:
            os.close(fd)
        self.assertFalse(result["embeddedGoModPresent"])
        self.assertTrue(result["embeddedGoModByteParity"])

    def test_36_zip_with_matching_embedded_go_mod_passes(self) -> None:
        fd, item = self.make_zip(embedded_mod=self.mod)
        try:
            result = self.inspect_zip(fd, item)
        finally:
            os.close(fd)
        self.assertTrue(result["embeddedGoModPresent"])
        self.assertTrue(result["embeddedGoModByteParity"])

    def test_37_zip_with_mismatched_embedded_go_mod_is_rejected(self) -> None:
        wrong = f"module {self.module}\n\ngo 1.21\n".encode()
        fd, item = self.make_zip(embedded_mod=wrong)
        try:
            with self.assertRaises(runner.RunnerFailure) as caught:
                self.inspect_zip(fd, item)
        finally:
            os.close(fd)
        self.assertEqual(caught.exception.code, "E_GO_MOD_PARITY")

    def test_38_zip_module_h1_mismatch_is_rejected(self) -> None:
        fd, item = self.make_zip(
            embedded_mod=None,
            h1_override="h1:" + ("B" * 43) + "=",
        )
        try:
            with self.assertRaises(runner.RunnerFailure) as caught:
                self.inspect_zip(fd, item)
        finally:
            os.close(fd)
        self.assertEqual(caught.exception.code, "E_MODULE_H1")

    def test_39_runner_has_fixed_permit_checker_trust_root(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "script/check_p2p_nat_g2_pion_dependency_wave1_execution_permit_v3.py",
            source,
        )
        self.assertIn("permit_checker.validate_repository(ROOT)", source)
        self.assertIn("EXPECTED_PERMIT_CHECKER_RAW_SHA256", source)

    def test_40_user_authentication_is_never_a_runner_prerequisite(self) -> None:
        failure = runner.runner_error_document(
            runner.RunnerFailure("E_PERMIT_STATE", "preflight")
        )
        self.assertFalse(failure["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(failure["externalAuthenticationRequired"])
        self.assertFalse(failure["userActionRequired"])

    def test_41_mod_download_streams_exact_body_and_hash(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = BodyResponse(
            url, "text/plain; charset=utf-8", self.mod, declared_length=len(self.mod)
        )
        opener = CapturingOpener(response)
        path = self.root / "download.mod"
        path.touch(mode=0o600)
        os.chmod(path, 0o600)
        fd = os.open(path, os.O_RDWR)
        try:
            result = runner.download_resource_once(
                self.download_legacy(),
                opener,
                self.item,
                fd,
                resource_kind="mod",
                url=url,
                maximum_bytes=1024,
                aggregate_kind_before=0,
                maximum_aggregate_kind_bytes=2048,
                aggregate_total_before=0,
                per_request_timeout_seconds=10.0,
                wave_deadline=runner.time.monotonic() + 20.0,
            )
            os.lseek(fd, 0, os.SEEK_SET)
            self.assertEqual(os.read(fd, 1024), self.mod)
        finally:
            os.close(fd)
        self.assertEqual(result["rawSha256"], hashlib.sha256(self.mod).hexdigest())
        self.assertEqual(result["rawByteSize"], len(self.mod))

    def test_42_download_rejects_declared_length_mismatch(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = BodyResponse(
            url, "text/plain", self.mod, declared_length=len(self.mod) + 1
        )
        path = self.root / "length.mod"
        path.touch(mode=0o600)
        os.chmod(path, 0o600)
        fd = os.open(path, os.O_RDWR)
        try:
            with self.assertRaises(runner.RunnerFailure) as caught:
                runner.download_resource_once(
                    self.download_legacy(),
                    CapturingOpener(response),
                    self.item,
                    fd,
                    resource_kind="mod",
                    url=url,
                    maximum_bytes=1024,
                    aggregate_kind_before=0,
                    maximum_aggregate_kind_bytes=2048,
                    aggregate_total_before=0,
                    per_request_timeout_seconds=10.0,
                    wave_deadline=runner.time.monotonic() + 20.0,
                )
        finally:
            os.close(fd)
        self.assertEqual(caught.exception.code, "E_CONTENT_LENGTH_MISMATCH")

    def test_43_download_rejects_per_resource_limit(self) -> None:
        url = runner.derive_mod_url(self.item)
        body = b"x" * 17
        response = BodyResponse(url, "text/plain", body)
        path = self.root / "oversize.mod"
        path.touch(mode=0o600)
        os.chmod(path, 0o600)
        fd = os.open(path, os.O_RDWR)
        try:
            with self.assertRaises(runner.RunnerFailure) as caught:
                runner.download_resource_once(
                    self.download_legacy(),
                    CapturingOpener(response),
                    self.item,
                    fd,
                    resource_kind="mod",
                    url=url,
                    maximum_bytes=16,
                    aggregate_kind_before=0,
                    maximum_aggregate_kind_bytes=2048,
                    aggregate_total_before=0,
                    per_request_timeout_seconds=10.0,
                    wave_deadline=runner.time.monotonic() + 20.0,
                )
        finally:
            os.close(fd)
        self.assertEqual(caught.exception.code, "E_RESPONSE_TOO_LARGE")

    def test_44_download_request_has_no_credentials_or_cookies(self) -> None:
        url = runner.derive_mod_url(self.item)
        opener = CapturingOpener(BodyResponse(url, "text/plain", self.mod))
        path = self.root / "headers.mod"
        path.touch(mode=0o600)
        os.chmod(path, 0o600)
        fd = os.open(path, os.O_RDWR)
        try:
            runner.download_resource_once(
                self.download_legacy(),
                opener,
                self.item,
                fd,
                resource_kind="mod",
                url=url,
                maximum_bytes=1024,
                aggregate_kind_before=0,
                maximum_aggregate_kind_bytes=2048,
                aggregate_total_before=0,
                per_request_timeout_seconds=10.0,
                wave_deadline=runner.time.monotonic() + 20.0,
            )
        finally:
            os.close(fd)
        self.assertEqual(opener.request.get_method(), "GET")
        headers = {key.lower(): value for key, value in opener.request.header_items()}
        self.assertEqual(headers["accept"], "text/plain")
        self.assertEqual(headers["accept-encoding"], "identity")
        self.assertNotIn("authorization", headers)
        self.assertNotIn("proxy-authorization", headers)
        self.assertNotIn("cookie", headers)

    def test_45_empty_response_is_rejected(self) -> None:
        url = runner.derive_mod_url(self.item)
        response = BodyResponse(url, "text/plain", b"")
        path = self.root / "empty.mod"
        path.touch(mode=0o600)
        os.chmod(path, 0o600)
        fd = os.open(path, os.O_RDWR)
        try:
            with self.assertRaises(runner.RunnerFailure) as caught:
                runner.download_resource_once(
                    self.download_legacy(),
                    CapturingOpener(response),
                    self.item,
                    fd,
                    resource_kind="mod",
                    url=url,
                    maximum_bytes=1024,
                    aggregate_kind_before=0,
                    maximum_aggregate_kind_bytes=2048,
                    aggregate_total_before=0,
                    per_request_timeout_seconds=10.0,
                    wave_deadline=runner.time.monotonic() + 20.0,
                )
        finally:
            os.close(fd)
        self.assertEqual(caught.exception.code, "E_EMPTY_RESPONSE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
