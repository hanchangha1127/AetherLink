#!/usr/bin/env python3
"""Synthetic-only tests for the separate one-use G2 rung-three v3 runner."""

from __future__ import annotations

import ast
import builtins
import copy
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "script/run_p2p_nat_g2_pion_rung3_offline_review_v3_once.py"
AGGREGATOR_PATH = ROOT / "script/p2p_nat_g2_pion_candidate_inventory_v3.py"


def load_source_without_importlib(path: Path, *, name: str) -> ModuleType:
    module = ModuleType(name)
    module.__file__ = str(path)
    raw = path.read_bytes()
    exec(
        compile(
            raw,
            path.name,
            "exec",
            flags=0,
            dont_inherit=True,
            optimize=0,
        ),
        module.__dict__,
        module.__dict__,
    )
    return module


RUNNER = load_source_without_importlib(
    RUNNER_PATH,
    name="g2_pion_rung3_review_v3_runner_test_subject",
)
AGGREGATOR = load_source_without_importlib(
    AGGREGATOR_PATH,
    name="g2_pion_candidate_inventory_v3_runner_test_subject",
)

SOURCE_BODY_SENTINEL = "V3_SYNTHETIC_SOURCE_BODY_MUST_NOT_BE_RECORDED_7f40db"
SYNTHETIC_SOURCE = (
    "package ice\n\n"
    f"// {SOURCE_BODY_SENTINEL}\n"
    "func boundedReviewCandidates() {\n"
    + ("    Dial()\n" * 513)
    + """    Debugf("synthetic-password-marker")
    OnConnectionStateChange()
    SetDeadline()
    _ = udp
    _ = Resolver{}
    _ = nonce
}
"""
).encode()
SYNTHETIC_ENTRIES = (
    (
        "go.mod",
        b"module github.com/pion/ice/v4\n"
        b"go 1.23\n"
        b"require example.invalid/dependency v1.2.3\n",
    ),
    (
        "go.sum",
        b"example.invalid/dependency v1.2.3 h1:c3ludGhldGlj\n",
    ),
    ("review_candidates.go", SYNTHETIC_SOURCE),
    ("LICENSE", b"synthetic license inventory fixture\n"),
)
V1_NAMES = (
    ".g2-pion-ice-v4.3.0-rung3-offline-review-v1.claim",
    "offline-source-review-result-v1.json",
    "offline-source-review-manifest-v1.json",
    ".offline-source-review-result-v1.json.tmp",
    ".offline-source-review-manifest-v1.json.tmp",
)
V2_NAMES = (
    ".g2-pion-ice-v4.3.0-rung3-offline-review-v2.claim",
    "offline-source-review-result-v2.json",
    "offline-source-review-manifest-v2.json",
    ".offline-source-review-result-v2.json.tmp",
    ".offline-source-review-manifest-v2.json.tmp",
)


def authority_fixture() -> dict[str, object]:
    return {
        "permit": {
            "permitId": "g2-pion-rung3-offline-review-execution-permit-v3",
            "archiveIdentityBinding": {
                "receiptPath": RUNNER.RECEIPT_PATH,
                "receiptRawSha256": "c" * 64,
            },
        },
        "permitRawSha256": "a" * 64,
        "permitSemanticSha256": "b" * 64,
        "archiveOpenCount": 0,
        "archiveReadPassCount": 0,
        "buildPathReadCount": 0,
        "outputPathReadCount": 0,
        "fileWriteCount": 0,
        "permitConsumptionState": "not_inspected",
        "authorityReadPaths": ("docs/synthetic-permit-v3.json",),
    }


