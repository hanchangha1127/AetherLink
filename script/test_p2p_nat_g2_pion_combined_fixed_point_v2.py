#!/usr/bin/env python3
"""Tests for the read-only Wave1+Wave2+Wave3 candidate checker v2."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter():
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
            "combined fixed-point v2 tests require unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_combined_fixed_point_v2.py"


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "combined_fixed_point_v2_tests_target",
        CHECKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("checker load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()


class FakeRunner:
    DEFAULT_MAXIMUM_ARCHIVE_BYTES = 1024 * 1024
    DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE = 100
    DEFAULT_MAXIMUM_ENTRY_BYTES = 1024 * 1024
    zipfile = zipfile
    io = io

    class ReviewFailure(RuntimeError):
        def __init__(
            self,
            code,
            phase,
            *,
            tuple_id=None,
            tuple_order=None,
            resource_kind=None,
            observations=None,
        ):
            super().__init__(code)
            self.code = code
            self.phase = phase
            self.tuple_id = tuple_id
            self.tuple_order = tuple_order
            self.resource_kind = resource_kind
            self.observations = observations

    @staticmethod
    def exact_int(value, *, minimum):
        if type(value) is not int or value < minimum:
            raise FakeRunner.ReviewFailure("E_BOUND", "archive")
        return value

    @staticmethod
    def require(condition, code, phase, **kwargs):
        if not condition:
            raise FakeRunner.ReviewFailure(code, phase, **kwargs)

    @staticmethod
    def _eocd_exact(raw):
        return bool(raw)

    @staticmethod
    def safe_archive_name(name, prefix):
        if not name.startswith(prefix) or name.endswith("/"):
            raise FakeRunner.ReviewFailure("E_ARCHIVE_STRUCTURE", "archive")
        return name

    @staticmethod
    def has_zip64_extra(extra):
        return False

    @staticmethod
    def source_class(relative):
        lower = relative.casefold()
        parts = lower.split("/")
        if parts[-1].endswith("_test.go"):
            return "test"
        if any(part in {"example", "examples", "testdata"} for part in parts[:-1]):
            return "example"
        if any(part in {"cmd", "commands", "tool", "tools"} for part in parts[:-1]):
            return "tool"
        return "production"

    @staticmethod
    def extract_build_expression(text):
        if text.startswith("MALFORMED"):
            raise FakeRunner.ReviewFailure(
                "E_BUILD_CONSTRAINT",
                "source_inventory",
            )
        return None

    @staticmethod
    def parse_go_imports(text):
        if text.startswith("MALFORMED"):
            raise FakeRunner.ReviewFailure(
                "E_IMPORT_PARSE",
                "source_inventory",
            )
        return ["example.invalid/import"] if "IMPORT" in text else []

    @staticmethod
    def is_license_path(relative):
        return False

    @staticmethod
    def special_classes(relative, payload):
        return []

    @staticmethod
    def canonical_json_bytes(value):
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )


def zip_bytes(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
    ) as archive:
        for name, raw in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(info, raw)
    return buffer.getvalue()


def inspect_fixture(relative, payload):
    prefix = "example.test/module@v1.2.3/"
    raw = zip_bytes([(prefix + relative, payload)])
    binding = {
        "module": "example.test/module",
        "version": "v1.2.3",
        "tupleId": "fixture",
        "tupleOrder": 1,
        "kind": "zip",
        "modulePrefix": prefix,
    }
    return CHECKER.inspect_zip_bytes_v2(FakeRunner, raw, binding, {})


class CombinedFixedPointV2Tests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        command = [
            sys.executable,
            "-I",
            "-B",
            "-S",
            str(CHECKER_PATH),
        ]
        cls.live_runs = [
            subprocess.run(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=180,
            )
            for _ in range(2)
        ]

    def test_01_exact_tool_and_predecessor_pins(self):
        self.assertEqual(
            hashlib.sha256(
                (ROOT / CHECKER.V1_CHECKER_PATH).read_bytes()
            ).hexdigest(),
            CHECKER.V1_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / CHECKER.V1_PROVIDER_PATH).read_bytes()
            ).hexdigest(),
            CHECKER.V1_PROVIDER_RAW_SHA256,
        )
        for path, digest in CHECKER.WAVE3_CONTROL_SHA256.items():
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                digest,
            )

    def test_02_only_exact_lowercase_testdata_component_is_preparse_excluded(self):
        yes = [
            "testdata/bad.go",
            "a/testdata/bad.go",
            "a/testdata/deeper/bad.go",
        ]
        no = [
            "TestData/bad.go",
            "mytestdata/bad.go",
            "testdata.go",
            "a/bad_test.go",
            "example/bad.go",
            "tool/bad.go",
        ]
        self.assertTrue(all(CHECKER.exact_lowercase_testdata_component(v) for v in yes))
        self.assertTrue(
            all(not CHECKER.exact_lowercase_testdata_component(v) for v in no)
        )

    def test_03_testdata_malformed_source_is_inventory_preserved(self):
        result = inspect_fixture("testdata/bad.go", b"MALFORMED")
        self.assertEqual(result["entryCount"], 1)
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(len(result["testdataSemanticExclusions"]), 1)
        source = result["sources"][0]
        excluded = result["testdataSemanticExclusions"][0]
        self.assertEqual(source["relativePath"], "testdata/bad.go")
        self.assertEqual(source["sourceClass"], "example")
        self.assertIsNone(source["buildExpression"])
        self.assertEqual(source["imports"], [])
        self.assertFalse(source["semanticParsingPerformed"])
        self.assertEqual(
            source["graphExclusionReason"],
            "exact_lowercase_testdata_directory_component",
        )
        self.assertEqual(source["rawSha256"], excluded["rawSha256"])
        self.assertEqual(source["rawByteSize"], len(b"MALFORMED"))
        invalid_utf8 = inspect_fixture("testdata/invalid.go", b"\xff")
        self.assertFalse(
            invalid_utf8["sources"][0]["semanticParsingPerformed"],
        )
        self.assertEqual(
            invalid_utf8["sources"][0]["rawSha256"],
            hashlib.sha256(b"\xff").hexdigest(),
        )

    def test_04_case_suffix_test_example_and_tool_remain_strict(self):
        for relative in (
            "TestData/bad.go",
            "mytestdata/bad.go",
            "bad_test.go",
            "example/bad.go",
            "tool/bad.go",
        ):
            with self.subTest(relative=relative):
                with self.assertRaises(FakeRunner.ReviewFailure):
                    inspect_fixture(relative, b"MALFORMED")

    def test_05_testdata_imports_do_not_enter_graph_semantics(self):
        result = inspect_fixture(
            "testdata/ignored.go",
            b"package ignored\n// IMPORT\n",
        )
        self.assertEqual(result["sources"][0]["imports"], [])
        self.assertEqual(len(result["testdataSemanticExclusions"]), 1)

    def test_06_production_source_is_still_strict_and_parsed(self):
        with self.assertRaises(FakeRunner.ReviewFailure):
            inspect_fixture("production.go", b"MALFORMED")
        with self.assertRaises(FakeRunner.ReviewFailure) as invalid_utf8:
            inspect_fixture("production.go", b"\xff")
        self.assertEqual(invalid_utf8.exception.code, "E_IMPORT_PARSE")
        result = inspect_fixture(
            "production.go",
            b"package production\n// IMPORT\n",
        )
        self.assertEqual(
            result["sources"][0]["imports"],
            ["example.invalid/import"],
        )
        self.assertTrue(
            result["sources"][0]["semanticParsingPerformed"],
        )
        self.assertIsNone(
            result["sources"][0]["graphExclusionReason"],
        )
        self.assertEqual(result["testdataSemanticExclusions"], [])

    def test_07_error_output_is_canonical_authentication_free(self):
        value = json.loads(CHECKER.error_document_bytes())
        self.assertFalse(value["externalAuthenticationRequired"])
        self.assertFalse(value["userActionRequired"])
        self.assertEqual(value["networkOperationCount"], 0)
        self.assertEqual(value["sourceExecutionCount"], 0)
        self.assertEqual(value["fileWriteCount"], 0)
        expected = (
            json.dumps(
                value,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        self.assertEqual(CHECKER.error_document_bytes(), expected)

    def test_08_route_and_closure_are_graph_derived(self):
        v1 = type(
            "V1",
            (),
            {
                "route_for_graph": staticmethod(
                    lambda graph: {
                        "route": (
                            "fixed_point_candidate"
                            if graph["fixedPointReached"]
                            else "next_wave_required"
                        ),
                        "status": "fixture",
                        "nextAction": "fixture",
                    }
                )
            },
        )
        self.assertEqual(
            v1.route_for_graph({"fixedPointReached": True})["route"],
            "fixed_point_candidate",
        )
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '"dependencyFixedPointReached": fixed_point',
            source,
        )
        self.assertNotIn(
            '"dependencyFixedPointReached": False',
            source,
        )

    def test_09_static_surface_is_read_only_offline_and_has_no_record_mode(self):
        source = CHECKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_imports = {
            "requests",
            "socket",
            "subprocess",
            "urllib",
            "http",
            "ftplib",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(
                    all(alias.name.split(".")[0] not in forbidden_imports for alias in node.names)
                )
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(
                    (node.module or "").split(".")[0],
                    forbidden_imports,
                )
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    self.assertNotIn(
                        node.func.attr,
                        {
                            "write_bytes",
                            "write_text",
                            "replace",
                            "rename",
                            "unlink",
                            "mkdir",
                            "makedirs",
                        },
                    )
        self.assertNotIn("--execute", source)
        self.assertNotIn("--record", source)
        self.assertNotIn("input(", source)
        self.assertNotIn("getpass", source)

    def test_10_cli_error_is_stderr_free_and_content_free(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(CHECKER_PATH),
                "--not-a-real-option",
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(completed.stdout, CHECKER.error_document_bytes())

    def test_11_live_candidate_is_canonical_exact_and_non_authorizing(self):
        completed = self.live_runs[0]
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(completed.stderr, b"")
        candidate = json.loads(completed.stdout)
        self.assertEqual(candidate["schemaVersion"], "2.0")
        inputs = candidate["inputSet"]
        self.assertEqual(inputs["heldSourceInputCount"], 101)
        self.assertEqual(inputs["resourceCount"], 100)
        self.assertEqual(inputs["modCount"], 50)
        self.assertEqual(inputs["zipCount"], 50)
        self.assertEqual(inputs["wave1ResourceCount"], 38)
        self.assertEqual(inputs["wave2ResourceCount"], 30)
        self.assertEqual(inputs["wave3ResourceCount"], 32)
        self.assertEqual(inputs["uniqueModuleVersionTupleCount"], 50)
        self.assertEqual(len(inputs["sourceBindings"]), 101)
        self.assertEqual(
            inputs["aggregateRawByteSize"],
            73_022_054,
        )
        self.assertEqual(
            candidate["status"],
            "combined_graph_discovery_complete_next_wave_required",
        )
        self.assertEqual(candidate["route"], "next_wave_required")
        graph = candidate["graphDiscovery"]
        self.assertEqual(graph["newTupleCount"], 16)
        self.assertFalse(graph["fixedPointReached"])
        self.assertEqual(graph["graphNodeCount"], 132)
        self.assertEqual(graph["graphEdgeCount"], 1_047)
        self.assertEqual(graph["moduleNodeCount"], 67)
        self.assertEqual(graph["moduleEdgeCount"], 181)
        expected_graph_hashes = {
            "nodeSetSha256":
                "970144c5bd6c1a7d8a13a8bdd5c9efc63fc81afab5860ca8fa77fce49871601a",
            "edgeSetSha256":
                "25cb01585c5d7fc4ec8840d038a195c513e0383e2a4931947312ea9e47e3db47",
            "moduleNodeSetSha256":
                "c28bd8fd5499381466b9a32f5574162e32966527d921da976e0a42118e2af148",
            "moduleEdgeSetSha256":
                "9c79640ccabf8fa415bfefa0ca4908bf9cfed05d48821f65873e27f929fc770c",
            "moduleGraphAndFrontierSha256":
                "5022008181e58b433604617df013a8998b21eeba20f9ea8d4c96a767d161090d",
            "reconstructionProjectionSha256":
                "a824e5e3bf5fe0ede2c795192c3102a5f8d607309b3409073163de1313a23fb5",
            "graphSha256":
                "a824e5e3bf5fe0ede2c795192c3102a5f8d607309b3409073163de1313a23fb5",
        }
        for key, expected in expected_graph_hashes.items():
            self.assertEqual(graph[key], expected)
        coverage = candidate["coverage"]
        self.assertEqual(coverage["archiveCount"], 51)
        self.assertEqual(coverage["aggregateEntryCount"], 14_836)
        self.assertEqual(
            coverage["aggregateUncompressedByteCount"],
            269_029_720,
        )
        self.assertEqual(coverage["goSourceFileCount"], 11_820)
        self.assertEqual(
            coverage["semanticParsedGoSourceCount"],
            10_953,
        )
        self.assertEqual(
            coverage["testdataSemanticExclusionCount"],
            867,
        )
        self.assertEqual(
            coverage["semanticParsedGoSourceCount"]
            + coverage["testdataSemanticExclusionCount"],
            coverage["goSourceFileCount"],
        )
        self.assertEqual(
            coverage["testdataSemanticExclusionSetSha256"],
            "faa269291008c3a4b75e2bce637ccfd562c2c0e72eee98d3d3457f9bc7622603",
        )
        authority = candidate["authority"]
        self.assertTrue(authority)
        self.assertTrue(all(value is False for value in authority.values()))
        counters = candidate["operationCounters"]
        self.assertEqual(counters["networkOperationCount"], 0)
        self.assertEqual(counters["fileWriteCount"], 0)
        self.assertEqual(counters["sourceExecutionCount"], 0)
        self.assertEqual(counters["archiveExtractionCount"], 0)
        canonical = (
            json.dumps(
                candidate,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        self.assertEqual(completed.stdout, canonical)

    def test_12_live_candidate_reproduces_exact_bytes(self):
        first, second = self.live_runs
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, b"")
        self.assertEqual(second.stderr, b"")
        self.assertEqual(first.stdout, second.stdout)

    def test_13_workspace_root_rebind_fails_closed(self):
        class HeldRoot:
            def __init__(self, path):
                self.root_fd = os.open(
                    path,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_CLOEXEC,
                )
                self.barrier_count = 0

            def final_barrier(self):
                self.barrier_count += 1

            def close(self):
                os.close(self.root_fd)
                self.root_fd = -1

        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            workspace = parent / "workspace"
            displaced = parent / "workspace-displaced"
            workspace.mkdir(mode=0o700)
            held_inputs = [HeldRoot(workspace), HeldRoot(workspace)]
            try:
                CHECKER.combined_identity_barrier(workspace, held_inputs)
                self.assertEqual(
                    [held.barrier_count for held in held_inputs],
                    [1, 1],
                )
                workspace.rename(displaced)
                workspace.mkdir(mode=0o700)
                with self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught:
                    CHECKER.combined_identity_barrier(
                        workspace,
                        held_inputs,
                    )
                self.assertEqual(str(caught.exception), "E_ROOT_IDENTITY")
                workspace.rmdir()
                displaced.rename(workspace)
            finally:
                for held in held_inputs:
                    held.close()

    def test_14_explicit_import_into_testdata_is_an_unresolved_gap(self):
        with CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V1_CHECKER_PATH,
            CHECKER.V1_CHECKER_RAW_SHA256,
        ) as v1_held:
            v1 = CHECKER.load_v1_checker(v1_held)
            with v1.PinnedRunnerFile(ROOT) as provider_held:
                runner = v1.load_pinned_runner(provider_held)
                edge = runner.package_edge_bfs(
                    "linux-amd64",
                    "example.test/module",
                    "example.test/module/testdata/fixture",
                    {
                        "example.test/module": {
                            "module": "example.test/module",
                        },
                    },
                    ["example.test/module"],
                    {"example.test/module": "v1.2.3"},
                )
                self.assertEqual(edge["edgeClass"], "declared_external")
                self.assertEqual(
                    edge["targetModule"],
                    "example.test/module",
                )
                self.assertEqual(
                    v1.route_for_graph(
                        {
                            "independentReproductionPassed": True,
                            "reconstructionCount": 2,
                            "fixedPointReached": False,
                            "newTupleCount": 0,
                            "unmappedExternalImportCount": 0,
                            "unresolvedDeclaredExternalImportCount": 1,
                        }
                    )["route"],
                    "external_import_resolution_required",
                )

    def test_15_wave3_resource_mutation_fails_semantic_parity(self):
        with CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V1_CHECKER_PATH,
            CHECKER.V1_CHECKER_RAW_SHA256,
        ) as v1_held:
            v1 = CHECKER.load_v1_checker(v1_held)
            with v1.PinnedRunnerFile(ROOT) as provider_held:
                runner = v1.load_pinned_runner(provider_held)
                with runner.HeldInputSet(
                    ROOT,
                    CHECKER.wave3_control_bindings(),
                ) as control_held:
                    documents = CHECKER.parse_wave3_documents(
                        runner,
                        control_held,
                    )
                    mutated = copy.deepcopy(documents)
                    readback = mutated[CHECKER.WAVE3_READBACK_PATH]
                    readback["verified"]["resources"][0]["rawSha256"] = "0" * 64
                    without_binding = dict(readback)
                    without_binding.pop("contentBinding")
                    mutated_content = CHECKER.sha256_bytes(
                        runner.canonical_json_bytes(without_binding)
                    )
                    readback["contentBinding"]["sha256"] = mutated_content
                    readback_manifest = mutated[
                        CHECKER.WAVE3_READBACK_MANIFEST_PATH
                    ]
                    readback_manifest["receipt"][
                        "contentSha256"
                    ] = mutated_content
                    manifest_without_binding = dict(readback_manifest)
                    manifest_without_binding.pop("contentBinding")
                    mutated_manifest_content = CHECKER.sha256_bytes(
                        runner.canonical_json_bytes(manifest_without_binding)
                    )
                    readback_manifest["contentBinding"][
                        "sha256"
                    ] = mutated_manifest_content
                    with mock.patch.dict(
                        CHECKER.WAVE3_CONTENT_SHA256,
                        {
                            CHECKER.WAVE3_READBACK_PATH:
                                mutated_content,
                            CHECKER.WAVE3_READBACK_MANIFEST_PATH:
                                mutated_manifest_content,
                        },
                    ):
                        with self.assertRaises(
                            CHECKER.CombinedCheckFailure,
                        ) as caught:
                            CHECKER.wave3_request_resources(
                                runner,
                                mutated,
                            )
                    self.assertEqual(
                        str(caught.exception),
                        "E_WAVE3_RESOURCE",
                    )

    def test_16_pinned_code_rejects_hardlink_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = script / "tool.py"
            raw = b"VALUE = 1\n"
            target.write_bytes(raw)
            target.chmod(0o644)
            linked = script / "linked.py"
            os.link(target, linked)
            with self.assertRaises(CHECKER.CombinedCheckFailure):
                CHECKER.PinnedCodeFile(
                    root,
                    "script/tool.py",
                    hashlib.sha256(raw).hexdigest(),
                )
            linked.unlink()
            target.rename(linked)
            target.symlink_to("linked.py")
            with self.assertRaises(OSError):
                CHECKER.PinnedCodeFile(
                    root,
                    "script/tool.py",
                    hashlib.sha256(raw).hexdigest(),
                )


if __name__ == "__main__":
    unittest.main()
