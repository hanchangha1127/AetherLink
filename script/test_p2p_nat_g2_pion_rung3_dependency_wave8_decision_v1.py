#!/usr/bin/env python3
"""Focused adversarial tests for the read-only Wave8 decision checker."""

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
    raise RuntimeError("Wave8 decision tests require `python3 -I -B -S`")

import ast
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import types
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave8_decision_v1.py"
)
DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.json"
)
READER_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave8-v1.md"
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
    module = types.ModuleType("wave8_decision_checker_test_subject")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(path),
            "__loader__": None,
            "__name__": "wave8_decision_checker_test_subject",
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
        ] * 14
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
        zip_h1[first] = [minimal_witness(VALID_H1_A)]
        mod_h1[first] = [
            minimal_witness(VALID_H1_A),
            minimal_witness(VALID_H1_B),
        ]
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertTrue(rows[0]["goModH1Conflict"])
        declarations[first] = []
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertFalse(rows[0]["declarationComplete"])

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

    def test_06_self_normalization_rejects_ambiguous_marker(
        self,
    ) -> None:
        raw = (ROOT / CHECKER_PATH).read_bytes()
        normalized = CHECKER.normalized_self_bytes(raw)
        self.assertEqual(
            sha256(normalized),
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
        with self.assertRaises(CHECKER.DecisionFailure) as caught:
            CHECKER.normalized_self_bytes(raw + marker + b"0" * 64 + b'"\n)')
        self.assertEqual(caught.exception.code, "E_SELF_IDENTITY")

    def test_07_frontier_and_request_order_are_exact(self) -> None:
        frontier = CHECKER.expected_frontier()
        self.assertEqual(len(frontier), 14)
        self.assertEqual(
            sha256(canonical(frontier)),
            CHECKER.V6_FRONTIER_SHA256,
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
        self.assertEqual(
            sha256(CHECKER.digest_json_bytes(requests)),
            "b0f0f887864ddc4cf3ab15319a9e89dbea8c84087fa3d0e374a0332240336ddc",
        )


class HardeningBoundaryTests(unittest.TestCase):
    def test_main_failure_documents_are_canonical(self) -> None:
        for raised, code in (
            (CHECKER.DecisionFailure("E_SYNTHETIC"), "E_SYNTHETIC"),
            (RuntimeError("sensitive details"), "E_INTERNAL"),
        ):
            stdout = types.SimpleNamespace(buffer=io.BytesIO())
            with (
                mock.patch.object(
                    CHECKER,
                    "evaluate",
                    side_effect=raised,
                ),
                mock.patch.object(CHECKER.sys, "stdout", stdout),
            ):
                returncode = CHECKER.main([])
            self.assertEqual(returncode, 1)
            self.assertEqual(
                stdout.buffer.getvalue(),
                canonical(CHECKER.error_document(code)),
            )

    def test_bootstrap_alias_and_close_retry_fail_closed(self) -> None:
        alias = types.SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600,
            st_nlink=2,
            st_uid=CHECKER.os.geteuid(),
            st_size=1,
        )
        with self.assertRaises(CHECKER.DecisionFailure) as caught:
            CHECKER.BootstrapPinnedCodeFile._validate_file(alias)
        self.assertEqual(caught.exception.code, "E_TOOL_IDENTITY")

        pinned = object.__new__(CHECKER.BootstrapPinnedCodeFile)
        pinned.owned_fds = [10, 11]
        pinned.directories = []
        pinned.fd = 11
        pinned.parent_fd = 10
        pinned.root_fd = 10
        failed = False

        def close_once(fd: int) -> None:
            nonlocal failed
            if fd == 10 and not failed:
                failed = True
                raise OSError(5, "synthetic")

        with (
            mock.patch.object(
                CHECKER.os,
                "close",
                side_effect=close_once,
            ),
            mock.patch.object(
                CHECKER.os,
                "fstat",
                return_value=alias,
            ),
        ):
            with self.assertRaises(OSError):
                pinned.close()
        self.assertEqual(pinned.owned_fds, [10])
        with mock.patch.object(CHECKER.os, "close", return_value=None):
            pinned.close()
        self.assertEqual(pinned.owned_fds, [])


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
            CHECKER.V6_CHECKER_PATH:
                (ROOT / CHECKER.V6_CHECKER_PATH).read_bytes(),
            CHECKER.V6_TESTS_PATH:
                (ROOT / CHECKER.V6_TESTS_PATH).read_bytes(),
        }
        cls.expected, _ = CHECKER.evaluate(
            ROOT,
            verify_disk=False,
        )
        cls.generated_raw = canonical(cls.expected)

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

    def test_08_self_reader_tests_and_v6_pins(self) -> None:
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
            sha256(self.package_raw[CHECKER.V6_CHECKER_PATH]),
            CHECKER.V6_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.V6_TESTS_PATH]),
            CHECKER.V6_TESTS_RAW_SHA256,
        )

    def test_09_materialized_decision_is_exact_canonical_output(
        self,
    ) -> None:
        decision_raw = (ROOT / DECISION_PATH).read_bytes()
        self.assertEqual(decision_raw, self.generated_raw)
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
            (14, 14, 93, 15, 14, 0, 0),
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
            "combinedFixedPointV6"
        ]
        self.assertEqual(
            lineage,
            {
                "checkerPath": CHECKER.V6_CHECKER_PATH,
                "checkerRawSha256": CHECKER.V6_CHECKER_RAW_SHA256,
                "checkerNormalizedSha256":
                    CHECKER.V6_CHECKER_NORMALIZED_SHA256,
                "testsPath": CHECKER.V6_TESTS_PATH,
                "testsRawSha256": CHECKER.V6_TESTS_RAW_SHA256,
                "contentSha256":
                    CHECKER.V6_CANDIDATE_CONTENT_SHA256,
                "combinedInputSetSha256": CHECKER.V6_INPUT_SET_SHA256,
                "sourceBindingsSha256":
                    CHECKER.V6_SOURCE_BINDINGS_SHA256,
                "graphSha256": CHECKER.V6_GRAPH_SHA256,
                "frontierSha256": CHECKER.V6_FRONTIER_SHA256,
                "fixedPointReached": False,
                "frontierTupleCount": 14,
                "totalFullSourceReconstructionCount": 10,
                "totalGraphArchiveOpenCount": 830,
                "providerFacadeVerificationScope":
                    "trusted_pinned_normal_reconstruction_path",
                "trustedPinnedNormalPathFileWriteCount": 0,
                "osSyscallSandboxProvided": False,
                "retainedSnapshotBoundary": {
                    "completionAppliesToRetainedSnapshot": True,
                    "currentPathIdentityGuaranteedThroughManifestPublication":
                        False,
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                        False,
                },
            },
        )
        self.assertEqual(
            lineage["providerFacadeVerificationScope"],
            "trusted_pinned_normal_reconstruction_path",
        )
        self.assertFalse(lineage["osSyscallSandboxProvided"])
        self.assertEqual(
            (
                lineage["checkerRawSha256"],
                lineage["checkerNormalizedSha256"],
                lineage["testsRawSha256"],
                lineage["contentSha256"],
                lineage["combinedInputSetSha256"],
                lineage["sourceBindingsSha256"],
                lineage["graphSha256"],
                lineage["frontierSha256"],
                lineage["frontierTupleCount"],
            ),
            (
                CHECKER.V6_CHECKER_RAW_SHA256,
                CHECKER.V6_CHECKER_NORMALIZED_SHA256,
                CHECKER.V6_TESTS_RAW_SHA256,
                CHECKER.V6_CANDIDATE_CONTENT_SHA256,
                CHECKER.V6_INPUT_SET_SHA256,
                CHECKER.V6_SOURCE_BINDINGS_SHA256,
                CHECKER.V6_GRAPH_SHA256,
                CHECKER.V6_FRONTIER_SHA256,
                14,
            ),
        )
        self.assertEqual(
            (
                lineage["totalFullSourceReconstructionCount"],
                lineage["totalGraphArchiveOpenCount"],
                lineage["trustedPinnedNormalPathFileWriteCount"],
            ),
            (10, 830, 0),
        )
        counters = self.expected["operationCounters"]
        self.assertEqual(
            (
                counters["identityWitnessScanCount"],
                counters["identityWitnessArchiveOpenCount"],
                counters["overallDecisionExecutionArchiveOpenCount"],
                counters["fileWriteCount"],
            ),
            (2, 230, 1060, 0),
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
                        "combinedFixedPointV6"
                    ].__setitem__("fixedPointReached", 0),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV6"
                    ].__setitem__("osSyscallSandboxProvided", 0),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV6"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "completionAppliesToRetainedSnapshot",
                        1,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV6"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "currentPathIdentityGuaranteedThroughManifestPublication",
                        0,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV6"
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
                        "combinedFixedPointV6"
                    ].__setitem__("frontierSha256", "0" * 64),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV6"
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
                "aetherlink.wave8-identity-acquisition-decision-check",
            "validationPassed": True,
            "tupleCount": 14,
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

    def test_14_request_contract_rejects_duplicates_and_encoding(
        self,
    ) -> None:
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
        duplicate = copy.deepcopy(rows)
        duplicate[1]["module"] = duplicate[0]["module"]
        duplicate[1]["version"] = duplicate[0]["version"]
        uppercase = copy.deepcopy(rows)
        uppercase[0]["module"] = "github.com/Example/module"
        reordered = copy.deepcopy(rows)
        reordered[0]["tupleOrder"] = 2
        for value in (duplicate, uppercase, reordered):
            with self.subTest(value=value[0]):
                with self.assertRaises(
                    CHECKER.DecisionFailure,
                ) as caught:
                    CHECKER.request_set(value)
                self.assertEqual(caught.exception.code, "E_REQUEST_SET")

    def test_15_go_sum_strips_only_exact_trailing_mod_suffix(
        self,
    ) -> None:
        targets = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        zip_rows, mod_rows = CHECKER.parse_go_sum_entry(
            raw=(
                f"example.test/target v1.0.0 {VALID_H1_A}\n"
                f"example.test/target v1.0.0/go.mod {VALID_H1_B}\n"
                f"example.test/target v1.0.0/go.mod/go.mod {VALID_H1_A}\n"
            ).encode(),
            targets=targets,
            holder_module="example.test/parent",
            holder_version="v1.0.0",
            holder_wave="synthetic",
            archive_path="held.zip",
            archive_raw_sha256="0" * 64,
            entry_path="parent@v1.0.0/go.sum",
        )
        pair = ("example.test/target", "v1.0.0")
        self.assertEqual(
            [row["h1"] for row in zip_rows[pair]],
            [VALID_H1_A],
        )
        self.assertEqual(
            [row["h1"] for row in mod_rows[pair]],
            [VALID_H1_B],
        )

    def test_16_every_closure_value_mutation_fails_closed(
        self,
    ) -> None:
        closure = self.expected["closure"]
        for key, expected in closure.items():
            with self.subTest(key=key):
                self.mutated_failure(
                    lambda value, key=key, expected=expected:
                        value["closure"].__setitem__(key, not expected),
                    "E_DECISION_CLOSURE",
                )

if __name__ == "__main__":
    unittest.main(verbosity=2)
