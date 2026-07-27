#!/usr/bin/env python3
"""Focused adversarial tests for the metadata-only Wave17 decision checker."""

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
    raise RuntimeError("Wave17 decision tests require `python3 -I -B -S`")

import ast
import builtins
import copy
import hashlib
import io
import json
import os
from pathlib import Path
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
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_decision_v1.py"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.md"
)
V15_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v15.py"
V15_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v15.py"
NAMESPACE_ANCHOR_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-16-v1.claim"
)
X_TEXT_MOD_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-16-v1/accepted/003-d0a18208476fea968bb8.mod"
)
X_TEXT_ZIP_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-16-v1/accepted/003-d0a18208476fea968bb8.zip"
)

CHECKER_RAW_SHA256 = (
    "564a8f0c3a6dbf9331fe8e02d121efe8c4e91fcd6c5e7415607e0c0b6d9fb256"
)
CHECKER_NORMALIZED_SHA256 = (
    "226cb948492708f50e695c9d5e849c4f0acff11143625f473372c1bb59cec269"
)
CHECKER_CALL_COUNT = 217
CHECKER_CALL_SURFACE_SHA256 = (
    "630670204ad37178ec6aa2235fbd9426bf1073233f8c8a9acf5d8f42ddb4c35d"
)
CHECKER_FULL_AST_SHA256 = (
    "58f680293d8aafb438434041fdf9d5491dd0d4e2ad22af58ae861915b1e75c35"
)
DECISION_RAW_SHA256 = (
    "659e9ce6f079701cab68e337d2746959741ef4868ffff6392fcdbf26ae692f93"
)
DECISION_CONTENT_SHA256 = (
    "867a2ba1a7da54b5466951b1caea9b09eb355d2325a58fa552037047d3fad7df"
)
READER_RAW_SHA256 = (
    "3af49874bd518628971566d6067331c75e2f4fbcf7ac36bafee914938873ef51"
)
V15_CHECKER_RAW_SHA256 = (
    "e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5"
)
V15_CHECKER_NORMALIZED_SHA256 = (
    "63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7"
)
V15_TESTS_RAW_SHA256 = (
    "65d7f435cef11da2cccae7e31a3c410d7a3038f6bc3261552753801a0de431b1"
)
V15_CANDIDATE_CONTENT_SHA256 = (
    "4666c802e40734bb1b5b91489eb24aa782cb346710caec9605be4e0e005553ee"
)
V15_GRAPH_SHA256 = (
    "ffe9f910669401198b88752663055ca2e6622d19e171f2d20a2b303d06c989d7"
)
V15_FRONTIER_SHA256 = (
    "ce1be1152aabf580a211f038d80aeaf9249418117b7d12ff26ffc909f1e4d593"
)
V15_INPUT_SET_SHA256 = (
    "4b12b7ca7f0a8b1556c692522e8832af033f9d2a1f00fbeb7469623a00541f1e"
)
V15_SOURCE_BINDINGS_SHA256 = (
    "86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd"
)
NAMESPACE_ANCHOR_RAW_SHA256 = (
    "df97f5d9bf8c56f3bbf08635b8332bbc18b25babd0e5f35742fee3657555f4b8"
)
X_TEXT_MOD_RAW_SHA256 = (
    "178b8e330288183eabcb6e776a3f01099b5926661fc866b750acec7cb8402dc2"
)
X_TEXT_ZIP_RAW_SHA256 = (
    "c524f4ace2e1f35b75d9e6177b1597cf31736c81064df5978a4d61300d7626c8"
)

MODULE = "golang.org/x/tools"
VERSION = "v0.33.0"
GO_MOD_H1 = "h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI="
MODULE_ZIP_H1 = "h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc="
TUPLE_DIGEST = (
    "8bd04ea612cec978713135c7452cb52e20350f82cd8b2a17691e3c431b43973c"
)
COMPACT_IDENTITY_SHA256 = (
    "813ac6030c903b716fb5f68852468a53ebb0bcfe60c7c11582d2f2ffb18041ca"
)
FULL_WITNESS_SHA256 = (
    "ee3f4b0e1072a8bc0e1eb6e53b83fe8d749fdfd8c13bec54c60774dc3755dc54"
)
REQUEST_SET_SHA256 = (
    "acf64af2352fb4d82325f3e5bd2a3e913b8ef95db553fa0015bc71a239f3fb35"
)
GO_SUM_ENTRY = "golang.org/x/text@v0.26.0/go.sum"
CHECKER_ID = "g2-pion-ice-v4.3.0-wave17-identity-acquisition-decision-check-v1"

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

