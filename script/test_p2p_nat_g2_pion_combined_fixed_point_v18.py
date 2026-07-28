#!/usr/bin/env python3
"""Focused tests for the exact read-only 369-source combined v18 checker."""

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
            "combined fixed-point v18 tests require unoptimized "
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
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "script/check_p2p_nat_g2_pion_combined_fixed_point_v18.py"


def load_checker():
    raw = CHECKER_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_CHECKER_RAW_SHA256:
        raise RuntimeError("checker raw preload gate failed")
    marker = re.compile(
        br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
    )
    normalized, count = marker.subn(
        rb"\g<1>" + b"0" * 64 + rb"\g<2>",
        raw,
    )
    if (
        count != 1
        or hashlib.sha256(normalized).hexdigest()
        != EXPECTED_SELF_NORMALIZED_SHA256
    ):
        raise RuntimeError("checker normalized preload gate failed")
    source = raw.decode("utf-8")
    validate_checker_static_surface(source)
    module = types.ModuleType("combined_fixed_point_v18_tests_target")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(CHECKER_PATH),
            "__loader__": None,
            "__name__": "combined_fixed_point_v18_tests_target",
            "__package__": None,
        }
    )
    code = compile(
        raw,
        str(CHECKER_PATH),
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    exec(code, module.__dict__, module.__dict__)
    return module


CHECKER = None

UNRESOLVED_SHA256 = "0" * 64
EXPECTED_SELF_NORMALIZED_SHA256 = (
    "b53fa66b34a8379216d64892502bb352220397c598cbe0b84911ca641b9e40aa"
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
        "role": "current_v18_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v18.py",
        "normalizedSha256": EXPECTED_SELF_NORMALIZED_SHA256,
    },
    {
        "role": "immutable_v17_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v17.py",
        "rawSha256":
            "32df9bd1bf9b4b6610a2a74038956eab7e51c506198c11f45fa5058968caacb8",
        "normalizedSha256":
            "d2ebef7f9aad384b08a68c438320de882d640a859a7d35521853818afbcdd7ce",
    },
    {
        "role": "immutable_v16_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v16.py",
        "rawSha256":
            "2e388d466c5346fa6f82b7fd23fa6dca24009acadacdd62f1fe2ba25b0a10879",
        "normalizedSha256":
            "7dd2c81a2032a374192f7c502afc65305d97f7c1e3699654e416b60bf64c6bd5",
    },
    {
        "role": "immutable_v15_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v15.py",
        "rawSha256":
            "e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5",
        "normalizedSha256":
            "63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7",
    },
    {
        "role": "immutable_v14_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v14.py",
        "rawSha256":
            "bf729f8dbfc0508fa977893eb1c7c30e07d15fa751a29856d4c4d386f1001292",
        "normalizedSha256":
            "8be3cf62cc66c2aaf780c658acf5b6e242fcbd52e44dd6fd90a11e3eeba505ec",
    },
    {
        "role": "immutable_v13_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v13.py",
        "rawSha256":
            "0b0ea7d68ef5fc11b8c0defe56bf443c681a6952a27e2c9b6c41d9702241a80b",
        "normalizedSha256":
            "73a778e53bdc1d15ffd34109ff02297e85eb6a91b52d1577acefe9bc1383e674",
    },
    {
        "role": "immutable_v12_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v12.py",
        "rawSha256":
            "cc693cb0126267962813a418a53ece371aec0172d24a75ea70cf6dbe89a1db45",
        "normalizedSha256":
            "cfcf095861bd753e3cfb7521e339e2bb5a3e59b5a75258ff5b8ee5cfc8ba43f2",
    },
    {
        "role": "immutable_v11_combined_checker",
        "path": "script/check_p2p_nat_g2_pion_combined_fixed_point_v11.py",
        "rawSha256":
            "d330a2f7dd4f12bd4f972e6c34749e10701c594cad75308ccc7de4d3e6aba176",
        "normalizedSha256":
            "1ef7c9fb874c33b8b25c02f0024e6d85e3df070718c0de9861c60173697af82e",
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
EXPECTED_WAVE19_RESOURCE_IDENTITY = [
    (
        1, 183, "mod",
        "golang.org/x/crypto", "v0.38.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/001-a26a2513c9f4c49c479c.mod",
        "e9c23d3613ad3c29e18552f90d02798b7295419dd47d4f667d5843d7dc1673b3",
    ),
    (
        2, 183, "zip",
        "golang.org/x/crypto", "v0.38.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/001-a26a2513c9f4c49c479c.zip",
        "02824dd62fa3241946a2ac14fdadbd393514d76cebbfbd8bddcddbfc80c7f94b",
    ),
    (
        3, 184, "mod",
        "golang.org/x/text", "v0.25.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/002-c6022d5be99f60f2428e.mod",
        "8133f6f3b232cb388b50d1c74be92f39198cbd62e3b0991c917cdbc1322bbe14",
    ),
    (
        4, 184, "zip",
        "golang.org/x/text", "v0.25.0",
        "build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/002-c6022d5be99f60f2428e.zip",
        "3f218b1dd9a690036d1226f46f142fc7ae3cc9cd4f28610b96bb8080b7e194c9",
    ),
]
EXPECTED_WAVE19_FALSE_ROOT_GO_MOD_FILES = set()
EXPECTED_WAVE19_FROZEN_PATH_RAWS = [
    ("docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave19-v1.json", "7486a8a4659459ce49128bcf05501abb065f2b64c542715eaebd3c1ca686a8cf"),
    ("docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave19-v1.md", "3aefdd1e3a283e099ad4a3624103461eee821043ad4bf18a57a39c81b100d526"),
    ("script/check_p2p_nat_g2_pion_rung3_dependency_wave19_decision_v1.py", "cd6926a344b52fafd0265ec8bd1f08cbdf250826fa53e46e6c5a3e94049f0d92"),
    ("script/test_p2p_nat_g2_pion_rung3_dependency_wave19_decision_v1.py", "2bd972108f75739be378c20544eaa518425ad875156cf83065f27fb34d2a47d2"),
    ("script/check_p2p_nat_g2_pion_combined_fixed_point_v17.py", "32df9bd1bf9b4b6610a2a74038956eab7e51c506198c11f45fa5058968caacb8"),
    ("script/test_p2p_nat_g2_pion_combined_fixed_point_v17.py", "3403ec05b1f6a9561a74a44b001352230d0d68db72789403f6155785f01588f0"),
    ("build/offline-source/pion-ice-v4.3.0/dependencies/.wave-18-v1.claim", "08f5134ce03805e512c2dec0dee13251ce682d793d2b87f7f8e29f6d3426d362"),
    ("docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave19-execution-permit-v1.md", "5bca347cbe948bc82912464aca23b43e8d0323204ad33289ed8d42be3ddec977"),
    ("docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave19-execution-permit-v1.json", "ea80d045fb13042f2c673dcd3363a46aaf4bc81ffbe65af53e9ecd65b1369a3e"),
    ("script/check_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py", "9fc0b1eae88a029ae3f3c180acdfbb2f296736c8745cebc75248efe3aa2bc435"),
    ("script/test_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py", "aeaee4516fae2630b1cf803f467a191dddfa12011f990201a854cd6def3adbbb"),
    ("script/acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py", "c9c197b247cc8f9bdcc581ab3e56e87d0ba1de6d568a6826b7ad839dc64a96a3"),
    ("script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py", "9c9514e23d5a9abe0d69a9ae3c8af210ebd477206b08a964b41c29c07d37d47f"),
    ("script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py", "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"),
    ("script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py", "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"),
    ("build/offline-source/pion-ice-v4.3.0/dependencies/.wave-19-v1.claim", "0454a51b04fd51c967221e7b1ca178b6d750cddec2ea4fc884ada61af6e2f6c1"),
    ("build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/evidence.json", "9e108c036f7ba30b7dc0f9cbfe88390b783f2f8b0658b32a24020bed36060b4a"),
    ("build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/001-a26a2513c9f4c49c479c.mod", "e9c23d3613ad3c29e18552f90d02798b7295419dd47d4f667d5843d7dc1673b3"),
    ("build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/001-a26a2513c9f4c49c479c.zip", "02824dd62fa3241946a2ac14fdadbd393514d76cebbfbd8bddcddbfc80c7f94b"),
    ("build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/002-c6022d5be99f60f2428e.mod", "8133f6f3b232cb388b50d1c74be92f39198cbd62e3b0991c917cdbc1322bbe14"),
    ("build/offline-source/pion-ice-v4.3.0/dependencies/wave-19-v1/accepted/002-c6022d5be99f60f2428e.zip", "3f218b1dd9a690036d1226f46f142fc7ae3cc9cd4f28610b96bb8080b7e194c9"),
    ("docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave19-receipt-v1.json", "97e208dde0b41dfe400ed948ae8636d7e2e25bf644d4fda6beb057d97e9a746e"),
    ("docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave19-manifest-v1.json", "eed663ad8e0ce4e1a3300d3666ad879223a1aaa4b0adc107a6293123499d0de8"),
]
EXPECTED_CHECKER_RAW_SHA256 = (
    "35c35e98bfc0ea4b49f29b76d732a54f8f0f80dbbe20812266f35143c92da564"
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
EXPECTED_CHECKER_CALL_COUNT = 1_947
EXPECTED_CHECKER_CALL_SURFACE_SHA256 = (
    "3d0065b320d74d452dea497e20c5f9bd08394d3e4a10f11bbbfb5d1ee865718a"
)
EXPECTED_V18_CANDIDATE_CONTENT_SHA256 = (
    "9dce50013314ec8934ad52ac57cb0de92e982c2334303fc77289f01bc9c285fb"
)
EXPECTED_V18_GRAPH_SHA256 = (
    "a865a62a7a80a0dece55aeebd537d3fb9aa73ce6ceeea10304a6a2074c2dfaba"
)
EXPECTED_V18_FRONTIER_SHA256 = (
    "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570"
)
# Resolve this fixture only from the same audited full reconstruction that
# resolves the three output seals above.  Its eventual shape is:
# {
#     "exactFrontier": ((module, version, selected), ...),
#     "newTupleCount": int,
#     "unmappedExternalImportCount": int,
#     "unresolvedDeclaredExternalImportCount": int,
#     "fixedPointReached": bool,
#     "route": {
#         "route": str,
#         "status": str,
#         "nextAction": str,
#     },
# }
EXPECTED_V18_OUTCOME = {
    "exactFrontier": (),
    "newTupleCount": 0,
    "unmappedExternalImportCount": 0,
    "unresolvedDeclaredExternalImportCount": 0,
    "fixedPointReached": True,
    "route": {
        "route": "fixed_point_candidate",
        "status": "combined_graph_discovery_complete_fixed_point_candidate",
        "nextAction":
            "prepare_separate_combined_fixed_point_closure_review_decision",
    },
}
EXPECTED_V18_INPUT_SET_SHA256 = (
    "321c50408978ff6b8795c17b51b53cd1dabf8f124e4a691c42cb2eb4fd961ded"
)
EXPECTED_V18_SOURCE_BINDINGS_SHA256 = (
    "622a644a86e6ffe4596a3186034fbf141d964f34b5f3044f1b175db716d099f7"
)
EXPECTED_V18_EXACT_INPUT_INVENTORY_SHA256 = (
    "a349cd67bd0f3355146b7008c5fcf595f79801bc1d7f8ab6d85f69178e565cda"
)
OUTPUT_SEALS_UNRESOLVED = (
    EXPECTED_V18_OUTCOME is None
    or any(
        value == UNRESOLVED_SHA256
        for value in (
            EXPECTED_V18_CANDIDATE_CONTENT_SHA256,
            EXPECTED_V18_GRAPH_SHA256,
            EXPECTED_V18_FRONTIER_SHA256,
        )
    )
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
        "load_v17_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v14_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v13_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v12_checker",
        static_expression_dump("getattr(module, name, None)"),
    ),
    (
        "load_v11_checker",
        static_expression_dump("getattr(module, name, None)"),
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
                "load_v17_checker": "V17_CHECKER_PATH",
                "load_v14_checker": "V14_CHECKER_PATH",
                "load_v13_checker": "V13_CHECKER_PATH",
                "load_v12_checker": "V12_CHECKER_PATH",
                "load_v11_checker": "V11_CHECKER_PATH",
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
                    and type(
                        ast.literal_eval(keyword_values["optimize"])
                    ) is int
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
    if (compile_count, exec_count) != (11, 11):
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
            CHECKER.V17_CHECKER_PATH,
            CHECKER.V17_CHECKER_RAW_SHA256,
        ) as held_v17,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V16_CHECKER_PATH,
            CHECKER.V16_CHECKER_RAW_SHA256,
        ) as held_v16,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V15_CHECKER_PATH,
            CHECKER.V15_CHECKER_RAW_SHA256,
        ) as held_v15,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V14_CHECKER_PATH,
            CHECKER.V14_CHECKER_RAW_SHA256,
        ) as held_v14,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V13_CHECKER_PATH,
            CHECKER.V13_CHECKER_RAW_SHA256,
        ) as held_v13,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V12_CHECKER_PATH,
            CHECKER.V12_CHECKER_RAW_SHA256,
        ) as held_v12,
        CHECKER.PinnedCodeFile(
            ROOT,
            CHECKER.V11_CHECKER_PATH,
            CHECKER.V11_CHECKER_RAW_SHA256,
        ) as held_v11,
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
        v17 = CHECKER.harden_checker_module(
            CHECKER.load_v17_checker(held_v17)
        )
        v16 = v17.load_v16_checker(held_v16)
        v15 = v16.load_v15_checker(held_v15)
        v14 = v15.load_v14_checker(held_v14)
        v13 = v14.load_v13_checker(held_v13)
        v12 = v13.load_v12_checker(held_v12)
        v11 = v12.load_v11_checker(held_v11)
        v10 = v11.load_v10_checker(held_v10)
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
                yield (
                    v17,
                    v16,
                    v15,
                    v14,
                    v13,
                    v12,
                    v11,
                    v10,
                    v9,
                    v8,
                    v7,
                    v6,
                    v5,
                    v4,
                    v1,
                    runner,
                )


