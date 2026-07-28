#!/usr/bin/env python3
"""Focused adversarial tests for the metadata-only Wave19 decision checker."""

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
    raise RuntimeError("Wave19 decision tests require `python3 -I -B -S`")

import ast
import builtins
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import types
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_decision_v1.py"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave19-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave19-v1.md"
)
V17_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v17.py"
V17_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v17.py"
NAMESPACE_ANCHOR_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-18-v1.claim"
)
X_NET_MOD_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-18-v1/accepted/002-3c84a9eecca520aed886.mod"
)
X_NET_ZIP_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-18-v1/accepted/002-3c84a9eecca520aed886.zip"
)

CHECKER_RAW_SHA256 = (
    "cd6926a344b52fafd0265ec8bd1f08cbdf250826fa53e46e6c5a3e94049f0d92"
)
CHECKER_NORMALIZED_SHA256 = (
    "a2a6535e18e26f0ba65a2a04614bee26e4a10e660c440928c70f80766c5a007f"
)
CHECKER_CALL_COUNT = 243
CHECKER_CALL_SURFACE_SHA256 = (
    "19da634124d6b35d8e2060b7feebadb9492515d6198e01f0930fb18da5ef2c30"
)
DECISION_RAW_SHA256 = (
    "7486a8a4659459ce49128bcf05501abb065f2b64c542715eaebd3c1ca686a8cf"
)
DECISION_CONTENT_SHA256 = (
    "39edf590a88d728a105c74ef0eeb1600c84159888d3b4edbbe4acba05e7a6f56"
)
READER_RAW_SHA256 = (
    "3aefdd1e3a283e099ad4a3624103461eee821043ad4bf18a57a39c81b100d526"
)
V17_CHECKER_RAW_SHA256 = (
    "32df9bd1bf9b4b6610a2a74038956eab7e51c506198c11f45fa5058968caacb8"
)
V17_CHECKER_NORMALIZED_SHA256 = (
    "d2ebef7f9aad384b08a68c438320de882d640a859a7d35521853818afbcdd7ce"
)
V17_TESTS_RAW_SHA256 = (
    "3403ec05b1f6a9561a74a44b001352230d0d68db72789403f6155785f01588f0"
)
NAMESPACE_ANCHOR_RAW_SHA256 = (
    "08f5134ce03805e512c2dec0dee13251ce682d793d2b87f7f8e29f6d3426d362"
)
X_NET_MOD_RAW_SHA256 = (
    "3258ec9e17abe2bf1053d0b176d3d50367815237a7701eb373c38152bbd6b9a0"
)
X_NET_ZIP_RAW_SHA256 = (
    "388e4a624f48990057f1a2a2cc5f3e0f81e41b99dd2036247d98c931c59d44d4"
)
V17_CANDIDATE_CONTENT_SHA256 = (
    "1267edbe7f1a4f2554808376f67c6ba25a9217db0e6e2cc80a0822d780710f78"
)
V17_GRAPH_SHA256 = (
    "cc748b6a5285321d8e74abab1c881dbc5ffd4433865ba9c75e459152f459092e"
)
V17_FRONTIER_SHA256 = (
    "4a7998ef0c1e5716640cccf9c5b349e92124bd787a2ca4090e3ba0920b68b006"
)
V17_INPUT_SET_SHA256 = (
    "79f2c8e28daf3f46c97d827cdc7416b77905eea49bc482911f8d234e0de3765f"
)
V17_SOURCE_BINDINGS_SHA256 = (
    "72c1253423412744380ed5c7f8b74f9d5b34daaefd05caf5b384d9bb55589490"
)
COMPACT_IDENTITY_SHA256 = (
    "a3f5a20989a886accb15c79d8c47202c38a84e8d42fe54e44da7b598bd44534b"
)
FULL_WITNESS_SHA256 = (
    "6fd00b2ec910ef9dae4a3f03dc74105038f1ae855092366509c509e8394c5e7d"
)
REQUEST_SET_SHA256 = (
    "97f4d8c1775c01c27f83f19b66af6274e0ae77b1be328456c2685ba18552b6e7"
)

EXPECTED_IMPORT_SURFACE = (
    ("from", "__future__", 0, (("annotations", None),)),
    ("import", (("sys", None),)),
    ("import", (("argparse", None),)),
    ("import", (("base64", None),)),
    ("from", "contextlib", 0, (("ExitStack", None),)),
    ("import", (("hashlib", None),)),
    ("import", (("io", None),)),
    ("import", (("json", None),)),
    ("import", (("os", None),)),
    ("from", "pathlib", 0, (("Path", None),)),
    ("import", (("re", None),)),
    ("import", (("stat", None),)),
    (
        "from",
        "typing",
        0,
        (("Any", None), ("Mapping", None), ("Sequence", None)),
    ),
    ("import", (("zipfile", None),)),
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
        ).encode()
        + b"\n"
    )