EXPECTED_AUTHORITY = {
    "acquisitionAuthorityGranted": False,
    "authenticationRequired": False,
    "compileAuthorized": False,
    "decisionAuthorityGranted": False,
    "dependencySourceExecutionAuthorized": False,
    "deploymentAuthorized": False,
    "deviceInteractionRequired": False,
    "dnsAuthorized": False,
    "executionAuthorityGranted": False,
    "externalAuthenticationRequired": False,
    "fileWriteAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "gitWriteAuthorized": False,
    "networkAuthorized": False,
    "ownerProofRequired": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "productRuntimeNetworkAuthorized": False,
    "publicationAuthorityGranted": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}

EXPECTED_CLOSURE = {
    "candidateSelected": False,
    "dependencyClosureComplete": False,
    "dependencyFixedPointReached": False,
    "librarySelected": False,
    "releaseReady": False,
    "rungThreeComplete": False,
    "semanticClosureComplete": False,
    "wave17AcquisitionComplete": False,
    "wave17AcquisitionReady": True,
    "wave17IdentityResolved": True,
}

EXPECTED_COUNTERS = {
    "archiveExtractionCount": 0,
    "authenticationOperationCount": 0,
    "combinedV15CandidateInvocationCount": 0,
    "dependencySourceCompileCount": 0,
    "dependencySourceExecutionCount": 0,
    "dependencySourceLoadCount": 0,
    "dependencySourceReconstructionCount": 0,
    "fileWriteCount": 0,
    "metadataArchiveOpenCount": 2,
    "metadataScanCount": 2,
    "namespaceSnapshotCount": 2,
    "networkOperationCount": 0,
    "predecessorFullSourceReconstructionCount": 28,
    "predecessorGraphArchiveOpenCount": 3696,
    "productRuntimeNetworkOperationCount": 0,
    "socketOperationCount": 0,
    "subprocessCount": 0,
}

EXPECTED_NON_CLAIMS = [
    "retained_go_sum_h1_is_not_fresh_checksum_database_inclusion_proof",
    "wave17_dependency_source_not_acquired",
    "dependency_source_not_extracted_loaded_executed_or_compiled",
    "combined_v15_not_executed_by_this_checker",
    "dependency_source_not_reconstructed_by_this_checker",
    "dependency_fixed_point_not_reached",
    "dependency_and_semantic_closure_not_complete",
    "candidate_and_library_not_selected",
    "release_not_ready",
    (
        "namespace_check_is_point_in_time_only_and_does_not_prevent_"
        "same_uid_concurrent_replacement"
    ),
]


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


def compact(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def independent_normalized_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    if raw.count(marker) != 1:
        raise AssertionError("normalization marker count")
    start = raw.index(marker) + len(marker)
    end = raw.find(b'"\n)', start)
    payload = raw[start:end]
    if (
        len(payload) != 64
        or any(character not in b"0123456789abcdef" for character in payload)
    ):
        raise AssertionError("normalization marker payload")
    return raw[:start] + b"0" * 64 + raw[end:]


def load_checker(raw: bytes) -> types.ModuleType:
    module = types.ModuleType("wave17_decision_checker_test_subject")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / CHECKER_PATH),
            "__loader__": None,
            "__name__": "wave17_decision_checker_test_subject",
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


def independent_identity_row() -> dict[str, object]:
    return {
        "acquisitionAuthorized": False,
        "acquisitionReady": True,
        "goModH1": GO_MOD_H1,
        "goModH1WitnessCount": 1,
        "identityConflict": False,
        "identityPairComplete": True,
        "module": MODULE,
        "moduleZipH1": MODULE_ZIP_H1,
        "moduleZipH1WitnessCount": 1,
        "parentDeclarationComplete": True,
        "parentDeclarationCount": 1,
        "selectedByGraphAlgorithm": False,
        "tupleOrder": 1,
        "version": VERSION,
    }


def independent_request_set() -> list[dict[str, object]]:
    common = {
        "acquisitionAuthorized": False,
        "authenticationRequired": False,
        "host": "proxy.golang.org",
        "method": "GET",
        "module": MODULE,
        "networkAuthorized": False,
        "selectedByGraphAlgorithm": False,
        "tupleOrder": 1,
        "version": VERSION,
    }
    return [
        {
            **common,
            "acceptedFileName": f"001-{TUPLE_DIGEST[:20]}.mod",
            "expectedH1": GO_MOD_H1,
            "maximumResponseBytes": 1_048_576,
            "requestOrdinal": 1,
            "resourceKind": "mod",
            "url": (
                "https://proxy.golang.org/golang.org/x/tools/"
                "@v/v0.33.0.mod"
            ),
        },
        {
            **common,
            "acceptedFileName": f"001-{TUPLE_DIGEST[:20]}.zip",
            "expectedH1": MODULE_ZIP_H1,
            "maximumResponseBytes": 16_777_216,
            "requestOrdinal": 2,
            "resourceKind": "zip",
            "url": (
                "https://proxy.golang.org/golang.org/x/tools/"
                "@v/v0.33.0.zip"
            ),
        },
    ]