def synthetic_inspection() -> dict[str, object]:
    entries = tuple(
        {
            "relativePath": path,
            "bytes": raw,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        for path, raw in SYNTHETIC_ENTRIES
    )
    metadata = [
        {
            "path": RUNNER.MODULE_PREFIX + path,
            "creatorSystem": 0 if index % 2 == 0 else 3,
            "externalAttributes": "00000020" if index % 2 == 0 else "81a40000",
            "modeSource": (
                "synthetic_read_only_regular_mode"
                if index % 2 == 0
                else "archive_unix_mode"
            ),
            "effectiveUnixMode": "100444" if index % 2 == 0 else "100644",
        }
        for index, (path, _raw) in enumerate(SYNTHETIC_ENTRIES)
    ]
    return {
        "entryCount": len(entries),
        "fileCount": len(entries),
        "totalUncompressedBytes": sum(len(raw) for _path, raw in SYNTHETIC_ENTRIES),
        "entries": entries,
        "creatorMetadataPolicy": {
            "policyVersion": "2.0",
            "semantics": RUNNER.EXPECTED_CREATOR_POLICY_SEMANTICS,
            "msDosCreatorSystem": 0,
            "unixCreatorSystem": 3,
            "msDosRegularFileCount": 2,
            "unixEntryCount": 2,
            "acceptedDosExternalAttributes": ["20"],
            "allowedDosAttributeMask": "21",
            "syntheticReadOnlyRegularMode": "100444",
            "entryMetadata": metadata,
            "filesystemExtractionAllowed": False,
            "sourceExecutionAllowed": False,
        },
    }


def read_v1_sentinels(v1_directory: Path) -> dict[str, bytes]:
    return {name: (v1_directory / name).read_bytes() for name in V1_NAMES}


def read_v2_sentinels(v2_directory: Path) -> dict[str, bytes]:
    return {name: (v2_directory / name).read_bytes() for name in V2_NAMES}


@contextmanager
def synthetic_execution_environment(
    temporary_root: str,
    *,
    module_failure: Exception | None = None,
    adapter_failure: Exception | None = None,
):
    root = Path(temporary_root)
    archive_relative = "build/synthetic-pion-v4.3.0.zip"
    archive_path = root / archive_relative
    archive_path.parent.mkdir(mode=0o700)
    archive_raw = b"synthetic archive bytes; adapter owns parsing"
    archive_path.write_bytes(archive_raw)
    archive_path.chmod(0o600)

    v1_directory = root / "build/offline-source/pion-ice-v4.3.0/review-v1"
    v1_directory.mkdir(parents=True, mode=0o700)
    for index, name in enumerate(V1_NAMES):
        path = v1_directory / name
        path.write_bytes(f"v1-sentinel-{index}\n".encode())
        path.chmod(0o600)
    v1_before = read_v1_sentinels(v1_directory)
    v2_directory = root / "build/offline-source/pion-ice-v4.3.0/review-v2"
    v2_directory.mkdir(parents=True, mode=0o700)
    for index, name in enumerate(V2_NAMES):
        path = v2_directory / name
        path.write_bytes(f"v2-sentinel-{index}\n".encode())
        path.chmod(0o600)
    v2_before = read_v2_sentinels(v2_directory)

    inspect_mock = mock.Mock(return_value=synthetic_inspection())
    if adapter_failure is not None:
        inspect_mock.side_effect = adapter_failure
    aggregate_mock = mock.Mock(side_effect=AGGREGATOR.aggregate_candidate_inventory)
    adapter = SimpleNamespace(
        inspect_module_zip=inspect_mock,
        aggregate_candidate_inventory=aggregate_mock,
    )
    checker = ModuleType("synthetic_v3_execution_permit_checker")
    checker.validate_repository = mock.Mock(return_value=authority_fixture())
    checker.load_validated_review_modules = mock.Mock(return_value=adapter)
    if module_failure is not None:
        checker.load_validated_review_modules.side_effect = module_failure

    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(RUNNER, "ROOT", root))
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "OUTPUT_PARENT",
                RUNNER.PurePosixPath("build/synthetic-review-v3"),
            )
        )
        stack.enter_context(
            mock.patch.object(RUNNER, "EXPECTED_ARCHIVE_BYTES", len(archive_raw))
        )
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "EXPECTED_ARCHIVE_SHA256",
                hashlib.sha256(archive_raw).hexdigest(),
            )
        )
        stack.enter_context(
            mock.patch.object(RUNNER, "EXPECTED_ENTRY_COUNT", len(SYNTHETIC_ENTRIES))
        )
        stack.enter_context(
            mock.patch.object(RUNNER, "EXPECTED_FILE_COUNT", len(SYNTHETIC_ENTRIES))
        )
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "EXPECTED_TOTAL_UNCOMPRESSED_BYTES",
                sum(len(raw) for _path, raw in SYNTHETIC_ENTRIES),
            )
        )
        stack.enter_context(
            mock.patch.object(RUNNER, "load_checker_trust_root", return_value=checker)
        )
        stack.enter_context(
            mock.patch.object(
                RUNNER,
                "read_pinned_receipt_archive_path",
                return_value=archive_relative,
            )
        )
        yield {
            "root": root,
            "archive": archive_path,
            "output": root / "build/synthetic-review-v3",
            "raw": archive_raw,
            "checker": checker,
            "adapter": adapter,
            "inspectMock": inspect_mock,
            "aggregateMock": aggregate_mock,
            "v1Directory": v1_directory,
            "v1Before": v1_before,
            "v2Directory": v2_directory,
            "v2Before": v2_before,
        }