def compact(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def independently_normalized(raw: bytes) -> bytes:
    pattern = re.compile(
        br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
    )
    result, count = pattern.subn(
        rb"\g<1>" + b"0" * 64 + rb"\g<2>",
        raw,
    )
    if count != 1:
        raise AssertionError("normalization marker mismatch")
    return result


def static_import_surface(tree: ast.AST) -> tuple[object, ...]:
    rows: list[object] = []
    imports = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for node in imports:
        if isinstance(node, ast.Import):
            rows.append(
                (
                    "import",
                    tuple((alias.name, alias.asname) for alias in node.names),
                )
            )
        else:
            rows.append(
                (
                    "from",
                    node.module,
                    node.level,
                    tuple((alias.name, alias.asname) for alias in node.names),
                )
            )
    return tuple(rows)


def dotted_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


class CheckerCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.calls: list[tuple[int, int, str, ast.Call]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(
            (
                node.lineno,
                node.col_offset,
                ".".join(self.scope) or "<module>",
                node,
            )
        )
        self.generic_visit(node)


def call_surface_sha256(
    rows: list[tuple[int, int, str, ast.Call]],
) -> str:
    projection = [
        {
            "call": ast.dump(
                call,
                annotate_fields=True,
                include_attributes=False,
            ),
            "scope": scope,
        }
        for _, _, scope, call in sorted(
            rows,
            key=lambda row: (
                row[0],
                row[1],
                row[2],
                ast.dump(
                    row[3],
                    annotate_fields=True,
                    include_attributes=False,
                ),
            ),
        )
    ]
    return sha256(canonical(projection))


def checker_surface_signature(
    source: str,
) -> tuple[tuple[object, ...], int, str]:
    tree = ast.parse(source, filename=CHECKER_PATH)
    visitor = CheckerCallVisitor()
    visitor.visit(tree)
    return (
        static_import_surface(tree),
        len(visitor.calls),
        call_surface_sha256(visitor.calls),
    )


def load_checker() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "wave19_decision_checker_tests_target",
        ROOT / CHECKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("checker load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER_RAW = (ROOT / CHECKER_PATH).read_bytes()
CHECKER_SOURCE = CHECKER_RAW.decode("utf-8", errors="strict")
CHECKER_TREE = ast.parse(CHECKER_SOURCE, filename=CHECKER_PATH)
CHECKER = load_checker()
DECISION_RAW = (ROOT / DECISION_PATH).read_bytes()
DECISION = json.loads(DECISION_RAW)
READER_RAW = (ROOT / READER_PATH).read_bytes()
MOD_RAW = (ROOT / X_NET_MOD_PATH).read_bytes()
ZIP_RAW = (ROOT / X_NET_ZIP_PATH).read_bytes()


def bound(value: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(value)
    result.pop("contentBinding", None)
    digest = sha256(canonical(result))
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "decision_without_contentBinding",
        "sha256": digest,
    }
    return result


def synthetic_zip(go_sum_raw: bytes, *, duplicate: bool = False) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr(CHECKER.X_NET_GO_SUM_PATH, go_sum_raw)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                archive.writestr(CHECKER.X_NET_GO_SUM_PATH, go_sum_raw)
    return output.getvalue()


def exact_go_sum_raw() -> bytes:
    with zipfile.ZipFile(io.BytesIO(ZIP_RAW), mode="r") as archive:
        return archive.read(CHECKER.X_NET_GO_SUM_PATH)


class Wave19DecisionTests(unittest.TestCase):
    maxDiff = None

    def assert_decision_failure(
        self,
        changed: dict[str, object],
        code: str,
        *,
        rebind: bool = True,
        namespace_clean: bool = True,
    ) -> None:
        candidate = bound(changed) if rebind else changed
        with self.assertRaises(CHECKER.DecisionCheckFailure) as caught:
            CHECKER.validate_decision(
                candidate,
                namespace_clean=namespace_clean,
            )
        self.assertEqual(str(caught.exception), code)

    def test_01_static_checker_surface_is_exact_and_read_only(self) -> None:
        self.assertEqual(sha256(CHECKER_RAW), CHECKER_RAW_SHA256)
        self.assertEqual(
            sha256(independently_normalized(CHECKER_RAW)),
            CHECKER_NORMALIZED_SHA256,
        )
        tree = CHECKER_TREE
        self.assertEqual(
            static_import_surface(tree),
            EXPECTED_IMPORT_SURFACE,
        )
        visitor = CheckerCallVisitor()
        visitor.visit(tree)
        self.assertEqual(len(visitor.calls), CHECKER_CALL_COUNT)
        self.assertEqual(
            call_surface_sha256(visitor.calls),
            CHECKER_CALL_SURFACE_SHA256,
        )
        forbidden_import_roots = {
            "asyncio",
            "ctypes",
            "getpass",
            "http",
            "importlib",
            "keyring",
            "multiprocessing",
            "requests",
            "runpy",
            "socket",
            "ssl",
            "subprocess",
            "urllib",
        }
        forbidden_names = {"compile", "eval", "exec", "__import__", "open"}
        forbidden_attributes = {
            "bind",
            "chmod",
            "chown",
            "connect",
            "create_connection",
            "extract",
            "extractall",
            "fork",
            "forkpty",
            "link",
            "listen",
            "makedirs",
            "mkdir",
            "popen",
            "posix_spawn",
            "remove",
            "rename",
            "replace",
            "rmdir",
            "send",
            "sendall",
            "sendto",
            "socket",
            "symlink",
            "system",
            "touch",
            "truncate",
            "unlink",
            "urlopen",
            "write_bytes",
            "write_text",
        }
        os_open_calls = 0
        stdout_calls = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name.split(".", 1)[0],
                        forbidden_import_roots,
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(
                    node.module.split(".", 1)[0],
                    forbidden_import_roots,
                )
            if not isinstance(node, ast.Call):
                continue
            dotted = dotted_name(node.func)
            self.assertNotIn(
                dotted,
                {
                    "io.open",
                    "os.write",
                    "runpy.run_module",
                    "runpy.run_path",
                },
            )
            if isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, forbidden_names)
            if isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden_attributes)
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr == "open"
                ):
                    os_open_calls += 1
                if (
                    node.func.attr == "write"
                    and ast.unparse(node.func.value)
                    == "sys.stdout.buffer"
                ):
                    stdout_calls += 1
        self.assertEqual(os_open_calls, 1)
        self.assertEqual(stdout_calls, 3)
        source = CHECKER_RAW.decode()
        self.assertIn("os.O_RDONLY | os.O_CLOEXEC", source)
        for flag in (
            "os.O_APPEND",
            "os.O_CREAT",
            "os.O_RDWR",
            "os.O_TRUNC",
            "os.O_WRONLY",
        ):
            self.assertNotIn(flag, source)

    def test_02_repository_seals_and_content_binding_are_exact(self) -> None:
        expected = {
            CHECKER_PATH: CHECKER_RAW_SHA256,
            DECISION_PATH: DECISION_RAW_SHA256,
            READER_PATH: READER_RAW_SHA256,
            V17_CHECKER_PATH: V17_CHECKER_RAW_SHA256,
            V17_TESTS_PATH: V17_TESTS_RAW_SHA256,
            NAMESPACE_ANCHOR_PATH: NAMESPACE_ANCHOR_RAW_SHA256,
            X_NET_MOD_PATH: X_NET_MOD_RAW_SHA256,
            X_NET_ZIP_PATH: X_NET_ZIP_RAW_SHA256,
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(
                    sha256((ROOT / path).read_bytes()),
                    digest,
                )
        self.assertEqual(DECISION_RAW, canonical(DECISION))
        without = dict(DECISION)
        binding = without.pop("contentBinding")
        self.assertEqual(
            sha256(canonical(without)),
            DECISION_CONTENT_SHA256,
        )
        self.assertEqual(
            binding["sha256"],
            DECISION_CONTENT_SHA256,
        )
        self.assertEqual(
            sha256(
                independently_normalized(
                    (ROOT / V17_CHECKER_PATH).read_bytes()
                )
            ),
            V17_CHECKER_NORMALIZED_SHA256,
        )

    def test_03_v17_predecessor_binding_is_exact(self) -> None:
        predecessor = DECISION["predecessorBindings"][
            "combinedFixedPointV17"
        ]
        self.assertEqual(
            predecessor,
            CHECKER.expected_predecessor()["combinedFixedPointV17"],
        )
        self.assertFalse(predecessor["fixedPointReached"])
        self.assertEqual(predecessor["frontierTupleCount"], 2)
        self.assertEqual(
            (
                predecessor["contentSha256"],
                predecessor["graphSha256"],
                predecessor["frontierSha256"],
                predecessor["combinedInputSetSha256"],
                predecessor["sourceBindingsSha256"],
            ),
            (
                V17_CANDIDATE_CONTENT_SHA256,
                V17_GRAPH_SHA256,
                V17_FRONTIER_SHA256,
                V17_INPUT_SET_SHA256,
                V17_SOURCE_BINDINGS_SHA256,
            ),
        )
        self.assertEqual(
            (
                predecessor["sourceBindingCount"],
                predecessor["totalFullSourceReconstructionCount"],
                predecessor["totalGraphArchiveOpenCount"],
            ),
            (365, 32, 4422),
        )

    def test_04_exact_identity_order_and_h1_pairs(self) -> None:
        rows = DECISION["identityResolution"]["tuples"]
        self.assertEqual(rows, CHECKER.expected_identity_rows())
        self.assertEqual(
            [
                (row["tupleOrder"], row["module"], row["version"])
                for row in rows
            ],
            [
                (1, "golang.org/x/crypto", "v0.38.0"),
                (2, "golang.org/x/text", "v0.25.0"),
            ],
        )
        for row in rows:
            self.assertFalse(row["selectedByGraphAlgorithm"])
            self.assertTrue(row["identityPairComplete"])
            self.assertTrue(row["acquisitionReady"])
            self.assertFalse(row["acquisitionAuthorized"])
            CHECKER.validate_h1(row["goModH1"])
            CHECKER.validate_h1(row["moduleZipH1"])

    def test_05_exact_request_order_ordinals_and_names(self) -> None:
        requests = DECISION["sourceAcquisitionPreparation"]["requestSet"]
        self.assertEqual(requests, CHECKER.expected_request_set())
        self.assertEqual(
            [row["requestOrdinal"] for row in requests],
            list(range(1, 5)),
        )
        self.assertEqual(
            [row["resourceKind"] for row in requests],
            ["mod", "zip"] * 2,
        )
        self.assertEqual(
            [row["tupleOrder"] for row in requests],
            [1, 1, 2, 2],
        )
        self.assertEqual(
            [row["acceptedFileName"] for row in requests],
            [
                "001-a26a2513c9f4c49c479c.mod",
                "001-a26a2513c9f4c49c479c.zip",
                "002-c6022d5be99f60f2428e.mod",
                "002-c6022d5be99f60f2428e.zip",
            ],
        )
        for row in requests:
            self.assertFalse(row["authenticationRequired"])
            self.assertFalse(row["networkAuthorized"])
            self.assertFalse(row["acquisitionAuthorized"])

    def test_06_authority_closure_and_counters_are_exact(self) -> None:
        self.assertEqual(DECISION["authority"], CHECKER.EXPECTED_AUTHORITY)
        self.assertTrue(DECISION["authority"])
        for value in DECISION["authority"].values():
            self.assertIs(value, False)
        self.assertEqual(DECISION["closure"], CHECKER.EXPECTED_CLOSURE)
        self.assertEqual(
            {
                key
                for key, value in DECISION["closure"].items()
                if value is True
            },
            {"wave19AcquisitionReady", "wave19IdentityResolved"},
        )
        self.assertEqual(
            DECISION["operationCounters"],
            CHECKER.EXPECTED_COUNTERS,
        )
        zero_names = {
            "archiveExtractionCount",
            "authenticationOperationCount",
            "combinedV17CandidateInvocationCount",
            "dependencySourceCompileCount",
            "dependencySourceExecutionCount",
            "dependencySourceLoadCount",
            "dependencySourceReconstructionCount",
            "fileWriteCount",
            "networkOperationCount",
            "productRuntimeNetworkOperationCount",
            "socketOperationCount",
            "subprocessCount",
        }
        for name in zero_names:
            self.assertIs(type(DECISION["operationCounters"][name]), int)
            self.assertEqual(DECISION["operationCounters"][name], 0)

    def test_07_nonclaims_reader_and_bindings_are_exact(self) -> None:
        self.assertEqual(DECISION["nonClaims"], CHECKER.EXPECTED_NON_CLAIMS)
        self.assertEqual(
            DECISION["readerDocumentBinding"],
            {"path": READER_PATH, "rawSha256": READER_RAW_SHA256},
        )
        text = READER_RAW.decode()
        for fragment in (
            "No\nWave19 acquisition has run.",
            "`fixedPointReached=false`",
            "creates no permit or runner",
            "performs no source reconstruction",
            "independent review of this decision package",
        ):
            self.assertIn(fragment, text)

    def test_08_compact_witness_and_request_seals_reproduce(self) -> None:
        self.assertEqual(
            sha256(compact(CHECKER.expected_compact_identity())),
            COMPACT_IDENTITY_SHA256,
        )
        self.assertEqual(
            sha256(compact(CHECKER.expected_full_witness())),
            FULL_WITNESS_SHA256,
        )
        self.assertEqual(
            sha256(compact(CHECKER.expected_request_set())),
            REQUEST_SET_SHA256,
        )
        identity = DECISION["identityResolution"]
        self.assertEqual(
            (
                identity["compactIdentitySha256"],
                identity["fullWitnessSha256"],
                DECISION["sourceAcquisitionPreparation"][
                    "requestSetCanonicalSha256"
                ],
            ),
            (
                COMPACT_IDENTITY_SHA256,
                FULL_WITNESS_SHA256,
                REQUEST_SET_SHA256,
            ),
        )

    def test_09_strict_json_rejects_duplicate_float_and_encoding(self) -> None:
        invalid = (
            b'{"a":1,"a":2}\n',
            b'{"a":1.0}\n',
            b'{"a":NaN}\n',
            b'{ "a":1 }\n',
            b'{"a":"\xff"}\n',
        )
        for index, raw in enumerate(invalid):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.DecisionCheckFailure):
                    CHECKER.strict_json(raw, "fixture")

    def test_10_h1_validation_is_exact(self) -> None:
        for source in CHECKER.TUPLES:
            CHECKER.validate_h1(source["goModH1"])
            CHECKER.validate_h1(source["moduleZipH1"])
        for value in (
            True,
            1,
            "h1:",
            "h1:not-base64",
            "sha256:" + "0" * 64,
        ):
            with self.subTest(value=value):
                with self.assertRaises(CHECKER.DecisionCheckFailure):
                    CHECKER.validate_h1(value)

    def test_11_metadata_scanner_reproduces_exact_witness(self) -> None:
        first = CHECKER.scan_retained_metadata(MOD_RAW, ZIP_RAW)
        second = CHECKER.scan_retained_metadata(MOD_RAW, ZIP_RAW)
        self.assertEqual(first, second)
        self.assertEqual(first, CHECKER.expected_full_witness())
        self.assertEqual(sha256(compact(first)), FULL_WITNESS_SHA256)

        logical_mod = MOD_RAW.replace(
            b"\tgolang.org/x/crypto v0.38.0",
            b"\tgolang.org/x/crypto\t  v0.38.0",
            1,
        )
        go_sum = exact_go_sum_raw()
        logical_go_sum = go_sum.replace(
            (
                b"golang.org/x/crypto v0.38.0 "
                b"h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8="
            ),
            (
                b"golang.org/x/crypto\tv0.38.0  "
                b"h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8="
            ),
            1,
        ).replace(
            (
                b"golang.org/x/crypto v0.38.0/go.mod "
                b"h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw="
            ),
            (
                b"golang.org/x/crypto  v0.38.0/go.mod\t"
                b"h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw="
            ),
            1,
        )
        self.assertEqual(
            CHECKER.scan_retained_metadata(
                logical_mod,
                synthetic_zip(logical_go_sum),
            ),
            CHECKER.expected_full_witness(),
        )

    def test_12_metadata_scanner_rejects_parent_mutations(self) -> None:
        first_line = CHECKER.TUPLES[0]["parentLine"].encode()
        cases = (
            MOD_RAW.replace(first_line, b"", 1),
            MOD_RAW + b"\n" + first_line + b"\n",
            (
                MOD_RAW
                + b"\n\tgolang.org/x/crypto\t  v0.38.0\n"
            ),
            (
                MOD_RAW
                + b"\n\tgolang.org/x/crypto v0.37.0"
                + b" // conflicting alternate parent\n"
            ),
            MOD_RAW.replace(b"require (", b"require", 1),
        )
        for index, raw in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.DecisionCheckFailure) as caught:
                    CHECKER.scan_retained_metadata(raw, ZIP_RAW)
                self.assertEqual(str(caught.exception), "E_METADATA")

    def test_13_metadata_scanner_rejects_h1_and_zip_mutations(self) -> None:
        go_sum = exact_go_sum_raw()
        line = (
            b"golang.org/x/crypto v0.38.0 "
            b"h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8="
        )
        cases = (
            synthetic_zip(go_sum.replace(line, b"", 1)),
            synthetic_zip(go_sum + b"\n" + line + b"\n"),
            synthetic_zip(
                go_sum
                + b"\n"
                + (
                    b"golang.org/x/crypto\tv0.38.0  "
                    b"h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8=\n"
                )
            ),
            synthetic_zip(
                go_sum
                + b"\n"
                + (
                    b"golang.org/x/crypto  v0.38.0/go.mod\t"
                    b"h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw=\n"
                )
            ),
            synthetic_zip(
                go_sum
                + b"\n"
                + (
                    b"golang.org/x/crypto v0.38.0 "
                    b"h1:qVyWApTSYLk/drJRO5mDlNYskwQznZmkpV2c8q9zls4=\n"
                )
            ),
            synthetic_zip(
                go_sum
                + b"\n"
                + (
                    b"golang.org/x/crypto v0.38.0/go.mod "
                    b"h1:WEdwpYrmk1qmdHvhkSTNPm3app7v4rsT8F2UD6+VHIA=\n"
                )
            ),
            synthetic_zip(
                go_sum.replace(
                    line,
                    (
                        b"golang.org/x/crypto v0.38.0 "
                        b"h1:qVyWApTSYLk/drJRO5mDlNYskwQznZmkpV2c8q9zls4="
                    ),
                    1,
                )
            ),
            synthetic_zip(go_sum, duplicate=True),
            b"not a zip",
        )
        for index, raw in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.DecisionCheckFailure):
                    CHECKER.scan_retained_metadata(MOD_RAW, raw)

    def test_14_materialized_decision_passes_exact_validation(self) -> None:
        CHECKER.validate_decision(DECISION, namespace_clean=True)
        self.assertEqual(
            DECISION["status"],
            (
                "wave19_exact_2_frontier_identity_classified_2_complete_"
                "0_blocked_acquisition_ready_not_authorized"
            ),
        )
        self.assertEqual(
            DECISION["nextAction"],
            "independent_review_of_wave19_decision_package",
        )

    def test_15_each_validation_section_has_own_failure_code(self) -> None:
        cases: list[tuple[str, object]] = [
            (
                "E_HEADER",
                lambda value: value.__setitem__("schemaVersion", "2.0"),
            ),
            (
                "E_NON_CLAIMS",
                lambda value: value["nonClaims"].append("invented"),
            ),
            (
                "E_PREDECESSOR",
                lambda value: value["predecessorBindings"][
                    "combinedFixedPointV17"
                ].__setitem__("frontierTupleCount", 3),
            ),
            (
                "E_IDENTITY",
                lambda value: value["identityResolution"]["tuples"][0].__setitem__(
                    "module",
                    "example.invalid/module",
                ),
            ),
            (
                "E_ACQUISITION",
                lambda value: value["sourceAcquisitionPreparation"].__setitem__(
                    "requestCount",
                    5,
                ),
            ),
            (
                "E_CLOSURE",
                lambda value: value["closure"].__setitem__(
                    "dependencyFixedPointReached",
                    True,
                ),
            ),
            (
                "E_COUNTERS",
                lambda value: value["operationCounters"].__setitem__(
                    "networkOperationCount",
                    1,
                ),
            ),
            (
                "E_METADATA_BINDING",
                lambda value: value["retainedMetadataEvidence"].__setitem__(
                    "sourceCodeInspected",
                    True,
                ),
            ),
            (
                "E_BINDINGS",
                lambda value: value["readerDocumentBinding"].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
            ),
            (
                "E_RESULT",
                lambda value: value.__setitem__("status", "invented"),
            ),
        ]
        for code, mutate in cases:
            changed = copy.deepcopy(DECISION)
            mutate(changed)
            with self.subTest(code=code):
                self.assert_decision_failure(changed, code)

        changed = copy.deepcopy(DECISION)
        changed["contentBinding"]["sha256"] = "0" * 64
        self.assert_decision_failure(
            changed,
            "E_CONTENT_BINDING",
            rebind=False,
        )

    def test_16_unknown_keys_fail_closed_at_nested_boundaries(self) -> None:
        cases: list[tuple[str, object]] = [
            ("E_TOP_LEVEL_KEYS", lambda value: value.__setitem__("extra", 0)),
            (
                "E_AUTHORITY",
                lambda value: value["authority"].__setitem__("extra", False),
            ),
            (
                "E_PREDECESSOR",
                lambda value: value["predecessorBindings"][
                    "combinedFixedPointV17"
                ].__setitem__("extra", False),
            ),
            (
                "E_IDENTITY",
                lambda value: value["identityResolution"].__setitem__(
                    "extra",
                    0,
                ),
            ),
            (
                "E_IDENTITY",
                lambda value: value["identityResolution"]["tuples"][0].__setitem__(
                    "extra",
                    False,
                ),
            ),
            (
                "E_ACQUISITION",
                lambda value: value["sourceAcquisitionPreparation"].__setitem__(
                    "extra",
                    False,
                ),
            ),
            (
                "E_ACQUISITION",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ][0].__setitem__("extra", False),
            ),
            (
                "E_CLOSURE",
                lambda value: value["closure"].__setitem__("extra", False),
            ),
            (
                "E_COUNTERS",
                lambda value: value["operationCounters"].__setitem__(
                    "extra",
                    0,
                ),
            ),
            (
                "E_METADATA_BINDING",
                lambda value: value["retainedMetadataEvidence"].__setitem__(
                    "extra",
                    False,
                ),
            ),
            (
                "E_BINDINGS",
                lambda value: value["toolBindings"][0].__setitem__(
                    "extra",
                    False,
                ),
            ),
        ]
        for code, mutate in cases:
            changed = copy.deepcopy(DECISION)
            mutate(changed)
            with self.subTest(code=code):
                self.assert_decision_failure(changed, code)

    def test_17_bool_integer_and_float_aliases_fail_closed(self) -> None:
        cases: list[tuple[str, object]] = [
            (
                "E_AUTHORITY",
                lambda value: value["authority"].__setitem__(
                    "networkAuthorized",
                    0,
                ),
            ),
            (
                "E_PREDECESSOR",
                lambda value: value["predecessorBindings"][
                    "combinedFixedPointV17"
                ].__setitem__("frontierTupleCount", True),
            ),
            (
                "E_IDENTITY",
                lambda value: value["identityResolution"]["tuples"][0].__setitem__(
                    "tupleOrder",
                    True,
                ),
            ),
            (
                "E_ACQUISITION",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ][0].__setitem__("requestOrdinal", True),
            ),
            (
                "E_COUNTERS",
                lambda value: value["operationCounters"].__setitem__(
                    "networkOperationCount",
                    False,
                ),
            ),
            (
                "E_IDENTITY",
                lambda value: value["identityResolution"].__setitem__(
                    "tupleCount",
                    2.0,
                ),
            ),
        ]
        for code, mutate in cases:
            changed = copy.deepcopy(DECISION)
            mutate(changed)
            with self.subTest(code=code):
                self.assert_decision_failure(changed, code)

    def test_18_tuple_permutation_duplicate_and_cross_pair_fail(self) -> None:
        mutations = []

        def permute(value: dict[str, object]) -> None:
            rows = value["identityResolution"]["tuples"]
            rows[0], rows[1] = rows[1], rows[0]

        mutations.append(permute)
        mutations.append(
            lambda value: value["identityResolution"]["tuples"].__setitem__(
                1,
                copy.deepcopy(value["identityResolution"]["tuples"][0]),
            )
        )

        def cross_pair(value: dict[str, object]) -> None:
            rows = value["identityResolution"]["tuples"]
            rows[0]["moduleZipH1"], rows[1]["moduleZipH1"] = (
                rows[1]["moduleZipH1"],
                rows[0]["moduleZipH1"],
            )

        mutations.append(cross_pair)
        mutations.append(
            lambda value: value["identityResolution"]["tuples"].pop()
        )
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(DECISION)
            mutate(changed)
            with self.subTest(index=index):
                self.assert_decision_failure(changed, "E_IDENTITY")

    def test_19_request_permutation_duplicate_and_ordinal_fail(self) -> None:
        mutations = []

        def permute(value: dict[str, object]) -> None:
            rows = value["sourceAcquisitionPreparation"]["requestSet"]
            rows[0], rows[1] = rows[1], rows[0]

        mutations.append(permute)
        mutations.append(
            lambda value: value["sourceAcquisitionPreparation"][
                "requestSet"
            ][1].__setitem__("requestOrdinal", 1)
        )
        mutations.append(
            lambda value: value["sourceAcquisitionPreparation"][
                "requestSet"
            ][0].__setitem__(
                "acceptedFileName",
                "001-00000000000000000000.mod",
            )
        )
        mutations.append(
            lambda value: value["sourceAcquisitionPreparation"][
                "requestSet"
            ].__setitem__(
                2,
                copy.deepcopy(
                    value["sourceAcquisitionPreparation"]["requestSet"][0]
                ),
            )
        )

        def cross_tuple_pair_permutation(value: dict[str, object]) -> None:
            rows = value["sourceAcquisitionPreparation"]["requestSet"]
            rows[:] = rows[2:4] + rows[0:2]

        mutations.append(cross_tuple_pair_permutation)

        def cross_h1(value: dict[str, object]) -> None:
            rows = value["sourceAcquisitionPreparation"]["requestSet"]
            rows[0]["expectedH1"], rows[2]["expectedH1"] = (
                rows[2]["expectedH1"],
                rows[0]["expectedH1"],
            )

        mutations.append(cross_h1)

        def cross_module(value: dict[str, object]) -> None:
            rows = value["sourceAcquisitionPreparation"]["requestSet"]
            rows[1]["module"], rows[3]["module"] = (
                rows[3]["module"],
                rows[1]["module"],
            )

        mutations.append(cross_module)

        def cross_version(value: dict[str, object]) -> None:
            rows = value["sourceAcquisitionPreparation"]["requestSet"]
            rows[0]["version"], rows[2]["version"] = (
                rows[2]["version"],
                rows[0]["version"],
            )

        mutations.append(cross_version)
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(DECISION)
            mutate(changed)
            with self.subTest(index=index):
                self.assert_decision_failure(changed, "E_ACQUISITION")

    def test_20_namespace_snapshot_and_argument_fail_closed(self) -> None:
        for name in (
            ".wave-19-v1.claim",
            "wave-19-v1",
            ".wave-19-v1-staging-test",
        ):
            with (
                self.subTest(name=name),
                mock.patch.object(
                    CHECKER.os,
                    "listdir",
                    return_value=("existing", name),
                ),
                self.assertRaises(CHECKER.DecisionCheckFailure) as caught,
            ):
                CHECKER.namespace_snapshot(ROOT)
            self.assertEqual(str(caught.exception), "E_NAMESPACE")
        self.assert_decision_failure(
            copy.deepcopy(DECISION),
            "E_ACQUISITION",
            namespace_clean=False,
        )

    def test_21_live_run_has_exact_eight_read_only_holds(self) -> None:
        real_os_open = os.open
        opened: list[tuple[object, int]] = []

        def observed_open(path: object, flags: int, *args: object) -> int:
            opened.append((path, flags))
            return real_os_open(path, flags, *args)

        with (
            mock.patch.object(
                CHECKER,
                "scan_retained_metadata",
                wraps=CHECKER.scan_retained_metadata,
            ) as scan,
            mock.patch.object(
                CHECKER,
                "namespace_snapshot",
                wraps=CHECKER.namespace_snapshot,
            ) as namespace,
            mock.patch.object(CHECKER.os, "open", side_effect=observed_open),
            mock.patch.object(
                CHECKER.io,
                "open",
                side_effect=AssertionError("io.open forbidden"),
            ),
            mock.patch.object(
                CHECKER.os,
                "write",
                side_effect=AssertionError("os.write forbidden"),
            ),
            mock.patch.object(
                builtins,
                "open",
                side_effect=AssertionError("builtins.open forbidden"),
            ),
            mock.patch.object(
                builtins,
                "compile",
                side_effect=AssertionError("compile forbidden"),
            ),
            mock.patch.object(
                builtins,
                "exec",
                side_effect=AssertionError("exec forbidden"),
            ),
        ):
            result = CHECKER.run_check(ROOT)
        self.assertEqual(result, DECISION)
        self.assertEqual(scan.call_count, 2)
        self.assertEqual(namespace.call_count, 2)
        self.assertEqual(len(opened), 8)
        self.assertEqual(
            tuple(
                Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
                for path, _ in opened
            ),
            CHECKER.EXPECTED_HOLD_PATHS,
        )
        forbidden = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_CREAT
            | os.O_TRUNC
            | os.O_APPEND
        )
        for path, flags in opened:
            with self.subTest(path=path):
                self.assertEqual(flags & forbidden, 0)
                self.assertTrue(flags & os.O_RDONLY == os.O_RDONLY)
                self.assertTrue(flags & os.O_CLOEXEC)

    def test_22_main_success_and_failure_outputs_are_canonical(self) -> None:
        success_stdout = types.SimpleNamespace(buffer=io.BytesIO())
        with (
            mock.patch.object(CHECKER, "run_check", return_value=DECISION),
            mock.patch.object(CHECKER.sys, "stdout", success_stdout),
        ):
            self.assertEqual(CHECKER.main([]), 0)
        self.assertEqual(success_stdout.buffer.getvalue(), DECISION_RAW)

        for error in (
            CHECKER.DecisionCheckFailure("E_TEST"),
            OSError("test"),
        ):
            failure_stdout = types.SimpleNamespace(buffer=io.BytesIO())
            with (
                self.subTest(error=type(error).__name__),
                mock.patch.object(CHECKER, "run_check", side_effect=error),
                mock.patch.object(CHECKER.sys, "stdout", failure_stdout),
            ):
                self.assertEqual(CHECKER.main([]), 1)
            payload = json.loads(failure_stdout.buffer.getvalue())
            self.assertEqual(
                failure_stdout.buffer.getvalue(),
                canonical(payload),
            )
            self.assertEqual(
                set(payload),
                {
                    "checkerId",
                    "error",
                    "externalAuthenticationRequired",
                    "status",
                    "userActionRequired",
                },
            )
            self.assertIs(payload["externalAuthenticationRequired"], False)
            self.assertIs(payload["userActionRequired"], False)
            self.assertEqual(
                payload["status"],
                "wave19_decision_check_failed",
            )

    def test_23_v17_frontier_projection_is_exact_and_mutation_closed(
        self,
    ) -> None:
        projection = CHECKER.expected_v17_frontier_projection()
        self.assertEqual(
            sha256(canonical(projection)),
            V17_FRONTIER_SHA256,
        )
        self.assertEqual(
            projection,
            [
                {
                    "acquisitionAuthorized": False,
                    "module": "golang.org/x/crypto",
                    "requiresSeparateWaveDecision": True,
                    "selectedByGraphAlgorithm": False,
                    "version": "v0.38.0",
                },
                {
                    "acquisitionAuthorized": False,
                    "module": "golang.org/x/text",
                    "requiresSeparateWaveDecision": True,
                    "selectedByGraphAlgorithm": False,
                    "version": "v0.25.0",
                },
            ],
        )
        mutations: list[tuple[dict[str, object], ...]] = []
        changed_version = tuple(copy.deepcopy(row) for row in CHECKER.TUPLES)
        changed_version[0]["version"] = "v0.38.1"
        mutations.append(changed_version)
        reordered = tuple(copy.deepcopy(row) for row in CHECKER.TUPLES)
        mutations.append((reordered[1], reordered[0]))
        changed_module = tuple(copy.deepcopy(row) for row in CHECKER.TUPLES)
        changed_module[1]["module"] = "golang.org/x/text/v2"
        mutations.append(changed_module)
        for index, rows in enumerate(mutations):
            with (
                self.subTest(index=index),
                mock.patch.object(CHECKER, "TUPLES", rows),
                self.assertRaises(CHECKER.DecisionCheckFailure) as caught,
            ):
                CHECKER.expected_v17_frontier_projection()
            self.assertEqual(
                str(caught.exception),
                "E_V17_FRONTIER_PROJECTION",
            )

    def test_24_static_surface_rejects_dynamic_and_write_bypasses(
        self,
    ) -> None:
        baseline = checker_surface_signature(CHECKER_SOURCE)
        self.assertEqual(
            baseline,
            (
                EXPECTED_IMPORT_SURFACE,
                CHECKER_CALL_COUNT,
                CHECKER_CALL_SURFACE_SHA256,
            ),
        )
        mutations = (
            (
                "runpy_v17_dynamic_execution",
                CHECKER_SOURCE.replace(
                    "import stat\n",
                    "import runpy\nimport stat\n",
                    1,
                ).replace(
                    "normalized_v17_bytes(v17_held.raw)",
                    "runpy.run_path(V17_CHECKER_PATH)",
                    1,
                ),
                False,
            ),
            (
                "io_open_write",
                CHECKER_SOURCE.replace(
                    "os.open(self.path, flags)",
                    'io.open(self.path, "wb")',
                    1,
                ),
                True,
            ),
            (
                "os_write",
                CHECKER_SOURCE.replace(
                    "sys.stdout.buffer.write(canonical_json_bytes(decision))",
                    "os.write(1, canonical_json_bytes(decision))",
                    1,
                ),
                True,
            ),
            (
                "path_write_text",
                CHECKER_SOURCE.replace(
                    "self.final_barrier()",
                    'self.path.write_text("forbidden")',
                    1,
                ),
                True,
            ),
        )
        for name, changed, same_imports in mutations:
            with self.subTest(name=name):
                self.assertNotEqual(changed, CHECKER_SOURCE)
                signature = checker_surface_signature(changed)
                self.assertEqual(signature[1], CHECKER_CALL_COUNT)
                if same_imports:
                    self.assertEqual(signature[0], EXPECTED_IMPORT_SURFACE)
                else:
                    self.assertNotEqual(
                        signature[0],
                        EXPECTED_IMPORT_SURFACE,
                    )
                self.assertNotEqual(
                    signature[2],
                    CHECKER_CALL_SURFACE_SHA256,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
