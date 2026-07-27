#!/usr/bin/env python3
"""Focused tests for the exact read-only 299-input combined v9 checker."""

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
            "combined fixed-point v9 tests require unoptimized "
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
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_combined_fixed_point_v9.py"


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "combined_fixed_point_v9_tests_target",
        CHECKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("checker load failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()

EXPECTED_SELF_NORMALIZED_SHA256 = (
    "b4cdbfd385e0606fa2ca37017983bd80b6856dd69dfafb46df6579e76c618684"
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
        "role": "current_v9_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v9.py",
        "normalizedSha256": EXPECTED_SELF_NORMALIZED_SHA256,
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
EXPECTED_WAVE10_RESOURCE_IDENTITY = [
    (
        1, 139, "mod", "golang.org/x/crypto", "v0.42.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/001-5d152fd915392fd2a5b5.mod",
        "68845acdeae2efec8dcf23dca9c759c0328cbaec288e2a2565d9eb7f70e00eb7",
    ),
    (
        2, 139, "zip", "golang.org/x/crypto", "v0.42.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/001-5d152fd915392fd2a5b5.zip",
        "dd13a44ed4e46d97aebf16b3bb654323f199c3bb37b9484e0104a5e537721c71",
    ),
    (
        3, 140, "mod", "golang.org/x/net",
        "v0.0.0-20190620200207-3b0461eec859",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/002-ef7a0a4d5e9b983df87c.mod",
        "e6efdaf78a29503f080cf6d2615e289cfb1d9e3ab7d570f53668eca2b4ab41da",
    ),
    (
        4, 140, "zip", "golang.org/x/net",
        "v0.0.0-20190620200207-3b0461eec859",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/002-ef7a0a4d5e9b983df87c.zip",
        "8b437b88ece68e61336150fbdd2a4c0e8d80f143bcdc86ce4ef047c4c93f3caa",
    ),
    (
        5, 141, "mod", "golang.org/x/net",
        "v0.0.0-20210226172049-e18ecbb05110",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/003-82364176d91c7e0dfbf1.mod",
        "fef5896d103a0bce5055fdb5e96e830944334792437865347718edceb633348a",
    ),
    (
        6, 141, "zip", "golang.org/x/net",
        "v0.0.0-20210226172049-e18ecbb05110",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/003-82364176d91c7e0dfbf1.zip",
        "17ae555c0bec70b583d84ec7a099db3fdc5b3b688cb2814f8c388d174e7ada15",
    ),
    (
        7, 142, "mod", "golang.org/x/sync",
        "v0.0.0-20190423024810-112230192c58",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/004-253ee61bed5449c9f94f.mod",
        "421f6139686d5891f3dc5a563d0995780d3279f65cad4d225cea52686794161c",
    ),
    (
        8, 142, "zip", "golang.org/x/sync",
        "v0.0.0-20190423024810-112230192c58",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/004-253ee61bed5449c9f94f.zip",
        "dc105c2b4d6c7ab48e54946ce2f624e8d1f5d47270eff1e88fed06cc65f91fb4",
    ),
    (
        9, 143, "mod", "golang.org/x/sys",
        "v0.0.0-20210615035016-665e8c7367d1",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/005-ce062f853b3e2f943440.mod",
        "f033333096fe198f3151deed93f2deba74e50bbfe7739134045bc3b7ce4a5024",
    ),
    (
        10, 143, "zip", "golang.org/x/sys",
        "v0.0.0-20210615035016-665e8c7367d1",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/005-ce062f853b3e2f943440.zip",
        "0d25c11d65a4ac84a6e2c3bd56a6afeb1da3923d2752a5aa59b7e99a94359fcb",
    ),
    (
        11, 144, "mod", "golang.org/x/term",
        "v0.0.0-20201126162022-7de9c90e9dd1",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/006-834e41a3e70906cfb6c2.mod",
        "4cbab14f7706771b271d995a1b3cc131fe5a246aadc7ee6d1ba6f0bd894781fa",
    ),
    (
        12, 144, "zip", "golang.org/x/term",
        "v0.0.0-20201126162022-7de9c90e9dd1",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/006-834e41a3e70906cfb6c2.zip",
        "475a86f11dd148b474ce405c5dbdd5f6bcae056c3e44e52445a45926dd69a552",
    ),
    (
        13, 145, "mod", "golang.org/x/term", "v0.35.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/007-402a22726fd998461a52.mod",
        "c210e4c5cb0c2f3a1fc3f64588acc627cbf8bbf8ce29e578a387e9ed8456c4fc",
    ),
    (
        14, 145, "zip", "golang.org/x/term", "v0.35.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/007-402a22726fd998461a52.zip",
        "ec4f6a729019902f333d2e6f40cd6160a63e1f7fa0d3f4c233e899d9aaec2db6",
    ),
    (
        15, 146, "mod", "golang.org/x/text", "v0.29.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/008-3477722dbaf554a645bd.mod",
        "b57bcc7ffdfddb1b8235f77262bf41422c75d72dda5a145543cc36bccac43ad3",
    ),
    (
        16, 146, "zip", "golang.org/x/text", "v0.29.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/008-3477722dbaf554a645bd.zip",
        "fb47744565fd36da42ab2ebd3ee4db0038dfed4f703c926a9e7327debab8af77",
    ),
    (
        17, 147, "mod", "golang.org/x/text", "v0.3.3",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/009-c6eaa7316993afbcb5cb.mod",
        "fbb7a88ed140515e790eca7a10ffd319c9786b11c6a6c7e59f80f7fb37bb4542",
    ),
    (
        18, 147, "zip", "golang.org/x/text", "v0.3.3",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/009-c6eaa7316993afbcb5cb.zip",
        "8a896da346baf94ab4f24b0e396df0b79393c93aa05c50ef07cddd561a1ff8d7",
    ),
    (
        19, 148, "mod", "golang.org/x/tools", "v0.36.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/010-a2764930729cea661be3.mod",
        "53792e623827ef40be8f1af36dcf12790e82780b3d33b4b0944f56a3584bc429",
    ),
    (
        20, 148, "zip", "golang.org/x/tools", "v0.36.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/010-a2764930729cea661be3.zip",
        "85b486030e995cd5b4d56dea92f247b32bf4e0ae2fe6816b29d4514b5a43fec8",
    ),
    (
        21, 149, "mod", "golang.org/x/xerrors",
        "v0.0.0-20190717185122-a985d3407aa7",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/011-4638677582e2455c59ce.mod",
        "aa5e3ec9bb7b9f681609efac019d9de1a7ba7719248ff1eaa27e78882db3d7f5",
    ),
    (
        22, 149, "zip", "golang.org/x/xerrors",
        "v0.0.0-20190717185122-a985d3407aa7",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "accepted/011-4638677582e2455c59ce.zip",
        "c4e9f063cfed546c90f00a9657deac4f915a8994f8cbe6dbd3f18e79eb8302cf",
    ),
]
EXPECTED_WAVE10_FROZEN_PATH_RAWS = [
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-identity-and-acquisition-decision-"
        "wave10-v1.json",
        "d1c23056487d88b92f1f2fd105d219abd029079590b379f7a671317b4158b6eb",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-identity-and-acquisition-decision-"
        "wave10-v1.md",
        "700a0ae5d4067806cfbad2f8efd6439f272c1d02e5311da7e60d153cf2d85caa",
    ),
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave10_decision_v1.py",
        "e7c3aabac84dd14f33b77b777730eb95bcd4160b6886645698ccad9060defebc",
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave10_decision_v1.py",
        "9336e06a6fde88ad382a0cd54176d3cf3807c3a51c215769659c4fb7e199b9a4",
    ),
    (
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v8.py",
        "798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32",
    ),
    (
        "script/test_p2p_nat_g2_pion_combined_fixed_point_v8.py",
        "347a1e0083d2daedb40deba5fca491b63ee3137b5a7c18a56886be694ded16a0",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave10-execution-permit-v1.md",
        "25b5a7cee6b0c9b4ddd633d39ed000b03a85a795b74770ecf0b28e08c4884074",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave10-execution-permit-v1.json",
        "841d30e43ce839662baab07d0f47f39cfe9c52d2b4d3757e2066a128452a6c93",
    ),
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave10_acquisition_v1.py",
        "fe39b88609bbca78461bf7db416cb311143371d68ebab176703bbc2c7a81eaec",
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave10_acquisition_v1.py",
        "fe4d7372b82f9fd4e50529ab4a17076ed3787ec2f663512476b846de6f6e0c3c",
    ),
    (
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave10_v1_once.py",
        "5395afdaff0d928e786d3e7fb50cea46bf83dd78e57865196813ca1d080546b3",
    ),
    (
        "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave10_v1_once.py",
        "5aa7f30a6debda432577227e86f0b933b7d668732141d78d3cf9c0a150bad747",
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
        "build/offline-source/pion-ice-v4.3.0/dependencies/"
        ".wave-10-v1.claim",
        "5260f5d7e7473013871573717848a3e8eae868a47ab2bfe538340d681ec4a6de",
    ),
    (
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-10-v1/"
        "evidence.json",
        "0b3700d12d11d334e91c95dfd561d43aa8827294ab9caee0b21258ded48cf9de",
    ),
    *[
        (
            path,
            raw_sha256,
        )
        for _, _, _, _, _, path, raw_sha256
        in EXPECTED_WAVE10_RESOURCE_IDENTITY
    ],
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave10-receipt-v1.json",
        "49f4aab3f71e52631aa48ac34ba7ee2a1ef3613814b06e87095ef75c3adaa1a1",
    ),
    (
        "docs/security-hardening/production-p2p-nat-v1/"
        "g2-pion-restricted-fork-v1/rung-three/"
        "bounded-dependency-source-acquisition-wave10-manifest-v1.json",
        "3f1f178d3bd48b3b8d8792ae1be57716aacd7cba16f526afccfca3d4b998643c",
    ),
]
EXPECTED_CHECKER_RAW_SHA256 = (
    "c0f098cf0a047c4d1aca03f5b7f16f327306b56ed8e656d67afe32503eb117da"
)
EXPECTED_CHECKER_CALL_COUNT = 1_253
EXPECTED_CHECKER_CALL_SURFACE_SHA256 = (
    "e2e938b1e274e2457c45dd7c9951086875450571bfe657fdd79ca4800f2292cd"
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
    if (compile_count, exec_count) != (4, 4):
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
        v8 = CHECKER.harden_checker_module(
            CHECKER.load_v8_checker(held_v8)
        )
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
                yield v8, v7, v6, v5, v4, v1, runner


@contextmanager
def held_wave10_documents(*, include_held=False):
    with held_toolchain() as chain:
        v8, v7, v6, v5, v4, v1, runner = chain
        bindings = (
            CHECKER.wave10_control_bindings()
            + CHECKER.wave10_auxiliary_evidence_bindings()
        )
        with runner.HeldInputSet(ROOT, bindings) as held:
            documents = CHECKER.parse_wave10_documents(runner, held)
            if include_held:
                yield v4, runner, documents, held
            else:
                yield v4, runner, documents


@contextmanager
def held_all_documents():
    with held_toolchain() as chain:
        v8, v7, v6, v5, v4, v1, runner = chain
        controls = (
            v1.control_bindings()
            + v4.wave3_control_bindings()
            + v4.wave4_control_bindings()
            + v4.wave5_control_bindings()
            + v5.wave6_control_bindings()
            + v6.wave7_control_bindings()
            + v7.wave8_control_bindings()
            + v8.wave9_control_bindings()
            + CHECKER.wave10_control_bindings()
        )
        auxiliary = CHECKER.wave10_auxiliary_evidence_bindings()
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
                CHECKER.parse_wave10_documents(runner, held),
            )


