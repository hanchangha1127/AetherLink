#!/usr/bin/env python3
"""Focused tests for the exact read-only 325-input combined v11 checker."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
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
            "combined fixed-point v11 tests require unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import ast
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_combined_fixed_point_v11.py"


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "combined_fixed_point_v11_tests_target",
        CHECKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("checker load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()

EXPECTED_SELF_NORMALIZED_SHA256 = (
    "1ef7c9fb874c33b8b25c02f0024e6d85e3df070718c0de9861c60173697af82e"
)
EXPECTED_CLOSED_AUTHORITY = {
    "decisionAuthorityGranted": False,
    "executionAuthorityGranted": False,
    "acquisitionAuthorityGranted": False,
    "publicationAuthorityGranted": False,
    "networkAuthorized": False,
    "sourceExecutionAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "subprocessAuthorized": False,
    "fileWriteAuthorized": False,
    "gitWriteAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "externalAuthenticationRequired": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "signatureRequired": False,
    "tokenRequired": False,
    "userActionRequired": False,
    "osSyscallSandboxProvided": False,
}
EXPECTED_TOOL_BINDINGS = [
    {
        "role": "current_v11_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v11.py",
        "normalizedSha256": EXPECTED_SELF_NORMALIZED_SHA256,
    },
    {
        "role": "immutable_v10_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py",
        "rawSha256":
            "11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985",
        "normalizedSha256":
            "ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751",
    },
    {
        "role": "immutable_v9_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v9.py",
        "rawSha256":
            "c0f098cf0a047c4d1aca03f5b7f16f327306b56ed8e656d67afe32503eb117da",
        "normalizedSha256":
            "b4cdbfd385e0606fa2ca37017983bd80b6856dd69dfafb46df6579e76c618684",
    },
    {
        "role": "immutable_v8_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v8.py",
        "rawSha256":
            "798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32",
        "normalizedSha256":
            "cfd83cdd00b6daee857cbff915ec48fd78390bbf06098ccab963a54e8748ba4b",
    },
    {
        "role": "immutable_v7_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v7.py",
        "rawSha256":
            "7264d85e1948bc8f86e8238192663706e7bf7472153d37fe812bd118620e99c7",
        "normalizedSha256":
            "cf4fd9d25efe04c2ecb3eea882bb24d6c40b02f2f258c4ab01d824d1373d1c02",
    },
    {
        "role": "immutable_v6_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v6.py",
        "rawSha256":
            "eee3d6bd5ec0857bc4832895f4c2d463b608ffc0a59436ebc2cde507cd9750e4",
        "normalizedSha256":
            "3f2a9866a185d157ab4fca021b52bc55aecac914fd5a08003e2f2f34e9522eef",
    },
    {
        "role": "immutable_v5_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v5.py",
        "rawSha256":
            "b63047c6867175655cf95710767dd930783dae5d99883dfb731aedeb59459e92",
        "normalizedSha256":
            "63587ee84ebe68aeb579c1bf85478e3c818ceaeaa8770e499d36b05ee41fe1aa",
    },
    {
        "role": "immutable_v4_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v4.py",
        "rawSha256":
            "2576f7d2e0f0c8dffd2f4956254af3f62b39fdabb25b793242315f50b1373a52",
    },
    {
        "role": "immutable_v1_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py",
        "rawSha256":
            "b11047fd74e8ba4b41d66590975270921a5835bf444ad2e942af357d56764f15",
    },
    {
        "role": "immutable_wave1_graph_provider",
        "path":
            "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py",
        "rawSha256":
            "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3",
    },
]
EXPECTED_WAVE12_RESOURCE_IDENTITY = [
    (
        1, 159, "mod", "golang.org/x/crypto", "v0.41.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/001-799bf8d6fecbf233990b.mod",
        "e4fd109052ee9be5365272aa1744f592f57c031179e887d1b56ff07509c1ac77",
    ),
    (
        2, 159, "zip", "golang.org/x/crypto", "v0.41.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/001-799bf8d6fecbf233990b.zip",
        "7da981b09d79d021f79ea2953637a85e3c72e43fc88b6a3230e7976fbbeec2de",
    ),
    (
        3, 160, "mod", "golang.org/x/term", "v0.34.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/002-770419a13c10bfa04a33.mod",
        "a5ff80baa7f2639db9ed9df46ef6ce29fd1ab1b4275e9b8a6856aa9b8ecde27a",
    ),
    (
        4, 160, "zip", "golang.org/x/term", "v0.34.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/002-770419a13c10bfa04a33.zip",
        "22281cbf30560433d57de8d72c1151f9cac2917795dc6e9f694f7a525bb5309c",
    ),
    (
        5, 161, "mod", "golang.org/x/text", "v0.28.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/003-c1737882fb6983bc924a.mod",
        "5114acdbfab7e7a097808d0bd4cdf06e3a3043e4bc5e4e4974715d664502698a",
    ),
    (
        6, 161, "zip", "golang.org/x/text", "v0.28.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/003-c1737882fb6983bc924a.zip",
        "46259e1416ae7ec6adf1867c5f9fab32af0476a148e3c95f1dfbb134f4acf48d",
    ),
    (
        7, 162, "mod", "golang.org/x/tools", "v0.35.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/004-a1d2779b41be5e008b9a.mod",
        "3104836d5c92f046e64149ddd1c42df237855f8a6520abd9ca5374e554ed99d9",
    ),
    (
        8, 162, "zip", "golang.org/x/tools", "v0.35.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "accepted/004-a1d2779b41be5e008b9a.zip",
        "6d2391d8a9a89e54c79cdeaf5e776dfc079838c90c3ac49e97fd91cf20606e9a",
    ),
]
EXPECTED_WAVE12_FALSE_ROOT_GO_MOD_FILES = set()
EXPECTED_WAVE12_FROZEN_PATH_RAWS = [
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-identity-and-acquisition-decision-"
        "wave12-v1.json",
        "230d4329170a27fd27f8eef4c33337971441726837693526b732a4847a779c0a",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-identity-and-acquisition-decision-"
        "wave12-v1.md",
        "31036c0f25364c5f316c30a4541a6a649a13cdcc9952ec9df9cf2c94a1de5398",
    ),
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave12_decision_v1.py",
        "bb9d62377d676cc6de7678db6be8e64b6d65a088c4c508269fdd51f6f9ca9b53",
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave12_decision_v1.py",
        "196fcdaf9a20a60d1b29b628492d1c3f0164805adc5df05678921437e7243def",
    ),
    (
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py",
        "11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985",
    ),
    (
        "script/test_p2p_nat_g2_pion_combined_fixed_point_v10.py",
        "ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave12-execution-permit-v1.md",
        "fa09ad2834fb1a145ab606a4251769a5321d17d97e6bdfb4477dd500de7ad047",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave12-execution-permit-v1.json",
        "ab96943fd74a110b42099826f3555517995e4b2e1ed7f7552cbb683fbe7330a5",
    ),
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave12_acquisition_v1.py",
        "b00ea74bf16e02d429ecf9130ac15ffba9b594a0ae105aa620cd2439cda9bcc1",
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave12_acquisition_v1.py",
        "493c85a538d86f8c78a5b08c22395e4f0d084d8bdc74960028d5f8d08115ec36",
    ),
    (
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave12_v1_once.py",
        "d954a733dafdb9296d79a5a1bb81d7801393dc8063fcee2a70e41bf85f6961c9",
    ),
    (
        "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave12_v1_once.py",
        "0590055346f99746bcdd5aef6deeadc251295fae29336a644c5fadd48044c666",
    ),
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py",
        "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd",
    ),
    (
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py",
        "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b",
    ),
    (
        "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-12-v1.claim",
        "58145cf6660a9a6c3ed5ab36ec4f38df388e88d10c5a1e6820ca9416f06b8280",
    ),
    (
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-12-v1/"
        "evidence.json",
        "edb157c04b1255d87717ef41c2b890115030dfa2800574f7cd34f60d8d1ec251",
    ),
    *[
        (path, raw_sha256)
        for _, _, _, _, _, path, raw_sha256
        in EXPECTED_WAVE12_RESOURCE_IDENTITY
    ],
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave12-receipt-v1.json",
        "59117c663f4eff44057e74690acffa506d71dd86b07d3f4f7aa86b96704edd43",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave12-manifest-v1.json",
        "f00f4ae58f5d193bf32d8ff77661037fa6f38114c55766abb1bbd25c29b5900b",
    ),
]
EXPECTED_CHECKER_RAW_SHA256 = (
    "d330a2f7dd4f12bd4f972e6c34749e10701c594cad75308ccc7de4d3e6aba176"
)
EXPECTED_CHECKER_IMPORT_SURFACE = (
    ("from", "__future__", 0, (("annotations", None),)),
    ("import", (("sys", None),)),
    ("import", (("argparse", None),)),
    ("from", "collections", 0, (("defaultdict", None),)),
    ("import", (("errno", None),)),
    ("import", (("hashlib", None),)),
    ("import", (("io", None),)),
    ("import", (("json", None),)),
    ("import", (("os", None),)),
    ("from", "pathlib", 0, (("Path", None),)),
    ("import", (("stat", None),)),
    ("import", (("types", None),)),
    (
        "from",
        "typing",
        0,
        (("Any", None), ("Mapping", None), ("Sequence", None)),
    ),
    ("import", (("unicodedata", None),)),
    ("import", (("zipfile", None),)),
)
EXPECTED_CHECKER_CALL_COUNT = 1_293
EXPECTED_CHECKER_CALL_SURFACE_SHA256 = (
    "080b20ff9e958e456aa8e92084b744f695584cae8306c67c3e17550e2131184c"
)
EXPECTED_V11_CANDIDATE_CONTENT_SHA256 = (
    "1976ed89f18f28b0b3440a693581f171bdd574bc615f2054bea2cba1cf85b837"
)
EXPECTED_V11_GRAPH_SHA256 = (
    "b4b0ec50d5538e80de93e89574249ca0d49b411443ebd2c78827928704b0a44d"
)
EXPECTED_V11_FRONTIER_SHA256 = (
    "3528abe3579eb1d06ba01f66f56002a6e193fe1e25e233f03eab9b8ac3e4fc32"
)


class StaticSurfaceFailure(AssertionError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def static_expression_dump(expression):
    return ast.dump(
        ast.parse(expression, mode="eval").body,
        annotate_fields=True,
        include_attributes=False,
    )


ALLOWED_GETATTR_CALLS = {
    (
        "ReadOnlyOSProxy.open",
        static_expression_dump("getattr(os, name, 0)"),
    ),
    (
        "ReadOnlyOSProxy.__getattr__",
        static_expression_dump("getattr(os, name)"),
    ),
    (
        "load_provider_facade",
        static_expression_dump("getattr(module, name)"),
    ),
    (
        "load_v10_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v9_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v8_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v7_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v6_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
}
ALLOWED_DYNAMIC_OS_OPEN_CALLS = {
    (
        "ReadOnlyOSProxy.open",
        static_expression_dump("os.open(path, flags, mode)"),
    ),
    (
        "ReadOnlyOSProxy.open",
        static_expression_dump(
            "os.open(path, flags, mode, dir_fd=dir_fd)"
        ),
    ),
}
ALLOWED_OUTPUT_CALLS = {
    (
        "emit_error_document",
        static_expression_dump(
            "sys.stdout.buffer.write(error_document_bytes())"
        ),
    ),
    (
        "main",
        static_expression_dump(
            "sys.stdout.buffer.write("
            "json.dumps("
            "candidate, ensure_ascii=True, sort_keys=True, "
            "separators=(',', ':'), allow_nan=False"
            ").encode() + b'\\n'"
            ")"
        ),
    ),
}
ALLOWED_TEXT_REPLACE_CALL = (
    "pinned_wave9_extract_build_expression.extract",
    static_expression_dump(
        "text.replace("
        "WAVE9_LEGACY_BUILD_ORIGINAL_LINE, "
        "WAVE9_LEGACY_BUILD_NORMALIZED_LINE"
        ")"
    ),
)
SENSITIVE_MODULE_ROOTS = {
    "asyncio",
    "builtins",
    "ctypes",
    "http",
    "importlib",
    "multiprocessing",
    "requests",
    "socket",
    "ssl",
    "subprocess",
    "urllib",
}
IMPORTED_MODULE_NAMES = {
    "argparse",
    "errno",
    "hashlib",
    "io",
    "json",
    "os",
    "stat",
    "sys",
    "types",
    "unicodedata",
    "zipfile",
}
ALLOWED_MODULE_ATTRIBUTE_ALIASES = {
    (("flags",), "sys.flags"),
    (("BadZipFile",), "zipfile.BadZipFile"),
    (("ZIP_DEFLATED",), "zipfile.ZIP_DEFLATED"),
    (("ZIP_STORED",), "zipfile.ZIP_STORED"),
    (("BytesIO",), "io.BytesIO"),
}
FILESYSTEM_MUTATION_CALL_ATTRIBUTES = {
    "chmod",
    "chown",
    "extract",
    "extractall",
    "hardlink_to",
    "link",
    "makedirs",
    "mkdir",
    "open",
    "remove",
    "removedirs",
    "rename",
    "renames",
    "replace",
    "rmdir",
    "symlink",
    "symlink_to",
    "touch",
    "truncate",
    "unlink",
    "write",
    "write_bytes",
    "write_text",
    "writelines",
}
PROCESS_CALL_ATTRIBUTES = {
    "fork",
    "forkpty",
    "popen",
    "posix_spawn",
    "posix_spawnp",
    "system",
}
NETWORK_CALL_ATTRIBUTES = {
    "bind",
    "connect",
    "create_connection",
    "listen",
    "send",
    "sendall",
    "sendto",
    "urlopen",
}


def static_dotted_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


class StaticCallSurfaceVisitor(ast.NodeVisitor):
    def __init__(self):
        self.scope = []
        self.calls = []

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Call(self, node):
        self.calls.append(
            (
                node.lineno,
                node.col_offset,
                ".".join(self.scope) or "<module>",
                node,
            )
        )
        self.generic_visit(node)


def static_import_surface(tree):
    rows = []
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    for node in sorted(imports, key=lambda value: (value.lineno, value.col_offset)):
        if isinstance(node, ast.Import):
            rows.append(
                (
                    "import",
                    tuple(
                        (alias.name, alias.asname)
                        for alias in node.names
                    ),
                )
            )
        else:
            rows.append(
                (
                    "from",
                    node.module,
                    node.level,
                    tuple(
                        (alias.name, alias.asname)
                        for alias in node.names
                    ),
                )
            )
    return tuple(rows)


def static_call_surface_sha256(call_rows):
    projection = [
        {
            "scope": scope,
            "call": ast.dump(
                call,
                annotate_fields=True,
                include_attributes=False,
            ),
        }
        for _, _, scope, call in sorted(
            call_rows,
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
    return hashlib.sha256(
        json.dumps(
            projection,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    ).hexdigest()


def is_read_only_flag_expression(node):
    allowed = {
        "O_CLOEXEC",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_NONBLOCK",
        "O_RDONLY",
    }
    found = []

    def visit(value):
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr):
            return visit(value.left) and visit(value.right)
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "os"
            and value.attr in allowed
        ):
            found.append(value.attr)
            return True
        return False

    return visit(node) and "O_RDONLY" in found


def assignment_values(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]
            names = tuple(
                target.id
                for root in targets
                for target in ast.walk(root)
                if isinstance(target, ast.Name)
                and isinstance(target.ctx, ast.Store)
            )
            yield names, node.value


def validate_checker_static_surface(source):
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise StaticSurfaceFailure("E_STATIC_PARSE") from error
    if static_import_surface(tree) != EXPECTED_CHECKER_IMPORT_SURFACE:
        raise StaticSurfaceFailure("E_IMPORT_ALLOWLIST")

    visitor = StaticCallSurfaceVisitor()
    visitor.visit(tree)
    call_rows = visitor.calls
    allowed_getattr_ids = {
        id(call)
        for _, _, scope, call in call_rows
        if (
            scope,
            ast.dump(
                call,
                annotate_fields=True,
                include_attributes=False,
            ),
        )
        in ALLOWED_GETATTR_CALLS
    }

    for _, _, scope, call in call_rows:
        dotted = static_dotted_name(call.func)
        if isinstance(call.func, ast.Name) and call.func.id == "getattr":
            if id(call) not in allowed_getattr_ids:
                raise StaticSurfaceFailure("E_GETATTR_ALLOWLIST")
        if dotted in {"builtins.__import__", "__import__"}:
            raise StaticSurfaceFailure("E_DYNAMIC_IMPORT")
        if isinstance(call.func, ast.Name) and call.func.id in {
            "eval",
            "__import__",
            "open",
        }:
            raise StaticSurfaceFailure("E_BUILTIN_CALL")
        if isinstance(call.func, ast.Name) and call.func.id in {
            "compile",
            "exec",
        }:
            allowed_loaders = {
                "load_provider_facade": "V1_PROVIDER_PATH",
                "load_v10_checker": "V10_CHECKER_PATH",
                "load_v9_checker": "V9_CHECKER_PATH",
                "load_v8_checker": "V8_CHECKER_PATH",
                "load_v7_checker": "V7_CHECKER_PATH",
                "load_v6_checker": "V6_CHECKER_PATH",
            }
            if scope not in allowed_loaders:
                raise StaticSurfaceFailure("E_PINNED_CODE_CALL")
            if call.func.id == "compile":
                keyword_values = {
                    keyword.arg: keyword.value
                    for keyword in call.keywords
                }
                valid = (
                    len(call.args) == 3
                    and isinstance(call.args[0], ast.Attribute)
                    and isinstance(call.args[0].value, ast.Name)
                    and call.args[0].value.id == "held"
                    and call.args[0].attr == "raw"
                    and isinstance(call.args[1], ast.Name)
                    and call.args[1].id == allowed_loaders[scope]
                    and isinstance(call.args[2], ast.Constant)
                    and call.args[2].value == "exec"
                    and set(keyword_values) == {
                        "dont_inherit",
                        "optimize",
                    }
                    and ast.literal_eval(
                        keyword_values["dont_inherit"]
                    ) is True
                    and ast.literal_eval(
                        keyword_values["optimize"]
                    ) == 0
                )
            else:
                valid = (
                    len(call.args) == 3
                    and not call.keywords
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == "code"
                    and all(
                        isinstance(argument, ast.Attribute)
                        and isinstance(argument.value, ast.Name)
                        and argument.value.id == "module"
                        and argument.attr == "__dict__"
                        for argument in call.args[1:]
                    )
                )
            if not valid:
                raise StaticSurfaceFailure("E_PINNED_CODE_CALL")

        if dotted and dotted.split(".", 1)[0] in SENSITIVE_MODULE_ROOTS:
            raise StaticSurfaceFailure("E_FORBIDDEN_MODULE_CALL")
        if dotted and dotted.startswith("os."):
            os_attribute = dotted.split(".", 1)[1]
            if os_attribute not in {
                "close",
                "dup",
                "fstat",
                "geteuid",
                "listdir",
                "lseek",
                "open",
                "read",
                "stat",
            }:
                raise StaticSurfaceFailure("E_OS_CALL")
            if os_attribute == "open":
                dumped = ast.dump(
                    call,
                    annotate_fields=True,
                    include_attributes=False,
                )
                if (
                    len(call.args) >= 2
                    and isinstance(call.args[1], ast.Name)
                    and call.args[1].id == "flags"
                ):
                    if (scope, dumped) not in ALLOWED_DYNAMIC_OS_OPEN_CALLS:
                        raise StaticSurfaceFailure("E_OS_OPEN_FLAGS")
                elif (
                    len(call.args) < 2
                    or not is_read_only_flag_expression(call.args[1])
                ):
                    raise StaticSurfaceFailure("E_OS_OPEN_FLAGS")

        if dotted and dotted.startswith("sys."):
            dumped = ast.dump(
                call,
                annotate_fields=True,
                include_attributes=False,
            )
            if (scope, dumped) not in ALLOWED_OUTPUT_CALLS:
                raise StaticSurfaceFailure("E_OUTPUT_CALL")
        if isinstance(call.func, ast.Attribute):
            attribute = call.func.attr
            if attribute in PROCESS_CALL_ATTRIBUTES:
                raise StaticSurfaceFailure("E_PROCESS_CALL")
            if attribute in NETWORK_CALL_ATTRIBUTES:
                raise StaticSurfaceFailure("E_NETWORK_CALL")
            if attribute in FILESYSTEM_MUTATION_CALL_ATTRIBUTES:
                if dotted == "sys.stdout.buffer.write":
                    continue
                if dotted == "os.open":
                    continue
                dumped = ast.dump(
                    call,
                    annotate_fields=True,
                    include_attributes=False,
                )
                if (
                    attribute == "replace"
                    and (scope, dumped) == ALLOWED_TEXT_REPLACE_CALL
                ):
                    continue
                raise StaticSurfaceFailure("E_FILESYSTEM_CALL")

    for target_names, value in assignment_values(tree):
        dotted = static_dotted_name(value)
        if isinstance(value, ast.Name) and value.id in (
            IMPORTED_MODULE_NAMES | {"eval", "exec", "__import__"}
        ):
            raise StaticSurfaceFailure("E_SENSITIVE_ALIAS")
        if isinstance(value, ast.Attribute):
            root = dotted.split(".", 1)[0] if dotted else None
            if (target_names, dotted) in ALLOWED_MODULE_ATTRIBUTE_ALIASES:
                continue
            if (
                root in IMPORTED_MODULE_NAMES
                or root in SENSITIVE_MODULE_ROOTS
                or value.attr in (
                    FILESYSTEM_MUTATION_CALL_ATTRIBUTES
                    | PROCESS_CALL_ATTRIBUTES
                    | NETWORK_CALL_ATTRIBUTES
                    | {"__import__", "eval", "exec", "import_module"}
                )
            ):
                raise StaticSurfaceFailure("E_SENSITIVE_ALIAS")
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "getattr"
            and id(value) not in allowed_getattr_ids
        ):
            raise StaticSurfaceFailure("E_GETATTR_ALLOWLIST")

    compile_count = sum(
        isinstance(call.func, ast.Name)
        and call.func.id == "compile"
        for _, _, _, call in call_rows
    )
    exec_count = sum(
        isinstance(call.func, ast.Name)
        and call.func.id == "exec"
        for _, _, _, call in call_rows
    )
    if (compile_count, exec_count) != (6, 6):
        raise StaticSurfaceFailure("E_PINNED_CODE_COUNT")
    if len(call_rows) != EXPECTED_CHECKER_CALL_COUNT:
        raise StaticSurfaceFailure("E_CALL_ALLOWLIST")
    if (
        static_call_surface_sha256(call_rows)
        != EXPECTED_CHECKER_CALL_SURFACE_SHA256
    ):
        raise StaticSurfaceFailure("E_CALL_ALLOWLIST")
    return tree


@contextmanager
def held_toolchain():
    with (
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V10_CHECKER_PATH,
            CHECKER.V10_CHECKER_RAW_SHA256,
        ) as held_v10,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V9_CHECKER_PATH,
            CHECKER.V9_CHECKER_RAW_SHA256,
        ) as held_v9,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V8_CHECKER_PATH,
            CHECKER.V8_CHECKER_RAW_SHA256,
        ) as held_v8,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V7_CHECKER_PATH,
            CHECKER.V7_CHECKER_RAW_SHA256,
        ) as held_v7,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V6_CHECKER_PATH,
            CHECKER.V6_CHECKER_RAW_SHA256,
        ) as held_v6,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V5_CHECKER_PATH,
            CHECKER.V5_CHECKER_RAW_SHA256,
        ) as held_v5,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V4_CHECKER_PATH,
            CHECKER.V4_CHECKER_RAW_SHA256,
        ) as held_v4,
    ):
        v10 = CHECKER.harden_checker_module(
            CHECKER.load_v10_checker(held_v10)
        )
        v9 = v10.load_v9_checker(held_v9)
        v8 = v9.load_v8_checker(held_v8)
        v7 = v8.load_v7_checker(held_v7)
        v6 = v7.load_v6_checker(held_v6)
        v5 = v6.load_v5_checker(held_v5)
        v4 = v5.load_v4_checker(held_v4)
        with v4.PinnedCodeFile(
            ROOT,
            v4.V1_CHECKER_PATH,
            v4.V1_CHECKER_RAW_SHA256,
        ) as held_v1:
            v1 = v4.load_v1_checker(held_v1)
            with v1.PinnedRunnerFile(ROOT) as held_provider:
                runner = v1.load_pinned_runner(held_provider)
                yield v10, v9, v8, v7, v6, v5, v4, v1, runner


@contextmanager
def held_wave12_documents(*, include_held=False):
    with held_toolchain() as chain:
        v10, v9, v8, v7, v6, v5, v4, v1, runner = chain
        bindings = (
            CHECKER.wave12_control_bindings()
            + CHECKER.wave12_auxiliary_evidence_bindings()
        )
        with runner.HeldInputSet(ROOT, bindings) as held:
            documents = CHECKER.parse_wave12_documents(runner, held)
            if include_held:
                yield v4, runner, documents, held
            else:
                yield v4, runner, documents


@contextmanager
def held_all_documents():
    with held_toolchain() as chain:
        v10, v9, v8, v7, v6, v5, v4, v1, runner = chain
        controls = (
            v1.control_bindings()
            + v4.wave3_control_bindings()
            + v4.wave4_control_bindings()
            + v4.wave5_control_bindings()
            + v5.wave6_control_bindings()
            + v6.wave7_control_bindings()
            + v7.wave8_control_bindings()
            + v8.wave9_control_bindings()
            + v9.wave10_control_bindings()
            + v10.wave11_control_bindings()
            + CHECKER.wave12_control_bindings()
        )
        auxiliary = CHECKER.wave12_auxiliary_evidence_bindings()
        with runner.HeldInputSet(ROOT, controls + auxiliary) as held:
            yield (
                chain,
                controls,
                auxiliary,
                held,
                v1.parse_control_documents(runner, held),
                v4.parse_wave3_documents(runner, held),
                v4.parse_wave4_documents(runner, held),
                v4.parse_wave5_documents(runner, held),
                v5.parse_wave6_documents(runner, held),
                v6.parse_wave7_documents(runner, held),
                v7.parse_wave8_documents(runner, held),
                v8.parse_wave9_documents(runner, held),
                v9.parse_wave10_documents(runner, held),
                v10.parse_wave11_documents(runner, held),
                CHECKER.parse_wave12_documents(runner, held),
            )


def assert_wave12_mutation_fails(
    testcase: unittest.TestCase,
    mutate,
    expected_code: str,
) -> None:
    with held_wave12_documents() as (v4, runner, documents):
        mutated = copy.deepcopy(documents)
        mutate(mutated)
        with (
            mock.patch.object(
                CHECKER,
                "verify_wave12_content_bindings",
            ),
            testcase.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught,
        ):
            CHECKER.wave12_request_resources(v4, runner, mutated)
    testcase.assertEqual(str(caught.exception), expected_code)


def rebind_wave12_selector_hashes(
    runner,
    documents,
) -> tuple[str, str]:
    """Rebind selector-bearing projections so semantic checks run."""

    decision = documents[CHECKER.WAVE12_DECISION_PATH]
    permit = documents[CHECKER.WAVE12_PERMIT_PATH]
    readback_permit = documents[CHECKER.WAVE12_READBACK_PERMIT_PATH]
    readback = documents[CHECKER.WAVE12_READBACK_PATH]
    resources = permit["requestContract"]["resources"]
    source_requests = decision["sourceAcquisitionPreparation"]["requestSet"]
    resources_sha256 = CHECKER.sha256_bytes(
        runner.canonical_json_bytes(resources)
    )
    request_set_sha256 = CHECKER.sha256_bytes(
        CHECKER.wave12_digest_bytes(source_requests)
    )

    decision["sourceAcquisitionPreparation"][
        "requestSetCanonicalSha256"
    ] = request_set_sha256
    permit["requestContract"]["resourcesCanonicalSha256"] = resources_sha256
    permit["requestContract"][
        "sourceRequestSetCanonicalSha256"
    ] = request_set_sha256
    snapshot_bindings = readback_permit["frozenAcquisitionSnapshot"][
        "identityBindings"
    ]
    snapshot_bindings["resourcesCanonicalSha256"] = resources_sha256
    snapshot_bindings[
        "sourceRequestSetCanonicalSha256"
    ] = request_set_sha256
    verified = readback["verified"]
    verified["resourcesCanonicalSha256"] = resources_sha256
    verified["sourceRequestSetCanonicalSha256"] = request_set_sha256
    return resources_sha256, request_set_sha256


class CombinedFixedPointV11Tests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        original_load_v10 = CHECKER.load_v10_checker
        original_derive_tool_paths = CHECKER.derive_and_validate_tool_paths
        original_os_open = os.open
        cls.actual_python_open_paths = []

        def capturing_load_v10(held):
            module = original_load_v10(held)
            original_generate = module.generate_candidate

            def capturing_generate(root):
                value = original_generate(root)
                cls.predecessor_candidate = value
                return value

            module.generate_candidate = capturing_generate
            return module

        def capturing_derive_tool_paths(
            v10,
            predecessor_candidate,
            direct_tool_bindings,
            direct_tool_inputs,
        ):
            result = original_derive_tool_paths(
                v10,
                predecessor_candidate,
                direct_tool_bindings,
                direct_tool_inputs,
            )
            cls.actual_direct_hold_records = [
                {
                    "role": binding["role"],
                    "path": held.relative_path,
                    "fdOpen": os.fstat(held.fd).st_nlink == 1,
                }
                for binding, held in zip(
                    direct_tool_bindings,
                    direct_tool_inputs,
                )
            ]
            return result

        def recording_os_open(path, *args, **kwargs):
            fd = original_os_open(path, *args, **kwargs)
            text = os.fspath(path)
            if text.endswith(".py"):
                candidate = Path(text)
                if candidate.is_absolute():
                    try:
                        relative = candidate.relative_to(ROOT).as_posix()
                    except ValueError:
                        relative = candidate.name
                elif "/" in text:
                    relative = candidate.as_posix()
                else:
                    relative = f"script/{text}"
                cls.actual_python_open_paths.append(relative)
            return fd

        with (
            mock.patch.object(
                CHECKER,
                "load_v10_checker",
                side_effect=capturing_load_v10,
            ),
            mock.patch.object(
                CHECKER,
                "derive_and_validate_tool_paths",
                side_effect=capturing_derive_tool_paths,
            ),
            mock.patch.object(
                os,
                "open",
                side_effect=recording_os_open,
            ),
        ):
            cls.candidate = CHECKER.generate_candidate(ROOT)

    def test_01_self_predecessor_and_terminal_bytes_are_exact(self):
        raw = CHECKER_PATH.read_bytes()
        marker = re.compile(
            br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
        )
        independently_normalized, count = marker.subn(
            rb"\g<1>" + b"0" * 64 + rb"\g<2>",
            raw,
        )
        self.assertEqual(count, 1)
        self.assertEqual(
            hashlib.sha256(independently_normalized).hexdigest(),
            EXPECTED_SELF_NORMALIZED_SHA256,
        )
        self.assertEqual(
            CHECKER.SELF_NORMALIZED_SHA256,
            EXPECTED_SELF_NORMALIZED_SHA256,
        )
        for path, expected in (
            (CHECKER.V10_CHECKER_PATH, CHECKER.V10_CHECKER_RAW_SHA256),
            (CHECKER.V10_TESTS_PATH, CHECKER.V10_TESTS_RAW_SHA256),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                expected,
            )
        for path, expected in CHECKER.WAVE12_CONTROL_SHA256.items():
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                expected,
            )

    def test_02_candidate_content_authority_and_route_are_derived(self):
        candidate = self.candidate
        binding = candidate["contentBinding"]
        without = dict(candidate)
        without.pop("contentBinding")
        self.assertEqual(
            hashlib.sha256(
                json.dumps(
                    without,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
                + b"\n"
            ).hexdigest(),
            binding["sha256"],
        )
        self.assertEqual(candidate["schemaVersion"], "11.0")
        self.assertEqual(
            binding["sha256"],
            EXPECTED_V11_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            candidate["graphDiscovery"]["graphSha256"],
            EXPECTED_V11_GRAPH_SHA256,
        )
        self.assertEqual(
            candidate["derivedResult"],
            {
                "fixedPointReached": False,
                "frontierSha256": EXPECTED_V11_FRONTIER_SHA256,
                "frontierTupleCount": 4,
            },
        )
        self.assertEqual(candidate["route"], "next_wave_required")
        self.assertEqual(
            candidate["nextAction"],
            (
                "prepare_separate_versioned_dependency_wave_identity_and_"
                "acquisition_decision"
            ),
        )
        self.assertEqual(candidate["authority"], EXPECTED_CLOSED_AUTHORITY)
        self.assertFalse(candidate["closure"]["releaseReady"])
        self.assertFalse(candidate["closure"]["dependencySourceReviewed"])
        self.assertEqual(
            candidate["derivedResult"]["fixedPointReached"],
            candidate["graphDiscovery"]["fixedPointReached"],
        )
        self.assertEqual(
            candidate["derivedResult"]["frontierTupleCount"],
            len(candidate["graphDiscovery"]["exactFrontier"]),
        )

    def test_03_exact_325_input_composition_and_hashes(self):
        inputs = self.candidate["inputSet"]
        rows = inputs["sourceBindings"]
        expected_counts = {
            "heldSourceInputCount": 325,
            "resourceCount": 324,
            "modCount": 162,
            "zipCount": 162,
            "wave1ResourceCount": 38,
            "wave2ResourceCount": 30,
            "wave3ResourceCount": 32,
            "wave4ResourceCount": 32,
            "wave5ResourceCount": 30,
            "wave6ResourceCount": 36,
            "wave7ResourceCount": 30,
            "wave8ResourceCount": 28,
            "wave9ResourceCount": 20,
            "wave10ResourceCount": 22,
            "wave11ResourceCount": 18,
            "wave12ResourceCount": 8,
            "uniqueModuleVersionTupleCount": 162,
            "aggregateRawByteSize": 302_389_009,
        }
        for key, value in expected_counts.items():
            self.assertEqual(inputs[key], value, key)
        self.assertEqual(len(rows), 325)
        self.assertEqual(len({row["path"] for row in rows}), 325)
        self.assertEqual(
            inputs["combinedInputSetSha256"],
            CHECKER.V11_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(CHECKER.wave12_digest_bytes(rows)).hexdigest(),
            CHECKER.V11_SOURCE_BINDINGS_SHA256,
        )
        pair_orders = sorted(
            {
                row["tupleOrder"]
                for row in rows
                if row["kind"] != "root_zip"
            }
        )
        self.assertEqual(pair_orders, list(range(1, 163)))
        self.assertEqual(
            sorted(
                {
                    row["tupleOrder"]
                    for row in rows
                    if row["wave"] == "wave12"
                }
            ),
            list(range(159, 163)),
        )

    def test_04_reconstruction_and_archive_counters_are_not_stale(self):
        verification = self.candidate["checkerVerification"]
        counters = self.candidate["operationCounters"]
        coverage = self.candidate["coverage"]
        self.assertEqual(
            (
                coverage["archiveCount"],
                coverage["aggregateEntryCount"],
                coverage["aggregateUncompressedByteCount"],
                CHECKER.V11_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
            ),
            (163, 62_041, 1_154_162_168, 1_154_162_168),
        )
        self.assertEqual(
            (
                verification["directFullInputReconstructionCount"],
                verification["inheritedFullInputReconstructionCount"],
                verification["totalFullInputReconstructionCount"],
            ),
            (2, 18, 20),
        )
        self.assertEqual(
            (
                counters["directFullSourceReconstructionCount"],
                counters["inheritedFullSourceReconstructionCount"],
                counters["totalFullSourceReconstructionCount"],
            ),
            (2, 18, 20),
        )
        self.assertEqual(
            (
                counters["directArchiveOpenCount"],
                counters["inheritedArchiveOpenCount"],
                counters["totalArchiveOpenCount"],
                counters["archiveOpenCount"],
            ),
            (326, 1_984, 2_310, 2_310),
        )
        self.assertEqual(
            verification["underlyingIndependentGraphAlgorithmCount"],
            40,
        )
        self.assertEqual(verification["hardenedCheckerModuleCount"], 10)
        self.assertEqual(verification["providerFacadeLoadCount"], 10)
        self.assertEqual(counters["heldTerminalEvidenceCount"], 80)
        self.assertEqual(counters["heldAuxiliaryEvidenceCount"], 3)
        self.assertEqual(counters["heldToolInputCount"], 10)
        self.assertEqual(counters["transitiveDistinctToolPathCount"], 12)
        for key in (
            "archiveExtractionCount",
            "dependencySourceLoadCount",
            "dependencySourceExecutionCount",
            "dependencySourceCompileCount",
            "subprocessCount",
            "networkOperationCount",
            "fileWriteCount",
        ):
            self.assertEqual(counters[key], 0, key)

    def test_05_live_and_historical_boundaries_are_explicit(self):
        verification = self.candidate["checkerVerification"]
        predecessor = self.candidate["predecessorVerification"]
        self.assertTrue(verification["pinnedV10PredecessorExecuted"])
        self.assertEqual(
            verification["v10TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(verification["v10TestsLiveHeld"])
        self.assertTrue(
            verification[
                "wave12HistoricalExact26FrozenSnapshotDescriptorSetBound"
            ]
        )
        self.assertTrue(
            verification["wave12LiveTerminalControlMetadataVerified"]
        )
        self.assertTrue(
            verification["wave12LiveFinalAndAcceptedInventoriesVerified"]
        )
        self.assertTrue(
            verification["wave12CompletionAppliesToRetainedSnapshot"]
        )
        self.assertFalse(
            verification[
                "wave12CurrentPathIdentityGuaranteedThroughManifestPublication"
            ]
        )
        self.assertFalse(
            verification[
                "wave12SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ]
        )
        self.assertEqual(
            predecessor["v10TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(predecessor["v10TestsLiveHeld"])

    def test_06_wave12_terminal_resources_are_exact(self):
        with held_wave12_documents() as (v4, runner, documents):
            resources = CHECKER.wave12_request_resources(
                v4,
                runner,
                documents,
            )
            snapshot = documents[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]
            frozen_rows = [
                *snapshot["acquisitionAuthority"],
                snapshot["acquisitionClaim"],
                snapshot["evidence"],
                *snapshot["acceptedDirectory"]["files"],
                snapshot["acquisitionReceipt"],
                snapshot["acquisitionManifest"],
            ]
            verified_resources = documents[CHECKER.WAVE12_READBACK_PATH][
                "verified"
            ]["resources"]
        self.assertEqual(len(resources), 8)
        self.assertEqual(
            [
                (
                    row["order"],
                    row["tupleOrder"],
                    row["kind"],
                    row["module"],
                    row["version"],
                    row["path"],
                    row["rawSha256"],
                )
                for row in resources
            ],
            EXPECTED_WAVE12_RESOURCE_IDENTITY,
        )
        self.assertEqual(
            [
                (row["path"], row["rawSha256"])
                for row in frozen_rows
            ],
            EXPECTED_WAVE12_FROZEN_PATH_RAWS,
        )
        self.assertEqual(len(EXPECTED_WAVE12_FROZEN_PATH_RAWS), 26)
        self.assertEqual(
            (
                sum(row["kind"] == "mod" for row in resources),
                sum(row["kind"] == "zip" for row in resources),
            ),
            (4, 4),
        )
        self.assertEqual(
            [row["order"] for row in resources],
            list(range(1, 9)),
        )
        self.assertEqual(
            sorted({row["tupleOrder"] for row in resources}),
            list(range(159, 163)),
        )
        self.assertEqual(
            sum(row["maximumBytes"] for row in resources),
            15_036_269,
        )
        self.assertEqual(
            {
                row["acceptedFileName"]
                for row in verified_resources
                if row["kind"] == "zip"
                and row["rootGoModPresent"] is False
            },
            EXPECTED_WAVE12_FALSE_ROOT_GO_MOD_FILES,
        )

    def test_07_combined_input_inventory_is_recomputed(self):
        with held_all_documents() as value:
            (
                chain,
                controls,
                auxiliary,
                _,
                d1,
                d3,
                d4,
                d5,
                d6,
                d7,
                d8,
                d9,
                d10,
                d11,
                d12,
            ) = value
            v10, v9, v8, v7, v6, v5, v4, v1, runner = chain
            rows = CHECKER.combined_source_bindings(
                v10,
                v9,
                v8,
                v7,
                v6,
                v5,
                v4,
                v1,
                runner,
                d1,
                d3,
                d4,
                d5,
                d6,
                d7,
                d8,
                d9,
                d10,
                d11,
                d12,
            )
            projection = v1.source_projection(rows)
        self.assertEqual((len(controls), len(auxiliary)), (80, 3))
        self.assertEqual(len(rows), 325)
        self.assertEqual(
            hashlib.sha256(
                runner.canonical_json_bytes(projection)
            ).hexdigest(),
            CHECKER.V11_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                CHECKER.wave12_digest_bytes(projection)
            ).hexdigest(),
            CHECKER.V11_SOURCE_BINDINGS_SHA256,
        )

    def test_08_unknown_authority_and_tool_pin_fail_closed(self):
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_PERMIT_PATH][
                "authority"
            ].__setitem__("unknownAuthority", False),
            "E_WAVE12_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_DECISION_PATH][
                "toolBindings"
            ][0].__setitem__("normalizedSha256", "0" * 64),
            "E_WAVE12_DECISION",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "toolBindings"
            ][2].__setitem__("rawSha256", "0" * 64),
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_DECISION_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE12_DECISION",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE12_READBACK",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_MANIFEST_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE12_READBACK_MANIFEST",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionReceipt"].__setitem__("rawSha256", "0" * 64),
            "E_WAVE12_READBACK_PERMIT",
        )
        for key in ("acquisitionClaim", "evidence"):
            assert_wave12_mutation_fails(
                self,
                lambda docs, target=key: docs[
                    CHECKER.WAVE12_READBACK_PERMIT_PATH
                ]["frozenAcquisitionSnapshot"][target].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
                "E_WAVE12_READBACK_PERMIT",
            )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PATH][
                "readbackClaim"
            ].__setitem__("rawSha256", "0" * 64),
            "E_WAVE12_READBACK",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_MANIFEST_PATH][
                "receipt"
            ].__setitem__("rawSha256", "0" * 64),
            "E_WAVE12_READBACK_MANIFEST",
        )

    def test_08_each_wave12_accepted_raw_binding_tamper_fails_closed(self):
        with held_wave12_documents() as (v4, runner, documents):
            accepted = documents[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"]
            self.assertEqual(len(accepted), 8)
            for index in range(8):
                mutated = copy.deepcopy(documents)
                mutated[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["acceptedDirectory"]["files"][index]["rawSha256"] = "0" * 64
                with (
                    self.subTest(accepted_raw_index=index),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave12_content_bindings",
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave12_request_resources(v4, runner, mutated)
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE12_READBACK_PERMIT",
                )

    def test_09_stale_v10_and_wave12_cardinality_fail_closed(self):
        def substitute_resource_same_cardinality(documents):
            rows = documents[CHECKER.WAVE12_PERMIT_PATH][
                "requestContract"
            ]["resources"]
            rows[0] = copy.deepcopy(rows[2])

        def substitute_authority_same_cardinality(documents):
            rows = documents[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionAuthority"]
            rows[0] = copy.deepcopy(rows[1])

        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_DECISION_PATH][
                "heldSourceInputSet"
            ].__setitem__("sourceBindingCount", 299),
            "E_WAVE12_DECISION",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_DECISION_PATH][
                "identityResolution"
            ].__setitem__("tupleCount", 9),
            "E_WAVE12_DECISION",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_PERMIT_PATH][
                "requestContract"
            ].__setitem__("requestCount", 18),
            "E_WAVE12_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFileCount", 36),
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"].__setitem__("exactFileCount", 18),
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("acceptedResourceCount", 18),
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"][0].__setitem__(
                "rawSha256",
                "0" * 64,
            ),
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            substitute_resource_same_cardinality,
            "E_WAVE12_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            substitute_authority_same_cardinality,
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFilesCanonicalSha256", "0" * 64),
            "E_WAVE12_READBACK_PERMIT",
        )

    def test_10_selected_tuple_and_live_hold_overclaim_fail_closed(self):
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_DECISION_PATH][
                "identityResolution"
            ].__setitem__("graphSelectedTupleCount", 1),
            "E_WAVE12_DECISION",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", [7, 8]),
            "E_WAVE12_READBACK",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", [17, 18]),
            "E_WAVE12_READBACK",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "verificationContract"
            ].__setitem__("v10TestsLiveHeld", False),
            "E_WAVE12_READBACK_PERMIT",
        )

    def test_10_all_wave12_selectors_and_false_root_mods_are_exact(self):
        with held_wave12_documents() as (v4, runner, documents):
            baseline = documents[CHECKER.WAVE12_PERMIT_PATH][
                "requestContract"
            ]["resources"]
            verified = documents[CHECKER.WAVE12_READBACK_PATH]["verified"][
                "resources"
            ]
            self.assertEqual(len(baseline), 8)
            self.assertTrue(
                all(
                    row["selectedByGraphAlgorithm"] is False
                    for row in baseline
                )
            )
            zip_root_indexes = [
                index
                for index, row in enumerate(verified)
                if row["kind"] == "zip"
                and row["rootGoModPresent"] is True
            ]
            self.assertEqual(zip_root_indexes, [1, 3, 5, 7])

            selector_collections = (
                (
                    "permit_resource",
                    8,
                    lambda docs: docs[CHECKER.WAVE12_PERMIT_PATH][
                        "requestContract"
                    ]["resources"],
                ),
                (
                    "source_request",
                    8,
                    lambda docs: docs[CHECKER.WAVE12_DECISION_PATH][
                        "sourceAcquisitionPreparation"
                    ]["requestSet"],
                ),
                (
                    "identity_tuple",
                    4,
                    lambda docs: docs[CHECKER.WAVE12_DECISION_PATH][
                        "identityResolution"
                    ]["tuples"],
                ),
            )
            missing = object()
            for location, count, rows_for in selector_collections:
                for index in range(count):
                    for value in (True, 0, "false", None, missing):
                        mutated = copy.deepcopy(documents)
                        row = rows_for(mutated)[index]
                        if value is missing:
                            del row["selectedByGraphAlgorithm"]
                            case_value = "missing"
                        else:
                            row["selectedByGraphAlgorithm"] = value
                            case_value = value
                        resources_sha256, request_set_sha256 = (
                            rebind_wave12_selector_hashes(runner, mutated)
                        )
                        with (
                            self.subTest(
                                selector_location=location,
                                selector_index=index,
                                value=case_value,
                            ),
                            mock.patch.object(
                                CHECKER,
                                "verify_wave12_content_bindings",
                            ),
                            mock.patch.object(
                                CHECKER,
                                "WAVE12_PERMIT_RESOURCES_SHA256",
                                resources_sha256,
                            ),
                            mock.patch.object(
                                CHECKER,
                                "WAVE12_REQUEST_SET_SHA256",
                                request_set_sha256,
                            ),
                            self.assertRaises(
                                CHECKER.CombinedCheckFailure,
                            ) as caught,
                        ):
                            CHECKER.wave12_request_resources(
                                v4,
                                runner,
                                mutated,
                            )
                        self.assertEqual(
                            str(caught.exception),
                            "E_WAVE12_RESOURCE",
                        )

            for index in zip_root_indexes:
                mutated = copy.deepcopy(documents)
                mutated[CHECKER.WAVE12_READBACK_PATH]["verified"][
                    "resources"
                ][index]["rootGoModPresent"] = False
                with (
                    self.subTest(root_go_mod_index=index),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave12_content_bindings",
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave12_request_resources(v4, runner, mutated)
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE12_RESOURCE",
                )

    def test_11_post_success_reporting_contract_is_pinned(self):
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH][
                "verificationContract"
            ]["postSuccessReportingFailure"].__setitem__(
                "retryAllowed",
                True,
            ),
            "E_WAVE12_READBACK_PERMIT",
        )
        assert_wave12_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE12_READBACK_PERMIT_PATH].__setitem__(
                "recorderNormalizedSha256",
                "0" * 64,
            ),
            "E_WAVE12_READBACK_PERMIT",
        )

    def test_12_terminal_modes_sizes_and_namespace_are_live(self):
        with held_wave12_documents(include_held=True) as (
            _,
            _,
            documents,
            held,
        ):
            CHECKER.validate_wave12_completed_namespace(held, documents)
            for path, (size, mode) in CHECKER.WAVE12_CONTROL_METADATA.items():
                info = os.fstat(held.files[path].fd)
                self.assertEqual(info.st_size, size)
                self.assertEqual(stat.S_IMODE(info.st_mode), mode)
                self.assertEqual(info.st_nlink, 1)

    def test_13_legacy_wave9_compatibility_remains_exact_and_bounded(self):
        with held_all_documents() as value:
            chain = value[0]
            d9 = value[-4]
            _, _, v8, _, _, _, v4, _, runner = chain
            resources = v8.wave9_request_resources(v4, runner, d9)
            target = next(
                row
                for row in resources
                if row["tupleOrder"] == 137 and row["kind"] == "zip"
            )
            with CHECKER.zipfile.ZipFile(
                ROOT / target["path"],
                mode="r",
            ) as archive:
                name = next(
                    value
                    for value in archive.namelist()
                    if value.endswith("go/loader/example_test.go")
                )
                raw = archive.read(name)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            CHECKER.WAVE9_LEGACY_BUILD_SOURCE_SHA256,
        )

        def parser(text):
            if CHECKER.WAVE9_LEGACY_BUILD_ORIGINAL_LINE in text:
                raise CHECKER.SafeReviewFailure(
                    "E_BUILD_CONSTRAINT",
                    "source_inventory",
                )
            self.assertIn(CHECKER.WAVE9_LEGACY_BUILD_NORMALIZED_LINE, text)
            return CHECKER.WAVE9_LEGACY_BUILD_EXPRESSION

        previous = CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
        wrapped = CHECKER.pinned_wave9_extract_build_expression(parser)
        self.assertEqual(
            wrapped(raw.decode("utf-8")),
            CHECKER.WAVE9_LEGACY_BUILD_EXPRESSION,
        )
        self.assertEqual(
            CHECKER.WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
            previous + 1,
        )

    def test_14_static_surface_rejects_dynamic_process_network_and_write_bypass(
        self,
    ):
        raw = CHECKER_PATH.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            EXPECTED_CHECKER_RAW_SHA256,
        )
        marker = re.compile(
            br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
        )
        normalized, count = marker.subn(
            rb"\g<1>" + b"0" * 64 + rb"\g<2>",
            raw,
        )
        self.assertEqual(count, 1)
        self.assertEqual(
            hashlib.sha256(normalized).hexdigest(),
            EXPECTED_SELF_NORMALIZED_SHA256,
        )
        source = raw.decode("utf-8")
        validate_checker_static_surface(source)
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {
                "asyncio",
                "ctypes",
                "http",
                "importlib",
                "multiprocessing",
                "requests",
                "socket",
                "ssl",
                "subprocess",
                "urllib",
            }
            .isdisjoint(imported)
        )
        calls = [
            node for node in ast.walk(tree) if isinstance(node, ast.Call)
        ]
        named_calls = [
            node.func.id
            for node in calls
            if isinstance(node.func, ast.Name)
        ]
        self.assertTrue(
            {"eval", "__import__", "open"}.isdisjoint(named_calls)
        )

        forbidden_attributes = {
            "connect",
            "create_connection",
            "extract",
            "extractall",
            "fork",
            "forkpty",
            "makedirs",
            "mkdir",
            "popen",
            "posix_spawn",
            "removedirs",
            "renames",
            "rmdir",
            "system",
            "unlink",
            "urlopen",
            "write_bytes",
            "write_text",
        }
        called_attributes = [
            node.func.attr
            for node in calls
            if isinstance(node.func, ast.Attribute)
        ]
        self.assertTrue(
            forbidden_attributes.isdisjoint(called_attributes)
        )
        self.assertFalse(
            any(
                name.startswith(("spawn", "exec"))
                for name in called_attributes
            )
        )
        self.assertFalse(
            any(
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr
                in {"remove", "rename", "replace", "write"}
                for node in calls
            )
        )

        allowed_loader_functions = {
            "load_provider_facade",
            "load_v10_checker",
            "load_v9_checker",
            "load_v8_checker",
            "load_v7_checker",
            "load_v6_checker",
        }
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        def enclosing_function(call):
            matches = [
                function
                for function in functions
                if function.lineno <= call.lineno <= function.end_lineno
            ]
            return min(
                matches,
                key=lambda function: function.end_lineno - function.lineno,
            )

        compile_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "compile"
        ]
        exec_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "exec"
        ]
        self.assertEqual(len(compile_calls), 6)
        self.assertEqual(len(exec_calls), 6)
        self.assertEqual(
            {enclosing_function(node).name for node in compile_calls},
            allowed_loader_functions,
        )
        self.assertEqual(
            {enclosing_function(node).name for node in exec_calls},
            allowed_loader_functions,
        )
        for node in compile_calls:
            self.assertEqual(len(node.args), 3)
            self.assertIsInstance(node.args[0], ast.Attribute)
            self.assertIsInstance(node.args[0].value, ast.Name)
            self.assertEqual(node.args[0].value.id, "held")
            self.assertEqual(node.args[0].attr, "raw")
            self.assertIsInstance(node.args[2], ast.Constant)
            self.assertEqual(node.args[2].value, "exec")
            keyword_values = {
                keyword.arg: keyword.value for keyword in node.keywords
            }
            self.assertIs(
                ast.literal_eval(keyword_values["dont_inherit"]),
                True,
            )
            self.assertEqual(
                ast.literal_eval(keyword_values["optimize"]),
                0,
            )
        for node in exec_calls:
            self.assertEqual(len(node.args), 3)
            self.assertIsInstance(node.args[0], ast.Name)
            self.assertEqual(node.args[0].id, "code")
            for argument in node.args[1:]:
                self.assertIsInstance(argument, ast.Attribute)
                self.assertIsInstance(argument.value, ast.Name)
                self.assertEqual(argument.value.id, "module")
                self.assertEqual(argument.attr, "__dict__")

        write_flag_names = {
            "O_APPEND",
            "O_CREAT",
            "O_EXCL",
            "O_RDWR",
            "O_TRUNC",
            "O_WRONLY",
        }
        for node in calls:
            if not (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "open"
            ):
                continue
            call_source = ast.get_source_segment(source, node)
            if (
                len(node.args) >= 2
                and isinstance(node.args[1], ast.Name)
                and node.args[1].id == "flags"
            ):
                self.assertEqual(enclosing_function(node).name, "open")
                continue
            self.assertTrue(
                all(name not in call_source for name in write_flag_names)
            )
            self.assertIn("O_RDONLY", call_source)

        authority = self.candidate["authority"]
        self.assertEqual(authority, EXPECTED_CLOSED_AUTHORITY)
        self.assertTrue(all(value is False for value in authority.values()))

    def test_15_no_follow_pin_rejects_a_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.py"
            target.write_bytes(b"pass\n")
            alias = root / "alias.py"
            alias.symlink_to(target)
            with self.assertRaises(OSError):
                with CHECKER.PinnedCodeFile(
                    root,
                    "alias.py",
                    hashlib.sha256(b"pass\n").hexdigest(),
                ):
                    pass

    def test_16_error_document_requests_no_credentials(self):
        value = json.loads(CHECKER.error_document_bytes())
        self.assertEqual(value["schemaVersion"], "11.0")
        self.assertEqual(value["status"], "verification_failed")
        self.assertFalse(value["externalAuthenticationRequired"])
        self.assertFalse(value["userActionRequired"])

    def test_17_v10_predecessor_is_exact_and_mutations_fail_closed(self):
        predecessor = self.predecessor_candidate
        self.assertEqual(
            predecessor["contentBinding"]["sha256"],
            CHECKER.V10_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            predecessor["inputSet"]["combinedInputSetSha256"],
            CHECKER.V10_INPUT_SET_SHA256,
        )
        self.assertEqual(
            predecessor["graphDiscovery"]["graphSha256"],
            CHECKER.V10_GRAPH_SHA256,
        )
        self.assertEqual(
            predecessor["derivedResult"]["frontierSha256"],
            CHECKER.V10_FRONTIER_SHA256,
        )
        self.assertEqual(
            predecessor["checkerVerification"]["v9TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(
            predecessor["checkerVerification"]["v9TestsLiveHeld"]
        )
        with held_wave12_documents() as (_, runner, documents):
            decision = documents[CHECKER.WAVE12_DECISION_PATH]
            verified = CHECKER.validate_v10_predecessor_candidate(
                runner,
                predecessor,
                decision,
            )
            self.assertEqual(
                verified["candidateContentSha256"],
                CHECKER.V10_CANDIDATE_CONTENT_SHA256,
            )
            stale_key_decision = copy.deepcopy(decision)
            stale_key_decision["predecessorBindings"][
                "combinedFixedPointV9"
            ] = stale_key_decision["predecessorBindings"].pop(
                "combinedFixedPointV10"
            )
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.validate_v10_predecessor_candidate(
                    runner,
                    predecessor,
                    stale_key_decision,
                )
            self.assertEqual(str(caught.exception), "E_V10_PREDECESSOR")
            for key in (
                "contentSha256",
                "combinedInputSetSha256",
                "sourceBindingsSha256",
                "graphSha256",
                "frontierSha256",
                "checkerRawSha256",
                "checkerNormalizedSha256",
                "testsRawSha256",
            ):
                with self.subTest(predecessor_binding=key):
                    mutated_decision = copy.deepcopy(decision)
                    mutated_decision["predecessorBindings"][
                        "combinedFixedPointV10"
                    ][key] = "0" * 64
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v10_predecessor_candidate(
                            runner,
                            predecessor,
                            mutated_decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V10_PREDECESSOR",
                    )
            candidate_mutations = [
                lambda value: value["inputSet"]["sourceBindings"][0].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
                lambda value: value["graphDiscovery"].__setitem__(
                    "graphSha256",
                    "0" * 64,
                ),
                lambda value: value["derivedResult"].__setitem__(
                    "frontierSha256",
                    "0" * 64,
                ),
                lambda value: value["operationCounters"].__setitem__(
                    "archiveOpenCount",
                    1_983,
                ),
            ]
            for index, mutate in enumerate(candidate_mutations):
                with self.subTest(predecessor_candidate=index):
                    mutated_candidate = copy.deepcopy(predecessor)
                    mutate(mutated_candidate)
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v10_predecessor_candidate(
                            runner,
                            mutated_candidate,
                            decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V10_PREDECESSOR",
                    )

    def test_18_live_protocol_order_and_tool_holds_are_observed(self):
        expected_direct_records = [
            {
                "role": row["role"],
                "path": row["path"],
                "fdOpen": True,
            }
            for row in EXPECTED_TOOL_BINDINGS
        ]
        expected_transitive_paths = {
            (
                "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                f"v{version}.py"
            )
            for version in range(1, 12)
        } | {
            (
                "script/run_p2p_nat_g2_pion_dependency_source_review_"
                "wave1_once.py"
            )
        }
        self.assertEqual(
            self.actual_direct_hold_records,
            expected_direct_records,
        )
        self.assertEqual(
            set(self.actual_python_open_paths),
            expected_transitive_paths,
        )
        self.assertNotIn(CHECKER.V10_TESTS_PATH, self.actual_python_open_paths)
        self.assertNotIn(CHECKER.V9_TESTS_PATH, self.actual_python_open_paths)
        for forbidden in (
            "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave12_v1_once.py",
            (
                "script/record_p2p_nat_g2_pion_rung3_dependency_wave12_"
                "readback_v1_once.py"
            ),
            (
                "script/check_p2p_nat_g2_pion_rung3_dependency_wave12_"
                "acquisition_v1.py"
            ),
            (
                "script/check_p2p_nat_g2_pion_rung3_dependency_wave12_"
                "readback_execution_permit_v1.py"
            ),
        ):
            self.assertNotIn(forbidden, self.actual_python_open_paths)
        self.assertEqual(
            self.candidate["toolBindings"],
            EXPECTED_TOOL_BINDINGS,
        )
        self.assertEqual(
            self.candidate["operationCounters"]["heldToolInputCount"],
            len(expected_direct_records),
        )
        self.assertEqual(
            self.candidate["operationCounters"][
                "transitiveDistinctToolPathCount"
            ],
            len(expected_transitive_paths),
        )

        events = []

        class V4:
            reconstruction_count = 0

            @staticmethod
            def combined_identity_barrier(_root, _held_inputs):
                events.append("barrier")

            @classmethod
            def reconstruct_graph_v3(
                cls,
                _runner,
                _permit,
                _bindings,
                _source_held,
                _limits,
            ):
                cls.reconstruction_count += 1
                events.append(f"reconstruct{cls.reconstruction_count}")
                return {"graph": "same"}, {"coverage": "same"}

        class Runner:
            @staticmethod
            def canonical_json_bytes(value):
                return json.dumps(value, sort_keys=True).encode()

        namespace_count = 0

        def namespace_spy(_held, _documents):
            nonlocal namespace_count
            namespace_count += 1
            events.append(
                "namespace-pre"
                if namespace_count == 1
                else "namespace-post"
            )

        original_check = CHECKER.check

        def check_spy(condition, code):
            if code == "E_REPRODUCTION":
                events.append("equality")
            return original_check(condition, code)

        held_inputs = (object(),)
        with (
            mock.patch.object(
                CHECKER,
                "validate_wave12_completed_namespace",
                side_effect=namespace_spy,
            ),
            mock.patch.object(CHECKER, "check", side_effect=check_spy),
        ):
            state = CHECKER.execute_reconstruction_protocol_prefix(
                ROOT,
                held_inputs,
                V4,
                Runner(),
                {},
                [],
                object(),
                {},
                object(),
                {},
            )
            events.append("candidate/result")
            candidate = {"candidate": True}
            result = CHECKER.finalize_reconstruction_protocol(
                ROOT,
                held_inputs,
                V4,
                object(),
                {},
                state,
                candidate,
            )
        self.assertIs(result, candidate)
        self.assertEqual(
            events,
            [
                "namespace-pre",
                "barrier",
                "reconstruct1",
                "barrier",
                "reconstruct2",
                "equality",
                "barrier",
                "candidate/result",
                "barrier",
                "namespace-post",
            ],
        )

        source = CHECKER_PATH.read_text()
        tree = ast.parse(source)
        generate = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "generate_candidate"
        )
        calls = [
            node
            for node in ast.walk(generate)
            if isinstance(node, ast.Call)
        ]
        prefix = next(
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "execute_reconstruction_protocol_prefix"
        )
        content_bound = next(
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "content_bound"
        )
        finalizer = next(
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "finalize_reconstruction_protocol"
        )
        self.assertLess(prefix.lineno, content_bound.lineno)
        self.assertLess(content_bound.lineno, finalizer.lineno)

    def test_19_derived_route_and_fixed_point_are_fail_closed(self):
        class Runner:
            @staticmethod
            def canonical_json_bytes(value):
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

        runner = Runner()
        scenarios = [
            (
                {
                    "exactFrontier": [{"module": "example.invalid/next"}],
                    "newTupleCount": 1,
                    "unmappedExternalImportCount": 0,
                    "unresolvedDeclaredExternalImportCount": 0,
                    "fixedPointReached": False,
                },
                {
                    "route": "next_wave_required",
                    "status":
                        "combined_graph_discovery_complete_next_wave_required",
                    "nextAction": (
                        "prepare_separate_versioned_dependency_wave_"
                        "identity_and_acquisition_decision"
                    ),
                },
            ),
            (
                {
                    "exactFrontier": [],
                    "newTupleCount": 0,
                    "unmappedExternalImportCount": 1,
                    "unresolvedDeclaredExternalImportCount": 0,
                    "fixedPointReached": False,
                },
                {
                    "route": "external_import_resolution_required",
                    "status": (
                        "combined_graph_discovery_complete_external_import_"
                        "resolution_required"
                    ),
                    "nextAction":
                        "prepare_separate_external_import_resolution_decision",
                },
            ),
            (
                {
                    "exactFrontier": [],
                    "newTupleCount": 0,
                    "unmappedExternalImportCount": 0,
                    "unresolvedDeclaredExternalImportCount": 0,
                    "fixedPointReached": True,
                },
                {
                    "route": "fixed_point_candidate",
                    "status":
                        "combined_graph_discovery_complete_fixed_point_candidate",
                    "nextAction": (
                        "prepare_separate_combined_fixed_point_closure_"
                        "review_decision"
                    ),
                },
            ),
        ]
        for graph, route in scenarios:
            result = CHECKER.derive_and_validate_graph_result(
                runner,
                graph,
                route,
            )
            self.assertEqual(
                result["fixedPointReached"],
                graph["fixedPointReached"],
            )
            self.assertEqual(
                result["frontierTupleCount"],
                len(graph["exactFrontier"]),
            )

        invalid = [
            (
                {
                    **scenarios[0][0],
                    "newTupleCount": True,
                },
                scenarios[0][1],
            ),
            (
                {
                    **scenarios[0][0],
                    "newTupleCount": 0,
                },
                scenarios[0][1],
            ),
            (
                {
                    **scenarios[2][0],
                    "fixedPointReached": False,
                },
                scenarios[2][1],
            ),
            (
                scenarios[0][0],
                {
                    **scenarios[0][1],
                    "route": "fixed_point_candidate",
                },
            ),
        ]
        for graph, route in invalid:
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.derive_and_validate_graph_result(
                    runner,
                    graph,
                    route,
                )
            self.assertEqual(str(caught.exception), "E_DERIVED_RESULT")

    def test_20_tool_path_derivation_rejects_duplicate_missing_and_extra(self):
        class V10:
            TRANSITIVE_CHECKER_PATHS = {
                (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                    f"v{version}.py"
                )
                for version in range(1, 10)
            }
            V1_CHECKER_PATH = (
                "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
            )
            V1_PROVIDER_PATH = (
                "script/run_p2p_nat_g2_pion_dependency_source_review_"
                "wave1_once.py"
            )

        class Held:
            def __init__(self, relative_path):
                self.relative_path = relative_path

        direct_bindings = copy.deepcopy(EXPECTED_TOOL_BINDINGS)
        direct_inputs = tuple(
            Held(row["path"]) for row in EXPECTED_TOOL_BINDINGS
        )
        direct_paths, transitive_paths = (
            CHECKER.derive_and_validate_tool_paths(
                V10,
                self.predecessor_candidate,
                direct_bindings,
                direct_inputs,
            )
        )
        self.assertEqual(len(direct_paths), 10)
        self.assertEqual(len(transitive_paths), 12)

        duplicate = copy.deepcopy(direct_bindings)
        duplicate[-1] = copy.deepcopy(duplicate[0])
        missing = copy.deepcopy(direct_bindings)
        missing.pop()
        extra = copy.deepcopy(direct_bindings)
        extra.append(
            {
                "role": "unexpected_tool",
                "path": "script/unexpected_tool.py",
                "rawSha256": "0" * 64,
            }
        )
        for label, mutated in (
            ("duplicate", duplicate),
            ("missing", missing),
            ("extra", extra),
        ):
            with self.subTest(direct=label), self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.derive_and_validate_tool_paths(
                    V10,
                    self.predecessor_candidate,
                    mutated,
                    direct_inputs,
                )
            self.assertEqual(str(caught.exception), "E_TOOL_BINDINGS")

        predecessor_duplicate = copy.deepcopy(self.predecessor_candidate)
        predecessor_duplicate["toolBindings"][-1] = copy.deepcopy(
            predecessor_duplicate["toolBindings"][0]
        )
        with self.assertRaises(CHECKER.CombinedCheckFailure) as caught:
            CHECKER.derive_and_validate_tool_paths(
                V10,
                predecessor_duplicate,
                direct_bindings,
                direct_inputs,
            )
        self.assertEqual(str(caught.exception), "E_TOOL_BINDINGS")

        declared = set(CHECKER.TRANSITIVE_CHECKER_PATHS)
        for label, mutated in (
            ("missing", declared - {
                "script/check_p2p_nat_g2_pion_combined_fixed_point_v2.py"
            }),
            ("extra", declared | {"script/unexpected_tool.py"}),
        ):
            with (
                self.subTest(declared=label),
                mock.patch.object(
                    CHECKER,
                    "TRANSITIVE_CHECKER_PATHS",
                    mutated,
                ),
                self.assertRaises(CHECKER.CombinedCheckFailure) as caught,
            ):
                CHECKER.derive_and_validate_tool_paths(
                    V10,
                    self.predecessor_candidate,
                    direct_bindings,
                    direct_inputs,
                )
            self.assertEqual(str(caught.exception), "E_TOOL_BINDINGS")

    def test_21_synthetic_static_bypasses_fail_the_strict_allowlist(self):
        source = CHECKER_PATH.read_text()
        validate_checker_static_surface(source)
        mutations = [
            (
                "from_os_system",
                "from os import system\nsystem('x')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "from_os_remove_alias",
                "from os import remove as cleanup\ncleanup('x')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "import_os_alias",
                "import os as operating_system\n"
                "operating_system.system('x')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "import_subprocess_alias",
                "import subprocess as process\nprocess.run(['x'])\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "from_builtins_eval",
                "from builtins import eval as evaluator\n"
                "evaluator('1 + 1')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "literal_getattr",
                "getattr(os, 'system')('x')\n",
                "E_GETATTR_ALLOWLIST",
            ),
            (
                "dynamic_getattr",
                "dynamic_name = 'system'\n"
                "getattr(os, dynamic_name)('x')\n",
                "E_GETATTR_ALLOWLIST",
            ),
            (
                "non_os_dynamic_getattr",
                "getattr(module, name)()\n",
                "E_GETATTR_ALLOWLIST",
            ),
            (
                "builtins_import",
                "builtins.__import__('socket')\n",
                "E_DYNAMIC_IMPORT",
            ),
            (
                "import_alias",
                "loader = __import__\nloader('socket')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "eval_alias",
                "evaluator = eval\nevaluator('1 + 1')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "exec_alias",
                "executor = exec\nexecutor('pass')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "importlib_alias",
                "loader = importlib.import_module\nloader('socket')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "ctypes_alias",
                "loader = ctypes.CDLL\nloader('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "subprocess_alias",
                "process = subprocess.run\nprocess(['x'])\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "socket_alias",
                "connector = socket.socket\nconnector()\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "network_alias",
                "request = requests.get\nrequest('https://invalid')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "process_alias",
                "process = os.system\nprocess('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "filesystem_alias",
                "cleanup = os.remove\ncleanup('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "path_write_alias",
                "writer = Path('/tmp/x').write_text\nwriter('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "direct_process",
                "os.system('x')\n",
                "E_OS_CALL",
            ),
            (
                "direct_filesystem",
                "os.remove('x')\n",
                "E_OS_CALL",
            ),
            (
                "path_unlink",
                "Path('/tmp/x').unlink()\n",
                "E_FILESYSTEM_CALL",
            ),
            (
                "output_write",
                "sys.stdout.buffer.write(b'x')\n",
                "E_OUTPUT_CALL",
            ),
            (
                "write_open_flag",
                "os.open('x', os.O_WRONLY)\n",
                "E_OS_OPEN_FLAGS",
            ),
            (
                "builtin_open",
                "open('x', 'w')\n",
                "E_BUILTIN_CALL",
            ),
            (
                "unscoped_exec",
                "exec('pass')\n",
                "E_PINNED_CODE_CALL",
            ),
            (
                "unscoped_compile",
                "compile(b'pass', 'x', 'exec')\n",
                "E_PINNED_CODE_CALL",
            ),
            (
                "otherwise_safe_extra_call",
                "len([])\n",
                "E_CALL_ALLOWLIST",
            ),
        ]
        for name, suffix, expected_code in mutations:
            with self.subTest(mutation=name):
                with self.assertRaises(StaticSurfaceFailure) as caught:
                    validate_checker_static_surface(
                        f"{source}\n{suffix}"
                    )
                self.assertEqual(caught.exception.code, expected_code)


class CombinedFixedPointV11FastBoundaryTests(unittest.TestCase):
    def test_aggregate_uncompressed_limit_minus_one_is_rejected(self):
        aggregate_bytes = (
            CHECKER.V11_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
        )
        archive = {
            "embeddedGoMod": b"module example.invalid/root\n",
            "entryCount": 1,
            "licenses": [],
            "sources": [],
            "special": [],
            "testdataSemanticExclusions": [],
            "uncompressedByteCount": aggregate_bytes,
        }
        binding = {
            "kind": "root_zip",
            "path": "fixture.zip",
        }
        held = type("Held", (), {"raw": {"fixture.zip": b""}})()
        limits = {
            "maximumAggregateEntries": 1,
            "maximumAggregateUncompressedBytes": aggregate_bytes - 1,
        }
        with held_toolchain() as chain:
            v4 = chain[6]
            with (
                mock.patch.object(
                    v4,
                    "inspect_zip_bytes_v3",
                    return_value=archive,
                ),
                self.assertRaises(v4.CombinedCheckFailure) as caught,
            ):
                v4.reconstruct_graph_v3(
                    object(),
                    {},
                    [binding],
                    held,
                    limits,
                )
        self.assertEqual(str(caught.exception), "E_ARCHIVE_AGGREGATE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
