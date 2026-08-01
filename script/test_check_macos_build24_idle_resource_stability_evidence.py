#!/usr/bin/env python3
"""Regression tests for the Build 24 idle-resource static readback."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from script import (
    check_macos_build24_idle_resource_stability_evidence as checker,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / checker.RESULT_RELATIVE_PATH
MANIFEST_PATH = ROOT / checker.MANIFEST_RELATIVE_PATH
CHECKSUM_PATH = ROOT / checker.CHECKSUM_RELATIVE_PATH
LEDGER_PATH = ROOT / "release/version-ledger.tsv"
CHECKER_PATH = (
    ROOT / "script/check_macos_build24_idle_resource_stability_evidence.py"
)


def retained_document() -> dict[str, object]:
    value = checker.parse_canonical_json(
        RESULT_PATH.read_bytes(),
        "test result",
    )
    if type(value) is not dict:
        raise AssertionError("retained result is not an object")
    return value


def validate_mutation(document: dict[str, object]) -> None:
    checker.validate_result_bytes(
        checker.canonical_json_bytes(document),
        enforce_identity=False,
    )


def static_effect_findings(source: str) -> list[str]:
    tree = ast.parse(source)
    findings: list[str] = []
    forbidden_import_roots = {
        "asyncio",
        "ctypes",
        "dulwich",
        "fcntl",
        "ftplib",
        "git",
        "http",
        "importlib",
        "mmap",
        "multiprocessing",
        "requests",
        "resource",
        "runpy",
        "selectors",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "ssl",
        "subprocess",
        "tarfile",
        "telnetlib",
        "tempfile",
        "threading",
        "urllib",
        "zipfile",
    }
    forbidden_name_calls = {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "input",
        "open",
        "setattr",
    }
    forbidden_os_calls = {
        "_exit",
        "chmod",
        "chown",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "fchmod",
        "fchown",
        "fdopen",
        "fork",
        "forkpty",
        "ftruncate",
        "link",
        "lchown",
        "makedirs",
        "mkfifo",
        "mknod",
        "mkdir",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "pwrite",
        "pwritev",
        "remove",
        "removedirs",
        "rename",
        "renames",
        "replace",
        "rmdir",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "symlink",
        "system",
        "truncate",
        "unlink",
        "utime",
        "write",
        "writev",
    }
    forbidden_write_attributes = {
        "chmod",
        "chown",
        "dump",
        "link_to",
        "mkdir",
        "rename",
        "replace",
        "rmdir",
        "symlink_to",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
    forbidden_open_flags = {
        "O_APPEND",
        "O_CREAT",
        "O_EXCL",
        "O_RDWR",
        "O_TMPFILE",
        "O_TRUNC",
        "O_WRONLY",
    }
    allowed_getattr_flags = {
        "O_CLOEXEC",
        "O_DIRECTORY",
        "O_NOFOLLOW",
    }
    os_aliases = {"os"}
    os_imported_symbols: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    os_aliases.add(alias.asname or "os")
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".", 1)[0] == "os"
        ):
            for alias in node.names:
                if alias.name != "*":
                    os_imported_symbols[alias.asname or alias.name] = (
                        alias.name
                    )

    os_symbol_aliases = dict(os_imported_symbols)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            targets = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            if not targets:
                continue
            if (
                isinstance(node.value, ast.Name)
                and node.value.id in os_aliases
            ):
                for target in targets:
                    if target not in os_aliases:
                        os_aliases.add(target)
                        changed = True
            elif (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id in os_aliases
            ):
                canonical_name = node.value.attr
                for target in targets:
                    existing_name = os_symbol_aliases.get(target)
                    if existing_name is None:
                        os_symbol_aliases[target] = canonical_name
                        changed = True
                    elif (
                        existing_name != canonical_name
                        and existing_name != "__dynamic__"
                    ):
                        os_symbol_aliases[target] = "__dynamic__"
                        changed = True
            elif (
                isinstance(node.value, ast.Name)
                and node.value.id in os_symbol_aliases
            ):
                canonical_name = os_symbol_aliases[node.value.id]
                for target in targets:
                    existing_name = os_symbol_aliases.get(target)
                    if existing_name is None:
                        os_symbol_aliases[target] = canonical_name
                        changed = True
                    elif (
                        existing_name != canonical_name
                        and existing_name != "__dynamic__"
                    ):
                        os_symbol_aliases[target] = "__dynamic__"
                        changed = True

    def module_root(expression: ast.expr) -> str | None:
        current = expression
        while isinstance(current, ast.Attribute):
            current = current.value
        return current.id if isinstance(current, ast.Name) else None

    def is_os_module(expression: ast.expr) -> bool:
        return (
            isinstance(expression, ast.Name)
            and expression.id in os_aliases
        )

    def is_dynamic_os_subscript(expression: ast.expr) -> bool:
        if not isinstance(expression, ast.Subscript):
            return False
        namespace = expression.value
        if (
            isinstance(namespace, ast.Attribute)
            and is_os_module(namespace.value)
            and namespace.attr == "__dict__"
        ):
            return True
        return (
            isinstance(namespace, ast.Call)
            and isinstance(namespace.func, ast.Name)
            and namespace.func.id == "vars"
            and len(namespace.args) == 1
            and is_os_module(namespace.args[0])
        )

    def safe_flag_expression(expression: ast.expr) -> bool:
        if isinstance(expression, ast.BinOp) and isinstance(
            expression.op,
            ast.BitOr,
        ):
            return safe_flag_expression(
                expression.left
            ) and safe_flag_expression(expression.right)
        if (
            isinstance(expression, ast.Attribute)
            and is_os_module(expression.value)
            and expression.attr == "O_RDONLY"
        ):
            return True
        if (
            isinstance(expression, ast.Name)
            and os_symbol_aliases.get(expression.id) == "O_RDONLY"
        ):
            return True
        if (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "getattr"
            and len(expression.args) == 3
            and is_os_module(expression.args[0])
            and isinstance(expression.args[1], ast.Constant)
            and expression.args[1].value in allowed_getattr_flags
            and isinstance(expression.args[2], ast.Constant)
            and expression.args[2].value == 0
        ):
            return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in forbidden_import_roots or root == "script":
                    findings.append(f"forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in forbidden_import_roots or root == "script":
                findings.append(f"forbidden import {node.module}")
            if root == "os" and any(
                alias.name == "*" for alias in node.names
            ):
                findings.append("dynamic os star import")
        elif isinstance(node, ast.Attribute):
            if (
                is_os_module(node.value)
                and node.attr in forbidden_open_flags
            ):
                findings.append(
                    f"forbidden open flag {module_root(node)}.{node.attr}"
                )
            if (
                is_os_module(node.value)
                and node.attr
                in {"__dict__", "__getattr__", "__getattribute__"}
            ):
                findings.append("dynamic os effect lookup")
        elif isinstance(node, ast.Name):
            canonical_name = os_symbol_aliases.get(node.id)
            if canonical_name in forbidden_open_flags:
                findings.append(
                    f"forbidden imported os flag {canonical_name}"
                )
        elif isinstance(node, ast.Subscript):
            if is_dynamic_os_subscript(node):
                findings.append("dynamic os effect lookup")
        elif isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "flags"
                for target in node.targets
            ) and not safe_flag_expression(node.value):
                findings.append("unsafe os.open flag expression")
        elif isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and is_os_module(node.args[0])
                and not (
                    len(node.args) == 3
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value in allowed_getattr_flags
                    and isinstance(node.args[2], ast.Constant)
                    and node.args[2].value == 0
                )
            ):
                findings.append("dynamic os effect lookup")
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "vars"
                and len(node.args) == 1
                and is_os_module(node.args[0])
            ):
                findings.append("dynamic os effect lookup")
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in forbidden_name_calls
            ):
                findings.append(f"forbidden call {node.func.id}")
            elif isinstance(node.func, ast.Name):
                canonical_name = os_symbol_aliases.get(node.func.id)
                if canonical_name in forbidden_os_calls:
                    findings.append(
                        f"forbidden imported os call {canonical_name}"
                    )
                elif canonical_name == "__dynamic__":
                    findings.append("dynamic os effect alias")
                elif canonical_name == "open":
                    findings.append(
                        "imported os.open bypasses audited flags"
                    )
            elif isinstance(node.func, ast.Attribute):
                root = module_root(node.func)
                if (
                    root in os_aliases
                    and node.func.attr in forbidden_os_calls
                ):
                    findings.append(f"forbidden os call {node.func.attr}")
                if node.func.attr in forbidden_write_attributes:
                    findings.append(
                        f"forbidden write call {node.func.attr}"
                    )
                if (
                    root in os_aliases
                    and node.func.attr == "open"
                    and (
                        len(node.args) < 2
                        or not isinstance(node.args[1], ast.Name)
                        or node.args[1].id != "flags"
                    )
                ):
                    findings.append("os.open must use audited flags")
    return findings


class Build24IdleResourceEvidenceCheckerTests(unittest.TestCase):
    def test_01_retained_result_and_full_readback_pass(self) -> None:
        document = checker.validate_result_bytes(RESULT_PATH.read_bytes())
        self.assertEqual(document["status"], "passed")
        report = checker.readback()
        self.assertEqual(report["targetCount"], 16)
        self.assertEqual(report["sampleCount"], 120)
        self.assertEqual(
            report["maximumObservedLatenessMilliseconds"],
            79,
        )

    def test_02_result_identity_and_canonical_encoding_are_fixed(
        self,
    ) -> None:
        payload = RESULT_PATH.read_bytes()
        expected = checker.TARGET_IDENTITIES[checker.RESULT_RELATIVE_PATH]
        self.assertEqual(len(payload), expected.size)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), expected.sha256)
        with self.assertRaises(checker.IdleResourceEvidenceError):
            checker.validate_result_bytes(payload + b" ")
        with self.assertRaises(checker.IdleResourceEvidenceError):
            checker.parse_canonical_json(
                b'{ "status": "passed" }\n',
                "spaced JSON",
            )

    def test_03_json_parser_rejects_duplicates_float_nonfinite_and_utf8(
        self,
    ) -> None:
        invalid_payloads = (
            b'{"a":1,"a":2}\n',
            b'{"a":1.0}\n',
            b'{"a":NaN}\n',
            b'{"a":Infinity}\n',
            b"\xff\n",
            b'{"b":1,"a":2}\n',
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    checker.parse_canonical_json(payload, "mutation")

    def test_04_exact_json_equality_rejects_boolean_integer_aliases(
        self,
    ) -> None:
        self.assertFalse(checker.exact_json_value_equal(False, 0))
        self.assertFalse(checker.exact_json_value_equal(True, 1))
        self.assertFalse(
            checker.exact_json_value_equal(
                {"metric": [{"value": 0}]},
                {"metric": [{"value": False}]},
            )
        )
        self.assertTrue(
            checker.exact_json_value_equal(
                {"metric": [{"value": 0}]},
                {"metric": [{"value": 0}]},
            )
        )

    def test_05_top_level_schema_scope_status_and_limitations_are_closed(
        self,
    ) -> None:
        document = retained_document()
        mutations: list[dict[str, object]] = []
        missing = copy.deepcopy(document)
        missing.pop("cleanup")
        mutations.append(missing)
        extra = copy.deepcopy(document)
        extra["unexpected"] = True
        mutations.append(extra)
        for field, value in (
            ("schemaVersion", True),
            ("scope", "different"),
            ("status", "failed"),
        ):
            mutation = copy.deepcopy(document)
            mutation[field] = value
            mutations.append(mutation)
        reordered = copy.deepcopy(document)
        reordered["limitations"] = list(reversed(reordered["limitations"]))
        mutations.append(reordered)
        for mutation in mutations:
            with self.subTest(keys=tuple(mutation)):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

    def test_06_archive_artifact_and_release_bindings_are_exact(
        self,
    ) -> None:
        document = retained_document()
        mutations = (
            ("archiveReadback", "currentSourceCompared", True),
            ("archiveReadback", "signatureVerificationPerformed", True),
            ("archiveReadback", "mode", "different"),
            ("artifact", "buildNumber", True),
            ("artifact", "executableMode", False),
            ("artifact", "executableSize", 18_592_369),
            ("artifact", "uuid", "different"),
            ("release", "releaseId", "different"),
            ("release", "archiveSha256", "0" * 64),
        )
        for section, field, value in mutations:
            mutation = copy.deepcopy(document)
            mutation[section][field] = value
            with self.subTest(section=section, field=field):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

        tree_mutation = copy.deepcopy(document)
        tree_mutation["artifact"]["appTree"]["regularFileCount"] = True
        with self.assertRaises(checker.IdleResourceEvidenceError):
            validate_mutation(tree_mutation)

        snapshot_mutation = copy.deepcopy(document)
        snapshot_mutation["archiveReadback"]["snapshotFiles"][
            checker.ARCHIVE_NAME
        ]["size"] = True
        with self.assertRaises(checker.IdleResourceEvidenceError):
            validate_mutation(snapshot_mutation)

    def test_07_cleanup_isolation_and_completion_flags_are_exact(
        self,
    ) -> None:
        document = retained_document()
        mutations = (
            ("cleanup", "ownedChildOnly", False),
            ("cleanup", "preexistingApplicationsPreserved", False),
            ("cleanup", "temporaryRootRemovedBeforePublication", False),
            ("isolation", "networkDenied", False),
            ("isolation", "sandboxed", 1),
            ("process", "rawProcessIdentifierRetained", True),
            (
                "process",
                "preexistingApplicationsUsedAsTerminationTargets",
                True,
            ),
            ("repeatability", "performed", True),
        )
        for section, field, value in mutations:
            mutation = copy.deepcopy(document)
            mutation[section][field] = value
            with self.subTest(section=section, field=field):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

        run_fields = {
            "activationPolicy": False,
            "appKitProcessAbsentAfterReap": False,
            "exitCode": False,
            "finishedLaunching": False,
            "gracefulTerminationAccepted": False,
            "ownedChildProcess": False,
            "processIdentifierRetained": True,
            "processReaped": False,
        }
        for field, value in run_fields.items():
            mutation = copy.deepcopy(document)
            mutation["measurement"]["run"][field] = value
            with self.subTest(run_field=field):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

    def test_08_measurement_policy_fields_are_exact_integers(
        self,
    ) -> None:
        document = retained_document()
        for field, value in (
            ("warmupMilliseconds", 59_999),
            ("observationMilliseconds", 599_999),
            ("intervalMilliseconds", True),
            ("sampleCount", 119),
            ("baselineWindowSampleCount", 11),
            ("finalWindowSampleCount", 13),
            ("sampleLatenessLimitMilliseconds", 1_001),
            ("status", "failed"),
            ("api", "different"),
        ):
            mutation = copy.deepcopy(document)
            mutation["measurement"][field] = value
            with self.subTest(field=field):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

    def test_09_sample_count_and_closed_schema_are_enforced(
        self,
    ) -> None:
        document = retained_document()
        missing = copy.deepcopy(document)
        missing["measurement"]["run"]["samples"].pop()
        extra = copy.deepcopy(document)
        extra["measurement"]["run"]["samples"].append(
            copy.deepcopy(extra["measurement"]["run"]["samples"][-1])
        )
        missing_key = copy.deepcopy(document)
        missing_key["measurement"]["run"]["samples"][0].pop("threadCount")
        extra_key = copy.deepcopy(document)
        extra_key["measurement"]["run"]["samples"][0]["pid"] = 59809
        for mutation in (missing, extra, missing_key, extra_key):
            with self.assertRaises(checker.IdleResourceEvidenceError):
                validate_mutation(mutation)

    def test_10_sample_schedule_lateness_and_resource_types_are_exact(
        self,
    ) -> None:
        document = retained_document()
        mutations = (
            ("ordinal", True),
            ("ordinal", 2),
            ("targetElapsedMilliseconds", 4_999),
            ("observedLatenessMilliseconds", -1),
            ("observedLatenessMilliseconds", 1_001),
            ("openFileDescriptorCount", 0),
            ("openFileDescriptorCount", True),
            ("residentBytes", 0),
            ("threadCount", False),
        )
        for field, value in mutations:
            mutation = copy.deepcopy(document)
            mutation["measurement"]["run"]["samples"][0][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

    def test_11_maximum_lateness_is_recomputed_from_raw_samples(
        self,
    ) -> None:
        document = retained_document()
        mutation = copy.deepcopy(document)
        mutation["measurement"]["run"][
            "maximumObservedLatenessMilliseconds"
        ] = 78
        with self.assertRaises(checker.IdleResourceEvidenceError):
            validate_mutation(mutation)

        mutation = copy.deepcopy(document)
        samples = mutation["measurement"]["run"]["samples"]
        samples[0]["observedLatenessMilliseconds"] = 80
        with self.assertRaises(checker.IdleResourceEvidenceError):
            validate_mutation(mutation)

    def test_12_all_metric_summaries_are_recomputed_with_exact_types(
        self,
    ) -> None:
        document = retained_document()
        mutations = (
            ("threads", "finalDelta", False),
            ("threads", "peakDelta", False),
            ("threads", "passed", 1),
            ("openFileDescriptors", "maximum", 11),
            ("residentBytes", "peakDelta", 49_153),
            ("threads", "finalDeltaLimit", 3),
            ("threads", "peakDeltaLimit", 9),
        )
        for metric, field, value in mutations:
            mutation = copy.deepcopy(document)
            mutation["measurement"]["run"]["summary"][metric][field] = value
            with self.subTest(metric=metric, field=field):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

    def test_13_metric_budget_boundaries_and_plus_one_are_distinct(
        self,
    ) -> None:
        for metric, (_, final_limit, peak_limit) in (
            checker.METRIC_CONTRACTS.items()
        ):
            values = [100] * checker.SAMPLE_COUNT
            values[-checker.FINAL_WINDOW_SAMPLE_COUNT :] = [
                100 + final_limit
            ] * checker.FINAL_WINDOW_SAMPLE_COUNT
            values[checker.BASELINE_WINDOW_SAMPLE_COUNT] = 100 + peak_limit
            boundary = checker.recompute_metric(
                values,
                final_delta_limit=final_limit,
                peak_delta_limit=peak_limit,
            )
            with self.subTest(metric=metric, boundary="exact"):
                self.assertIs(boundary["passed"], True)

            final_overrun = list(values)
            final_overrun[-checker.FINAL_WINDOW_SAMPLE_COUNT :] = [
                101 + final_limit
            ] * checker.FINAL_WINDOW_SAMPLE_COUNT
            with self.subTest(metric=metric, boundary="final+1"):
                self.assertIs(
                    checker.recompute_metric(
                        final_overrun,
                        final_delta_limit=final_limit,
                        peak_delta_limit=peak_limit,
                    )["passed"],
                    False,
                )

            peak_overrun = [100] * checker.SAMPLE_COUNT
            peak_overrun[checker.BASELINE_WINDOW_SAMPLE_COUNT] = (
                101 + peak_limit
            )
            with self.subTest(metric=metric, boundary="peak+1"):
                self.assertIs(
                    checker.recompute_metric(
                        peak_overrun,
                        final_delta_limit=final_limit,
                        peak_delta_limit=peak_limit,
                    )["passed"],
                    False,
                )

    def test_14_upper_median_uses_the_upper_even_window_value(
        self,
    ) -> None:
        self.assertEqual(checker.upper_median([9, 1, 7, 3]), 7)
        self.assertEqual(checker.upper_median([3]), 3)
        with self.assertRaises(checker.IdleResourceEvidenceError):
            checker.upper_median([])
        with self.assertRaises(checker.IdleResourceEvidenceError):
            checker.upper_median([1, True])

    def test_15_environment_and_process_counts_reject_bool_as_int(
        self,
    ) -> None:
        document = retained_document()
        for section, field, value in (
            ("environment", "architecture", ""),
            ("environment", "macOSVersion", 26),
            ("environment", "logicalCpuCount", True),
            ("environment", "pageSizeBytes", 0),
            ("process", "preexistingApplicationCount", False),
            ("process", "preexistingApplicationCount", -1),
        ):
            mutation = copy.deepcopy(document)
            mutation[section][field] = value
            with self.subTest(section=section, field=field):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    validate_mutation(mutation)

    def test_16_release_sidecars_and_terminal_ledger_semantics_match(
        self,
    ) -> None:
        payloads = {
            checker.MANIFEST_RELATIVE_PATH: MANIFEST_PATH.read_bytes(),
            checker.CHECKSUM_RELATIVE_PATH: CHECKSUM_PATH.read_bytes(),
            "release/version-ledger.tsv": LEDGER_PATH.read_bytes(),
        }
        checker.validate_release_payloads(payloads)
        for path in tuple(payloads):
            mutation = dict(payloads)
            mutation[path] = mutation[path] + b" "
            with self.subTest(path=path):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    checker.validate_release_payloads(mutation)

        manifest = json.loads(MANIFEST_PATH.read_bytes())
        manifest["release"]["buildNumber"] = True
        mutation = dict(payloads)
        mutation[checker.MANIFEST_RELATIVE_PATH] = (
            checker.canonical_json_bytes(manifest, ensure_ascii=True)
        )
        with self.assertRaises(checker.IdleResourceEvidenceError):
            checker.validate_release_payloads(mutation)

    def test_17_fixed_target_inventory_binds_runner_test_and_transitives(
        self,
    ) -> None:
        expected_sources = {
            "release/version-ledger.tsv",
            "script/check_release_version_ledger.py",
            "script/run_macos_packaged_app_lifecycle_smoke.py",
            "script/run_macos_packaged_app_state_recovery_smoke.py",
            "script/run_macos_clean_home_installed_app_smoke.py",
            "script/run_macos_clean_home_installed_state_recovery_smoke.py",
            "script/run_macos_isolated_uninstall_reinstall_smoke.py",
            "script/run_macos_isolated_upgrade_smoke.py",
            "script/run_macos_local_dmg_install_smoke.py",
            checker.HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH,
            (
                "script/"
                "run_macos_build24_idle_resource_stability_smoke.py"
            ),
            (
                "script/"
                "test_run_macos_build24_idle_resource_stability_smoke.py"
            ),
        }
        self.assertTrue(expected_sources.issubset(checker.TARGET_IDENTITIES))
        self.assertEqual(len(checker.TARGET_IDENTITIES), 16)
        self.assertEqual(
            checker.HISTORICAL_SOURCE_SNAPSHOT_COMMIT,
            "38027523f65f97a81044555c2f42b020eada3436",
        )
        self.assertEqual(
            checker.HISTORICAL_SOURCE_SNAPSHOT_ROOT,
            "docs/evidence/macos-build24-lifecycle-source-v1",
        )
        self.assertNotIn(
            "script/run_macos_local_dmg_install_smoke_v2.py",
            checker.TARGET_IDENTITIES,
        )
        checker.validate_historical_source_snapshot_contract()
        for relative, expected in checker.TARGET_IDENTITIES.items():
            path = ROOT / relative
            with self.subTest(relative=relative):
                self.assertFalse(path.is_symlink())
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, expected.size)
        fixture = ROOT / checker.HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH
        self.assertEqual(fixture.stat().st_mode & 0o111, 0)
        self.assertEqual(
            hashlib.sha256(fixture.read_bytes()).hexdigest(),
            checker.TARGET_IDENTITIES[
                checker.HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH
            ].sha256,
        )

    def test_18_historical_snapshot_contract_fails_closed(self) -> None:
        with mock.patch.object(
            checker,
            "HISTORICAL_SOURCE_SNAPSHOT_COMMIT",
            "0" * 40,
        ):
            with self.assertRaises(checker.IdleResourceEvidenceError):
                checker.validate_historical_source_snapshot_contract()
        with mock.patch.object(
            checker,
            "HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH",
            "script/run_macos_local_dmg_install_smoke_v2.py",
        ):
            with self.assertRaises(checker.IdleResourceEvidenceError):
                checker.validate_historical_source_snapshot_contract()
        mutated_targets = dict(checker.TARGET_IDENTITIES)
        mutated_targets["unexpected"] = checker.identity(
            0,
            hashlib.sha256(b"").hexdigest(),
        )
        with mock.patch.object(checker, "TARGET_IDENTITIES", mutated_targets):
            with self.assertRaises(checker.IdleResourceEvidenceError):
                checker.validate_historical_source_snapshot_contract()

    def test_18_historical_fixture_rejects_mutation_symlink_and_extra(
        self,
    ) -> None:
        expected = checker.TARGET_IDENTITIES[
            checker.HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH
        ]
        payload = (
            ROOT / checker.HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH
        ).read_bytes()

        def materialize(root: Path) -> Path:
            relative_directory = (
                f"{checker.HISTORICAL_SOURCE_SNAPSHOT_ROOT}/script"
            )
            fixture_directory = root / relative_directory
            fixture_directory.mkdir(parents=True)
            for name in checker.HISTORICAL_SOURCE_DIRECTORY_INVENTORIES[
                relative_directory
            ]:
                source = ROOT / relative_directory / name
                (fixture_directory / name).write_bytes(source.read_bytes())
            return root / checker.HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH

        def validate(root: Path) -> None:
            snapshot = checker.RepositorySnapshot(
                root,
                {checker.HISTORICAL_LOCAL_DMG_V2_SOURCE_PATH: expected},
            )
            try:
                snapshot.open_all()
                checker.validate_historical_source_snapshot_contract(snapshot)
                snapshot.read_all()
                snapshot.verify_graph()
            finally:
                snapshot.close()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = materialize(root)
            live = root / "script/run_macos_local_dmg_install_smoke_v2.py"
            live.parent.mkdir()
            live.write_bytes(b"current live runner bytes\n")
            validate(root)
            fixture.write_bytes(payload + b"mutation")
            with self.assertRaises(checker.IdleResourceEvidenceError):
                validate(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = materialize(root)
            live = root / "live.py"
            live.write_bytes(payload)
            fixture.unlink()
            fixture.symlink_to(live)
            with self.assertRaises((checker.IdleResourceEvidenceError, OSError)):
                validate(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = materialize(root)
            (fixture.parent / "unexpected.py").write_bytes(b"pass\n")
            with self.assertRaises(checker.IdleResourceEvidenceError):
                validate(root)

    def test_18_identity_constructor_and_path_normalization_fail_closed(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            checker.identity(True, "0" * 64)
        with self.assertRaises(ValueError):
            checker.identity(1, "G" * 64)
        for value in ("", "/absolute", "../escape", "a/../b", "./a"):
            with self.subTest(value=value):
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    checker.normalized_relative_parts(value)
        self.assertEqual(
            checker.normalized_relative_parts("a/b"),
            ("a", "b"),
        )

    def test_19_small_repository_snapshot_holds_and_rechecks_graph(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "nested/evidence.bin"
            target.parent.mkdir()
            payload = b"bounded-evidence"
            target.write_bytes(payload)
            contracts = {
                "nested/evidence.bin": checker.identity(
                    len(payload),
                    hashlib.sha256(payload).hexdigest(),
                )
            }
            snapshot = checker.RepositorySnapshot(root, contracts)
            try:
                snapshot.open_all()
                self.assertEqual(
                    snapshot.read_all(),
                    {"nested/evidence.bin": payload},
                )
                snapshot.verify_graph()
            finally:
                snapshot.close()

    def test_20_snapshot_rejects_symlink_directory_and_wrong_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular"
            regular.write_bytes(b"x")
            symlink = root / "symlink"
            symlink.symlink_to(regular)
            folder = root / "folder"
            folder.mkdir()
            cases = (
                (
                    "symlink",
                    checker.identity(
                        1,
                        hashlib.sha256(b"x").hexdigest(),
                    ),
                ),
                (
                    "folder",
                    checker.identity(
                        0,
                        hashlib.sha256(b"").hexdigest(),
                    ),
                ),
                (
                    "regular",
                    checker.identity(
                        2,
                        hashlib.sha256(b"xx").hexdigest(),
                    ),
                ),
            )
            for relative, contract in cases:
                snapshot = checker.RepositorySnapshot(
                    root,
                    {relative: contract},
                )
                with self.subTest(relative=relative):
                    rejected = False
                    try:
                        snapshot.open_all()
                        snapshot.read_all()
                    except (
                        checker.IdleResourceEvidenceError,
                        OSError,
                    ):
                        rejected = True
                    finally:
                        snapshot.close()
                    self.assertTrue(rejected)

    def test_21_snapshot_detects_file_entry_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "evidence"
            payload = b"fixed"
            target.write_bytes(payload)
            snapshot = checker.RepositorySnapshot(
                root,
                {
                    "evidence": checker.identity(
                        len(payload),
                        hashlib.sha256(payload).hexdigest(),
                    )
                },
            )
            retained = root / "retained"
            try:
                snapshot.open_all()
                self.assertEqual(
                    snapshot.read_all(),
                    {"evidence": payload},
                )
                target.replace(retained)
                target.write_bytes(payload)
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    snapshot.verify_graph()
            finally:
                snapshot.close()

    def test_22_snapshot_detects_parent_directory_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            payload = b"fixed"
            (nested / "evidence").write_bytes(payload)
            snapshot = checker.RepositorySnapshot(
                root,
                {
                    "nested/evidence": checker.identity(
                        len(payload),
                        hashlib.sha256(payload).hexdigest(),
                    )
                },
            )
            retained = root / "retained"
            try:
                snapshot.open_all()
                snapshot.read_all()
                nested.replace(retained)
                nested.mkdir()
                (nested / "evidence").write_bytes(payload)
                with self.assertRaises(checker.IdleResourceEvidenceError):
                    snapshot.verify_graph()
            finally:
                snapshot.close()

    def test_23_checker_ast_has_no_runner_import_execution_or_write_api(
        self,
    ) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertEqual(static_effect_findings(source), [])
        for token in (
            "runpy.run_path",
            "importlib.import_module",
            "os.O_CREAT",
            "os.O_WRONLY",
            "os.O_RDWR",
            "os.O_TRUNC",
            "os.O_APPEND",
            "subprocess",
        ):
            self.assertNotIn(token, source)

        mutations = (
            "import os\nos.execv('/bin/true', ['true'])\n",
            (
                "import os as system_os\n"
                "system_os.execv('/bin/true', ['true'])\n"
            ),
            "from os import execv\nexecv('/bin/true', ['true'])\n",
            "from os import write\nwrite(1, b'x')\n",
            (
                "import os\nfirst = os.execv\nsecond = first\n"
                "second('/bin/true', ['true'])\n"
            ),
            "import os\nos.__dict__['system']('true')\n",
            "import os\nos.fork()\n",
            "import os\nos.posix_spawn('/bin/true', ['true'], {})\n",
            "import os\nos.write(1, b'x')\n",
            "import os\nos.open('x', os.O_WRONLY)\n",
            "import http.client\n",
            "import ftplib\n",
            "import ctypes\n",
            "import git\n",
            "import socket\n",
            "from pathlib import Path\nPath('x').write_text('x')\n",
            "__import__('subprocess')\n",
            "import os\ngetattr(os, 'system')('true')\n",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(static_effect_findings(mutation))

    def test_24_retained_result_contains_no_raw_pid_or_temporary_path(
        self,
    ) -> None:
        document = retained_document()
        serialized = checker.canonical_json_bytes(document).decode("utf-8")
        self.assertNotIn('"pid"', serialized)
        self.assertNotIn("/private/var/", serialized)
        self.assertNotIn(
            "aetherlink-macos-build24-idle-resource-v1-",
            serialized,
        )
        self.assertIs(
            document["process"]["rawProcessIdentifierRetained"],
            False,
        )

    def test_25_main_has_bounded_success_failure_and_argument_status(
        self,
    ) -> None:
        report = {
            "maximumObservedLatenessMilliseconds": 79,
            "resultSha256": (
                checker.TARGET_IDENTITIES[
                    checker.RESULT_RELATIVE_PATH
                ].sha256
            ),
            "sampleCount": 120,
            "targetCount": 16,
        }
        output = io.StringIO()
        with (
            redirect_stdout(output),
            redirect_stderr(output),
            mock.patch.object(checker, "readback", return_value=report),
        ):
            self.assertEqual(checker.main([]), 0)
        with (
            redirect_stdout(output),
            redirect_stderr(output),
            mock.patch.object(
                checker,
                "readback",
                side_effect=checker.IdleResourceEvidenceError("mutation"),
            ),
        ):
            self.assertEqual(checker.main([]), 1)
        with (
            redirect_stdout(output),
            redirect_stderr(output),
            mock.patch.object(checker, "readback") as readback,
        ):
            self.assertEqual(checker.main(["unexpected"]), 2)
            readback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
