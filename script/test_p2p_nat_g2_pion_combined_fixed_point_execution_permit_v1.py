#!/usr/bin/env python3
"""Regressions for the combined fixed-point one-use permit checker."""

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


CHECKER_PATH = (
    Path(__file__).resolve().parent
    / "check_p2p_nat_g2_pion_combined_fixed_point_execution_permit_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "combined_fixed_point_permit_checker_v1",
    CHECKER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load permit checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class Capture:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


class CombinedFixedPointPermitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = checker.expected_permit(checker.ROOT)
        cls.permit_raw = (checker.ROOT / checker.PERMIT_PATH).read_bytes()

    def test_01_baseline_exact_permit(self) -> None:
        result = checker.validate_repository(checker.ROOT)
        self.assertTrue(result["executionAuthorized"])
        self.assertTrue(result["namespacePreflightChecked"])
        self.assertEqual(result["heldSourceInputCount"], 69)
        for key in (
            "networkUsed",
            "sourceExecutionUsed",
            "filesystemExtractionUsed",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ):
            self.assertFalse(result[key])

    def test_02_print_expected_equals_canonical_disk_bytes(self) -> None:
        capture = Capture()
        with mock.patch.object(sys, "stdout", capture):
            self.assertEqual(checker.main(["--print-expected"]), 0)
        self.assertEqual(capture.buffer.getvalue(), self.permit_raw)
        self.assertEqual(
            self.permit_raw,
            checker.canonical_bytes(self.expected),
        )

    def test_03_content_binding_and_schema_mutation_fail(self) -> None:
        actual = checker.validate_permit_bytes(
            self.permit_raw,
            self.expected,
        )
        without = dict(actual)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            checker.sha256(checker.canonical_bytes(without)),
        )
        mutated = copy.deepcopy(actual)
        mutated["status"] = "consumed"
        mutated.pop("contentBinding")
        rebound = checker.content_bound(mutated)
        with self.assertRaises(checker.PermitError) as caught:
            checker.validate_permit_bytes(
                checker.canonical_bytes(rebound),
                self.expected,
            )
        self.assertEqual(caught.exception.code, "E_PERMIT")

    def test_04_noncanonical_duplicate_and_nonfinite_fail(self) -> None:
        pretty = json.dumps(
            self.expected,
            indent=2,
            ensure_ascii=True,
        ).encode() + b"\n"
        with self.assertRaises(checker.PermitError) as caught:
            checker.validate_permit_bytes(pretty, self.expected)
        self.assertEqual(caught.exception.code, "E_CANONICAL_PERMIT")
        with self.assertRaises(checker.PermitError) as caught:
            checker.validate_permit_bytes(
                b'{"a":1,"a":2}\n',
                self.expected,
            )
        self.assertEqual(caught.exception.code, "E_JSON")
        with self.assertRaises(checker.PermitError) as caught:
            checker.validate_permit_bytes(
                b'{"a":NaN}\n',
                self.expected,
            )
        self.assertEqual(caught.exception.code, "E_JSON")

    def test_05_exact_source_profiles_and_limits_are_frozen(self) -> None:
        sources = self.expected["sourceInputSet"]
        self.assertEqual(sources["heldInputCount"], 69)
        self.assertEqual(len(sources["bindings"]), 69)
        self.assertEqual(
            sources["decisionHeldBindingSetSha256"],
            self.expected["decisionBinding"]
            and json.loads(
                (checker.ROOT / checker.DECISION_PATH).read_bytes()
            )["sourceInputSet"]["decisionHeldBindingSetSha256"],
        )
        self.assertEqual(
            sources["candidateSourceProjectionSha256"],
            "c744597d53e9bf50611f154421f661aec19f95a767dcbb9a80aa653fe83f2036",
        )
        self.assertEqual(len(self.expected["profiles"]), 2)
        self.assertEqual(
            self.expected["fixedPointAcceptance"][
                "exactFrontierCountRequired"
            ],
            0,
        )
        self.assertEqual(
            self.expected["currentExpectedRoute"]["newTupleCount"],
            16,
        )
        self.assertFalse(
            self.expected["currentExpectedRoute"]["fixedPointReached"]
        )

    def test_06_reverse_circular_pins_match_permit_checker(self) -> None:
        with checker.open_authority_context(
            checker.ROOT,
            include_permit=True,
            require_clean_namespace=True,
        ) as context:
            checker.validate_reverse_pins(context)
            expected_checker_sha = hashlib.sha256(
                (checker.ROOT / checker.THIS_CHECKER_PATH).read_bytes()
            ).hexdigest()
            for path in (
                checker.RUNNER_PATH,
                checker.READBACK_CHECKER_PATH,
            ):
                source = (checker.ROOT / path).read_text(encoding="utf-8")
                self.assertEqual(
                    checker.assigned_string(
                        source,
                        "EXPECTED_PERMIT_CHECKER_RAW_SHA256",
                    ),
                    expected_checker_sha,
                )
            checker.validate_tool_freeze(context)

    def test_06a_normalized_anchor_rejects_body_and_test_mutation(self) -> None:
        runner_raw = (checker.ROOT / checker.RUNNER_PATH).read_bytes()
        readback_raw = (
            checker.ROOT / checker.READBACK_CHECKER_PATH
        ).read_bytes()
        runner_digest = checker.normalized_executor_sha256(runner_raw)
        readback_digest = checker.normalized_executor_sha256(readback_raw)
        self.assertEqual(
            runner_digest,
            checker.EXPECTED_RUNNER_NORMALIZED_SHA256,
        )
        self.assertEqual(
            readback_digest,
            checker.EXPECTED_READBACK_NORMALIZED_SHA256,
        )
        runner_source = runner_raw.decode("utf-8")
        reverse_pin = checker.assigned_string(
            runner_source,
            checker.REVERSE_PIN_NAME,
        )
        self.assertIsNotNone(reverse_pin)
        changed_pin = runner_source.replace(
            f'"{reverse_pin}"',
            f'"{"f" * 64}"',
            1,
        ).encode()
        self.assertEqual(
            checker.normalized_executor_sha256(changed_pin),
            runner_digest,
        )
        changed_body = runner_raw.replace(
            b"Run the exact combined fixed-point gate",
            b"Run a changed combined fixed-point gate",
            1,
        )
        self.assertNotEqual(
            checker.normalized_executor_sha256(changed_body),
            runner_digest,
        )
        runner_tests = (
            checker.ROOT / checker.RUNNER_TESTS_PATH
        ).read_bytes()
        readback_tests = (
            checker.ROOT / checker.READBACK_TESTS_PATH
        ).read_bytes()
        self.assertEqual(
            checker.sha256(runner_tests),
            checker.EXPECTED_RUNNER_TESTS_RAW_SHA256,
        )
        self.assertEqual(
            checker.sha256(readback_tests),
            checker.EXPECTED_READBACK_TESTS_RAW_SHA256,
        )
        self.assertNotEqual(
            checker.sha256(runner_tests + b"# mutation\n"),
            checker.EXPECTED_RUNNER_TESTS_RAW_SHA256,
        )

    def test_06b_normalization_rejects_all_rebind_and_literal_variants(
        self,
    ) -> None:
        name = checker.REVERSE_PIN_NAME
        digest = "a" * 64
        valid = f'{name} = ("{digest}")\n'
        normalized = checker.normalized_executor_bytes(valid.encode())
        expected = valid.replace(digest, "0" * 64).encode()
        self.assertEqual(normalized, expected)
        self.assertEqual(
            checker.normalized_executor_bytes(normalized),
            normalized,
        )
        changed = [
            index
            for index, (before, after) in enumerate(
                zip(valid.encode(), normalized)
            )
            if before != after
        ]
        self.assertEqual(len(changed), 64)
        self.assertEqual(
            changed,
            list(range(changed[0], changed[0] + 64)),
        )
        invalid_sources = {
            "duplicate_nonconstant": (
                valid + f"{name} = object()\n"
            ),
            "nested_rebind": (
                valid + f"def nested():\n    {name} = \"{digest}\"\n"
            ),
            "augassign": valid + f"{name} += \"x\"\n",
            "annassign": valid + f"{name}: str = \"{digest}\"\n",
            "namedexpr": valid + f"({name} := \"{digest}\")\n",
            "for_target": valid + f"for {name} in ():\n    pass\n",
            "with_target": (
                valid + f"with open('x') as {name}:\n    pass\n"
            ),
            "import_binding": valid + f"import os as {name}\n",
            "f_string": f'{name} = f"{digest}"\n',
            "concatenated": (
                f'{name} = "{digest[:32]}" "{digest[32:]}"\n'
            ),
            "single_quote": f"{name} = '{digest}'\n",
            "raw_prefix": f'{name} = r"{digest}"\n',
            "uppercase": f'{name} = "{"A" * 64}"\n',
            "length_63": f'{name} = "{"a" * 63}"\n',
            "length_65": f'{name} = "{"a" * 65}"\n',
            "nonhex": f'{name} = "{"g" * 64}"\n',
        }
        for label, source in invalid_sources.items():
            with self.subTest(label=label):
                with self.assertRaises(checker.PermitError) as caught:
                    checker.normalized_executor_bytes(source.encode())
                self.assertEqual(caught.exception.code, "E_TOOL_FREEZE")

    def test_06c_assigned_string_rejects_nonconstant_or_nested_rebind(
        self,
    ) -> None:
        name = checker.REVERSE_PIN_NAME
        digest = "b" * 64
        valid = f'{name} = "{digest}"\n'
        self.assertEqual(checker.assigned_string(valid, name), digest)
        for suffix in (
            f"{name} = other\n",
            f"def nested():\n    {name} = \"{digest}\"\n",
            f"import os as {name}\n",
        ):
            with self.assertRaises(checker.PermitError) as caught:
                checker.assigned_string(valid + suffix, name)
            self.assertEqual(caught.exception.code, "E_REVERSE_PIN")

    def test_07_namespace_includes_readback_failure_and_is_clean(self) -> None:
        contract = self.expected["oneUseContract"]
        self.assertEqual(
            contract["readbackFailurePath"],
            checker.READBACK_FAILURE_PATH,
        )
        self.assertTrue(
            contract["readbackReceiptOrFailureMutuallyExclusive"]
        )
        self.assertFalse(
            contract["readbackFailureBackfillAfterReceiptAttemptAllowed"]
        )
        checker.validate_namespace_absent(checker.ROOT)
        self.assertEqual(
            len(checker.PUBLICATION_PATHS),
            len(set(checker.PUBLICATION_PATHS)),
        )

    def test_08_authority_is_bounded_and_authentication_free(self) -> None:
        authority = self.expected["authority"]
        self.assertTrue(authority["singleOfflineEvaluationAuthorized"])
        self.assertTrue(authority["independentReadbackAuthorized"])
        for key in (
            "networkAuthorized",
            "dnsAuthorized",
            "socketAuthorized",
            "filesystemExtractionAuthorized",
            "sourceExecutionAuthorized",
            "packageManagerAuthorized",
            "compilerAuthorized",
            "subprocessAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "gitWriteAuthorized",
            "repositoryOwnerIdentityProofRequired",
            "externalAuthenticationRequired",
            "signatureRequired",
            "privateKeyRequired",
            "tokenRequired",
            "passwordRequired",
            "userActionRequired",
        ):
            self.assertFalse(authority[key])
        self.assertTrue(
            all(value is False for value in self.expected["closure"].values())
        )

    def test_09_tool_hash_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            target = root / "tool.py"
            target.write_bytes(b"pass\n")
            os.chmod(target, 0o600)
            decision_checker = checker.load_decision_checker(checker.ROOT)
            binding = {
                "path": "tool.py",
                "rawSha256": "0" * 64,
                "maximumBytes": 16,
                "ownerOnly": True,
            }
            with self.assertRaises(Exception):
                decision_checker.HeldSet(root, [binding])

    def test_10_namespace_collision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency = root / checker.DEPENDENCY_ROOT
            dependency.mkdir(parents=True)
            collision = root / checker.CLAIM_PATH
            collision.write_bytes(b"x")
            with self.assertRaises(checker.PermitError) as caught:
                checker.validate_namespace_absent(root)
            self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_10a_retained_namespace_detects_staging_and_parent_swap(
        self,
    ) -> None:
        decision_checker = checker.load_decision_checker(checker.ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / checker.DEPENDENCY_ROOT).mkdir(parents=True)
            (root / checker.BASE).mkdir(parents=True)
            namespace = decision_checker.HeldNamespace(root)
            context = object.__new__(checker.AuthorityContext)
            context.namespace = namespace
            try:
                context.namespace_barrier()
                dependency = root / checker.DEPENDENCY_ROOT
                (dependency / f"{checker.STAGING_PREFIX}injected").mkdir()
                with self.assertRaises(checker.PermitError) as caught:
                    context.namespace_barrier()
                self.assertEqual(caught.exception.code, "E_NAMESPACE")
                (dependency / f"{checker.STAGING_PREFIX}injected").rmdir()
                moved = dependency.with_name("dependencies-held-old")
                dependency.rename(moved)
                dependency.mkdir()
                with self.assertRaises(Exception):
                    context.namespace_barrier()
            finally:
                namespace.close()

    def test_11_static_surface_is_read_only_and_offline(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "socket",
                    "subprocess",
                    "urllib",
                    "http",
                    "ftplib",
                    "requests",
                    "ssl",
                    "zipfile",
                }
            )
        )
        for forbidden in (
            "O_WRONLY",
            "O_RDWR",
            "O_CREAT",
            "O_EXCL",
            "O_TRUNC",
            "O_APPEND",
            ".write_bytes(",
            ".write_text(",
            "os.rename(",
            "os.replace(",
            "os.unlink(",
            "os.remove(",
            ".extract(",
            ".extractall(",
            "os.system(",
            "os.popen(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertEqual(source.count("exec("), 1)
        self.assertIn("--print-expected", source)
        self.assertNotIn("--output", source)
        self.assertNotIn("--record", source)

    def test_12_cli_errors_are_canonical_and_stderr_free(self) -> None:
        expected = checker.canonical_bytes(
            {
                "documentType": (
                    "aetherlink.g2-pion-combined-fixed-point-"
                    "permit-check-error"
                ),
                "schemaVersion": "1.0",
                "status": "failed_closed",
                "networkOperationCount": 0,
                "sourceExecutionCount": 0,
                "fileWriteCount": 0,
            }
        )
        for argv in (
            ["--output", "x"],
            ["--record"],
            ["--root", "/tmp"],
        ):
            with self.subTest(argv=argv):
                capture = Capture()
                stderr = io.StringIO()
                with (
                    mock.patch.object(sys, "stdout", capture),
                    mock.patch.object(sys, "stderr", stderr),
                ):
                    self.assertEqual(checker.main(argv), 1)
                self.assertEqual(capture.buffer.getvalue(), expected)
                self.assertEqual(stderr.getvalue(), "")
        capture = Capture()
        stderr = io.StringIO()
        with (
            mock.patch.object(sys, "stdout", capture),
            mock.patch.object(sys, "stderr", stderr),
            mock.patch.object(
                checker,
                "require_isolated_interpreter",
                side_effect=RuntimeError("nonisolated"),
            ),
        ):
            self.assertEqual(checker.main([]), 1)
        self.assertEqual(capture.buffer.getvalue(), expected)
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
