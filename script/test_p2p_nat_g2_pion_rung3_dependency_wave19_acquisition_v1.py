#!/usr/bin/env python3
"""Focused offline tests for the Wave19 acquisition permit checker."""

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
    raise RuntimeError("Wave19 acquisition tests require `python3 -I -B -S`")

import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py"
)
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py"
)
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave19-"
    "execution-permit-v1.md"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave19-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave19-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave19_decision_v1.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
WAVE4_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)

DECISION_RAW_SHA256 = (
    "7486a8a4659459ce49128bcf05501abb065f2b64c542715eaebd3c1ca686a8cf"
)
DECISION_CONTENT_SHA256 = (
    "39edf590a88d728a105c74ef0eeb1600c84159888d3b4edbbe4acba05e7a6f56"
)
DECISION_READER_RAW_SHA256 = (
    "3aefdd1e3a283e099ad4a3624103461eee821043ad4bf18a57a39c81b100d526"
)
DECISION_CHECKER_RAW_SHA256 = (
    "cd6926a344b52fafd0265ec8bd1f08cbdf250826fa53e46e6c5a3e94049f0d92"
)
DECISION_TESTS_RAW_SHA256 = (
    "2bd972108f75739be378c20544eaa518425ad875156cf83065f27fb34d2a47d2"
)
WAVE4_CHECKER_RAW_SHA256 = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
WAVE4_RUNNER_RAW_SHA256 = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)
DECISION_REQUEST_SHA256 = (
    "97f4d8c1775c01c27f83f19b66af6274e0ae77b1be328456c2685ba18552b6e7"
)
RESOURCE_SHA256 = (
    "e5effbf132773b38711521ab3da4fec70732867556024fe997a4f735027ce484"
)
PROJECTION_SHA256 = (
    "2da2915bfcf76ddc2d3bf6d15c6ad7246116e17ab0d175554484b8662068e375"
)
CHECKER_CALL_COUNT = 406
CHECKER_CALL_SURFACE_SHA256 = (
    "8558c332589add8ad99555b5bf4ad2c6ebb3d228a91cda3928f75affeea1178d"
)
TUPLES = (
    (
        "golang.org/x/crypto",
        "v0.38.0",
        "a26a2513c9f4c49c479c1378fd9e7d313032cb9ffc32a1a38dcebd0be1ae9b43",
        "h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw=",
        "h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8=",
    ),
    (
        "golang.org/x/text",
        "v0.25.0",
        "c6022d5be99f60f2428ee0f587172a28d4eeeebb9f36694f4ab42177bcd585b8",
        "h1:WEdwpYrmk1qmdHvhkSTNPm3app7v4rsT8F2UD6+VHIA=",
        "h1:qVyWApTSYLk/drJRO5mDlNYskwQznZmkpV2c8q9zls4=",
    ),
)


EXPECTED_IMPORTS = (
    ("from", "__future__", 0, (("annotations", None),)),
    ("import", (("sys", None),)),
    ("import", (("argparse", None),)),
    ("import", (("ast", None),)),
    ("from", "contextlib", 0, (("ExitStack", None),)),
    ("import", (("hashlib", None),)),
    ("import", (("json", None),)),
    ("import", (("os", None),)),
    ("from", "pathlib", 0, (("Path", None),)),
    ("import", (("re", None),)),
    ("import", (("stat", None),)),
    ("import", (("types", None),)),
    (
        "from",
        "typing",
        0,
        (("Any", None), ("Mapping", None), ("Sequence", None)),
    ),
    ("import", (("unicodedata", None),)),
)

EXPECTED_AUTHORITY = {
    "accountRequired": False,
    "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized": False,
    "authenticationRequired": False,
    "clientCertificateRequired": False,
    "compileAuthorized": False,
    "cookieRequired": False,
    "deploymentAuthorized": False,
    "deviceAuthorized": False,
    "dnsTcpTlsHttpsToExactProxyAuthorized": True,
    "externalAuthenticationRequired": False,
    "gitOperationAuthorized": False,
    "gpgRequired": False,
    "ownerProofRequired": False,
    "ownerRequired": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "productRuntimeNetworkAuthorized": False,
    "publicationAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "sshRequired": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
    "wave19PublicProxy4GetAcquisitionAuthorizedOnce": True,
}


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


def normalized_checker(raw: bytes) -> bytes:
    marker = re.compile(
        br'(SELF_NORMALIZED_SHA256 = \(\n    ")[0-9a-f]{64}("\n\))'
    )
    result, count = marker.subn(
        rb"\g<1>" + b"0" * 64 + rb"\g<2>",
        raw,
    )
    if count != 1:
        raise AssertionError("checker normalization")
    return result