def assert_wave10_mutation_fails(
    testcase: unittest.TestCase,
    mutate,
    expected_code: str,
) -> None:
    with held_wave10_documents() as (v4, runner, documents):
        mutated = copy.deepcopy(documents)
        mutate(mutated)
        with (
            mock.patch.object(
                CHECKER,
                "verify_wave10_content_bindings",
            ),
            testcase.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught,
        ):
            CHECKER.wave10_request_resources(v4, runner, mutated)
    testcase.assertEqual(str(caught.exception), expected_code)


class CombinedFixedPointV9Tests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        original_load_v8 = CHECKER.load_v8_checker
        original_derive_tool_paths = CHECKER.derive_and_validate_tool_paths
        original_os_open = os.open
        cls.actual_python_open_paths = []

        def capturing_load_v8(held):
            module = original_load_v8(held)
            original_generate = module.generate_candidate

            def capturing_generate(root):
                value = original_generate(root)
                cls.predecessor_candidate = value
                return value

            module.generate_candidate = capturing_generate
            return module

        def capturing_derive_tool_paths(
            v8,
            predecessor_candidate,
            direct_tool_bindings,
            direct_tool_inputs,
        ):
            result = original_derive_tool_paths(
                v8,
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
                "load_v8_checker",
                side_effect=capturing_load_v8,
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
            (CHECKER.V8_CHECKER_PATH, CHECKER.V8_CHECKER_RAW_SHA256),
            (CHECKER.V8_TESTS_PATH, CHECKER.V8_TESTS_RAW_SHA256),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                expected,
            )
        for path, expected in CHECKER.WAVE10_CONTROL_SHA256.items():
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
        self.assertEqual(candidate["schemaVersion"], "9.0")
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

    def test_03_exact_299_input_composition_and_hashes(self):
        inputs = self.candidate["inputSet"]
        rows = inputs["sourceBindings"]
        expected_counts = {
            "heldSourceInputCount": 299,
            "resourceCount": 298,
            "modCount": 149,
            "zipCount": 149,
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
            "uniqueModuleVersionTupleCount": 149,
            "aggregateRawByteSize": 270_988_846,
        }
        for key, value in expected_counts.items():
            self.assertEqual(inputs[key], value, key)
        self.assertEqual(len(rows), 299)
        self.assertEqual(len({row["path"] for row in rows}), 299)
        self.assertEqual(
            inputs["combinedInputSetSha256"],
            CHECKER.V9_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(CHECKER.wave10_digest_bytes(rows)).hexdigest(),
            CHECKER.V9_SOURCE_BINDINGS_SHA256,
        )
        pair_orders = sorted(
            {
                row["tupleOrder"]
                for row in rows
                if row["kind"] != "root_zip"
            }
        )
        self.assertEqual(pair_orders, list(range(1, 150)))
        self.assertEqual(
            sorted(
                {
                    row["tupleOrder"]
                    for row in rows
                    if row["wave"] == "wave10"
                }
            ),
            list(range(139, 150)),
        )

    def test_04_reconstruction_and_archive_counters_are_not_stale(self):
        verification = self.candidate["checkerVerification"]
        counters = self.candidate["operationCounters"]
        self.assertEqual(
            (
                verification["directFullInputReconstructionCount"],
                verification["inheritedFullInputReconstructionCount"],
                verification["totalFullInputReconstructionCount"],
            ),
            (2, 14, 16),
        )
        self.assertEqual(
            (
                counters["directFullSourceReconstructionCount"],
                counters["inheritedFullSourceReconstructionCount"],
                counters["totalFullSourceReconstructionCount"],
            ),
            (2, 14, 16),
        )
        self.assertEqual(
            (
                counters["directArchiveOpenCount"],
                counters["inheritedArchiveOpenCount"],
                counters["totalArchiveOpenCount"],
                counters["archiveOpenCount"],
            ),
            (300, 1_366, 1_666, 1_666),
        )
        self.assertEqual(
            verification["underlyingIndependentGraphAlgorithmCount"],
            32,
        )
        self.assertEqual(verification["hardenedCheckerModuleCount"], 8)
        self.assertEqual(verification["providerFacadeLoadCount"], 8)
        self.assertEqual(counters["heldTerminalEvidenceCount"], 66)
        self.assertEqual(counters["heldAuxiliaryEvidenceCount"], 3)
        self.assertEqual(counters["heldToolInputCount"], 8)
        self.assertEqual(counters["transitiveDistinctToolPathCount"], 10)
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
        self.assertTrue(verification["pinnedV8PredecessorExecuted"])
        self.assertEqual(
            verification["v8TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(verification["v8TestsLiveHeld"])
        self.assertTrue(
            verification[
                "wave10HistoricalExact40FrozenSnapshotDescriptorSetBound"
            ]
        )
        self.assertTrue(
            verification["wave10LiveTerminalControlMetadataVerified"]
        )
        self.assertTrue(
            verification["wave10LiveFinalAndAcceptedInventoriesVerified"]
        )
        self.assertTrue(
            verification["wave10CompletionAppliesToRetainedSnapshot"]
        )
        self.assertFalse(
            verification[
                "wave10CurrentPathIdentityGuaranteedThroughManifestPublication"
            ]
        )
        self.assertFalse(
            verification[
                "wave10SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ]
        )
        self.assertEqual(
            predecessor["v8TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(predecessor["v8TestsLiveHeld"])

    def test_06_wave10_terminal_resources_are_exact(self):
        with held_wave10_documents() as (v4, runner, documents):
            resources = CHECKER.wave10_request_resources(
                v4,
                runner,
                documents,
            )
            snapshot = documents[CHECKER.WAVE10_READBACK_PERMIT_PATH][
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
        self.assertEqual(len(resources), 22)
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
            EXPECTED_WAVE10_RESOURCE_IDENTITY,
        )
        self.assertEqual(
            [
                (row["path"], row["rawSha256"])
                for row in frozen_rows
            ],
            EXPECTED_WAVE10_FROZEN_PATH_RAWS,
        )
        self.assertEqual(len(EXPECTED_WAVE10_FROZEN_PATH_RAWS), 40)
        self.assertEqual(
            (
                sum(row["kind"] == "mod" for row in resources),
                sum(row["kind"] == "zip" for row in resources),
            ),
            (11, 11),
        )
        self.assertEqual(
            [row["order"] for row in resources],
            list(range(1, 23)),
        )
        self.assertEqual(
            sorted({row["tupleOrder"] for row in resources}),
            list(range(139, 150)),
        )
        self.assertEqual(
            sum(row["maximumBytes"] for row in resources),
            27_773_526,
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
            ) = value
            v8, v7, v6, v5, v4, v1, runner = chain
            rows = CHECKER.combined_source_bindings(
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
            )
            projection = v1.source_projection(rows)
        self.assertEqual((len(controls), len(auxiliary)), (66, 3))
        self.assertEqual(len(rows), 299)
        self.assertEqual(
            hashlib.sha256(
                runner.canonical_json_bytes(projection)
            ).hexdigest(),
            CHECKER.V9_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                CHECKER.wave10_digest_bytes(projection)
            ).hexdigest(),
            CHECKER.V9_SOURCE_BINDINGS_SHA256,
        )

    def test_08_unknown_authority_and_tool_pin_fail_closed(self):
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_PERMIT_PATH][
                "authority"
            ].__setitem__("unknownAuthority", False),
            "E_WAVE10_PERMIT",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_DECISION_PATH][
                "toolBindings"
            ][0].__setitem__("normalizedSha256", "0" * 64),
            "E_WAVE10_DECISION",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "toolBindings"
            ][2].__setitem__("rawSha256", "0" * 64),
            "E_WAVE10_READBACK_PERMIT",
        )

    def test_09_stale_v8_and_wave9_cardinality_fail_closed(self):
        def substitute_resource_same_cardinality(documents):
            rows = documents[CHECKER.WAVE10_PERMIT_PATH][
                "requestContract"
            ]["resources"]
            rows[0] = copy.deepcopy(rows[2])

        def substitute_authority_same_cardinality(documents):
            rows = documents[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionAuthority"]
            rows[0] = copy.deepcopy(rows[1])

        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_DECISION_PATH][
                "heldSourceInputSet"
            ].__setitem__("sourceBindingCount", 257),
            "E_WAVE10_DECISION",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFileCount", 38),
            "E_WAVE10_READBACK_PERMIT",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"].__setitem__("exactFileCount", 20),
            "E_WAVE10_READBACK_PERMIT",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"][0].__setitem__(
                "rawSha256",
                "0" * 64,
            ),
            "E_WAVE10_READBACK_PERMIT",
        )
        assert_wave10_mutation_fails(
            self,
            substitute_resource_same_cardinality,
            "E_WAVE10_PERMIT",
        )
        assert_wave10_mutation_fails(
            self,
            substitute_authority_same_cardinality,
            "E_WAVE10_READBACK_PERMIT",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFilesCanonicalSha256", "0" * 64),
            "E_WAVE10_READBACK_PERMIT",
        )

    def test_10_selected_tuple_and_live_hold_overclaim_fail_closed(self):
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_DECISION_PATH][
                "identityResolution"
            ].__setitem__("graphSelectedTupleCount", 0),
            "E_WAVE10_DECISION",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", []),
            "E_WAVE10_READBACK",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", [20, 22]),
            "E_WAVE10_READBACK",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "verificationContract"
            ].__setitem__("v8TestsLiveHeld", False),
            "E_WAVE10_READBACK_PERMIT",
        )

    def test_11_post_success_reporting_contract_is_pinned(self):
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH][
                "verificationContract"
            ]["postSuccessReportingFailure"].__setitem__(
                "retryAllowed",
                True,
            ),
            "E_WAVE10_READBACK_PERMIT",
        )
        assert_wave10_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE10_READBACK_PERMIT_PATH].__setitem__(
                "recorderNormalizedSha256",
                "0" * 64,
            ),
            "E_WAVE10_READBACK_PERMIT",
        )

    def test_12_terminal_modes_sizes_and_namespace_are_live(self):
        with held_wave10_documents(include_held=True) as (
            _,
            _,
            documents,
            held,
        ):
            CHECKER.validate_wave10_completed_namespace(held, documents)
            for path, (size, mode) in CHECKER.WAVE10_CONTROL_METADATA.items():
                info = os.fstat(held.files[path].fd)
                self.assertEqual(info.st_size, size)
                self.assertEqual(stat.S_IMODE(info.st_mode), mode)
                self.assertEqual(info.st_nlink, 1)

    def test_13_legacy_wave9_compatibility_remains_exact_and_bounded(self):
        with held_all_documents() as value:
            chain = value[0]
            d9 = value[-2]
            v8, _, _, _, v4, _, runner = chain
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
        self.assertEqual(len(compile_calls), 4)
        self.assertEqual(len(exec_calls), 4)
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
        self.assertEqual(value["schemaVersion"], "9.0")
        self.assertEqual(value["status"], "verification_failed")
        self.assertFalse(value["externalAuthenticationRequired"])
        self.assertFalse(value["userActionRequired"])

    def test_17_v8_predecessor_is_exact_and_mutations_fail_closed(self):
        predecessor = self.predecessor_candidate
        self.assertEqual(
            predecessor["contentBinding"]["sha256"],
            CHECKER.V8_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            predecessor["inputSet"]["combinedInputSetSha256"],
            CHECKER.V8_INPUT_SET_SHA256,
        )
        self.assertEqual(
            predecessor["graphDiscovery"]["graphSha256"],
            CHECKER.V8_GRAPH_SHA256,
        )
        self.assertEqual(
            predecessor["derivedResult"]["frontierSha256"],
            CHECKER.V8_FRONTIER_SHA256,
        )
        self.assertEqual(
            predecessor["checkerVerification"]["v7TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertFalse(
            predecessor["checkerVerification"]["v7TestsLiveHeld"]
        )
        with held_wave10_documents() as (_, runner, documents):
            decision = documents[CHECKER.WAVE10_DECISION_PATH]
            verified = CHECKER.validate_v8_predecessor_candidate(
                runner,
                predecessor,
                decision,
            )
            self.assertEqual(
                verified["candidateContentSha256"],
                CHECKER.V8_CANDIDATE_CONTENT_SHA256,
            )
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
                        "combinedFixedPointV8"
                    ][key] = "0" * 64
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v8_predecessor_candidate(
                            runner,
                            predecessor,
                            mutated_decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V8_PREDECESSOR",
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
                    1_365,
                ),
            ]
            for index, mutate in enumerate(candidate_mutations):
                with self.subTest(predecessor_candidate=index):
                    mutated_candidate = copy.deepcopy(predecessor)
                    mutate(mutated_candidate)
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v8_predecessor_candidate(
                            runner,
                            mutated_candidate,
                            decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V8_PREDECESSOR",
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
            for version in range(1, 10)
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
        self.assertNotIn(CHECKER.V8_TESTS_PATH, self.actual_python_open_paths)
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
                "validate_wave10_completed_namespace",
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
        class V8:
            TRANSITIVE_CHECKER_PATHS = {
                (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                    f"v{version}.py"
                )
                for version in range(1, 8)
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
                V8,
                self.predecessor_candidate,
                direct_bindings,
                direct_inputs,
            )
        )
        self.assertEqual(len(direct_paths), 8)
        self.assertEqual(len(transitive_paths), 10)

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
                    V8,
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
                V8,
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
                    V8,
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
            with (
                self.subTest(mutation=name),
                self.assertRaises(StaticSurfaceFailure) as caught,
            ):
                validate_checker_static_surface(
                    f"{source}\n{suffix}"
                )
            self.assertEqual(caught.exception.code, expected_code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