def independent_full_witness() -> dict[str, object]:
    return {
        "goModH1": {
            "line": f"{MODULE} {VERSION}/go.mod {GO_MOD_H1}",
            "path": GO_SUM_ENTRY,
            "retainedArchivePath": X_TEXT_ZIP_PATH,
            "witnessCount": 1,
        },
        "moduleZipH1": {
            "line": f"{MODULE} {VERSION} {MODULE_ZIP_H1}",
            "path": GO_SUM_ENTRY,
            "retainedArchivePath": X_TEXT_ZIP_PATH,
            "witnessCount": 1,
        },
        "parentDeclaration": {
            "line": f"require {MODULE} {VERSION} // tagx:ignore",
            "retainedModPath": X_TEXT_MOD_PATH,
            "witnessCount": 1,
        },
    }


def rebind(decision: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(decision)
    without = dict(changed)
    without.pop("contentBinding", None)
    changed["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization":
            "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256(canonical(without)),
    }
    return changed


def make_zip(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(
            output,
            mode="w",
            compression=zipfile.ZIP_STORED,
        ) as archive:
            for name, raw in entries:
                archive.writestr(name, raw)
    return output.getvalue()


def valid_metadata() -> tuple[bytes, bytes]:
    mod_raw = (
        f"module golang.org/x/text\n\n"
        f"require {MODULE} {VERSION} // tagx:ignore\n"
    ).encode("utf-8")
    go_sum = (
        f"{MODULE} {VERSION} {MODULE_ZIP_H1}\n"
        f"{MODULE} {VERSION}/go.mod {GO_MOD_H1}\n"
    ).encode("utf-8")
    return mod_raw, make_zip([(GO_SUM_ENTRY, go_sum)])


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


class CallVisitor(ast.NodeVisitor):
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


def full_ast_sha256(tree: ast.AST) -> str:
    normalized = copy.deepcopy(tree)
    count = 0
    for node in normalized.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "SELF_NORMALIZED_SHA256"
        ):
            continue
        if not (
            isinstance(node.value, ast.Constant)
            and type(node.value.value) is str
            and len(node.value.value) == 64
        ):
            raise AssertionError("full AST normalization payload")
        count += 1
        node.value = ast.Constant(
            value="<normalized-self-normalized-sha256>"
        )
    if count != 1:
        raise AssertionError("full AST normalization count")
    return sha256(
        ast.dump(
            normalized,
            annotate_fields=True,
            include_attributes=False,
        ).encode("utf-8")
        + b"\n"
    )


CHECKER_RAW = (ROOT / CHECKER_PATH).read_bytes()
CHECKER_SOURCE = CHECKER_RAW.decode("utf-8", errors="strict")
CHECKER_TREE = ast.parse(CHECKER_SOURCE, filename=CHECKER_PATH)
CHECKER = load_checker(CHECKER_RAW)
DECISION_RAW = (ROOT / DECISION_PATH).read_bytes()
DECISION = json.loads(DECISION_RAW)


class Wave17DecisionTests(unittest.TestCase):
    maxDiff = None

    def assert_decision_failure(
        self,
        changed: dict[str, object],
        code: str,
        *,
        bind: bool = True,
    ) -> None:
        candidate = rebind(changed) if bind else changed
        with self.assertRaisesRegex(
            CHECKER.DecisionCheckFailure,
            f"^{code}$",
        ):
            CHECKER.validate_decision(candidate, namespace_clean=True)

    def test_01_static_checker_surface_is_exact_and_read_only(self) -> None:
        self.assertEqual(sha256(CHECKER_RAW), CHECKER_RAW_SHA256)
        self.assertEqual(
            sha256(independent_normalized_bytes(CHECKER_RAW)),
            CHECKER_NORMALIZED_SHA256,
        )
        self.assertEqual(
            static_import_surface(CHECKER_TREE),
            EXPECTED_IMPORT_SURFACE,
        )
        visitor = CallVisitor()
        visitor.visit(CHECKER_TREE)
        self.assertEqual(len(visitor.calls), CHECKER_CALL_COUNT)
        self.assertEqual(
            call_surface_sha256(visitor.calls),
            CHECKER_CALL_SURFACE_SHA256,
        )
        self.assertEqual(
            full_ast_sha256(CHECKER_TREE),
            CHECKER_FULL_AST_SHA256,
        )

        sensitive_roots = {
            "asyncio",
            "ctypes",
            "getpass",
            "http",
            "importlib",
            "keyring",
            "multiprocessing",
            "requests",
            "socket",
            "ssl",
            "subprocess",
            "urllib",
        }
        for row in EXPECTED_IMPORT_SURFACE:
            names = (
                (row[1],)
                if row[0] == "from"
                else tuple(name for name, _ in row[1])
            )
            self.assertTrue(
                sensitive_roots.isdisjoint(
                    name.split(".", 1)[0] for name in names if name
                )
            )

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
            "hardlink_to",
            "link",
            "listen",
            "makedirs",
            "mkdir",
            "popen",
            "posix_spawn",
            "posix_spawnp",
            "remove",
            "removedirs",
            "rename",
            "renames",
            "replace",
            "rmdir",
            "send",
            "sendall",
            "sendto",
            "socket",
            "symlink",
            "symlink_to",
            "system",
            "touch",
            "truncate",
            "unlink",
            "urlopen",
            "write_bytes",
            "write_text",
            "writelines",
        }
        os_open_count = 0
        stdout_write_count = 0
        for _, _, scope, call in visitor.calls:
            dotted = dotted_name(call.func)
            if isinstance(call.func, ast.Name):
                self.assertNotIn(call.func.id, forbidden_names)
            if isinstance(call.func, ast.Attribute):
                self.assertNotIn(call.func.attr, forbidden_attributes)
            if dotted == "os.open":
                os_open_count += 1
                self.assertEqual(scope, "HeldFile.__init__")
                self.assertGreaterEqual(len(call.args), 2)
                self.assertIsInstance(call.args[1], ast.Name)
                self.assertEqual(call.args[1].id, "flags")
            if dotted == "sys.stdout.buffer.write":
                stdout_write_count += 1
        self.assertEqual(os_open_count, 1)
        self.assertEqual(stdout_write_count, 2)
        flag_values = [
            node.value
            for node in ast.walk(CHECKER_TREE)
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "flags"
                and "O_RDONLY" in ast.dump(
                    node.value,
                    include_attributes=False,
                )
            )
        ]
        self.assertEqual(len(flag_values), 1)
        flags = ast.dump(flag_values[0], include_attributes=False)
        self.assertIn("O_RDONLY", flags)
        for forbidden_flag in (
            "O_APPEND",
            "O_CREAT",
            "O_EXCL",
            "O_RDWR",
            "O_TRUNC",
            "O_WRONLY",
        ):
            self.assertNotIn(forbidden_flag, flags)

    def test_02_repository_seals_and_content_binding_are_exact(self) -> None:
        expected = {
            CHECKER_PATH: CHECKER_RAW_SHA256,
            DECISION_PATH: DECISION_RAW_SHA256,
            READER_PATH: READER_RAW_SHA256,
            V15_CHECKER_PATH: V15_CHECKER_RAW_SHA256,
            V15_TESTS_PATH: V15_TESTS_RAW_SHA256,
            NAMESPACE_ANCHOR_PATH: NAMESPACE_ANCHOR_RAW_SHA256,
            X_TEXT_MOD_PATH: X_TEXT_MOD_RAW_SHA256,
            X_TEXT_ZIP_PATH: X_TEXT_ZIP_RAW_SHA256,
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(sha256((ROOT / path).read_bytes()), digest)
        self.assertEqual(DECISION_RAW, canonical(DECISION))
        without = dict(DECISION)
        binding = without.pop("contentBinding")
        self.assertEqual(sha256(canonical(without)), DECISION_CONTENT_SHA256)
        self.assertEqual(
            binding,
            {
                "algorithm": "sha256",
                "canonicalization":
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf",
                "scope": "decision_without_contentBinding",
                "sha256": DECISION_CONTENT_SHA256,
            },
        )
        v15_raw = (ROOT / V15_CHECKER_PATH).read_bytes()
        self.assertEqual(
            sha256(independent_normalized_bytes(v15_raw)),
            V15_CHECKER_NORMALIZED_SHA256,
        )

    def test_03_exact_identity_and_request_contract(self) -> None:
        self.assertEqual(
            sha256(f"{MODULE}\n{VERSION}\n".encode("utf-8")),
            TUPLE_DIGEST,
        )
        identity = DECISION["identityResolution"]
        self.assertEqual(identity["tuples"], [independent_identity_row()])
        self.assertFalse(identity["tuples"][0]["selectedByGraphAlgorithm"])
        self.assertEqual(identity["graphSelectedTupleCount"], 0)
        self.assertEqual(identity["versionSpecificNonSelectedTupleCount"], 1)
        self.assertEqual(identity["compactIdentitySha256"], COMPACT_IDENTITY_SHA256)
        compact_identity = [
            {
                "goModH1": GO_MOD_H1,
                "module": MODULE,
                "moduleZipH1": MODULE_ZIP_H1,
                "selectedByGraphAlgorithm": False,
                "version": VERSION,
            }
        ]
        self.assertEqual(
            sha256(compact(compact_identity)),
            COMPACT_IDENTITY_SHA256,
        )
        self.assertEqual(
            sha256(compact(independent_full_witness())),
            FULL_WITNESS_SHA256,
        )
        self.assertEqual(identity["fullWitnessSha256"], FULL_WITNESS_SHA256)

        acquisition = DECISION["sourceAcquisitionPreparation"]
        requests = independent_request_set()
        self.assertEqual(acquisition["requestSet"], requests)
        self.assertEqual(acquisition["requestCount"], 2)
        self.assertEqual(
            sha256(compact(requests)),
            REQUEST_SET_SHA256,
        )
        self.assertEqual(
            acquisition["requestSetCanonicalSha256"],
            REQUEST_SET_SHA256,
        )
        self.assertEqual(
            [row["resourceKind"] for row in requests],
            ["mod", "zip"],
        )
        self.assertEqual(
            [row["requestOrdinal"] for row in requests],
            [1, 2],
        )
        for row in requests:
            self.assertEqual(row["method"], "GET")
            self.assertEqual(row["host"], "proxy.golang.org")
            self.assertFalse(row["selectedByGraphAlgorithm"])
            self.assertFalse(row["authenticationRequired"])
            self.assertFalse(row["networkAuthorized"])
            self.assertFalse(row["acquisitionAuthorized"])

    def test_04_authority_and_operation_boundaries_are_all_explicit(self) -> None:
        self.assertEqual(DECISION["authority"], EXPECTED_AUTHORITY)
        self.assertTrue(EXPECTED_AUTHORITY)
        for name, value in EXPECTED_AUTHORITY.items():
            with self.subTest(authority=name):
                self.assertIs(value, False)
        for name in (
            "acquisitionAuthorityGranted",
            "authenticationRequired",
            "compileAuthorized",
            "deploymentAuthorized",
            "dependencySourceExecutionAuthorized",
            "deviceInteractionRequired",
            "externalAuthenticationRequired",
            "fileWriteAuthorized",
            "filesystemExtractionAuthorized",
            "networkAuthorized",
            "ownerProofRequired",
            "packageManagerAuthorized",
            "productRuntimeNetworkAuthorized",
            "sourceExtractionAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "userActionRequired",
        ):
            self.assertIs(DECISION["authority"][name], False)

        self.assertEqual(DECISION["operationCounters"], EXPECTED_COUNTERS)
        zero_counters = {
            "archiveExtractionCount",
            "authenticationOperationCount",
            "combinedV15CandidateInvocationCount",
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
        for name in zero_counters:
            with self.subTest(counter=name):
                self.assertIs(type(DECISION["operationCounters"][name]), int)
                self.assertEqual(DECISION["operationCounters"][name], 0)
        self.assertEqual(DECISION["closure"], EXPECTED_CLOSURE)
        self.assertFalse(DECISION["closure"]["wave17AcquisitionComplete"])
        self.assertTrue(DECISION["closure"]["wave17AcquisitionReady"])

    def test_05_v15_lineage_and_reader_bindings_are_exact(self) -> None:
        self.assertEqual(
            DECISION["predecessorBindings"],
            {
                "combinedFixedPointV15": {
                    "checkerNormalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
                    "checkerPath": V15_CHECKER_PATH,
                    "checkerRawSha256": V15_CHECKER_RAW_SHA256,
                    "combinedInputSetSha256": V15_INPUT_SET_SHA256,
                    "contentSha256": V15_CANDIDATE_CONTENT_SHA256,
                    "fixedPointReached": False,
                    "frontierSha256": V15_FRONTIER_SHA256,
                    "frontierTupleCount": 1,
                    "graphSha256": V15_GRAPH_SHA256,
                    "sourceBindingCount": 357,
                    "sourceBindingsSha256": V15_SOURCE_BINDINGS_SHA256,
                    "testsPath": V15_TESTS_PATH,
                    "testsRawSha256": V15_TESTS_RAW_SHA256,
                    "totalFullSourceReconstructionCount": 28,
                    "totalGraphArchiveOpenCount": 3696,
                    "wave16NamespaceAnchor": {
                        "path": NAMESPACE_ANCHOR_PATH,
                        "rawSha256": NAMESPACE_ANCHOR_RAW_SHA256,
                    },
                }
            },
        )
        self.assertEqual(
            DECISION["readerDocumentBinding"],
            {"path": READER_PATH, "rawSha256": READER_RAW_SHA256},
        )
        self.assertEqual(
            DECISION["toolBindings"],
            [
                {
                    "normalizedSha256": CHECKER_NORMALIZED_SHA256,
                    "path": CHECKER_PATH,
                    "role": "current_wave17_decision_checker",
                },
                {
                    "normalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
                    "path": V15_CHECKER_PATH,
                    "rawSha256": V15_CHECKER_RAW_SHA256,
                    "role": "immutable_combined_v15_checker",
                },
                {
                    "path": V15_TESTS_PATH,
                    "rawSha256": V15_TESTS_RAW_SHA256,
                    "role": "immutable_combined_v15_tests",
                },
            ],
        )

    def test_06_retained_metadata_binding_is_exact(self) -> None:
        self.assertEqual(
            DECISION["retainedMetadataEvidence"],
            {
                "allEvidenceInputsReadTwice": True,
                "goSumEntryPath": GO_SUM_ENTRY,
                "metadataScanCount": 2,
                "retainedModPath": X_TEXT_MOD_PATH,
                "retainedModRawSha256": X_TEXT_MOD_RAW_SHA256,
                "retainedZipPath": X_TEXT_ZIP_PATH,
                "retainedZipRawSha256": X_TEXT_ZIP_RAW_SHA256,
                "sourceCodeInspected": False,
                "sourceReconstructionPerformed": False,
            },
        )
        self.assertEqual(DECISION["nonClaims"], EXPECTED_NON_CLAIMS)

    def test_07_strict_json_rejects_non_json_numbers_and_encoding(self) -> None:
        self.assertEqual(
            CHECKER.strict_json(DECISION_RAW, DECISION_PATH),
            DECISION,
        )
        rejected = (
            (b'{"value":1.0}\n', f"E_JSON:{DECISION_PATH}"),
            (b'{"value":NaN}\n', f"E_JSON:{DECISION_PATH}"),
            (b'{"value":Infinity}\n', f"E_JSON:{DECISION_PATH}"),
            (b'{"value":-Infinity}\n', f"E_JSON:{DECISION_PATH}"),
            (b"\xff", f"E_JSON:{DECISION_PATH}"),
            (b"[]\n", f"E_JSON:{DECISION_PATH}"),
            (b'{"x":1,"x":1}\n', f"E_CANONICAL_JSON:{DECISION_PATH}"),
            (b'{ "x": 1 }\n', f"E_CANONICAL_JSON:{DECISION_PATH}"),
            (b'{"x":1}', f"E_CANONICAL_JSON:{DECISION_PATH}"),
        )
        for raw, code in rejected:
            with (
                self.subTest(raw=raw),
                self.assertRaisesRegex(
                    CHECKER.DecisionCheckFailure,
                    f"^{code}$",
                ),
            ):
                CHECKER.strict_json(raw, DECISION_PATH)

    def test_08_h1_validation_is_exact(self) -> None:
        CHECKER.validate_h1(GO_MOD_H1)
        CHECKER.validate_h1(MODULE_ZIP_H1)
        for value in (
            None,
            b"h1:",
            "",
            "sha256:AAAA",
            "h1:",
            "h1:not-base64!",
            "h1:AA==",
            "h1:" + ("A" * 44),
        ):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(
                    CHECKER.DecisionCheckFailure,
                    "^E_H1$",
                ),
            ):
                CHECKER.validate_h1(value)

    def test_09_metadata_scanner_reproduces_only_the_exact_witness(self) -> None:
        mod_raw, zip_raw = valid_metadata()
        self.assertEqual(
            CHECKER.scan_retained_metadata(mod_raw, zip_raw),
            independent_full_witness(),
        )

    def test_10_metadata_scanner_rejects_declaration_mutations(self) -> None:
        _, zip_raw = valid_metadata()
        declaration = f"require {MODULE} {VERSION} // tagx:ignore\n"
        mutations = (
            b"module golang.org/x/text\n",
            (declaration + declaration).encode("utf-8"),
            declaration.replace("// tagx:ignore", "").encode("utf-8"),
            b"\xff",
        )
        for mod_raw in mutations:
            with (
                self.subTest(mod_raw=mod_raw),
                self.assertRaisesRegex(
                    CHECKER.DecisionCheckFailure,
                    "^E_METADATA$",
                ),
            ):
                CHECKER.scan_retained_metadata(mod_raw, zip_raw)

    def test_11_metadata_scanner_rejects_zip_and_go_sum_mutations(self) -> None:
        mod_raw, _ = valid_metadata()
        zip_line = f"{MODULE} {VERSION} {MODULE_ZIP_H1}\n"
        mod_line = f"{MODULE} {VERSION}/go.mod {GO_MOD_H1}\n"
        valid_sum = (zip_line + mod_line).encode("utf-8")
        mutations = (
            b"not-a-zip",
            make_zip([("other/go.sum", valid_sum)]),
            make_zip([(GO_SUM_ENTRY, b"\xff")]),
            make_zip([(GO_SUM_ENTRY, mod_line.encode("utf-8"))]),
            make_zip([(GO_SUM_ENTRY, zip_line.encode("utf-8"))]),
            make_zip([(GO_SUM_ENTRY, (zip_line + zip_line + mod_line).encode())]),
            make_zip([(GO_SUM_ENTRY, (zip_line + mod_line + mod_line).encode())]),
            make_zip(
                [
                    (GO_SUM_ENTRY, valid_sum),
                    (GO_SUM_ENTRY, valid_sum),
                ]
            ),
        )
        for index, zip_raw in enumerate(mutations):
            with (
                self.subTest(mutation=index),
                self.assertRaisesRegex(
                    CHECKER.DecisionCheckFailure,
                    "^E_METADATA$",
                ),
            ):
                CHECKER.scan_retained_metadata(mod_raw, zip_raw)

    def test_12_namespace_snapshot_rejects_claim_accepted_and_staging(self) -> None:
        with mock.patch.object(
            CHECKER.os,
            "listdir",
            return_value=["z", ".wave-16-v1.claim", "a"],
        ):
            self.assertEqual(
                CHECKER.namespace_snapshot(ROOT),
                (".wave-16-v1.claim", "a", "z"),
            )
        for name in (
            ".wave-17-v1.claim",
            "wave-17-v1",
            ".wave-17-v1-staging-test",
        ):
            with (
                self.subTest(name=name),
                mock.patch.object(CHECKER.os, "listdir", return_value=[name]),
                self.assertRaisesRegex(
                    CHECKER.DecisionCheckFailure,
                    "^E_NAMESPACE$",
                ),
            ):
                CHECKER.namespace_snapshot(ROOT)
        with (
            mock.patch.object(
                CHECKER.os,
                "listdir",
                side_effect=OSError("test"),
            ),
            self.assertRaisesRegex(
                CHECKER.DecisionCheckFailure,
                "^E_NAMESPACE$",
            ),
        ):
            CHECKER.namespace_snapshot(ROOT)

    def test_13_materialized_decision_passes_exact_validation(self) -> None:
        CHECKER.validate_decision(DECISION, namespace_clean=True)
        self.assertEqual(
            DECISION["status"],
            (
                "wave17_exact_1_frontier_identity_classified_1_complete_"
                "0_blocked_acquisition_ready_not_authorized"
            ),
        )
        self.assertEqual(
            DECISION["result"],
            (
                "exact_1_version_vertex_0_selected_1_nonselected_"
                "1_complete_h1_pair_acquisition_ready_not_authorized"
            ),
        )
        self.assertEqual(
            DECISION["nextAction"],
            "independent_review_of_wave17_decision_package",
        )

    def test_14_each_validation_section_fails_with_its_own_code(self) -> None:
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
                    "combinedFixedPointV15"
                ].__setitem__("sourceBindingCount", 358),
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
                    "proxyHost",
                    "example.invalid",
                ),
            ),
            (
                "E_CLOSURE",
                lambda value: value["closure"].__setitem__("releaseReady", True),
            ),
            (
                "E_COUNTERS",
                lambda value: value["operationCounters"].__setitem__(
                    "networkOperationCount",
                    1,
                ),
            ),
            (
                "E_RESULT",
                lambda value: value.__setitem__("status", "invented"),
            ),
            (
                "E_BINDINGS",
                lambda value: value["readerDocumentBinding"].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
            ),
            (
                "E_METADATA_BINDING",
                lambda value: value["retainedMetadataEvidence"].__setitem__(
                    "sourceCodeInspected",
                    True,
                ),
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
            bind=False,
        )

    def test_15_unknown_keys_fail_closed_at_every_nested_boundary(self) -> None:
        cases: list[tuple[str, object]] = [
            ("E_TOP_LEVEL_KEYS", lambda value: value.__setitem__("extra", False)),
            (
                "E_AUTHORITY",
                lambda value: value["authority"].__setitem__("extra", False),
            ),
            (
                "E_PREDECESSOR",
                lambda value: value["predecessorBindings"][
                    "combinedFixedPointV15"
                ].__setitem__("extra", False),
            ),
            (
                "E_IDENTITY",
                lambda value: value["identityResolution"].__setitem__(
                    "extra",
                    False,
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
                "E_BINDINGS",
                lambda value: value["readerDocumentBinding"].__setitem__(
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
            (
                "E_METADATA_BINDING",
                lambda value: value["retainedMetadataEvidence"].__setitem__(
                    "extra",
                    False,
                ),
            ),
        ]
        for index, (code, mutate) in enumerate(cases):
            changed = copy.deepcopy(DECISION)
            mutate(changed)
            with self.subTest(index=index, code=code):
                self.assert_decision_failure(changed, code)

    def test_16_bool_integer_and_float_aliases_fail_closed(self) -> None:
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
                    "combinedFixedPointV15"
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
                "E_IDENTITY",
                lambda value: value["identityResolution"]["tuples"][0].__setitem__(
                    "tupleOrder",
                    1.0,
                ),
            ),
            (
                "E_ACQUISITION",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ][0].__setitem__("requestOrdinal", True),
            ),
            (
                "E_CLOSURE",
                lambda value: value["closure"].__setitem__(
                    "wave17AcquisitionReady",
                    1,
                ),
            ),
            (
                "E_COUNTERS",
                lambda value: value["operationCounters"].__setitem__(
                    "metadataScanCount",
                    True,
                ),
            ),
            (
                "E_METADATA_BINDING",
                lambda value: value["retainedMetadataEvidence"].__setitem__(
                    "metadataScanCount",
                    True,
                ),
            ),
        ]
        for index, (code, mutate) in enumerate(cases):
            changed = copy.deepcopy(DECISION)
            mutate(changed)
            with self.subTest(index=index, code=code):
                self.assert_decision_failure(changed, code)

    def test_17_identity_and_request_list_shape_mutations_fail_closed(self) -> None:
        identity_mutations = (
            lambda rows: rows.clear(),
            lambda rows: rows.append(copy.deepcopy(rows[0])),
            lambda rows: rows[0].__setitem__("module", "example.invalid"),
            lambda rows: rows[0].pop("goModH1"),
        )
        for index, mutate in enumerate(identity_mutations):
            changed = copy.deepcopy(DECISION)
            mutate(changed["identityResolution"]["tuples"])
            with self.subTest(kind="identity", index=index):
                self.assert_decision_failure(changed, "E_IDENTITY")

        request_mutations = (
            lambda rows: rows.clear(),
            lambda rows: rows.reverse(),
            lambda rows: rows.append(copy.deepcopy(rows[0])),
            lambda rows: rows[0].__setitem__("method", "POST"),
            lambda rows: rows[0].pop("expectedH1"),
        )
        for index, mutate in enumerate(request_mutations):
            changed = copy.deepcopy(DECISION)
            mutate(changed["sourceAcquisitionPreparation"]["requestSet"])
            with self.subTest(kind="request", index=index):
                self.assert_decision_failure(changed, "E_ACQUISITION")

    def test_18_namespace_clean_argument_is_bound_exactly(self) -> None:
        CHECKER.validate_decision(DECISION, namespace_clean=True)
        with self.assertRaisesRegex(
            CHECKER.DecisionCheckFailure,
            "^E_ACQUISITION$",
        ):
            CHECKER.validate_decision(DECISION, namespace_clean=False)
        with self.assertRaisesRegex(
            CHECKER.DecisionCheckFailure,
            "^E_ACQUISITION$",
        ):
            CHECKER.validate_decision(DECISION, namespace_clean=1)

    def test_19_live_run_check_is_bounded_metadata_only(self) -> None:
        real_open = os.open
        opened: list[tuple[object, int]] = []

        def observed_open(path: object, flags: int, *args: object) -> int:
            opened.append((path, flags))
            return real_open(path, flags, *args)

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
        forbidden_mask = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_CREAT
            | os.O_TRUNC
            | os.O_APPEND
        )
        for path, flags in opened:
            with self.subTest(path=path):
                self.assertEqual(flags & forbidden_mask, 0)
                self.assertTrue(flags & os.O_CLOEXEC)

    def test_20_main_success_and_failure_outputs_are_canonical(self) -> None:
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
            self.assertEqual(payload["checkerId"], CHECKER_ID)
            self.assertEqual(payload["status"], "wave17_decision_check_failed")
            self.assertIs(payload["externalAuthenticationRequired"], False)
            self.assertIs(payload["userActionRequired"], False)
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


if __name__ == "__main__":
    unittest.main()