@contextmanager
def held_wave19_documents(*, include_held=False):
    with held_toolchain() as chain:
        (
            v17,
            v16,
            v15,
            v14,
            v13,
            v12,
            v11,
            v10,
            v9,
            v8,
            v7,
            v6,
            v5,
            v4,
            v1,
            runner,
        ) = chain
        bindings = (
            CHECKER.wave19_control_bindings()
            + CHECKER.wave19_auxiliary_evidence_bindings()
        )
        with runner.HeldInputSet(ROOT, bindings) as held:
            documents = CHECKER.parse_wave19_documents(runner, held)
            if include_held:
                yield v4, runner, documents, held
            else:
                yield v4, runner, documents


@contextmanager
def held_all_documents():
    with held_toolchain() as chain:
        (
            v17,
            v16,
            v15,
            v14,
            v13,
            v12,
            v11,
            v10,
            v9,
            v8,
            v7,
            v6,
            v5,
            v4,
            v1,
            runner,
        ) = chain
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
            + v11.wave12_control_bindings()
            + v12.wave13_control_bindings()
            + v13.wave14_control_bindings()
            + v14.wave15_control_bindings()
            + v15.wave16_control_bindings()
            + v16.wave17_control_bindings()
            + v17.wave18_control_bindings()
            + CHECKER.wave19_control_bindings()
        )
        auxiliary = CHECKER.wave19_auxiliary_evidence_bindings()
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
                v11.parse_wave12_documents(runner, held),
                v12.parse_wave13_documents(runner, held),
                v13.parse_wave14_documents(runner, held),
                v14.parse_wave15_documents(runner, held),
                v15.parse_wave16_documents(runner, held),
                v16.parse_wave17_documents(runner, held),
                v17.parse_wave18_documents(runner, held),
                CHECKER.parse_wave19_documents(runner, held),
            )


def assert_wave19_mutation_fails(
    testcase: unittest.TestCase,
    mutate,
    expected_code: str,
) -> None:
    with held_wave19_documents() as (v4, runner, documents):
        mutated = copy.deepcopy(documents)
        mutate(mutated)
        with (
            mock.patch.object(
                CHECKER,
                "verify_wave19_content_bindings",
            ),
            testcase.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught,
        ):
            CHECKER.wave19_request_resources(v4, runner, mutated)
    testcase.assertEqual(str(caught.exception), expected_code)


