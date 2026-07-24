#!/usr/bin/env python3
"""Offline regression tests for the independent wave-two readback checker."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    ROOT / "script/check_p2p_nat_g2_pion_dependency_wave2_success_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave2_readback_tests_target",
    CHECKER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)
COMMON = CHECKER.COMMON


class WaveTwoReadbackTests(unittest.TestCase):
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

    def record_for(self, item) -> dict:
        return {
            "order": item["order"],
            "tupleId": item["tupleId"],
            "module": item["module"],
            "version": item["version"],
            "selectedByGraphAlgorithm": item["selectedByGraphAlgorithm"],
            "modRequestOrdinal": item["modRequestOrdinal"],
            "zipRequestOrdinal": item["zipRequestOrdinal"],
            "modUrl": item["modUrl"],
            "zipUrl": item["url"],
            "modOutputFileName": item["modOutputFileName"],
            "zipOutputFileName": item["zipOutputFileName"],
            "goModH1": item["goModH1"],
            "moduleZipH1": item["moduleZipH1"],
            "modRawByteSize": 1,
            "modRawSha256": "a" * 64,
            "zipRawByteSize": 1,
            "zipRawSha256": "b" * 64,
            "entryCount": 1,
            "uncompressedByteCount": 1,
            "modulePrefix": f"{item['module']}@{item['version']}/",
            "embeddedGoModPresent": False,
            "embeddedGoModByteParity": True,
            "modMode": "0600",
            "zipMode": "0600",
            "modLinkCount": 1,
            "zipLinkCount": 1,
            "compressionTelemetry": {
                "policy": "non_gating_bounded_telemetry",
                "historicalV2ComparisonRatio": 200,
                "maximumRatioEntryOrdinal": 1,
                "maximumRatioEntryUncompressedBytes": 201,
                "maximumRatioEntryCompressedBytes": 1,
                "maximumRatioExceededHistoricalV2Limit": True,
                "floatingPointRatioUsed": False,
                "entryNameOrBodyRecorded": False,
            },
        }

    def test_01_default_mode_is_check(self) -> None:
        args = CHECKER.parse_args([])
        self.assertFalse(args.record)

    def test_02_record_mode_is_explicit(self) -> None:
        args = CHECKER.parse_args(["--record"])
        self.assertTrue(args.record)

    def test_03_modes_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            CHECKER.parse_args(["--check", "--record"])

    def test_04_exact_source_record_accepts_bound_values(self) -> None:
        item = self.items[0]
        CHECKER.exact_source_record(item, self.record_for(item))

    def test_05_tuple_id_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["tupleId"] = "drift"
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_06_version_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["version"] = "v9.9.9"
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_07_selection_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["selectedByGraphAlgorithm"] = not item[
            "selectedByGraphAlgorithm"
        ]
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_08_mod_url_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["modUrl"] += "?x=1"
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_09_zip_url_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["zipUrl"] = record["zipUrl"].replace("https:", "http:")
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_10_h1_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["goModH1"] = "h1:" + "A" * 44
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_11_mode_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["modMode"] = "0644"
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_12_link_count_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["zipLinkCount"] = 2
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_13_compression_telemetry_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["compressionTelemetry"][
            "maximumRatioExceededHistoricalV2Limit"
        ] = False
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_14_exact_15_records_can_be_matched(self) -> None:
        for item in self.items:
            CHECKER.exact_source_record(item, self.record_for(item))

    def test_15_error_document_is_offline(self) -> None:
        document = CHECKER.error_document(
            COMMON.Wave2Failure("E_SYNTHETIC", "readback")
        )
        self.assertFalse(document["networkUsed"])
        self.assertFalse(document["externalAuthenticationRequired"])
        self.assertFalse(document["userActionRequired"])
        mapped = COMMON.map_readback_failure(
            self.legacy.AcquisitionFailure(
                "E_FILESYSTEM_MODE",
                "filesystem",
            ),
            core=self.core,
            legacy=self.legacy,
        )
        self.assertEqual(mapped.code, "E_FILESYSTEM_MODE")
        self.assertEqual(mapped.phase, "readback")
        self.assertEqual(
            COMMON.map_readback_failure(OSError()).code,
            "E_READBACK_FILESYSTEM",
        )

    def test_16_readback_paths_are_distinct(self) -> None:
        self.assertNotEqual(
            COMMON.READBACK_RECEIPT_PATH,
            COMMON.READBACK_MANIFEST_PATH,
        )
        self.assertNotEqual(
            COMMON.READBACK_RECEIPT_PATH,
            COMMON.SUCCESS_RECEIPT_PATH,
        )

    def test_17_readback_checker_imports_no_network_modules(self) -> None:
        tree = ast.parse(CHECKER_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {"http", "requests", "socket", "subprocess", "urllib"}
            )
        )

    def test_18_readback_checker_has_no_shell_git_or_go_invocation(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("os.system(", source)
        self.assertNotIn("subprocess.", source)
        self.assertNotIn('["git"', source)
        self.assertNotIn('["go"', source)

    def test_19_check_is_read_only_in_source(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        check_source = source[source.index("def check()"):source.index("def record()")]
        self.assertNotIn("write_repo_relative_artifact", check_source)

    def test_20_record_writes_receipt_before_manifest(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertLess(
            source.index("receipt_sha256 = authority[\"legacy\"].write_repo_relative_artifact("),
            source.index("manifest_sha256 = authority[\"legacy\"].write_repo_relative_artifact("),
        )

    def test_21_two_stable_passes_are_required(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn("first = validate_resource_pass(authority)", source)
        self.assertIn("second = validate_resource_pass(authority)", source)
        self.assertIn('"stableReadPassCount": 2', source)

    def test_22_readback_does_not_claim_fixed_point(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn('"dependencyFixedPointReached": False', source)
        self.assertIn('"dependencySourceReviewed": False', source)
        self.assertIn('"candidateSelected": False', source)
        self.assertIn('"librarySelected": False', source)

    def test_23_readback_does_not_claim_fresh_sumdb_proof(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn('"freshChecksumDatabaseProof": False', source)

    def test_24_preacquisition_check_fails_without_writes(self) -> None:
        before = {
            path: (ROOT / path).exists()
            for path in (
                COMMON.READBACK_RECEIPT_PATH,
                COMMON.READBACK_MANIFEST_PATH,
            )
        }
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.check()
        after = {
            path: (ROOT / path).exists()
            for path in (
                COMMON.READBACK_RECEIPT_PATH,
                COMMON.READBACK_MANIFEST_PATH,
            )
        }
        self.assertEqual(before, after)

    def test_25_permit_checker_pin_is_not_placeholder(self) -> None:
        self.assertNotEqual(
            CHECKER.EXPECTED_PERMIT_CHECKER_RAW_SHA256,
            "0" * 64,
        )
        info = ROOT.stat()
        identity = {
            "device": info.st_dev,
            "inode": info.st_ino,
            "uid": info.st_uid,
            "mode": stat.S_IMODE(info.st_mode),
        }
        adapted = COMMON.legacy_repository_root_identity(identity)
        root_fd = self.legacy.open_root_directory(adapted)
        self.legacy.close_quietly(root_fd)
        self.assertIn(
            "COMMON.legacy_repository_root_identity(",
            CHECKER_PATH.read_text(encoding="utf-8"),
        )

    def test_26_extra_source_record_key_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["unexpected"] = False
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_27_source_record_schema_is_exact(self) -> None:
        self.assertEqual(
            set(self.record_for(self.items[0])),
            CHECKER.SOURCE_RECORD_KEYS,
        )

    def test_28_named_resource_barrier_is_rechecked(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        function = source[
            source.index("def read_resource_twice("):
            source.index("def validate_resource_pass(")
        ]
        self.assertGreaterEqual(
            function.count("named_entry_matches_open_file("),
            2,
        )

    def test_29_record_uses_one_authority_lifecycle(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        function = source[source.index("def record()"):source.index("def error_document(")]
        self.assertNotIn("checked = check()", function)
        self.assertEqual(function.count("authority = load_authority()"), 1)

    def test_30_record_has_final_third_resource_pass(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        function = source[source.index("def record()"):source.index("def error_document(")]
        self.assertIn("final_pass = validate_resource_pass(", function)
        self.assertIn("retain_fds=publication_guard", function)
        self.assertIn('checked["stableReadPassCount"] = 3', function)

    def test_31_acquisition_lineage_fields_are_exactly_checked(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        for token in (
            "permitRawSha256",
            "permitContentSha256",
            "decisionRawSha256",
            "decisionContentSha256",
            "orderedResourceSetSha256",
            "orderedSourceSetSha256",
            "acceptedArtifactCount",
            "acceptedTupleCount",
        ):
            self.assertIn(token, source)
        self.assertEqual(
            COMMON.v3_ordered_resource_set_sha256(self.decision),
            COMMON.EXPECTED_V3_ORDERED_RESOURCE_SET_SHA256,
        )
        self.assertNotEqual(
            self.decision["wave"]["orderedResourceSetSha256"],
            COMMON.EXPECTED_V3_ORDERED_RESOURCE_SET_SHA256,
        )

    def test_32_canonical_utc_claim_timestamp_is_accepted(self) -> None:
        self.assertTrue(
            CHECKER.canonical_utc_timestamp("2026-07-24T12:34:56Z")
        )

    def test_33_noncanonical_claim_timestamp_is_rejected(self) -> None:
        for value in (
            None,
            True,
            "2026-7-24T12:34:56Z",
            "2026-07-24T12:34:56+00:00",
            "2026-02-30T12:34:56Z",
        ):
            self.assertFalse(CHECKER.canonical_utc_timestamp(value))

    def test_34_module_prefix_drift_is_rejected(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        record["modulePrefix"] = "example.invalid@v0.0.0/"
        with self.assertRaises(COMMON.Wave2Failure):
            CHECKER.exact_source_record(item, record)

    def test_35_acquisition_fixed_meaning_values_are_checked(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        for token in (
            "claim_persists_after_any_network_attempt_and_blocks_retry",
            "fresh_exact_15_dependency_mod_zip_pairs_acquired_and_",
            "receipt_and_fresh_exact_15_mod_zip_pairs_published_",
            "repositoryOwnerIdentityProofRequired",
            "run_separate_wave2_v3_independent_readback",
        ):
            self.assertIn(token, source)

    def test_36_record_retains_resource_fds_through_publication(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        function = source[
            source.index("def record()"):
            source.index("def error_document(")
        ]
        self.assertIn("retain_fds=publication_guard", function)
        self.assertGreaterEqual(
            function.count("revalidate_retained_resource_pass("),
            3,
        )
        self.assertIn(
            "close_retained_resource_pass(publication_guard)",
            function,
        )

    def test_37_resource_guard_is_checked_after_manifest_write(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        function = source[
            source.index("def record()"):
            source.index("def error_document(")
        ]
        manifest_write = function.index(
            'manifest_sha256 = authority["legacy"].write_repo_relative_artifact('
        )
        final_barrier = function.rindex(
            "revalidate_retained_resource_pass(publication_guard)"
        )
        self.assertGreater(final_barrier, manifest_write)

    def test_38_published_artifact_named_replacement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            evidence = root / "evidence"
            evidence.mkdir(mode=0o700)
            root_fd = os.open(root, self.legacy.directory_open_flags())
            guard = None
            try:
                relative = "evidence/receipt.json"
                payload = b'{"status":"synthetic"}\n'
                self.legacy.write_repo_relative_artifact(
                    root_fd,
                    relative,
                    payload,
                    4096,
                )
                guard = CHECKER.open_published_artifact(
                    root_fd,
                    relative,
                    payload,
                    self.legacy,
                )
                target = root / relative
                target.rename(evidence / "old-receipt.json")
                target.write_bytes(payload)
                target.chmod(0o600)
                with self.assertRaises(Exception):
                    CHECKER.revalidate_published_artifact(guard)
            finally:
                if guard is not None:
                    CHECKER.close_published_artifact(guard)
                os.close(root_fd)

    def test_39_retained_resource_named_replacement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            dependency = root / COMMON.DEPENDENCY_PARENT
            wave = dependency / COMMON.WAVE_PARENT_NAME
            final = wave / COMMON.FINAL_DIRECTORY_NAME
            final.mkdir(parents=True, mode=0o700)
            for parent in (dependency, wave, final):
                parent.chmod(0o700)
            resource = final / "one.mod"
            resource.write_bytes(b"module example.test\n")
            resource.chmod(0o600)
            root_fd = os.open(root, self.legacy.directory_open_flags())
            dependency_fd = self.legacy.open_directory_chain(
                root_fd,
                self.legacy.validate_relative_path(
                    str(COMMON.DEPENDENCY_PARENT)
                ),
                create=False,
            )
            wave_fd = os.open(
                COMMON.WAVE_PARENT_NAME,
                self.legacy.directory_open_flags(),
                dir_fd=dependency_fd,
            )
            final_fd = os.open(
                COMMON.FINAL_DIRECTORY_NAME,
                self.legacy.directory_open_flags(),
                dir_fd=wave_fd,
            )
            resource_fd = os.open(
                "one.mod",
                self.legacy.file_open_flags(),
                dir_fd=final_fd,
            )
            info = os.fstat(resource_fd)
            guard = {
                "legacy": self.legacy,
                "rootFd": root_fd,
                "dependencyFd": dependency_fd,
                "waveFd": wave_fd,
                "finalFd": final_fd,
                "rootIdentity": CHECKER.retained_directory_identity(
                    os.fstat(root_fd)
                ),
                "dependencyIdentity": (
                    CHECKER.retained_directory_identity(
                        os.fstat(dependency_fd)
                    )
                ),
                "waveIdentity": CHECKER.retained_directory_identity(
                    os.fstat(wave_fd)
                ),
                "finalIdentity": CHECKER.retained_directory_identity(
                    os.fstat(final_fd)
                ),
                "resourceFds": [resource_fd],
                "identities": [
                    {
                        "name": "one.mod",
                        "device": info.st_dev,
                        "inode": info.st_ino,
                        "mode": stat.S_IMODE(info.st_mode),
                        "uid": info.st_uid,
                        "linkCount": info.st_nlink,
                        "size": info.st_size,
                        "mtimeNs": info.st_mtime_ns,
                        "ctimeNs": info.st_ctime_ns,
                    }
                ],
                "expectedResourceNames": ["one.mod"],
            }
            try:
                wave.chmod(0o755)
                with self.assertRaises(Exception):
                    CHECKER.revalidate_retained_resource_pass(guard)
                wave.chmod(0o700)
                guard["waveIdentity"] = (
                    CHECKER.retained_directory_identity(os.fstat(wave_fd))
                )
                resource.rename(final / "old-one.mod")
                resource.write_bytes(b"module example.test\n")
                resource.chmod(0o600)
                with self.assertRaises(Exception):
                    CHECKER.revalidate_retained_resource_pass(guard)
            finally:
                CHECKER.close_retained_resource_pass(guard)

    def test_40_above_historical_ratio_remains_valid_telemetry(self) -> None:
        item = self.items[0]
        record = self.record_for(item)
        CHECKER.exact_source_record(item, record)
        self.assertTrue(
            record["compressionTelemetry"][
                "maximumRatioExceededHistoricalV2Limit"
            ]
        )

    def test_41_missing_or_extra_telemetry_key_is_rejected(self) -> None:
        item = self.items[0]
        for mutation in ("missing", "extra"):
            record = self.record_for(item)
            if mutation == "missing":
                record["compressionTelemetry"].pop(
                    "maximumRatioEntryOrdinal"
                )
            else:
                record["compressionTelemetry"]["unexpected"] = False
            with self.assertRaises(COMMON.Wave2Failure):
                CHECKER.exact_source_record(item, record)

    def test_42_readback_compares_independently_recomputed_telemetry(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'archive["compressionTelemetry"]',
            source,
        )
        self.assertIn(
            'record.get("compressionTelemetry")',
            source,
        )
        self.assertIn(
            "archiveCountExceedingHistoricalV2Ratio",
            source,
        )

    def test_43_ratio_rejection_gate_is_absent(self) -> None:
        source = (
            CHECKER_PATH.read_text(encoding="utf-8")
            + (ROOT / CHECKER.COMMON_PATH).read_text(encoding="utf-8")
        )
        for token in (
            "E_ZIP_COMPRESSION_RATIO",
            "MAXIMUM_COMPRESSION_RATIO",
            "compressionRatioLimitPassed",
            "ratioLimitPassed",
        ):
            self.assertNotIn(token, source)

    def test_44_failure_receipt_blocks_readback_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dependency = root / COMMON.DEPENDENCY_PARENT
            dependency.mkdir(parents=True)
            failure = root / COMMON.FAILURE_RECEIPT_PATH
            failure.parent.mkdir(parents=True)
            failure.write_bytes(b"{}\n")
            with self.assertRaises(COMMON.Wave2Failure) as caught:
                CHECKER.require_success_namespace_exclusions(root)
            self.assertEqual(caught.exception.code, "E_READBACK_NAMESPACE")

    def test_45_staging_residue_blocks_readback_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dependency = root / COMMON.DEPENDENCY_PARENT
            dependency.mkdir(parents=True)
            (dependency / f"{COMMON.STAGING_PREFIX}synthetic").mkdir()
            with self.assertRaises(COMMON.Wave2Failure) as caught:
                CHECKER.require_success_namespace_exclusions(root)
            self.assertEqual(caught.exception.code, "E_READBACK_NAMESPACE")

    def test_46_record_rechecks_namespace_across_publication(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        function = source[
            source.index("def record()"):
            source.index("def error_document(")
        ]
        final_pass = function.index("final_pass = validate_resource_pass(")
        prepublication = function.index(
            "require_readback_publication_namespace(ROOT)",
            final_pass,
        )
        receipt_write = function.index(
            'receipt_sha256 = authority["legacy"].write_repo_relative_artifact('
        )
        post_receipt = function.index(
            "require_success_namespace_exclusions(ROOT)",
            receipt_write,
        )
        manifest_write = function.index(
            'manifest_sha256 = authority["legacy"].write_repo_relative_artifact('
        )
        post_manifest = function.index(
            "require_success_namespace_exclusions(ROOT)",
            manifest_write,
        )
        self.assertLess(final_pass, prepublication)
        self.assertLess(prepublication, receipt_write)
        self.assertLess(receipt_write, post_receipt)
        self.assertLess(post_receipt, manifest_write)
        self.assertLess(manifest_write, post_manifest)

    def test_47_outer_authority_holds_full_permit_preparation_set(
        self,
    ) -> None:
        expected = {
            binding["path"]
            for binding in (
                CHECKER.PERMIT_CHECKER_BOOTSTRAP.preparation_bindings(
                    include_permit=True,
                )
            )
        }
        actual = {
            binding["path"]
            for binding in CHECKER.authority_bindings()
        }
        self.assertTrue(expected.issubset(actual))
        for path in (
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.RECOVERY_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.RECOVERY_CHECKER_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.V2_PERMIT_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.V2_PERMIT_CHECKER_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.RUNNER_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.RUNNER_TEST_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.READBACK_TEST_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.PERMIT_READER_PATH,
            CHECKER.PERMIT_CHECKER_BOOTSTRAP.THIS_TEST_PATH,
        ):
            self.assertIn(path, actual)
        checker_binding = next(
            binding
            for binding in CHECKER.authority_bindings()
            if binding["path"] == CHECKER.PERMIT_CHECKER_PATH
        )
        self.assertEqual(
            checker_binding.get("rawSha256"),
            CHECKER.EXPECTED_PERMIT_CHECKER_RAW_SHA256,
        )

    def test_48_lineage_named_replacement_hits_final_barrier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.chmod(root, 0o700)
            paths = (
                "docs/recovery-v2.json",
                "script/check-recovery-v2.py",
                "docs/permit-v2.json",
            )
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.parent.chmod(0o700)
                target.write_bytes(relative.encode())
                target.chmod(0o600)
            held = COMMON.HeldInputSet(
                root,
                [
                    {
                        "path": relative,
                        "maximumBytes": 4096,
                    }
                    for relative in paths
                ],
            )
            try:
                target = root / paths[1]
                target.rename(target.with_name("old-check-recovery-v2.py"))
                target.write_bytes(paths[1].encode())
                target.chmod(0o600)
                with self.assertRaises(COMMON.Wave2Failure) as caught:
                    held.final_barrier()
                self.assertEqual(caught.exception.code, "E_TOCTOU")
            finally:
                held.close()


if __name__ == "__main__":
    unittest.main()
