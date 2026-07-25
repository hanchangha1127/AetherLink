#!/usr/bin/env python3
"""Tests for the Wave4 acquisition permit checker."""

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
    raise RuntimeError("Wave4 acquisition tests require `python3 -I -B -S`")

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave4_acquisition_permit_v1",
    CHECKER_PATH,
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


class Wave4AcquisitionPermitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package, cls.summary = check.evaluate(True)
        cls.decision = cls.package["decision"]
        cls.permit = cls.package["permit"]
        cls.rows = check.normalized_resources(cls.decision)

    def test_materialized_package_is_exact_and_content_bound(self) -> None:
        raw = (check.ROOT / check.PERMIT_PATH).read_bytes()
        self.assertEqual(raw, check.canonical_bytes(self.permit))
        self.assertEqual(check.strict_json(raw), self.permit)
        without = dict(self.permit)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            check.sha256(check.canonical_bytes(without)),
        )
        actual = {
            path: check.sha256((check.ROOT / path).read_bytes())
            for path in (
                check.THIS_CHECKER_PATH,
                check.THIS_TESTS_PATH,
                check.RUNNER_PATH,
                check.RUNNER_TESTS_PATH,
            )
        }
        self.assertEqual(
            {
                row["path"]: row["rawSha256"]
                for row in self.permit["toolBindings"]
            },
            actual,
        )

    def test_exact_request_contract_and_no_authentication(self) -> None:
        self.assertEqual(len(self.rows), 32)
        self.assertEqual(
            [row["requestOrdinal"] for row in self.rows],
            list(range(1, 33)),
        )
        self.assertEqual(
            [row["kind"] for row in self.rows],
            ["mod", "zip"] * 16,
        )
        self.assertEqual(
            sum(row["selectedByGraphAlgorithm"] for row in self.rows[::2]),
            3,
        )
        self.assertFalse(
            self.permit["authority"]["externalAuthenticationRequired"]
        )
        self.assertFalse(
            self.permit["authority"]["repositoryOwnerIdentityProofRequired"]
        )
        self.assertFalse(self.permit["authority"]["passwordRequired"])
        self.assertFalse(self.permit["authority"]["privateKeyRequired"])
        self.assertFalse(self.permit["authority"]["signatureRequired"])
        self.assertFalse(self.permit["authority"]["tokenRequired"])
        self.assertFalse(self.permit["authority"]["userActionRequired"])
        self.assertFalse(
            self.permit["requestContract"]["authenticationAllowed"]
        )

    def test_resource_schema_mutations_fail_closed(self) -> None:
        for mutation in (
            lambda row: row.__setitem__("requestOrdinal", 2),
            lambda row: row.__setitem__("resourceKind", "zip"),
            lambda row: row.__setitem__("authenticationRequired", True),
            lambda row: row.__setitem__("networkAuthorized", True),
            lambda row: row.__setitem__("maximumResponseBytes", 3),
            lambda row: row.__setitem__("url", row["url"] + "?x=1"),
            lambda row: row.__setitem__("acceptedFileName", "wrong.mod"),
            lambda row: row.__setitem__(
                "selectedByGraphAlgorithm",
                "false",
            ),
            lambda row: row.__setitem__("selectedByGraphAlgorithm", 1),
            lambda row: row.__setitem__("module", "a//b"),
            lambda row: row.__setitem__("module", "a/../b"),
        ):
            source = copy.deepcopy(
                self.decision["sourceAcquisitionPreparation"]["requestSet"]
            )
            mutation(source[0])
            with self.assertRaises(check.CheckError):
                check._normalize_request_rows(source)

    def test_runner_reverse_pin_and_normalized_hash_fail_closed(self) -> None:
        runner_raw = (check.ROOT / check.RUNNER_PATH).read_bytes()
        checker_raw = (check.ROOT / check.THIS_CHECKER_PATH).read_bytes()
        check.validate_runner(runner_raw, checker_raw)
        reverse_mutation = runner_raw.replace(
            check.sha256(checker_raw).encode(),
            b"0" * 64,
            1,
        )
        with self.assertRaises(check.CheckError):
            check.validate_runner(reverse_mutation, checker_raw)
        body_mutation = runner_raw.replace(
            b"consumed_active",
            b"consumed_altered",
            1,
        )
        with self.assertRaises(check.CheckError):
            check.validate_runner(body_mutation, checker_raw)

    def test_strict_json_rejects_duplicates_and_noncanonical_is_separate(self) -> None:
        with self.assertRaises(check.CheckError):
            check.strict_json(b'{"a":1,"a":2}\n')
        value = {"b": 1, "a": 2}
        raw = check.canonical_bytes(value)
        self.assertEqual(check.strict_json(raw), value)
        self.assertNotEqual(raw, b'{"b":1,"a":2}\n')

    def test_runner_ast_has_no_ambient_network_or_subprocess_client(self) -> None:
        raw = (check.ROOT / check.RUNNER_PATH).read_bytes()
        source = raw.decode("utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        self.assertTrue(
            {"subprocess", "requests", "socket", "urllib.request"}
            .isdisjoint(imports)
        )
        self.assertNotIn("Authorization", source)
        self.assertNotIn("Proxy-Authorization", source)
        self.assertNotIn("Cookie", source)

    def test_terminal_namespace_rejects_broken_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / check.BASE
            base.mkdir(parents=True)
            os.symlink(
                "missing",
                base / Path(check.RECEIPT_PATH).name,
            )
            with self.assertRaises(check.CheckError):
                check.HeldTerminalNamespace(root)

    def test_content_binding_is_reproducible(self) -> None:
        payload = check.content_bound({"z": 1, "a": [2]})
        without = dict(payload)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            check.sha256(check.canonical_bytes(without)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