def rebind_wave19_selector_hashes(
    runner,
    documents,
) -> tuple[str, str]:
    """Rebind selector-bearing projections so semantic checks run."""

    decision = documents[CHECKER.WAVE19_DECISION_PATH]
    permit = documents[CHECKER.WAVE19_PERMIT_PATH]
    readback_permit = documents[CHECKER.WAVE19_READBACK_PERMIT_PATH]
    readback = documents[CHECKER.WAVE19_READBACK_PATH]
    resources = permit["requestContract"]["resources"]
    source_requests = decision["sourceAcquisitionPreparation"]["requestSet"]
    resources_sha256 = CHECKER.sha256_bytes(
        runner.canonical_json_bytes(resources)
    )
    request_set_sha256 = CHECKER.sha256_bytes(
        CHECKER.wave19_digest_bytes(source_requests)
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


CHECKER = load_checker()


class CombinedFixedPointV18DryOracleTests(unittest.TestCase):
    """Read-only oracles that never invoke full graph reconstruction."""

    maxDiff = None

    @staticmethod
    def _document(path: str, expected_raw_sha256: str):
        raw = (ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_raw_sha256:
            raise AssertionError(path)
        value = json.loads(raw)
        if type(value) is not dict:
            raise AssertionError(path)
        return value

    def test_00_static_surface_is_read_only_and_exact(self):
        source = CHECKER_PATH.read_text()
        tree = validate_checker_static_surface(source)
        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("load_v17_checker", functions)
        self.assertIn("validate_v17_predecessor_candidate", functions)
        self.assertIn("derive_and_validate_graph_result", functions)
        self.assertIn("execute_reconstruction_protocol_prefix", functions)
        self.assertIn("finalize_reconstruction_protocol", functions)
        bool_optimize_source = source.replace(
            "            optimize=0,",
            "            optimize=False,",
            1,
        )
        self.assertNotEqual(bool_optimize_source, source)
        with self.assertRaises(StaticSurfaceFailure) as caught:
            validate_checker_static_surface(bool_optimize_source)
        self.assertEqual(caught.exception.code, "E_PINNED_CODE_CALL")

    def test_00_exact_wave19_consumed_bindings_and_input_delta(self):
        controls = {
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-identity-and-acquisition-"
                "decision-wave19-v1.json"
            ): "7486a8a4659459ce49128bcf05501abb065f2b64c542715eaebd3c1ca686a8cf",
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-acquisition-wave19-"
                "execution-permit-v1.json"
            ): "ea80d045fb13042f2c673dcd3363a46aaf4bc81ffbe65af53e9ecd65b1369a3e",
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-acquisition-wave19-"
                "receipt-v1.json"
            ): "97e208dde0b41dfe400ed948ae8636d7e2e25bf644d4fda6beb057d97e9a746e",
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-acquisition-wave19-"
                "manifest-v1.json"
            ): "eed663ad8e0ce4e1a3300d3666ad879223a1aaa4b0adc107a6293123499d0de8",
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-acquisition-wave19-readback-"
                "execution-permit-v1.json"
            ): "822bdc144957462b6ebe17fc2a8a7fd8256c97fea40690aec6eeba99c760b312",
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-acquisition-wave19-"
                "readback-v1.json"
            ): "31343f4f9511694acef39078ee7124b8747ebd7796da326ef9b316f06829992e",
            (
                "docs/security-hardening/production-p2p-nat-v1/"
                "g2-pion-restricted-fork-v1/rung-three/"
                "bounded-dependency-source-acquisition-wave19-readback-"
                "manifest-v1.json"
            ): "84db859af7e370a1967f7327990f3ade3ea5ef9b87e7390dffeb6305189e9d99",
        }
        documents = {
            path: self._document(path, digest)
            for path, digest in controls.items()
        }
        self.assertEqual(CHECKER.WAVE19_CONTROL_SHA256, controls)

        readback_permit = documents[CHECKER.WAVE19_READBACK_PERMIT_PATH]
        readback = documents[CHECKER.WAVE19_READBACK_PATH]
        snapshot = readback_permit["frozenAcquisitionSnapshot"]
        frozen_rows = (
            snapshot["acquisitionAuthority"]
            + [snapshot["acquisitionClaim"], snapshot["evidence"]]
            + snapshot["acceptedDirectory"]["files"]
            + [
                snapshot["acquisitionReceipt"],
                snapshot["acquisitionManifest"],
            ]
        )
        self.assertEqual(
            [(row["path"], row["rawSha256"]) for row in frozen_rows],
            EXPECTED_WAVE19_FROZEN_PATH_RAWS,
        )
        self.assertEqual(snapshot["frozenFileCount"], 23)
        self.assertEqual(len(snapshot["acquisitionAuthority"]), 15)
        self.assertEqual(snapshot["acceptedResourceCount"], 4)
        for key in (
            "acceptedResourceCount",
            "frozenFileCount",
            "modCount",
            "selectedTupleCount",
            "zipCount",
        ):
            self.assertIs(type(snapshot[key]), int, key)
        self.assertEqual(snapshot["modCount"], 2)
        self.assertEqual(snapshot["zipCount"], 2)
        self.assertEqual(
            (
                snapshot["aggregateModBytes"],
                snapshot["aggregateZipBytes"],
                snapshot["aggregateAcceptedBytes"],
                snapshot["aggregateZipEntryCount"],
                snapshot["aggregateZipUncompressedBytes"],
            ),
            (415, 11_453_540, 11_453_955, 931, 46_404_827),
        )

        resources = readback["verified"]["resources"]
        identity = [
            (
                row["requestOrdinal"],
                182 + (row["requestOrdinal"] + 1) // 2,
                row["kind"],
                (
                    "golang.org/x/crypto",
                    "golang.org/x/text",
                )[(row["requestOrdinal"] - 1) // 2],
                (
                    "v0.38.0",
                    "v0.25.0",
                )[(row["requestOrdinal"] - 1) // 2],
                (
                    "build/offline-source/pion-ice-v4.3.0/dependencies/"
                    "wave-19-v1/accepted/"
                    + row["acceptedFileName"]
                ),
                row["rawSha256"],
            )
            for row in resources
        ]
        self.assertEqual(identity, EXPECTED_WAVE19_RESOURCE_IDENTITY)
        self.assertEqual(
            [row["verifiedH1"] for row in resources],
            [
                "h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw=",
                "h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8=",
                "h1:WEdwpYrmk1qmdHvhkSTNPm3app7v4rsT8F2UD6+VHIA=",
                "h1:qVyWApTSYLk/drJRO5mDlNYskwQznZmkpV2c8q9zls4=",
            ],
        )
        for key in (
            "requiredRetainedFdPreManifestBarrierCount",
            "verificationPassCount",
        ):
            self.assertIs(type(readback[key]), int, key)
        self.assertEqual(readback["verificationPassCount"], 2)
        self.assertEqual(
            readback["requiredRetainedFdPreManifestBarrierCount"],
            3,
        )
        self.assertIs(
            readback["completionAppliesToRetainedSnapshot"],
            True,
        )
        self.assertIs(
            readback[
                "currentPathIdentityGuaranteedThroughManifestPublication"
            ],
            False,
        )

        predecessor = {
            "inputs": 365,
            "resources": 364,
            "tuples": 182,
            "raw": 344_638_685,
            "archives": 183,
            "entries": 71_373,
            "uncompressed": 1_312_942_457,
        }
        delta = {
            "inputs": 4,
            "resources": 4,
            "tuples": 2,
            "raw": snapshot["aggregateAcceptedBytes"],
            "archives": 2,
            "entries": snapshot["aggregateZipEntryCount"],
            "uncompressed": snapshot[
                "aggregateZipUncompressedBytes"
            ],
        }
        self.assertEqual(
            {
                key: predecessor[key] + delta[key]
                for key in predecessor
            },
            {
                "inputs": 369,
                "resources": 368,
                "tuples": 184,
                "raw": 356_092_640,
                "archives": 185,
                "entries": 72_304,
                "uncompressed": 1_359_347_284,
            },
        )
        self.assertEqual(
            CHECKER.V18_INPUT_SET_SHA256,
            EXPECTED_V18_INPUT_SET_SHA256,
        )
        self.assertEqual(
            CHECKER.V18_SOURCE_BINDINGS_SHA256,
            EXPECTED_V18_SOURCE_BINDINGS_SHA256,
        )
        self.assertEqual(
            (
                CHECKER.V18_EXPECTED_HELD_SOURCE_INPUT_COUNT,
                CHECKER.V18_EXPECTED_ARCHIVE_COUNT,
                CHECKER.V18_EXPECTED_AGGREGATE_ENTRY_COUNT,
                CHECKER.V18_EXPECTED_AGGREGATE_RAW_BYTE_SIZE,
                CHECKER.V18_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
            ),
            (369, 185, 72_304, 356_092_640, 1_359_347_284),
        )

    def test_00_exact_379_input_inventory_is_disjoint_and_bound(self):
        with held_all_documents() as value:
            chain, controls, auxiliary, _, *documents = value
            (
                v17,
                v16,
                v15,
                v14,
                v13,
                v12,
                v11,
                v10,
                v9,
                v8,
                v7,
                v6,
                v5,
                v4,
                v1,
                runner,
            ) = chain
            bindings = CHECKER.combined_source_bindings(
                v17,
                v16,
                v15,
                v14,
                v13,
                v12,
                v11,
                v10,
                v9,
                v8,
                v7,
                v6,
                v5,
                v4,
                v1,
                runner,
                *documents,
            )
            inventory = CHECKER.exact_input_inventory_bindings(
                runner,
                bindings,
            )
        self.assertEqual((len(controls), len(auxiliary)), (129, 3))
        self.assertEqual(len(bindings), 369)
        self.assertEqual(len(inventory), 379)
        self.assertEqual(len({row["path"] for row in inventory}), 379)
        self.assertEqual(
            sum(row["bytes"] for row in inventory),
            356_152_035,
        )
        self.assertEqual(
            hashlib.sha256(
                runner.canonical_json_bytes(inventory)
            ).hexdigest(),
            EXPECTED_V18_EXACT_INPUT_INVENTORY_SHA256,
        )
        self.assertEqual(
            [row["category"] for row in inventory[-10:]],
            ["wave19_terminal_control"] * 7
            + ["wave19_auxiliary_evidence"] * 3,
        )
        self.assertEqual(
            hashlib.sha256(
                runner.canonical_json_bytes(inventory[-10:])
            ).hexdigest(),
            CHECKER.V18_WAVE19_READBACK_BINDINGS_SHA256,
        )

    def test_00_authority_and_request_contract_require_no_credentials(self):
        permit = self._document(
            CHECKER.WAVE19_PERMIT_PATH,
            "ea80d045fb13042f2c673dcd3363a46aaf4bc81ffbe65af53e9ecd65b1369a3e",
        )
        readback_permit = self._document(
            CHECKER.WAVE19_READBACK_PERMIT_PATH,
            "822bdc144957462b6ebe17fc2a8a7fd8256c97fea40690aec6eeba99c760b312",
        )
        readback = self._document(
            CHECKER.WAVE19_READBACK_PATH,
            "31343f4f9511694acef39078ee7124b8747ebd7796da326ef9b316f06829992e",
        )
        false_keys = (
            "authenticationRequired",
            "externalAuthenticationRequired",
            "repositoryOwnerIdentityProofRequired",
            "ownerProofRequired",
            "passwordRequired",
            "privateKeyRequired",
            "signatureRequired",
            "tokenRequired",
            "cookieRequired",
            "clientCertificateRequired",
            "userActionRequired",
            "sourceExtractionAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "compileAuthorized",
            "packageManagerAuthorized",
            "subprocessAuthorized",
            "gitOperationAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
        )
        for authority in (
            permit["authority"],
            readback_permit["authority"],
        ):
            for key in false_keys:
                if key in authority:
                    self.assertIs(authority[key], False, key)
        request = permit["requestContract"]
        for key in (
            "authenticationAllowed",
            "authorizationHeaderAllowed",
            "proxyAuthorizationHeaderAllowed",
            "cookieAllowed",
            "clientCertificateAllowed",
        ):
            self.assertIs(request[key], False, key)
        self.assertIs(readback["externalAuthenticationRequired"], False)
        self.assertIs(readback["userActionRequired"], False)
        self.assertIs(readback["sourceExtracted"], False)
        self.assertIs(readback["sourceLoadedOrExecuted"], False)
        self.assertIs(readback["compiled"], False)
        self.assertIs(
            type(readback["networkRequestAttemptCount"]),
            int,
        )
        self.assertEqual(readback["networkRequestAttemptCount"], 0)

    def test_00_wave19_exact_control_validator_is_read_only(self):
        with held_wave19_documents() as (v4, runner, documents):
            resources = CHECKER.wave19_request_resources(
                v4,
                runner,
                documents,
            )
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
            EXPECTED_WAVE19_RESOURCE_IDENTITY,
        )
        for row in resources:
            self.assertIs(type(row["order"]), int)
            self.assertIs(type(row["tupleOrder"]), int)

    def test_00_wave19_unknown_bool_int_and_stale_v17_fail_closed(self):
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                "authority"
            ].__setitem__("unknown", False),
            "E_WAVE19_DECISION",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                "requestContract"
            ].__setitem__("requestCount", True),
            "E_WAVE19_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFileCount", 21),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PATH][
                "verified"
            ].__setitem__("acceptedResourceCount", 2),
            "E_WAVE19_READBACK",
        )

        def stale_predecessor(documents):
            predecessors = documents[
                CHECKER.WAVE19_READBACK_PERMIT_PATH
            ]["frozenAcquisitionSnapshot"]["predecessorBindings"]
            predecessors["combinedFixedPointV15"] = predecessors.pop(
                "combinedFixedPointV17"
            )

        assert_wave19_mutation_fails(
            self,
            stale_predecessor,
            "E_WAVE19_READBACK_PERMIT",
        )

    def test_00_wave19_bool_int_and_typed_dicts_fail_closed(self):
        cases = (
            (
                lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                    "identityResolution"
                ].__setitem__("tupleCount", True),
                "E_WAVE19_DECISION",
            ),
            (
                lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ].__setitem__("selectedTupleCount", False),
                "E_WAVE19_READBACK_PERMIT",
            ),
            (
                lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                    "authority"
                ].__setitem__("externalAuthenticationRequired", 0),
                "E_WAVE19_DECISION",
            ),
            (
                lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                    "absoluteResourceLimits"
                ].__setitem__(
                    "callerBlockedSigalrmRejectedBeforePreflight",
                    1,
                ),
                "E_WAVE19_PERMIT",
            ),
            (
                lambda docs: docs[CHECKER.WAVE19_MANIFEST_PATH].__setitem__(
                    "manifestWrittenLast",
                    1,
                ),
                "E_WAVE19_MANIFEST",
            ),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                assert_wave19_mutation_fails(
                    self,
                    mutate,
                    expected,
                )

    def test_00_wave19_rebound_resource_bool_int_fails_closed(self):
        with held_wave19_documents() as (v4, runner, documents):
            cases = (
                (
                    "selector_zero",
                    lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                        "requestContract"
                    ]["resources"][0].__setitem__(
                        "selectedByGraphAlgorithm",
                        0,
                    ),
                ),
                (
                    "ordinal_true",
                    lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                        "requestContract"
                    ]["resources"][0].__setitem__(
                        "requestOrdinal",
                        True,
                    ),
                ),
            )
            for label, mutate in cases:
                mutated = copy.deepcopy(documents)
                mutate(mutated)
                resources_sha256, request_set_sha256 = (
                    rebind_wave19_selector_hashes(runner, mutated)
                )
                with (
                    self.subTest(case=label),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave19_content_bindings",
                    ),
                    mock.patch.object(
                        CHECKER,
                        "WAVE19_PERMIT_RESOURCES_SHA256",
                        resources_sha256,
                    ),
                    mock.patch.object(
                        CHECKER,
                        "WAVE19_REQUEST_SET_SHA256",
                        request_set_sha256,
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave19_request_resources(
                        v4,
                        runner,
                        mutated,
                    )
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE19_RESOURCE",
                )

    def test_00_derived_route_is_graph_owned_and_bool_int_fails(self):
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

        scenarios = (
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
                    "status": (
                        "combined_graph_discovery_complete_fixed_point_"
                        "candidate"
                    ),
                    "nextAction": (
                        "prepare_separate_combined_fixed_point_closure_"
                        "review_decision"
                    ),
                },
            ),
        )
        for graph, route in scenarios:
            with self.subTest(route=route["route"]):
                result = CHECKER.derive_and_validate_graph_result(
                    Runner(),
                    graph,
                    route,
                )
                self.assertEqual(
                    result["frontierTupleCount"],
                    len(graph["exactFrontier"]),
                )
                self.assertIs(
                    result["fixedPointReached"],
                    graph["fixedPointReached"],
                )
                self.assertIs(type(result["frontierTupleCount"]), int)

        invalid = (
            ({**scenarios[0][0], "newTupleCount": True}, scenarios[0][1]),
            ({**scenarios[0][0], "newTupleCount": 0}, scenarios[0][1]),
            (
                {
                    **scenarios[2][0],
                    "unmappedExternalImportCount": False,
                },
                scenarios[2][1],
            ),
            (
                {**scenarios[2][0], "fixedPointReached": False},
                scenarios[2][1],
            ),
            (
                scenarios[0][0],
                {**scenarios[0][1], "unknown": False},
            ),
        )
        for graph, route in invalid:
            with self.subTest(graph=graph, route=route):
                with self.assertRaises(
                    CHECKER.CombinedCheckFailure,
                ) as caught:
                    CHECKER.derive_and_validate_graph_result(
                        Runner(),
                        graph,
                        route,
                    )
                self.assertEqual(str(caught.exception), "E_DERIVED_RESULT")

    def test_00_nofollow_code_pin_rejects_symlink(self):
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

    def test_00_error_document_requests_no_authentication(self):
        value = json.loads(CHECKER.error_document_bytes())
        self.assertEqual(value["schemaVersion"], "18.0")
        self.assertEqual(value["status"], "verification_failed")
        self.assertIs(value["externalAuthenticationRequired"], False)
        self.assertIs(value["userActionRequired"], False)


