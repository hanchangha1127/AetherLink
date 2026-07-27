#!/usr/bin/env python3
"""Focused tests for the exact read-only 317-input combined v10 checker."""

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
            "combined fixed-point v10 tests require unoptimized "
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
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py"


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "combined_fixed_point_v10_tests_target",
        CHECKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("checker load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()

EXPECTED_SELF_NORMALIZED_SHA256 = (
    "ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751"
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
        "role": "current_v10_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py",
        "normalizedSha256": EXPECTED_SELF_NORMALIZED_SHA256,
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
EXPECTED_WAVE11_RESOURCE_IDENTITY = [
    (
        1, 150, "mod", "golang.org/x/crypto",
        "v0.0.0-20190308221718-c2843e01d9a2",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/001-9894bdc57c7ef00afa59.mod",
        "33ed070a5a66e0960685ac5386440e1b59899e74d8a38a1180685e72a2195ded",
    ),
    (
        2, 150, "zip", "golang.org/x/crypto",
        "v0.0.0-20190308221718-c2843e01d9a2",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/001-9894bdc57c7ef00afa59.zip",
        "46882ccda86aa64aa862fc64b7c6861318f03b18b834550be83d91b26acad6d4",
    ),
    (
        3, 151, "mod", "golang.org/x/mod", "v0.27.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/002-2987c4fcc316ee835233.mod",
        "b20d6c1f4b46742e6af828327160346aeb3e622ab1780ad51b80e1d67adfe95b",
    ),
    (
        4, 151, "zip", "golang.org/x/mod", "v0.27.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/002-2987c4fcc316ee835233.zip",
        "19fb241d46e4397d3193b5fa899e2a9d62bb5d1c41f73d09d29c17c3c0d3953c",
    ),
    (
        5, 152, "mod", "golang.org/x/net", "v0.43.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/003-b2a9b4140098e83d3001.mod",
        "4a24c4398df8c261eae7ba52cdb4b01691725cdc46e4ad497811aad357c25832",
    ),
    (
        6, 152, "zip", "golang.org/x/net", "v0.43.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/003-b2a9b4140098e83d3001.zip",
        "24d4f49b7e781763942533d5a5acc49ebd054e05c50bf4402b264695ef8d10c5",
    ),
    (
        7, 153, "mod", "golang.org/x/sync", "v0.16.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/004-8efa828872614a15a5da.mod",
        "720b98f1bf033d6b64a454ca8c29cdca6e9265ab7d70db3b834dff49560f1587",
    ),
    (
        8, 153, "zip", "golang.org/x/sync", "v0.16.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/004-8efa828872614a15a5da.zip",
        "ca43984183eb14f7f50d33da350312fed1c42e106dceac2437bfd5084b497dcd",
    ),
    (
        9, 154, "mod", "golang.org/x/sys",
        "v0.0.0-20190215142949-d0b11bdaac8a",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/005-f170b64e48ac0bef3a82.mod",
        "8969115e4a39108848324e79a1bd8a8445230e6e3aaccbe9f8057fb50fffc8c1",
    ),
    (
        10, 154, "zip", "golang.org/x/sys",
        "v0.0.0-20190215142949-d0b11bdaac8a",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/005-f170b64e48ac0bef3a82.zip",
        "d6bf74e7bc64e245a75dd666e62160a8446242b1cde4e66b2e5f93399950a97f",
    ),
    (
        11, 155, "mod", "golang.org/x/sys",
        "v0.0.0-20201119102817-f84b799fce68",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/006-03aa3c1ad42e5d2db095.mod",
        "181979e8bd57d2d9e064182da86c9a6111aa69755e888f08431ece4742aec343",
    ),
    (
        12, 155, "zip", "golang.org/x/sys",
        "v0.0.0-20201119102817-f84b799fce68",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/006-03aa3c1ad42e5d2db095.zip",
        "2681eb52677683be3760258aafe13c91c1c83888442e9c6545334ae97a02b386",
    ),
    (
        13, 156, "mod", "golang.org/x/sys", "v0.35.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/007-98301425f58c02425c44.mod",
        "f67e3e18f4c08e60a7e80726ab36b691fdcea5b81ae1c696ff64caf518bcfe3d",
    ),
    (
        14, 156, "zip", "golang.org/x/sys", "v0.35.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/007-98301425f58c02425c44.zip",
        "dc3c20611168aaa8fda0d71999be1a5222a0ba57bc767c978a590e41ff2ede35",
    ),
    (
        15, 157, "mod", "golang.org/x/telemetry",
        "v0.0.0-20250807160809-1a19826ec488",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/008-46354906cc6226f910d2.mod",
        "0a2f520fac6da1a1d35c6fe76b1aaa39aa4c5b704a3b91c8f9423daaf4b7b60e",
    ),
    (
        16, 157, "zip", "golang.org/x/telemetry",
        "v0.0.0-20250807160809-1a19826ec488",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/008-46354906cc6226f910d2.zip",
        "9829c06173ef37d970b47879e67da1d31c8bf36b6e29cea873815b0798bbab74",
    ),
    (
        17, 158, "mod", "golang.org/x/text", "v0.3.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/009-3bcf448e615ad4014b25.mod",
        "36879d586fd8001e84da8787190a11e4f78749e2a81dfe8b9b6931899fff31cf",
    ),
    (
        18, 158, "zip", "golang.org/x/text", "v0.3.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "accepted/009-3bcf448e615ad4014b25.zip",
        "ea3068395503d3c7ef8ce16a286f75c8c93882c25a66c2aa6c8e2ad4da7a9ae0",
    ),
]
EXPECTED_WAVE11_FALSE_ROOT_GO_MOD_FILES = {
    "005-f170b64e48ac0bef3a82.zip",
    "009-3bcf448e615ad4014b25.zip",
}
EXPECTED_WAVE11_FROZEN_PATH_RAWS = [
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-identity-and-acquisition-decision-"
        "wave11-v1.json",
        "e1f3a82025c711694cb6551a53407aa1164493396a65f383eacf95dbf90b881a",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-identity-and-acquisition-decision-"
        "wave11-v1.md",
        "a153ab49d1d6e2c0f99564fd49704b9d4000ba686b076e1e19ce7a68413c8c74",
    ),
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave11_decision_v1.py",
        "d73fa27a15a2936e21bdc1dfb12ad83c0f7b4b2399a67c637e84626170698f16",
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave11_decision_v1.py",
        "b124eb04e26faa66ab9a194ae945583e8eedf3f4788fa23122f50e86b46a35cc",
    ),
    (
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v9.py",
        "c0f098cf0a047c4d1aca03f5b7f16f327306b56ed8e656d67afe32503eb117da",
    ),
    (
        "script/test_p2p_nat_g2_pion_combined_fixed_point_v9.py",
        "fca6a0ca437356185d287816bcfaf5e110794207b3413addf95e9eb24038c217",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave11-execution-permit-v1.md",
        "0941c3e5132eacd386a90f5b2064d256bd1c3ca1f63b52fc8f4e69d900645a55",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave11-execution-permit-v1.json",
        "9d8d2aa4d5be23575ef42aecf3fd2dffb37a1af56e86a208bc85a63f167f342e",
    ),
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave11_acquisition_v1.py",
        "72c6709e51dff3753f7ca92b2a64bcb6ed3057573798e05c829184f627b8fd87",
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave11_acquisition_v1.py",
        "77ea295e4c8c1b60854cfec0170655a22c0b7f5ced09324bedda9805e18a1ac2",
    ),
    (
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave11_v1_once.py",
        "ca6849f3ca9a47c4bb3f1e1efe477dd24e21419895fdc7ce738bbe41737b55a0",
    ),
    (
        "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave11_v1_once.py",
        "79ae96707650e63dfcc73e8825e53ceb51283069b9958bf3af0949681b684aca",
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
        "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-11-v1.claim",
        "a41663bd827b8f07e0e04e887b21a7306c0ba286396e43d854ea3f2369a3e985",
    ),
    (
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-11-v1/"
        "evidence.json",
        "c4194219b35723fb61ee41fca23a10ffe5f2c18f01f82fb70856a404019fb797",
    ),
    *[
        (path, raw_sha256)
        for _, _, _, _, _, path, raw_sha256
        in EXPECTED_WAVE11_RESOURCE_IDENTITY
    ],
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave11-receipt-v1.json",
        "0c35d330476362fdaba23192229d8aa0fa096c0f47fddb39955f8976db6115a8",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave11-manifest-v1.json",
        "ac247bed91f7cbe50c90d8a640b885ca1adaa2888fa8447f6ea0baeb4a046a15",
    ),
]
EXPECTED_CHECKER_RAW_SHA256 = (
    "11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985"
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
EXPECTED_CHECKER_CALL_COUNT = 1_273
EXPECTED_CHECKER_CALL_SURFACE_SHA256 = (
    "171b4ee8532629c9ffbe92e026a452bfc16c55f11ba9978c2fe73f841601a178"
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
    if (compile_count, exec_count) != (5, 5):
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
        v9 = CHECKER.harden_checker_module(
            CHECKER.load_v9_checker(held_v9)
        )
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
                yield v9, v8, v7, v6, v5, v4, v1, runner


@contextmanager
def held_wave11_documents(*, include_held=False):
    with held_toolchain() as chain:
        v9, v8, v7, v6, v5, v4, v1, runner = chain
        bindings = (
            CHECKER.wave11_control_bindings()
            + CHECKER.wave11_auxiliary_evidence_bindings()
        )
        with runner.HeldInputSet(ROOT, bindings) as held:
            documents = CHECKER.parse_wave11_documents(runner, held)
            if include_held:
                yield v4, runner, documents, held
            else:
                yield v4, runner, documents


@contextmanager
def held_all_documents():
    with held_toolchain() as chain:
        v9, v8, v7, v6, v5, v4, v1, runner = chain
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
            + CHECKER.wave11_control_bindings()
        )
        auxiliary = CHECKER.wave11_auxiliary_evidence_bindings()
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
                CHECKER.parse_wave11_documents(runner, held),
            )


