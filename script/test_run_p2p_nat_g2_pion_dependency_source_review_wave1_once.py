#!/usr/bin/env python3
"""Synthetic regressions for the bounded dependency source-review runner."""

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

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
import zipfile


RUNNER_PATH = (
    Path(__file__).resolve().parent
    / "run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
SPEC = importlib.util.spec_from_file_location(
    "g2_dependency_source_review_wave1_runner",
    RUNNER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load dependency source-review runner")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=False,
    ) as archive:
        for name, payload in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, payload)
    return output.getvalue()


class SyntheticRepository:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        os.chmod(self.root, 0o700)
        self.root_module = "example.com/root"
        self.root_version = "v1.0.0"
        self.dependency_module = "example.com/dep"
        self.dependency_version = "v1.0.0"
        self.new_module = "example.com/new"
        self.new_version = "v1.2.0"
        self.root_mod = (
            "module example.com/root\n\n"
            "go 1.24.0\n"
            "require example.com/dep v1.0.0\n"
        ).encode()
        self.dependency_mod = (
            "module example.com/dep\n\n"
            "go 1.24.0\n"
            "require example.com/new v1.2.0\n"
        ).encode()
        self.root_zip = zip_bytes(
            [
                (
                    "example.com/root@v1.0.0/go.mod",
                    self.root_mod,
                ),
                (
                    "example.com/root@v1.0.0/root.go",
                    (
                        "package root\n"
                        'import "example.com/dep/pkg"\n'
                        "func Root() {}\n"
                    ).encode(),
                ),
                (
                    "example.com/root@v1.0.0/LICENSE",
                    b"synthetic license\n",
                ),
            ]
        )
        self.dependency_zip = zip_bytes(
            [
                (
                    "example.com/dep@v1.0.0/go.mod",
                    self.dependency_mod,
                ),
                (
                    "example.com/dep@v1.0.0/pkg/dep.go",
                    (
                        "package pkg\n"
                        "import (\n"
                        '  "net"\n'
                        '  "example.com/new/sub"\n'
                        ")\n"
                        "func Dep() {}\n"
                    ).encode(),
                ),
                (
                    "example.com/dep@v1.0.0/License",
                    b"synthetic dependency license\n",
                ),
                (
                    "example.com/dep@v1.0.0/native_arm64.s",
                    b"// synthetic assembly\n",
                ),
            ]
        )
        self._prepare_directories()
        self._write_tools()
        self.decision_path = f"{runner.BASE}/synthetic-decision.json"
        self.root_zip_path = (
            "build/offline-source/pion-ice-v4.3.0/original/root.zip"
        )
        dependency_source = (
            "build/offline-source/pion-ice-v4.3.0/dependencies/"
            "wave-1-v3/accepted"
        )
        self.mod_path = f"{dependency_source}/dependency.mod"
        self.zip_path = f"{dependency_source}/dependency.zip"
        decision = runner.content_bound(
            {
                "documentType": "synthetic.review.decision",
                "schemaVersion": "1.0",
                "decisionId": "synthetic-decision",
                "profiles": [
                    {
                        "profileId": "android",
                        "tags": [
                            "android",
                            "arm64",
                            "unix",
                            "cgo",
                            "gc",
                            "go1.24",
                        ],
                    },
                    {
                        "profileId": "macos",
                        "tags": [
                            "darwin",
                            "arm64",
                            "unix",
                            "cgo",
                            "gc",
                            "go1.24",
                        ],
                    },
                ],
            },
            "decision_without_contentBinding",
        )
        self.decision_raw = runner.canonical_json_bytes(decision)
        self._write(self.decision_path, self.decision_raw, 0o644)
        self._write(self.root_zip_path, self.root_zip, 0o600)
        self._write(self.mod_path, self.dependency_mod, 0o600)
        self._write(self.zip_path, self.dependency_zip, 0o600)
        self.bindings = [
            self._binding(
                self.decision_path,
                self.decision_raw,
                kind="decision",
                owner_only=False,
                maximum=runner.MAXIMUM_JSON_BYTES,
            ),
            self._binding(
                self.root_zip_path,
                self.root_zip,
                kind="root_zip",
                owner_only=True,
                maximum=runner.DEFAULT_MAXIMUM_ARCHIVE_BYTES,
                module=self.root_module,
                version=self.root_version,
                module_prefix="example.com/root@v1.0.0/",
                tuple_id="root",
                tuple_order=0,
            ),
            self._binding(
                self.mod_path,
                self.dependency_mod,
                kind="mod",
                owner_only=True,
                maximum=1024 * 1024,
                module=self.dependency_module,
                version=self.dependency_version,
                tuple_id="wave1-001",
                tuple_order=1,
            ),
            self._binding(
                self.zip_path,
                self.dependency_zip,
                kind="zip",
                owner_only=True,
                maximum=runner.DEFAULT_MAXIMUM_ARCHIVE_BYTES,
                module=self.dependency_module,
                version=self.dependency_version,
                module_prefix="example.com/dep@v1.0.0/",
                tuple_id="wave1-001",
                tuple_order=1,
            ),
        ]
        self.permit = runner.build_expected_permit(
            decision_binding={
                "path": self.decision_path,
                "rawSha256": sha256(self.decision_raw),
                "contentSha256": decision["contentBinding"]["sha256"],
                "decisionId": "synthetic-decision",
                "profiles": decision["profiles"],
            },
            input_bindings=self.bindings,
            runner_raw_sha256=sha256(RUNNER_PATH.read_bytes()),
            runner_tests_raw_sha256=sha256(Path(__file__).read_bytes()),
        )

    def _prepare_directories(self) -> None:
        directories = {
            "fixtures",
            "script",
            "build",
            "build/offline-source",
            "build/offline-source/pion-ice-v4.3.0",
            "build/offline-source/pion-ice-v4.3.0/original",
            "build/offline-source/pion-ice-v4.3.0/dependencies",
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-1-v3"
            ),
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-1-v3/accepted"
            ),
            "docs",
            "docs/security-hardening",
            "docs/security-hardening/production-p2p-nat-v1",
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1"
            ),
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three"
            ),
        }
        for relative in sorted(directories, key=lambda value: value.count("/")):
            path = self.root / relative
            path.mkdir(exist_ok=True)
            os.chmod(path, 0o700)

    def _write_tools(self) -> None:
        self._write(runner.RUNNER_PATH, RUNNER_PATH.read_bytes(), 0o644)
        self._write(
            runner.RUNNER_TESTS_PATH,
            Path(__file__).read_bytes(),
            0o644,
        )

    def _write(self, relative: str, payload: bytes, mode: int) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        os.chmod(path, mode)

    @staticmethod
    def _binding(
        path: str,
        payload: bytes,
        *,
        kind: str,
        owner_only: bool,
        maximum: int,
        module: str | None = None,
        version: str | None = None,
        module_prefix: str | None = None,
        tuple_id: str | None = None,
        tuple_order: int | None = None,
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "path": path,
            "rawSha256": sha256(payload),
            "byteSize": len(payload),
            "maximumBytes": maximum,
            "ownerOnly": owner_only,
            "kind": kind,
        }
        if module is not None:
            result["module"] = module
        if version is not None:
            result["version"] = version
        if module_prefix is not None:
            result["modulePrefix"] = module_prefix
        if tuple_id is not None:
            result["tupleId"] = tuple_id
        if tuple_order is not None:
            result["tupleOrder"] = tuple_order
        return result

    def cleanup(self) -> None:
        self.temporary.cleanup()


class DependencySourceReviewWaveOneRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = SyntheticRepository()

    def tearDown(self) -> None:
        self.fixture.cleanup()

    def test_01_cli_requires_exact_explicit_mode(self) -> None:
        with self.assertRaises(SystemExit):
            runner.parse_arguments([])
        with self.assertRaises(SystemExit):
            runner.parse_arguments(["--preflight", "--execute"])
        with self.assertRaises(SystemExit):
            runner.parse_arguments(["--root", "/tmp/no"])
        self.assertTrue(runner.parse_arguments(["--preflight"]).preflight)
        self.assertTrue(runner.parse_arguments(["--execute"]).execute)

    def test_02_permit_is_self_bound_and_has_no_authentication(self) -> None:
        permit = self.fixture.permit
        without = dict(permit)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            sha256(runner.canonical_json_bytes(without)),
        )
        authority = permit["authority"]
        self.assertTrue(
            authority["boundedDependencySourceReviewWave1Authorized"]
        )
        self.assertTrue(authority["boundedInMemoryArchiveInspectionAuthorized"])
        for name in (
            "filesystemExtractionAuthorized",
            "reviewedSourceLoadOrExecutionAuthorized",
            "shellOrSubprocessAuthorized",
            "networkAuthorized",
            "gitWriteAuthorized",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "userActionRequired",
        ):
            self.assertFalse(authority[name])
        personal = permit["personalProjectBoundary"]
        self.assertFalse(
            personal["productEndpointAuthenticationEvaluatedByThisReview"]
        )
        self.assertTrue(
            personal[
                "productEndpointAuthenticationIsSeparateRuntimeInvariant"
            ]
        )

    def test_03_preflight_holds_inputs_but_does_not_inspect_archives(self) -> None:
        with mock.patch.object(
            runner,
            "inspect_zip_bytes",
            side_effect=AssertionError("preflight inspected an archive"),
        ):
            result = runner.preflight_with_authority(
                self.fixture.root,
                self.fixture.permit,
                self.fixture.bindings,
            )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["archiveInspectionCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertEqual(result["networkOperationCount"], 0)
        self.assertFalse(
            result["productEndpointAuthenticationEvaluatedByThisReview"]
        )
        for path in (
            runner.CLAIM_PATH,
            runner.RESULT_PATH,
            runner.FAILURE_PATH,
            runner.MANIFEST_PATH,
        ):
            self.assertFalse((self.fixture.root / path).exists())

    def test_04_fixed_input_drift_and_bool_integer_alias_fail_closed(self) -> None:
        drifted = copy.deepcopy(self.fixture.bindings)
        drifted[-1]["rawSha256"] = "0" * 64
        with self.assertRaises(runner.ReviewFailure) as caught:
            runner.preflight_with_authority(
                self.fixture.root,
                self.fixture.permit,
                drifted,
            )
        self.assertEqual(caught.exception.code, "E_PREDECESSOR_IDENTITY")
        permit = copy.deepcopy(self.fixture.permit)
        permit["authority"][
            "boundedDependencySourceReviewWave1Authorized"
        ] = 1
        body = dict(permit)
        body.pop("contentBinding")
        permit["contentBinding"]["sha256"] = sha256(
            runner.canonical_json_bytes(body)
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.validate_permit(permit, self.fixture.root)

    def test_05_strict_json_rejects_duplicate_nonfinite_and_float(self) -> None:
        for payload in (
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'{"a":1.5}\n',
            b"\xff",
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(runner.ReviewFailure):
                    runner.strict_json(payload)

    def test_06_go_mod_parser_supports_quotes_blocks_and_rejects_unknown(self) -> None:
        parsed = runner.parse_go_mod(
            (
                'module "example.com/quoted"\n'
                "go 1.24.0\n"
                "require (\n"
                '  "example.com/dep" v1.2.3 // indirect\n'
                ")\n"
                "exclude example.com/old v1.0.0\n"
                "replace example.com/old v1.0.0 => example.com/new v1.1.0\n"
                "retract v1.0.1\n"
            ).encode(),
            "example.com/quoted",
        )
        self.assertEqual(parsed["requires"][0]["module"], "example.com/dep")
        self.assertEqual(parsed["excludes"][0]["version"], "v1.0.0")
        self.assertEqual(parsed["retracts"], ["v1.0.1"])
        with self.assertRaises(runner.ReviewFailure):
            runner.parse_go_mod(
                b"module example.com/no\nunknown value\n",
                "example.com/no",
            )
        with self.assertRaises(runner.ReviewFailure):
            runner.parse_go_mod(
                b"module example.com/a\nmodule example.com/b\n",
            )

    def test_07_build_constraint_and_import_parsers_are_deterministic(self) -> None:
        expression = "(android || darwin) && cgo && !race"
        self.assertTrue(
            runner.active_for_profile(
                expression,
                {"android", "arm64", "cgo"},
            )
        )
        self.assertFalse(
            runner.active_for_profile(expression, {"linux", "arm64", "cgo"})
        )
        imports = runner.parse_go_imports(
            """
            package p
            import (
                _ "example.com/blank"
                alias `example.com/raw`
                . "example.com/dot"
            )
            """
        )
        self.assertEqual(
            imports,
            [
                "example.com/blank",
                "example.com/dot",
                "example.com/raw",
            ],
        )
        self.assertEqual(
            runner.parse_go_imports(
                "package p\n"
                'import "example.com/runes"\n'
                "var (\n"
                "    doubleQuote = '\"'\n"
                "    singleQuote = '\\''\n"
                "    escaped = '\\n'\n"
                ")\n"
            ),
            ["example.com/runes"],
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.active_for_profile("android && (", {"android"})
        with self.assertRaises(runner.ReviewFailure):
            runner.parse_go_imports('package p\nimport "unterminated\n')
        with self.assertRaises(runner.ReviewFailure):
            runner.parse_go_imports("package p\nvar broken = 'unterminated\n")
        android = runner.normalized_profile(
            {
                "profileId": "android",
                "tags": ["android", "arm64", "cgo"],
            }
        )
        android_tags = set(android["tags"])
        self.assertIn("linux", android_tags)
        self.assertTrue(
            all(
                f"go1.{minor}" in android_tags
                for minor in range(1, 25)
            )
        )
        self.assertNotIn("go1.25", android_tags)
        self.assertIn("arm64.v8.0", android_tags)
        self.assertNotIn("arm64.v8.1", android_tags)
        self.assertTrue(
            runner.active_for_profile(
                (
                    "linux && go1.1 && go1.23 && go1.24 && !go1.25 "
                    "&& arm64.v8.0 && !arm64.v8.1"
                ),
                android_tags,
            )
        )
        self.assertTrue(
            runner.active_for_profile_monotone(
                (
                    "linux && go1.1 && go1.23 && go1.24 && !go1.25 "
                    "&& arm64.v8.0 && !arm64.v8.1"
                ),
                android_tags,
            )
        )
        for candidate in (
            "(android || darwin) && cgo && !race",
            "!(darwin || race) && !!android",
            "darwin || android && cgo",
            "(android && !cgo) || (linux && arm64.v8.0)",
        ):
            self.assertEqual(
                runner.active_for_profile(candidate, android_tags),
                runner.active_for_profile_monotone(
                    candidate,
                    android_tags,
                ),
            )
        legacy = runner.extract_build_expression(
            "// +build linux,arm64 darwin,arm64\n\npackage p\n"
        )
        self.assertTrue(runner.active_for_profile(legacy, android_tags))
        darwin = runner.normalized_profile(
            {
                "profileId": "darwin",
                "tags": ["darwin", "arm64", "cgo"],
            }
        )
        self.assertTrue(
            runner.active_for_profile(legacy, set(darwin["tags"]))
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.extract_build_expression(
                "// +build linux,,arm64\n\npackage p\n"
            )

    def test_08_bounded_zip_inventory_never_extracts(self) -> None:
        binding = self.fixture.bindings[-1]
        inventory = runner.inspect_zip_bytes(
            self.fixture.dependency_zip,
            binding,
            self.fixture.permit["resourceLimits"],
        )
        self.assertEqual(inventory["entryCount"], 4)
        self.assertEqual(len(inventory["sources"]), 1)
        self.assertEqual(len(inventory["licenses"]), 1)
        self.assertIn("assembly", inventory["special"][0]["classes"])
        traversal = zip_bytes(
            [
                (
                    "example.com/dep@v1.0.0/../escape.go",
                    b"package escape\n",
                )
            ]
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.inspect_zip_bytes(
                traversal,
                {**binding, "rawSha256": sha256(traversal)},
                self.fixture.permit["resourceLimits"],
            )
        duplicate = zip_bytes(
            [
                ("example.com/dep@v1.0.0/A.go", b"package p\n"),
                ("example.com/dep@v1.0.0/a.go", b"package p\n"),
            ]
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.inspect_zip_bytes(
                duplicate,
                {**binding, "rawSha256": sha256(duplicate)},
                self.fixture.permit["resourceLimits"],
            )
        invalid_source = zip_bytes(
            [
                (
                    "example.com/dep@v1.0.0/broken.go",
                    b'package p\nimport "unterminated\n',
                )
            ]
        )
        with self.assertRaises(runner.ReviewFailure) as caught:
            runner.inspect_zip_bytes(
                invalid_source,
                {**binding, "rawSha256": sha256(invalid_source)},
                self.fixture.permit["resourceLimits"],
            )
        self.assertEqual(caught.exception.code, "E_IMPORT_PARSE")
        self.assertEqual(caught.exception.phase, "source_inventory")
        self.assertEqual(caught.exception.tuple_id, "wave1-001")
        self.assertEqual(caught.exception.tuple_order, 1)
        self.assertEqual(caught.exception.resource_kind, "zip")
        rune_source = zip_bytes(
            [
                (
                    "example.com/dep@v1.0.0/runes.go",
                    (
                        "package p\n"
                        'import "example.com/runes"\n'
                        "var doubleQuote = '\"'\n"
                        "var singleQuote = '\\''\n"
                    ).encode(),
                )
            ]
        )
        rune_inventory = runner.inspect_zip_bytes(
            rune_source,
            {**binding, "rawSha256": sha256(rune_source)},
            self.fixture.permit["resourceLimits"],
        )
        self.assertEqual(
            rune_inventory["sources"][0]["imports"],
            ["example.com/runes"],
        )
        corrupt = bytearray(rune_source)
        central_directory = corrupt.find(b"PK\x01\x02")
        self.assertGreaterEqual(central_directory, 0)
        corrupt[central_directory] ^= 0x01
        with self.assertRaises(runner.ReviewFailure) as caught:
            runner.inspect_zip_bytes(
                bytes(corrupt),
                {**binding, "rawSha256": sha256(bytes(corrupt))},
                self.fixture.permit["resourceLimits"],
            )
        self.assertEqual(caught.exception.code, "E_ARCHIVE_STRUCTURE")
        self.assertEqual(caught.exception.phase, "archive")

    def test_09_review_discovers_new_tuple_without_claiming_closure(self) -> None:
        with runner.HeldInputSet(
            self.fixture.root,
            self.fixture.bindings,
        ) as held:
            result = runner.review_held_inputs(
                self.fixture.permit,
                self.fixture.bindings,
                held,
            )
        graph = result["graphDiscovery"]
        self.assertEqual(
            graph["algorithm"],
            "go1.24_mvs_profile_union_fixed_point_v1",
        )
        self.assertEqual(graph["algorithm"], runner.GRAPH_ALGORITHM)
        self.assertTrue(graph["versionSpecificVertexTraversal"])
        self.assertEqual(graph["newTupleCount"], 1)
        self.assertEqual(
            graph["newlyReachableTuples"][0]["module"],
            self.fixture.new_module,
        )
        self.assertFalse(graph["fixedPointReached"])
        self.assertTrue(graph["independentReproductionPassed"])
        self.assertEqual(graph["reconstructionCount"], 2)
        self.assertEqual(
            graph["reconstructions"][0]["reconstructionSha256"],
            graph["reconstructions"][1]["reconstructionSha256"],
        )
        projection = {
            field: graph[field]
            for field in (
                "selectedVersions",
                "nodes",
                "edges",
                "moduleNodes",
                "moduleEdges",
                "exactFrontier",
                "unmappedExternalImports",
                "unresolvedDeclaredExternalImports",
            )
        }
        projection_digest = sha256(
            runner.canonical_json_bytes(projection)
        )
        self.assertEqual(graph["graphSha256"], projection_digest)
        self.assertEqual(
            graph["reconstructionProjectionSha256"],
            projection_digest,
        )
        self.assertTrue(
            all(
                row["reconstructionSha256"] == projection_digest
                for row in graph["reconstructions"]
            )
        )
        module_projection = {
            "selectedVersions": graph["selectedVersions"],
            "moduleNodes": graph["moduleNodes"],
            "moduleEdges": graph["moduleEdges"],
            "exactFrontier": graph["exactFrontier"],
        }
        self.assertEqual(
            graph["moduleGraphAndFrontierSha256"],
            sha256(runner.canonical_json_bytes(module_projection)),
        )
        self.assertEqual(
            graph["selectedVersions"],
            sorted(
                graph["selectedVersions"],
                key=lambda row: (row["module"], row["version"]),
            ),
        )
        missing = copy.deepcopy(graph)
        missing.pop("selectedVersions")
        with self.assertRaises(runner.ReviewFailure):
            runner.graph_reconstruction_projection(missing)
        modified = copy.deepcopy(projection)
        modified["selectedVersions"][0]["version"] = "v9.9.9"
        self.assertNotEqual(
            sha256(runner.canonical_json_bytes(modified)),
            projection_digest,
        )
        self.assertFalse(
            graph["newlyReachableTuples"][0]["acquisitionAuthorized"]
        )
        closure = result["closure"]
        self.assertFalse(closure["dependencySourceReviewed"])
        self.assertFalse(closure["dependencyClosureComplete"])
        self.assertFalse(closure["candidateSelected"])
        self.assertFalse(closure["librarySelected"])
        self.assertEqual(
            result["nextAction"],
            runner.INDEPENDENT_READBACK_NEXT_ACTION,
        )
        self.assertEqual(
            result["postReadbackNextAction"],
            runner.WAVE2_POST_READBACK_ACTION,
        )

    def test_10_graph_digest_is_stable_and_mvs_never_downgrades(self) -> None:
        with runner.HeldInputSet(
            self.fixture.root,
            self.fixture.bindings,
        ) as held:
            first = runner.review_held_inputs(
                self.fixture.permit,
                self.fixture.bindings,
                held,
            )
            second = runner.review_held_inputs(
                self.fixture.permit,
                list(self.fixture.bindings),
                held,
            )
        self.assertEqual(
            first["graphDiscovery"]["graphSha256"],
            second["graphDiscovery"]["graphSha256"],
        )
        self.assertGreater(
            runner.semver_key("v1.2.0"),
            runner.semver_key("v1.1.0"),
        )

    def test_11_unreachable_root_subpackage_is_not_a_graph_seed(self) -> None:
        archives = [
            {
                "kind": "root_zip",
                "module": "example.com/root",
                "version": "v1.0.0",
                "sources": [
                    {
                        "sourceClass": "production",
                        "buildExpression": None,
                        "relativePath": "root.go",
                        "imports": [],
                    },
                    {
                        "sourceClass": "production",
                        "buildExpression": None,
                        "relativePath": "unused/unused.go",
                        "imports": ["example.com/unreachable/pkg"],
                    },
                ],
            }
        ]
        metadata = [
            {
                "module": "example.com/root",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/root",
                    "requires": [
                        {
                            "module": "example.com/unreachable",
                            "version": "v1.0.0",
                        }
                    ],
                    "excludes": [],
                },
            }
        ]
        graph = runner.build_graph(
            archives,
            metadata,
            [{"profileId": "android", "tags": ["android", "arm64"]}],
            {
                "maximumGraphNodes": 16,
                "maximumGraphEdges": 16,
            },
        )
        self.assertEqual(
            graph["nodes"],
            [
                {
                    "profileId": "android",
                    "module": "example.com/root",
                    "package": "example.com/root",
                }
            ],
        )
        self.assertEqual(graph["edges"], [])
        self.assertEqual(
            graph["newlyReachableTuples"],
            [
                {
                    "module": "example.com/unreachable",
                    "version": "v1.0.0",
                    "selectedByGraphAlgorithm": True,
                    "requiresSeparateWaveDecision": True,
                    "acquisitionAuthorized": False,
                }
            ],
        )

    def test_12_apfs_shared_ancestor_publication_completes_once(self) -> None:
        claim_ancestor = (self.fixture.root / runner.CLAIM_PATH).parent
        result_ancestor = (self.fixture.root / runner.RESULT_PATH).parent
        self.assertIn(
            claim_ancestor,
            (self.fixture.root / self.fixture.mod_path).parents,
        )
        self.assertEqual(
            result_ancestor,
            (self.fixture.root / self.fixture.decision_path).parent,
        )
        initial_directory = os.stat(claim_ancestor)
        self.assertEqual(
            runner.directory_identity(initial_directory),
            (
                initial_directory.st_dev,
                initial_directory.st_ino,
                initial_directory.st_mode,
                initial_directory.st_uid,
                initial_directory.st_gid,
            ),
        )
        apfs_sibling_created = mock.Mock(
            st_dev=initial_directory.st_dev,
            st_ino=initial_directory.st_ino,
            st_mode=initial_directory.st_mode,
            st_uid=initial_directory.st_uid,
            st_gid=initial_directory.st_gid,
            st_nlink=initial_directory.st_nlink + 1,
        )
        self.assertEqual(
            runner.directory_identity(initial_directory),
            runner.directory_identity(apfs_sibling_created),
        )
        result = runner.execute_with_authority(
            self.fixture.root,
            self.fixture.permit,
            self.fixture.bindings,
        )
        self.assertEqual(result["fileWriteCount"], 3)
        self.assertEqual(result["networkOperationCount"], 0)
        self.assertFalse(
            result["productEndpointAuthenticationEvaluatedByThisReview"]
        )
        claim_path = self.fixture.root / runner.CLAIM_PATH
        result_path = self.fixture.root / runner.RESULT_PATH
        manifest_path = self.fixture.root / runner.MANIFEST_PATH
        self.assertTrue(claim_path.is_file())
        self.assertTrue(result_path.is_file())
        self.assertTrue(manifest_path.is_file())
        self.assertFalse((self.fixture.root / runner.FAILURE_PATH).exists())
        self.assertEqual(stat.S_IMODE(claim_path.stat().st_mode), 0o600)
        manifest = runner.strict_json(manifest_path.read_bytes())
        result_document = runner.strict_json(result_path.read_bytes())
        self.assertTrue(manifest["manifestWrittenLast"])
        self.assertFalse(manifest["independentReadbackPassed"])
        self.assertTrue(
            result_document["graphDiscovery"][
                "independentReproductionPassed"
            ]
        )
        self.assertEqual(
            manifest["resultRawSha256"],
            sha256(result_path.read_bytes()),
        )
        self.assertEqual(
            manifest["graphSha256"],
            result_document["graphDiscovery"]["graphSha256"],
        )
        self.assertEqual(
            result_document["nextAction"],
            manifest["nextAction"],
        )
        self.assertEqual(
            manifest["nextAction"],
            runner.INDEPENDENT_READBACK_NEXT_ACTION,
        )
        classification, _ = runner.classify_one_use_state(
            self.fixture.root,
            self.fixture.permit,
        )
        self.assertEqual(classification, "success")
        with self.assertRaises(runner.ReviewFailure) as caught:
            runner.execute_with_authority(
                self.fixture.root,
                self.fixture.permit,
                self.fixture.bindings,
            )
        self.assertEqual(caught.exception.code, "E_ONE_USE_STATE_PRESENT")

    def test_13_postclaim_analysis_failure_is_durable_and_consumed(self) -> None:
        bad_mod = b"module example.com/wrong\n"
        (self.fixture.root / self.fixture.mod_path).write_bytes(bad_mod)
        os.chmod(self.fixture.root / self.fixture.mod_path, 0o600)
        bindings = copy.deepcopy(self.fixture.bindings)
        bindings[2]["rawSha256"] = sha256(bad_mod)
        bindings[2]["maximumBytes"] = len(bad_mod)
        permit = runner.build_expected_permit(
            decision_binding=self.fixture.permit["decisionBinding"],
            input_bindings=bindings,
            runner_raw_sha256=sha256(RUNNER_PATH.read_bytes()),
            runner_tests_raw_sha256=sha256(Path(__file__).read_bytes()),
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.execute_with_authority(
                self.fixture.root,
                permit,
                bindings,
            )
        self.assertTrue((self.fixture.root / runner.CLAIM_PATH).is_file())
        self.assertTrue((self.fixture.root / runner.FAILURE_PATH).is_file())
        self.assertFalse((self.fixture.root / runner.RESULT_PATH).exists())
        self.assertFalse((self.fixture.root / runner.MANIFEST_PATH).exists())
        failure = runner.strict_json(
            (self.fixture.root / runner.FAILURE_PATH).read_bytes()
        )
        self.assertFalse(failure["automaticRetryAllowed"])
        classification, _ = runner.classify_one_use_state(
            self.fixture.root,
            permit,
        )
        self.assertEqual(classification, "failure")

    def test_14_partial_or_conflicting_namespace_is_blocked(self) -> None:
        path = self.fixture.root / runner.CLAIM_PATH
        path.write_bytes(b"claim")
        os.chmod(path, 0o600)
        classification, kinds = runner.classify_one_use_state(
            self.fixture.root,
            self.fixture.permit,
        )
        self.assertEqual(classification, "blocked")
        self.assertEqual(kinds["claim"], "regular")

    def test_15_error_schema_is_bounded_and_never_requests_authentication(self) -> None:
        failure = runner.ReviewFailure(
            "E_GRAPH_BOUND",
            "graph",
            tuple_id="wave1-001",
            tuple_order=1,
            observations={
                "graphNodeCount": 513,
                "secret": 9,
            },
        )
        document = runner.runner_error_document(failure)
        self.assertEqual(document["safeNumericObservations"], {"graphNodeCount": 513})
        self.assertFalse(document["automaticRetryAllowed"])
        self.assertFalse(document["repositoryOwnerIdentityProofRequired"])
        self.assertFalse(document["externalAuthenticationRequired"])
        self.assertFalse(document["userActionRequired"])
        self.assertFalse(
            document["productEndpointAuthenticationEvaluatedByThisReview"]
        )

    def test_16_runner_has_no_network_subprocess_or_extraction_surface(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "import socket",
            "from socket",
            "import subprocess",
            "from subprocess",
            "import urllib",
            "from urllib",
            ".extract(",
            ".extractall(",
            "os.system(",
            "os.popen(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("zipfile.ZipFile(io.BytesIO(raw)", source)
        self.assertIn("manifestWrittenLast", source)

    def test_17_preclaim_hash_failure_writes_nothing(self) -> None:
        bindings = copy.deepcopy(self.fixture.bindings)
        bindings[-1]["rawSha256"] = "0" * 64
        with self.assertRaises(runner.ReviewFailure):
            runner.execute_with_authority(
                self.fixture.root,
                self.fixture.permit,
                bindings,
            )
        for path in (
            runner.CLAIM_PATH,
            runner.RESULT_PATH,
            runner.FAILURE_PATH,
            runner.MANIFEST_PATH,
        ):
            self.assertFalse((self.fixture.root / path).exists())

    def test_18_filename_suffix_profiles_match_frozen_go_rules(self) -> None:
        self.assertTrue(
            runner.filename_active_for_profile(
                "pkg/source_linux_arm64.go",
                "android",
                "arm64",
            )
        )
        self.assertFalse(
            runner.filename_active_for_profile(
                "pkg/source_linux_arm64.go",
                "darwin",
                "arm64",
            )
        )
        self.assertTrue(
            runner.filename_active_for_profile(
                "pkg/source_android_extra.go",
                "darwin",
                "arm64",
            )
        )
        self.assertFalse(
            runner.filename_active_for_profile(
                "pkg/source_android_amd64.go",
                "android",
                "arm64",
            )
        )
        self.assertFalse(
            runner.filename_active_for_profile(
                "pkg/_hidden_linux_arm64.go",
                "android",
                "arm64",
            )
        )
        self.assertFalse(
            runner.filename_active_for_profile(
                "pkg/.hidden.go",
                "android",
                "arm64",
            )
        )
        self.assertFalse(
            runner.filename_active_for_profile(
                "pkg/_hidden/source.go",
                "android",
                "arm64",
            )
        )
        self.assertFalse(
            runner.filename_active_for_profile(
                "pkg/.hidden/source.go",
                "android",
                "arm64",
            )
        )
        self.assertTrue(
            runner.filename_active_for_profile(
                "pkg/source.extra_linux_amd64.go",
                "android",
                "arm64",
            )
        )
        self.assertTrue(
            runner.filename_active_for_profile(
                "pkg/source_linux_arm64.extra.go",
                "android",
                "arm64",
            )
        )
        self.assertFalse(
            runner.filename_active_for_profile(
                "pkg/source_linux_arm64.extra.go",
                "darwin",
                "arm64",
            )
        )

    def test_19_selected_unavailable_exact_pair_is_frontier_not_source(self) -> None:
        def source(path: str, imports: list[str]) -> dict[str, object]:
            return {
                "sourceClass": "production",
                "buildExpression": None,
                "relativePath": path,
                "imports": imports,
            }

        archives = [
            {
                "kind": "root_zip",
                "module": "example.com/root",
                "version": "v1.0.0",
                "sources": [
                    source(
                        "root.go",
                        ["example.com/b/pkg", "example.com/c/pkg"],
                    )
                ],
            },
            {
                "kind": "zip",
                "module": "example.com/b",
                "version": "v1.2.0",
                "sources": [
                    source("pkg/b.go", ["example.com/stale-only/pkg"])
                ],
            },
            {
                "kind": "zip",
                "module": "example.com/c",
                "version": "v1.0.0",
                "sources": [source("pkg/c.go", [])],
            },
        ]
        metadata = [
            {
                "module": "example.com/root",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/root",
                    "requires": [
                        {"module": "example.com/b", "version": "v1.2.0"},
                        {"module": "example.com/c", "version": "v1.0.0"},
                    ],
                    "excludes": [],
                },
            },
            {
                "module": "example.com/b",
                "version": "v1.2.0",
                "metadata": {
                    "module": "example.com/b",
                    "requires": [
                        {
                            "module": "example.com/stale-only",
                            "version": "v1.0.0",
                        }
                    ],
                    "excludes": [],
                },
            },
            {
                "module": "example.com/c",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/c",
                    "requires": [
                        {"module": "example.com/b", "version": "v1.3.0"}
                    ],
                    "excludes": [],
                },
            },
        ]
        graph = runner.build_graph(
            archives,
            metadata,
            [{"profileId": "android", "tags": ["android", "arm64"]}],
            {"maximumGraphNodes": 32, "maximumGraphEdges": 64},
        )
        self.assertEqual(
            graph["newlyReachableTuples"],
            [
                {
                    "module": "example.com/b",
                    "version": "v1.3.0",
                    "selectedByGraphAlgorithm": True,
                    "requiresSeparateWaveDecision": True,
                    "acquisitionAuthorized": False,
                },
                {
                    "module": "example.com/stale-only",
                    "version": "v1.0.0",
                    "selectedByGraphAlgorithm": True,
                    "requiresSeparateWaveDecision": True,
                    "acquisitionAuthorized": False,
                }
            ],
        )
        self.assertIn(
            {
                "module": "example.com/b",
                "version": "v1.3.0",
                "isRoot": False,
                "sourceAvailable": False,
                "frontier": True,
                "selectedForModule": True,
            },
            graph["moduleNodes"],
        )
        self.assertFalse(
            any(
                row["module"] == "example.com/b"
                for row in graph["nodes"]
            )
        )
        self.assertFalse(
            any(
                row["targetModule"] == "example.com/stale-only"
                for row in graph["edges"]
            )
        )
        b_edges = [
            row
            for row in graph["edges"]
            if row["targetModule"] == "example.com/b"
        ]
        self.assertTrue(b_edges)
        self.assertTrue(
            all(
                row["targetVersion"] == "v1.3.0"
                and row["edgeClass"] == "declared_external"
                for row in b_edges
            )
        )
        self.assertEqual(graph["moduleNodeCount"], len(graph["moduleNodes"]))
        self.assertEqual(graph["moduleEdgeCount"], len(graph["moduleEdges"]))
        self.assertEqual(
            graph["moduleNodeSetSha256"],
            sha256(runner.canonical_json_bytes(graph["moduleNodes"])),
        )
        self.assertEqual(
            graph["moduleEdgeSetSha256"],
            sha256(runner.canonical_json_bytes(graph["moduleEdges"])),
        )
        self.assertEqual(
            graph["reconstructions"][0]["reconstructionSha256"],
            graph["reconstructions"][1]["reconstructionSha256"],
        )

    def test_20_reconstruction_mismatch_fails_closed(self) -> None:
        with runner.HeldInputSet(
            self.fixture.root,
            self.fixture.bindings,
        ) as held:
            original = runner.package_graph_fixed_point

            def divergent(*args: object, **kwargs: object) -> object:
                nodes, edges = original(*args, **kwargs)
                return [
                    *nodes,
                    {
                        "profileId": "android",
                        "module": "example.com/divergent",
                        "package": "example.com/divergent",
                    },
                ], edges

            with mock.patch.object(
                runner,
                "package_graph_fixed_point",
                side_effect=divergent,
            ):
                with self.assertRaises(runner.ReviewFailure) as caught:
                    runner.review_held_inputs(
                        self.fixture.permit,
                        self.fixture.bindings,
                        held,
                    )
        self.assertEqual(caught.exception.code, "E_GRAPH_SEMANTICS")

    def test_21_mvs_preserves_edges_from_every_visited_version_vertex(self) -> None:
        metadata = [
            {
                "module": "example.com/root",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/root",
                    "requires": [
                        {"module": "example.com/a", "version": "v1.0.0"},
                        {"module": "example.com/c", "version": "v1.0.0"},
                    ],
                },
            },
            {
                "module": "example.com/a",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/a",
                    "requires": [
                        {"module": "example.com/d", "version": "v1.0.0"}
                    ],
                },
            },
            {
                "module": "example.com/c",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/c",
                    "requires": [
                        {"module": "example.com/a", "version": "v2.0.0"}
                    ],
                },
            },
            {
                "module": "example.com/d",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/d",
                    "requires": [],
                },
            },
        ]
        acquired = {
            ("example.com/root", "v1.0.0"),
            ("example.com/a", "v1.0.0"),
            ("example.com/c", "v1.0.0"),
            ("example.com/d", "v1.0.0"),
        }
        bfs = runner.module_graph(
            "example.com/root",
            metadata,
            acquired,
            32,
            64,
        )
        monotone = runner.module_graph_monotone(
            "example.com/root",
            metadata,
            acquired,
            32,
            64,
        )
        self.assertEqual(
            runner.canonical_json_bytes(bfs),
            runner.canonical_json_bytes(monotone),
        )
        selected, nodes, edges = bfs
        self.assertEqual(selected["example.com/a"], "v2.0.0")
        self.assertEqual(selected["example.com/d"], "v1.0.0")
        self.assertIn(
            {
                "module": "example.com/a",
                "version": "v1.0.0",
                "isRoot": False,
                "sourceAvailable": True,
                "frontier": False,
                "selectedForModule": False,
            },
            nodes,
        )
        self.assertIn(
            {
                "module": "example.com/a",
                "version": "v2.0.0",
                "isRoot": False,
                "sourceAvailable": False,
                "frontier": True,
                "selectedForModule": True,
            },
            nodes,
        )
        self.assertTrue(
            any(
                row["fromModule"] == "example.com/a"
                and row["fromVersion"] == "v1.0.0"
                and row["requiredModule"] == "example.com/d"
                and row["requestedVersion"] == "v1.0.0"
                for row in edges
            )
        )

    def test_22_root_replace_exclude_fail_dependency_inventory_does_not_select(self) -> None:
        source = {
            "sourceClass": "production",
            "buildExpression": None,
            "relativePath": "root.go",
            "imports": ["example.com/dep"],
        }
        archives = [
            {
                "kind": "root_zip",
                "module": "example.com/root",
                "version": "v1.0.0",
                "sources": [source],
            },
            {
                "kind": "zip",
                "module": "example.com/dep",
                "version": "v1.0.0",
                "sources": [
                    {
                        "sourceClass": "production",
                        "buildExpression": None,
                        "relativePath": "dep.go",
                        "imports": [],
                    }
                ],
            },
        ]
        metadata = [
            {
                "module": "example.com/root",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/root",
                    "requires": [
                        {"module": "example.com/dep", "version": "v1.0.0"}
                    ],
                    "replaces": [["synthetic-root-replace"]],
                    "excludes": [],
                },
            },
            {
                "module": "example.com/dep",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/dep",
                    "requires": [],
                    "replaces": [["inventory-only"]],
                    "excludes": [
                        {"module": "example.com/dep", "version": "v1.0.0"}
                    ],
                },
            },
        ]
        profile = [{"profileId": "android", "tags": ["android", "arm64"]}]
        limits = {"maximumGraphNodes": 32, "maximumGraphEdges": 64}
        with self.assertRaises(runner.ReviewFailure) as caught:
            runner.build_graph(archives, metadata, profile, limits)
        self.assertEqual(caught.exception.code, "E_GRAPH_SEMANTICS")
        metadata[0]["metadata"]["replaces"] = []
        metadata[0]["metadata"]["excludes"] = [
            {"module": "example.com/dep", "version": "v1.0.0"}
        ]
        with self.assertRaises(runner.ReviewFailure) as caught:
            runner.build_graph(archives, metadata, profile, limits)
        self.assertEqual(caught.exception.code, "E_GRAPH_SEMANTICS")
        metadata[0]["metadata"]["excludes"] = []
        graph = runner.build_graph(archives, metadata, profile, limits)
        self.assertTrue(
            any(
                row["module"] == "example.com/dep"
                and row["version"] == "v1.0.0"
                and row["selectedForModule"]
                for row in graph["moduleNodes"]
            )
        )
        self.assertEqual(graph["newlyReachableTuples"], [])

    def test_23_no_frontier_routes_to_byte_readback_not_graph_reproduction(self) -> None:
        status, post_readback_next_action = runner.graph_result_routing(
            {
                "newTupleCount": 0,
                "unmappedExternalImportCount": 0,
                "unresolvedDeclaredExternalImportCount": 0,
                "fixedPointReached": True,
                "independentReproductionPassed": True,
                "reconstructionCount": 2,
            }
        )
        self.assertEqual(
            status,
            (
                "wave1_graph_discovery_complete_fixed_point_candidate_"
                "pending_independent_readback"
            ),
        )
        self.assertEqual(
            post_readback_next_action,
            runner.FIXED_POINT_POST_READBACK_ACTION,
        )

    def test_24_build_header_state_machine_matches_leading_comment_rules(self) -> None:
        long_header = "\n".join(
            f"// synthetic license line {index}"
            for index in range(100)
        )
        expression = runner.extract_build_expression(
            long_header
            + "\n   //go:build linux && arm64\n\npackage p\n"
        )
        self.assertEqual(expression, "linux && arm64")
        block_expression = runner.extract_build_expression(
            (
                "/*\n"
                "bare license text without a leading star\n"
                "//go:build windows\n"
                "// +build windows\n"
                "*/\n"
                "   //go:build android && arm64\n"
                "\npackage p\n"
            )
        )
        self.assertEqual(block_expression, "android && arm64")
        legacy = runner.extract_build_expression(
            "   // +build android,arm64\n\npackage p\n"
        )
        self.assertTrue(
            runner.active_for_profile(
                legacy,
                {"android", "arm64"},
            )
        )
        self.assertIsNone(
            runner.extract_build_expression(
                "   // +build android,arm64\npackage p\n"
            )
        )
        self.assertEqual(
            runner.extract_build_expression(
                "   //go:build android && arm64\npackage p\n"
            ),
            "android && arm64",
        )
        self.assertEqual(
            runner.extract_build_expression(
                (
                    "//go:build android && arm64\n"
                    "// +build linux,,arm64\n\n"
                    "package p\n"
                )
            ),
            "android && arm64",
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.extract_build_expression(
                "// +build linux,,arm64\n\npackage p\n"
            )
        self.assertIsNone(
            runner.extract_build_expression(
                "//go:builder linux\n// +builder linux\n\npackage p\n"
            )
        )
        with self.assertRaises(runner.ReviewFailure):
            runner.extract_build_expression(
                "/* unterminated\nbare text\npackage p\n"
            )
        with self.assertRaises(runner.ReviewFailure):
            runner.extract_build_expression(
                "//go:build\n\npackage p\n"
            )
        with self.assertRaises(runner.ReviewFailure):
            runner.extract_build_expression(
                "//go:build android\n//go:build darwin\npackage p\n"
            )

    def test_25_module_reconstruction_mismatch_fails_closed(self) -> None:
        with runner.HeldInputSet(
            self.fixture.root,
            self.fixture.bindings,
        ) as held:
            original = runner.module_graph_monotone

            def divergent(*args: object, **kwargs: object) -> object:
                selected, nodes, edges = original(*args, **kwargs)
                return selected, [
                    *nodes,
                    {
                        "module": "example.com/divergent",
                        "version": "v1.0.0",
                        "isRoot": False,
                        "sourceAvailable": False,
                        "frontier": True,
                        "selectedForModule": False,
                    },
                ], edges

            with mock.patch.object(
                runner,
                "module_graph_monotone",
                side_effect=divergent,
            ):
                with self.assertRaises(runner.ReviewFailure) as caught:
                    runner.review_held_inputs(
                        self.fixture.permit,
                        self.fixture.bindings,
                        held,
                    )
        self.assertEqual(caught.exception.code, "E_GRAPH_SEMANTICS")

    def test_26_unmapped_external_import_blocks_fixed_point_and_readback_route(self) -> None:
        archives = [
            {
                "kind": "root_zip",
                "module": "example.com/root",
                "version": "v1.0.0",
                "sources": [
                    {
                        "sourceClass": "production",
                        "buildExpression": None,
                        "relativePath": "root.go",
                        "imports": ["unknown.example/pkg"],
                    }
                ],
            }
        ]
        metadata = [
            {
                "module": "example.com/root",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/root",
                    "requires": [],
                    "replaces": [],
                    "excludes": [],
                },
            }
        ]
        graph = runner.build_graph(
            archives,
            metadata,
            [{"profileId": "android", "tags": ["android", "arm64"]}],
            {"maximumGraphNodes": 16, "maximumGraphEdges": 16},
        )
        self.assertEqual(graph["newTupleCount"], 0)
        self.assertEqual(graph["unmappedExternalImportCount"], 1)
        self.assertEqual(
            graph["unmappedExternalImports"],
            [
                {
                    "profileId": "android",
                    "fromPackage": "example.com/root",
                    "importPath": "unknown.example/pkg",
                }
            ],
        )
        self.assertEqual(
            graph["unmappedExternalImportSetSha256"],
            sha256(
                runner.canonical_json_bytes(
                    graph["unmappedExternalImports"]
                )
            ),
        )
        self.assertFalse(graph["fixedPointReached"])
        status, post_readback_next_action = runner.graph_result_routing(graph)
        self.assertEqual(
            status,
            (
                "wave1_graph_discovery_complete_external_import_"
                "resolution_required"
            ),
        )
        self.assertEqual(
            post_readback_next_action,
            runner.EXTERNAL_RESOLUTION_POST_READBACK_ACTION,
        )

    def test_27_declared_missing_package_blocks_fixed_point(self) -> None:
        archives = [
            {
                "kind": "root_zip",
                "module": "example.com/root",
                "version": "v1.0.0",
                "sources": [
                    {
                        "sourceClass": "production",
                        "buildExpression": None,
                        "relativePath": "root.go",
                        "imports": ["example.com/dep/missing"],
                    }
                ],
            },
            {
                "kind": "zip",
                "module": "example.com/dep",
                "version": "v1.0.0",
                "sources": [
                    {
                        "sourceClass": "production",
                        "buildExpression": None,
                        "relativePath": "dep.go",
                        "imports": [],
                    }
                ],
            },
        ]
        metadata = [
            {
                "module": "example.com/root",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/root",
                    "requires": [
                        {"module": "example.com/dep", "version": "v1.0.0"}
                    ],
                    "replaces": [],
                    "excludes": [],
                },
            },
            {
                "module": "example.com/dep",
                "version": "v1.0.0",
                "metadata": {
                    "module": "example.com/dep",
                    "requires": [],
                    "replaces": [],
                    "excludes": [],
                },
            },
        ]
        graph = runner.build_graph(
            archives,
            metadata,
            [{"profileId": "android", "tags": ["android", "arm64"]}],
            {"maximumGraphNodes": 16, "maximumGraphEdges": 16},
        )
        self.assertEqual(graph["newTupleCount"], 0)
        self.assertEqual(graph["unmappedExternalImportCount"], 0)
        self.assertEqual(graph["unresolvedDeclaredExternalImportCount"], 1)
        self.assertEqual(
            graph["unresolvedDeclaredExternalImports"][0],
            {
                "profileId": "android",
                "fromPackage": "example.com/root",
                "importPath": "example.com/dep/missing",
                "targetModule": "example.com/dep",
                "targetVersion": "v1.0.0",
            },
        )
        self.assertEqual(
            graph["unresolvedDeclaredExternalImportSetSha256"],
            sha256(
                runner.canonical_json_bytes(
                    graph["unresolvedDeclaredExternalImports"]
                )
            ),
        )
        self.assertFalse(graph["fixedPointReached"])
        self.assertIn(
            "external_import_resolution_required",
            runner.graph_result_routing(graph)[0],
        )

    def test_28_monotone_edge_mapping_mutation_fails_closed(self) -> None:
        with runner.HeldInputSet(
            self.fixture.root,
            self.fixture.bindings,
        ) as held:
            original = runner.package_edge_monotone

            def divergent(*args: object, **kwargs: object) -> object:
                row = original(*args, **kwargs)
                if row["edgeClass"] == "standard_library":
                    row = {
                        **row,
                        "edgeClass": "unmapped_external",
                    }
                return row

            with mock.patch.object(
                runner,
                "package_edge_monotone",
                side_effect=divergent,
            ):
                with self.assertRaises(runner.ReviewFailure) as caught:
                    runner.review_held_inputs(
                        self.fixture.permit,
                        self.fixture.bindings,
                        held,
                    )
        self.assertEqual(caught.exception.code, "E_GRAPH_SEMANTICS")

    def test_29_monotone_frontier_filename_and_build_mutations_fail_closed(self) -> None:
        mutations: list[tuple[str, str, object]] = []
        frontier_original = runner.exact_frontier_monotone

        def frontier_divergent(*args: object, **kwargs: object) -> object:
            return [
                *frontier_original(*args, **kwargs),
                {
                    "module": "example.com/divergent",
                    "version": "v1.0.0",
                    "selectedByGraphAlgorithm": False,
                    "requiresSeparateWaveDecision": True,
                    "acquisitionAuthorized": False,
                },
            ]

        mutations.append(
            ("frontier", "exact_frontier_monotone", frontier_divergent)
        )
        filename_original = runner.filename_active_for_profile_monotone

        def filename_divergent(
            relative: str,
            goos: str,
            goarch: str,
        ) -> bool:
            if relative == "pkg/dep.go":
                return False
            return filename_original(relative, goos, goarch)

        mutations.append(
            (
                "filename",
                "filename_active_for_profile_monotone",
                filename_divergent,
            )
        )
        build_original = runner.active_for_profile_monotone
        call_count = 0

        def build_divergent(
            expression: str | None,
            tags: object,
        ) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return False
            return build_original(expression, tags)

        mutations.append(
            ("build", "active_for_profile_monotone", build_divergent)
        )
        with runner.HeldInputSet(
            self.fixture.root,
            self.fixture.bindings,
        ) as held:
            for label, attribute, mutation in mutations:
                with self.subTest(label=label):
                    call_count = 0
                    with mock.patch.object(
                        runner,
                        attribute,
                        side_effect=mutation,
                    ):
                        with self.assertRaises(
                            runner.ReviewFailure
                        ) as caught:
                            runner.review_held_inputs(
                                self.fixture.permit,
                                self.fixture.bindings,
                                held,
                            )
                    self.assertEqual(
                        caught.exception.code,
                        "E_GRAPH_SEMANTICS",
                    )

    def test_30_held_input_ancestor_replacement_still_fails_closed(self) -> None:
        accepted = (self.fixture.root / self.fixture.mod_path).parent
        displaced = accepted.with_name("accepted-displaced")
        with runner.HeldInputSet(
            self.fixture.root,
            self.fixture.bindings,
        ) as held:
            accepted.rename(displaced)
            accepted.mkdir(mode=0o700)
            with self.assertRaises(runner.ReviewFailure) as caught:
                held.final_barrier()
        self.assertEqual(caught.exception.code, "E_HELD_SET")

    def test_31_output_parent_replacement_and_aba_are_safe(self) -> None:
        parent_relative = runner.CLAIM_PATH.rsplit("/", 1)[0]
        named_parent = self.fixture.root / parent_relative
        displaced = named_parent.with_name("dependencies-displaced")
        replacement = named_parent.with_name("dependencies-replacement")
        probe_name = ".held-output-aba-probe"
        with runner.HeldOutputDirectory(
            self.fixture.root,
            parent_relative,
        ) as held_parent:
            named_parent.rename(displaced)
            named_parent.mkdir(mode=0o700)
            with self.assertRaises(runner.ReviewFailure) as caught:
                held_parent.barrier()
            self.assertEqual(caught.exception.code, "E_PUBLICATION")
            named_parent.rmdir()
            displaced.rename(named_parent)
            held_parent.barrier()

            real_listdir = runner.os.listdir
            real_fsync = runner.os.fsync
            swapped = False
            restored = False

            def swap_after_listdir(fd: int) -> list[str]:
                nonlocal swapped
                entries = real_listdir(fd)
                if fd == held_parent.fd and not swapped:
                    named_parent.rename(displaced)
                    named_parent.mkdir(mode=0o700)
                    swapped = True
                return entries

            def restore_before_post_barrier(fd: int) -> None:
                nonlocal restored
                real_fsync(fd)
                if fd == held_parent.fd and swapped and not restored:
                    named_parent.rename(replacement)
                    displaced.rename(named_parent)
                    restored = True

            with (
                mock.patch.object(
                    runner.os,
                    "listdir",
                    side_effect=swap_after_listdir,
                ),
                mock.patch.object(
                    runner.os,
                    "fsync",
                    side_effect=restore_before_post_barrier,
                ),
            ):
                published = runner.write_exclusive(
                    held_parent,
                    probe_name,
                    b"held-parent-only",
                )
            try:
                self.assertTrue(swapped)
                self.assertTrue(restored)
                self.assertEqual(
                    (named_parent / probe_name).read_bytes(),
                    b"held-parent-only",
                )
                self.assertFalse((replacement / probe_name).exists())
                held_parent.barrier()
                published.barrier()
            finally:
                published.close()

    def test_32_v1_v2_history_does_not_block_clean_v3_namespace(self) -> None:
        self.assertTrue(runner.PERMIT_PATH.endswith("execution-permit-v3.json"))
        self.assertTrue(runner.PERMIT_ID.endswith("execution-permit-v3"))
        self.assertTrue(runner.REVIEW_ID.endswith("review-wave1-v3"))
        self.assertTrue(runner.CLAIM_PATH.endswith(".wave-1-review-v3.claim"))
        self.assertTrue(runner.RESULT_PATH.endswith("result-v3.json"))
        self.assertTrue(runner.FAILURE_PATH.endswith("failure-v3.json"))
        self.assertTrue(runner.MANIFEST_PATH.endswith("manifest-v3.json"))
        self.assertEqual(
            runner.STAGING_DIRECTORY_PREFIX,
            ".wave-1-review-v3-staging-",
        )
        historical = {
            (
                f"{runner.BASE}/bounded-dependency-source-review-wave1-"
                "execution-permit-v1.json"
            ): (b'{"historical":"permit-v1"}\n', 0o644),
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-1-review-v1.claim"
            ): (b'{"historical":"claim-v1"}\n', 0o600),
            (
                f"{runner.BASE}/bounded-dependency-source-review-wave1-"
                "failure-v1.json"
            ): (b'{"historical":"failure-v1"}\n', 0o600),
            (
                f"{runner.BASE}/bounded-dependency-source-review-wave1-"
                "execution-permit-v2.json"
            ): (b'{"historical":"permit-v2"}\n', 0o644),
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-1-review-v2.claim"
            ): (b'{"historical":"claim-v2"}\n', 0o600),
            (
                f"{runner.BASE}/bounded-dependency-source-review-wave1-"
                "failure-v2.json"
            ): (b'{"historical":"failure-v2"}\n', 0o600),
        }
        for path, (payload, mode) in historical.items():
            self.fixture._write(path, payload, mode)
        before = {
            path: (self.fixture.root / path).read_bytes()
            for path in historical
        }
        classification, kinds = runner.classify_one_use_state(
            self.fixture.root,
            self.fixture.permit,
        )
        self.assertEqual(classification, "clean")
        self.assertEqual(set(kinds.values()), {"absent"})
        preflight = runner.preflight_with_authority(
            self.fixture.root,
            self.fixture.permit,
            self.fixture.bindings,
        )
        self.assertEqual(preflight["status"], "passed")
        self.assertEqual(
            {
                path: (self.fixture.root / path).read_bytes()
                for path in historical
            },
            before,
        )
        for path in (
            runner.CLAIM_PATH,
            runner.RESULT_PATH,
            runner.FAILURE_PATH,
            runner.MANIFEST_PATH,
        ):
            self.assertFalse((self.fixture.root / path).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
