#!/usr/bin/env python3
"""Focused tests for the exact read-only 277-input combined v8 checker."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "combined fixed-point v8 tests require unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import ast
from contextlib import contextmanager, nullcontext, redirect_stderr
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_combined_fixed_point_v8.py"


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "combined_fixed_point_v8_tests_target",
        CHECKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("checker load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()


def canonical_bytes(value) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


@contextmanager
def held_v1_checker():
    with CHECKER.PinnedCodeFile(
        ROOT,
        CHECKER.V7_CHECKER_PATH,
        CHECKER.V7_CHECKER_RAW_SHA256,
    ) as v7_held:
        v7 = CHECKER.harden_checker_module(
            CHECKER.load_v7_checker(v7_held)
        )
        with v7.PinnedCodeFile(
            ROOT,
            v7.V6_CHECKER_PATH,
            v7.V6_CHECKER_RAW_SHA256,
        ) as v6_held:
            v6 = v7.load_v6_checker(v6_held)
            with v6.PinnedCodeFile(
                ROOT,
                v6.V5_CHECKER_PATH,
                v6.V5_CHECKER_RAW_SHA256,
            ) as v5_held:
                v5 = v6.load_v5_checker(v5_held)
                with v5.PinnedCodeFile(
                    ROOT,
                    v5.V4_CHECKER_PATH,
                    v5.V4_CHECKER_RAW_SHA256,
                ) as v4_held:
                    v4 = v5.load_v4_checker(v4_held)
                    with v4.PinnedCodeFile(
                        ROOT,
                        v4.V1_CHECKER_PATH,
                        v4.V1_CHECKER_RAW_SHA256,
                    ) as v1_held:
                        yield v4.load_v1_checker(v1_held)


@contextmanager
def held_wave9_documents(*, include_held=False):
    with CHECKER.PinnedCodeFile(
        ROOT,
        CHECKER.V7_CHECKER_PATH,
        CHECKER.V7_CHECKER_RAW_SHA256,
    ) as v7_held:
        v7 = CHECKER.load_v7_checker(v7_held)
        v7 = CHECKER.harden_checker_module(v7)
        with v7.PinnedCodeFile(
            ROOT,
            CHECKER.V6_CHECKER_PATH,
            CHECKER.V6_CHECKER_RAW_SHA256,
        ) as v6_held:
            v6 = v7.load_v6_checker(v6_held)
            with v6.PinnedCodeFile(
                ROOT,
                CHECKER.V5_CHECKER_PATH,
                CHECKER.V5_CHECKER_RAW_SHA256,
            ) as v5_held:
                v5 = v6.load_v5_checker(v5_held)
                with v5.PinnedCodeFile(
                    ROOT,
                    CHECKER.V4_CHECKER_PATH,
                    CHECKER.V4_CHECKER_RAW_SHA256,
                ) as v4_held:
                    v4 = v5.load_v4_checker(v4_held)
                    with v4.PinnedCodeFile(
                        ROOT,
                        v4.V1_CHECKER_PATH,
                        v4.V1_CHECKER_RAW_SHA256,
                    ) as v1_held:
                        v1 = v4.load_v1_checker(v1_held)
                        with v1.PinnedRunnerFile(ROOT) as provider_held:
                            runner = v1.load_pinned_runner(provider_held)
                            with runner.HeldInputSet(
                                ROOT,
                                (
                                    CHECKER.wave9_control_bindings()
                                    + CHECKER.wave9_auxiliary_evidence_bindings()
                                ),
                            ) as controls:
                                documents = CHECKER.parse_wave9_documents(
                                    runner,
                                    controls,
                                )
                                if include_held:
                                    yield v4, runner, documents, controls
                                else:
                                    yield v4, runner, documents


def assert_wave9_mutation_fails(
    testcase: unittest.TestCase,
    mutate,
    expected_code: str,
) -> None:
    with held_wave9_documents() as (v4, runner, documents):
        mutated = copy.deepcopy(documents)
        mutate(mutated)
        with (
            mock.patch.object(
                CHECKER,
                "verify_wave9_content_bindings",
            ),
            testcase.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught,
        ):
            CHECKER.wave9_request_resources(v4, runner, mutated)
    testcase.assertEqual(str(caught.exception), expected_code)


class CombinedFixedPointV8Tests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.candidate = CHECKER.generate_candidate(ROOT)

    def test_01_exact_self_predecessor_and_wave9_control_pins(self):
        raw = CHECKER_PATH.read_bytes()
        self.assertEqual(
            hashlib.sha256(
                CHECKER.normalized_self_bytes(raw)
            ).hexdigest(),
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / CHECKER.V7_CHECKER_PATH).read_bytes()
            ).hexdigest(),
            CHECKER.V7_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                CHECKER.normalized_self_bytes(
                    (ROOT / CHECKER.V7_CHECKER_PATH).read_bytes()
                )
            ).hexdigest(),
            CHECKER.V7_CHECKER_NORMALIZED_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / CHECKER.V6_CHECKER_PATH).read_bytes()
            ).hexdigest(),
            CHECKER.V6_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / CHECKER.V5_CHECKER_PATH).read_bytes()
            ).hexdigest(),
            CHECKER.V5_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / CHECKER.V4_CHECKER_PATH).read_bytes()
            ).hexdigest(),
            CHECKER.V4_CHECKER_RAW_SHA256,
        )
        for path, digest in CHECKER.WAVE9_CONTROL_SHA256.items():
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                digest,
            )

    def test_02_candidate_content_and_authority_are_derived_and_closed(self):
        candidate = self.candidate
        self.assertEqual(candidate["schemaVersion"], "8.0")
        self.assertTrue(candidate["verificationOnly"])
        self.assertFalse(candidate["recordModeExposed"])
        self.assertTrue(candidate["authority"])
        self.assertTrue(
            all(value is False for value in candidate["authority"].values())
        )
        self.assertFalse(
            candidate["authority"]["osSyscallSandboxProvided"]
        )
        self.assertEqual(
            candidate["checkerVerification"][
                "providerFacadeVerificationScope"
            ],
            "trusted_pinned_normal_reconstruction_path",
        )
        without = dict(candidate)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            hashlib.sha256(canonical_bytes(without)).hexdigest(),
        )

    def test_03_exact_277_input_composition_and_tuple_order(self):
        inputs = self.candidate["inputSet"]
        self.assertEqual(
            {
                key: inputs[key]
                for key in (
                    "heldSourceInputCount",
                    "rootArchiveCount",
                    "resourceCount",
                    "modCount",
                    "zipCount",
                    "wave1ResourceCount",
                    "wave2ResourceCount",
                    "wave3ResourceCount",
                    "wave4ResourceCount",
                    "wave5ResourceCount",
                    "wave6ResourceCount",
                    "wave7ResourceCount",
                    "wave8ResourceCount",
                    "wave9ResourceCount",
                    "uniqueModuleVersionTupleCount",
                )
            },
            {
                "heldSourceInputCount": 277,
                "rootArchiveCount": 1,
                "resourceCount": 276,
                "modCount": 138,
                "zipCount": 138,
                "wave1ResourceCount": 38,
                "wave2ResourceCount": 30,
                "wave3ResourceCount": 32,
                "wave4ResourceCount": 32,
                "wave5ResourceCount": 30,
                "wave6ResourceCount": 36,
                "wave7ResourceCount": 30,
                "wave8ResourceCount": 28,
                "wave9ResourceCount": 20,
                "uniqueModuleVersionTupleCount": 138,
            },
        )
        rows = inputs["sourceBindings"]
        self.assertEqual(inputs["aggregateRawByteSize"], 243_215_320)
        self.assertEqual(len(rows), 277)
        self.assertEqual(len({row["path"] for row in rows}), 277)
        pair_orders = sorted(
            {
                row["tupleOrder"]
                for row in rows
                if row["kind"] != "root_zip"
            }
        )
        self.assertEqual(pair_orders, list(range(1, 139)))
        self.assertEqual(
            sorted(
                {
                    row["tupleOrder"]
                    for row in rows
                    if row["wave"] == "wave9"
                }
            ),
            list(range(129, 139)),
        )

    def test_04_fixed_point_and_frontier_are_recomputed_not_expected(self):
        candidate = self.candidate
        graph = candidate["graphDiscovery"]
        derived = candidate["derivedResult"]
        frontier = graph["exactFrontier"]
        self.assertIs(
            derived["fixedPointReached"],
            graph["fixedPointReached"],
        )
        self.assertEqual(derived["frontierTupleCount"], len(frontier))
        self.assertEqual(
            derived["frontierSha256"],
            hashlib.sha256(canonical_bytes(frontier)).hexdigest(),
        )
        self.assertIs(
            candidate["checkerVerification"][
                "calculatedFixedPointCandidate"
            ],
            graph["fixedPointReached"],
        )
        if frontier:
            self.assertEqual(candidate["route"], "next_wave_required")
        elif (
            graph.get("unmappedExternalImportCount", 0)
            or graph.get("unresolvedDeclaredExternalImportCount", 0)
        ):
            self.assertEqual(
                candidate["route"],
                "external_import_resolution_required",
            )
        else:
            self.assertTrue(graph["fixedPointReached"])
            self.assertEqual(candidate["route"], "fixed_point_candidate")

        assigned_names = {
            target.id
            for node in ast.walk(ast.parse(CHECKER_PATH.read_text()))
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            if isinstance(target, ast.Name)
        }
        self.assertFalse(
            {
                "V8_GRAPH_SHA256",
                "V8_FRONTIER_SHA256",
                "V8_FIXED_POINT_REACHED",
                "EXPECTED_GRAPH_SHA256",
                "EXPECTED_FRONTIER_SHA256",
                "EXPECTED_FIXED_POINT_REACHED",
            }
            & assigned_names
        )
        base_graph = {
            "independentReproductionPassed": True,
            "reconstructionCount": 2,
        }
        with held_v1_checker() as v1:
            next_route = v1.route_for_graph(
                {**base_graph, "newTupleCount": 1}
            )
            external_route = v1.route_for_graph(
                {
                    **base_graph,
                    "newTupleCount": 0,
                    "unmappedExternalImportCount": 1,
                }
            )
            fixed_route = v1.route_for_graph(
                {
                    **base_graph,
                    "newTupleCount": 0,
                    "unmappedExternalImportCount": 0,
                    "unresolvedDeclaredExternalImportCount": 0,
                    "fixedPointReached": True,
                }
            )
            self.assertEqual(
                next_route["route"],
                "next_wave_required",
            )
            self.assertEqual(
                external_route["route"],
                "external_import_resolution_required",
            )
            self.assertEqual(
                fixed_route["route"],
                "fixed_point_candidate",
            )
            contradictory_cases = (
                (
                    {
                        "exactFrontier": [{}],
                        "newTupleCount": 1,
                        "unmappedExternalImportCount": 0,
                        "unresolvedDeclaredExternalImportCount": 0,
                        "fixedPointReached": True,
                    },
                    next_route,
                ),
                (
                    {
                        "exactFrontier": [],
                        "newTupleCount": 0,
                        "unmappedExternalImportCount": 1,
                        "unresolvedDeclaredExternalImportCount": 0,
                        "fixedPointReached": True,
                    },
                    external_route,
                ),
                (
                    {
                        "exactFrontier": [],
                        "newTupleCount": 0,
                        "unmappedExternalImportCount": 0,
                        "unresolvedDeclaredExternalImportCount": 0,
                        "fixedPointReached": False,
                    },
                    fixed_route,
                ),
                (
                    {
                        "exactFrontier": [],
                        "newTupleCount": 0,
                        "unmappedExternalImportCount": True,
                        "unresolvedDeclaredExternalImportCount": 0,
                        "fixedPointReached": False,
                    },
                    external_route,
                ),
                (
                    {
                        "exactFrontier": [],
                        "newTupleCount": 0,
                        "unmappedExternalImportCount": 0,
                        "unresolvedDeclaredExternalImportCount": True,
                        "fixedPointReached": False,
                    },
                    external_route,
                ),
                (
                    {
                        "exactFrontier": [{}],
                        "newTupleCount": 1,
                        "unmappedExternalImportCount": 0,
                        "unresolvedDeclaredExternalImportCount": 0,
                        "fixedPointReached": False,
                    },
                    fixed_route,
                ),
            )
            for inconsistent_graph, inconsistent_route in contradictory_cases:
                with self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught:
                    CHECKER.derive_and_validate_graph_result(
                        CHECKER,
                        inconsistent_graph,
                        inconsistent_route,
                    )
                self.assertEqual(
                    str(caught.exception),
                    "E_DERIVED_RESULT",
                )

    def test_05_reconstruction_and_archive_counters_are_separate(self):
        verification = self.candidate["checkerVerification"]
        self.assertEqual(
            (
                verification["directFullInputReconstructionCount"],
                verification["inheritedFullInputReconstructionCount"],
                verification["totalFullInputReconstructionCount"],
            ),
            (2, 12, 14),
        )
        counters = self.candidate["operationCounters"]
        self.assertEqual(
            (
                counters["directArchiveOpenCount"],
                counters["inheritedArchiveOpenCount"],
                counters["totalArchiveOpenCount"],
                counters["archiveOpenCount"],
            ),
            (278, 1088, 1366, 1366),
        )
        self.assertEqual(
            self.candidate["coverage"]["archiveCount"],
            139,
        )
        self.assertEqual(counters["heldTerminalEvidenceCount"], 59)
        self.assertEqual(counters["heldAuxiliaryEvidenceCount"], 3)
        self.assertEqual(counters["heldToolInputCount"], 7)
        self.assertEqual(counters["transitiveDistinctToolPathCount"], 9)
        self.assertEqual(len(self.candidate["toolBindings"]), 7)
        self.assertNotIn(
            CHECKER.V7_TESTS_PATH,
            {
                binding["path"]
                for binding in self.candidate["toolBindings"]
            },
        )
        self.assertEqual(
            verification["v7TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(verification["v7TestsLiveHeld"])
        self.assertEqual(
            self.candidate["predecessorVerification"][
                "v7TestsBindingScope"
            ],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(
            self.candidate["predecessorVerification"][
                "v7TestsLiveHeld"
            ]
        )
        self.assertEqual(
            verification[
                "wave9PinnedLegacyBuildCompatibilityCount"
            ],
            4,
        )
        self.assertEqual(
            counters["wave9PinnedLegacyBuildCompatibilityCount"],
            4,
        )
        self.assertEqual(
            self.candidate["wave9LegacyBuildCompatibilityPolicy"],
            {
                "configuredProfileInclusionEquivalent": True,
                "directReconstructionApplicationCount": 4,
                "expectedExpression":
                    CHECKER.WAVE9_LEGACY_BUILD_EXPRESSION,
                "fallbackErrorCode": "E_BUILD_CONSTRAINT",
                "fallbackErrorPhase": "source_inventory",
                "go111TrailingWordOrSemanticsChecked": True,
                "normalizedSourceSha256":
                    CHECKER.WAVE9_LEGACY_BUILD_NORMALIZED_SHA256,
                "originalLineOccurrenceCount": 1,
                "originalProviderParserTriedFirst": True,
                "rawSourceSha256":
                    CHECKER.WAVE9_LEGACY_BUILD_SOURCE_SHA256,
                "sourceBytesModified": False,
            },
        )
        self.assertTrue(
            verification[
                "wave9HistoricalExact38FrozenSnapshotDescriptorSetBound"
            ]
        )
        self.assertTrue(
            verification["wave9LiveTerminalControlMetadataVerified"]
        )
        self.assertTrue(
            verification["wave9LiveFinalAndAcceptedInventoriesVerified"]
        )
        self.assertTrue(
            verification[
                "wave9FinalNamespaceReverifiedAfterReconstruction"
            ]
        )
        self.assertEqual(
            self.candidate["auxiliaryEvidenceBindings"],
            [
                {
                    "path": CHECKER.WAVE9_ACQUISITION_CLAIM_PATH,
                    "rawSha256":
                        CHECKER.WAVE9_ACQUISITION_CLAIM_RAW_SHA256,
                },
                {
                    "path": CHECKER.WAVE9_EVIDENCE_PATH,
                    "rawSha256":
                        CHECKER.WAVE9_ACQUISITION_EVIDENCE_RAW_SHA256,
                },
                {
                    "path": CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    "rawSha256":
                        CHECKER.WAVE9_READBACK_CLAIM_RAW_SHA256,
                },
            ],
        )

    def test_06_wave9_controls_produce_exact_20_resources(self):
        with held_wave9_documents() as (v4, runner, documents):
            resources = CHECKER.wave9_request_resources(
                v4,
                runner,
                documents,
            )
        self.assertEqual(len(resources), 20)
        self.assertEqual(
            sum(row["kind"] == "mod" for row in resources),
            10,
        )
        self.assertEqual(
            sum(row["kind"] == "zip" for row in resources),
            10,
        )
        self.assertEqual(
            sorted({row["tupleOrder"] for row in resources}),
            list(range(129, 139)),
        )
        duplicate_mod_a = resources[4]
        duplicate_mod_b = resources[6]
        self.assertEqual(
            duplicate_mod_a["kind"],
            duplicate_mod_b["kind"],
        )
        self.assertEqual(duplicate_mod_a["kind"], "mod")
        self.assertEqual(
            duplicate_mod_a["rawSha256"],
            duplicate_mod_b["rawSha256"],
        )
        self.assertNotEqual(
            duplicate_mod_a["path"],
            duplicate_mod_b["path"],
        )
        self.assertNotEqual(
            duplicate_mod_a["version"],
            duplicate_mod_b["version"],
        )
        for field in ("tupleId", "path", "version"):
            with self.subTest(duplicate_field=field):
                mutated = copy.deepcopy(resources)
                mutated[6][field] = mutated[4][field]
                with self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught:
                    CHECKER.validate_wave9_duplicate_mod_boundary(
                        mutated
                    )
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE9_DUPLICATE_MOD",
                )

    def test_07_unknown_acquisition_authority_fails_closed(self):
        assert_wave9_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE9_PERMIT_PATH][
                "authority"
            ].__setitem__("unknownAuthority", False),
            "E_WAVE9_PERMIT",
        )

    def test_08_accepted_raw_cross_document_mutation_fails_closed(self):
        def mutate(documents):
            documents[CHECKER.WAVE9_READBACK_PATH]["verified"][
                "resources"
            ][0]["rawSha256"] = "0" * 64

        assert_wave9_mutation_fails(
            self,
            mutate,
            "E_WAVE9_RESOURCE",
        )

    def test_09_selection_and_frozen38_mutations_fail_closed(self):
        def mutate_selection(documents):
            documents[CHECKER.WAVE9_PERMIT_PATH][
                "requestContract"
            ]["resources"][0]["selectedByGraphAlgorithm"] = True

        def mutate_frozen_count(documents):
            documents[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["frozenFileCount"] = 37

        assert_wave9_mutation_fails(
            self,
            mutate_selection,
            "E_WAVE9_PERMIT",
        )
        assert_wave9_mutation_fails(
            self,
            mutate_frozen_count,
            "E_WAVE9_READBACK_PERMIT",
        )

    def test_10_retained_readback_boundary_mutation_fails_closed(self):
        def mutate(documents):
            documents[CHECKER.WAVE9_READBACK_PATH][
                "currentPathIdentityGuaranteedThroughManifestPublication"
            ] = True

        assert_wave9_mutation_fails(
            self,
            mutate,
            "E_WAVE9_READBACK",
        )

    def test_11_static_surface_is_offline_read_only_and_auth_free(self):
        source = CHECKER_PATH.read_text()
        self.assertIn(
            "trusted pinned normal reconstruction path invokes zero",
            source,
        )
        self.assertIn("not an OS syscall sandbox", source)
        tree = ast.parse(source)
        forbidden_imports = {
            "ftplib",
            "http",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(
                    all(
                        alias.name.split(".")[0] not in forbidden_imports
                        for alias in node.names
                    )
                )
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(
                    (node.module or "").split(".")[0],
                    forbidden_imports,
                )
            if isinstance(node, ast.Call) and isinstance(
                node.func,
                ast.Attribute,
            ):
                if (
                    node.func.attr == "replace"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "text"
                ):
                    self.assertEqual(len(node.args), 2)
                    self.assertEqual(
                        {
                            argument.id
                            for argument in node.args
                            if isinstance(argument, ast.Name)
                        },
                        {
                            "WAVE9_LEGACY_BUILD_ORIGINAL_LINE",
                            "WAVE9_LEGACY_BUILD_NORMALIZED_LINE",
                        },
                    )
                    continue
                self.assertNotIn(
                    node.func.attr,
                    {
                        "mkdir",
                        "makedirs",
                        "rename",
                        "replace",
                        "unlink",
                        "write_bytes",
                        "write_text",
                    },
                )
        mutation_flags = {
            "O_APPEND",
            "O_CREAT",
            "O_EXCL",
            "O_RDWR",
            "O_TMPFILE",
            "O_TRUNC",
            "O_WRONLY",
        }
        dynamic_open_count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                self.fail("built-in open is outside the pinned read surface")
            if not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "open"
            ):
                continue
            self.assertIsInstance(node.func.value, ast.Name)
            self.assertEqual(node.func.value.id, "os")
            self.assertGreaterEqual(len(node.args), 2)
            flags = node.args[1]
            names = {
                child.attr
                for child in ast.walk(flags)
                if isinstance(child, ast.Attribute)
            } | {
                child.id
                for child in ast.walk(flags)
                if isinstance(child, ast.Name)
            }
            self.assertFalse(names & mutation_flags)
            if "flags" in names:
                dynamic_open_count += 1
        self.assertEqual(dynamic_open_count, 2)
        self.assertIn("flags & write_mask == 0", source)
        self.assertNotIn("os.write(", source)
        for token in (
            "--execute",
            "--record",
            "input(",
        ):
            self.assertNotIn(token, source)
        counters = self.candidate["operationCounters"]
        for key in (
            "archiveExtractionCount",
            "dependencySourceLoadCount",
            "dependencySourceExecutionCount",
            "dependencySourceCompileCount",
            "subprocessCount",
            "networkOperationCount",
            "fileWriteCount",
        ):
            self.assertEqual(counters[key], 0)
        error = json.loads(CHECKER.error_document_bytes())
        self.assertFalse(error["externalAuthenticationRequired"])
        self.assertFalse(error["userActionRequired"])
        for exception in (
            RuntimeError("sensitive runtime detail"),
            KeyError("sensitive key detail"),
            TypeError("sensitive type detail"),
        ):
            with self.subTest(exception=type(exception).__name__):
                sink = type("Sink", (), {})()
                sink.buffer = io.BytesIO()
                stderr = io.StringIO()
                with (
                    mock.patch.object(
                        CHECKER,
                        "generate_candidate",
                        side_effect=exception,
                    ),
                    mock.patch.object(CHECKER.sys, "stdout", sink),
                    redirect_stderr(stderr),
                ):
                    exit_code = CHECKER.main([])
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    sink.buffer.getvalue(),
                    CHECKER.error_document_bytes(),
                )
                self.assertEqual(stderr.getvalue(), "")
                self.assertNotIn(
                    b"sensitive",
                    sink.buffer.getvalue(),
                )

    def test_12_tool_hardlink_alias_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = script / "tool.py"
            target.write_bytes(b"VALUE = 1\n")
            os.link(target, script / "alias.py")
            with self.assertRaises(CHECKER.CombinedCheckFailure):
                CHECKER.PinnedCodeFile(
                    root,
                    "script/tool.py",
                    hashlib.sha256(target.read_bytes()).hexdigest(),
                )

    def test_13_identity_h1_must_match_request_permit_and_readback(self):
        def mutate(documents):
            documents[CHECKER.WAVE9_DECISION_PATH][
                "identityResolution"
            ]["tuples"][0]["goModH1"] = "h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAA"

        assert_wave9_mutation_fails(
            self,
            mutate,
            "E_WAVE9_RESOURCE",
        )

    def test_14_wave9_claim_tool_authority_and_barrier_pins_fail_closed(self):
        cases = (
            (
                "acquisition claim",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["acquisitionClaim"].__setitem__("rawSha256", "0" * 64),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "acquisition tool",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["acquisitionAuthority"][8].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "readback claim",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "readbackClaim"
                ].__setitem__("rawSha256", "0" * 64),
                "E_WAVE9_READBACK",
            ),
            (
                "readback authority",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "authorityBinding"
                ]["recorder"].__setitem__("rawSha256", "0" * 64),
                "E_WAVE9_READBACK",
            ),
            (
                "readback barriers",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "retainedFdPreManifestBarriers"
                ].reverse(),
                "E_WAVE9_READBACK",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label):
                assert_wave9_mutation_fails(
                    self,
                    mutate,
                    expected,
                )

    def test_15_v7_predecessor_deep_binding_mutations_fail_closed(self):
        class Runner:
            @staticmethod
            def canonical_json_bytes(value):
                if type(value) is list:
                    return b"source" if len(value) == 257 else b"frontier"
                return b"candidate"

        frontier = [{} for _ in range(10)]
        source_bindings = [
            {
                "kind": "root_zip",
                "module": "root",
                "path": "root.zip",
                "rawSha256": "0" * 64,
                "tupleId": "root",
                "tupleOrder": 0,
                "version": "local",
                "wave": "root",
            }
        ]
        ordinal = 0
        for order in range(1, 129):
            wave = (
                "wave1"
                if order <= 19
                else "wave2"
                if order <= 34
                else "wave3"
                if order <= 50
                else "wave4"
                if order <= 66
                else "wave5"
                if order <= 81
                else "wave6"
                if order <= 99
                else "wave7"
                if order <= 114
                else "wave8"
            )
            for kind in ("mod", "zip"):
                ordinal += 1
                source_bindings.append(
                    {
                        "kind": kind,
                        "module": f"example.invalid/module-{order}",
                        "path": f"source/{ordinal}.{kind}",
                        "rawSha256": f"{ordinal:064x}",
                        "tupleId": f"tuple-{order}",
                        "tupleOrder": order,
                        "version": "v1.0.0",
                        "wave": wave,
                    }
                )
        candidate = {
            "contentBinding": {
                "algorithm": "sha256",
                "canonicalization":
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf",
                "scope": "candidate_without_contentBinding",
                "sha256": CHECKER.V7_CANDIDATE_CONTENT_SHA256,
            },
            "documentType": (
                "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
                "wave5-wave6-wave7-wave8-fixed-point-candidate"
            ),
            "schemaVersion": "7.0",
            "status": "combined_graph_discovery_complete_next_wave_required",
            "result": (
                "combined_graph_recomputed_twice_from_exact_"
                "wave1_through_wave8_source_bytes"
            ),
            "route": "next_wave_required",
            "nextAction": (
                "prepare_separate_versioned_dependency_wave_identity_and_"
                "acquisition_decision"
            ),
            "inputSet": {
                "heldSourceInputCount": 257,
                "combinedInputSetSha256": CHECKER.V7_INPUT_SET_SHA256,
                "sourceBindings": source_bindings,
            },
            "graphDiscovery": {
                "fixedPointReached": False,
                "newTupleCount": 10,
                "graphSha256": CHECKER.V7_GRAPH_SHA256,
                "exactFrontier": frontier,
            },
            "derivedResult": {
                "fixedPointReached": False,
                "frontierTupleCount": 10,
                "frontierSha256": CHECKER.V7_FRONTIER_SHA256,
            },
            "authority": copy.deepcopy(CHECKER.V7_AUTHORITY),
        }
        predecessor = {
            "checkerNormalizedSha256":
                CHECKER.V7_CHECKER_NORMALIZED_SHA256,
            "checkerPath": CHECKER.V7_CHECKER_PATH,
            "checkerRawSha256": CHECKER.V7_CHECKER_RAW_SHA256,
            "testsPath": CHECKER.V7_TESTS_PATH,
            "testsRawSha256": CHECKER.V7_TESTS_RAW_SHA256,
            "contentSha256": CHECKER.V7_CANDIDATE_CONTENT_SHA256,
            "combinedInputSetSha256": CHECKER.V7_INPUT_SET_SHA256,
            "sourceBindingsSha256":
                CHECKER.WAVE9_HELD_SOURCE_BINDINGS_SHA256,
            "graphSha256": CHECKER.V7_GRAPH_SHA256,
            "frontierSha256": CHECKER.V7_FRONTIER_SHA256,
            "frontierTupleCount": 10,
            "fixedPointReached": False,
            "totalFullSourceReconstructionCount": 12,
            "totalGraphArchiveOpenCount": 1088,
            "trustedPinnedNormalPathFileWriteCount": 0,
            "osSyscallSandboxProvided": False,
            "providerFacadeVerificationScope":
                "trusted_pinned_normal_reconstruction_path",
            "retainedSnapshotBoundary": {
                "completionAppliesToRetainedSnapshot": True,
                "currentPathIdentityGuaranteedThroughManifestPublication":
                    False,
                "finalNamespaceReverifiedAfterCombinedV7Reconstruction":
                    True,
                "historicalExact46FrozenSnapshotDescriptorSetBound": True,
                "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV7Barrier":
                    True,
                "liveTerminalControlMetadataVerifiedAtCombinedV7Barrier":
                    True,
                "retainedFdPreManifestBarrierCount": 3,
                (
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrier"
                    "Prevented"
                ): False,
            },
        }
        decision = {
            "predecessorBindings": {
                "combinedFixedPointV7": predecessor,
            }
        }

        def digest(raw):
            return {
                b"candidate": CHECKER.V7_CANDIDATE_CONTENT_SHA256,
                b"frontier": CHECKER.V7_FRONTIER_SHA256,
                b"source": CHECKER.V7_INPUT_SET_SHA256,
                b"wave9-source":
                    CHECKER.WAVE9_HELD_SOURCE_BINDINGS_SHA256,
            }[raw]

        with (
            mock.patch.object(CHECKER, "sha256_bytes", side_effect=digest),
            mock.patch.object(
                CHECKER,
                "wave9_digest_bytes",
                return_value=b"wave9-source",
            ),
        ):
            CHECKER.validate_v7_predecessor_candidate(
                Runner,
                candidate,
                decision,
            )

        mutations = (
            (
                "source bindings",
                lambda value: value["decision"]["predecessorBindings"][
                    "combinedFixedPointV7"
                ].__setitem__("sourceBindingsSha256", "0" * 64),
            ),
            (
                "source row keyset",
                lambda value: value["candidate"]["inputSet"][
                    "sourceBindings"
                ][0].__setitem__("unexpected", False),
            ),
            (
                "source path uniqueness",
                lambda value: value["candidate"]["inputSet"][
                    "sourceBindings"
                ][1].__setitem__("path", "root.zip"),
            ),
            (
                "retained boundary",
                lambda value: value["decision"]["predecessorBindings"][
                    "combinedFixedPointV7"
                ]["retainedSnapshotBoundary"].__setitem__(
                    "completionAppliesToRetainedSnapshot",
                    False,
                ),
            ),
            (
                "content binding schema",
                lambda value: value["candidate"][
                    "contentBinding"
                ].__setitem__("unexpected", False),
            ),
            (
                "new tuple count",
                lambda value: value["candidate"]["graphDiscovery"].__setitem__(
                    "newTupleCount",
                    9,
                ),
            ),
            (
                "route",
                lambda value: value["candidate"].__setitem__(
                    "route",
                    "fixed_point_candidate",
                ),
            ),
            (
                "authority keyset",
                lambda value: value["candidate"]["authority"].__setitem__(
                    "unexpected",
                    False,
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label):
                values = {
                    "candidate": copy.deepcopy(candidate),
                    "decision": copy.deepcopy(decision),
                }
                mutate(values)
                with (
                    mock.patch.object(
                        CHECKER,
                        "sha256_bytes",
                        side_effect=digest,
                    ),
                    mock.patch.object(
                        CHECKER,
                        "wave9_digest_bytes",
                        return_value=b"wave9-source",
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.validate_v7_predecessor_candidate(
                        Runner,
                        values["candidate"],
                        values["decision"],
                    )
                self.assertEqual(str(caught.exception), "E_V7_PREDECESSOR")

    def test_16_tool_close_attempts_every_owned_descriptor_after_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = script / "tool.py"
            target.write_bytes(b"VALUE = 1\n")
            pinned = CHECKER.PinnedCodeFile(
                root,
                "script/tool.py",
                hashlib.sha256(target.read_bytes()).hexdigest(),
            )
            descriptors = {
                pinned.fd,
                pinned.parent_fd,
                pinned.root_fd,
                *(
                    fd
                    for child, _, parent, _ in pinned.directories
                    for fd in (child, parent)
                ),
            }
            first = pinned.fd
            real_close = os.close
            attempted = []

            def close_then_fail(fd):
                attempted.append(fd)
                real_close(fd)
                if fd == first:
                    raise OSError("synthetic close failure")

            with (
                mock.patch.object(
                    CHECKER.os,
                    "close",
                    side_effect=close_then_fail,
                ),
                self.assertRaises(OSError),
            ):
                pinned.close()

            self.assertEqual(set(attempted), descriptors)
            for descriptor in descriptors:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_17_partial_open_cleanup_preserves_primary_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "script"
            script.mkdir(mode=0o700)
            script.chmod(0o777)
            opened = []
            real_open = os.open
            real_dup = os.dup
            real_close = os.close
            close_calls = 0

            def record_open(*args, **kwargs):
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd

            def record_dup(fd):
                duplicate = real_dup(fd)
                opened.append(duplicate)
                return duplicate

            def close_then_fail_once(fd):
                nonlocal close_calls
                close_calls += 1
                if close_calls == 1:
                    raise OSError("synthetic cleanup failure")
                real_close(fd)

            with (
                mock.patch.object(
                    CHECKER.os,
                    "open",
                    side_effect=record_open,
                ),
                mock.patch.object(
                    CHECKER.os,
                    "dup",
                    side_effect=record_dup,
                ),
                mock.patch.object(
                    CHECKER.os,
                    "close",
                    side_effect=close_then_fail_once,
                ),
                self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught,
            ):
                CHECKER.PinnedCodeFile(
                    root,
                    "script/tool.py",
                    "0" * 64,
                )

            self.assertEqual(str(caught.exception), "E_TOOL_IDENTITY")
            self.assertEqual(close_calls, len(opened) + 1)
            for descriptor in opened:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_18_canonical_snapshot_only_mutations_fail_closed(self):
        cases = (
            (
                "identity binding",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["identityBindings"].__setitem__(
                    "compactIdentitySha256",
                    "0" * 64,
                ),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "final directory inventory",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["finalDirectory"]["exactEntries"].reverse(),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "absence canonical contract",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["absenceContract"].__setitem__(
                    "portableNameComparison",
                    "case_sensitive",
                ),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "receipt descriptor only",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["acquisitionReceipt"].__setitem__("bytes", 1_669),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "frozen38 canonical authority row only",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["acquisitionAuthority"][0].__setitem__(
                    "bytes",
                    22_531,
                ),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "decision binding schema",
                lambda docs: docs[CHECKER.WAVE9_DECISION_PATH][
                    "contentBinding"
                ].__setitem__("algorithm", "sha512"),
                "E_WAVE9_DECISION",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label):
                assert_wave9_mutation_fails(
                    self,
                    mutate,
                    expected,
                )
        with held_wave9_documents() as (v4, runner, documents):
            CHECKER.wave9_request_resources(v4, runner, documents)
            evidence_raw = (
                ROOT / CHECKER.WAVE9_EVIDENCE_PATH
            ).read_bytes()
            evidence_document = runner.strict_json(
                evidence_raw,
                CHECKER.WAVE9_EVIDENCE_PATH,
            )
            CHECKER.validate_wave9_evidence(
                runner,
                evidence_raw,
                evidence_document,
                documents,
            )
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.validate_wave9_evidence(
                    runner,
                    b"[]\n",
                    [],
                    documents,
                )
            self.assertEqual(
                str(caught.exception),
                "E_WAVE9_EVIDENCE",
            )
            evidence_mutations = (
                (
                    "evidence unknown key",
                    lambda value: value.__setitem__("unexpected", False),
                ),
                (
                    "evidence and readback resource divergence",
                    lambda value: value["resources"][0].__setitem__(
                        "rawSha256",
                        "0" * 64,
                    ),
                ),
            )
            for label, mutate in evidence_mutations:
                with self.subTest(label):
                    mutated = copy.deepcopy(evidence_document)
                    mutate(mutated)
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_wave9_evidence(
                            runner,
                            canonical_bytes(mutated),
                            mutated,
                            documents,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_WAVE9_EVIDENCE",
                    )
            divergent_documents = copy.deepcopy(documents)
            divergent_documents[CHECKER.WAVE9_READBACK_PATH]["verified"][
                "resources"
            ][0]["rawSha256"] = "0" * 64
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.validate_wave9_evidence(
                    runner,
                    evidence_raw,
                    evidence_document,
                    divergent_documents,
                )
            self.assertEqual(
                str(caught.exception),
                "E_WAVE9_EVIDENCE",
            )

    def test_19_manifest_and_verified_only_mutations_fail_closed(self):
        cases = (
            (
                "manifest receipt bytes",
                lambda docs: docs[CHECKER.WAVE9_READBACK_MANIFEST_PATH][
                    "receipt"
                ].__setitem__("bytes", 15_103),
                "E_WAVE9_READBACK_MANIFEST",
            ),
            (
                "manifest authority",
                lambda docs: docs[
                    CHECKER.WAVE9_READBACK_MANIFEST_PATH
                ]["authorityBinding"]["recorder"].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
                "E_WAVE9_READBACK_MANIFEST",
            ),
            (
                "manifest barrier count",
                lambda docs: docs[
                    CHECKER.WAVE9_READBACK_MANIFEST_PATH
                ].__setitem__(
                    "completedPreManifestCurrentPathIdentityBarrierCount",
                    2,
                ),
                "E_WAVE9_READBACK_MANIFEST",
            ),
            (
                "manifest barrier timing",
                lambda docs: docs[
                    CHECKER.WAVE9_READBACK_MANIFEST_PATH
                ].__setitem__(
                    "lastCurrentPathIdentityBarrierTiming",
                    "after_manifest_publication",
                ),
                "E_WAVE9_READBACK_MANIFEST",
            ),
            (
                "verified status",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "verified"
                ].__setitem__("status", "unverified"),
                "E_WAVE9_READBACK",
            ),
            (
                "verified aggregate",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "verified"
                ].__setitem__("aggregateModBytes", 1_729),
                "E_WAVE9_READBACK",
            ),
            (
                "verified claim",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "verified"
                ].__setitem__("acquisitionClaimRawSha256", "0" * 64),
                "E_WAVE9_READBACK",
            ),
            (
                "verified source flag",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "verified"
                ].__setitem__("sourceLoadedOrExecuted", True),
                "E_WAVE9_READBACK",
            ),
            (
                "readback unknown key",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH].__setitem__(
                    "authorityGranted",
                    True,
                ),
                "E_WAVE9_READBACK",
            ),
            (
                "verified unknown key",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PATH][
                    "verified"
                ].__setitem__("sourceAcquired", True),
                "E_WAVE9_READBACK",
            ),
            (
                "manifest unknown key",
                lambda docs: docs[
                    CHECKER.WAVE9_READBACK_MANIFEST_PATH
                ].__setitem__("authorityGranted", True),
                "E_WAVE9_READBACK_MANIFEST",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label):
                assert_wave9_mutation_fails(
                    self,
                    mutate,
                    expected,
                )

    def test_20_recursive_checker_and_provider_hardening_is_exact(self):
        verification = self.candidate["checkerVerification"]
        self.assertTrue(verification["transitiveSafePinnedClassesVerified"])
        self.assertTrue(verification["readOnlyProviderFacadeVerified"])
        self.assertEqual(verification["hardenedCheckerModuleCount"], 7)
        self.assertEqual(verification["providerFacadeLoadCount"], 7)

        with CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V7_CHECKER_PATH,
            CHECKER.V7_CHECKER_RAW_SHA256,
        ) as held_v7:
            v7 = CHECKER.load_v7_checker(held_v7)
            v7 = CHECKER.harden_checker_module(v7)
            self.assertIs(v7.PinnedCodeFile, CHECKER.PinnedCodeFile)
            with v7.PinnedCodeFile(
                ROOT,
                v7.V6_CHECKER_PATH,
                v7.V6_CHECKER_RAW_SHA256,
            ) as held_v6:
                v6 = v7.load_v6_checker(held_v6)
                self.assertIs(v6.PinnedCodeFile, CHECKER.PinnedCodeFile)
                with v6.PinnedCodeFile(
                    ROOT,
                    v6.V5_CHECKER_PATH,
                    v6.V5_CHECKER_RAW_SHA256,
                ) as held_v5:
                    v5 = v6.load_v5_checker(held_v5)
                    self.assertIs(v5.PinnedCodeFile, CHECKER.PinnedCodeFile)
                    with v5.PinnedCodeFile(
                        ROOT,
                        v5.V4_CHECKER_PATH,
                        v5.V4_CHECKER_RAW_SHA256,
                    ) as held_v4:
                        v4 = v5.load_v4_checker(held_v4)
                        self.assertIs(
                            v4.PinnedCodeFile,
                            CHECKER.PinnedCodeFile,
                        )
                        with v4.PinnedCodeFile(
                            ROOT,
                            v4.V3_CHECKER_PATH,
                            v4.V3_CHECKER_RAW_SHA256,
                        ) as held_v3:
                            v3 = v4.load_v3_checker(held_v3)
                            self.assertIs(
                                v3.PinnedCodeFile,
                                CHECKER.PinnedCodeFile,
                            )
                            with v3.PinnedCodeFile(
                                ROOT,
                                v3.V2_CHECKER_PATH,
                                v3.V2_CHECKER_RAW_SHA256,
                            ) as held_v2:
                                v2 = v3.load_v2_checker(held_v2)
                                self.assertIs(
                                    v2.PinnedCodeFile,
                                    CHECKER.PinnedCodeFile,
                                )
                                with v2.PinnedCodeFile(
                                    ROOT,
                                    v2.V1_CHECKER_PATH,
                                    v2.V1_CHECKER_RAW_SHA256,
                                ) as held_v1:
                                    v1 = v2.load_v1_checker(held_v1)
                                    self.assertIs(
                                        v1.PinnedRunnerFile,
                                        CHECKER.SafePinnedRunnerFile,
                                    )
                                    with v1.PinnedRunnerFile(
                                        ROOT
                                    ) as held_provider:
                                        runner = v1.load_pinned_runner(
                                            held_provider
                                        )
                                        self.assertIs(
                                            type(runner),
                                            CHECKER.ReadOnlyProviderFacade,
                                        )
                                        self.assertIs(
                                            type(runner.HeldInputSet),
                                            CHECKER.ReadOnlyProviderCallable,
                                        )

    def test_21_provider_facade_blocks_actual_transitive_write(self):
        with held_wave9_documents() as (_, runner, _):
            self.assertIs(
                type(runner),
                CHECKER.ReadOnlyProviderFacade,
            )
            self.assertFalse(hasattr(runner, "write_exclusive"))
            self.assertIs(
                type(runner.strict_json),
                CHECKER.ReadOnlyProviderCallable,
            )
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ):
                runner.strict_json = lambda *_: None
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as zip_error:
                runner.zipfile.ZipFile(
                    runner.io.BytesIO(),
                    mode="w",
                )
            self.assertEqual(
                str(zip_error.exception),
                "E_TRANSITIVE_WRITE",
            )

            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "blocked.json"
                proxy = CHECKER.ReadOnlyOSProxy()
                with self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught:
                    proxy.open(
                        target,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                self.assertEqual(
                    str(caught.exception),
                    "E_TRANSITIVE_WRITE",
                )
                self.assertFalse(target.exists())
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ):
                proxy.write(1, b"blocked")
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ):
                proxy.write = os.write

    def test_22_safe_held_file_partial_open_preserves_primary_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsafe = root / "unsafe"
            unsafe.mkdir(mode=0o700)
            unsafe.chmod(0o777)
            root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
            )
            opened = []
            real_open = os.open
            real_dup = os.dup
            real_close = os.close
            close_calls = 0

            def record_open(*args, **kwargs):
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd

            def record_dup(fd):
                duplicate = real_dup(fd)
                opened.append(duplicate)
                return duplicate

            def close_then_fail_once(fd):
                nonlocal close_calls
                close_calls += 1
                if close_calls == 1:
                    raise OSError("synthetic held-file cleanup failure")
                real_close(fd)

            try:
                with (
                    mock.patch.object(
                        CHECKER.os,
                        "open",
                        side_effect=record_open,
                    ),
                    mock.patch.object(
                        CHECKER.os,
                        "dup",
                        side_effect=record_dup,
                    ),
                    mock.patch.object(
                        CHECKER.os,
                        "close",
                        side_effect=close_then_fail_once,
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.SafeHeldFile(
                        root_fd,
                        "unsafe/input.bin",
                        maximum_bytes=1,
                        owner_only=False,
                    )
            finally:
                real_close(root_fd)

            self.assertEqual(str(caught.exception), "E_HELD_SET")
            self.assertEqual(close_calls, len(opened) + 1)
            for descriptor in opened:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_23_safe_held_set_closes_all_after_first_close_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.bin"
            second = root / "second.bin"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            first.chmod(0o600)
            second.chmod(0o600)
            bindings = [
                {
                    "path": path.name,
                    "rawSha256": hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest(),
                    "maximumBytes": 16,
                    "ownerOnly": True,
                    "kind": "test",
                }
                for path in (first, second)
            ]
            held = CHECKER.SafeHeldInputSet(root, bindings)
            descriptors = {
                held.root_fd,
                *(
                    descriptor
                    for item in held.files.values()
                    for descriptor in item.owned_fds
                ),
            }
            first_held = next(iter(held.files.values()))
            original_close = first_held.close

            def close_then_fail():
                original_close()
                raise OSError("synthetic held-set close failure")

            first_held.close = close_then_fail
            with self.assertRaises(OSError):
                held.close()

            for descriptor in descriptors:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_24_safe_held_set_constructor_retries_unclosed_fd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.bin"
            second = root / "second.bin"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            first.chmod(0o600)
            second.chmod(0o600)
            bindings = [
                {
                    "path": first.name,
                    "rawSha256": hashlib.sha256(
                        first.read_bytes()
                    ).hexdigest(),
                    "maximumBytes": 16,
                    "ownerOnly": True,
                    "kind": "test",
                },
                {
                    "path": second.name,
                    "rawSha256": "0" * 64,
                    "maximumBytes": 16,
                    "ownerOnly": True,
                    "kind": "test",
                },
            ]
            opened = []
            real_open = os.open
            real_dup = os.dup
            real_close = os.close
            close_calls = 0

            def record_open(*args, **kwargs):
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd

            def record_dup(fd):
                duplicate = real_dup(fd)
                opened.append(duplicate)
                return duplicate

            def fail_before_close_once(fd):
                nonlocal close_calls
                close_calls += 1
                if close_calls == 1:
                    raise OSError("synthetic held-set cleanup failure")
                real_close(fd)

            with (
                mock.patch.object(
                    CHECKER.os,
                    "open",
                    side_effect=record_open,
                ),
                mock.patch.object(
                    CHECKER.os,
                    "dup",
                    side_effect=record_dup,
                ),
                mock.patch.object(
                    CHECKER.os,
                    "close",
                    side_effect=fail_before_close_once,
                ),
                self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught,
            ):
                CHECKER.SafeHeldInputSet(root, bindings)

            self.assertEqual(
                str(caught.exception),
                "E_PREDECESSOR_IDENTITY",
            )
            self.assertEqual(close_calls, len(opened) + 1)
            for descriptor in opened:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_25_control_and_subobject_unknown_keys_fail_closed(self):
        cases = (
            (
                "decision",
                lambda docs: docs[CHECKER.WAVE9_DECISION_PATH].__setitem__(
                    "unexpected",
                    False,
                ),
                "E_WAVE9_DECISION",
            ),
            (
                "decision resolution",
                lambda docs: docs[CHECKER.WAVE9_DECISION_PATH][
                    "identityResolution"
                ].__setitem__("unexpected", False),
                "E_WAVE9_DECISION",
            ),
            (
                "permit",
                lambda docs: docs[CHECKER.WAVE9_PERMIT_PATH].__setitem__(
                    "unexpected",
                    False,
                ),
                "E_WAVE9_PERMIT",
            ),
            (
                "permit request contract",
                lambda docs: docs[CHECKER.WAVE9_PERMIT_PATH][
                    "requestContract"
                ].__setitem__("unexpected", False),
                "E_WAVE9_PERMIT",
            ),
            (
                "receipt",
                lambda docs: docs[CHECKER.WAVE9_RECEIPT_PATH].__setitem__(
                    "unexpected",
                    False,
                ),
                "E_WAVE9_RECEIPT",
            ),
            (
                "readback permit",
                lambda docs: docs[
                    CHECKER.WAVE9_READBACK_PERMIT_PATH
                ].__setitem__("unexpected", False),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "frozen snapshot",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ].__setitem__("unexpected", False),
                "E_WAVE9_READBACK_PERMIT",
            ),
            (
                "verification contract",
                lambda docs: docs[CHECKER.WAVE9_READBACK_PERMIT_PATH][
                    "verificationContract"
                ].__setitem__("unexpected", False),
                "E_WAVE9_READBACK_PERMIT",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label):
                assert_wave9_mutation_fails(
                    self,
                    mutate,
                    expected,
                )

    def test_26_consumed_claims_are_pinned_and_replay_mutations_fail(self):
        with held_wave9_documents(include_held=True) as (
            _,
            runner,
            _,
            held,
        ):
            acquisition_raw = held.raw[
                CHECKER.WAVE9_ACQUISITION_CLAIM_PATH
            ]
            readback_raw = held.raw[CHECKER.WAVE9_READBACK_CLAIM_PATH]
            CHECKER.validate_wave9_consumed_claims(
                runner,
                acquisition_raw,
                readback_raw,
            )
            cases = (
                (
                    "acquisition unknown key",
                    CHECKER.WAVE9_ACQUISITION_CLAIM_PATH,
                    lambda value: value.__setitem__("unexpected", False),
                    "E_WAVE9_ACQUISITION_CLAIM",
                ),
                (
                    "acquisition attempt",
                    CHECKER.WAVE9_ACQUISITION_CLAIM_PATH,
                    lambda value: value.__setitem__("attemptId", "0" * 32),
                    "E_WAVE9_ACQUISITION_CLAIM",
                ),
                (
                    "acquisition status",
                    CHECKER.WAVE9_ACQUISITION_CLAIM_PATH,
                    lambda value: value.__setitem__("status", "pending"),
                    "E_WAVE9_ACQUISITION_CLAIM",
                ),
                (
                    "readback mixed attempt",
                    CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    lambda value: value.__setitem__(
                        "acquisitionAttemptId",
                        "0" * 32,
                    ),
                    "E_WAVE9_READBACK_CLAIM",
                ),
                (
                    "readback attempt",
                    CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    lambda value: value.__setitem__(
                        "readbackAttemptId",
                        "0" * 32,
                    ),
                    "E_WAVE9_READBACK_CLAIM",
                ),
                (
                    "readback status",
                    CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    lambda value: value.__setitem__("status", "pending"),
                    "E_WAVE9_READBACK_CLAIM",
                ),
                (
                    "readback authority",
                    CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    lambda value: value["authorityBinding"][
                        "recorder"
                    ].__setitem__("rawSha256", "0" * 64),
                    "E_WAVE9_READBACK_CLAIM",
                ),
                (
                    "readback persistence",
                    CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    lambda value: value.__setitem__(
                        "claimPersistsAfterSuccessFailureOrUncertainty",
                        False,
                    ),
                    "E_WAVE9_READBACK_CLAIM",
                ),
                (
                    "readback retry",
                    CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    lambda value: value.__setitem__("retryAllowed", True),
                    "E_WAVE9_READBACK_CLAIM",
                ),
            )
            for label, path, mutate, expected in cases:
                with self.subTest(label):
                    acquisition = runner.strict_json(
                        acquisition_raw,
                        CHECKER.WAVE9_ACQUISITION_CLAIM_PATH,
                    )
                    readback = runner.strict_json(
                        readback_raw,
                        CHECKER.WAVE9_READBACK_CLAIM_PATH,
                    )
                    target = acquisition if path == (
                        CHECKER.WAVE9_ACQUISITION_CLAIM_PATH
                    ) else readback
                    mutate(target)
                    patch_content = nullcontext()
                    if target is readback:
                        without = dict(readback)
                        without.pop("contentBinding")
                        recomputed = hashlib.sha256(
                            canonical_bytes(without)
                        ).hexdigest()
                        readback["contentBinding"]["sha256"] = recomputed
                        patch_content = mock.patch.object(
                            CHECKER,
                            "WAVE9_READBACK_CLAIM_CONTENT_SHA256",
                            recomputed,
                        )
                    with (
                        patch_content,
                        self.assertRaises(
                            CHECKER.CombinedCheckFailure,
                        ) as caught,
                    ):
                        CHECKER.validate_wave9_consumed_claims(
                            runner,
                            canonical_bytes(acquisition),
                            canonical_bytes(readback),
                        )
                    self.assertEqual(str(caught.exception), expected)

    def test_27_completed_namespace_rejects_stale_portable_names(self):
        with held_wave9_documents(include_held=True) as (
            _,
            _,
            documents,
            held,
        ):
            CHECKER.validate_wave9_completed_namespace(held, documents)
            acquisition_claim = held.files[
                CHECKER.WAVE9_ACQUISITION_CLAIM_PATH
            ]
            readback = held.files[CHECKER.WAVE9_READBACK_PATH]
            evidence = held.files[CHECKER.WAVE9_EVIDENCE_PATH]
            real_listdir = CHECKER.os.listdir

            def altered_listdir(kind):
                def alter(descriptor):
                    names = list(real_listdir(descriptor))
                    if (
                        kind == "staging"
                        and descriptor == acquisition_claim.parent_fd
                    ):
                        names.append(".WAVE-9-V1-STAGING-stale")
                    elif (
                        kind == "claim alias"
                        and descriptor == acquisition_claim.parent_fd
                    ):
                        names.append(".WAVE-9-V1.CLAIM")
                    elif (
                        kind == "readback temp"
                        and descriptor == readback.parent_fd
                    ):
                        names.append(
                            ".BOUNDED-DEPENDENCY-SOURCE-ACQUISITION-"
                            "WAVE9-READBACK-V1.JSON.TMP-stale"
                        )
                    elif (
                        kind == "manifest temp"
                        and descriptor == readback.parent_fd
                    ):
                        names.append(
                            ".BOUNDED-DEPENDENCY-SOURCE-ACQUISITION-"
                            "WAVE9-READBACK-MANIFEST-V1.JSON.TMP-stale"
                        )
                    elif (
                        kind == "failure"
                        and descriptor == readback.parent_fd
                    ):
                        names.append(Path(CHECKER.WAVE9_FAILURE_PATH).name)
                    elif (
                        kind == "missing control"
                        and descriptor == readback.parent_fd
                    ):
                        names.remove(Path(CHECKER.WAVE9_DECISION_PATH).name)
                    elif (
                        kind == "final extra"
                        and descriptor == evidence.parent_fd
                    ):
                        names.append("unexpected")
                    elif (
                        kind == "accepted extra"
                        and descriptor
                        not in {
                            acquisition_claim.parent_fd,
                            readback.parent_fd,
                            evidence.parent_fd,
                        }
                    ):
                        names.append("unexpected")
                    return names

                return alter

            for label in (
                "staging",
                "claim alias",
                "readback temp",
                "manifest temp",
                "failure",
                "missing control",
                "final extra",
                "accepted extra",
            ):
                with (
                    self.subTest(label),
                    mock.patch.object(
                        CHECKER.os,
                        "listdir",
                        side_effect=altered_listdir(label),
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.validate_wave9_completed_namespace(
                        held,
                        documents,
                    )
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE9_NAMESPACE",
                )
        tree = ast.parse(CHECKER_PATH.read_text())
        final_namespace_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "validate_wave9_completed_namespace"
        ]
        self.assertEqual(len(final_namespace_calls), 2)

    def test_28_live_terminal_metadata_drift_fails_closed(self):
        with held_wave9_documents(include_held=True) as (
            _,
            _,
            documents,
            held,
        ):
            target_fd = held.files[CHECKER.WAVE9_RECEIPT_PATH].fd
            real_fstat = CHECKER.os.fstat

            def changed_mode(descriptor):
                info = real_fstat(descriptor)
                if descriptor != target_fd:
                    return info
                values = list(info)
                values[0] = (info.st_mode & ~0o777) | 0o644
                return os.stat_result(values)

            with (
                mock.patch.object(
                    CHECKER.os,
                    "fstat",
                    side_effect=changed_mode,
                ),
                self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught,
            ):
                CHECKER.validate_wave9_completed_namespace(
                    held,
                    documents,
                )
            self.assertEqual(
                str(caught.exception),
                "E_WAVE9_CONTROL_METADATA",
            )

    def test_29_exact_legacy_build_compatibility_is_fail_closed(self):
        with held_wave9_documents() as (v4, runner, documents):
            resources = CHECKER.wave9_request_resources(
                v4,
                runner,
                documents,
            )
            target = next(
                row
                for row in resources
                if row["tupleOrder"] == 137 and row["kind"] == "zip"
            )
            with CHECKER.zipfile.ZipFile(
                ROOT / target["path"],
                mode="r",
            ) as archive:
                name = next(
                    value
                    for value in archive.namelist()
                    if value.endswith("go/loader/example_test.go")
                )
                raw = archive.read(name)
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(),
                CHECKER.WAVE9_LEGACY_BUILD_SOURCE_SHA256,
            )
            text = raw.decode("utf-8", errors="strict")
            before = CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
            expression = runner.extract_build_expression(
                text
            )
            self.assertEqual(
                expression,
                CHECKER.WAVE9_LEGACY_BUILD_EXPRESSION,
            )
            self.assertEqual(
                CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
                before + 1,
            )
            with self.assertRaises(
                CHECKER.SafeReviewFailure,
            ) as caught:
                runner.extract_build_expression(text + "\n")
            self.assertEqual(str(caught.exception), "E_BUILD_CONSTRAINT")
            self.assertEqual(
                CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
                before + 1,
            )

            provider_first = (
                CHECKER.pinned_wave9_extract_build_expression(
                    lambda _: "provider_parser_success"
                )
            )
            provider_first_count = (
                CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
            )
            self.assertEqual(
                provider_first(text),
                "provider_parser_success",
            )
            self.assertEqual(
                CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
                provider_first_count,
            )

            normalized_text = text.replace(
                CHECKER.WAVE9_LEGACY_BUILD_ORIGINAL_LINE,
                CHECKER.WAVE9_LEGACY_BUILD_NORMALIZED_LINE,
            )

            def fallback_target(value):
                if value == normalized_text:
                    return CHECKER.WAVE9_LEGACY_BUILD_EXPRESSION
                raise CHECKER.SafeReviewFailure(
                    "E_BUILD_CONSTRAINT",
                    "source_inventory",
                )

            duplicated = text.replace(
                CHECKER.WAVE9_LEGACY_BUILD_ORIGINAL_LINE,
                (
                    CHECKER.WAVE9_LEGACY_BUILD_ORIGINAL_LINE
                    + "\n"
                    + CHECKER.WAVE9_LEGACY_BUILD_ORIGINAL_LINE
                ),
            )
            duplicated_sha256 = hashlib.sha256(
                duplicated.encode("utf-8")
            ).hexdigest()
            with (
                mock.patch.object(
                    CHECKER,
                    "WAVE9_LEGACY_BUILD_SOURCE_SHA256",
                    duplicated_sha256,
                ),
                self.assertRaises(
                    CHECKER.SafeReviewFailure,
                ) as duplicate_line_error,
            ):
                CHECKER.pinned_wave9_extract_build_expression(
                    fallback_target
                )(duplicated)
            self.assertEqual(
                str(duplicate_line_error.exception),
                "E_BUILD_CONSTRAINT",
            )

            with (
                mock.patch.object(
                    CHECKER,
                    "WAVE9_LEGACY_BUILD_NORMALIZED_SHA256",
                    "0" * 64,
                ),
                self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as normalized_hash_error,
            ):
                CHECKER.pinned_wave9_extract_build_expression(
                    fallback_target
                )(text)
            self.assertEqual(
                str(normalized_hash_error.exception),
                "E_WAVE9_BUILD_COMPATIBILITY",
            )

            def wrong_expression_target(value):
                if value == normalized_text:
                    return "wrong"
                raise CHECKER.SafeReviewFailure(
                    "E_BUILD_CONSTRAINT",
                    "source_inventory",
                )

            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as expression_error:
                CHECKER.pinned_wave9_extract_build_expression(
                    wrong_expression_target
                )(text)
            self.assertEqual(
                str(expression_error.exception),
                "E_WAVE9_BUILD_COMPATIBILITY",
            )

            def wrong_phase_target(_):
                raise CHECKER.SafeReviewFailure(
                    "E_BUILD_CONSTRAINT",
                    "graph",
                )

            with self.assertRaises(
                CHECKER.SafeReviewFailure,
            ) as phase_error:
                CHECKER.pinned_wave9_extract_build_expression(
                    wrong_phase_target
                )(text)
            self.assertEqual(str(phase_error.exception), "E_BUILD_CONSTRAINT")

            def wrong_code_target(_):
                raise CHECKER.SafeReviewFailure(
                    "E_IMPORT_PARSE",
                    "source_inventory",
                )

            wrong_code_count = (
                CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
            )
            with self.assertRaises(
                CHECKER.SafeReviewFailure,
            ) as code_error:
                CHECKER.pinned_wave9_extract_build_expression(
                    wrong_code_target
                )(text)
            self.assertEqual(str(code_error.exception), "E_IMPORT_PARSE")
            self.assertEqual(
                CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
                wrong_code_count,
            )
            for invalid_count in (False, 0, 3, 5):
                with (
                    self.subTest(invalid_count=invalid_count),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as count_error,
                ):
                    CHECKER.validate_wave9_legacy_build_compatibility_count(
                        invalid_count
                    )
                self.assertEqual(
                    str(count_error.exception),
                    "E_WAVE9_BUILD_COMPATIBILITY",
                )
            CHECKER.validate_wave9_legacy_build_compatibility_count(4)

            profiles = [
                {
                    "profileId":
                        "android_api_26_through_36_arm64_v8a",
                    "tags": [
                        "android", "arm64", "go1.8", "go1.9",
                    ],
                },
                {
                    "profileId": "macos_14_or_newer_arm64",
                    "tags": [
                        "arm64", "darwin", "go1.8", "go1.9",
                    ],
                },
            ]
            CHECKER.validate_wave9_legacy_build_profile_equivalence(
                profiles
            )
            profiles[0]["tags"].append("TODO(adonovan)")
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as profile_error:
                CHECKER.validate_wave9_legacy_build_profile_equivalence(
                    profiles
                )
            self.assertEqual(
                str(profile_error.exception),
                "E_WAVE9_BUILD_COMPATIBILITY",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
