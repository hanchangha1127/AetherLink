#!/usr/bin/env python3
"""Offline tests for the G2 rung-three execution-permit checker.

These tests never read the retained archive. Synthetic temporary files exercise
the safe tracked-reader behavior.
"""

from __future__ import annotations

import ast
import copy
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_RELATIVE_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_permit.py"
CHECKER_SOURCE = ROOT / CHECKER_RELATIVE_PATH
CHECKER_SOURCE_BYTES = CHECKER_SOURCE.read_bytes()
CHECKER_SOURCE_TEXT = CHECKER_SOURCE_BYTES.decode("utf-8")
CHECKER_CODE = compile(
    CHECKER_SOURCE_BYTES,
    CHECKER_RELATIVE_PATH,
    "exec",
    flags=0,
    dont_inherit=True,
    optimize=0,
)
CHECKER = ModuleType("g2_rung3_execution_permit_checker")
CHECKER.__dict__.update(
    {
        "__cached__": None,
        "__file__": str(CHECKER_SOURCE),
        "__loader__": None,
        "__package__": None,
    }
)
exec(CHECKER_CODE, CHECKER.__dict__, CHECKER.__dict__)


def checker_function_source(name: str) -> str:
    tree = ast.parse(CHECKER_SOURCE_TEXT, filename=CHECKER_RELATIVE_PATH)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            source = ast.get_source_segment(CHECKER_SOURCE_TEXT, node)
            if source is not None:
                return source
    raise AssertionError(f"checker function not found: {name}")


