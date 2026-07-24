#!/usr/bin/env python3
"""Offline tests for the G2 Pion dependency wave-one v2 runner."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPT_DIR / "acquire_p2p_nat_g2_pion_dependency_wave1_v2_once.py"
SPEC = importlib.util.spec_from_file_location("wave1_v2_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v2 runner")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

LEGACY_PATH = SCRIPT_DIR / "acquire_p2p_nat_g2_pion_dependency_wave1_once.py"
LEGACY_SPEC = importlib.util.spec_from_file_location(
    "wave1_v1_legacy_for_v2_tests",
    LEGACY_PATH,
)
if LEGACY_SPEC is None or LEGACY_SPEC.loader is None:
    raise RuntimeError("cannot load v1 runner")
legacy = importlib.util.module_from_spec(LEGACY_SPEC)
LEGACY_SPEC.loader.exec_module(legacy)
runner.configure_legacy(legacy)

SOURCE_DECISION_PATH = (
    SCRIPT_DIR.parent
    / "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
SOURCE_DECISION = json.loads(SOURCE_DECISION_PATH.read_text(encoding="utf-8"))


class DependencyWaveOneV2RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.limits = dict(SOURCE_DECISION["resourceLimits"])
        self.module = "example.com/aetherlink-test"
        self.version = "v1.0.0"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_zip(
        self,
        entries: list[tuple[str, bytes]],
        *,
        module_h1_override: str | None = None,
    ) -> tuple[int, dict[str, object]]:
        prefix = f"{self.module}@{self.version}/"
        path = self.root / "module.zip"
        rows: list[tuple[str, str]] = []
        with zipfile.ZipFile(
            path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            go_mod = f"module {self.module}\n\ngo 1.22\n".encode("utf-8")
            all_entries = [("go.mod", go_mod)] + entries
            for relative, payload in all_entries:
                name = prefix + relative
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = 0o100600 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, payload)
                rows.append((name, hashlib.sha256(payload).hexdigest()))
        os.chmod(path, 0o600)
        fd = os.open(path, os.O_RDWR)
        item: dict[str, object] = {
            "order": 2,
            "tupleId": "wave1-002-test",
            "module": self.module,
            "version": self.version,
            "url": "https://proxy.golang.org/example.com/@v/v1.0.0.zip",
            "outputPath": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-1/accepted/002.zip"
            ),
            "moduleZipH1": module_h1_override or legacy.dirhash_h1(rows),
            "goModH1": legacy.single_go_mod_h1(
                f"module {self.module}\n\ngo 1.22\n".encode("utf-8")
            ),
        }
        return fd, item

    def inspect(
        self,
        fd: int,
        item: dict[str, object],
        *,
        limits: dict[str, int] | None = None,
        aggregate_uncompressed_before: int = 0,
    ) -> dict[str, object]:
        return runner.inspect_module_zip_v2(
            legacy,
            fd,
            item,
            limits or self.limits,
            aggregate_entries_before=0,
            aggregate_uncompressed_before=aggregate_uncompressed_before,
        )

    def test_01_ratio_above_200_is_non_gating_and_recorded(self) -> None:
        fd, item = self.make_zip([("high-ratio.bin", b"\0" * 1_000_000)])
        try:
            result = self.inspect(fd, item)
        finally:
            os.close(fd)
        telemetry = result["compressionTelemetry"]
        self.assertTrue(telemetry["maximumRatioExceededHistoricalV1Limit"])
        self.assertGreater(
            telemetry["maximumRatioEntryUncompressedBytes"],
            telemetry["maximumRatioEntryCompressedBytes"] * 200,
        )
        self.assertFalse(telemetry["floatingPointRatioUsed"])

    def test_02_maximum_ratio_uses_exact_cross_product_and_first_tie(self) -> None:
        fd, item = self.make_zip(
            [
                ("first.bin", b"A" * 40_000),
                ("second.bin", b"B" * 80_000),
                ("third.bin", b"A" * 40_000),
            ]
        )
        try:
            telemetry = runner.collect_compression_telemetry(legacy, fd, item)
            with os.fdopen(os.dup(fd), "rb") as archive_file:
                with zipfile.ZipFile(archive_file) as archive:
                    infos = archive.infolist()
        finally:
            os.close(fd)
        selected = infos[telemetry["maximumRatioEntryOrdinal"] - 1]
        for candidate in infos:
            if candidate.file_size and candidate.compress_size:
                self.assertGreaterEqual(
                    selected.file_size * candidate.compress_size,
                    candidate.file_size * selected.compress_size,
                )
        source = inspect.getsource(runner.collect_compression_telemetry)
        tree = ast.parse(source)
        self.assertFalse(
            any(
                isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                for node in ast.walk(tree)
            )
        )

    def test_03_empty_entry_is_not_a_ratio_candidate(self) -> None:
        fd, item = self.make_zip(
            [("empty.bin", b""), ("payload.bin", b"payload")]
        )
        try:
            telemetry = runner.collect_compression_telemetry(legacy, fd, item)
            with os.fdopen(os.dup(fd), "rb") as archive_file:
                with zipfile.ZipFile(archive_file) as archive:
                    selected = archive.infolist()[
                        telemetry["maximumRatioEntryOrdinal"] - 1
                    ]
        finally:
            os.close(fd)
        self.assertGreater(selected.file_size, 0)
        self.assertGreater(selected.compress_size, 0)

    def test_04_nonempty_zero_compressed_size_is_rejected_with_context(self) -> None:
        path = self.root / "placeholder.zip"
        path.write_bytes(b"x")
        os.chmod(path, 0o600)
        fd = os.open(path, os.O_RDWR)

        class FakeArchive:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def infolist(self):
                return [
                    types.SimpleNamespace(file_size=1, compress_size=0)
                ]

        item = {"tupleId": "tuple-zero", "order": 7}
        try:
            with mock.patch.object(runner.zipfile, "ZipFile", return_value=FakeArchive()):
                with self.assertRaises(runner.RunnerFailure) as context:
                    runner.collect_compression_telemetry(legacy, fd, item)
        finally:
            os.close(fd)
        self.assertEqual(context.exception.code, "E_ZIP_COMPRESSED_SIZE")
        self.assertEqual(context.exception.tuple_id, "tuple-zero")
        self.assertEqual(context.exception.tuple_order, 7)

    def test_05_single_file_absolute_limit_still_rejects(self) -> None:
        fd, item = self.make_zip([("large.bin", b"x" * 4096)])
        limits = dict(self.limits)
        limits["maximumSingleFileBytes"] = 1024
        try:
            with self.assertRaises(runner.RunnerFailure) as context:
                self.inspect(fd, item, limits=limits)
        finally:
            os.close(fd)
        self.assertEqual(context.exception.code, "E_ZIP_FILE_SIZE")
        self.assertEqual(context.exception.tuple_id, item["tupleId"])

    def test_06_archive_uncompressed_limit_still_rejects(self) -> None:
        fd, item = self.make_zip([("large.bin", b"x" * 4096)])
        limits = dict(self.limits)
        limits["maximumUncompressedBytesPerArchive"] = 1024
        try:
            with self.assertRaises(runner.RunnerFailure) as context:
                self.inspect(fd, item, limits=limits)
        finally:
            os.close(fd)
        self.assertEqual(context.exception.code, "E_ZIP_UNCOMPRESSED")

    def test_07_aggregate_uncompressed_limit_still_rejects(self) -> None:
        fd, item = self.make_zip([("payload.bin", b"x" * 4096)])
        limits = dict(self.limits)
        limits["maximumAggregateUncompressedBytes"] = 5000
        try:
            with self.assertRaises(runner.RunnerFailure) as context:
                self.inspect(
                    fd,
                    item,
                    limits=limits,
                    aggregate_uncompressed_before=4096,
                )
        finally:
            os.close(fd)
        self.assertEqual(context.exception.code, "E_AGGREGATE_UNCOMPRESSED")

    def test_08_h1_failure_keeps_tuple_context(self) -> None:
        fd, item = self.make_zip(
            [("payload.bin", b"payload")],
            module_h1_override="h1:" + ("A" * 44),
        )
        try:
            with self.assertRaises(runner.RunnerFailure) as context:
                self.inspect(fd, item)
        finally:
            os.close(fd)
        self.assertEqual(context.exception.code, "E_MODULE_H1")
        self.assertEqual(context.exception.tuple_id, item["tupleId"])
        self.assertEqual(context.exception.tuple_order, item["order"])

    def test_09_safe_numeric_observation_allowlist_is_strict(self) -> None:
        result = runner.bounded_observations(
            {
                "httpStatus": 404,
                "responseBytes": 7,
                "entryOrdinal": 3,
                "entryCompressedBytes": True,
                "entryUncompressedBytes": -1,
                "ratio": 201.5,
                "entryName": 9,
            }
        )
        self.assertEqual(
            result,
            {"httpStatus": 404, "responseBytes": 7, "entryOrdinal": 3},
        )

    def test_10_counter_invariant_accepts_monotonic_split(self) -> None:
        for values in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 2, 1)):
            runner.validate_counters(
                {
                    "networkRequestAttemptCount": values[0],
                    "responseBodyCompletedCount": values[1],
                    "validatedAndStagedTupleCount": values[2],
                }
            )

    def test_11_counter_invariant_rejects_order_type_and_bounds(self) -> None:
        invalid = (
            (0, 1, 0),
            (1, 0, 1),
            (20, 19, 19),
            (True, 0, 0),
            (-1, 0, 0),
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(runner.RunnerFailure):
                    runner.validate_counters(
                        {
                            "networkRequestAttemptCount": values[0],
                            "responseBodyCompletedCount": values[1],
                            "validatedAndStagedTupleCount": values[2],
                        }
                    )

    def test_12_attempt_counter_increments_at_delegate_open(self) -> None:
        counters = {
            "networkRequestAttemptCount": 0,
            "responseBodyCompletedCount": 0,
            "validatedAndStagedTupleCount": 0,
        }
        delegate = mock.Mock()
        delegate.open.return_value = object()
        opener = runner.AttemptCountingOpener(delegate, counters)
        request = object()
        result = opener.open(request, timeout=1.5)
        self.assertIs(result, delegate.open.return_value)
        self.assertEqual(counters["networkRequestAttemptCount"], 1)
        delegate.open.assert_called_once_with(request, timeout=1.5)

    def test_13_open_failure_is_counted_but_response_is_not(self) -> None:
        counters = {
            "networkRequestAttemptCount": 0,
            "responseBodyCompletedCount": 0,
            "validatedAndStagedTupleCount": 0,
        }
        delegate = mock.Mock()
        delegate.open.side_effect = OSError("offline")
        opener = runner.AttemptCountingOpener(delegate, counters)
        with self.assertRaises(OSError):
            opener.open(object(), timeout=1.0)
        self.assertEqual(
            counters,
            {
                "networkRequestAttemptCount": 1,
                "responseBodyCompletedCount": 0,
                "validatedAndStagedTupleCount": 0,
            },
        )

    def test_14_failure_schema_uses_only_split_counters(self) -> None:
        permit = {
            "permitId": "permit-v2",
            "contentBinding": {"sha256": "a" * 64},
            "recoveryBinding": {"contentSha256": "b" * 64},
        }
        counters = {
            "networkRequestAttemptCount": 2,
            "responseBodyCompletedCount": 2,
            "validatedAndStagedTupleCount": 1,
        }
        failure = runner.RunnerFailure(
            "E_MODULE_H1",
            "zip",
            tuple_id="tuple-2",
            tuple_order=2,
            observations={"entryOrdinal": 4, "entryName": 1},
        )
        document = runner.safe_failure_document_v2(
            permit,
            failure,
            counters,
            claim_sha256="c" * 64,
            final_set_published=False,
        )
        self.assertNotIn("completed" + "RequestCount", document)
        self.assertEqual(document["failedTupleId"], "tuple-2")
        self.assertEqual(document["failedTupleOrder"], 2)
        self.assertEqual(document["safeNumericObservations"], {"entryOrdinal": 4})
        self.assertFalse(document["externalAuthenticationRequired"])

    def state(self, **updates: object) -> dict[str, object]:
        value: dict[str, object] = {
            "claimPresent": False,
            "stagingEntryCount": 0,
            "finalDirectoryPresent": False,
            "successReceiptPresent": False,
            "failureReceiptPresent": False,
            "manifestPresent": False,
            "dependencyParentInvalid": False,
            "waveParentInvalid": False,
        }
        value.update(updates)
        return value

    def test_15_clean_preflight_state_is_classified(self) -> None:
        self.assertEqual(runner.classify_preflight_state(self.state()), "clean")

    def test_16_complete_success_preflight_state_is_classified(self) -> None:
        self.assertEqual(
            runner.classify_preflight_state(
                self.state(
                    claimPresent=True,
                    finalDirectoryPresent=True,
                    successReceiptPresent=True,
                    manifestPresent=True,
                )
            ),
            "success",
        )

    def test_17_terminal_failure_preflight_state_is_classified(self) -> None:
        self.assertEqual(
            runner.classify_preflight_state(
                self.state(claimPresent=True, failureReceiptPresent=True)
            ),
            "failure",
        )

    def test_18_partial_mixed_and_invalid_states_are_blocked(self) -> None:
        states = (
            self.state(claimPresent=True),
            self.state(stagingEntryCount=1),
            self.state(finalDirectoryPresent=True),
            self.state(successReceiptPresent=True),
            self.state(manifestPresent=True),
            self.state(
                claimPresent=True,
                failureReceiptPresent=True,
                successReceiptPresent=True,
            ),
            self.state(dependencyParentInvalid=True),
            self.state(waveParentInvalid=True),
        )
        for state in states:
            with self.subTest(state=state):
                self.assertEqual(
                    runner.classify_preflight_state(state),
                    "blocked",
                )

    def permit(self) -> dict[str, object]:
        return {
            "permitId": "permit-v2",
            "contentBinding": {"sha256": "a" * 64},
            "recoveryBinding": {"contentSha256": "b" * 64},
        }

    def make_success_fixture(
        self,
    ) -> tuple[
        dict[str, object],
        bytes,
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        final_directory = self.root / runner.FINAL_DIRECTORY_PATH
        final_directory.mkdir(parents=True)
        os.chmod(final_directory.parent, 0o700)
        os.chmod(final_directory, 0o700)
        decision: dict[str, object] = {
            "decisionId": "fixture-decision-v1",
            "contentBinding": {"sha256": "d" * 64},
            "wave": {"tuples": []},
        }
        sources: list[dict[str, object]] = []
        aggregate_bytes = 0
        aggregate_entries = 0
        aggregate_uncompressed = 0
        exceeded_count = 0
        for order in range(1, 20):
            module = f"example.com/aetherlink-fixture-{order:03d}"
            version = "v1.0.0"
            prefix = f"{module}@{version}/"
            go_mod = f"module {module}\n\ngo 1.22\n".encode("utf-8")
            payload = f"archive-{order:03d}".encode("ascii")
            name = f"{order:03d}-fixture.zip"
            output_path = (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                f"wave-1/accepted/{name}"
            )
            archive_rows = [
                (
                    prefix + "go.mod",
                    hashlib.sha256(go_mod).hexdigest(),
                ),
                (
                    prefix + "payload.txt",
                    hashlib.sha256(payload).hexdigest(),
                ),
            ]
            item = {
                "order": order,
                "tupleId": f"fixture-wave1-{order:03d}",
                "module": module,
                "version": version,
                "url": (
                    "https://proxy.golang.org/"
                    f"{module}/@v/{version}.zip"
                ),
                "outputPath": output_path,
                "moduleZipH1": legacy.dirhash_h1(archive_rows),
                "goModH1": legacy.single_go_mod_h1(go_mod),
            }
            decision["wave"]["tuples"].append(item)
            path = final_directory / name
            with zipfile.ZipFile(
                path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for relative, body in (
                    ("go.mod", go_mod),
                    ("payload.txt", payload),
                ):
                    info = zipfile.ZipInfo(prefix + relative)
                    info.create_system = 3
                    info.external_attr = 0o100600 << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, body)
            os.chmod(path, 0o600)
            fd = os.open(path, os.O_RDWR)
            try:
                observed = runner.inspect_module_zip_v2(
                    legacy,
                    fd,
                    item,
                    self.limits,
                    aggregate_entries_before=aggregate_entries,
                    aggregate_uncompressed_before=aggregate_uncompressed,
                )
            finally:
                os.close(fd)
            raw = path.read_bytes()
            size = len(raw)
            aggregate_bytes += size
            aggregate_entries += observed["entryCount"]
            aggregate_uncompressed += observed[
                "uncompressedByteCount"
            ]
            exceeded_count += int(
                observed["compressionTelemetry"][
                    "maximumRatioExceededHistoricalV1Limit"
                ]
            )
            sources.append(
                {
                    "order": item["order"],
                    "tupleId": item["tupleId"],
                    "module": item["module"],
                    "version": item["version"],
                    "url": item["url"],
                    "outputFileName": name,
                    "rawByteSize": size,
                    "rawSha256": hashlib.sha256(raw).hexdigest(),
                    "moduleZipH1": item["moduleZipH1"],
                    "goModH1": item["goModH1"],
                    "entryCount": observed["entryCount"],
                    "uncompressedByteCount": observed[
                        "uncompressedByteCount"
                    ],
                    "modulePrefix": observed["modulePrefix"],
                    "compressionTelemetry": observed[
                        "compressionTelemetry"
                    ],
                    "mode": "0600",
                    "linkCount": 1,
                }
            )
        permit = self.permit()
        claim_sha256 = "c" * 64
        receipt: dict[str, object] = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v2-acquisition-receipt"
            ),
            "schemaVersion": "2.0",
            "status": "acquired_pending_independent_readback",
            "result": (
                "fresh_exact_19_dependency_module_zip_set_acquired_hash_"
                "verified_and_ratio_telemetry_recorded"
            ),
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "recoveryContentSha256": permit["recoveryBinding"][
                "contentSha256"
            ],
            "decisionId": decision["decisionId"],
            "decisionContentSha256": decision["contentBinding"][
                "sha256"
            ],
            "claimRawSha256": claim_sha256,
            "networkRequestAttemptCount": 19,
            "responseBodyCompletedCount": 19,
            "validatedAndStagedTupleCount": 19,
            "acceptedArtifactCount": 19,
            "aggregateRawByteSize": aggregate_bytes,
            "aggregateEntryCount": aggregate_entries,
            "aggregateUncompressedByteCount": aggregate_uncompressed,
            "archiveCountExceedingHistoricalV1Ratio": exceeded_count,
            "orderedSourceSetSha256": runner.ordered_source_set_digest_v2(
                sources
            ),
            "sources": sources,
            "compressionRatioPolicy": "non_gating_bounded_telemetry",
            "legacyCompletedRequestCountForbidden": True,
            "independentReadbackPassed": False,
            "dependencySourceReviewed": False,
            "dependencyClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v2_independent_readback",
        }
        receipt_raw = runner.canonical_json_bytes(receipt)
        manifest: dict[str, object] = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave1-v2-acquisition-manifest"
            ),
            "schemaVersion": "2.0",
            "status": (
                "wave1_v2_acquisition_publication_complete_pending_"
                "independent_readback"
            ),
            "result": (
                "receipt_and_fresh_exact_19_zip_final_set_published_"
                "manifest_written_last"
            ),
            "permitId": permit["permitId"],
            "permitContentSha256": permit["contentBinding"]["sha256"],
            "successReceiptPath": runner.SUCCESS_RECEIPT_PATH,
            "successReceiptRawSha256": hashlib.sha256(
                receipt_raw
            ).hexdigest(),
            "finalDirectoryPath": runner.FINAL_DIRECTORY_PATH,
            "networkRequestAttemptCount": 19,
            "responseBodyCompletedCount": 19,
            "validatedAndStagedTupleCount": 19,
            "acceptedArtifactCount": 19,
            "orderedSourceSetSha256": receipt["orderedSourceSetSha256"],
            "manifestWrittenLast": True,
            "independentReadbackPassed": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_wave1_v2_independent_readback",
        }
        return receipt, receipt_raw, manifest, permit, decision

    def claim(self) -> dict[str, object]:
        return {
            "claimType": (
                "aetherlink.g2-pion-dependency-wave1-v2-one-use-claim"
            ),
            "schemaVersion": "2.0",
            "permitId": "permit-v2",
            "permitContentSha256": "a" * 64,
            "recoveryContentSha256": "b" * 64,
            "createdAt": "2026-07-24T00:00:00Z",
            "rule": (
                "v2_claim_persists_after_any_network_attempt_and_blocks_retry"
            ),
            "v1ArtifactReuseAllowed": False,
        }

    def test_19_claim_contract_accepts_exact_and_rejects_reuse(self) -> None:
        claim = self.claim()
        runner.validate_claim_document(claim, self.permit())
        claim["v1ArtifactReuseAllowed"] = True
        with self.assertRaises(runner.RunnerFailure) as context:
            runner.validate_claim_document(claim, self.permit())
        self.assertEqual(context.exception.code, "E_CLAIM_STATE")

    def test_20_legacy_failure_is_rewrapped_with_tuple_and_safe_values(self) -> None:
        error = legacy.AcquisitionFailure(
            "E_ZIP_FILE_SIZE",
            "zip",
            observations={
                "responseBytes": 4,
                "entryCompressedBytes": True,
                "unknown": 9,
            },
        )
        converted = runner.convert_legacy_failure(
            legacy,
            error,
            tuple_id="tuple-9",
            tuple_order=9,
            extra_observations={"entryOrdinal": 2},
        )
        self.assertEqual(converted.tuple_id, "tuple-9")
        self.assertEqual(converted.tuple_order, 9)
        self.assertEqual(
            converted.observations,
            {"responseBytes": 4, "entryOrdinal": 2},
        )

    def test_21_failure_validation_rejects_forbidden_extra_field(self) -> None:
        item = SOURCE_DECISION["wave"]["tuples"][1]
        document = runner.safe_failure_document_v2(
            self.permit(),
            runner.RunnerFailure(
                "E_MODULE_H1",
                "zip",
                tuple_id=item["tupleId"],
                tuple_order=item["order"],
            ),
            {
                "networkRequestAttemptCount": 2,
                "responseBodyCompletedCount": 2,
                "validatedAndStagedTupleCount": 1,
            },
            claim_sha256="c" * 64,
            final_set_published=False,
        )
        runner.validate_failure_document(
            document,
            self.permit(),
            "c" * 64,
            SOURCE_DECISION,
        )
        document["rawResponseBody"] = "forbidden"
        with self.assertRaises(runner.RunnerFailure) as context:
            runner.validate_failure_document(
                document,
                self.permit(),
                "c" * 64,
                SOURCE_DECISION,
            )
        self.assertEqual(context.exception.code, "E_FAILURE_STATE")

    def test_22_failure_validation_rejects_unbounded_values(self) -> None:
        item = SOURCE_DECISION["wave"]["tuples"][1]
        baseline = runner.safe_failure_document_v2(
            self.permit(),
            runner.RunnerFailure(
                "E_MODULE_H1",
                "zip",
                tuple_id=item["tupleId"],
                tuple_order=item["order"],
            ),
            {
                "networkRequestAttemptCount": 2,
                "responseBodyCompletedCount": 2,
                "validatedAndStagedTupleCount": 1,
            },
            claim_sha256="c" * 64,
            final_set_published=False,
        )
        mutations = (
            {"failureCode": "E_ARBITRARY"},
            {"failedTupleId": None, "failedTupleOrder": None},
            {"safeNumericObservations": {"rawHeaders": 1}},
            {"safeNumericObservations": {"responseBytes": True}},
            {"acceptedArtifactCount": False},
            {
                "safeNumericObservations": {
                    "networkRequestAttemptCount": 1
                }
            },
            {"phase": "publication"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                document = dict(baseline)
                document.update(mutation)
                with self.assertRaises(runner.RunnerFailure):
                    runner.validate_failure_document(
                        document,
                        self.permit(),
                        "c" * 64,
                        SOURCE_DECISION,
                    )

    def test_23_success_schema_and_inventory_accept_exact_fixture(self) -> None:
        receipt, receipt_raw, manifest, permit, decision = (
            self.make_success_fixture()
        )
        root_fd = os.open(self.root, legacy.directory_open_flags())
        try:
            runner.validate_success_documents(
                legacy,
                root_fd,
                receipt,
                receipt_raw,
                manifest,
                permit,
                "c" * 64,
                decision,
                self.limits,
            )
        finally:
            os.close(root_fd)

    def test_24_success_schema_rejects_extra_and_empty_rows(self) -> None:
        receipt, receipt_raw, manifest, permit, decision = (
            self.make_success_fixture()
        )
        mutations = []
        extra_receipt = copy.deepcopy(receipt)
        extra_receipt["rawHeaders"] = {}
        mutations.append((extra_receipt, manifest))
        empty_source = copy.deepcopy(receipt)
        empty_source["sources"][0] = {}
        mutations.append((empty_source, manifest))
        type_confused_source = copy.deepcopy(receipt)
        type_confused_source["sources"][0]["linkCount"] = True
        mutations.append((type_confused_source, manifest))
        invalid_prefix = copy.deepcopy(receipt)
        invalid_prefix["sources"][0]["modulePrefix"] = "/"
        mutations.append((invalid_prefix, manifest))
        type_confused_aggregate = copy.deepcopy(receipt)
        type_confused_aggregate[
            "archiveCountExceedingHistoricalV1Ratio"
        ] = False
        mutations.append((type_confused_aggregate, manifest))
        extra_manifest = copy.deepcopy(manifest)
        extra_manifest["rawResponseBody"] = ""
        mutations.append((receipt, extra_manifest))
        root_fd = os.open(self.root, legacy.directory_open_flags())
        try:
            for candidate_receipt, candidate_manifest in mutations:
                with self.subTest(
                    receipt_keys=len(candidate_receipt),
                    manifest_keys=len(candidate_manifest),
                ):
                    candidate_raw = runner.canonical_json_bytes(
                        candidate_receipt
                    )
                    candidate_manifest = copy.deepcopy(candidate_manifest)
                    candidate_manifest["successReceiptRawSha256"] = (
                        hashlib.sha256(candidate_raw).hexdigest()
                    )
                    with self.assertRaises(runner.RunnerFailure):
                        runner.validate_success_documents(
                            legacy,
                            root_fd,
                            candidate_receipt,
                            candidate_raw,
                            candidate_manifest,
                            permit,
                            "c" * 64,
                            decision,
                            self.limits,
                        )
        finally:
            os.close(root_fd)

    def test_25_success_inventory_rejects_tampered_file(self) -> None:
        receipt, receipt_raw, manifest, permit, decision = (
            self.make_success_fixture()
        )
        first_name = receipt["sources"][0]["outputFileName"]
        path = self.root / runner.FINAL_DIRECTORY_PATH / first_name
        path.write_bytes(b"tampered-archive")
        os.chmod(path, 0o600)
        root_fd = os.open(self.root, legacy.directory_open_flags())
        try:
            with self.assertRaises(runner.RunnerFailure) as context:
                runner.validate_success_documents(
                    legacy,
                    root_fd,
                    receipt,
                    receipt_raw,
                    manifest,
                    permit,
                    "c" * 64,
                    decision,
                    self.limits,
                )
        finally:
            os.close(root_fd)
        self.assertEqual(context.exception.code, "E_OUTPUT_IDENTITY")

    def test_26_fchmod_failure_keeps_tuple_context(self) -> None:
        with mock.patch.object(runner.os, "fchmod", side_effect=OSError):
            with self.assertRaises(runner.RunnerFailure) as context:
                runner.enforce_download_file_mode(3, "tuple-3", 3)
        self.assertEqual(context.exception.code, "E_FILESYSTEM_MODE")
        self.assertEqual(context.exception.tuple_id, "tuple-3")
        self.assertEqual(context.exception.tuple_order, 3)

    def test_27_post_publish_error_is_explicitly_terminal(self) -> None:
        document = runner.runner_error_document(
            runner.RunnerFailure(
                "E_POST_PUBLISH_UNCERTAIN",
                "post_publish",
                observations={
                    "networkRequestAttemptCount": 19,
                    "responseBodyCompletedCount": 19,
                    "validatedAndStagedTupleCount": 19,
                },
            )
        )
        self.assertEqual(
            document["status"],
            "consumed_terminal_state_uncertain",
        )
        self.assertEqual(
            document["permitConsumptionState"],
            "consumed_terminal_state_uncertain",
        )
        self.assertFalse(document["automaticRetryAllowed"])
        self.assertEqual(
            document["nextAction"],
            "inspect_v2_terminal_state_without_retry",
        )

    def test_28_failure_preflight_cannot_pass_the_gate(self) -> None:
        self.assertTrue(runner.preflight_validation_passed("clean"))
        self.assertTrue(runner.preflight_validation_passed("success"))
        self.assertFalse(runner.preflight_validation_passed("failure"))
        self.assertFalse(runner.preflight_validation_passed("blocked"))


if __name__ == "__main__":
    unittest.main()
