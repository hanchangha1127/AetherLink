#!/usr/bin/env python3
"""Focused adversarial tests for the read-only Wave7 decision checker."""

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
    raise RuntimeError("Wave7 decision tests require `python3 -I -B -S`")

import ast
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave7_decision_v1.py"
)
DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave7-v1.json"
)
READER_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave7-v1.md"
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
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


def independent_request_oracle() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for tuple_order, identity in enumerate(
        CHECKER.EXPECTED_IDENTITY,
        1,
    ):
        module, version, mod_h1, zip_h1 = identity[:4]
        tuple_digest = hashlib.sha256(
            f"{module}\n{version}\n".encode("utf-8")
        ).hexdigest()
        for kind, expected_h1, maximum in (
            ("mod", mod_h1, 1_048_576),
            ("zip", zip_h1, 16_777_216),
        ):
            result.append(
                {
                    "requestOrdinal": len(result) + 1,
                    "tupleOrder": tuple_order,
                    "module": module,
                    "version": version,
                    "selectedByGraphAlgorithm": False,
                    "resourceKind": kind,
                    "method": "GET",
                    "host": "proxy.golang.org",
                    "url": (
                        f"https://proxy.golang.org/{module}/"
                        f"@v/{version}.{kind}"
                    ),
                    "expectedH1": expected_h1,
                    "maximumResponseBytes": maximum,
                    "acceptedFileName": (
                        f"{tuple_order:03d}-"
                        f"{tuple_digest[:20]}.{kind}"
                    ),
                    "authenticationRequired": False,
                    "networkAuthorized": False,
                    "acquisitionAuthorized": False,
                }
            )
    return result


def load_checker() -> types.ModuleType:
    path = ROOT / CHECKER_PATH
    raw = path.read_bytes()
    module = types.ModuleType("wave7_decision_checker_test_subject")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(path),
            "__loader__": None,
            "__name__": "wave7_decision_checker_test_subject",
            "__package__": None,
        }
    )
    exec(
        compile(
            raw,
            CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        ),
        module.__dict__,
        module.__dict__,
    )
    return module


CHECKER = load_checker()
VALID_H1_A = "h1:" + base64.b64encode(bytes(32)).decode("ascii")
VALID_H1_B = (
    "h1:" + base64.b64encode(bytes([1]) * 32).decode("ascii")
)


class FakeRunner:
    @staticmethod
    def parse_go_mod(
        raw: bytes,
        expected_module: str,
    ) -> dict[str, object]:
        if f"module {expected_module}" not in raw.decode("utf-8"):
            raise ValueError("module mismatch")
        return {}


def minimal_witness(h1: str) -> dict[str, object]:
    return {
        "archivePath": "held.zip",
        "archiveRawSha256": "0" * 64,
        "entryPath": "module@v1.0.0/go.sum",
        "entryRawSha256": "1" * 64,
        "holderModule": "example.test/parent",
        "holderVersion": "v4.0.0",
        "holderWave": "synthetic",
        "line": 1,
        "text": f"example.test/target v1.0.0 {h1}",
        "h1": h1,
    }


