#!/usr/bin/env python3
"""Offline regression tests for the wave-two one-use acquisition runner."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT / "script/acquire_p2p_nat_g2_pion_dependency_wave2_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location("wave2_runner_tests_target", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
COMMON = RUNNER.COMMON


class DelegateFailure:
    def open(self, request, *, timeout):
        del request, timeout
        raise OSError("synthetic")


class FakeLegacy:
    def create_exclusive_file(self, parent_fd, name, payload, *, maximum_bytes):
        del parent_fd
        self.name = name
        self.payload = payload
        self.maximum_bytes = maximum_bytes
        return COMMON.sha256_bytes(payload)


class WaveTwoRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bindings = COMMON.decision_bindings() + COMMON.primitive_bindings()
        with COMMON.HeldInputSet(ROOT, bindings) as inputs:
            cls.decision = COMMON.load_decision(
                inputs,
                ROOT,
                require_empty_namespace=True,
            )
            cls.items = COMMON.adapt_tuples(cls.decision)
            cls.legacy, cls.core = COMMON.configure_primitives(inputs, ROOT)

    def readback_documents(self):
        aggregate = {
            "aggregateModRawByteSize": 101,
            "aggregateZipRawByteSize": 202,
            "aggregateRawByteSize": 303,
            "aggregateEntryCount": 404,
            "aggregateUncompressedByteCount": 505,
        }
        acquisition_receipt = {
            "claimRawSha256": "a" * 64,
            "orderedSourceSetSha256": "b" * 64,
            **aggregate,
        }
        acquisition_receipt_raw = COMMON.canonical_json_bytes(
            acquisition_receipt
        )
        acquisition_manifest = {
            "orderedSourceSetSha256": "b" * 64,
        }
        acquisition_manifest_raw = COMMON.canonical_json_bytes(
            acquisition_manifest
        )
        readback = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-"
                "independent-readback-receipt"
            ),
            "schemaVersion": "1.0",
            "status": "wave2_v1_independent_readback_complete",
            "result": (
                "exact_30_retained_resources_reopened_three_times_and_h1_"
                "verified"
            ),
            "permitId": RUNNER.EXPECTED_PERMIT_ID,
            "decisionId": self.decision["decisionId"],
            "claimRawSha256": "a" * 64,
            "acquisitionReceiptRawSha256": COMMON.sha256_bytes(
                acquisition_receipt_raw
            ),
            "acquisitionManifestRawSha256": COMMON.sha256_bytes(
                acquisition_manifest_raw
            ),
            "orderedSourceSetSha256": "b" * 64,
            **aggregate,
            "resourceCount": 30,
            "tupleCount": 15,
            "resourceIdentitySetSha256": "c" * 64,
            "stableReadPassCount": 3,
            "networkUsed": False,
            "sourceExtractionUsed": False,
            "sourceExecutionUsed": False,
            "freshChecksumDatabaseProof": False,
            "dependencyFixedPointReached": False,
            "dependencySourceReviewed": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "publish_wave2_v1_readback_manifest_then_rerun_"
                "combined_fixed_point_graph"
            ),
            "independentReadbackPassed": True,
        }
        readback_raw = COMMON.canonical_json_bytes(readback)
        readback_manifest = {
            "documentType": (
                "aetherlink.g2-pion-dependency-wave2-v1-"
                "independent-readback-manifest"
            ),
            "schemaVersion": "1.0",
            "status": "wave2_v1_independent_readback_published",
            "result": "readback_receipt_published_then_manifest_written_last",
            "permitId": RUNNER.EXPECTED_PERMIT_ID,
            "decisionId": self.decision["decisionId"],
            "readbackReceiptPath": COMMON.READBACK_RECEIPT_PATH,
            "readbackReceiptRawSha256": COMMON.sha256_bytes(readback_raw),
            "acquisitionManifestPath": COMMON.MANIFEST_PATH,
            "acquisitionManifestRawSha256": COMMON.sha256_bytes(
                acquisition_manifest_raw
            ),
            "resourceCount": 30,
            "tupleCount": 15,
            "stableReadPassCount": 3,
            "manifestWrittenLast": True,
            "independentReadbackPassed": True,
            "networkUsed": False,
            "sourceExtractionUsed": False,
            "sourceExecutionUsed": False,
            "freshChecksumDatabaseProof": False,
            "dependencyFixedPointReached": False,
            "dependencySourceReviewed": False,
            "candidateSelected": False,
            "librarySelected": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": (
                "rerun_combined_wave1_wave2_fixed_point_dependency_graph"
            ),
        }
        return (
            acquisition_receipt_raw,
            acquisition_receipt,
            acquisition_manifest_raw,
            acquisition_manifest,
            readback_raw,
            readback,
            readback_manifest,
        )

    def test_01_default_mode_is_preflight(self) -> None:
        args = RUNNER.parse_args([])
        self.assertFalse(args.execute)

    def test_02_execute_mode_is_explicit(self) -> None:
        args = RUNNER.parse_args(["--execute"])
        self.assertTrue(args.execute)

    def test_03_modes_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            RUNNER.parse_args(["--preflight", "--execute"])

    def test_04_exact_tuple_count(self) -> None:
        self.assertEqual(len(self.items), 15)

    def test_05_exact_resource_count(self) -> None:
        self.assertEqual(len(COMMON.expected_resource_names(self.items)), 30)

    def test_06_resource_ordinals_are_exact(self) -> None:
        observed = [
            ordinal
            for item in self.items
            for ordinal in (
                item["modRequestOrdinal"],
                item["zipRequestOrdinal"],
            )
        ]
        self.assertEqual(observed, list(range(1, 31)))

    def test_07_mod_precedes_zip(self) -> None:
        self.assertTrue(
            all(
                item["modRequestOrdinal"] + 1
                == item["zipRequestOrdinal"]
                for item in self.items
            )
        )

    def test_08_selected_and_nonselected_versions_are_preserved(self) -> None:
        self.assertEqual(
            sum(item["selectedByGraphAlgorithm"] for item in self.items),
            5,
        )
        self.assertEqual(
            sum(not item["selectedByGraphAlgorithm"] for item in self.items),
            10,
        )

    def test_09_same_module_versions_are_distinct(self) -> None:
        pairs = {(item["module"], item["version"]) for item in self.items}
        self.assertIn(("golang.org/x/net", "v0.34.0"), pairs)
        self.assertIn(("golang.org/x/net", "v0.35.0"), pairs)
        self.assertIn(("golang.org/x/text", "v0.33.0"), pairs)
        self.assertIn(("golang.org/x/text", "v0.34.0"), pairs)

    def test_10_urls_are_exact_https_proxy_urls(self) -> None:
        for item in self.items:
            self.assertTrue(item["modUrl"].startswith("https://proxy.golang.org/"))
            self.assertTrue(item["modUrl"].endswith(".mod"))
            self.assertTrue(item["url"].startswith("https://proxy.golang.org/"))
            self.assertTrue(item["url"].endswith(".zip"))

    def test_11_output_names_are_unique(self) -> None:
        names = COMMON.expected_resource_names(self.items)
        self.assertEqual(len(names), len(set(names)))

    def test_12_h1_values_are_canonical(self) -> None:
        for item in self.items:
            self.assertEqual(COMMON.validate_h1(item["goModH1"]), item["goModH1"])
            self.assertEqual(
                COMMON.validate_h1(item["moduleZipH1"]),
                item["moduleZipH1"],
            )

    def test_13_invalid_h1_is_rejected(self) -> None:
        with self.assertRaises(COMMON.Wave2Failure):
            COMMON.validate_h1("h1:not-base64")

    def test_14_zero_counters_are_valid(self) -> None:
        counters = COMMON.zero_counters()
        COMMON.validate_counters(counters)

    def test_15_success_counters_are_exact(self) -> None:
        counters = dict(
            zip(
                COMMON.COUNTER_NAMES,
                [30, 30, 30, 15, 15, 15],
            )
        )
        self.assertTrue(COMMON.success_counters(counters))
        COMMON.validate_counters(counters)

    def test_16_bool_counter_is_rejected(self) -> None:
        counters = COMMON.zero_counters()
        counters["networkRequestAttemptCount"] = True
        with self.assertRaises(COMMON.Wave2Failure):
            COMMON.validate_counters(counters)

    def test_17_attempt_is_counted_before_delegate_failure(self) -> None:
        counters = COMMON.zero_counters()
        opener = RUNNER.AttemptCountingOpener(DelegateFailure(), counters)
        with self.assertRaises(OSError):
            opener.open(object(), timeout=1.0)
        self.assertEqual(counters["networkRequestAttemptCount"], 1)

    def test_18_claim_is_bound_and_has_random_attempt_id(self) -> None:
        fake = FakeLegacy()
        permit = {
            "permitId": RUNNER.EXPECTED_PERMIT_ID,
            "contentBinding": {"sha256": "a" * 64},
        }
        attempt, digest = RUNNER.create_claim(
            fake,
            1,
            permit,
            self.decision,
        )
        claim = json.loads(fake.payload)
        self.assertEqual(len(attempt), 32)
        self.assertEqual(claim["attemptId"], attempt)
        self.assertEqual(claim["permitId"], RUNNER.EXPECTED_PERMIT_ID)
        self.assertEqual(fake.name, COMMON.CLAIM_NAME)
        self.assertEqual(fake.maximum_bytes, 64 * 1024)
        self.assertEqual(digest, COMMON.sha256_bytes(fake.payload))

    def test_19_failure_document_allows_nullable_context(self) -> None:
        authority = {
            "permit": {
                "permitId": RUNNER.EXPECTED_PERMIT_ID,
                "contentBinding": {"sha256": "a" * 64},
            },
            "decision": self.decision,
            "core": self.core,
        }
        failure = COMMON.Wave2Failure("E_SYNTHETIC", "filesystem")
        document = RUNNER.failure_document(
            authority,
            failure,
            COMMON.zero_counters(),
            claim_sha256="b" * 64,
        )
        self.assertIsNone(document["failedRequestOrdinal"])
        self.assertIsNone(document["failedTupleId"])
        self.assertIsNone(document["failedResourceKind"])
        self.assertEqual(document["failureCode"], "E_INTERNAL")

    def test_20_error_document_never_requests_authentication(self) -> None:
        document = RUNNER.error_document(
            COMMON.Wave2Failure("E_SYNTHETIC", "preflight")
        )
        self.assertFalse(document["externalAuthenticationRequired"])
        self.assertFalse(document["userActionRequired"])
        self.assertFalse(document["repositoryOwnerIdentityProofRequired"])

    def test_21_limits_match_decision(self) -> None:
        limits = self.decision["resourceLimits"]
        self.assertEqual(COMMON.MAXIMUM_MOD_BYTES, limits["maximumSingleModBytes"])
        self.assertEqual(COMMON.MAXIMUM_ZIP_BYTES, limits["maximumSingleZipBytes"])
        self.assertEqual(
            COMMON.MAXIMUM_AGGREGATE_RESPONSE_BYTES,
            limits["maximumAggregateResponseBytes"],
        )
        self.assertEqual(
            COMMON.MAXIMUM_ENTRIES_PER_ARCHIVE,
            limits["maximumZipEntryCountPerArchive"],
        )
        self.assertEqual(
            COMMON.MAXIMUM_UNCOMPRESSED_BYTES_PER_ARCHIVE,
            limits["maximumZipUncompressedBytesPerArchive"],
        )
        self.assertEqual(
            COMMON.MAXIMUM_COMPRESSION_RATIO,
            limits["maximumCompressionRatio"],
        )

    def test_22_regular_file_count_is_33(self) -> None:
        self.assertEqual(RUNNER.EXPECTED_ACQUISITION_REGULAR_FILE_COUNT, 33)

    def test_23_clean_namespace_is_currently_observed(self) -> None:
        self.assertEqual(RUNNER.classify_state(), "clean")

    def test_24_foreign_wave_parent_is_blocked(self) -> None:
        old_root = RUNNER.ROOT
        old_common_root = COMMON.Path if hasattr(COMMON, "Path") else None
        del old_common_root
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / COMMON.DEPENDENCY_PARENT
            parent.mkdir(parents=True)
            (parent / COMMON.WAVE_PARENT_NAME / "foreign").mkdir(parents=True)
            RUNNER.ROOT = root
            try:
                self.assertEqual(RUNNER.classify_state(), "blocked")
            finally:
                RUNNER.ROOT = old_root

    def test_25_common_binding_matches_bytes(self) -> None:
        self.assertEqual(
            COMMON.sha256_bytes((ROOT / RUNNER.COMMON_PATH).read_bytes()),
            RUNNER.EXPECTED_COMMON_RAW_SHA256,
        )

    def test_26_runner_does_not_import_process_modules(self) -> None:
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(imported.isdisjoint({"subprocess", "socket", "requests"}))

    def test_27_runner_has_no_shell_or_git_invocation(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("os.system(", source)
        self.assertNotIn("subprocess.", source)
        self.assertNotIn('["git"', source)

    def test_28_failure_receipt_excludes_raw_material(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '"rawErrorsBodiesHeadersCertificatesPathsOrEntryNamesRecorded": False',
            source,
        )

    def test_29_claim_precedes_opener_in_source(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertLess(
            source.index("_, claim_sha256 = create_claim("),
            source.index("legacy.build_exact_opener()"),
        )

    def test_30_manifest_write_occurs_after_receipt_write(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertLess(
            source.index("receipt_sha256 = legacy.write_repo_relative_artifact("),
            source.index("manifest_sha256 = legacy.write_repo_relative_artifact("),
        )

    def test_31_runner_self_check_is_not_readback(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn('"independentReadbackPassed": False', source)

    def test_32_permit_checker_pin_is_not_placeholder(self) -> None:
        self.assertNotEqual(
            RUNNER.EXPECTED_PERMIT_CHECKER_RAW_SHA256,
            "0" * 64,
        )

    def test_33_wave2_failure_context_is_supplemented(self) -> None:
        failure = COMMON.map_core_failure(
            self.core,
            COMMON.Wave2Failure(
                "E_ZIP_COMPRESSION_RATIO",
                "zip",
            ),
            tuple_id=self.items[0]["tupleId"],
            tuple_order=1,
            request_ordinal=2,
            resource_kind="zip",
            phase="zip",
        )
        self.assertEqual(failure.tuple_order, 1)
        self.assertEqual(failure.request_ordinal, 2)
        self.assertEqual(failure.resource_kind, "zip")

    def test_34_post_request_failure_requires_context(self) -> None:
        authority = {
            "permit": {
                "permitId": RUNNER.EXPECTED_PERMIT_ID,
                "contentBinding": {"sha256": "a" * 64},
            },
            "decision": self.decision,
            "core": self.core,
        }
        counters = COMMON.zero_counters()
        counters["networkRequestAttemptCount"] = 1
        with self.assertRaises(COMMON.Wave2Failure):
            RUNNER.failure_document(
                authority,
                COMMON.Wave2Failure("E_INTERNAL", "mod"),
                counters,
                claim_sha256="b" * 64,
            )

    def test_35_unlisted_failure_code_is_bounded_to_internal(self) -> None:
        authority = {
            "permit": {
                "permitId": RUNNER.EXPECTED_PERMIT_ID,
                "contentBinding": {"sha256": "a" * 64},
            },
            "decision": self.decision,
            "core": self.core,
        }
        document = RUNNER.failure_document(
            authority,
            COMMON.Wave2Failure("E_UNLISTED", "filesystem"),
            COMMON.zero_counters(),
            claim_sha256="b" * 64,
        )
        self.assertEqual(document["failureCode"], "E_INTERNAL")

    def test_36_active_namespace_barrier_precedes_opener(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertLess(
            source.index("verify_active_namespace(", source.index("claim_attempted")),
            source.index("legacy.build_exact_opener()"),
        )

    def test_37_failure_state_allows_absent_wave_parent(self) -> None:
        old_root = RUNNER.ROOT
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / COMMON.DEPENDENCY_PARENT
            parent.mkdir(parents=True)
            (parent / COMMON.CLAIM_NAME).write_text("claim")
            failure = root / COMMON.FAILURE_RECEIPT_PATH
            failure.parent.mkdir(parents=True)
            failure.write_text("failure")
            RUNNER.ROOT = root
            try:
                self.assertEqual(RUNNER.classify_state(), "failure")
            finally:
                RUNNER.ROOT = old_root

    def test_38_partial_readback_state_is_blocked(self) -> None:
        old_root = RUNNER.ROOT
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / COMMON.DEPENDENCY_PARENT
            final = parent / COMMON.WAVE_PARENT_NAME / COMMON.FINAL_DIRECTORY_NAME
            final.mkdir(parents=True)
            (parent / COMMON.CLAIM_NAME).write_text("claim")
            for relative in (
                COMMON.SUCCESS_RECEIPT_PATH,
                COMMON.MANIFEST_PATH,
                COMMON.READBACK_RECEIPT_PATH,
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("artifact")
            RUNNER.ROOT = root
            try:
                self.assertEqual(RUNNER.classify_state(), "blocked")
            finally:
                RUNNER.ROOT = old_root

    def test_39_compression_ratio_200_is_allowed(self) -> None:
        self.assertTrue(COMMON.compression_ratio_allowed(200, 1))

    def test_40_compression_ratio_201_is_rejected(self) -> None:
        self.assertFalse(COMMON.compression_ratio_allowed(201, 1))

    def test_41_zero_length_ratio_is_allowed_only_for_zero_pair(self) -> None:
        self.assertTrue(COMMON.compression_ratio_allowed(0, 0))
        self.assertFalse(COMMON.compression_ratio_allowed(1, 0))

    def test_42_mod_h1_validation_uses_exact_bytes(self) -> None:
        payload = b"module example.com/wave2-test\n\ngo 1.20\n"
        item = {
            "tupleId": "wave2-test",
            "order": 1,
            "module": "example.com/wave2-test",
            "goModH1": self.legacy.single_go_mod_h1(payload),
        }
        result = self.core.validate_mod_bytes(payload, item, self.legacy)
        self.assertEqual(result["goModH1"], item["goModH1"])

    def test_43_mod_h1_byte_drift_is_rejected(self) -> None:
        payload = b"module example.com/wave2-test\n"
        item = {
            "tupleId": "wave2-test",
            "order": 1,
            "module": "example.com/wave2-test",
            "goModH1": self.legacy.single_go_mod_h1(payload),
        }
        with self.assertRaises(self.core.RunnerFailure):
            self.core.validate_mod_bytes(
                payload + b"\n",
                item,
                self.legacy,
            )

    def test_44_exact_readback_terminal_is_accepted(self) -> None:
        authority = {
            "permit": {"permitId": RUNNER.EXPECTED_PERMIT_ID},
            "decision": self.decision,
        }
        RUNNER.validate_readback_terminal(
            authority,
            *self.readback_documents(),
        )

    def test_45_extra_readback_key_is_rejected(self) -> None:
        documents = list(self.readback_documents())
        documents[5]["unexpected"] = False
        authority = {
            "permit": {"permitId": RUNNER.EXPECTED_PERMIT_ID},
            "decision": self.decision,
        }
        with self.assertRaises(COMMON.Wave2Failure):
            RUNNER.validate_readback_terminal(authority, *documents)

    def test_46_readback_pass_count_drift_is_rejected(self) -> None:
        documents = list(self.readback_documents())
        documents[5]["stableReadPassCount"] = 2
        authority = {
            "permit": {"permitId": RUNNER.EXPECTED_PERMIT_ID},
            "decision": self.decision,
        }
        with self.assertRaises(COMMON.Wave2Failure):
            RUNNER.validate_readback_terminal(authority, *documents)

    def test_47_acquisition_manifest_hash_drift_is_rejected(self) -> None:
        documents = list(self.readback_documents())
        documents[5]["acquisitionManifestRawSha256"] = "d" * 64
        authority = {
            "permit": {"permitId": RUNNER.EXPECTED_PERMIT_ID},
            "decision": self.decision,
        }
        with self.assertRaises(COMMON.Wave2Failure):
            RUNNER.validate_readback_terminal(authority, *documents)

    def test_48_held_terminal_artifact_replacement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            artifact = root / "terminal.json"
            artifact.write_bytes(b'{"status":"held"}\n')
            artifact.chmod(0o600)
            held = COMMON.HeldInputSet(
                root,
                [
                    {
                        "path": "terminal.json",
                        "maximumBytes": 4096,
                        "ownerOnly": True,
                    }
                ],
            )
            try:
                artifact.rename(root / "old-terminal.json")
                artifact.write_bytes(b'{"status":"held"}\n')
                artifact.chmod(0o600)
                with self.assertRaises(COMMON.Wave2Failure):
                    held.final_barrier()
            finally:
                held.close()

    def test_49_readback_complete_binds_all_terminal_artifacts(self) -> None:
        claim_path = (
            f"{COMMON.DEPENDENCY_PARENT.as_posix()}/{COMMON.CLAIM_NAME}"
        )
        paths = {
            binding["path"]
            for binding in RUNNER.terminal_artifact_bindings(
                "readback_complete"
            )
        }
        self.assertEqual(
            paths,
            {
                claim_path,
                COMMON.SUCCESS_RECEIPT_PATH,
                COMMON.MANIFEST_PATH,
                COMMON.READBACK_RECEIPT_PATH,
                COMMON.READBACK_MANIFEST_PATH,
            },
        )

    def test_50_readback_manifest_semantic_drift_is_rejected(self) -> None:
        documents = list(self.readback_documents())
        documents[6]["resourceCount"] = 29
        authority = {
            "permit": {"permitId": RUNNER.EXPECTED_PERMIT_ID},
            "decision": self.decision,
        }
        with self.assertRaises(COMMON.Wave2Failure):
            RUNNER.validate_readback_terminal(authority, *documents)


if __name__ == "__main__":
    unittest.main()