class G2PionRung3OfflineReviewV3RunnerTests(unittest.TestCase):
    def assert_v1_unchanged(self, environment: dict[str, object]) -> None:
        self.assertEqual(
            read_v1_sentinels(environment["v1Directory"]),
            environment["v1Before"],
        )
        self.assertEqual(
            read_v2_sentinels(environment["v2Directory"]),
            environment["v2Before"],
        )

    def test_00_nonisolated_source_stops_before_non_builtin_imports(self) -> None:
        source = RUNNER_PATH.read_bytes()
        fake_flags = SimpleNamespace(
            isolated=0,
            dont_write_bytecode=0,
            ignore_environment=0,
            no_user_site=0,
            no_site=0,
            optimize=0,
        )
        original_import = builtins.__import__
        observed_imports: list[str] = []

        def import_probe(name, globals_value=None, locals_value=None, fromlist=(), level=0):
            observed_imports.append(name)
            if name not in {"__future__", "sys"}:
                raise AssertionError(f"non-builtin import reached before isolation guard: {name}")
            return original_import(name, globals_value, locals_value, fromlist, level)

        namespace = {"__file__": RUNNER_PATH.name, "__name__": "nonisolated_v3_probe"}
        with (
            mock.patch.object(sys, "flags", fake_flags),
            mock.patch.object(builtins, "__import__", import_probe),
            self.assertRaisesRegex(RuntimeError, "python3 -I -B -S"),
        ):
            exec(
                compile(
                    source,
                    RUNNER_PATH.name,
                    "exec",
                    flags=0,
                    dont_inherit=True,
                    optimize=0,
                ),
                namespace,
                namespace,
            )
        self.assertEqual(observed_imports, ["__future__", "sys"])

    def test_01_checker_bootstrap_is_one_read_nofollow_in_memory_and_pyc_free(self) -> None:
        checker_source = b"""
def validate_repository(root):
    return {"root": str(root)}

def load_validated_review_modules(root):
    return {"root": str(root)}
"""
        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            script = root / "script"
            script.mkdir(mode=0o700)
            checker_path = script / "check_p2p_nat_g2_pion_rung3_execution_permit_v3.py"
            checker_path.write_bytes(checker_source)
            checker_path.chmod(0o600)
            with (
                mock.patch.object(RUNNER, "ROOT", root),
                mock.patch.object(
                    RUNNER,
                    "EXPECTED_CHECKER_RAW_SHA256",
                    hashlib.sha256(checker_source).hexdigest(),
                ),
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("checker path was reopened"),
                ) as path_read,
                mock.patch.object(
                    builtins,
                    "open",
                    side_effect=AssertionError("builtin open is forbidden"),
                ) as builtin_open,
            ):
                checker = RUNNER.load_checker_trust_root()
            self.assertEqual(checker.validate_repository(root), {"root": str(root)})
            self.assertTrue(callable(checker.load_validated_review_modules))
            self.assertEqual(list(root.rglob("__pycache__")), [])
            path_read.assert_not_called()
            builtin_open.assert_not_called()

            with (
                mock.patch.object(RUNNER, "ROOT", root),
                mock.patch.object(RUNNER, "EXPECTED_CHECKER_RAW_SHA256", "0" * 64),
                self.assertRaisesRegex(RUNNER.ReviewError, "raw digest mismatch"),
            ):
                RUNNER.load_checker_trust_root()

        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = root / "checker-target.py"
            target.write_bytes(checker_source)
            target.chmod(0o600)
            (script / "check_p2p_nat_g2_pion_rung3_execution_permit_v3.py").symlink_to(target)
            with (
                mock.patch.object(RUNNER, "ROOT", root),
                self.assertRaises(RUNNER.ReviewError),
            ):
                RUNNER.load_checker_trust_root()

    def test_02_runner_is_separate_from_v1_and_has_no_forbidden_api_imports(self) -> None:
        source = RUNNER_PATH.read_text()
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertTrue(
            {"subprocess", "socket", "urllib", "http", "requests", "importlib"}.isdisjoint(imports)
        )
        self.assertNotIn("run_p2p_nat_g2_pion_rung3_offline_review_once", source)
        self.assertNotIn("load_validated_pure_module", source)
        self.assertNotIn(".g2-pion-ice-v4.3.0-rung3-offline-review-v1.claim", source)
        self.assertNotIn(".g2-pion-ice-v4.3.0-rung3-offline-review-v2.claim", source)
        self.assertNotIn("offline-source-review-result-v2.json", source)
        self.assertNotIn("offline-source-review-manifest-v2.json", source)
        for forbidden_call in (
            "os.system(",
            "os.popen(",
            "os.fork(",
            "os.exec",
            "os.spawn",
        ):
            self.assertNotIn(forbidden_call, source)
        self.assertEqual(RUNNER.OUTPUT_PARENT.name, "review-v3")
        self.assertEqual(RUNNER.CLAIM_NAME, ".g2-pion-ice-v4.3.0-rung3-offline-review-v3.claim")
        self.assertEqual(RUNNER.RESULT_NAME, "offline-source-review-result-v3.json")
        self.assertEqual(RUNNER.MANIFEST_NAME, "offline-source-review-manifest-v3.json")

    def test_03_success_calls_adapter_once_and_publishes_bound_v3_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                outcome = RUNNER.execute_permit()
                environment["inspectMock"].assert_called_once()
                environment["aggregateMock"].assert_called_once()
                call = environment["inspectMock"].call_args
                self.assertEqual(call.args, (environment["raw"],))
                self.assertEqual(call.kwargs["module_prefix"], RUNNER.MODULE_PREFIX)
                self.assertIn("limits", call.kwargs)
                output = environment["output"]
                result_raw = (output / RUNNER.RESULT_NAME).read_bytes()
                manifest_raw = (output / RUNNER.MANIFEST_NAME).read_bytes()
                result = json.loads(result_raw)
                manifest = json.loads(manifest_raw)
                claim = json.loads((output / RUNNER.CLAIM_NAME).read_bytes())

                self.assertEqual(outcome["schemaVersion"], "3.0")
                self.assertEqual(outcome["reviewAdapterInvocationCount"], 2)
                self.assertEqual(outcome["candidateAggregatorInvocationCount"], 1)
                self.assertEqual(
                    outcome["candidateIndependentValidationPassCount"], 1
                )
                self.assertTrue(outcome["postRunReadbackRequired"])
                self.assertEqual(result["schemaVersion"], "3.0")
                self.assertEqual(
                    result["reviewId"],
                    "g2-pion-ice-v4.3.0-rung3-offline-source-review-v3",
                )
                self.assertFalse(result["publicationCompletion"]["complete"])
                self.assertEqual(
                    manifest["manifestId"],
                    "g2-pion-ice-v4.3.0-rung3-offline-source-review-runtime-manifest-v3",
                )
                self.assertTrue(manifest["publication"]["soleCompletionMarker"])
                self.assertTrue(
                    manifest["publication"][
                        "runtimePublicationRequiresPostRunReadbackForCanonicalEvidence"
                    ]
                )
                self.assertEqual(
                    manifest["resultBinding"]["rawSha256"],
                    hashlib.sha256(result_raw).hexdigest(),
                )
                self.assertEqual(claim["schemaVersion"], "3.0")
                self.assertFalse(claim["repositoryOwnerAuthenticationRequired"])
                self.assertFalse(claim["userActionRequired"])
                self.assertTrue(
                    result["executionBoundary"]["productEndpointAuthenticationRequired"]
                )
                candidates = result["patchUnitCandidateInventory"]
                self.assertEqual(candidates["representativeLimitPerRule"], 8)
                first_rule = candidates["patchUnits"][0]["rules"][0]
                self.assertGreaterEqual(first_rule["totalHitCount"], 513)
                self.assertEqual(first_rule["recordedRepresentativeCount"], 8)
                self.assertTrue(first_rule["truncated"])
                self.assertGreater(first_rule["omittedHitCount"], 0)
                self.assertFalse(result["executionBoundary"]["semanticSourceReviewPerformed"])
                self.assertFalse(result["executionBoundary"]["rungThreeComplete"])
                self.assertFalse(result["evidenceBoundary"]["sourceBodiesRecorded"])
                self.assertFalse(result["evidenceBoundary"]["sourceLineDigestsRecorded"])
                self.assertTrue(
                    result["evidenceBoundary"]["completeLexicalCandidateTotalsRecorded"]
                )
                self.assertTrue(
                    result["evidenceBoundary"][
                        "candidateAggregationIndependentlyRecomputedByRunner"
                    ]
                )
                self.assertEqual(
                    result["operationCounters"][
                        "candidateIndependentValidationPassCount"
                    ],
                    1,
                )

                rows = result["sourceInventory"]["entries"]
                self.assertEqual(len(rows), len(SYNTHETIC_ENTRIES))
                self.assertEqual(
                    {row["creatorSystem"] for row in rows},
                    {0, 3},
                )
                self.assertTrue(all("externalAttributes" in row for row in rows))
                self.assertTrue(all("modeSource" in row for row in rows))
                self.assertTrue(all("effectiveUnixMode" in row for row in rows))
                combined = result_raw + manifest_raw
                self.assertLessEqual(len(result_raw), RUNNER.MAXIMUM_JSON_REPORT_BYTES)
                self.assertLessEqual(len(manifest_raw), RUNNER.MAXIMUM_JSON_REPORT_BYTES)
                self.assertNotIn(SOURCE_BODY_SENTINEL.encode(), combined)
                self.assertNotIn(os.fspath(environment["root"]).encode(), combined)
                self.assertEqual(
                    (output / RUNNER.TEMP_RESULT_NAME).read_bytes(),
                    result_raw,
                )
                self.assertEqual(
                    (output / RUNNER.TEMP_MANIFEST_NAME).read_bytes(),
                    manifest_raw,
                )
                self.assertEqual((output / RUNNER.RESULT_NAME).stat().st_nlink, 2)
                self.assertEqual((output / RUNNER.MANIFEST_NAME).stat().st_nlink, 2)
                self.assert_v1_unchanged(environment)

    def test_04_claim_exclusive_precheck_race_loser_never_removes_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            root.chmod(0o700)
            output = root / "review-v3"
            output.mkdir(mode=0o700)
            directory_fd = os.open(output, RUNNER.directory_open_flags())
            barrier = threading.Barrier(2)
            original_name_exists = RUNNER.name_exists
            outcomes: list[tuple[str, object]] = []

            def synchronized_name_exists(fd: int, name: str) -> bool:
                exists = original_name_exists(fd, name)
                if name == RUNNER.TEMP_MANIFEST_NAME:
                    barrier.wait(timeout=5)
                return exists

            def contender() -> None:
                try:
                    outcomes.append(
                        ("won", RUNNER.create_claim(directory_fd, "a" * 64))
                    )
                except BaseException as error:
                    outcomes.append(("lost", error))

            try:
                with mock.patch.object(
                    RUNNER,
                    "name_exists",
                    side_effect=synchronized_name_exists,
                ):
                    threads = [threading.Thread(target=contender) for _index in range(2)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=10)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
                winners = [value for kind, value in outcomes if kind == "won"]
                losers = [value for kind, value in outcomes if kind == "lost"]
                self.assertEqual(len(winners), 1)
                self.assertEqual(len(losers), 1)
                self.assertIsInstance(losers[0], RUNNER.ReviewError)
                first_payload, first_digest = winners[0]
                self.assertEqual((output / RUNNER.CLAIM_NAME).read_bytes(), first_payload)
                self.assertEqual(hashlib.sha256(first_payload).hexdigest(), first_digest)
                self.assertEqual(stat.S_IMODE((output / RUNNER.CLAIM_NAME).stat().st_mode), 0o600)
            finally:
                os.close(directory_fd)

    def test_05_module_failure_retains_claim_and_v1_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(
                temporary_root,
                module_failure=RuntimeError("synthetic module failure"),
            ) as environment:
                with self.assertRaisesRegex(RUNNER.ReviewError, "after permit consumption"):
                    RUNNER.execute_permit()
                output = environment["output"]
                self.assertTrue((output / RUNNER.CLAIM_NAME).exists())
                self.assertFalse((output / RUNNER.RESULT_NAME).exists())
                self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
                environment["inspectMock"].assert_not_called()
                self.assert_v1_unchanged(environment)

    def test_06_archive_failure_retains_claim_and_does_not_call_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                with (
                    mock.patch.object(
                        RUNNER,
                        "open_relative_regular_file",
                        side_effect=RUNNER.ReviewError("synthetic archive failure"),
                    ),
                    self.assertRaisesRegex(RUNNER.ReviewError, "synthetic archive failure"),
                ):
                    RUNNER.execute_permit()
                self.assertTrue((environment["output"] / RUNNER.CLAIM_NAME).exists())
                environment["checker"].load_validated_review_modules.assert_called_once()
                environment["inspectMock"].assert_not_called()
                self.assert_v1_unchanged(environment)

    def test_07_adapter_failure_is_one_call_and_retains_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(
                temporary_root,
                adapter_failure=RuntimeError("synthetic adapter failure"),
            ) as environment:
                with self.assertRaisesRegex(RUNNER.ReviewError, "v3 validation failed"):
                    RUNNER.execute_permit()
                environment["inspectMock"].assert_called_once()
                output = environment["output"]
                self.assertTrue((output / RUNNER.CLAIM_NAME).exists())
                self.assertFalse((output / RUNNER.RESULT_NAME).exists())
                self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
                self.assert_v1_unchanged(environment)

    def test_08_manifest_failure_preserves_partial_result_and_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                original_publish = RUNNER.publish_no_replace
                calls: list[str] = []

                def fail_manifest(
                    directory_fd: int,
                    temporary_name: str,
                    final_name: str,
                    held_fd: int,
                    expected_payload: bytes,
                ) -> None:
                    calls.append(final_name)
                    if final_name == RUNNER.MANIFEST_NAME:
                        raise RUNNER.ReviewError("synthetic manifest publication failure")
                    original_publish(
                        directory_fd,
                        temporary_name,
                        final_name,
                        held_fd,
                        expected_payload,
                    )

                with (
                    mock.patch.object(RUNNER, "publish_no_replace", side_effect=fail_manifest),
                    self.assertRaisesRegex(
                        RUNNER.PublishedReportStateError,
                        "partially published evidence",
                    ),
                ):
                    RUNNER.execute_permit()
                self.assertEqual(calls, [RUNNER.RESULT_NAME, RUNNER.MANIFEST_NAME])
                output = environment["output"]
                self.assertTrue((output / RUNNER.CLAIM_NAME).exists())
                self.assertTrue((output / RUNNER.RESULT_NAME).exists())
                self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
                self.assertEqual(
                    (output / RUNNER.TEMP_RESULT_NAME).read_bytes(),
                    (output / RUNNER.RESULT_NAME).read_bytes(),
                )
                self.assertTrue((output / RUNNER.TEMP_MANIFEST_NAME).exists())
                self.assertEqual((output / RUNNER.RESULT_NAME).stat().st_nlink, 2)
                self.assertEqual((output / RUNNER.TEMP_MANIFEST_NAME).stat().st_nlink, 1)
                environment["inspectMock"].assert_called_once()
                self.assert_v1_unchanged(environment)

    def test_09_check_mode_does_not_inspect_consumption_or_archive(self) -> None:
        checker = ModuleType("synthetic_v3_checker")
        checker.validate_repository = mock.Mock(return_value=authority_fixture())
        checker.load_validated_review_modules = mock.Mock(
            side_effect=AssertionError("modules must not load in check mode")
        )
        with (
            mock.patch.object(RUNNER, "load_checker_trust_root", return_value=checker),
            mock.patch.object(
                RUNNER,
                "open_secure_output_directory",
                side_effect=AssertionError("outputs must not be inspected in check mode"),
            ),
            mock.patch.object(
                RUNNER,
                "open_relative_regular_file",
                side_effect=AssertionError("archive must not open in check mode"),
            ),
        ):
            result = RUNNER.check_permit()
        self.assertEqual(result["permitConsumptionState"], "not_inspected")
        self.assertEqual(result["archiveOpenCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        checker.load_validated_review_modules.assert_not_called()

    def test_10_claim_loser_does_not_remove_winner_temporary_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                output = environment["output"]
                output.mkdir(parents=True, mode=0o700)
                winner_files = {
                    RUNNER.CLAIM_NAME: b"winner-claim\n",
                    RUNNER.TEMP_RESULT_NAME: b"winner-result-temp\n",
                    RUNNER.TEMP_MANIFEST_NAME: b"winner-manifest-temp\n",
                }
                for name, payload in winner_files.items():
                    path = output / name
                    path.write_bytes(payload)
                    path.chmod(0o600)
                with self.assertRaisesRegex(
                    RUNNER.ReviewError,
                    "single-use v3 review cannot start",
                ):
                    RUNNER.execute_permit()
                self.assertEqual(
                    {name: (output / name).read_bytes() for name in winner_files},
                    winner_files,
                )
                environment["checker"].load_validated_review_modules.assert_not_called()
                environment["inspectMock"].assert_not_called()
                self.assert_v1_unchanged(environment)

    def test_11_rejects_malformed_or_leaking_creator_policy(self) -> None:
        authority = authority_fixture()
        archive_metadata = SimpleNamespace(st_size=123)

        def assert_rejected(inspection: dict[str, object]) -> None:
            with self.assertRaises(RUNNER.ReviewError):
                RUNNER.build_review_documents(
                    authority=authority,
                    claim_sha256="d" * 64,
                    archive_metadata=archive_metadata,
                    inspection=inspection,
                    aggregate_candidate_inventory=(
                        AGGREGATOR.aggregate_candidate_inventory
                    ),
                )

        extra_key = copy.deepcopy(synthetic_inspection())
        extra_key["creatorMetadataPolicy"]["sourceBody"] = SOURCE_BODY_SENTINEL
        assert_rejected(extra_key)

        mutations = (
            {
                "creatorSystem": 0,
                "externalAttributes": "ffffffff",
                "modeSource": "archive_unix_mode",
                "effectiveUnixMode": "107777",
            },
            {
                "creatorSystem": 3,
                "externalAttributes": "81ed0000",
                "modeSource": "archive_unix_mode",
                "effectiveUnixMode": "100755",
            },
            {
                "creatorSystem": 0,
                "externalAttributes": "00000020",
                "modeSource": "synthetic_read_only_regular_mode",
                "effectiveUnixMode": "100444",
                "absolutePath": "/tmp/leak",
            },
        )
        for mutation in mutations:
            inspection = copy.deepcopy(synthetic_inspection())
            inspection["creatorMetadataPolicy"]["entryMetadata"][0].update(mutation)
            assert_rejected(inspection)

        unsafe_path = copy.deepcopy(synthetic_inspection())
        unsafe_path["creatorMetadataPolicy"]["entryMetadata"][0]["path"] = (
            RUNNER.MODULE_PREFIX + "../escape.go"
        )
        assert_rejected(unsafe_path)

        count_drift = copy.deepcopy(synthetic_inspection())
        count_drift["creatorMetadataPolicy"]["msDosRegularFileCount"] = 3
        assert_rejected(count_drift)

    def test_12_candidate_zero_eight_nine_and_513_plus_are_exact_and_bounded(self) -> None:
        base = (
            b"Candidate\n"
            b"Debugf secret\n"
            b"OnConnectionStateChange\n"
            b"SetDeadline\n"
            b"udp\n"
            b"Resolver\n"
            b"nonce\n"
        )
        for count in (0, 8, 9, 513):
            with self.subTest(count=count):
                raw = base + (b"Dial\n" * count)
                entries = (("candidate.go", raw),)
                candidate = AGGREGATOR.aggregate_candidate_inventory(entries)
                validated = RUNNER.validate_candidate_inventory(
                    candidate,
                    source_entries=entries,
                )
                rule = validated["patchUnits"][0]["rules"][0]
                self.assertEqual(rule["totalHitCount"], count)
                self.assertEqual(
                    rule["recordedRepresentativeCount"],
                    min(count, RUNNER.REPRESENTATIVE_LIMIT_PER_RULE),
                )
                self.assertEqual(
                    rule["omittedHitCount"],
                    count - min(count, RUNNER.REPRESENTATIVE_LIMIT_PER_RULE),
                )
                self.assertIs(rule["truncated"], count > 8)
                self.assertLessEqual(
                    len(RUNNER.canonical_json_bytes(validated)),
                    RUNNER.MAXIMUM_JSON_REPORT_BYTES,
                )

    def test_13_candidate_output_mutations_fail_closed_and_source_mutation_changes_digest(
        self,
    ) -> None:
        entries = (
            (
                "candidate.go",
                b"Candidate\nDebugf secret\nOnConnectionStateChange\n"
                b"SetDeadline\nudp\nResolver\nnonce\nDial // alpha\n",
            ),
        )
        original = AGGREGATOR.aggregate_candidate_inventory(entries)
        changed_entries = (
            (
                "candidate.go",
                entries[0][1].replace(b"Dial // alpha", b"Dial // beta"),
            ),
        )
        changed = AGGREGATOR.aggregate_candidate_inventory(changed_entries)
        self.assertNotEqual(
            original["patchUnits"][0]["completeObservationSha256"],
            changed["patchUnits"][0]["completeObservationSha256"],
        )
        RUNNER.validate_candidate_inventory(original, source_entries=entries)

        mutations = []
        arithmetic = copy.deepcopy(original)
        arithmetic["totals"]["hitCount"] += 1
        mutations.append(arithmetic)
        bad_digest = copy.deepcopy(original)
        original_digest = bad_digest["patchUnits"][0]["completeObservationSha256"]
        bad_digest["patchUnits"][0]["completeObservationSha256"] = (
            ("0" if original_digest[0] != "0" else "1") + original_digest[1:]
        )
        bad_rank = copy.deepcopy(original)
        bad_rank["patchUnits"][0]["rules"][0]["representatives"][0][
            "rankSha256"
        ] = "0" * 64
        mutations.append(bad_rank)
        bad_path = copy.deepcopy(original)
        bad_path["patchUnits"][0]["rules"][0]["representatives"][0]["path"] = (
            "/absolute.go"
        )
        mutations.append(bad_path)
        extra = copy.deepcopy(original)
        extra["patchUnits"][0]["rules"][0]["representatives"][0]["sourceBody"] = (
            SOURCE_BODY_SENTINEL
        )
        mutations.append(extra)

        nonmatching_line = copy.deepcopy(original)
        nonmatching_representative = (
            nonmatching_line["patchUnits"][0]["rules"][0]["representatives"][0]
        )
        nonmatching_representative["line"] = 1
        nonmatching_representative["rankSha256"] = RUNNER.representative_rank_sha256(
            "candidate.go",
            1,
            "egress-dial",
        )

        omission_entries = (
            (
                "candidate.go",
                b"Candidate\nDebugf secret\nOnConnectionStateChange\n"
                b"SetDeadline\nudp\nResolver\nnonce\nDial\nDial\n",
            ),
        )
        omitted_real_hit = AGGREGATOR.aggregate_candidate_inventory(
            omission_entries
        )
        omitted_rule = omitted_real_hit["patchUnits"][0]["rules"][0]
        self.assertEqual(omitted_rule["totalHitCount"], 2)
        omitted_rule["totalHitCount"] = 1
        omitted_rule["representatives"] = omitted_rule["representatives"][:1]
        omitted_rule["recordedRepresentativeCount"] = 1
        omitted_rule["omittedHitCount"] = 0
        omitted_rule["truncated"] = False
        omitted_unit = omitted_real_hit["patchUnits"][0]
        omitted_unit["totalHitCount"] -= 1
        omitted_unit["recordedRepresentativeCount"] -= 1
        omitted_unit["omittedHitCount"] = (
            omitted_unit["totalHitCount"]
            - omitted_unit["recordedRepresentativeCount"]
        )
        omitted_unit["truncated"] = omitted_unit["omittedHitCount"] > 0
        omitted_totals = omitted_real_hit["totals"]
        omitted_totals["hitCount"] -= 1
        omitted_totals["recordedRepresentativeCount"] -= 1
        omitted_totals["omittedHitCount"] = (
            omitted_totals["hitCount"]
            - omitted_totals["recordedRepresentativeCount"]
        )
        omitted_totals["truncated"] = omitted_totals["omittedHitCount"] > 0

        nine_hit_entries = (
            (
                "candidate.go",
                b"Candidate\nDebugf secret\nOnConnectionStateChange\n"
                b"SetDeadline\nudp\nResolver\nnonce\n" + (b"Dial\n" * 9),
            ),
        )
        non_lowest_representatives = AGGREGATOR.aggregate_candidate_inventory(
            nine_hit_entries
        )
        nine_hit_rule = non_lowest_representatives["patchUnits"][0]["rules"][0]
        all_matching_representatives = [
            {
                "path": "candidate.go",
                "line": line,
                "ruleId": "egress-dial",
                "rankSha256": RUNNER.representative_rank_sha256(
                    "candidate.go", line, "egress-dial"
                ),
            }
            for line in range(8, 17)
        ]
        all_matching_representatives.sort(
            key=RUNNER.candidate_representative_sort_key
        )
        self.assertEqual(
            nine_hit_rule["representatives"],
            all_matching_representatives[:8],
        )
        nine_hit_rule["representatives"] = all_matching_representatives[1:]

        for candidate in mutations:
            with self.subTest(mutation=len(mutations)):
                with self.assertRaises(RUNNER.ReviewError):
                    RUNNER.validate_candidate_inventory(
                        candidate,
                        source_entries=entries,
                    )
        independent_counterexamples = (
            ("valid_64hex_fake_digest", bad_digest, entries),
            ("valid_rank_nonmatching_line", nonmatching_line, entries),
            ("internally_consistent_omitted_real_hit", omitted_real_hit, omission_entries),
            (
                "valid_rank_non_lowest_matching_representatives",
                non_lowest_representatives,
                nine_hit_entries,
            ),
        )
        for label, candidate, candidate_entries in independent_counterexamples:
            with self.subTest(independent_counterexample=label):
                with self.assertRaisesRegex(
                    RUNNER.ReviewError,
                    "independent bounded full observation",
                ):
                    RUNNER.validate_candidate_inventory(
                        candidate,
                        source_entries=candidate_entries,
                    )

    def test_14_postclaim_foreign_temp_is_not_deleted_without_owned_fd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                foreign_payload = b"foreign-concurrent-temp\n"

                def create_foreign_then_fail(_root: Path):
                    path = environment["output"] / RUNNER.TEMP_RESULT_NAME
                    path.write_bytes(foreign_payload)
                    path.chmod(0o600)
                    raise RuntimeError("synthetic loader failure after foreign temp")

                environment["checker"].load_validated_review_modules.side_effect = (
                    create_foreign_then_fail
                )
                with self.assertRaisesRegex(RUNNER.ReviewError, "after permit consumption"):
                    RUNNER.execute_permit()
                self.assertEqual(
                    (environment["output"] / RUNNER.TEMP_RESULT_NAME).read_bytes(),
                    foreign_payload,
                )
                self.assertTrue((environment["output"] / RUNNER.CLAIM_NAME).exists())
                self.assert_v1_unchanged(environment)

    def test_15_temp_name_swap_cannot_publish_false_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                original_link = RUNNER.os.link
                foreign_payload = b"foreign-unbound-publication-bytes\n"
                swapped = False

                def swap_then_link(source: str, target: str, **kwargs) -> None:
                    nonlocal swapped
                    if not swapped and target == RUNNER.RESULT_NAME:
                        swapped = True
                        temporary = environment["output"] / source
                        temporary.unlink()
                        temporary.write_bytes(foreign_payload)
                        temporary.chmod(0o600)
                    original_link(source, target, **kwargs)

                with (
                    mock.patch.object(RUNNER.os, "link", side_effect=swap_then_link),
                    self.assertRaises(RUNNER.PublishedReportStateError),
                ):
                    RUNNER.execute_permit()
                self.assertTrue(swapped)
                self.assertTrue((environment["output"] / RUNNER.CLAIM_NAME).exists())
                self.assertFalse((environment["output"] / RUNNER.MANIFEST_NAME).exists())
                self.assertEqual(
                    (environment["output"] / RUNNER.RESULT_NAME).read_bytes(),
                    foreign_payload,
                )
                self.assertEqual(
                    (environment["output"] / RUNNER.TEMP_RESULT_NAME).read_bytes(),
                    foreign_payload,
                )
                self.assert_v1_unchanged(environment)

    def test_16_base_exception_after_link_is_partial_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                original_link = RUNNER.os.link
                injected = False

                def link_then_interrupt(source: str, target: str, **kwargs) -> None:
                    nonlocal injected
                    original_link(source, target, **kwargs)
                    if not injected and target == RUNNER.RESULT_NAME:
                        injected = True
                        raise KeyboardInterrupt("synthetic post-link interrupt")

                with (
                    mock.patch.object(RUNNER.os, "link", side_effect=link_then_interrupt),
                    self.assertRaisesRegex(
                        RUNNER.PublishedReportStateError,
                        "publication completion is uncertain",
                    ),
                ):
                    RUNNER.execute_permit()
                self.assertTrue(injected)
                output = environment["output"]
                self.assertTrue((output / RUNNER.CLAIM_NAME).exists())
                self.assertTrue((output / RUNNER.RESULT_NAME).exists())
                self.assertTrue((output / RUNNER.TEMP_RESULT_NAME).exists())
                self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
                self.assert_v1_unchanged(environment)

    def test_17_exception_after_publish_return_is_reobserved_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            with synthetic_execution_environment(temporary_root) as environment:
                original_publish = RUNNER.publish_no_replace
                interrupted = False

                def publish_then_interrupt(*args, **kwargs) -> None:
                    nonlocal interrupted
                    original_publish(*args, **kwargs)
                    if not interrupted:
                        interrupted = True
                        raise KeyboardInterrupt("synthetic caller-side interrupt")

                with (
                    mock.patch.object(
                        RUNNER,
                        "publish_no_replace",
                        side_effect=publish_then_interrupt,
                    ),
                    self.assertRaisesRegex(
                        RUNNER.PublishedReportStateError,
                        "partially published evidence",
                    ),
                ):
                    RUNNER.execute_permit()
                self.assertTrue(interrupted)
                output = environment["output"]
                self.assertTrue((output / RUNNER.CLAIM_NAME).exists())
                self.assertTrue((output / RUNNER.RESULT_NAME).exists())
                self.assertTrue((output / RUNNER.TEMP_RESULT_NAME).exists())
                self.assertFalse((output / RUNNER.MANIFEST_NAME).exists())
                self.assert_v1_unchanged(environment)


if __name__ == "__main__":
    unittest.main(verbosity=2)
