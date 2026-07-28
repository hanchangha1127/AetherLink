#!/usr/bin/env python3
"""Tests for the zero-write fixed-point snapshot review adapter."""

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
    raise RuntimeError("tests require unoptimized `python3 -I -B -S`")

import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock
import zipfile


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_fixed_point_snapshot_source_license_review_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "g2_pion_fixed_point_snapshot_source_license_review_v1",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load snapshot review adapter")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class StdoutCapture:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()


def zip_bytes(rows: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=False,
    ) as archive:
        for path, raw in rows:
            info = zipfile.ZipInfo(path)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return output.getvalue()


class FixedPointSnapshotSourceLicenseReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        checker.validate_controls(checker.ROOT)
        cls.bindings, cls.snapshot = checker.build_snapshot(checker.ROOT)

    def test_01_exact_snapshot_preflight_is_current(self) -> None:
        self.assertEqual(len(self.bindings), 369)
        self.assertEqual(
            self.snapshot,
            {
                "sourceInputCount": 369,
                "moduleVersionTupleCount": 184,
                "archiveCount": 185,
                "aggregateRawBytes": 356_092_640,
                "aggregateEntryCount": 72_304,
                "aggregateUncompressedBytes": 1_359_347_284,
                "maximumArchiveBytes": 9_237_329,
                "maximumEntriesPerArchive": 2_065,
                "maximumEntryBytes": 5_477_310,
                "maximumPathUtf8Bytes": 174,
                "maximumUncompressedBytesPerArchive": 41_103_581,
                "licenseCandidateCountByName": 362,
                "goFileCountBySuffix": 58_478,
                "assemblyFileCountBySuffix": 1_528,
                "nativeFileCountBySuffix": 110,
                "binaryFileCountBySuffix": 144,
                "reviewBindingSetSha256": (
                    "3423f30722a5d9be67774be1b3dc7f25544ddd9b452c914e"
                    "891085f0e3e24d23"
                ),
            },
        )

    def test_02_main_emits_canonical_zero_write_preflight(self) -> None:
        capture = StdoutCapture()
        with mock.patch.object(sys, "stdout", capture):
            result = checker.main([])
        self.assertEqual(result, 0)
        raw = capture.buffer.getvalue()
        parsed = json.loads(raw)
        self.assertEqual(raw, checker.canonical_bytes(parsed))
        self.assertTrue(parsed["validationPassed"])
        self.assertEqual(parsed["fileWriteCount"], 0)
        self.assertFalse(parsed["externalAuthenticationRequired"])
        self.assertFalse(parsed["userActionRequired"])

    def test_03_binding_projection_is_exact_and_ordered(self) -> None:
        self.assertEqual(self.bindings[0]["kind"], "root_zip")
        self.assertEqual(self.bindings[0]["tupleOrder"], 0)
        dependency = self.bindings[1:]
        self.assertEqual(
            sum(row["kind"] == "mod" for row in dependency),
            184,
        )
        self.assertEqual(
            sum(row["kind"] == "zip" for row in dependency),
            184,
        )
        self.assertEqual(
            {
                (row["module"], row["version"], row["tupleOrder"])
                for row in dependency
            }.__len__(),
            184,
        )
        self.assertEqual(
            sum(row["byteSize"] for row in self.bindings),
            checker.EXPECTED_AGGREGATE_RAW_BYTES,
        )

    def test_04_quoted_and_plain_module_directives_parse(self) -> None:
        self.assertEqual(
            checker.parse_module_directive(
                b'module "github.com/kr/pretty"\n'
            ),
            "github.com/kr/pretty",
        )
        self.assertEqual(
            checker.parse_module_directive(
                b"module golang.org/x/text // old syntax\n"
            ),
            "golang.org/x/text",
        )
        with self.assertRaises(checker.ReviewError):
            checker.parse_module_directive(b"go 1.24\n")

    def test_05_archive_paths_and_roots_fail_closed(self) -> None:
        valid = zip_bytes(
            [
                ("example.com/mod@v1.0.0/go.mod", b"module example.com/mod\n"),
                ("example.com/mod@v1.0.0/source.go", b"package mod\n"),
            ]
        )
        metadata = checker.inspect_archive_metadata(
            valid,
            "example.com/mod",
            "v1.0.0",
        )
        self.assertEqual(metadata["entryCount"], 2)
        self.assertEqual(metadata["modulePrefix"], "example.com/mod@v1.0.0/")

        traversal = zip_bytes(
            [("example.com/mod@v1.0.0/../escape", b"x")]
        )
        with self.assertRaises(checker.ReviewError):
            checker.inspect_archive_metadata(
                traversal,
                "example.com/mod",
                "v1.0.0",
            )

        mixed = zip_bytes(
            [
                ("example.com/mod@v1.0.0/a", b"a"),
                ("example.com/other@v1.0.0/b", b"b"),
            ]
        )
        with self.assertRaises(checker.ReviewError):
            checker.detect_archive_prefix(mixed)

    def test_06_license_candidate_rule_is_broad_but_not_source(self) -> None:
        accepted = (
            "LICENSE",
            "PATENTS",
            "AUTHORS",
            "NOTICE.md",
            "COPYRIGHT.txt",
            "THIRD_PARTY_LICENSES",
        )
        for value in accepted:
            self.assertTrue(checker.is_license_path(value), value)
        for value in (
            "copyright.go",
            "authors.py",
            "license_check.sh",
            "not-a-license.txt",
        ):
            self.assertFalse(checker.is_license_path(value), value)

    def test_07_profile_contract_is_exact_and_local(self) -> None:
        self.assertEqual(len(checker.PROFILES), 2)
        android, macos = checker.PROFILES
        self.assertEqual(
            (android["goos"], android["goarch"]),
            ("android", "arm64"),
        )
        self.assertEqual(
            (macos["goos"], macos["goarch"]),
            ("darwin", "arm64"),
        )
        self.assertTrue(android["cgoEnabled"])
        self.assertTrue(macos["cgoEnabled"])
        self.assertEqual(
            {row["goVersion"] for row in checker.PROFILES},
            {"1.24"},
        )

    def test_08_control_and_runner_hashes_are_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(
                (checker.ROOT / checker.CLOSURE_DECISION_PATH).read_bytes()
            ).hexdigest(),
            checker.CLOSURE_DECISION_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (
                    checker.ROOT / checker.PINNED_REVIEW_RUNNER_PATH
                ).read_bytes()
            ).hexdigest(),
            checker.PINNED_REVIEW_RUNNER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                checker.normalized_self_bytes(CHECKER_PATH.read_bytes())
            ).hexdigest(),
            checker.SELF_NORMALIZED_SHA256,
        )

    def test_09_pinned_provider_removes_write_entry_points(self) -> None:
        provider = checker.load_pinned_review_runner(checker.ROOT)
        for name in (
            "execute_with_authority",
            "write_exclusive",
            "manifest_document",
            "durable_failure_document",
            "claim_document",
            "main",
        ):
            self.assertFalse(hasattr(provider, name), name)
        self.assertTrue(hasattr(provider, "review_held_inputs"))
        self.assertTrue(hasattr(provider, "HeldInputSet"))

    def test_10_stable_reader_rejects_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular"
            regular.write_bytes(b"ok")
            regular.chmod(0o600)
            self.assertEqual(
                checker.read_stable_owner_file(root, "regular", 2),
                b"ok",
            )
            symlink = root / "symlink"
            symlink.symlink_to(regular)
            with self.assertRaises(checker.ReviewError):
                checker.read_stable_owner_file(root, "symlink", 2)
            hardlink = root / "hardlink"
            os.link(regular, hardlink)
            with self.assertRaises(checker.ReviewError):
                checker.read_stable_owner_file(root, "regular", 2)
            with self.assertRaises(checker.ReviewError):
                checker.read_stable_owner_file(root, "../escape", 2)

    def test_11_incomplete_provider_projection_fails_closed(self) -> None:
        class FakeHeld:
            def __init__(self, *_: object) -> None:
                pass

            def __enter__(self) -> "FakeHeld":
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def final_barrier(self) -> None:
                return None

        reviewed = {
            "graphDiscovery": {
                "fixedPointReached": True,
                "newTupleCount": 0,
                "unmappedExternalImportCount": 0,
                "unresolvedDeclaredExternalImportCount": 0,
            },
            "coverage": {"modules": [{"module": "example.com/mod"}]},
            "sourceSurface": {
                "profiles": [{"profileId": "android"}],
                "sourceFileCount": 1,
                "sourceSurfaceSha256": "a" * 64,
            },
            "licenseInventory": {"entries": [{"path": "LICENSE"}]},
            "specialSourceInventory": {"entries": []},
            "moduleMetadata": {"modules": [{"module": "example.com/mod"}]},
        }
        provider = types.SimpleNamespace(
            HeldInputSet=FakeHeld,
            review_held_inputs=lambda *_: reviewed,
            snapshot_legacy_compatibility_state={
                "wave9LegacyBuildCount": 2,
                "wave9LegacyNonProductionOccurrenceCount": 2,
                "malformedNonProductionBuildCountBySha256": {
                    digest: row["expectedOccurrenceCount"]
                    for digest, row in (
                        checker.EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES.items()
                    )
                },
                "malformedNonProductionOccurrenceCountBySha256": {
                    digest: row["expectedOccurrenceCount"]
                    for digest, row in (
                        checker.EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES.items()
                    )
                },
            },
        )
        with mock.patch.object(
            checker,
            "load_pinned_review_runner",
            return_value=provider,
        ):
            with self.assertRaises(checker.ReviewError) as raised:
                checker.compact_full_scan(self.bindings, self.snapshot)
        self.assertEqual(raised.exception.code, "E_FULL_SCAN")

    def test_12_exact_fake_projection_keeps_review_and_closure_open(
        self,
    ) -> None:
        class FakeHeld:
            def __init__(self, *_: object) -> None:
                pass

            def __enter__(self) -> "FakeHeld":
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def final_barrier(self) -> None:
                return None

        coverage_rows = [{"module": "example.com/mod"}]
        license_rows = [{"path": "LICENSE"}]
        special_rows = [{"path": "generated.go"}]
        metadata_rows = [{"module": "example.com/mod"}]
        profiles = [
            {
                "profileId": row["profileId"],
                "goos": row["goos"],
                "goarch": row["goarch"],
                "tags": list(row["tags"]),
            }
            for row in checker.EXPECTED_PROVIDER_PROFILES
        ]
        graph = {
            "algorithm": "go1.24_mvs_profile_union_fixed_point_v1",
            "graphSha256": "a" * 64,
            "reconstructionProjectionSha256": "a" * 64,
            "nodeSetSha256": "b" * 64,
            "edgeSetSha256": "c" * 64,
            "moduleNodeSetSha256": "d" * 64,
            "moduleEdgeSetSha256": "e" * 64,
            "moduleGraphAndFrontierSha256": "f" * 64,
            "graphNodeCount": 1,
            "graphEdgeCount": 2,
            "moduleNodeCount": 3,
            "moduleEdgeCount": 4,
            "selectedVersions": [{"module": "example.com/mod"}],
            "exactFrontier": [],
            "newlyReachableTuples": [],
            "unmappedExternalImports": [],
            "unresolvedDeclaredExternalImports": [],
            "newTupleCount": 0,
            "unmappedExternalImportCount": 0,
            "unresolvedDeclaredExternalImportCount": 0,
            "fixedPointReached": True,
            "independentReproductionPassed": True,
            "reconstructionCount": 2,
        }
        reviewed = {
            "graphDiscovery": graph,
            "coverage": {
                "modules": coverage_rows,
                "aggregateEntryCount":
                    checker.EXPECTED_AGGREGATE_ENTRY_COUNT,
                "aggregateUncompressedBytes":
                    checker.EXPECTED_AGGREGATE_UNCOMPRESSED_BYTES,
                "omittedArchiveCount": 0,
                "filesystemExtractionCount": 0,
            },
            "sourceSurface": {
                "profiles": profiles,
                "sourceFileCount":
                    checker.EXPECTED_PROVIDER_SOURCE_FILE_COUNT,
                "sourceSurfaceSha256":
                    checker.EXPECTED_PROVIDER_SOURCE_SURFACE_SHA256,
            },
            "licenseInventory": {
                "entries": license_rows,
                "licenseCandidateCount": 1,
                "compatibilityReviewed": False,
            },
            "specialSourceInventory": {
                "entries": special_rows,
                "specialSourceCount": 1,
                "executed": False,
            },
            "moduleMetadata": {"modules": metadata_rows},
        }
        compatibility = {
            "wave9LegacyBuildCount": 2,
            "wave9LegacyNonProductionOccurrenceCount": 2,
            "malformedNonProductionBuildCountBySha256": {
                digest: row["expectedOccurrenceCount"]
                for digest, row in (
                    checker.EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES.items()
                )
            },
            "malformedNonProductionOccurrenceCountBySha256": {
                digest: row["expectedOccurrenceCount"]
                for digest, row in (
                    checker.EXACT_MALFORMED_NONPRODUCTION_GO_FIXTURES.items()
                )
            },
        }
        provider = types.SimpleNamespace(
            HeldInputSet=FakeHeld,
            review_held_inputs=lambda *_: reviewed,
            snapshot_legacy_compatibility_state=compatibility,
        )
        patched = {
            "EXPECTED_PROVIDER_COVERAGE_COUNT": 1,
            "EXPECTED_PROVIDER_COVERAGE_SHA256": hashlib.sha256(
                checker.canonical_bytes(coverage_rows)
            ).hexdigest(),
            "EXPECTED_PROVIDER_NARROW_LICENSE_CANDIDATE_COUNT": 1,
            "EXPECTED_PROVIDER_NARROW_LICENSE_INVENTORY_SHA256":
                hashlib.sha256(
                    checker.canonical_bytes(license_rows)
                ).hexdigest(),
            "EXPECTED_PROVIDER_SPECIAL_SOURCE_COUNT": 1,
            "EXPECTED_PROVIDER_SPECIAL_SOURCE_INVENTORY_SHA256":
                hashlib.sha256(
                    checker.canonical_bytes(special_rows)
                ).hexdigest(),
            "EXPECTED_PROVIDER_MODULE_METADATA_COUNT": 1,
            "EXPECTED_PROVIDER_MODULE_METADATA_SHA256": hashlib.sha256(
                checker.canonical_bytes(metadata_rows)
            ).hexdigest(),
            "EXPECTED_PROVIDER_GRAPH_CANONICAL_SHA256": hashlib.sha256(
                checker.canonical_bytes(graph)
            ).hexdigest(),
            "EXPECTED_V18_GRAPH_SHA256": "a" * 64,
            "EXPECTED_PROVIDER_NODE_SET_SHA256": "b" * 64,
            "EXPECTED_PROVIDER_EDGE_SET_SHA256": "c" * 64,
            "EXPECTED_PROVIDER_MODULE_NODE_SET_SHA256": "d" * 64,
            "EXPECTED_PROVIDER_MODULE_EDGE_SET_SHA256": "e" * 64,
            "EXPECTED_PROVIDER_MODULE_GRAPH_AND_FRONTIER_SHA256": "f" * 64,
            "EXPECTED_PROVIDER_GRAPH_NODE_COUNT": 1,
            "EXPECTED_PROVIDER_GRAPH_EDGE_COUNT": 2,
            "EXPECTED_PROVIDER_MODULE_NODE_COUNT": 3,
            "EXPECTED_PROVIDER_MODULE_EDGE_COUNT": 4,
            "EXPECTED_PROVIDER_SELECTED_VERSION_COUNT": 1,
        }
        with (
            mock.patch.object(
                checker,
                "load_pinned_review_runner",
                return_value=provider,
            ),
            mock.patch.multiple(checker, **patched),
        ):
            result = checker.compact_full_scan(
                self.bindings,
                self.snapshot,
            )
        self.assertTrue(result["graph"]["fixedPointReached"])
        self.assertFalse(result["reviewContract"]["reviewPerformedByThisAdapter"])
        self.assertTrue(result["closure"]["dependencyFixedPointReached"])
        for key, value in result["closure"].items():
            if key != "dependencyFixedPointReached":
                self.assertFalse(value, key)
        self.assertEqual(
            result["operationCounters"]["totalZipArchiveOpenCount"],
            554,
        )
        self.assertEqual(
            result["operationCounters"][
                "wave9PinnedLegacyBuildCompatibilityCount"
            ],
            2,
        )
        self.assertEqual(result["operationCounters"]["fileWriteCount"], 0)
        self.assertEqual(
            result["operationCounters"]["networkOperationCount"],
            0,
        )
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])

    def test_13_error_output_never_requests_authentication(self) -> None:
        result = checker.error_result("E_TEST")
        self.assertEqual(result["error"], "E_TEST")
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        self.assertEqual(result["fileWriteCount"], 0)

    def test_14_static_surface_has_no_write_network_or_subprocess(self) -> None:
        tree = ast.parse(CHECKER_PATH.read_bytes())
        imported_roots: set[str] = set()
        banned_calls: list[str] = []
        banned_attributes = {
            "chmod",
            "execv",
            "execve",
            "fork",
            "link",
            "mkdir",
            "popen",
            "remove",
            "rename",
            "replace",
            "rmdir",
            "spawn",
            "symlink",
            "system",
            "unlink",
            "write_bytes",
            "write_text",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "compile",
                    "eval",
                    "exec",
                }:
                    banned_calls.append(node.func.id)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in banned_attributes
                ):
                    banned_calls.append(node.func.attr)
        self.assertTrue(
            imported_roots.isdisjoint(
                {"http", "requests", "socket", "subprocess", "urllib"}
            )
        )
        self.assertEqual(banned_calls, [])


if __name__ == "__main__":
    unittest.main()