def assert_wave11_mutation_fails(
    testcase: unittest.TestCase,
    mutate,
    expected_code: str,
) -> None:
    with held_wave11_documents() as (v4, runner, documents):
        mutated = copy.deepcopy(documents)
        mutate(mutated)
        with (
            mock.patch.object(
                CHECKER,
                "verify_wave11_content_bindings",
            ),
            testcase.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught,
        ):
            CHECKER.wave11_request_resources(v4, runner, mutated)
    testcase.assertEqual(str(caught.exception), expected_code)


def rebind_wave11_selector_hashes(
    runner,
    documents,
) -> tuple[str, str]:
    """Rebind selector-bearing projections so semantic checks run."""

    decision = documents[CHECKER.WAVE11_DECISION_PATH]
    permit = documents[CHECKER.WAVE11_PERMIT_PATH]
    readback_permit = documents[CHECKER.WAVE11_READBACK_PERMIT_PATH]
    readback = documents[CHECKER.WAVE11_READBACK_PATH]
    resources = permit["requestContract"]["resources"]
    source_requests = decision["sourceAcquisitionPreparation"]["requestSet"]
    resources_sha256 = CHECKER.sha256_bytes(
        runner.canonical_json_bytes(resources)
    )
    request_set_sha256 = CHECKER.sha256_bytes(
        CHECKER.wave11_digest_bytes(source_requests)
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


class CombinedFixedPointV10Tests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        original_load_v9 = CHECKER.load_v9_checker
        original_derive_tool_paths = CHECKER.derive_and_validate_tool_paths
        original_os_open = os.open
        cls.actual_python_open_paths = []

        def capturing_load_v9(held):
            module = original_load_v9(held)
            original_generate = module.generate_candidate

            def capturing_generate(root):
                value = original_generate(root)
                cls.predecessor_candidate = value
                return value

            module.generate_candidate = capturing_generate
            return module

        def capturing_derive_tool_paths(
            v9,
            predecessor_candidate,
            direct_tool_bindings,
            direct_tool_inputs,
        ):
            result = original_derive_tool_paths(
                v9,
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
                "load_v9_checker",
                side_effect=capturing_load_v9,
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
            (CHECKER.V9_CHECKER_PATH, CHECKER.V9_CHECKER_RAW_SHA256),
            (CHECKER.V9_TESTS_PATH, CHECKER.V9_TESTS_RAW_SHA256),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                expected,
            )
        for path, expected in CHECKER.WAVE11_CONTROL_SHA256.items():
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
        self.assertEqual(candidate["schemaVersion"], "10.0")
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

    def test_03_exact_317_input_composition_and_hashes(self):
        inputs = self.candidate["inputSet"]
        rows = inputs["sourceBindings"]
        expected_counts = {
            "heldSourceInputCount": 317,
            "resourceCount": 316,
            "modCount": 158,
            "zipCount": 158,
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
            "uniqueModuleVersionTupleCount": 158,
            "aggregateRawByteSize": 287_352_740,
        }
        for key, value in expected_counts.items():
            self.assertEqual(inputs[key], value, key)
        self.assertEqual(len(rows), 317)
        self.assertEqual(len({row["path"] for row in rows}), 317)
        self.assertEqual(
            inputs["combinedInputSetSha256"],
            CHECKER.V10_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(CHECKER.wave11_digest_bytes(rows)).hexdigest(),
            CHECKER.V10_SOURCE_BINDINGS_SHA256,
        )
        pair_orders = sorted(
            {
                row["tupleOrder"]
                for row in rows
                if row["kind"] != "root_zip"
            }
        )
        self.assertEqual(pair_orders, list(range(1, 159)))
        self.assertEqual(
            sorted(
                {
                    row["tupleOrder"]
                    for row in rows
                    if row["wave"] == "wave11"
                }
            ),
            list(range(150, 159)),
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
                CHECKER.V10_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
            ),
            (159, 59_494, 1_098_221_637, 1_098_221_637),
        )
        self.assertEqual(
            (
                verification["directFullInputReconstructionCount"],
                verification["inheritedFullInputReconstructionCount"],
                verification["totalFullInputReconstructionCount"],
            ),
            (2, 16, 18),
        )
        self.assertEqual(
            (
                counters["directFullSourceReconstructionCount"],
                counters["inheritedFullSourceReconstructionCount"],
                counters["totalFullSourceReconstructionCount"],
            ),
            (2, 16, 18),
        )
        self.assertEqual(
            (
                counters["directArchiveOpenCount"],
                counters["inheritedArchiveOpenCount"],
                counters["totalArchiveOpenCount"],
                counters["archiveOpenCount"],
            ),
            (318, 1_666, 1_984, 1_984),
        )
        self.assertEqual(
            verification["underlyingIndependentGraphAlgorithmCount"],
            36,
        )
        self.assertEqual(verification["hardenedCheckerModuleCount"], 9)
        self.assertEqual(verification["providerFacadeLoadCount"], 9)
        self.assertEqual(counters["heldTerminalEvidenceCount"], 73)
        self.assertEqual(counters["heldAuxiliaryEvidenceCount"], 3)
        self.assertEqual(counters["heldToolInputCount"], 9)
        self.assertEqual(counters["transitiveDistinctToolPathCount"], 11)
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
        self.assertTrue(verification["pinnedV9PredecessorExecuted"])
        self.assertEqual(
            verification["v9TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(verification["v9TestsLiveHeld"])
        self.assertTrue(
            verification[
                "wave11HistoricalExact36FrozenSnapshotDescriptorSetBound"
            ]
        )
        self.assertTrue(
            verification["wave11LiveTerminalControlMetadataVerified"]
        )
        self.assertTrue(
            verification["wave11LiveFinalAndAcceptedInventoriesVerified"]
        )
        self.assertTrue(
            verification["wave11CompletionAppliesToRetainedSnapshot"]
        )
        self.assertFalse(
            verification[
                "wave11CurrentPathIdentityGuaranteedThroughManifestPublication"
            ]
        )
        self.assertFalse(
            verification[
                "wave11SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ]
        )
        self.assertEqual(
            predecessor["v9TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(predecessor["v9TestsLiveHeld"])

    def test_06_wave11_terminal_resources_are_exact(self):
        with held_wave11_documents() as (v4, runner, documents):
            resources = CHECKER.wave11_request_resources(
                v4,
                runner,
                documents,
            )
            snapshot = documents[CHECKER.WAVE11_READBACK_PERMIT_PATH][
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
            verified_resources = documents[CHECKER.WAVE11_READBACK_PATH][
                "verified"
            ]["resources"]
        self.assertEqual(len(resources), 18)
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
            EXPECTED_WAVE11_RESOURCE_IDENTITY,
        )
        self.assertEqual(
            [
                (row["path"], row["rawSha256"])
                for row in frozen_rows
            ],
            EXPECTED_WAVE11_FROZEN_PATH_RAWS,
        )
        self.assertEqual(len(EXPECTED_WAVE11_FROZEN_PATH_RAWS), 36)
        self.assertEqual(
            (
                sum(row["kind"] == "mod" for row in resources),
                sum(row["kind"] == "zip" for row in resources),
            ),
            (9, 9),
        )
        self.assertEqual(
            [row["order"] for row in resources],
            list(range(1, 19)),
        )
        self.assertEqual(
            sorted({row["tupleOrder"] for row in resources}),
            list(range(150, 159)),
        )
        self.assertEqual(
            sum(row["maximumBytes"] for row in resources),
            16_363_894,
        )
        self.assertEqual(
            {
                row["acceptedFileName"]
                for row in verified_resources
                if row["kind"] == "zip"
                and row["rootGoModPresent"] is False
            },
            EXPECTED_WAVE11_FALSE_ROOT_GO_MOD_FILES,
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
            ) = value
            v9, v8, v7, v6, v5, v4, v1, runner = chain
            rows = CHECKER.combined_source_bindings(
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
            )
            projection = v1.source_projection(rows)
        self.assertEqual((len(controls), len(auxiliary)), (73, 3))
        self.assertEqual(len(rows), 317)
        self.assertEqual(
            hashlib.sha256(
                runner.canonical_json_bytes(projection)
            ).hexdigest(),
            CHECKER.V10_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                CHECKER.wave11_digest_bytes(projection)
            ).hexdigest(),
            CHECKER.V10_SOURCE_BINDINGS_SHA256,
        )

    def test_08_unknown_authority_and_tool_pin_fail_closed(self):
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_PERMIT_PATH][
                "authority"
            ].__setitem__("unknownAuthority", False),
            "E_WAVE11_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_DECISION_PATH][
                "toolBindings"
            ][0].__setitem__("normalizedSha256", "0" * 64),
            "E_WAVE11_DECISION",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "toolBindings"
            ][2].__setitem__("rawSha256", "0" * 64),
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_DECISION_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE11_DECISION",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE11_READBACK",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_MANIFEST_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE11_READBACK_MANIFEST",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionReceipt"].__setitem__("rawSha256", "0" * 64),
            "E_WAVE11_READBACK_PERMIT",
        )
        for key in ("acquisitionClaim", "evidence"):
            assert_wave11_mutation_fails(
                self,
                lambda docs, target=key: docs[
                    CHECKER.WAVE11_READBACK_PERMIT_PATH
                ]["frozenAcquisitionSnapshot"][target].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
                "E_WAVE11_READBACK_PERMIT",
            )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PATH][
                "readbackClaim"
            ].__setitem__("rawSha256", "0" * 64),
            "E_WAVE11_READBACK",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_MANIFEST_PATH][
                "receipt"
            ].__setitem__("rawSha256", "0" * 64),
            "E_WAVE11_READBACK_MANIFEST",
        )

    def test_08_each_wave11_accepted_raw_binding_tamper_fails_closed(self):
        with held_wave11_documents() as (v4, runner, documents):
            accepted = documents[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"]
            self.assertEqual(len(accepted), 18)
            for index in range(18):
                mutated = copy.deepcopy(documents)
                mutated[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["acceptedDirectory"]["files"][index]["rawSha256"] = "0" * 64
                with (
                    self.subTest(accepted_raw_index=index),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave11_content_bindings",
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave11_request_resources(v4, runner, mutated)
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE11_READBACK_PERMIT",
                )

    def test_09_stale_v9_and_wave10_cardinality_fail_closed(self):
        def substitute_resource_same_cardinality(documents):
            rows = documents[CHECKER.WAVE11_PERMIT_PATH][
                "requestContract"
            ]["resources"]
            rows[0] = copy.deepcopy(rows[2])

        def substitute_authority_same_cardinality(documents):
            rows = documents[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionAuthority"]
            rows[0] = copy.deepcopy(rows[1])

        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_DECISION_PATH][
                "heldSourceInputSet"
            ].__setitem__("sourceBindingCount", 277),
            "E_WAVE11_DECISION",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_DECISION_PATH][
                "identityResolution"
            ].__setitem__("tupleCount", 11),
            "E_WAVE11_DECISION",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_PERMIT_PATH][
                "requestContract"
            ].__setitem__("requestCount", 22),
            "E_WAVE11_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFileCount", 40),
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"].__setitem__("exactFileCount", 22),
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("acceptedResourceCount", 22),
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"][0].__setitem__(
                "rawSha256",
                "0" * 64,
            ),
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            substitute_resource_same_cardinality,
            "E_WAVE11_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            substitute_authority_same_cardinality,
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFilesCanonicalSha256", "0" * 64),
            "E_WAVE11_READBACK_PERMIT",
        )

    def test_10_selected_tuple_and_live_hold_overclaim_fail_closed(self):
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_DECISION_PATH][
                "identityResolution"
            ].__setitem__("graphSelectedTupleCount", 1),
            "E_WAVE11_DECISION",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", [17, 18]),
            "E_WAVE11_READBACK",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", [21, 22]),
            "E_WAVE11_READBACK",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "verificationContract"
            ].__setitem__("v9TestsLiveHeld", False),
            "E_WAVE11_READBACK_PERMIT",
        )

    def test_10_all_wave11_selectors_and_false_root_mods_are_exact(self):
        with held_wave11_documents() as (v4, runner, documents):
            baseline = documents[CHECKER.WAVE11_PERMIT_PATH][
                "requestContract"
            ]["resources"]
            verified = documents[CHECKER.WAVE11_READBACK_PATH]["verified"][
                "resources"
            ]
            self.assertEqual(len(baseline), 18)
            self.assertTrue(
                all(
                    row["selectedByGraphAlgorithm"] is False
                    for row in baseline
                )
            )
            false_root_indexes = [
                index
                for index, row in enumerate(verified)
                if row["kind"] == "zip"
                and row["rootGoModPresent"] is False
            ]
            self.assertEqual(false_root_indexes, [9, 17])

            selector_collections = (
                (
                    "permit_resource",
                    18,
                    lambda docs: docs[CHECKER.WAVE11_PERMIT_PATH][
                        "requestContract"
                    ]["resources"],
                ),
                (
                    "source_request",
                    18,
                    lambda docs: docs[CHECKER.WAVE11_DECISION_PATH][
                        "sourceAcquisitionPreparation"
                    ]["requestSet"],
                ),
                (
                    "identity_tuple",
                    9,
                    lambda docs: docs[CHECKER.WAVE11_DECISION_PATH][
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
                            rebind_wave11_selector_hashes(runner, mutated)
                        )
                        with (
                            self.subTest(
                                selector_location=location,
                                selector_index=index,
                                value=case_value,
                            ),
                            mock.patch.object(
                                CHECKER,
                                "verify_wave11_content_bindings",
                            ),
                            mock.patch.object(
                                CHECKER,
                                "WAVE11_PERMIT_RESOURCES_SHA256",
                                resources_sha256,
                            ),
                            mock.patch.object(
                                CHECKER,
                                "WAVE11_REQUEST_SET_SHA256",
                                request_set_sha256,
                            ),
                            self.assertRaises(
                                CHECKER.CombinedCheckFailure,
                            ) as caught,
                        ):
                            CHECKER.wave11_request_resources(
                                v4,
                                runner,
                                mutated,
                            )
                        self.assertEqual(
                            str(caught.exception),
                            "E_WAVE11_RESOURCE",
                        )

            for index in false_root_indexes:
                mutated = copy.deepcopy(documents)
                mutated[CHECKER.WAVE11_READBACK_PATH]["verified"][
                    "resources"
                ][index]["rootGoModPresent"] = True
                with (
                    self.subTest(root_go_mod_index=index),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave11_content_bindings",
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave11_request_resources(v4, runner, mutated)
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE11_RESOURCE",
                )

    def test_11_post_success_reporting_contract_is_pinned(self):
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH][
                "verificationContract"
            ]["postSuccessReportingFailure"].__setitem__(
                "retryAllowed",
                True,
            ),
            "E_WAVE11_READBACK_PERMIT",
        )
        assert_wave11_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE11_READBACK_PERMIT_PATH].__setitem__(
                "recorderNormalizedSha256",
                "0" * 64,
            ),
            "E_WAVE11_READBACK_PERMIT",
        )

    def test_12_terminal_modes_sizes_and_namespace_are_live(self):
        with held_wave11_documents(include_held=True) as (
            _,
            _,
            documents,
            held,
        ):
            CHECKER.validate_wave11_completed_namespace(held, documents)
            for path, (size, mode) in CHECKER.WAVE11_CONTROL_METADATA.items():
                info = os.fstat(held.files[path].fd)
                self.assertEqual(info.st_size, size)
                self.assertEqual(stat.S_IMODE(info.st_mode), mode)
                self.assertEqual(info.st_nlink, 1)

    def test_13_legacy_wave9_compatibility_remains_exact_and_bounded(self):
        with held_all_documents() as value:
            chain = value[0]
            d9 = value[-3]
            _, v8, _, _, _, v4, _, runner = chain
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
        self.assertEqual(len(compile_calls), 5)
        self.assertEqual(len(exec_calls), 5)
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
        self.assertEqual(value["schemaVersion"], "10.0")
        self.assertEqual(value["status"], "verification_failed")
        self.assertFalse(value["externalAuthenticationRequired"])
        self.assertFalse(value["userActionRequired"])

    def test_17_v9_predecessor_is_exact_and_mutations_fail_closed(self):
        predecessor = self.predecessor_candidate
        self.assertEqual(
            predecessor["contentBinding"]["sha256"],
            CHECKER.V9_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            predecessor["inputSet"]["combinedInputSetSha256"],
            CHECKER.V9_INPUT_SET_SHA256,
        )
        self.assertEqual(
            predecessor["graphDiscovery"]["graphSha256"],
            CHECKER.V9_GRAPH_SHA256,
        )
        self.assertEqual(
            predecessor["derivedResult"]["frontierSha256"],
            CHECKER.V9_FRONTIER_SHA256,
        )
        self.assertEqual(
            predecessor["checkerVerification"]["v8TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(
            predecessor["checkerVerification"]["v8TestsLiveHeld"]
        )
        with held_wave11_documents() as (_, runner, documents):
            decision = documents[CHECKER.WAVE11_DECISION_PATH]
            verified = CHECKER.validate_v9_predecessor_candidate(
                runner,
                predecessor,
                decision,
            )
            self.assertEqual(
                verified["candidateContentSha256"],
                CHECKER.V9_CANDIDATE_CONTENT_SHA256,
            )
            stale_key_decision = copy.deepcopy(decision)
            stale_key_decision["predecessorBindings"][
                "combinedFixedPointV8"
            ] = stale_key_decision["predecessorBindings"].pop(
                "combinedFixedPointV9"
            )
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.validate_v9_predecessor_candidate(
                    runner,
                    predecessor,
                    stale_key_decision,
                )
            self.assertEqual(str(caught.exception), "E_V9_PREDECESSOR")
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
                        "combinedFixedPointV9"
                    ][key] = "0" * 64
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v9_predecessor_candidate(
                            runner,
                            predecessor,
                            mutated_decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V9_PREDECESSOR",
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
                    1_665,
                ),
            ]
            for index, mutate in enumerate(candidate_mutations):
                with self.subTest(predecessor_candidate=index):
                    mutated_candidate = copy.deepcopy(predecessor)
                    mutate(mutated_candidate)
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v9_predecessor_candidate(
                            runner,
                            mutated_candidate,
                            decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V9_PREDECESSOR",
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
            for version in range(1, 11)
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
        self.assertNotIn(CHECKER.V9_TESTS_PATH, self.actual_python_open_paths)
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
                "validate_wave11_completed_namespace",
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
        class V9:
            TRANSITIVE_CHECKER_PATHS = {
                (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                    f"v{version}.py"
                )
                for version in range(1, 9)
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
                V9,
                self.predecessor_candidate,
                direct_bindings,
                direct_inputs,
            )
        )
        self.assertEqual(len(direct_paths), 9)
        self.assertEqual(len(transitive_paths), 11)

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
                    V9,
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
                V9,
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
                    V9,
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


class CombinedFixedPointV10FastBoundaryTests(unittest.TestCase):
    def test_aggregate_uncompressed_limit_minus_one_is_rejected(self):
        aggregate_bytes = (
            CHECKER.V10_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
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
            v4 = chain[5]
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