class UnitBoundaryTests(unittest.TestCase):
    def test_01_static_surface_has_no_network_or_write_capability(
        self,
    ) -> None:
        raw = (ROOT / CHECKER_PATH).read_bytes()
        tree = ast.parse(raw.decode("utf-8"))
        banned_modules = {
            "asyncio",
            "http",
            "requests",
            "socket",
            "ssl",
            "subprocess",
            "urllib",
        }
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(
                    alias.name.split(".", 1)[0]
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Attribute):
                self.assertNotIn(
                    node.attr,
                    {
                        "O_APPEND",
                        "O_CREAT",
                        "O_RDWR",
                        "O_TRUNC",
                        "O_WRONLY",
                    },
                )
            elif isinstance(node, ast.Call) and isinstance(
                node.func,
                ast.Name,
            ):
                self.assertNotEqual(node.func.id, "input")
        self.assertTrue(imported.isdisjoint(banned_modules))
        source = raw.decode("utf-8")
        self.assertIn(
            "trusted_pinned_normal_reconstruction_path",
            source,
        )
        self.assertIn('"osSyscallSandboxProvided": False', source)

    def test_02_h1_validation_is_exact(self) -> None:
        self.assertTrue(CHECKER.valid_h1(VALID_H1_A))
        self.assertFalse(CHECKER.valid_h1("h1:not-base64"))
        self.assertFalse(
            CHECKER.valid_h1(
                "h1:"
                + base64.b64encode(bytes(31)).decode("ascii")
            )
        )
        self.assertFalse(CHECKER.valid_h1("sha256:" + "0" * 64))

    def test_03_declaration_capture_preserves_parent_and_line(
        self,
    ) -> None:
        raw = (
            b"module example.test/parent\n\n"
            b"require (\n"
            b"\texample.test/target v1.0.0 // indirect\n"
            b")\n"
        )
        target = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        result = CHECKER.capture_declarations(
            raw=raw,
            runner=FakeRunner,
            targets=target,
            holder_module="example.test/parent",
            holder_version="v4.0.0",
            holder_wave="synthetic",
            container_kind="external_mod",
            path="parent.mod",
            container_raw_sha256=sha256(raw),
            entry_raw_sha256=None,
        )
        rows = result[("example.test/target", "v1.0.0")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["line"], 4)
        self.assertEqual(
            rows[0]["text"],
            "\texample.test/target v1.0.0 // indirect",
        )
        self.assertEqual(
            rows[0]["holderModule"],
            "example.test/parent",
        )

    def test_04_missing_and_conflicting_h1_fail_identity(
        self,
    ) -> None:
        wave = [
            {
                "tupleOrder": 1,
                "module": "example.test/target",
                "version": "v1.0.0",
                "selectedByGraphAlgorithm": False,
            }
        ] * 15
        wave = [
            {
                **row,
                "tupleOrder": order,
                "module": f"example.test/target-{order}",
            }
            for order, row in enumerate(wave, 1)
        ]
        targets = {
            (row["module"], row["version"]): row
            for row in wave
        }
        declarations = {
            pair: [{"path": "parent.mod", "line": 1, "text": "x"}]
            for pair in targets
        }
        zip_h1 = {
            pair: [minimal_witness(VALID_H1_A)]
            for pair in targets
        }
        mod_h1 = {
            pair: [minimal_witness(VALID_H1_A)]
            for pair in targets
        }
        first = next(iter(targets))
        zip_h1[first] = []
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertFalse(rows[0]["identityPairComplete"])
        zip_h1[first] = [
            minimal_witness(VALID_H1_A),
            minimal_witness(VALID_H1_B),
        ]
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertTrue(rows[0]["moduleZipH1Conflict"])
        self.assertFalse(rows[0]["identityPairComplete"])

    def test_05_go_sum_and_zip_shapes_fail_closed(self) -> None:
        targets = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        common = {
            "targets": targets,
            "holder_module": "example.test/parent",
            "holder_version": "v4.0.0",
            "holder_wave": "synthetic",
            "archive_path": "held.zip",
            "archive_raw_sha256": "0" * 64,
            "entry_path": "parent@v4.0.0/go.sum",
        }
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.parse_go_sum_entry(
                raw=b"example.test/target v1.0.0 bad\n",
                **common,
            )
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.parse_go_sum_entry(raw=b"\xff\n", **common)
        duplicate = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("module@v1.0.0/go.sum", b"")
                archive.writestr("module@v1.0.0/go.sum", b"")
        duplicate.seek(0)
        with zipfile.ZipFile(duplicate, "r") as archive:
            with self.assertRaises(CHECKER.DecisionFailure):
                CHECKER.validate_archive_names(archive.infolist())
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.validate_archive_names(
                [zipfile.ZipInfo("../go.sum")]
            )

    def test_06_bootstrap_pin_rejects_aliases_and_retries_close(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir(mode=0o700)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = script / "tool.py"
            target.write_bytes(b"VALUE = 1\n")
            os.link(target, script / "alias.py")
            with self.assertRaises(CHECKER.DecisionFailure):
                CHECKER.BootstrapPinnedCodeFile(
                    root,
                    "script/tool.py",
                    sha256(target.read_bytes()),
                )
            (script / "alias.py").unlink()
            pinned = CHECKER.BootstrapPinnedCodeFile(
                root,
                "script/tool.py",
                sha256(target.read_bytes()),
            )
            descriptors = list(pinned.owned_fds)
            failed_fd = descriptors[len(descriptors) // 2]
            real_close = os.close
            failed = False

            def flaky_close(fd: int) -> None:
                nonlocal failed
                if fd == failed_fd and not failed:
                    failed = True
                    raise OSError(5, "synthetic")
                real_close(fd)

            with mock.patch.object(
                CHECKER.os,
                "close",
                side_effect=flaky_close,
            ):
                with self.assertRaises(OSError):
                    pinned.close()
            self.assertEqual(pinned.owned_fds, [failed_fd])
            pinned.close()
            self.assertEqual(pinned.owned_fds, [])

            alias_root = Path(temporary) / "alias-root"
            alias_root.symlink_to(root, target_is_directory=True)
            with self.assertRaises(Exception):
                CHECKER.BootstrapPinnedCodeFile(
                    alias_root,
                    "script/tool.py",
                    sha256(target.read_bytes()),
                )

    def test_07_frontier_and_request_order_are_exact(self) -> None:
        frontier = CHECKER.expected_frontier()
        self.assertEqual(len(frontier), 15)
        self.assertEqual(
            sha256(canonical(frontier)),
            CHECKER.V5_FRONTIER_SHA256,
        )
        rows = [
            {
                "tupleOrder": order,
                "module": value[0],
                "version": value[1],
                "goModH1Values": [value[2]],
                "moduleZipH1Values": [value[3]],
            }
            for order, value in enumerate(
                CHECKER.EXPECTED_IDENTITY,
                1,
            )
        ]
        requests = CHECKER.request_set(rows)
        self.assertEqual(requests, independent_request_oracle())


class LiveRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package_raw = {
            CHECKER.SELF_PATH:
                (ROOT / CHECKER.SELF_PATH).read_bytes(),
            CHECKER.TESTS_PATH:
                (ROOT / CHECKER.TESTS_PATH).read_bytes(),
            CHECKER.READER_PATH:
                (ROOT / CHECKER.READER_PATH).read_bytes(),
            CHECKER.V5_CHECKER_PATH:
                (ROOT / CHECKER.V5_CHECKER_PATH).read_bytes(),
            CHECKER.V5_TESTS_PATH:
                (ROOT / CHECKER.V5_TESTS_PATH).read_bytes(),
        }
        cls.generated = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(ROOT / CHECKER_PATH),
                "--print-expected",
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=600,
        )
        if cls.generated.returncode != 0:
            raise RuntimeError(
                cls.generated.stdout.decode("utf-8")
                + cls.generated.stderr.decode("utf-8")
            )
        cls.expected = json.loads(cls.generated.stdout)

    def mutated_failure(self, mutate, code: str) -> None:
        value = copy.deepcopy(self.expected)
        mutate(value)
        value.pop("contentBinding", None)
        value = CHECKER.content_bound(value)
        with self.assertRaises(
            CHECKER.DecisionFailure,
        ) as caught:
            CHECKER.validate_semantic_decision(
                value,
                self.package_raw,
            )
        self.assertEqual(caught.exception.code, code)

    def test_08_self_reader_tests_and_v5_pins(self) -> None:
        self.assertEqual(
            sha256(
                CHECKER.normalized_self_bytes(
                    self.package_raw[CHECKER.SELF_PATH]
                )
            ),
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.TESTS_PATH]),
            CHECKER.TESTS_RAW_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.READER_PATH]),
            CHECKER.READER_RAW_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.V5_CHECKER_PATH]),
            CHECKER.V5_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.V5_TESTS_PATH]),
            CHECKER.V5_TESTS_RAW_SHA256,
        )

    def test_09_materialized_decision_is_exact_canonical_output(
        self,
    ) -> None:
        decision_raw = (ROOT / DECISION_PATH).read_bytes()
        self.assertEqual(decision_raw, self.generated.stdout)
        self.assertEqual(decision_raw, canonical(self.expected))
        with mock.patch.object(
            CHECKER,
            "identity_barrier",
            wraps=CHECKER.identity_barrier,
        ) as identity_barrier:
            validated = CHECKER.validate_materialized_decision_path(
                ROOT,
                self.expected,
                self.package_raw,
            )
        self.assertEqual(validated, self.expected)
        self.assertEqual(identity_barrier.call_count, 2)
        identity = self.expected["identityResolution"]
        self.assertEqual(
            (
                identity["tupleCount"],
                identity["parentDeclarationCount"],
                identity["goModH1WitnessCount"],
                identity["moduleZipH1WitnessCount"],
                identity["completeIdentityPairCount"],
                identity["blockedTupleCount"],
                identity["conflictingIdentityCount"],
            ),
            (15, 18, 41, 20, 15, 0, 0),
        )
        self.assertEqual(
            identity["compactIdentitySha256"],
            CHECKER.COMPACT_IDENTITY_SHA256,
        )
        self.assertEqual(
            identity["fullWitnessSha256"],
            CHECKER.FULL_WITNESS_SHA256,
        )
        self.assertTrue(
            all(
                row["selectedByGraphAlgorithm"] is False
                for row in identity["tuples"]
            )
        )
        self.assertEqual(
            self.expected["sourceAcquisitionPreparation"][
                "requestSet"
            ],
            independent_request_oracle(),
        )

    def test_10_authority_scope_and_counters_are_closed(self) -> None:
        authority = self.expected["authority"]
        self.assertEqual(
            set(authority),
            set(CHECKER.EXPECTED_DECISION_AUTHORITY),
        )
        self.assertTrue(
            authority and all(value is False for value in authority.values())
        )
        lineage = self.expected["predecessorBindings"][
            "combinedFixedPointV5"
        ]
        self.assertEqual(
            lineage["providerFacadeVerificationScope"],
            "trusted_pinned_normal_reconstruction_path",
        )
        self.assertFalse(lineage["osSyscallSandboxProvided"])
        self.assertEqual(
            (
                lineage["totalFullSourceReconstructionCount"],
                lineage["totalGraphArchiveOpenCount"],
                lineage["trustedPinnedNormalPathFileWriteCount"],
            ),
            (8, 600, 0),
        )
        counters = self.expected["operationCounters"]
        self.assertEqual(
            (
                counters["identityWitnessScanCount"],
                counters["identityWitnessArchiveOpenCount"],
                counters["overallDecisionExecutionArchiveOpenCount"],
                counters["fileWriteCount"],
            ),
            (2, 200, 800, 0),
        )

    def test_11_unknown_keys_and_boolean_as_integer_fail(self) -> None:
        cases = (
            (
                lambda value:
                    value.__setitem__("unknown", False),
                "E_DECISION_SCHEMA",
            ),
            (
                lambda value:
                    value["authority"].__setitem__("unknown", False),
                "E_DECISION_AUTHORITY",
            ),
            (
                lambda value:
                    value["identityResolution"].__setitem__(
                        "unknown",
                        False,
                    ),
                "E_DECISION_IDENTITY",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("unknown", False),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"].__setitem__(
                        "requestCount",
                        True,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["operationCounters"].__setitem__(
                        "identityWitnessScanCount",
                        True,
                    ),
                "E_DECISION_COUNTERS",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV5"
                    ].__setitem__("fixedPointReached", 0),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV5"
                    ].__setitem__("osSyscallSandboxProvided", 0),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV5"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "completionAppliesToRetainedSnapshot",
                        1,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV5"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "currentPathIdentityGuaranteedThroughManifestPublication",
                        0,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV5"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
                        0,
                    ),
                "E_DECISION_LINEAGE",
            ),
        )
        for mutate, code in cases:
            with self.subTest(code=code):
                self.mutated_failure(mutate, code)

    def test_12_lineage_h1_request_and_scope_mutations_fail(
        self,
    ) -> None:
        cases = (
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV5"
                    ].__setitem__("frontierSha256", "0" * 64),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV5"
                    ].__setitem__("osSyscallSandboxProvided", True),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["heldSourceInputSet"].__setitem__(
                        "sourceBindingsSha256",
                        "0" * 64,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["identityResolution"]["tuples"][0].__setitem__(
                        "goModH1",
                        VALID_H1_A,
                    ),
                "E_DECISION_IDENTITY",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("resourceKind", "zip"),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("requestOrdinal", 2),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("expectedH1", VALID_H1_A),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__(
                        "url",
                        "https://proxy.golang.org/invalid",
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__(
                        "acceptedFileName",
                        "invalid.mod",
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__(
                        "maximumResponseBytes",
                        1_048_577,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["toolBindings"][0].__setitem__(
                        "normalizedSha256",
                        "0" * 64,
                    ),
                "E_DECISION_BINDINGS",
            ),
        )
        for mutate, code in cases:
            with self.subTest(code=code):
                self.mutated_failure(mutate, code)

    def test_13_main_normal_output_contract_is_fast(self) -> None:
        summary = {
            "documentType":
                "aetherlink.wave7-identity-acquisition-decision-check",
            "validationPassed": True,
            "tupleCount": 15,
            "acquisitionAuthorized": False,
            "externalAuthenticationRequired": False,
            "osSyscallSandboxProvided": False,
        }
        stdout = types.SimpleNamespace(buffer=io.BytesIO())
        with (
            mock.patch.object(
                CHECKER,
                "evaluate",
                return_value=(self.expected, summary),
            ) as evaluate_mock,
            mock.patch.object(CHECKER.sys, "stdout", stdout),
        ):
            returncode = CHECKER.main([])
        self.assertEqual(returncode, 0)
        evaluate_mock.assert_called_once_with(
            CHECKER.ROOT,
            verify_disk=True,
        )
        self.assertEqual(stdout.buffer.getvalue(), canonical(summary))


if __name__ == "__main__":
    unittest.main(verbosity=2)