class CombinedFixedPointV18LatentOracleTests(unittest.TestCase):
    """Seal-independent coverage for heavy-suite baseline assumptions."""

    maxDiff = None

    @staticmethod
    def _tool_path_fixture():
        v17 = types.SimpleNamespace(
            TRANSITIVE_CHECKER_PATHS={
                (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                    f"v{version}.py"
                )
                for version in range(1, 17)
            },
            V1_PROVIDER_PATH=(
                "script/run_p2p_nat_g2_pion_dependency_source_review_"
                "wave1_once.py"
            ),
        )
        direct_bindings = copy.deepcopy(EXPECTED_TOOL_BINDINGS)
        direct_inputs = tuple(
            types.SimpleNamespace(relative_path=row["path"])
            for row in direct_bindings
        )
        predecessor_bindings = [
            copy.deepcopy(row)
            for row in direct_bindings
            if row["path"] != CHECKER.SELF_PATH
        ]
        predecessor_candidate = {
            "toolBindings": predecessor_bindings,
            "operationCounters": {
                "heldToolInputCount": len(predecessor_bindings),
                "transitiveDistinctToolPathCount": 18,
            },
        }
        return (
            v17,
            predecessor_candidate,
            direct_bindings,
            direct_inputs,
        )

    def test_00_wave19_exact_mutation_domains_reach_semantic_checks(self):
        with held_wave19_documents() as (v4, runner, documents):
            decision = documents[CHECKER.WAVE19_DECISION_PATH]
            permit = documents[CHECKER.WAVE19_PERMIT_PATH]
            snapshot = documents[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]
            verified = documents[CHECKER.WAVE19_READBACK_PATH]["verified"]
            resources = permit["requestContract"]["resources"]
            source_requests = decision["sourceAcquisitionPreparation"][
                "requestSet"
            ]
            tuples = decision["identityResolution"]["tuples"]
            accepted = snapshot["acceptedDirectory"]["files"]
            self.assertEqual(
                (
                    len(resources),
                    len(source_requests),
                    len(tuples),
                    len(accepted),
                    len(verified["resources"]),
                ),
                (4, 4, 2, 4, 4),
            )
            self.assertEqual(
                [
                    index
                    for index, row in enumerate(verified["resources"])
                    if row["kind"] == "zip"
                    and row["rootGoModPresent"] is True
                ],
                [1, 3],
            )
            self.assertEqual(
                (
                    decision["identityResolution"]["tupleCount"],
                    permit["requestContract"]["requestCount"],
                    snapshot["frozenFileCount"],
                    snapshot["acceptedDirectory"]["exactFileCount"],
                    snapshot["acceptedResourceCount"],
                    snapshot["modCount"],
                ),
                (2, 4, 23, 4, 4, 2),
            )

            def assert_semantic_failure(label, mutate, expected):
                mutated = copy.deepcopy(documents)
                mutate(mutated)
                resources_sha256, request_set_sha256 = (
                    rebind_wave19_selector_hashes(runner, mutated)
                )
                with (
                    self.subTest(mutation=label),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave19_content_bindings",
                    ),
                    mock.patch.object(
                        CHECKER,
                        "WAVE19_PERMIT_RESOURCES_SHA256",
                        resources_sha256,
                    ),
                    mock.patch.object(
                        CHECKER,
                        "WAVE19_REQUEST_SET_SHA256",
                        request_set_sha256,
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave19_request_resources(
                        v4,
                        runner,
                        mutated,
                    )
                self.assertEqual(
                    str(caught.exception),
                    expected,
                    label,
                )

            cases = (
                (
                    "accepted_index_3",
                    lambda docs: docs[
                        CHECKER.WAVE19_READBACK_PERMIT_PATH
                    ]["frozenAcquisitionSnapshot"]["acceptedDirectory"][
                        "files"
                    ][3].__setitem__("rawSha256", "0" * 64),
                    "E_WAVE19_READBACK_PERMIT",
                ),
                (
                    "permit_selector_index_3",
                    lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                        "requestContract"
                    ]["resources"][3].__setitem__(
                        "selectedByGraphAlgorithm",
                        True,
                    ),
                    "E_WAVE19_RESOURCE",
                ),
                (
                    "source_selector_index_3",
                    lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                        "sourceAcquisitionPreparation"
                    ]["requestSet"][3].__setitem__(
                        "selectedByGraphAlgorithm",
                        True,
                    ),
                    "E_WAVE19_PERMIT",
                ),
                (
                    "tuple_selector_index_1",
                    lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                        "identityResolution"
                    ]["tuples"][1].__setitem__(
                        "selectedByGraphAlgorithm",
                        True,
                    ),
                    "E_WAVE19_DECISION",
                ),
                (
                    "tuple_count_3",
                    lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                        "identityResolution"
                    ].__setitem__("tupleCount", 3),
                    "E_WAVE19_DECISION",
                ),
                (
                    "request_count_5",
                    lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                        "requestContract"
                    ].__setitem__("requestCount", 5),
                    "E_WAVE19_PERMIT",
                ),
                (
                    "frozen_file_count_24",
                    lambda docs: docs[
                        CHECKER.WAVE19_READBACK_PERMIT_PATH
                    ]["frozenAcquisitionSnapshot"].__setitem__(
                        "frozenFileCount",
                        24,
                    ),
                    "E_WAVE19_READBACK_PERMIT",
                ),
                (
                    "exact_file_count_5",
                    lambda docs: docs[
                        CHECKER.WAVE19_READBACK_PERMIT_PATH
                    ]["frozenAcquisitionSnapshot"][
                        "acceptedDirectory"
                    ].__setitem__(
                        "exactFileCount",
                        5,
                    ),
                    "E_WAVE19_READBACK_PERMIT",
                ),
            )
            for label, mutate, expected in cases:
                assert_semantic_failure(label, mutate, expected)

            scalar_cases = (
                (
                    "accepted_resource_count_5",
                    "acceptedResourceCount",
                    5,
                ),
                ("mod_count_3", "modCount", 3),
            )
            for label, key, value in scalar_cases:
                assert_semantic_failure(
                    label,
                    lambda docs, field=key, replacement=value: docs[
                        CHECKER.WAVE19_READBACK_PERMIT_PATH
                    ]["frozenAcquisitionSnapshot"].__setitem__(
                        field,
                        replacement,
                    ),
                    "E_WAVE19_READBACK_PERMIT",
                )

            limit_cases = (
                (
                    "permit_aggregate_limit",
                    CHECKER.WAVE19_PERMIT_PATH,
                    "absoluteResourceLimits",
                    "maximumAggregateResponseBodyBytes",
                    35_651_585,
                    "E_WAVE19_PERMIT",
                ),
                (
                    "permit_zip_entry_limit",
                    CHECKER.WAVE19_PERMIT_PATH,
                    "zipLimits",
                    "maximumEntryCountAcrossAllZips",
                    40_001,
                    "E_WAVE19_PERMIT",
                ),
                (
                    "readback_aggregate_limit",
                    CHECKER.WAVE19_READBACK_PERMIT_PATH,
                    "resourceLimits",
                    "maximumAggregateAcceptedBytes",
                    35_651_585,
                    "E_WAVE19_READBACK_PERMIT",
                ),
                (
                    "readback_zip_entry_limit",
                    CHECKER.WAVE19_READBACK_PERMIT_PATH,
                    "resourceLimits",
                    "maximumZipEntriesAcrossAll",
                    40_001,
                    "E_WAVE19_READBACK_PERMIT",
                ),
            )
            for label, path, section, key, value, expected in limit_cases:
                assert_semantic_failure(
                    label,
                    lambda docs, target=path, group=section, field=key,
                    replacement=value: docs[target][group].__setitem__(
                        field,
                        replacement,
                    ),
                    expected,
                )

    def test_01_predecessor_namespace_and_metadata_names_are_current(self):
        expected_anchor = {
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-18-v1.claim"
            ),
            "rawSha256": (
                "08f5134ce03805e512c2dec0dee13251ce682d793d2b87f7f8e29f6d3426d362"
            ),
        }
        documents = {}
        for path in (
            CHECKER.WAVE19_DECISION_PATH,
            CHECKER.WAVE19_PERMIT_PATH,
            CHECKER.WAVE19_READBACK_PERMIT_PATH,
        ):
            raw = (ROOT / path).read_bytes()
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(),
                CHECKER.WAVE19_CONTROL_SHA256[path],
            )
            documents[path] = json.loads(raw)
        predecessor_bindings = (
            documents[CHECKER.WAVE19_DECISION_PATH]["predecessorBindings"],
            documents[CHECKER.WAVE19_PERMIT_PATH]["predecessorBindings"],
            documents[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["predecessorBindings"],
        )
        for bindings in predecessor_bindings:
            predecessor = bindings["combinedFixedPointV17"]
            self.assertEqual(
                predecessor["wave18NamespaceAnchor"],
                expected_anchor,
            )
            self.assertNotIn("wave17NamespaceAnchor", predecessor)

        v17_raw = (ROOT / CHECKER.V17_CHECKER_PATH).read_bytes()
        self.assertEqual(
            hashlib.sha256(v17_raw).hexdigest(),
            CHECKER.V17_CHECKER_RAW_SHA256,
        )
        tree = ast.parse(v17_raw.decode("utf-8"))
        generators = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "generate_candidate"
        ]
        self.assertEqual(len(generators), 1)
        literal_pairs = {
            (key.value, value.value)
            for node in ast.walk(generators[0])
            if isinstance(node, ast.Dict)
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant)
            and type(key.value) is str
            and isinstance(value, ast.Constant)
        }
        self.assertIn(
            (
                "v16TestsBindingScope",
                "historical_metadata_only_not_live_held",
            ),
            literal_pairs,
        )
        self.assertIn(("v16TestsLiveHeld", False), literal_pairs)
        self.assertFalse(
            any(
                key in {"v15TestsBindingScope", "v15TestsLiveHeld"}
                for key, _ in literal_pairs
            )
        )

    def test_02_tool_helper_baseline_includes_self_v18_and_v16(self):
        fixture = self._tool_path_fixture()
        direct_paths, transitive_paths = (
            CHECKER.derive_and_validate_tool_paths(*fixture)
        )
        expected_opened_paths = {
            (
                "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                f"v{version}.py"
            )
            for version in range(1, 19)
        } | {
            (
                "script/run_p2p_nat_g2_pion_dependency_source_review_"
                "wave1_once.py"
            )
        }
        self.assertEqual(
            direct_paths,
            {row["path"] for row in EXPECTED_TOOL_BINDINGS},
        )
        self.assertEqual(transitive_paths, expected_opened_paths)
        self.assertIn(CHECKER.SELF_PATH, transitive_paths)
        self.assertIn(CHECKER.V16_CHECKER_PATH, transitive_paths)

    def test_03_tool_helper_rejects_fake_v17_without_v16(self):
        fixture = list(self._tool_path_fixture())
        fixture[0].TRANSITIVE_CHECKER_PATHS = {
            (
                "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                f"v{version}.py"
            )
            for version in range(1, 16)
        }
        with self.assertRaises(
            CHECKER.CombinedCheckFailure,
        ) as caught:
            CHECKER.derive_and_validate_tool_paths(*fixture)
        self.assertEqual(str(caught.exception), "E_TOOL_BINDINGS")