class ExecutionPermitCheckerTests(unittest.TestCase):
    def read_json(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_01_runner_interface_is_stable(self) -> None:
        signature = inspect.signature(CHECKER.validate_repository)
        self.assertEqual(tuple(signature.parameters), ("root",))
        self.assertEqual(signature.parameters["root"].default, CHECKER.ROOT)
        self.assertEqual(
            CHECKER.ARCHIVE_RECEIPT_PATH,
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-two/source-acquisition-receipt-v1.json",
        )
        self.assertEqual(CHECKER.ARCHIVE_METADATA_JSON_POINTER, "/archive")
        self.assertEqual(CHECKER.ARCHIVE_PATH_JSON_POINTER, "/archive/path")

    def test_02_strict_json_rejects_duplicate_key(self) -> None:
        with self.assertRaisesRegex(CHECKER.CheckError, "duplicate"):
            CHECKER.strict_json(b'{"a":1,"a":2}\n', "fixture")

    def test_03_strict_json_rejects_cr_and_missing_lf(self) -> None:
        with self.assertRaisesRegex(CHECKER.CheckError, "final LF"):
            CHECKER.strict_json(b"{}", "fixture")
        with self.assertRaisesRegex(CHECKER.CheckError, "CR"):
            CHECKER.strict_json(b"{}\r\n", "fixture")

    def test_04_strict_json_rejects_nonfinite(self) -> None:
        with self.assertRaisesRegex(CHECKER.CheckError, "non-finite"):
            CHECKER.strict_json(b'{"n":NaN}\n', "fixture")

    def test_05_canonical_json_is_sorted_compact_ascii_and_lf(self) -> None:
        self.assertEqual(
            CHECKER.canonical_json_bytes({"z": "\u2603", "a": 1}),
            b'{"a":1,"z":"\\u2603"}\n',
        )

    def test_06_placeholder_walk_reports_exact_locations(self) -> None:
        self.assertEqual(
            CHECKER.unresolved_placeholders(
                {"a": ["ok", "__PENDING_X__"], "b": {"c": "__PENDING_Y__"}}
            ),
            ["$.a[1]", "$.b.c"],
        )

    def test_07_checker_read_allowlist_excludes_build_and_archives(self) -> None:
        self.assertFalse(any(path.startswith("build/") for path in CHECKER.TRACKED_READ_ALLOWLIST))
        self.assertFalse(any(path.endswith(".zip") for path in CHECKER.TRACKED_READ_ALLOWLIST))
        for unsafe in (
            "build/offline-source/example.zip",
            "/absolute/file.json",
            "../escape.json",
            "docs\\escape.json",
        ):
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_relative_path(unsafe)

    def test_08_safe_reader_rejects_final_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_bytes(b"safe\n")
            path = root / CHECKER.CHECKER_PATH
            path.parent.mkdir(parents=True)
            path.symlink_to(target)
            reader = CHECKER.SafeTrackedReader(root)
            with self.assertRaisesRegex(CHECKER.CheckError, "safe read failed"):
                reader.read(CHECKER.CHECKER_PATH)

    def test_09_safe_reader_rejects_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original"
            original.write_bytes(b"safe\n")
            path = root / CHECKER.CHECKER_PATH
            path.parent.mkdir(parents=True)
            os.link(original, path)
            reader = CHECKER.SafeTrackedReader(root)
            with self.assertRaisesRegex(CHECKER.CheckError, "single link"):
                reader.read(CHECKER.CHECKER_PATH)

    def test_10_predecessor_anchors_match_current_tracked_json(self) -> None:
        reader = CHECKER.SafeTrackedReader(ROOT)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        for label, expected in CHECKER.PREDECESSOR_ANCHORS.items():
            CHECKER.verify_json_binding(
                reader,
                permit["authorityBindings"][label],
                expected,
                f"fixture.{label}",
            )

    def test_11_policy_schema_passes_and_extra_key_fails(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        CHECKER.validate_policy(policy)
        mutated = copy.deepcopy(policy)
        mutated["unexpected"] = False
        with self.assertRaisesRegex(CHECKER.CheckError, "exact keys"):
            CHECKER.validate_policy(mutated)

    def test_12_policy_capability_mutation_fails(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        policy["capabilityBoundary"]["networkIoAllowed"] = True
        with self.assertRaisesRegex(CHECKER.CheckError, "capability boundary"):
            CHECKER.validate_policy(policy)

    def test_13_archive_identity_is_metadata_only_and_exact(self) -> None:
        permit = self.read_json(CHECKER.PERMIT_PATH)
        binding = permit["archiveIdentityBinding"]
        CHECKER.validate_archive_identity(binding)
        self.assertFalse(binding["archivePathCopiedIntoPermit"])
        self.assertNotIn("path", binding)
        mutated = copy.deepcopy(binding)
        mutated["expectedBytes"] += 1
        with self.assertRaisesRegex(CHECKER.CheckError, "archive identity"):
            CHECKER.validate_archive_identity(mutated)

    def test_14_permit_and_manifests_expose_unresolved_digest_placeholders(self) -> None:
        values = [
            self.read_json(CHECKER.PERMIT_PATH),
            self.read_json(CHECKER.CORE_MANIFEST_PATH),
            self.read_json(CHECKER.CHECKER_MANIFEST_PATH),
        ]
        placeholders = [
            item
            for value in values
            for item in CHECKER.unresolved_placeholders(value)
        ]
        constants_pending = any(
            not CHECKER.HEX_SHA256.fullmatch(value)
            for value in (
                CHECKER.EXPECTED_POLICY_RAW_SHA256,
                CHECKER.EXPECTED_PERMIT_RAW_SHA256,
                CHECKER.EXPECTED_RUNNER_RAW_SHA256,
                CHECKER.EXPECTED_CORE_MANIFEST_RAW_SHA256,
            )
        )
        if placeholders or constants_pending:
            self.assertTrue(placeholders)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_repository(ROOT)
        else:
            result = CHECKER.validate_repository(ROOT)
            self.assertEqual(
                set(result),
                {"permit", "permitRawSha256", "permitSemanticSha256"},
            )

    def test_15_checker_does_not_import_runner_or_network_modules(self) -> None:
        tree = ast.parse(CHECKER_SOURCE_TEXT, filename=CHECKER_RELATIVE_PATH)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint({"socket", "subprocess", "urllib", "http", "requests"}))
        self.assertNotIn(
            "run_p2p_nat_g2_pion_rung3_offline_review_once",
            imports,
        )

    def test_16_checker_manifest_separates_self_from_pinned_core(self) -> None:
        core = self.read_json(CHECKER.CORE_MANIFEST_PATH)
        checker_manifest = self.read_json(CHECKER.CHECKER_MANIFEST_PATH)
        core_paths = {item["path"] for item in core["artifacts"]}
        checker_paths = {item["path"] for item in checker_manifest["artifacts"]}
        self.assertNotIn(CHECKER.CHECKER_PATH, core_paths)
        self.assertEqual(
            checker_paths,
            {CHECKER.CHECKER_PATH, CHECKER.CHECKER_TEST_PATH},
        )
        self.assertFalse(
            checker_manifest["trustBoundary"]["checkerSelfAuthenticationClaimed"]
        )

    def test_17_output_contract_is_fixed_owner_only_and_no_replace(self) -> None:
        permit = self.read_json(CHECKER.PERMIT_PATH)
        output = permit["outputContract"]
        self.assertEqual(output, CHECKER.EXPECTED_OUTPUT_CONTRACT)
        self.assertEqual(output["directoryMode"], "0700")
        self.assertEqual(output["fileMode"], "0600")
        self.assertTrue(output["atomicNoReplacePublicationRequired"])
        self.assertFalse(output["sourceBodyCopiedToReport"])
        self.assertFalse(output["absolutePathsAllowedInOutput"])
        self.assertFalse(output["secretsAllowedInOutput"])

    def test_18_checker_source_compiles_without_runner_files(self) -> None:
        compile(
            CHECKER_SOURCE_BYTES,
            CHECKER_RELATIVE_PATH,
            "exec",
            flags=0,
            dont_inherit=True,
            optimize=0,
        )

    def test_19_tool_loading_is_distinct_from_reviewed_source_loading(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        for document in (policy, permit):
            boundary = document["capabilityBoundary"]
            self.assertTrue(boundary["verifiedPinnedReviewToolModuleLoadingAllowed"])
            self.assertFalse(boundary["reviewedSourceCodeLoadingAllowed"])
            self.assertNotIn("codeLoadingAllowed", boundary)
        self.assertIn(
            "reviewed_source_dynamic_code_loading",
            policy["forbiddenCapabilities"],
        )
        self.assertNotIn("dynamic_code_loading", policy["forbiddenCapabilities"])

    def test_20_pure_module_guard_accepts_capability_free_source(self) -> None:
        CHECKER.validate_pure_module_source(
            b"import hashlib\nimport json\n\ndef review(data):\n    return hashlib.sha256(data).hexdigest()\n"
        )

    def test_21_pure_module_guard_rejects_forbidden_imports(self) -> None:
        for module in (
            "os", "pathlib", "importlib", "ctypes", "fcntl", "glob", "http",
            "mmap", "multiprocessing", "requests", "shutil", "socket",
            "subprocess", "tempfile", "urllib",
        ):
            with self.subTest(module=module):
                with self.assertRaisesRegex(CHECKER.CheckError, "forbidden imports"):
                    CHECKER.validate_pure_module_source(
                        f"import {module}\n".encode("utf-8")
                    )

    def test_22_pure_module_guard_rejects_forbidden_calls(self) -> None:
        for call in (
            "open", "eval", "exec", "compile", "input", "system", "popen",
            "urlopen",
        ):
            with self.subTest(call=call):
                with self.assertRaisesRegex(CHECKER.CheckError, "forbidden calls"):
                    CHECKER.validate_pure_module_source(
                        f"{call}('x')\n".encode("utf-8")
                    )

    def test_23_actual_pure_module_passes_source_guard(self) -> None:
        raw = (ROOT / CHECKER.PURE_MODULE_PATH).read_bytes()
        CHECKER.validate_pure_module_source(raw)

    def test_24_pure_module_loader_reads_exact_source_once_without_reopen(self) -> None:
        raw = b"value = 7\n"
        compiled_same_object: list[bool] = []
        original_compile = CHECKER.builtins.compile

        def capture_compile(source: object, *args: object, **kwargs: object) -> object:
            if args and args[0] == CHECKER.PURE_MODULE_PATH:
                compiled_same_object.append(source is raw)
            return original_compile(source, *args, **kwargs)

        class OneReadReader:
            read_count = 0

            def __init__(self, _root: Path) -> None:
                pass

            def read(self, path: str) -> bytes:
                self.assert_path(path)
                type(self).read_count += 1
                if type(self).read_count != 1:
                    raise AssertionError("pure module path reopened")
                return raw

            @staticmethod
            def assert_path(path: str) -> None:
                if path != CHECKER.PURE_MODULE_PATH:
                    raise AssertionError(f"unexpected path: {path}")

        digest = CHECKER.sha256_bytes(raw)
        with (
            mock.patch.object(CHECKER, "SafeTrackedReader", OneReadReader),
            mock.patch.object(CHECKER, "EXPECTED_PURE_MODULE_RAW_SHA256", digest),
            mock.patch.object(
                CHECKER.builtins,
                "open",
                side_effect=AssertionError("path reopen forbidden"),
            ),
            mock.patch.object(
                CHECKER.os,
                "open",
                side_effect=AssertionError("descriptor reopen forbidden"),
            ),
            mock.patch.object(CHECKER.builtins, "compile", capture_compile),
        ):
            module = CHECKER.load_validated_pure_module(Path("/not-opened"))
        self.assertEqual(module.value, 7)
        self.assertEqual(OneReadReader.read_count, 1)
        self.assertEqual(compiled_same_object, [True])

    def test_25_pure_module_loader_rejects_unlisted_import(self) -> None:
        raw = b"import math\n"

        class MemoryReader:
            def __init__(self, _root: Path) -> None:
                pass

            def read(self, _path: str) -> bytes:
                return raw

        with (
            mock.patch.object(CHECKER, "SafeTrackedReader", MemoryReader),
            mock.patch.object(
                CHECKER,
                "EXPECTED_PURE_MODULE_RAW_SHA256",
                CHECKER.sha256_bytes(raw),
            ),
        ):
            with self.assertRaisesRegex(CHECKER.CheckError, "outside allowlist"):
                CHECKER.load_validated_pure_module(Path("/not-opened"))

    def test_26_actual_pure_module_loads_from_pinned_in_memory_bytes(self) -> None:
        raw = (ROOT / CHECKER.PURE_MODULE_PATH).read_bytes()
        with mock.patch.object(
            CHECKER,
            "EXPECTED_PURE_MODULE_RAW_SHA256",
            CHECKER.sha256_bytes(raw),
        ):
            module = CHECKER.load_validated_pure_module(ROOT)
        self.assertTrue(callable(module.inspect_module_zip))
        loader_source = checker_function_source("load_validated_pure_module")
        self.assertNotIn("SourceFileLoader", loader_source)
        self.assertNotIn("spec_from_file", loader_source)

    def test_27_checker_test_digest_is_exact_and_mutation_rejected(self) -> None:
        document = self.read_json(CHECKER.CHECKER_MANIFEST_PATH)
        actual = CHECKER.sha256_bytes((ROOT / CHECKER.CHECKER_TEST_PATH).read_bytes())
        document["artifacts"][1]["sha256"] = actual
        reader = CHECKER.SafeTrackedReader(ROOT)
        with mock.patch.object(CHECKER, "EXPECTED_CHECKER_TEST_RAW_SHA256", actual):
            CHECKER.validate_checker_test_binding(document, reader)
            mutated = copy.deepcopy(document)
            mutated["artifacts"][1]["sha256"] = "0" * 64
            with self.assertRaisesRegex(CHECKER.CheckError, "pinned digest"):
                CHECKER.validate_checker_test_binding(mutated, reader)
        self.assertFalse(hasattr(CHECKER, "EXPECTED_CHECKER_RAW_SHA256"))

    def test_28_scope_crosswalk_and_required_status_are_exact(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        self.assertEqual(policy["scope"], CHECKER.EXPECTED_SCOPE)
        self.assertEqual(permit["scope"], CHECKER.EXPECTED_SCOPE)
        for document in (policy, permit):
            plan = document["reviewPlan"]
            self.assertEqual(plan, CHECKER.EXPECTED_REVIEW_PLAN)
            self.assertEqual(
                plan["verificationCrosswalk"],
                CHECKER.VERIFICATION_CROSSWALK,
            )
            self.assertTrue(
                all(
                    unit["status"] == "required_check_not_executed"
                    for unit in plan["verificationUnits"]
                )
            )
        self.assertFalse(permit["nonClaims"]["semanticSourceReviewPerformed"])
        self.assertFalse(permit["nonClaims"]["rungThreeComplete"])

    def test_29_completion_marker_contract_is_fail_closed(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        for document in (policy, permit):
            output = document["outputContract"]
            self.assertFalse(output["resultIsCompletionMarker"])
            self.assertTrue(output["manifestIsSoleCompletionMarker"])
            self.assertTrue(output["manifestRequiresResultHashMatch"])
            self.assertTrue(output["partialPublicationIsIncomplete"])

    def test_30_interpreter_isolation_contract_and_mutation(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        for document in (policy, permit):
            self.assertEqual(
                document["interpreterIsolationContract"],
                CHECKER.EXPECTED_INTERPRETER_ISOLATION_CONTRACT,
            )
        mutated = copy.deepcopy(policy)
        mutated["interpreterIsolationContract"]["requiredSysFlags"]["optimize"] = 1
        with self.assertRaisesRegex(CHECKER.CheckError, "interpreterIsolationContract"):
            CHECKER.validate_policy(mutated)

    def test_31_runner_ast_requires_early_isolation_guard(self) -> None:
        guarded = b'''
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
def require_isolated_interpreter():
    return (
        sys.flags.isolated,
        sys.flags.dont_write_bytecode,
        sys.flags.ignore_environment,
        sys.flags.no_user_site,
        sys.flags.optimize,
    )
require_isolated_interpreter()
import argparse
def validate_repository():
    return None
def read_stable_checker_source():
    return b"pass"
def load_checker_trust_root():
    raw = read_stable_checker_source()
    code = compile(raw, "checker.py", "exec")
    namespace = {}
    exec(code, namespace, namespace)
def main():
    require_isolated_interpreter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-permit")
    parser.add_argument("--execute-permit")
'''
        CHECKER.validate_runner_source(guarded)
        unguarded = guarded.replace(
            b"    require_isolated_interpreter()\n    parser",
            b"    parser",
        )
        with self.assertRaisesRegex(CHECKER.CheckError, "invoke require_isolated_interpreter first"):
            CHECKER.validate_runner_source(unguarded)

    def test_32_standalone_output_does_not_claim_consumption_state(self) -> None:
        source = checker_function_source("main")
        self.assertIn('"permitConsumptionState": "not_inspected"', source)
        self.assertNotIn('"permitConsumed": False', source)

    def test_33_runner_compile_exec_are_scoped_to_stable_checker_loader(self) -> None:
        runner = (ROOT / CHECKER.RUNNER_PATH).read_bytes()
        CHECKER.validate_runner_source(runner)
        injected = runner + b"\ndef forbidden_compile():\n    return compile(b'pass', 'x', 'exec')\n"
        with self.assertRaisesRegex(CHECKER.CheckError, "compile exactly once"):
            CHECKER.validate_runner_source(injected)
        importlib_injected = runner.replace(
            b"import argparse\n",
            b"import argparse\nimport importlib\n",
            1,
        )
        with self.assertRaisesRegex(CHECKER.CheckError, "forbidden imports"):
            CHECKER.validate_runner_source(importlib_injected)
        reordered = runner.replace(
            b"import sys\n\nsys.dont_write_bytecode = True",
            b"import sys\nimport argparse\n\nsys.dont_write_bytecode = True",
            1,
        )
        with self.assertRaisesRegex(CHECKER.CheckError, "set sys.dont_write_bytecode"):
            CHECKER.validate_runner_source(reordered)

    def test_34_compiler_semantics_are_scoped_and_ambiguous_keys_rejected(self) -> None:
        policy = self.read_json(CHECKER.POLICY_PATH)
        permit = self.read_json(CHECKER.PERMIT_PATH)
        core = self.read_json(CHECKER.CORE_MANIFEST_PATH)
        checker_manifest = self.read_json(CHECKER.CHECKER_MANIFEST_PATH)
        boundaries = (
            policy["capabilityBoundary"],
            permit["capabilityBoundary"],
            core["executionBoundary"],
            checker_manifest["trustBoundary"],
        )
        for boundary in boundaries:
            self.assertFalse(boundary["reviewedSourceCompilerInvocationAllowed"])
            self.assertTrue(boundary["verifiedPinnedReviewToolModuleLoadingAllowed"])
            self.assertTrue(
                boundary["verifiedAuxiliaryToolModulePythonCompileAllowed"]
            )
            self.assertNotIn("compilerInvocationAllowed", boundary)
        self.assertIn(
            "reviewed_source_compiler",
            policy["forbiddenCapabilities"],
        )
        self.assertNotIn("compiler", policy["forbiddenCapabilities"])
        self.assertFalse(
            permit["nonClaims"]["reviewedSourceCompileAuthorized"]
        )
        self.assertNotIn("compileAuthorized", permit["nonClaims"])

        ambiguous_policy = copy.deepcopy(policy)
        ambiguous_policy["capabilityBoundary"]["compilerInvocationAllowed"] = False
        with self.assertRaisesRegex(CHECKER.CheckError, "ambiguous compiler key"):
            CHECKER.validate_policy(ambiguous_policy)

        ambiguous_forbidden = copy.deepcopy(policy)
        ambiguous_forbidden["forbiddenCapabilities"].append("compiler")
        with self.assertRaisesRegex(
            CHECKER.CheckError,
            "ambiguous compiler capability",
        ):
            CHECKER.validate_policy(ambiguous_forbidden)

        ambiguous_permit = copy.deepcopy(permit)
        ambiguous_permit["nonClaims"]["compileAuthorized"] = False
        with self.assertRaisesRegex(CHECKER.CheckError, "ambiguous compiler key"):
            CHECKER.validate_permit(ambiguous_permit, b"", None)

        ambiguous_core = copy.deepcopy(core)
        ambiguous_core["executionBoundary"]["compilerInvocationAllowed"] = False
        with self.assertRaisesRegex(CHECKER.CheckError, "ambiguous compiler key"):
            CHECKER.validate_core_manifest(ambiguous_core, b"", None)

        ambiguous_checker = copy.deepcopy(checker_manifest)
        ambiguous_checker["trustBoundary"]["compilerInvocationAllowed"] = False
        with self.assertRaisesRegex(CHECKER.CheckError, "ambiguous compiler key"):
            CHECKER.validate_checker_manifest(ambiguous_checker, None)

    def test_35_checker_bootstrap_uses_isolated_in_memory_source_bytes(self) -> None:
        self.assertIs(type(CHECKER), ModuleType)
        self.assertEqual(CHECKER_CODE.co_filename, CHECKER_RELATIVE_PATH)
        self.assertIsNone(CHECKER.__loader__)
        self.assertIsNone(CHECKER.__cached__)
        self.assertEqual(sys.flags.isolated, 1)
        self.assertEqual(sys.flags.dont_write_bytecode, 1)
        self.assertEqual(sys.flags.optimize, 0)


if __name__ == "__main__":
    unittest.main()