def normalized_runner(raw: bytes) -> bytes:
    marker = re.compile(br'EXPECTED_CHECKER_RAW = "[0-9a-f]{64}"')
    result, count = marker.subn(
        b'EXPECTED_CHECKER_RAW = "' + b"0" * 64 + b'"',
        raw,
    )
    if count != 1:
        raise AssertionError("runner normalization")
    return result


def load_module(raw: bytes) -> types.ModuleType:
    module = types.ModuleType("wave19_acquisition_checker_test_subject")
    module.__dict__.update(
        {
            "__file__": str(ROOT / CHECKER_PATH),
            "__name__": "wave19_acquisition_checker_test_subject",
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


def import_surface(tree: ast.AST) -> tuple[object, ...]:
    result: list[object] = []
    nodes = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for node in nodes:
        if isinstance(node, ast.Import):
            result.append(
                (
                    "import",
                    tuple((alias.name, alias.asname) for alias in node.names),
                )
            )
        else:
            result.append(
                (
                    "from",
                    node.module,
                    node.level,
                    tuple((alias.name, alias.asname) for alias in node.names),
                )
            )
    return tuple(result)


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


def surface_signature(
    source: str,
) -> tuple[tuple[object, ...], int, str]:
    tree = ast.parse(source, filename=CHECKER_PATH)
    visitor = CallVisitor()
    visitor.visit(tree)
    return (
        import_surface(tree),
        len(visitor.calls),
        call_surface_sha256(visitor.calls),
    )


def preload_checker_gate(
    raw: bytes,
    source: str,
    tree: ast.AST,
    permit: object,
) -> dict[str, object]:
    if type(permit) is not dict:
        raise RuntimeError("Wave19 checker test permit schema")
    tool_bindings = permit.get("toolBindings")
    if type(tool_bindings) is not list:
        raise RuntimeError("Wave19 checker test tool bindings")
    checker_bindings = [
        row
        for row in tool_bindings
        if type(row) is dict and row.get("path") == CHECKER_PATH
    ]
    if len(checker_bindings) != 1:
        raise RuntimeError(
            "Wave19 checker test checker binding cardinality"
        )
    binding = checker_bindings[0]
    if (
        set(binding)
        != {"normalizedSha256", "path", "rawSha256", "role"}
        or binding["role"] != "wave19_acquisition_checker"
        or type(binding["rawSha256"]) is not str
        or type(binding["normalizedSha256"]) is not str
        or import_surface(tree) != EXPECTED_IMPORTS
        or surface_signature(source)
        != (
            EXPECTED_IMPORTS,
            CHECKER_CALL_COUNT,
            CHECKER_CALL_SURFACE_SHA256,
        )
        or sha256(raw) != binding["rawSha256"]
        or sha256(normalized_checker(raw))
        != binding["normalizedSha256"]
    ):
        raise RuntimeError("Wave19 checker test preload gate")
    return binding


def identity_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for tuple_order, (
        module,
        version,
        digest,
        mod_h1,
        zip_h1,
    ) in enumerate(TUPLES, 1):
        for kind, expected_h1 in (("mod", mod_h1), ("zip", zip_h1)):
            path = f"/{module}/@v/{version}.{kind}"
            rows.append(
                {
                    "acceptedFileName":
                        f"{tuple_order:03d}-{digest[:20]}.{kind}",
                    "expectedH1": expected_h1,
                    "host": "proxy.golang.org",
                    "kind": kind,
                    "maximumResponseBodyBytes":
                        1_048_576 if kind == "mod" else 16_777_216,
                    "method": "GET",
                    "module": module,
                    "path": path,
                    "port": 443,
                    "requestOrdinal": len(rows) + 1,
                    "selectedByGraphAlgorithm": False,
                    "tupleDigestSha256": digest,
                    "tupleId":
                        f"wave19-{tuple_order:03d}-{digest[:12]}",
                    "tupleOrder": tuple_order,
                    "url": f"https://proxy.golang.org{path}",
                    "version": version,
                }
            )
    return rows


CHECKER_RAW = (ROOT / CHECKER_PATH).read_bytes()
CHECKER_SOURCE = CHECKER_RAW.decode("utf-8")
CHECKER_TREE = ast.parse(CHECKER_SOURCE, filename=CHECKER_PATH)
RUNNER_RAW = (ROOT / RUNNER_PATH).read_bytes()
DECISION_RAW = (ROOT / DECISION_PATH).read_bytes()
DECISION = json.loads(DECISION_RAW)
PERMIT_RAW = (ROOT / PERMIT_PATH).read_bytes()
PERMIT = json.loads(PERMIT_RAW)
PRELOAD_CHECKER_BINDING = preload_checker_gate(
    CHECKER_RAW,
    CHECKER_SOURCE,
    CHECKER_TREE,
    PERMIT,
)
CHECKER = load_module(CHECKER_RAW)


class Wave19AcquisitionCheckerTests(unittest.TestCase):
    maxDiff = None

    def test_01_static_surface_and_mutual_seals_are_exact(self) -> None:
        bindings = {
            row["path"]: row for row in PERMIT["toolBindings"]
        }
        self.assertEqual(
            set(bindings),
            {
                CHECKER_PATH,
                CHECKER_TEST_PATH,
                RUNNER_PATH,
                RUNNER_TEST_PATH,
            },
        )
        checker_binding = bindings[CHECKER_PATH]
        runner_binding = bindings[RUNNER_PATH]
        self.assertEqual(PRELOAD_CHECKER_BINDING, checker_binding)
        test_source = Path(__file__).read_text(encoding="utf-8")
        self.assertLess(
            test_source.index(
                "PRELOAD_CHECKER_BINDING = preload_checker_gate("
            ),
            test_source.index("CHECKER = load_module(CHECKER_RAW)"),
        )
        self.assertEqual(
            sha256(CHECKER_RAW),
            checker_binding["rawSha256"],
        )
        self.assertEqual(
            sha256(normalized_checker(CHECKER_RAW)),
            checker_binding["normalizedSha256"],
        )
        self.assertEqual(
            checker_binding["normalizedSha256"],
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        self.assertEqual(sha256(RUNNER_RAW), runner_binding["rawSha256"])
        self.assertEqual(
            sha256(normalized_runner(RUNNER_RAW)),
            runner_binding["normalizedSha256"],
        )
        self.assertEqual(import_surface(CHECKER_TREE), EXPECTED_IMPORTS)
        self.assertEqual(
            surface_signature(CHECKER_SOURCE),
            (
                EXPECTED_IMPORTS,
                CHECKER_CALL_COUNT,
                CHECKER_CALL_SURFACE_SHA256,
            ),
        )
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(CHECKER_TREE)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(CHECKER_TREE)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertTrue(
            imported_roots.isdisjoint(
                {"socket", "subprocess", "urllib", "requests", "http"}
            )
        )
        reverse = re.findall(
            rb'EXPECTED_CHECKER_RAW = "([0-9a-f]{64})"',
            RUNNER_RAW,
        )
        self.assertEqual(
            reverse,
            [sha256(CHECKER_RAW).encode("ascii")],
        )
        for seal_key in ("rawSha256", "normalizedSha256"):
            mutated_permit = json.loads(json.dumps(PERMIT))
            mutated_binding = next(
                row
                for row in mutated_permit["toolBindings"]
                if row["path"] == CHECKER_PATH
            )
            mutated_binding[seal_key] = "0" * 64
            with (
                self.subTest(preload_seal=seal_key),
                self.assertRaises(RuntimeError),
            ):
                preload_checker_gate(
                    CHECKER_RAW,
                    CHECKER_SOURCE,
                    CHECKER_TREE,
                    mutated_permit,
                )
        same_count_bypasses = (
            CHECKER_SOURCE.replace(
                "exec(code, module.__dict__, module.__dict__)",
                "eval(code, module.__dict__, module.__dict__)",
                1,
            ),
            CHECKER_SOURCE.replace(
                "os.open(self.path, flags)",
                "io.open(self.path, flags)",
                1,
            ),
            CHECKER_SOURCE.replace(
                "sys.stdout.buffer.write(",
                "os.write(",
                1,
            ),
            CHECKER_SOURCE.replace(
                "held.barrier()",
                'held.path.write_text("forbidden")',
                1,
            ),
        )
        for index, changed in enumerate(same_count_bypasses):
            with self.subTest(same_count_bypass=index):
                self.assertNotEqual(changed, CHECKER_SOURCE)
                signature = surface_signature(changed)
                self.assertEqual(signature[1], CHECKER_CALL_COUNT)
                self.assertNotEqual(
                    signature[2],
                    CHECKER_CALL_SURFACE_SHA256,
                )
                mutated_permit = json.loads(json.dumps(PERMIT))
                mutated_binding = next(
                    row
                    for row in mutated_permit["toolBindings"]
                    if row["path"] == CHECKER_PATH
                )
                changed_raw = changed.encode()
                mutated_binding["rawSha256"] = sha256(changed_raw)
                mutated_binding["normalizedSha256"] = sha256(
                    normalized_checker(changed_raw)
                )
                with self.assertRaises(RuntimeError):
                    preload_checker_gate(
                        changed_raw,
                        changed,
                        ast.parse(changed, filename=CHECKER_PATH),
                        mutated_permit,
                    )

        changed_import = CHECKER_SOURCE.replace(
            "import ast\n",
            "import ast\nimport socket\n",
            1,
        )
        self.assertNotEqual(changed_import, CHECKER_SOURCE)
        changed_import_raw = changed_import.encode()
        import_permit = json.loads(json.dumps(PERMIT))
        import_binding = next(
            row
            for row in import_permit["toolBindings"]
            if row["path"] == CHECKER_PATH
        )
        import_binding["rawSha256"] = sha256(changed_import_raw)
        import_binding["normalizedSha256"] = sha256(
            normalized_checker(changed_import_raw)
        )
        with self.assertRaises(RuntimeError):
            preload_checker_gate(
                changed_import_raw,
                changed_import,
                ast.parse(changed_import, filename=CHECKER_PATH),
                import_permit,
            )

    def test_02_repository_and_materialized_permit_seals_are_exact(self) -> None:
        expected = {
            DECISION_PATH: DECISION_RAW_SHA256,
            DECISION_READER_PATH: DECISION_READER_RAW_SHA256,
            DECISION_CHECKER_PATH: DECISION_CHECKER_RAW_SHA256,
            DECISION_TESTS_PATH: DECISION_TESTS_RAW_SHA256,
            WAVE4_CHECKER_PATH: WAVE4_CHECKER_RAW_SHA256,
            WAVE4_RUNNER_PATH: WAVE4_RUNNER_RAW_SHA256,
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(sha256((ROOT / path).read_bytes()), digest)
        self.assertEqual(PERMIT_RAW, canonical(PERMIT))
        without = dict(PERMIT)
        binding = without.pop("contentBinding")
        self.assertEqual(sha256(canonical(without)), binding["sha256"])
        reader = PERMIT["readerDocumentBinding"]
        self.assertEqual(reader["path"], PERMIT_READER_PATH)
        self.assertEqual(
            sha256((ROOT / PERMIT_READER_PATH).read_bytes()),
            reader["rawSha256"],
        )
        bindings = {
            row["path"]: row for row in PERMIT["toolBindings"]
        }
        self.assertEqual(
            PERMIT["runnerBinding"],
            {
                "normalizedSha256":
                    bindings[RUNNER_PATH]["normalizedSha256"],
                "path": RUNNER_PATH,
                "rawSha256": bindings[RUNNER_PATH]["rawSha256"],
            },
        )

    def test_03_exact_four_resource_typed_projection_and_hashes(self) -> None:
        rows = identity_rows()
        self.assertEqual(CHECKER.resource_contract(DECISION), rows)
        self.assertEqual(PERMIT["requestContract"]["resources"], rows)
        self.assertEqual(sha256(canonical(rows)), RESOURCE_SHA256)
        self.assertEqual(
            PERMIT["requestContract"]["resourcesCanonicalSha256"],
            RESOURCE_SHA256,
        )
        self.assertEqual(
            PERMIT["requestContract"]["sourceRequestSetCanonicalSha256"],
            DECISION_REQUEST_SHA256,
        )
        self.assertNotEqual(RESOURCE_SHA256, DECISION_REQUEST_SHA256)
        self.assertEqual(
            sha256(
                canonical(
                    [
                        {
                            "decisionRequest": source,
                            "permitResource": target,
                        }
                        for source, target in zip(
                            DECISION["sourceAcquisitionPreparation"][
                                "requestSet"
                            ],
                            rows,
                        )
                    ]
                )
            ),
            PROJECTION_SHA256,
        )
        self.assertEqual(
            PERMIT["requestContract"][
                "decisionToPermitTypedProjectionCanonicalSha256"
            ],
            PROJECTION_SHA256,
        )
        self.assertEqual(
            PERMIT["decisionBinding"]["typedProjectionCanonicalSha256"],
            PROJECTION_SHA256,
        )
        for module, version, digest, _, _ in TUPLES:
            self.assertEqual(
                sha256(f"{module}\n{version}\n".encode()),
                digest,
            )
        self.assertEqual(
            [row["kind"] for row in rows],
            ["mod", "zip", "mod", "zip"],
        )
        self.assertEqual(
            [row["maximumResponseBodyBytes"] for row in rows],
            [1_048_576, 16_777_216] * 2,
        )
        self.assertEqual(
            [row["requestOrdinal"] for row in rows],
            list(range(1, 5)),
        )
        self.assertTrue(
            all(row["selectedByGraphAlgorithm"] is False for row in rows)
        )

    def test_04_authority_requires_no_identity_or_user_action(self) -> None:
        self.assertEqual(CHECKER.authority(), EXPECTED_AUTHORITY)
        self.assertEqual(PERMIT["authority"], EXPECTED_AUTHORITY)
        true_keys = {
            key for key, value in EXPECTED_AUTHORITY.items() if value is True
        }
        self.assertEqual(
            true_keys,
            {
                "dnsTcpTlsHttpsToExactProxyAuthorized",
                "wave19PublicProxy4GetAcquisitionAuthorizedOnce",
            },
        )
        for key in (
            "accountRequired",
            "authenticationRequired",
            "externalAuthenticationRequired",
            "ownerProofRequired",
            "ownerRequired",
            "repositoryOwnerIdentityProofRequired",
            "sshRequired",
            "gpgRequired",
            "passwordRequired",
            "privateKeyRequired",
            "signatureRequired",
            "tokenRequired",
            "userActionRequired",
            "sourceExtractionAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "compileAuthorized",
            "packageManagerAuthorized",
            "gitOperationAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "productRuntimeNetworkAuthorized",
            "publicationAuthorized",
        ):
            with self.subTest(key=key):
                self.assertIs(PERMIT["authority"][key], False)

    def test_05_resource_limits_and_no_retry_contract_are_exact(self) -> None:
        limits = PERMIT["absoluteResourceLimits"]
        self.assertEqual(limits["maximumRequestCount"], 4)
        self.assertEqual(limits["maximumModResponseBodyBytes"], 1_048_576)
        self.assertEqual(limits["maximumZipResponseBodyBytes"], 16_777_216)
        self.assertEqual(
            limits["maximumAggregateResponseBodyBytes"],
            35_651_584,
        )
        self.assertEqual(
            limits["maximumAggregateModResponseBodyBytes"],
            2_097_152,
        )
        self.assertEqual(
            limits["maximumAggregateZipResponseBodyBytes"],
            33_554_432,
        )
        self.assertEqual(limits["maximumZipEntryCount"], 20_000)
        self.assertEqual(
            limits["maximumZipUncompressedBytes"],
            134_217_728,
        )
        self.assertEqual(
            limits["wholeAttemptDeadlineMilliseconds"],
            600_000,
        )
        request = PERMIT["requestContract"]
        for key in (
            "authenticationAllowed",
            "authorizationHeaderAllowed",
            "proxyAuthorizationHeaderAllowed",
            "cookieAllowed",
            "clientCertificateAllowed",
            "redirectAllowed",
            "alternateHostAllowed",
            "ambientProxyAllowed",
            "requestBodyAllowed",
            "rangeHeaderAllowed",
            "queryOrFragmentAllowed",
            "retryAllowed",
            "retryResumeOrBackfillAllowed",
        ):
            with self.subTest(key=key):
                self.assertIs(request[key], False)

    def test_06_claim_terminal_and_readback_contracts_are_exact(self) -> None:
        one_use = PERMIT["oneUseContract"]
        self.assertEqual(
            one_use["claimPath"],
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-19-v1.claim"
            ),
        )
        self.assertIs(one_use["claimAbsentAtPermitPublication"], True)
        self.assertIs(
            one_use["claimCreatedOExcl0600AndFsyncedBeforeDnsOrNetwork"],
            True,
        )
        self.assertIs(one_use["secondExecutionAllowed"], False)
        self.assertIs(
            one_use["retryResumeBackfillOverwriteOrCleanupAllowed"],
            False,
        )
        terminal = PERMIT["terminalContract"]
        self.assertIs(
            terminal[
                "successRequiresNoActiveOperationAndExact4CommittedCounts"
            ],
            True,
        )
        self.assertEqual(
            terminal["zeroCommittedResponsesWithActiveFetchState"],
            "unknown_after_dispatch",
        )
        self.assertIs(terminal["manifestWrittenLast"], True)
        self.assertIs(terminal["failurePublishesFailureOnly"], True)
        self.assertEqual(
            CHECKER.READBACK_CLAIM_PATH,
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-19-v1-readback.claim"
            ),
        )

    def test_07_primitive_and_verification_contracts_are_pinned(self) -> None:
        self.assertEqual(
            PERMIT["primitiveBindings"],
            [
                {
                    "path": WAVE4_CHECKER_PATH,
                    "rawSha256": WAVE4_CHECKER_RAW_SHA256,
                    "use": "constants_and_validation_contract_only",
                },
                {
                    "path": WAVE4_RUNNER_PATH,
                    "rawSha256": WAVE4_RUNNER_RAW_SHA256,
                    "use": (
                        "h1_go_mod_zip_and_direct_https_"
                        "validation_primitives_only"
                    ),
                },
            ],
        )
        verification = PERMIT["verificationContract"]
        self.assertIs(verification["sourceExtractionAllowed"], False)
        self.assertIs(verification["rawSha256RecordedSeparately"], True)
        self.assertIs(
            verification["zipExactModuleVersionPrefixRequired"],
            True,
        )
        self.assertIs(
            verification["zipSafetyShapeCrcAndModParityRequired"],
            True,
        )
        zip_limits = PERMIT["zipLimits"]
        self.assertIs(
            zip_limits[
                "encryptedSymlinkDirectoryDuplicateOrUnsafeEntriesAllowed"
            ],
            False,
        )
        self.assertEqual(zip_limits["maximumEntryCountPerZip"], 20_000)
        self.assertEqual(
            zip_limits["maximumEntryCountAcrossAllZips"],
            40_000,
        )
        self.assertEqual(zip_limits["maximumEntryNameBytes"], 1_024)
        self.assertEqual(
            zip_limits["maximumUncompressedBytesPerZip"],
            134_217_728,
        )
        self.assertEqual(
            zip_limits["maximumUncompressedBytesAcrossAllZips"],
            268_435_456,
        )
        self.assertEqual(
            verification["goModH1Algorithm"],
            "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod",
        )

    def test_08_invocation_contract_is_exact_and_not_authentication(self) -> None:
        invocation = PERMIT["invocationContract"]
        self.assertEqual(invocation["exactArgv"], ["--execute"])
        self.assertEqual(invocation["runnerPath"], RUNNER_PATH)
        self.assertIs(invocation["additionalArgumentsAllowed"], False)
        self.assertIs(invocation["abbreviatedArgumentsAllowed"], False)
        self.assertIs(invocation["duplicateArgumentsAllowed"], False)
        self.assertIs(
            invocation["executionEntryPointRevalidatesInvocationShape"],
            True,
        )
        self.assertIs(invocation["invocationChecksAuthenticateOrigin"], False)
        self.assertIs(
            invocation["invocationOriginAttestationProvided"],
            False,
        )
        self.assertIs(invocation["externalLauncherReceiptRequired"], False)

    def test_09_generator_reproduces_the_materialized_permit(self) -> None:
        generated = CHECKER.content_bound(
            CHECKER.permit_payload(
                decision=DECISION,
                checker_raw_sha256=sha256(CHECKER_RAW),
                runner_raw_sha256=sha256(RUNNER_RAW),
                runner_normalized_sha256=sha256(
                    normalized_runner(RUNNER_RAW)
                ),
            )
        )
        self.assertEqual(generated, PERMIT)
        self.assertEqual(canonical(generated), PERMIT_RAW)
        for bad in (
            "",
            "0" * 63,
            "G" * 64,
            0,
            False,
        ):
            with (
                self.subTest(bad=bad),
                self.assertRaisesRegex(CHECKER.CheckError, "^E_RUNNER_BINDING$"),
            ):
                CHECKER.permit_payload(
                    decision=DECISION,
                    checker_raw_sha256=bad,
                    runner_raw_sha256=sha256(RUNNER_RAW),
                    runner_normalized_sha256=sha256(
                        normalized_runner(RUNNER_RAW)
                    ),
                )
        with self.assertRaisesRegex(
            CHECKER.CheckError,
            "^E_RUNNER_BINDING$",
        ):
            CHECKER.permit_payload(
                decision=DECISION,
                checker_raw_sha256=sha256(CHECKER_RAW),
                runner_raw_sha256=sha256(RUNNER_RAW),
                runner_normalized_sha256="0" * 64,
            )

    def test_10_strict_json_rejects_duplicates_floats_and_noncanonical(self) -> None:
        self.assertEqual(CHECKER.strict_json(PERMIT_RAW), PERMIT)
        for raw in (
            b'{"x":1.0}\n',
            b'{"x":NaN}\n',
            b'{"x":Infinity}\n',
            b'{"x":1,"x":1}\n',
            b'{ "x": 1 }\n',
            b'{"x":1}',
            b"[]\n",
            b"\xff",
        ):
            with (
                self.subTest(raw=raw),
                self.assertRaisesRegex(CHECKER.CheckError, "^E_JSON$"),
            ):
                CHECKER.strict_json(raw)

    def test_11_reserved_namespace_rejects_all_wave19_names(self) -> None:
        reserved = object.__new__(CHECKER.HeldReservedNamespace)
        clean = [".wave-18-v1.claim", "wave-18-v1"]
        with mock.patch.object(reserved, "_names", return_value=clean):
            reserved.observe_absent()
        for name in (
            ".wave-19-v1.claim",
            "wave-19-v1",
            ".wave-19-v1-readback.claim",
            ".wave-19-v1-staging-test",
            ".wave-19-readback-v1-test",
        ):
            with (
                self.subTest(name=name),
                mock.patch.object(reserved, "_names", return_value=[name]),
                self.assertRaisesRegex(CHECKER.CheckError, "^E_NAMESPACE$"),
            ):
                reserved.observe_absent()

    def test_12_terminal_namespace_rejects_broken_symlink_names(self) -> None:
        terminal = object.__new__(CHECKER.HeldTerminalNamespace)
        with mock.patch.object(terminal, "_names", return_value=[]):
            terminal.observe_absent()
        reserved = (
            CHECKER.RECEIPT_PATH,
            CHECKER.FAILURE_PATH,
            CHECKER.MANIFEST_PATH,
            CHECKER.READBACK_PATH,
            CHECKER.READBACK_MANIFEST_PATH,
        )
        for path in reserved:
            name = Path(path).name
            with (
                self.subTest(name=name),
                mock.patch.object(terminal, "_names", return_value=[name]),
                self.assertRaisesRegex(
                    CHECKER.CheckError,
                    "^E_TERMINAL_NAMESPACE$",
                ),
            ):
                terminal.observe_absent()

    def test_13_runner_validation_rejects_reverse_pin_and_surface_drift(
        self,
    ) -> None:
        CHECKER.validate_runner(RUNNER_RAW, CHECKER_RAW)
        mutations = (
            RUNNER_RAW.replace(
                sha256(CHECKER_RAW).encode(),
                b"0" * 64,
                1,
            ),
            RUNNER_RAW.replace(b"ImmutablePhaseLedger", b"RemovedPhaseLedger"),
            RUNNER_RAW.replace(
                b"RENAME_EXCL = 0x00000004",
                b"RENAME_EXCL = 0x00000000",
                1,
            ),
            RUNNER_RAW + b'\nvalue = "Authorization"\n',
        )
        for index, raw in enumerate(mutations):
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(CHECKER.CheckError, "^E_RUNNER$"),
            ):
                CHECKER.validate_runner(raw, CHECKER_RAW)

    def test_14_live_evaluate_is_dry_read_only_and_semantically_exact(
        self,
    ) -> None:
        real_open = os.open
        opened: list[tuple[object, int]] = []

        def observed_open(path: object, flags: int, *args: object, **kwargs: object):
            opened.append((path, flags))
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(CHECKER.os, "open", side_effect=observed_open):
            values, summary = CHECKER.evaluate(True, ROOT)
        self.assertEqual(values["permit"], PERMIT)
        self.assertEqual(
            values["decision"]["contentBinding"]["sha256"],
            DECISION_CONTENT_SHA256,
        )
        self.assertEqual(values["decision"]["identityResolution"]["tupleCount"], 2)
        self.assertIs(
            values["decision"]["identityResolution"]["tuples"][0][
                "selectedByGraphAlgorithm"
            ],
            False,
        )
        self.assertEqual(summary["requestCount"], 4)
        self.assertEqual(summary["fileWriteCount"], 0)
        self.assertIs(summary["networkUsed"], False)
        self.assertIs(summary["runnerInvoked"], False)
        self.assertIs(summary["externalAuthenticationRequired"], False)
        self.assertIs(summary["userActionRequired"], False)
        forbidden = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        self.assertTrue(opened)
        for path, flags in opened:
            with self.subTest(path=path):
                self.assertEqual(flags & forbidden, 0)

    def test_15_error_and_main_dry_outputs_never_request_authentication(
        self,
    ) -> None:
        error = CHECKER.error_document("E_TEST")
        self.assertIs(error["externalAuthenticationRequired"], False)
        self.assertIs(error["userActionRequired"], False)
        self.assertIs(error["networkAuthorized"], False)
        self.assertIs(error["fileWriteAuthorized"], False)

        output = types.SimpleNamespace(buffer=io.BytesIO())
        with (
            mock.patch.object(CHECKER, "evaluate", return_value=(
                {"permit": PERMIT},
                {
                    "status": "authorized_not_consumed",
                    "requestCount": 4,
                    "fileWriteCount": 0,
                    "networkUsed": False,
                },
            )),
            mock.patch.object(CHECKER.sys, "stdout", output),
        ):
            self.assertEqual(CHECKER.main(["--print-permit"]), 0)
        self.assertEqual(output.buffer.getvalue(), PERMIT_RAW)

    def test_16_permit_decision_and_bool_int_mutations_fail_closed(
        self,
    ) -> None:
        real_permit_payload = CHECKER.permit_payload

        def mutated_permit(kind: str):
            def build(*args: object, **kwargs: object) -> dict[str, object]:
                payload = real_permit_payload(*args, **kwargs)
                if kind == "permit_extra":
                    payload["unknown"] = False
                elif kind == "authority_extra":
                    payload["authority"]["unknown"] = False
                elif kind == "authority_bool_int":
                    payload["authority"]["authenticationRequired"] = 0
                elif kind == "request_count_bool":
                    payload["requestContract"]["requestCount"] = True
                else:
                    raise AssertionError(kind)
                return payload

            return build

        for kind in (
            "permit_extra",
            "authority_extra",
            "authority_bool_int",
            "request_count_bool",
        ):
            with (
                self.subTest(kind=kind),
                mock.patch.object(
                    CHECKER,
                    "permit_payload",
                    side_effect=mutated_permit(kind),
                ),
                self.assertRaisesRegex(CHECKER.CheckError, "^E_PERMIT$"),
            ):
                CHECKER.evaluate(True, ROOT)

        for name, mutate in (
            (
                "ordinal_bool",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ][0].__setitem__("requestOrdinal", True),
            ),
            (
                "maximum_bool",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ][1].__setitem__("maximumResponseBytes", False),
            ),
            (
                "selected_int",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ][2].__setitem__("selectedByGraphAlgorithm", 0),
            ),
            (
                "cross_tuple_h1",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ][3].__setitem__(
                    "expectedH1",
                    value["sourceAcquisitionPreparation"]["requestSet"][1][
                        "expectedH1"
                    ],
                ),
            ),
            (
                "same_count_reorder",
                lambda value: value["sourceAcquisitionPreparation"][
                    "requestSet"
                ].__setitem__(
                    slice(0, 2),
                    list(
                        reversed(
                            value["sourceAcquisitionPreparation"][
                                "requestSet"
                            ][:2]
                        )
                    ),
                ),
            ),
        ):
            mutated = json.loads(json.dumps(DECISION))
            mutate(mutated)
            with (
                self.subTest(projection_mutation=name),
                self.assertRaisesRegex(
                    CHECKER.CheckError,
                    "^E_DECISION_PROJECTION$",
                ),
            ):
                CHECKER.resource_contract(mutated)

        duplicate = json.loads(json.dumps(PERMIT))
        duplicate["toolBindings"][0]["path"] = duplicate[
            "decisionBinding"
        ]["files"][0]["path"]
        with self.assertRaisesRegex(
            CHECKER.CheckError,
            "^E_AUTHORITY_PATH$",
        ):
            CHECKER.AuthorityFiles(ROOT, duplicate).__enter__()

        decision_checker = CHECKER.load_decision_checker(
            (ROOT / DECISION_CHECKER_PATH).read_bytes()
        )
        live_decision = decision_checker.run_check(ROOT)
        for kind in (
            "decision_extra",
            "decision_authority_bool_int",
            "decision_count_bool",
        ):
            mutated = json.loads(json.dumps(live_decision))
            if kind == "decision_extra":
                mutated["unknown"] = False
            elif kind == "decision_authority_bool_int":
                mutated["authority"]["authenticationRequired"] = 0
            else:
                mutated["identityResolution"]["tupleCount"] = True
            substitute = types.SimpleNamespace(
                run_check=lambda _root, value=mutated: value,
                expected_request_set=decision_checker.expected_request_set,
            )
            with (
                self.subTest(kind=kind),
                mock.patch.object(
                    CHECKER,
                    "load_decision_checker",
                    return_value=substitute,
                ),
                self.assertRaisesRegex(CHECKER.CheckError, "^E_DECISION$"),
            ):
                CHECKER.evaluate(True, ROOT)

        package_paths = (
            PERMIT_READER_PATH,
            PERMIT_PATH,
            CHECKER_PATH,
            RUNNER_PATH,
            CHECKER_TEST_PATH,
            RUNNER_TEST_PATH,
        )
        stale_tokens = (
            ("wave" + "18PublicProxy6GetAcquisitionAuthorizedOnce").encode(),
            ("aetherlink.wave" + "18-source-acquisition").encode(),
            ("g2-pion-rung3-wave" + "18-6-resource").encode(),
            ("combinedFixedPoint" + "V16").encode(),
            ("wave17" + "NamespaceAnchor").encode(),
            ("exact_6_resource_one_use_wave" + "18").encode(),
            (
                "successRequiresNoActiveOperationAndExact"
                + "6CommittedCounts"
            ).encode(),
            (".wave-" + "18-v1-staging-").encode(),
            ("wave-" + "18-v1/accepted").encode(),
            ("wave-" + "18-v1/evidence.json").encode(),
            (".wave-" + "18-v1-readback.claim").encode(),
            (".wave-" + "18-readback-v1-").encode(),
            (
                "bounded-dependency-source-acquisition-wave" + "18-"
            ).encode(),
            ("golang.org/x/mod@" + "v0." + "24.0").encode(),
            ("golang.org/x/net@" + "v0." + "40.0").encode(),
            ("golang.org/x/sync@" + "v0." + "14.0").encode(),
            ("v0." + "24.0").encode(),
            ("v0." + "40.0").encode(),
            ("v0." + "14.0").encode(),
            ("001-" + "bb2025870bcef7a0c287").encode(),
            ("002-" + "3c84a9eecca520aed886").encode(),
            ("003-" + "4615480e24f0c4184e4c").encode(),
            ("wave" + "17PublicProxy2GetAcquisitionAuthorizedOnce").encode(),
            ("aetherlink.wave" + "17-source-acquisition").encode(),
            ("g2-pion-rung3-wave" + "17-2-resource").encode(),
            ("combinedFixedPoint" + "V15").encode(),
            ("wave16" + "NamespaceAnchor").encode(),
            ("golang.org/x/" + "tools").encode(),
            ("v0." + "33.0").encode(),
            ("8bd04e" + "a612ce").encode(),
            ("exact_2_resource_one_use_wave" + "18").encode(),
        )
        for path in package_paths:
            raw = (ROOT / path).read_bytes()
            for token in stale_tokens:
                with self.subTest(path=path, stale=token):
                    self.assertNotIn(token, raw)


if __name__ == "__main__":
    unittest.main()
