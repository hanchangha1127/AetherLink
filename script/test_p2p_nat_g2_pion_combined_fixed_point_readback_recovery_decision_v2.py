#!/usr/bin/env python3
"""Regression tests for the combined fixed-point recovery decision v2."""

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
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / (
        "check_p2p_nat_g2_pion_combined_fixed_point_"
        "readback_recovery_decision_v2.py"
    )
)
SPEC = importlib.util.spec_from_file_location(
    "combined_fixed_point_readback_recovery_decision_v2_tests_target",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load recovery decision checker")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class CombinedFixedPointRecoveryDecisionV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision = json.loads(
            (CHECKER.ROOT / CHECKER.RECOVERY_DECISION_PATH).read_bytes()
        )

    def test_01_exact_repository_package_validates(self) -> None:
        expected, summary = CHECKER.evaluate(
            CHECKER.ROOT,
            verify_disk=True,
        )
        self.assertEqual(expected, self.decision)
        self.assertTrue(summary["validationPassed"])
        self.assertFalse(summary["executionAuthorized"])
        self.assertFalse(summary["readbackRecordingAuthorized"])
        self.assertEqual(summary["heldSourceInputCount"], 69)
        self.assertEqual(summary["newTupleCount"], 16)

    def test_02_original_and_recovery_package_pins_are_exact(self) -> None:
        for path, expected in CHECKER.EXPECTED_RAW.items():
            with self.subTest(path=path):
                self.assertEqual(
                    hashlib.sha256(
                        (CHECKER.ROOT / path).read_bytes()
                    ).hexdigest(),
                    expected,
                )
        package = self.decision["selectedRecoveryPackage"]
        for path_key, sha_key in (
            ("readerPath", "readerRawSha256"),
            ("checkerPath", "checkerRawSha256"),
            ("checkerTestsPath", "checkerTestsRawSha256"),
        ):
            self.assertEqual(
                hashlib.sha256(
                    (CHECKER.ROOT / package[path_key]).read_bytes()
                ).hexdigest(),
                package[sha_key],
            )

    def test_03_direct_pure_payload_paths_replace_clean_bug(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "def validate_original_decision_direct(",
            source,
        )
        self.assertIn(
            "def validate_original_permit_direct(",
            source,
        )
        self.assertIn(
            "self.decision = validate_original_decision_direct(self)",
            source,
        )
        self.assertIn(
            "self.permit = validate_original_permit_direct(self)",
            source,
        )
        for forbidden in (
            ".expected_decision(",
            ".evaluate(",
            ".check_repository(",
        ):
            self.assertNotIn(forbidden, source)
        decision_calls = []

        class DecisionChecker:
            def expected_payload(self, *args):
                decision_calls.append(("payload", args))
                return {"direct": "decision"}

            def content_bound(self, payload):
                decision_calls.append(("bound", payload))
                return {"bound": payload}

            def validate_decision_bytes(self, raw, expected):
                decision_calls.append(("validate", raw, expected))
                return {"validated": "decision"}

            def validate_reader_bytes(self, raw):
                decision_calls.append(("reader", raw))

        context = types.SimpleNamespace(
            decision_checker=DecisionChecker(),
            candidate=object(),
            runner=object(),
            documents=object(),
            source_rows=object(),
            static=types.SimpleNamespace(
                raw={
                    CHECKER.DECISION_PATH: b"decision",
                    CHECKER.DECISION_READER_PATH: b"reader",
                }
            ),
        )
        self.assertEqual(
            CHECKER.validate_original_decision_direct(context),
            {"validated": "decision"},
        )
        self.assertEqual(
            decision_calls[2],
            (
                "validate",
                b"decision",
                {"bound": {"direct": "decision"}},
            ),
        )
        permit_calls = []

        class PermitChecker:
            def expected_payload(self, actual_context):
                permit_calls.append(("payload", actual_context))
                return {"direct": "permit"}

            def content_bound(self, payload):
                permit_calls.append(("bound", payload))
                return {"bound": payload}

            def validate_permit_bytes(self, raw, expected):
                permit_calls.append(("validate", raw, expected))
                return {"validated": "permit"}

        context.permit_checker = PermitChecker()
        context.static.raw[CHECKER.PERMIT_PATH] = b"permit"
        self.assertEqual(
            CHECKER.validate_original_permit_direct(context),
            {"validated": "permit"},
        )
        self.assertEqual(
            permit_calls[2],
            (
                "validate",
                b"permit",
                {"bound": {"direct": "permit"}},
            ),
        )

    def test_04_source_and_terminal_semantic_tamper_is_detected(self) -> None:
        permit = json.loads(
            (CHECKER.ROOT / CHECKER.PERMIT_PATH).read_bytes()
        )
        rows = permit["sourceInputSet"]["bindings"]
        self.assertEqual(len(rows), 69)
        self.assertEqual(
            hashlib.sha256(CHECKER.canonical_bytes(rows)).hexdigest(),
            CHECKER.EXPECTED_HELD_BINDING_SET_SHA256,
        )
        projection = [
            {
                field: row[field]
                for field in CHECKER.TRUST.CANDIDATE_SOURCE_PROJECTION_FIELDS
            }
            for row in rows
        ]
        self.assertEqual(
            hashlib.sha256(
                CHECKER.canonical_bytes(projection)
            ).hexdigest(),
            CHECKER.EXPECTED_CANDIDATE_PROJECTION_SHA256,
        )
        source_context = types.SimpleNamespace(
            decision_checker=CHECKER.TRUST,
        )
        CHECKER.validate_source_rows(source_context, rows, rows)
        changed_rows = copy.deepcopy(rows)
        changed_rows[0]["rawSha256"] = "0" * 64
        with self.assertRaises(CHECKER.RecoveryError):
            CHECKER.validate_source_rows(
                source_context,
                changed_rows,
                changed_rows,
            )
        claim = json.loads(
            (CHECKER.ROOT / CHECKER.CLAIM_PATH).read_bytes()
        )
        result = json.loads(
            (CHECKER.ROOT / CHECKER.RESULT_PATH).read_bytes()
        )
        manifest = json.loads(
            (CHECKER.ROOT / CHECKER.MANIFEST_PATH).read_bytes()
        )
        CHECKER.validate_terminal_semantics(claim, result, manifest)
        self.assertEqual(
            hashlib.sha256(
                CHECKER.canonical_bytes(
                    CHECKER.result_semantic_projection(result)
                )
            ).hexdigest(),
            CHECKER.EXPECTED_RESULT_SEMANTIC_SHA256,
        )
        result["graphSha256"] = "0" * 64
        with self.assertRaises(CHECKER.RecoveryError):
            CHECKER.validate_terminal_semantics(claim, result, manifest)

    def test_04a_bad_original_source_and_terminal_pins_are_rejected(
        self,
    ) -> None:
        original = CHECKER.original_binding_rows()
        original[0] = {**original[0], "rawSha256": "0" * 64}
        with self.assertRaises(Exception):
            CHECKER.TRUST.HeldSet(CHECKER.ROOT, original)
        permit = json.loads(
            (CHECKER.ROOT / CHECKER.PERMIT_PATH).read_bytes()
        )
        first_source = permit["sourceInputSet"]["bindings"][0]
        with self.assertRaises(Exception):
            CHECKER.TRUST.HeldSet(
                CHECKER.ROOT,
                [
                    {
                        "path": first_source["path"],
                        "rawSha256": "0" * 64,
                        "maximumBytes": first_source["byteSize"],
                        "ownerOnly": True,
                    }
                ],
            )
        terminal = CHECKER.terminal_binding_rows()
        terminal[0] = {**terminal[0], "rawSha256": "0" * 64}
        with self.assertRaises(Exception):
            CHECKER.TRUST.HeldSet(CHECKER.ROOT, terminal)

    def namespace_root(self, root: Path) -> None:
        os.chmod(root, 0o700)
        (root / CHECKER.DEPENDENCY_ROOT).mkdir(parents=True)
        (root / CHECKER.BASE).mkdir(parents=True)

    def test_05_namespace_matrix_and_staging_fail_closed(self) -> None:
        forbidden = (
            CHECKER.FAILURE_PATH,
            *CHECKER.V1_READBACK_PATHS,
            *CHECKER.V2_RECOVERY_PATHS,
        )
        for relative in forbidden:
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    self.namespace_root(root)
                    namespace = CHECKER.TRUST.HeldNamespace(root)
                    try:
                        target = root / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(b"x")
                        with self.assertRaises(CHECKER.RecoveryError):
                            CHECKER.validate_namespace(root, namespace)
                    finally:
                        namespace.close()
        for prefix in CHECKER.STAGING_PREFIXES:
            with self.subTest(prefix=prefix):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    self.namespace_root(root)
                    namespace = CHECKER.TRUST.HeldNamespace(root)
                    try:
                        (root / CHECKER.DEPENDENCY_ROOT / f"{prefix}x").mkdir()
                        with self.assertRaises(CHECKER.RecoveryError):
                            CHECKER.validate_namespace(root, namespace)
                    finally:
                        namespace.close()

    def test_06_root_and_parent_swap_are_caught_by_fd_barrier(self) -> None:
        for target_name in ("root", "dependency", "base"):
            with self.subTest(target=target_name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    self.namespace_root(root)
                    namespace = CHECKER.TRUST.HeldNamespace(root)
                    moved_root = None
                    try:
                        if target_name == "root":
                            moved_root = root.with_name(root.name + "-old")
                            root.rename(moved_root)
                            root.mkdir()
                        elif target_name == "dependency":
                            target = root / CHECKER.DEPENDENCY_ROOT
                            target.rename(target.with_name("dependencies-old"))
                            target.mkdir()
                        else:
                            target = root / CHECKER.BASE
                            target.rename(target.with_name("rung-three-old"))
                            target.mkdir()
                        with self.assertRaises(Exception):
                            namespace.final_barrier()
                    finally:
                        namespace.close()
                        if moved_root is not None and moved_root.exists():
                            root.rmdir()
                            moved_root.rename(root)

    def test_06a_swap_and_restore_scans_original_held_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.namespace_root(root)
            namespace = CHECKER.TRUST.HeldNamespace(root)
            dependency = root / CHECKER.DEPENDENCY_ROOT
            moved = dependency.with_name("dependencies-held")
            forbidden = CHECKER.V2_RECOVERY_PATHS[0]
            try:
                dependency.rename(moved)
                dependency.mkdir()
                (moved / forbidden.rsplit("/", 1)[-1]).write_bytes(b"x")
                (moved / f"{CHECKER.STAGING_PREFIXES[1]}x").mkdir()
                self.assertFalse(
                    CHECKER.absent_from_held_namespace(
                        namespace,
                        forbidden,
                    )
                )
                self.assertIn(
                    f"{CHECKER.STAGING_PREFIXES[1]}x",
                    CHECKER.held_dependency_names(namespace),
                )
            finally:
                dependency.rmdir()
                moved.rename(dependency)
                namespace.final_barrier()
                namespace.close()

    def test_07_reader_and_terminal_identity_are_exact(self) -> None:
        self.assertEqual(
            (CHECKER.ROOT / CHECKER.RECOVERY_READER_PATH).read_bytes(),
            CHECKER.READER_BYTES,
        )
        terminal = self.decision["consumedSuccessTerminal"]
        for name in ("claim", "result", "manifest"):
            binding = terminal[name]
            info = (CHECKER.ROOT / binding["path"]).stat()
            self.assertEqual(stat_mode(info.st_mode), 0o600)
            self.assertEqual(info.st_nlink, 1)
            self.assertEqual(info.st_size, binding["byteSize"])

    def test_08_decision_schema_content_and_authority_tamper_fail(self) -> None:
        expected, _ = CHECKER.evaluate(
            CHECKER.ROOT,
            verify_disk=False,
        )
        mutations = []
        for key in ("status", "nextAction", "result"):
            value = copy.deepcopy(expected)
            value[key] = "drift"
            mutations.append(value)
        for key in (
            "executionAuthorized",
            "readbackRecordingAuthorized",
            "originalPermitRetryAllowed",
            "originalTerminalModifyAllowed",
            "externalAuthenticationRequired",
        ):
            value = copy.deepcopy(expected)
            value["preservationAndAuthority"][key] = True
            mutations.append(value)
        value = copy.deepcopy(expected)
        value["consumedSuccessTerminal"]["newTupleCount"] = 0
        mutations.append(value)
        for mutation in mutations:
            with self.subTest(mutation=mutation.get("status")):
                with self.assertRaises(CHECKER.RecoveryError):
                    CHECKER.validate_recovery_document(mutation, expected)

    def test_09_static_checker_has_no_publication_network_or_source_run(
        self,
    ) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        for token in (
            "urllib.",
            "socket.",
            "subprocess.",
            "os.system(",
            "write_text(",
            "write_bytes(",
            "os.write(",
            "os.mkdir(",
            "os.rename(",
            "generate_candidate(",
        ):
            self.assertNotIn(token, source)

    def run_checker(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(CHECKER_PATH),
                *arguments,
            ],
            cwd=CHECKER.ROOT,
            check=False,
            capture_output=True,
        )

    def test_10_print_expected_equals_exact_canonical_disk_bytes(self) -> None:
        completed = self.run_checker("--print-expected")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(
            completed.stdout,
            (CHECKER.ROOT / CHECKER.RECOVERY_DECISION_PATH).read_bytes(),
        )

    def test_11_default_cli_is_canonical_read_only(self) -> None:
        completed = self.run_checker()
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, b"")
        result = json.loads(completed.stdout)
        self.assertEqual(completed.stdout, CHECKER.canonical_bytes(result))
        self.assertTrue(result["validationPassed"])
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertFalse(result["executionAuthorized"])
        self.assertFalse(result["readbackRecordingAuthorized"])

    def test_12_invalid_cli_is_canonical_stdout_only(self) -> None:
        completed = self.run_checker("--forbidden-secret-value")
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stderr, b"")
        result = json.loads(completed.stdout)
        self.assertEqual(completed.stdout, CHECKER.canonical_bytes(result))
        self.assertEqual(result["failureCode"], "E_ARGUMENT")
        self.assertNotIn(b"forbidden-secret-value", completed.stdout)


def stat_mode(mode: int) -> int:
    return mode & 0o777


if __name__ == "__main__":
    unittest.main(verbosity=2)