class CombinedFixedPointV18Tests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        unresolved_bootstrap = {
            "SELF_NORMALIZED_SHA256": CHECKER.SELF_NORMALIZED_SHA256,
            "V18_INPUT_SET_SHA256": CHECKER.V18_INPUT_SET_SHA256,
            "V18_SOURCE_BINDINGS_SHA256":
                CHECKER.V18_SOURCE_BINDINGS_SHA256,
            "EXPECTED_V18_CANDIDATE_CONTENT_SHA256":
                EXPECTED_V18_CANDIDATE_CONTENT_SHA256,
            "EXPECTED_V18_GRAPH_SHA256": EXPECTED_V18_GRAPH_SHA256,
            "EXPECTED_V18_FRONTIER_SHA256": EXPECTED_V18_FRONTIER_SHA256,
        }
        if (
            EXPECTED_V18_OUTCOME is None
            or any(
                value == UNRESOLVED_SHA256
                for value in unresolved_bootstrap.values()
            )
        ):
            raise unittest.SkipTest(
                "V18 exact bootstrap seals/outcome remain unresolved; "
                "full reconstruction is intentionally not run"
            )
        original_load_v17 = CHECKER.load_v17_checker
        original_derive_tool_paths = CHECKER.derive_and_validate_tool_paths
        original_os_open = os.open
        cls.actual_python_open_paths = []

        def capturing_load_v17(held):
            module = original_load_v17(held)
            original_generate = module.generate_candidate

            def capturing_generate(root):
                value = original_generate(root)
                cls.predecessor_candidate = value
                return value

            module.generate_candidate = capturing_generate
            return module

        def capturing_derive_tool_paths(
            v17,
            predecessor_candidate,
            direct_tool_bindings,
            direct_tool_inputs,
        ):
            result = original_derive_tool_paths(
                v17,
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
                "load_v17_checker",
                side_effect=capturing_load_v17,
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
        self.assertIs(type(count), int)
        self.assertEqual(count, 1)
        derived_self_sha256 = hashlib.sha256(
            independently_normalized
        ).hexdigest()
        self.assertRegex(derived_self_sha256, r"^[0-9a-f]{64}$")
        self.assertNotEqual(derived_self_sha256, UNRESOLVED_SHA256)
        self.assertEqual(
            CHECKER.SELF_NORMALIZED_SHA256,
            EXPECTED_SELF_NORMALIZED_SHA256,
        )
        for path, expected in (
            (CHECKER.V17_CHECKER_PATH, CHECKER.V17_CHECKER_RAW_SHA256),
            (CHECKER.V17_TESTS_PATH, CHECKER.V17_TESTS_RAW_SHA256),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                expected,
            )
        for path, expected in CHECKER.WAVE19_CONTROL_SHA256.items():
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
        self.assertEqual(candidate["schemaVersion"], "18.0")
        self.assertEqual(
            candidate["documentType"],
            (
                "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
                "wave5-wave6-wave7-wave8-wave9-wave10-wave11-wave12-"
                "wave13-wave14-wave15-wave16-wave17-wave18-wave19-"
                "fixed-point-candidate"
            ),
        )
        self.assertEqual(
            binding["sha256"],
            EXPECTED_V18_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            candidate["graphDiscovery"]["graphSha256"],
            EXPECTED_V18_GRAPH_SHA256,
        )
        self.assertEqual(
            candidate["derivedResult"]["frontierSha256"],
            EXPECTED_V18_FRONTIER_SHA256,
        )
        self.assertEqual(candidate["authority"], EXPECTED_CLOSED_AUTHORITY)
        for key, expected in EXPECTED_CLOSED_AUTHORITY.items():
            self.assertIs(candidate["authority"][key], expected, key)
        self.assertIs(candidate["closure"]["releaseReady"], False)
        self.assertIs(
            candidate["closure"]["dependencySourceReviewed"],
            False,
        )
        self.assertIs(
            type(candidate["derivedResult"]["fixedPointReached"]),
            bool,
        )
        self.assertIs(
            candidate["derivedResult"]["fixedPointReached"],
            candidate["graphDiscovery"]["fixedPointReached"],
        )
        self.assertIs(
            type(candidate["derivedResult"]["frontierTupleCount"]),
            int,
        )
        self.assertEqual(
            candidate["derivedResult"]["frontierTupleCount"],
            len(candidate["graphDiscovery"]["exactFrontier"]),
        )

    def test_02_actual_candidate_is_cross_bound_to_outcome_fixture(self):
        candidate = self.candidate
        graph = candidate["graphDiscovery"]
        outcome = EXPECTED_V18_OUTCOME
        self.assertIs(type(outcome), dict)
        self.assertEqual(
            set(outcome),
            {
                "exactFrontier",
                "newTupleCount",
                "unmappedExternalImportCount",
                "unresolvedDeclaredExternalImportCount",
                "fixedPointReached",
                "route",
            },
        )
        expected_frontier = outcome["exactFrontier"]
        self.assertIs(type(expected_frontier), tuple)
        self.assertTrue(
            all(
                type(row) is tuple
                and len(row) == 3
                and type(row[0]) is str
                and row[0] != ""
                and type(row[1]) is str
                and row[1] != ""
                and type(row[2]) is bool
                for row in expected_frontier
            )
        )
        actual_frontier = graph["exactFrontier"]
        self.assertIs(type(actual_frontier), list)
        self.assertTrue(
            all(
                type(row) is dict
                and set(row)
                == {
                    "acquisitionAuthorized",
                    "module",
                    "requiresSeparateWaveDecision",
                    "selectedByGraphAlgorithm",
                    "version",
                }
                and type(row["module"]) is str
                and type(row["version"]) is str
                and type(row["selectedByGraphAlgorithm"]) is bool
                and row["acquisitionAuthorized"] is False
                and row["requiresSeparateWaveDecision"] is True
                for row in actual_frontier
            )
        )
        self.assertEqual(
            tuple(
                (
                    row["module"],
                    row["version"],
                    row["selectedByGraphAlgorithm"],
                )
                for row in actual_frontier
            ),
            expected_frontier,
        )
        for key in (
            "newTupleCount",
            "unmappedExternalImportCount",
            "unresolvedDeclaredExternalImportCount",
        ):
            self.assertIs(type(outcome[key]), int)
            self.assertGreaterEqual(outcome[key], 0)
            self.assertIs(type(graph[key]), int)
            self.assertEqual(graph[key], outcome[key], key)
        self.assertEqual(outcome["newTupleCount"], len(expected_frontier))
        self.assertIs(type(outcome["fixedPointReached"]), bool)
        self.assertIs(type(graph["fixedPointReached"]), bool)
        self.assertIs(
            graph["fixedPointReached"],
            outcome["fixedPointReached"],
        )
        self.assertIs(
            candidate["derivedResult"]["fixedPointReached"],
            outcome["fixedPointReached"],
        )
        self.assertEqual(
            candidate["derivedResult"]["frontierTupleCount"],
            len(expected_frontier),
        )
        expected_route = outcome["route"]
        self.assertIs(type(expected_route), dict)
        self.assertEqual(
            set(expected_route),
            {"route", "status", "nextAction"},
        )
        self.assertTrue(
            all(
                type(value) is str and value != ""
                for value in expected_route.values()
            )
        )
        self.assertEqual(
            {
                "route": candidate["route"],
                "status": candidate["status"],
                "nextAction": candidate["nextAction"],
            },
            expected_route,
        )

    def test_03_exact_369_source_and_379_input_composition_and_hashes(self):
        inputs = self.candidate["inputSet"]
        rows = inputs["sourceBindings"]
        expected_counts = {
            "heldSourceInputCount": 369,
            "resourceCount": 368,
            "modCount": 184,
            "zipCount": 184,
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
            "wave13ResourceCount": 8,
            "wave14ResourceCount": 8,
            "wave15ResourceCount": 10,
            "wave16ResourceCount": 6,
            "wave17ResourceCount": 2,
            "wave18ResourceCount": 6,
            "wave19ResourceCount": 4,
            "uniqueModuleVersionTupleCount": 184,
            "aggregateRawByteSize": 356_092_640,
        }
        for key, value in expected_counts.items():
            self.assertEqual(inputs[key], value, key)
        self.assertNotEqual(
            (
                inputs["heldSourceInputCount"],
                inputs["resourceCount"],
                inputs["modCount"],
                inputs["zipCount"],
                inputs["uniqueModuleVersionTupleCount"],
            ),
            (365, 364, 182, 182, 182),
            "stale V17/Wave18 combined cardinality was accepted",
        )
        self.assertEqual(len(rows), 369)
        self.assertEqual(len({row["path"] for row in rows}), 369)
        self.assertEqual(
            inputs["combinedInputSetSha256"],
            EXPECTED_V18_INPUT_SET_SHA256,
        )
        self.assertEqual(
            CHECKER.V18_INPUT_SET_SHA256,
            EXPECTED_V18_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(CHECKER.wave19_digest_bytes(rows)).hexdigest(),
            EXPECTED_V18_SOURCE_BINDINGS_SHA256,
        )
        self.assertEqual(
            CHECKER.V18_SOURCE_BINDINGS_SHA256,
            EXPECTED_V18_SOURCE_BINDINGS_SHA256,
        )
        pair_orders = sorted(
            {
                row["tupleOrder"]
                for row in rows
                if row["kind"] != "root_zip"
            }
        )
        self.assertEqual(pair_orders, list(range(1, 185)))
        self.assertEqual(
            sorted(
                {
                    row["tupleOrder"]
                    for row in rows
                    if row["wave"] == "wave19"
                }
            ),
            [183, 184],
        )
        inventory = self.candidate["exactInputInventory"]
        self.assertEqual(
            (
                inventory["heldInputCount"],
                inventory["sourceBindingCount"],
                inventory["wave19TerminalControlBindingCount"],
                inventory["wave19AuxiliaryEvidenceBindingCount"],
                inventory["aggregateRawByteSize"],
            ),
            (379, 369, 7, 3, 356_152_035),
        )
        self.assertEqual(
            inventory["orderedBindingsSha256"],
            EXPECTED_V18_EXACT_INPUT_INVENTORY_SHA256,
        )
        self.assertEqual(len(inventory["orderedBindings"]), 379)
        self.assertEqual(len(inventory["wave19ReadbackBindings"]), 10)
        self.assertEqual(
            inventory["wave19ReadbackBindingsSha256"],
            CHECKER.V18_WAVE19_READBACK_BINDINGS_SHA256,
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
                CHECKER.V18_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
            ),
            (185, 72_304, 1_359_347_284, 1_359_347_284),
        )
        self.assertEqual(
            (
                verification["directFullInputReconstructionCount"],
                verification["inheritedFullInputReconstructionCount"],
                verification["totalFullInputReconstructionCount"],
            ),
            (2, 32, 34),
        )
        self.assertEqual(
            (
                counters["directFullSourceReconstructionCount"],
                counters["inheritedFullSourceReconstructionCount"],
                counters["totalFullSourceReconstructionCount"],
            ),
            (2, 32, 34),
        )
        self.assertEqual(
            (
                counters["directArchiveOpenCount"],
                counters["inheritedArchiveOpenCount"],
                counters["totalArchiveOpenCount"],
                counters["archiveOpenCount"],
            ),
            (370, 4_422, 4_792, 4_792),
        )
        self.assertEqual(
            verification["underlyingIndependentGraphAlgorithmCount"],
            68,
        )
        self.assertEqual(verification["hardenedCheckerModuleCount"], 17)
        self.assertEqual(verification["providerFacadeLoadCount"], 17)
        self.assertEqual(counters["heldTerminalEvidenceCount"], 129)
        self.assertEqual(counters["heldAuxiliaryEvidenceCount"], 3)
        self.assertEqual(counters["heldToolInputCount"], 17)
        self.assertEqual(counters["transitiveDistinctToolPathCount"], 19)
        self.assertEqual(
            counters["heldSourceInputCount"]
            + counters["heldTerminalEvidenceCount"]
            + counters["heldAuxiliaryEvidenceCount"]
            + counters["heldToolInputCount"],
            518,
        )
        for key in (
            "archiveExtractionCount",
            "dependencySourceLoadCount",
            "dependencySourceExecutionCount",
            "dependencySourceCompileCount",
            "subprocessCount",
            "networkOperationCount",
            "fileWriteCount",
        ):
            self.assertIs(type(counters[key]), int, key)
            self.assertEqual(counters[key], 0, key)

    def test_05_live_and_historical_boundaries_are_explicit(self):
        verification = self.candidate["checkerVerification"]
        predecessor = self.candidate["predecessorVerification"]
        self.assertIs(
            verification["pinnedV17PredecessorExecuted"],
            True,
        )
        self.assertEqual(
            verification["v17TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertIs(verification["v17TestsLiveHeld"], False)
        self.assertIs(
            verification[
                "wave19HistoricalExact23FrozenSnapshotDescriptorSetBound"
            ],
            True,
        )
        self.assertIs(
            verification["wave19LiveTerminalControlMetadataVerified"],
            True,
        )
        self.assertIs(
            verification["wave19LiveFinalAndAcceptedInventoriesVerified"],
            True,
        )
        self.assertIs(
            verification["wave19CompletionAppliesToRetainedSnapshot"],
            True,
        )
        self.assertIs(
            verification[
                "wave19CurrentPathIdentityGuaranteedThroughManifestPublication"
            ],
            False,
        )
        self.assertIs(
            verification[
                "wave19SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ],
            False,
        )
        self.assertEqual(
            predecessor["v17TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertIs(predecessor["v17TestsLiveHeld"], False)

    def test_06_wave19_terminal_resources_are_exact(self):
        with held_wave19_documents() as (v4, runner, documents):
            resources = CHECKER.wave19_request_resources(
                v4,
                runner,
                documents,
            )
            snapshot = documents[CHECKER.WAVE19_READBACK_PERMIT_PATH][
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
            verified_resources = documents[CHECKER.WAVE19_READBACK_PATH][
                "verified"
            ]["resources"]
        self.assertEqual(len(resources), 4)
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
            EXPECTED_WAVE19_RESOURCE_IDENTITY,
        )
        self.assertEqual(
            [
                (row["path"], row["rawSha256"])
                for row in frozen_rows
            ],
            EXPECTED_WAVE19_FROZEN_PATH_RAWS,
        )
        self.assertEqual(len(EXPECTED_WAVE19_FROZEN_PATH_RAWS), 23)
        self.assertEqual(snapshot["frozenFileCount"], 23)
        self.assertEqual(len(snapshot["acquisitionAuthority"]), 15)
        self.assertEqual(
            (
                snapshot["aggregateAcceptedBytes"],
                snapshot["aggregateModBytes"],
                snapshot["aggregateZipBytes"],
                snapshot["aggregateZipEntryCount"],
                snapshot["aggregateZipUncompressedBytes"],
            ),
            (11_453_955, 415, 11_453_540, 931, 46_404_827),
        )
        self.assertIs(
            documents[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "verificationContract"
            ]["exact23FrozenFileSnapshotRequired"],
            True,
        )
        self.assertEqual(
            (
                sum(row["kind"] == "mod" for row in resources),
                sum(row["kind"] == "zip" for row in resources),
            ),
            (2, 2),
        )
        self.assertEqual(
            [row["order"] for row in resources],
            list(range(1, 5)),
        )
        self.assertEqual(
            sorted({row["tupleOrder"] for row in resources}),
            [183, 184],
        )
        self.assertEqual(
            sum(row["maximumBytes"] for row in resources),
            11_453_955,
        )
        self.assertEqual(
            {
                row["acceptedFileName"]
                for row in verified_resources
                if row["kind"] == "zip"
                and row["rootGoModPresent"] is False
            },
            EXPECTED_WAVE19_FALSE_ROOT_GO_MOD_FILES,
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
                d13,
                d14,
                d15,
                d16,
                d17,
                d18,
                d19,
            ) = value
            (
                v17,
                v16,
                v15,
                v14,
                v13,
                v12,
                v11,
                v10,
                v9,
                v8,
                v7,
                v6,
                v5,
                v4,
                v1,
                runner,
            ) = chain
            rows = CHECKER.combined_source_bindings(
                v17,
                v16,
                v15,
                v14,
                v13,
                v12,
                v11,
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
                d13,
                d14,
                d15,
                d16,
                d17,
                d18,
                d19,
            )
            projection = v1.source_projection(rows)
            inventory = CHECKER.exact_input_inventory_bindings(
                runner,
                rows,
            )
        self.assertEqual((len(controls), len(auxiliary)), (129, 3))
        self.assertEqual(len(rows), 369)
        self.assertEqual(len(inventory), 379)
        self.assertEqual(
            hashlib.sha256(
                runner.canonical_json_bytes(projection)
            ).hexdigest(),
            EXPECTED_V18_INPUT_SET_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                CHECKER.wave19_digest_bytes(projection)
            ).hexdigest(),
            EXPECTED_V18_SOURCE_BINDINGS_SHA256,
        )

    def test_08_unknown_authority_and_tool_pin_fail_closed(self):
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                "authority"
            ].__setitem__("unknownAuthority", False),
            "E_WAVE19_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                "toolBindings"
            ][0].__setitem__("normalizedSha256", "0" * 64),
            "E_WAVE19_DECISION",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "toolBindings"
            ][2].__setitem__("rawSha256", "0" * 64),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE19_DECISION",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE19_READBACK",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_MANIFEST_PATH][
                "contentBinding"
            ].__setitem__("sha256", "0" * 64),
            "E_WAVE19_READBACK_MANIFEST",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionReceipt"].__setitem__("rawSha256", "0" * 64),
            "E_WAVE19_READBACK_PERMIT",
        )
        for key in ("acquisitionClaim", "evidence"):
            assert_wave19_mutation_fails(
                self,
                lambda docs, target=key: docs[
                    CHECKER.WAVE19_READBACK_PERMIT_PATH
                ]["frozenAcquisitionSnapshot"][target].__setitem__(
                    "rawSha256",
                    "0" * 64,
                ),
                "E_WAVE19_READBACK_PERMIT",
            )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PATH][
                "readbackClaim"
            ].__setitem__("rawSha256", "0" * 64),
            "E_WAVE19_READBACK",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_MANIFEST_PATH][
                "receipt"
            ].__setitem__("rawSha256", "0" * 64),
            "E_WAVE19_READBACK_MANIFEST",
        )

    def test_08_each_wave19_accepted_raw_binding_tamper_fails_closed(self):
        with held_wave19_documents() as (v4, runner, documents):
            accepted = documents[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"]
            self.assertEqual(len(accepted), 4)
            for index in range(4):
                mutated = copy.deepcopy(documents)
                mutated[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                    "frozenAcquisitionSnapshot"
                ]["acceptedDirectory"]["files"][index]["rawSha256"] = "0" * 64
                with (
                    self.subTest(accepted_raw_index=index),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave19_content_bindings",
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave19_request_resources(v4, runner, mutated)
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE19_READBACK_PERMIT",
                )

    def test_09_wave19_cardinality_wave18_anchor_and_explicit_v14_downgrade(
        self,
    ):
        def substitute_resource_same_cardinality(documents):
            rows = documents[CHECKER.WAVE19_PERMIT_PATH][
                "requestContract"
            ]["resources"]
            rows[0] = copy.deepcopy(rows[1])

        def substitute_authority_same_cardinality(documents):
            rows = documents[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionAuthority"]
            rows[0] = copy.deepcopy(rows[1])

        def substitute_explicit_transitive_v14_predecessor(documents):
            predecessors = documents[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["predecessorBindings"]
            predecessors["combinedFixedPointV14"] = predecessors.pop(
                "combinedFixedPointV17"
            )

        def add_explicit_transitive_v14_predecessor_sibling(
            documents,
            path,
            nested=False,
        ):
            container = documents[path]
            if nested:
                container = container["frozenAcquisitionSnapshot"]
            predecessors = container["predecessorBindings"]
            predecessors["combinedFixedPointV14"] = copy.deepcopy(
                predecessors["combinedFixedPointV17"]
            )

        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_DECISION_PATH].__setitem__(
                "retainedMetadataEvidence",
                {
                    **docs[CHECKER.WAVE19_DECISION_PATH][
                        "retainedMetadataEvidence"
                    ],
                    "unknown": False,
                },
            ),
            "E_WAVE19_DECISION",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                "identityResolution"
            ].__setitem__("tupleCount", 3),
            "E_WAVE19_DECISION",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                "requestContract"
            ].__setitem__("requestCount", 5),
            "E_WAVE19_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFileCount", 24),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"].__setitem__("exactFileCount", 5),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("acceptedResourceCount", 5),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acquisitionAuthority"].pop(),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            substitute_explicit_transitive_v14_predecessor,
            "E_WAVE19_READBACK_PERMIT",
        )
        for path, nested, expected in (
            (CHECKER.WAVE19_DECISION_PATH, False, "E_WAVE19_DECISION"),
            (CHECKER.WAVE19_PERMIT_PATH, False, "E_WAVE19_PERMIT"),
            (
                CHECKER.WAVE19_READBACK_PERMIT_PATH,
                True,
                "E_WAVE19_READBACK_PERMIT",
            ),
        ):
            assert_wave19_mutation_fails(
                self,
                lambda docs, target=path, is_nested=nested:
                    add_explicit_transitive_v14_predecessor_sibling(
                        docs,
                        target,
                        nested=is_nested,
                    ),
                expected,
            )
        for path, nested, expected in (
            (CHECKER.WAVE19_PERMIT_PATH, False, "E_WAVE19_PERMIT"),
            (
                CHECKER.WAVE19_READBACK_PERMIT_PATH,
                True,
                "E_WAVE19_READBACK_PERMIT",
            ),
        ):
            for key, value in (
                ("path", "build/offline-source/stale-wave16.claim"),
                ("rawSha256", "0" * 64),
            ):
                assert_wave19_mutation_fails(
                    self,
                    lambda docs, target=path, is_nested=nested,
                    anchor_key=key, anchor_value=value: (
                        (
                            docs[target]["frozenAcquisitionSnapshot"]
                            if is_nested
                            else docs[target]
                        )["predecessorBindings"]["combinedFixedPointV17"][
                            "wave18NamespaceAnchor"
                        ].__setitem__(anchor_key, anchor_value)
                    ),
                    expected,
                )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ]["acceptedDirectory"]["files"][0].__setitem__(
                "rawSha256",
                "0" * 64,
            ),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            substitute_resource_same_cardinality,
            "E_WAVE19_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            substitute_authority_same_cardinality,
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__("frozenFilesCanonicalSha256", "0" * 64),
            "E_WAVE19_READBACK_PERMIT",
        )
        for key, value in (
            ("aggregateAcceptedBytes", 11_475_644),
            ("modCount", 4),
            ("aggregateZipBytes", 11_475_192),
            ("aggregateZipEntryCount", 948),
            ("aggregateZipUncompressedBytes", 46_464_212),
        ):
            assert_wave19_mutation_fails(
                self,
                lambda docs, field=key, stale=value: docs[
                    CHECKER.WAVE19_READBACK_PERMIT_PATH
                ]["frozenAcquisitionSnapshot"].__setitem__(field, stale),
                "E_WAVE19_READBACK_PERMIT",
            )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "frozenAcquisitionSnapshot"
            ].__setitem__(
                "frozenFilesCanonicalSha256",
                "b8863a58dd5db814afe94eb101c166e4f5bfb92d9b8197dbe3e32a3b1f0e99c4",
            ),
            "E_WAVE19_READBACK_PERMIT",
        )
        for path, key, value, expected in (
            (
                CHECKER.WAVE19_PERMIT_PATH,
                "maximumAggregateResponseBodyBytes",
                35_651_585,
                "E_WAVE19_PERMIT",
            ),
            (
                CHECKER.WAVE19_PERMIT_PATH,
                "maximumEntryCountAcrossAllZips",
                40_001,
                "E_WAVE19_PERMIT",
            ),
            (
                CHECKER.WAVE19_READBACK_PERMIT_PATH,
                "maximumAggregateAcceptedBytes",
                35_651_585,
                "E_WAVE19_READBACK_PERMIT",
            ),
            (
                CHECKER.WAVE19_READBACK_PERMIT_PATH,
                "maximumZipEntriesAcrossAll",
                40_001,
                "E_WAVE19_READBACK_PERMIT",
            ),
        ):
            def mutate_limit(
                documents,
                target=path,
                field=key,
                stale=value,
            ):
                document = documents[target]
                if target == CHECKER.WAVE19_PERMIT_PATH:
                    section = (
                        "zipLimits"
                        if field == "maximumEntryCountAcrossAllZips"
                        else "absoluteResourceLimits"
                    )
                else:
                    section = "resourceLimits"
                document[section][field] = stale

            assert_wave19_mutation_fails(
                self,
                mutate_limit,
                expected,
            )

    def test_10_selected_tuple_and_live_hold_overclaim_fail_closed(self):
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                "identityResolution"
            ].__setitem__("graphSelectedTupleCount", 1),
            "E_WAVE19_DECISION",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", [1]),
            "E_WAVE19_READBACK",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PATH][
                "verified"
            ].__setitem__("selectedRequestOrdinals", [1, 2]),
            "E_WAVE19_READBACK",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "verificationContract"
            ].__setitem__("v17TestsLiveHeld", False),
            "E_WAVE19_READBACK_PERMIT",
        )

    def test_10_all_wave19_selectors_and_false_root_mods_are_exact(self):
        with held_wave19_documents() as (v4, runner, documents):
            baseline = documents[CHECKER.WAVE19_PERMIT_PATH][
                "requestContract"
            ]["resources"]
            verified = documents[CHECKER.WAVE19_READBACK_PATH]["verified"][
                "resources"
            ]
            self.assertEqual(len(baseline), 4)
            self.assertEqual(len(verified), 4)
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
            self.assertEqual(zip_root_indexes, [1, 3])

            selector_collections = (
                (
                    "permit_resource",
                    4,
                    lambda docs: docs[CHECKER.WAVE19_PERMIT_PATH][
                        "requestContract"
                    ]["resources"],
                    "E_WAVE19_RESOURCE",
                ),
                (
                    "source_request",
                    4,
                    lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                        "sourceAcquisitionPreparation"
                    ]["requestSet"],
                    "E_WAVE19_PERMIT",
                ),
                (
                    "identity_tuple",
                    2,
                    lambda docs: docs[CHECKER.WAVE19_DECISION_PATH][
                        "identityResolution"
                    ]["tuples"],
                    "E_WAVE19_DECISION",
                ),
            )
            missing = object()
            for location, count, rows_for, expected in selector_collections:
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
                            rebind_wave19_selector_hashes(runner, mutated)
                        )
                        with (
                            self.subTest(
                                selector_location=location,
                                selector_index=index,
                                value=case_value,
                            ),
                            mock.patch.object(
                                CHECKER,
                                "verify_wave19_content_bindings",
                            ),
                            mock.patch.object(
                                CHECKER,
                                "WAVE19_PERMIT_RESOURCES_SHA256",
                                resources_sha256,
                            ),
                            mock.patch.object(
                                CHECKER,
                                "WAVE19_REQUEST_SET_SHA256",
                                request_set_sha256,
                            ),
                            self.assertRaises(
                                CHECKER.CombinedCheckFailure,
                            ) as caught,
                        ):
                            CHECKER.wave19_request_resources(
                                v4,
                                runner,
                                mutated,
                            )
                        self.assertEqual(
                            str(caught.exception),
                            expected,
                        )

            for index in zip_root_indexes:
                mutated = copy.deepcopy(documents)
                mutated[CHECKER.WAVE19_READBACK_PATH]["verified"][
                    "resources"
                ][index]["rootGoModPresent"] = False
                with (
                    self.subTest(root_go_mod_index=index),
                    mock.patch.object(
                        CHECKER,
                        "verify_wave19_content_bindings",
                    ),
                    self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught,
                ):
                    CHECKER.wave19_request_resources(v4, runner, mutated)
                self.assertEqual(
                    str(caught.exception),
                    "E_WAVE19_RESOURCE",
                )

    def test_11_post_success_reporting_contract_is_pinned(self):
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH][
                "verificationContract"
            ]["postSuccessReportingFailure"].__setitem__(
                "retryAllowed",
                True,
            ),
            "E_WAVE19_READBACK_PERMIT",
        )
        assert_wave19_mutation_fails(
            self,
            lambda docs: docs[CHECKER.WAVE19_READBACK_PERMIT_PATH].__setitem__(
                "recorderNormalizedSha256",
                "0" * 64,
            ),
            "E_WAVE19_READBACK_PERMIT",
        )

    def test_12_terminal_modes_sizes_and_namespace_are_live(self):
        with held_wave19_documents(include_held=True) as (
            _,
            _,
            documents,
            held,
        ):
            CHECKER.validate_wave19_completed_namespace(held, documents)
            for path, (size, mode) in CHECKER.WAVE19_CONTROL_METADATA.items():
                info = os.fstat(held.files[path].fd)
                self.assertEqual(info.st_size, size)
                self.assertEqual(stat.S_IMODE(info.st_mode), mode)
                self.assertIs(type(info.st_nlink), int)
                self.assertEqual(info.st_nlink, 1)

    def test_13_legacy_wave9_compatibility_remains_exact_and_bounded(self):
        with held_all_documents() as value:
            chain = value[0]
            d9 = value[11]
            v8 = chain[9]
            v4 = chain[13]
            runner = chain[15]
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
        self.assertIs(type(count), int)
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
            "load_v17_checker",
            "load_v14_checker",
            "load_v13_checker",
            "load_v12_checker",
            "load_v11_checker",
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
        self.assertEqual(len(compile_calls), 11)
        self.assertEqual(len(exec_calls), 11)
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
            self.assertIs(
                type(ast.literal_eval(keyword_values["optimize"])),
                int,
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
        for key, expected in EXPECTED_CLOSED_AUTHORITY.items():
            self.assertIs(authority[key], expected, key)
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
        self.assertEqual(value["schemaVersion"], "18.0")
        self.assertEqual(value["status"], "verification_failed")
        self.assertIs(value["externalAuthenticationRequired"], False)
        self.assertIs(value["userActionRequired"], False)

    def test_17_v17_candidate_v16_metadata_and_wave18_anchor_are_exact(self):
        predecessor = self.predecessor_candidate
        self.assertEqual(
            predecessor["contentBinding"]["sha256"],
            CHECKER.V17_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            predecessor["inputSet"]["combinedInputSetSha256"],
            CHECKER.V17_INPUT_SET_SHA256,
        )
        self.assertEqual(
            predecessor["graphDiscovery"]["graphSha256"],
            CHECKER.V17_GRAPH_SHA256,
        )
        self.assertEqual(
            predecessor["derivedResult"]["frontierSha256"],
            CHECKER.V17_FRONTIER_SHA256,
        )
        self.assertEqual(
            predecessor["checkerVerification"]["v16TestsBindingScope"],
            "historical_metadata_only_not_live_held",
        )
        self.assertIs(
            predecessor["checkerVerification"]["v16TestsLiveHeld"],
            False,
        )
        with held_wave19_documents() as (_, runner, documents):
            decision = documents[CHECKER.WAVE19_DECISION_PATH]
            verified = CHECKER.validate_v17_predecessor_candidate(
                runner,
                predecessor,
                decision,
            )
            self.assertEqual(
                verified["candidateContentSha256"],
                CHECKER.V17_CANDIDATE_CONTENT_SHA256,
            )
            explicit_transitive_v14_decision = copy.deepcopy(decision)
            explicit_transitive_v14_decision["predecessorBindings"][
                "combinedFixedPointV14"
            ] = explicit_transitive_v14_decision[
                "predecessorBindings"
            ].pop(
                "combinedFixedPointV17"
            )
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.validate_v17_predecessor_candidate(
                    runner,
                    predecessor,
                    explicit_transitive_v14_decision,
                )
            self.assertEqual(str(caught.exception), "E_V17_PREDECESSOR")
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
                        "combinedFixedPointV17"
                    ][key] = "0" * 64
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v17_predecessor_candidate(
                            runner,
                            predecessor,
                            mutated_decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V17_PREDECESSOR",
                    )
            for key, value in (
                ("path", "build/offline-source/stale-wave16.claim"),
                ("rawSha256", "0" * 64),
            ):
                with self.subTest(wave18_namespace_anchor=key):
                    mutated_decision = copy.deepcopy(decision)
                    mutated_decision["predecessorBindings"][
                        "combinedFixedPointV17"
                    ]["wave18NamespaceAnchor"][key] = value
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v17_predecessor_candidate(
                            runner,
                            predecessor,
                            mutated_decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V17_PREDECESSOR",
                    )
            mismatched_identity_decision = copy.deepcopy(decision)
            mismatched_identity_decision["identityResolution"]["tuples"][0][
                "module"
            ] = "example.invalid/frontier-identity-mismatch"
            with self.assertRaises(
                CHECKER.CombinedCheckFailure,
            ) as caught:
                CHECKER.validate_v17_predecessor_candidate(
                    runner,
                    predecessor,
                    mismatched_identity_decision,
                )
            self.assertEqual(
                str(caught.exception),
                "E_V17_PREDECESSOR",
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
                    3_695,
                ),
            ]
            for index, mutate in enumerate(candidate_mutations):
                with self.subTest(predecessor_candidate=index):
                    mutated_candidate = copy.deepcopy(predecessor)
                    mutate(mutated_candidate)
                    with self.assertRaises(
                        CHECKER.CombinedCheckFailure,
                    ) as caught:
                        CHECKER.validate_v17_predecessor_candidate(
                            runner,
                            mutated_candidate,
                            decision,
                        )
                    self.assertEqual(
                        str(caught.exception),
                        "E_V17_PREDECESSOR",
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
            for version in range(1, 19)
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
        self.assertNotIn(CHECKER.V17_TESTS_PATH, self.actual_python_open_paths)
        self.assertNotIn(CHECKER.V14_TESTS_PATH, self.actual_python_open_paths)
        self.assertNotIn(CHECKER.V13_TESTS_PATH, self.actual_python_open_paths)
        self.assertNotIn(CHECKER.V12_TESTS_PATH, self.actual_python_open_paths)
        self.assertNotIn(CHECKER.V11_TESTS_PATH, self.actual_python_open_paths)
        self.assertNotIn(CHECKER.V10_TESTS_PATH, self.actual_python_open_paths)
        self.assertNotIn(CHECKER.V9_TESTS_PATH, self.actual_python_open_paths)
        for forbidden in (
            "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py",
            (
                "script/record_p2p_nat_g2_pion_rung3_dependency_wave19_"
                "readback_v1_once.py"
            ),
            (
                "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_"
                "acquisition_v1.py"
            ),
            (
                "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_"
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
                "validate_wave19_completed_namespace",
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
            self.assertIs(
                result["fixedPointReached"],
                graph["fixedPointReached"],
            )
            self.assertIs(type(result["frontierTupleCount"]), int)
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
        class V17:
            TRANSITIVE_CHECKER_PATHS = {
                (
                    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
                    f"v{version}.py"
                )
                for version in range(1, 17)
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
                V17,
                self.predecessor_candidate,
                direct_bindings,
                direct_inputs,
            )
        )
        self.assertEqual(len(direct_paths), 17)
        self.assertEqual(len(transitive_paths), 19)

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
                    V17,
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
                V17,
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
                    V17,
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


@unittest.skipIf(
    OUTPUT_SEALS_UNRESOLVED,
    "V18 output seals/outcome fixture remain unresolved",
)
class CombinedFixedPointV18FastBoundaryTests(unittest.TestCase):
    def test_v18_regression_seals_and_outcome_are_resolved(self):
        self.assertEqual(
            (
                CHECKER.V18_INPUT_SET_SHA256,
                CHECKER.V18_SOURCE_BINDINGS_SHA256,
            ),
            (
                EXPECTED_V18_INPUT_SET_SHA256,
                EXPECTED_V18_SOURCE_BINDINGS_SHA256,
            ),
        )
        self.assertEqual(
            CHECKER.SELF_NORMALIZED_SHA256,
            EXPECTED_SELF_NORMALIZED_SHA256,
        )
        self.assertNotEqual(
            CHECKER.SELF_NORMALIZED_SHA256,
            UNRESOLVED_SHA256,
        )
        for digest in (
            EXPECTED_V18_CANDIDATE_CONTENT_SHA256,
            EXPECTED_V18_GRAPH_SHA256,
            EXPECTED_V18_FRONTIER_SHA256,
        ):
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertNotEqual(digest, UNRESOLVED_SHA256)
        outcome = EXPECTED_V18_OUTCOME
        self.assertIs(type(outcome), dict)
        self.assertEqual(
            set(outcome),
            {
                "exactFrontier",
                "newTupleCount",
                "unmappedExternalImportCount",
                "unresolvedDeclaredExternalImportCount",
                "fixedPointReached",
                "route",
            },
        )
        frontier = outcome["exactFrontier"]
        self.assertIs(type(frontier), tuple)
        self.assertTrue(
            all(
                type(row) is tuple
                and len(row) == 3
                and type(row[0]) is str
                and row[0] != ""
                and type(row[1]) is str
                and row[1] != ""
                and type(row[2]) is bool
                for row in frontier
            )
        )
        for key in (
            "newTupleCount",
            "unmappedExternalImportCount",
            "unresolvedDeclaredExternalImportCount",
        ):
            self.assertIs(type(outcome[key]), int)
            self.assertGreaterEqual(outcome[key], 0)
        self.assertEqual(outcome["newTupleCount"], len(frontier))
        self.assertIs(type(outcome["fixedPointReached"]), bool)
        route = outcome["route"]
        self.assertIs(type(route), dict)
        self.assertEqual(
            set(route),
            {"route", "status", "nextAction"},
        )
        self.assertTrue(
            all(type(value) is str and value != "" for value in route.values())
        )

    def test_genuine_v18_boundary_matches_audited_outcome(self):
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

        outcome = EXPECTED_V18_OUTCOME
        frontier = [
            {
                "acquisitionAuthorized": False,
                "module": module,
                "requiresSeparateWaveDecision": True,
                "selectedByGraphAlgorithm": selected,
                "version": version,
            }
            for module, version, selected in outcome["exactFrontier"]
        ]
        graph = {
            "exactFrontier": frontier,
            "newTupleCount": outcome["newTupleCount"],
            "unmappedExternalImportCount": (
                outcome["unmappedExternalImportCount"]
            ),
            "unresolvedDeclaredExternalImportCount": (
                outcome["unresolvedDeclaredExternalImportCount"]
            ),
            "fixedPointReached": outcome["fixedPointReached"],
        }
        route = dict(outcome["route"])

        result = CHECKER.derive_and_validate_graph_result(
            Runner(),
            graph,
            route,
        )

        self.assertEqual(
            [
                (
                    row["module"],
                    row["version"],
                    row["selectedByGraphAlgorithm"],
                )
                for row in frontier
            ],
            list(outcome["exactFrontier"]),
        )
        self.assertEqual(
            result,
            {
                "fixedPointReached": outcome["fixedPointReached"],
                "frontierTupleCount": len(frontier),
                "frontierSha256": EXPECTED_V18_FRONTIER_SHA256,
            },
        )
        self.assertIs(
            result["fixedPointReached"],
            outcome["fixedPointReached"],
        )
        self.assertEqual(route, outcome["route"])

    def test_aggregate_uncompressed_limit_minus_one_is_rejected(self):
        aggregate_bytes = (
            CHECKER.V18_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
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
            v4 = chain[13]
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
